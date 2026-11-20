"""Tonal shapes: paint a value band of a target as hard-edged puddles, one flat wash per shape.

This is the method of layered-shape chiaroscuro (references/styles/layered-shape-chiaroscuro.md): the picture is
seen as nested tonal shapes, and each band is laid as separate puddles on dry paper that dry with a crisp rim.

For one band (every place of the target darker than --threshold):

  1. The band's mask is smoothed, cleaned and split into shapes. Shapes smaller than --min-area are dropped; holes
     smaller than --min-hole are filled. The holes that remain are lights the band paints round.
  2. Each shape gets one mix, solved from what the sheet still lacks there (target absorbance less the look's), at
     the --percentile of that gap inside the shape: a flat wash may not bury the shape's lightest part.
  3. Each shape is laid as a painter lays a puddle: the contour (and the contour of every hole) is cut with a small
     round set in by its own radius, and the inside is flooded with rows of a larger round while the cut is wet.
     The shape is worked in horizontal stripes, cut then flood, so no cut dries before the flood reaches it.
  4. Where the target turns gently across the shape's edge (its value range over a small window is under
     --soft-range), the edge is softened while wet with a clean brush drained to 0.45. Where the target has a real
     edge (a cast shadow, hair against skin), the edge is left to dry crisp.
  5. Shapes too thin for the cut brush are drawn as one stroke along their centre line.

--variegated lays the shape's flood in chunks of about 60 pixels, each with the mix solved under it, capped by
--cap: the first wash of the method, one wet wash whose colour changes across the sheet.

Usage:
    tonal_shapes.py <target.png> <output pass.json> --sheet W,H --paints yellow_ochre,burnt_sienna,...
        --threshold 0.72 [--look look.png] [--blur 3] [--min-area 80] [--min-hole 40] [--cut 3.5] [--fill 8]
        [--percentile 20] [--least 0.04] [--gain 1.0] [--soft-range 0.10] [--stripe 70] [--variegated]
        [--cap 0.3] [--exclude x0,y0,x1,y1 ...] [--preview preview.png] [--no-dry]

Without --look the sheet is taken to be bare paper, so on a painting begun with a printed ground (`new --ground`) give
a look even before the first band; a look is measured as in measured_layers.py.

Run it with the Python that the watercolor tool uses, beside measured_layers.py and shape_strokes.py.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw
from torch.nn import functional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import itertools

from measured_layers import PAPER, absorbance, paint_absorption, sheet_paper, solve_mix, to_load
from shape_strokes import centre_lines, half_width, thin

LUMA = np.array([0.2126, 0.7152, 0.0722])
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Marching squares: for each case (tl=8, tr=4, br=2, bl=1 inside), the cell edges each contour segment joins.
SEGMENTS = {
    1: [("L", "B")],
    2: [("B", "R")],
    3: [("L", "R")],
    4: [("T", "R")],
    5: [("T", "R"), ("L", "B")],
    6: [("T", "B")],
    7: [("T", "L")],
    8: [("T", "L")],
    9: [("T", "B")],
    10: [("T", "L"), ("B", "R")],
    11: [("T", "R")],
    12: [("L", "R")],
    13: [("B", "R")],
    14: [("L", "B")],
}


def blurred(image: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur of a float image with values 0 to 1 (or 3-channel absorbance), per channel."""
    if sigma <= 0:
        return image
    radius = int(3 * sigma) + 1
    offsets = torch.arange(-radius, radius + 1, dtype=torch.float64)
    kernel = torch.exp(-(offsets**2) / (2 * sigma**2))
    kernel /= kernel.sum()
    channels = image[..., None] if image.ndim == 2 else image
    tensor = torch.from_numpy(np.ascontiguousarray(np.moveaxis(channels, -1, 0), dtype=np.float64))[:, None]
    tensor = functional.conv2d(
        functional.pad(tensor, (radius, radius, 0, 0), mode="replicate"), kernel.view(1, 1, 1, -1)
    )
    tensor = functional.conv2d(
        functional.pad(tensor, (0, 0, radius, radius), mode="replicate"), kernel.view(1, 1, -1, 1)
    )
    out = np.moveaxis(tensor[:, 0].numpy(), 0, -1)
    return out[..., 0] if image.ndim == 2 else out


def labels(mask: np.ndarray) -> np.ndarray:
    """Connected shapes (8-connected) numbered from 1, background 0."""
    height, width = mask.shape
    inside = torch.from_numpy(mask).to(DEVICE)
    big = float(height * width + 1)
    current = torch.where(
        inside, torch.arange(height * width, device=DEVICE, dtype=torch.float32).view(height, width), big
    )
    while True:
        pooled = -functional.max_pool2d(-current[None, None], 3, 1, 1)[0, 0]
        updated = torch.where(inside, torch.minimum(current, pooled), current)
        if torch.equal(updated, current):
            break
        current = updated
    values = current.cpu().numpy()
    out = np.zeros(mask.shape, dtype=np.int32)
    unique = np.unique(values[mask])
    lookup = {value: index + 1 for index, value in enumerate(unique)}
    out[mask] = np.vectorize(lookup.get)(values[mask])
    return out


def morph(mask: np.ndarray, radius: int, grow: bool) -> np.ndarray:
    tensor = torch.from_numpy(mask.astype(np.float32))[None, None]
    for _ in range(radius):
        if grow:
            tensor = functional.max_pool2d(functional.pad(tensor, (1, 1, 1, 1), value=0.0), 3, stride=1)
        else:
            tensor = -functional.max_pool2d(-functional.pad(tensor, (1, 1, 1, 1), value=0.0), 3, stride=1)
    return tensor[0, 0].numpy() > 0.5


def inset(mask: np.ndarray, radius: float) -> np.ndarray:
    """The part of a shape at least `radius` from its edge (a round erosion)."""
    return half_width(mask, math.ceil(radius) + 2) > radius


def contours(mask: np.ndarray) -> list[np.ndarray]:
    """Closed outlines of a mask (outer edges and holes) as arrays of (x, y), by marching squares on a softened mask."""
    field = np.pad(mask.astype(np.float32), 2)
    field = blurred(field, 0.8)
    inside = field > 0.5
    case = inside[:-1, :-1] * 8 + inside[:-1, 1:] * 4 + inside[1:, 1:] * 2 + inside[1:, :-1] * 1
    points: dict[tuple, tuple[float, float]] = {}

    def edge_point(key):
        if key not in points:
            kind, y, x = key
            if kind == "h":
                a, b = field[y, x], field[y, x + 1]
                t = 0.5 if a == b else (0.5 - a) / (b - a)
                points[key] = (x + t - 2, y - 2)
            else:
                a, b = field[y, x], field[y + 1, x]
                t = 0.5 if a == b else (0.5 - a) / (b - a)
                points[key] = (x - 2, y + t - 2)
        return points[key]

    def key_of(side, y, x):
        return {"T": ("h", y, x), "B": ("h", y + 1, x), "L": ("v", y, x), "R": ("v", y, x + 1)}[side]

    segments, touching = [], {}
    for y, x in zip(*np.nonzero((case > 0) & (case < 15))):
        for a, b in SEGMENTS[int(case[y, x])]:
            pair = (key_of(a, y, x), key_of(b, y, x))
            for key in pair:
                touching.setdefault(key, []).append(len(segments))
            segments.append(pair)
    used = [False] * len(segments)
    loops = []
    for start in range(len(segments)):
        if used[start]:
            continue
        used[start] = True
        first, key = segments[start]
        loop = [edge_point(first)]
        while key != first:
            loop.append(edge_point(key))
            following = [index for index in touching[key] if not used[index]]
            if not following:
                break
            used[following[0]] = True
            a, b = segments[following[0]]
            key = b if a == key else a
        if len(loop) >= 6:
            loops.append(np.array(loop))
    return loops


def resampled(loop: np.ndarray, step: float = 3.0) -> np.ndarray:
    """Points every `step` pixels along a closed loop, lightly smoothed."""
    closed = np.vstack([loop, loop[:1]])
    lengths = np.hypot(*np.diff(closed, axis=0).T)
    distance = np.concatenate([[0], np.cumsum(lengths)])
    if distance[-1] < step * 2:
        return loop
    at = np.arange(0, distance[-1], step)
    points = np.stack([np.interp(at, distance, closed[:, 0]), np.interp(at, distance, closed[:, 1])], 1)
    padded = np.vstack([points[-1:], points, points[:1]])
    return (padded[:-2] + points + padded[2:]) / 3


def runs_of_stripe(points: np.ndarray, top: float, bottom: float, longest: int = 90) -> list[np.ndarray]:
    """The stretches of a closed loop that lie between two heights, split to at most `longest` points."""
    inside = (points[:, 1] >= top) & (points[:, 1] < bottom)
    if inside.all():
        pieces = [points]
    else:
        start = int(np.argmin(inside))  # an outside point: begin there so no stretch wraps round
        order = np.roll(np.arange(len(points)), -start)
        pieces, current = [], []
        for index in order:
            if inside[index]:
                current.append(points[index])
            elif current:
                pieces.append(np.array(current))
                current = []
        if current:
            pieces.append(np.array(current))
    out = []
    for piece in pieces:
        for begin in range(0, len(piece), longest):
            chunk = piece[max(0, begin - 1) : begin + longest]
            if len(chunk) >= 2:
                out.append(chunk)
    return out


def path(points: np.ndarray, pressure: float = 0.9) -> list[list[float]]:
    return [[round(float(x), 1), round(float(y), 1), pressure] for x, y in points]


MAX_STRENGTH = 7.8


def load(size: float, pigments: dict, water: float = 0.95) -> dict:
    total = sum(pigments.values())
    if total > MAX_STRENGTH:
        # Above about 3.5 a load is paste: it skips on the grain and dries as speckle, not as a dark wash.
        pigments = {name: round(amount * MAX_STRENGTH / total, 3) for name, amount in pigments.items()}
    return {
        "action": "load",
        "brush": "round",
        "hair": "squirrel",
        "size": round(size, 2),
        "pigments": pigments,
        "water": water,
    }


def mix_for(gap: np.ndarray, region: np.ndarray, percentile: float, absorption, cap: float | None):
    """The paints that lay, over a region, the given percentile of what it still lacks (in linear units)."""
    values = gap[region]
    if not len(values):
        return {}, 0.0
    scalar = values @ LUMA
    amount = float(np.percentile(scalar, percentile))
    if cap is not None:
        amount = min(amount, cap)
    mean = values.mean(0)
    if amount <= 0 or mean @ LUMA <= 0:
        return {}, 0.0
    return solve_mix(mean * amount / (mean @ LUMA), absorption), amount


def build(arguments) -> tuple[list[dict], np.ndarray]:
    width, height = (int(part) for part in arguments.sheet.split(","))
    absorption = paint_absorption(arguments.paints.split(","))
    target = np.asarray(Image.open(arguments.target).convert("RGB").resize((width, height), Image.Resampling.LANCZOS))
    target = target.astype(np.float64)
    if arguments.look:
        sheet = np.asarray(Image.open(arguments.look).convert("RGB").resize((width, height), Image.Resampling.LANCZOS))
        sheet = sheet.astype(np.float64)
        paper = sheet_paper(arguments.look)
    else:
        sheet = np.broadcast_to(PAPER, target.shape).copy()
        paper = PAPER
    gap = np.clip(blurred(absorbance(target, PAPER), 1.5) - blurred(absorbance(sheet, paper), 1.5), 0.0, None)
    value = blurred((target @ LUMA) / (PAPER @ LUMA), arguments.blur)
    sharp = blurred((target @ LUMA) / (PAPER @ LUMA), 1.0)
    window = torch.from_numpy(sharp.astype(np.float32))[None, None]
    radius = 4
    spread = (
        functional.max_pool2d(window, 2 * radius + 1, 1, radius)
        + functional.max_pool2d(-window, 2 * radius + 1, 1, radius)
    )[0, 0].numpy()

    mask = value < arguments.threshold
    for box in arguments.exclude:
        x0, y0, x1, y1 = (int(part) for part in box.split(","))
        mask[y0:y1, x0:x1] = False
    mask = morph(morph(mask, 1, False), 1, True)
    mask = morph(morph(mask, 2, True), 2, False)
    holes = labels(~mask)
    for index in range(1, holes.max() + 1):
        hole = holes == index
        if hole.sum() < arguments.min_hole:
            mask |= hole
    shapes = labels(mask)

    actions: list[dict] = []
    layer = np.zeros(target.shape)
    tops = []
    for index in range(1, shapes.max() + 1):
        region = shapes == index
        if region.sum() >= arguments.min_area:
            tops.append((int(np.nonzero(region)[0].min()), index))
    # Backruns go into the largest shapes inside --backrun-region, while their own wash is still wet.
    backrun_shapes = set()
    if arguments.backruns:
        x0b, y0b, x1b, y1b = (int(part) for part in arguments.backrun_region.split(","))
        sizes = []
        for _, index in tops:
            region = shapes == index
            ys, xs = np.nonzero(region)
            if x0b <= xs.mean() <= x1b and y0b <= ys.mean() <= y1b:
                sizes.append((int(region.sum()), index))
        backrun_shapes = {index for _, index in sorted(sizes, reverse=True)[: arguments.backruns]}
    for _, index in sorted(tops):
        region = shapes == index
        mix, amount = mix_for(gap, region, arguments.percentile, absorption, arguments.cap)
        if amount < arguments.least and not arguments.variegated:
            continue
        rows_at, cols_at = np.nonzero(region)
        y0, y1, x0, x1 = rows_at.min(), rows_at.max() + 1, cols_at.min(), cols_at.max() + 1
        pad = 6
        y0p, x0p = max(0, y0 - pad), max(0, x0 - pad)
        local = region[y0p : y1 + pad, x0p : x1 + pad]
        cut_mask = inset(local, arguments.cut)
        if not cut_mask.any():
            actions += centre_line_strokes(local, x0p, y0p, mix, arguments)
            layer[region] += solved_absorbance(mix, absorption)
            continue
        fill_size = arguments.fill
        fill_mask = inset(local, fill_size)
        if fill_mask.sum() < 4:
            fill_size, fill_mask = arguments.cut, cut_mask
        cut_loops = [resampled(loop) + [x0p, y0p] for loop in contours(cut_mask)]
        edge_loops = [resampled(loop) + [x0p, y0p] for loop in contours(local)]
        for top in range(y0, y1, arguments.stripe):
            bottom = top + arguments.stripe
            for loop in cut_loops:
                for piece in runs_of_stripe(loop, top, bottom):
                    piece_mix = mix
                    if arguments.variegated:
                        piece_mix, _ = mix_for(
                            gap, near(piece, region, arguments.cut * 2), arguments.percentile, absorption, arguments.cap
                        )
                    if piece_mix:
                        # The cut is loaded at the flood's strength: it merges with the flood while wet, and a
                        # stronger small-brush load dries as a drawn outline round every shape.
                        actions.append(
                            load(arguments.cut, to_load(piece_mix, arguments.gain, fill_size), arguments.water)
                        )
                        actions.append({"action": "stroke", "path": path(piece), "speed": 160, "smooth": True})
            actions += flood_rows(fill_mask, x0p, y0p, top, bottom, fill_size, mix, gap, region, absorption, arguments)
            for loop in edge_loops:
                for piece in runs_of_stripe(loop, top, bottom):
                    actions += soften(piece, region, spread, arguments)
        if index in backrun_shapes:
            # only where this band is the last layer: a later, darker band would bury the bloom
            final = local & (value[y0p : y0p + local.shape[0], x0p : x0p + local.shape[1]] >= arguments.backrun_floor)
            actions += backruns_in(final, x0p, y0p)
        layer[region] += solved_absorbance(mix, absorption)
    if not arguments.no_dry:
        actions.append({"action": "dry"})
    predicted = np.clip(sheet * np.exp(-layer), 0, 255)
    return actions, predicted


def backruns_in(local: np.ndarray, x0p: int, y0p: int) -> list[dict]:
    """Wait for the shape's shine to go at its deepest point, then drop clear water there and at a second deep point:
    the water floods back into the drying wash and dries as a backrun: a pale centre inside a dark rim that is
    smoothly lobed, not frilled or branched (film 0.08, dwell 0.8, a size 6 round, full)."""
    depth = half_width(local, 30)
    if depth.max() < 8:
        return []
    y, x = np.unravel_index(np.argmax(depth), depth.shape)
    away = depth * (np.hypot(*np.indices(depth.shape) - np.array([y, x])[:, None, None]) > 24)
    points = [(x, y)]
    if away.max() >= 8:
        y2, x2 = np.unravel_index(np.argmax(away), away.shape)
        points.append((x2, y2))
    actions = [
        {"action": "wait", "seconds": 150, "at": [int(x + x0p), int(y + y0p)], "film": 0.08},
        load(6.0, {}, water=1.0),
    ]
    for px, py in points:
        actions.append({"action": "stroke", "path": [[int(px + x0p), int(py + y0p), 0.8]], "dwell": 0.8})
    return actions


def solved_absorbance(mix: dict, absorption) -> np.ndarray:
    return sum((np.array(absorption[name]) * amount for name, amount in mix.items()), np.zeros(3))


def near(piece: np.ndarray, region: np.ndarray, reach: float) -> np.ndarray:
    """The part of a shape within `reach` of a run of points."""
    height, width = region.shape
    canvas = Image.new("L", (width, height), 0)
    ImageDraw.Draw(canvas).line([tuple(point) for point in piece.tolist()], fill=255, width=max(1, int(reach * 2)))
    return region & (np.asarray(canvas) > 0)


def flood_rows(fill_mask, x0p, y0p, top, bottom, size, mix, gap, region, absorption, arguments) -> list[dict]:
    """Rows one radius apart inside the shape, set in by the brush radius, alternating direction."""
    actions, forward, travelled = [], True, 1e9
    first = math.ceil((top - y0p) / size) * size
    for local_y in np.arange(first, fill_mask.shape[0], size * 0.95):
        y = local_y + y0p
        if y < top or y >= bottom:
            continue
        row = fill_mask[min(round(local_y), fill_mask.shape[0] - 1)]
        edges = np.flatnonzero(np.diff(np.concatenate([[0], row.astype(np.int8), [0]])))
        for start, end in zip(edges[::2], edges[1::2]):
            a, b = start + x0p, end - 1 + x0p
            pieces = [(a, b)]
            if arguments.variegated and b - a > 90:
                cuts = np.linspace(a, b, math.ceil((b - a) / 60) + 1)
                pieces = list(itertools.pairwise(cuts))
            if not forward:
                pieces = [(right, left) for left, right in reversed(pieces)]
            for left, right in pieces:
                piece_mix = mix
                if arguments.variegated:
                    strip = np.zeros(region.shape, bool)
                    lo, hi = sorted((int(left), int(right)))
                    strip[max(0, int(y - size)) : int(y + size) + 1, max(0, lo - int(size)) : hi + int(size) + 1] = True
                    piece_mix, _ = mix_for(gap, region & strip, arguments.percentile, absorption, arguments.cap)
                    travelled = 1e9
                if not piece_mix:
                    continue
                if travelled > 420:
                    actions.append(load(size, to_load(piece_mix, arguments.gain, size), arguments.water))
                    travelled = 0
                points = [
                    [round(float(left), 1), round(float(y), 1), 0.9],
                    [round(float(right), 1), round(float(y), 1), 0.9],
                ]
                if abs(right - left) < 1:
                    actions.append({"action": "stroke", "path": [points[0]], "dwell": 0.25})
                else:
                    actions.append({"action": "stroke", "path": points, "speed": 240, "smooth": False})
                travelled += abs(right - left)
        forward = not forward
    return actions


def soften(piece: np.ndarray, region: np.ndarray, spread: np.ndarray, arguments) -> list[dict]:
    """A damp clean brush along the stretches of an edge where the target turns gently."""
    height, width = region.shape
    ys = np.clip(np.round(piece[:, 1]).astype(int), 0, height - 1)
    xs = np.clip(np.round(piece[:, 0]).astype(int), 0, width - 1)
    gentle = spread[ys, xs] < arguments.soft_range
    actions, start = [], None
    for index in range(len(piece) + 1):
        inside = index < len(piece) and gentle[index]
        if inside and start is None:
            start = index
        elif not inside and start is not None:
            if index - start >= 4:
                run = piece[start:index]
                tangent = np.gradient(run, axis=0)
                normal = np.stack([-tangent[:, 1], tangent[:, 0]], 1)
                normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-9
                probe = np.round(run + normal * 3).astype(int)
                probe[:, 0] = np.clip(probe[:, 0], 0, width - 1)
                probe[:, 1] = np.clip(probe[:, 1], 0, height - 1)
                outward = 1.0 if (~region[probe[:, 1], probe[:, 0]]).mean() >= 0.5 else -1.0
                moved = run + normal * outward * 2.0
                actions.append(load(4.0, {}, water=0.45))
                actions.append({"action": "stroke", "path": path(moved, 0.6), "speed": 140, "smooth": True})
            start = None
    return actions


def centre_line_strokes(local: np.ndarray, x0p: int, y0p: int, mix: dict, arguments) -> list[dict]:
    distance = half_width(local, 12)
    actions = []
    for line in centre_lines(thin(local)):
        widths = [distance[y, x] for y, x in line]
        size = float(np.clip(np.median(widths), 1.2, arguments.cut))
        actions.append(load(size, to_load(mix, arguments.gain, size)))
        points = [[int(x + x0p), int(y + y0p)] for y, x in line][::3] + [
            [int(line[-1][1] + x0p), int(line[-1][0] + y0p)]
        ]
        if len(points) < 2:
            actions.append({"action": "stroke", "path": [[points[0][0], points[0][1], 0.9]], "dwell": 0.25})
        else:
            actions.append({"action": "stroke", "path": [[x, y, 0.9] for x, y in points], "speed": 120, "smooth": True})
    return actions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--paints", required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--look")
    parser.add_argument("--blur", type=float, default=3.0)
    parser.add_argument("--min-area", type=int, default=80)
    parser.add_argument("--min-hole", type=int, default=40)
    parser.add_argument("--cut", type=float, default=3.5)
    parser.add_argument("--fill", type=float, default=8.0)
    parser.add_argument("--percentile", type=float, default=20.0)
    parser.add_argument("--least", type=float, default=0.04)
    parser.add_argument("--gain", type=float, default=1.0)
    parser.add_argument(
        "--water",
        type=float,
        default=0.95,
        help="brush fullness for cut and flood; lower it for dark bands so the film stays shallow",
    )
    parser.add_argument("--soft-range", type=float, default=0.10)
    parser.add_argument("--stripe", type=int, default=70)
    parser.add_argument("--variegated", action="store_true")
    parser.add_argument("--cap", type=float)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--backruns", type=int, default=0, help="how many of the band's largest shapes get backruns")
    parser.add_argument(
        "--backrun-region",
        default="0,0,100000,100000",
        help="x0,y0,x1,y1: only shapes whose centre lies inside it get backruns",
    )
    parser.add_argument(
        "--backrun-floor",
        type=float,
        default=0.0,
        help="the next band's threshold: backruns go only where the target is lighter than it",
    )
    parser.add_argument(
        "--max-strength",
        type=float,
        default=7.8,
        help="cap on a load's total strength; 3.5 keeps a dark wash from turning to paste",
    )
    parser.add_argument("--preview")
    parser.add_argument("--no-dry", action="store_true")
    arguments = parser.parse_args()

    global MAX_STRENGTH
    MAX_STRENGTH = arguments.max_strength
    actions, predicted = build(arguments)
    with open(arguments.output, "w") as handle:
        json.dump(actions, handle)
    strokes = sum(action["action"] == "stroke" for action in actions)
    print(f"{arguments.output}: {len(actions)} actions, {strokes} strokes")
    if arguments.preview:
        Image.fromarray(predicted.astype(np.uint8)).save(arguments.preview)


if __name__ == "__main__":
    main()

"""Measured layering: write a pass that lays, with one brush size, what the sheet still lacks against a reference.

The method is the painter's own, made numerical:

  1. Express reference and sheet as absorbance per channel (how much each darkens the paper).
  2. The gap between them is what remains to be painted. Paint can only darken, so only positive gaps count.
  3. A brush of a given width can lay, without covering any light, only what is common to its whole footprint:
     the MINIMUM of the gap under the footprint. Broad brushes therefore lay the pale, general tone; each smaller
     brush that follows adds the darker, more local remainder. Light and broad first, dark and small last.
  4. Each stroke carries the mix solved for the gap beneath it, so a wash varies in colour along its length.

Usage:
    measured_layers.py <reference> <output pass.json> --sheet W,H --paints cobalt_blue,burnt_sienna,...
        [--look current_look.png] [--origin x,y --crop W,H]
        --brush round --size 12 [--hair squirrel] [--angle 0] [--gain 0.8] [--least 0.07] [--water 1.0]
        [--longest 140] [--tolerance 0.3] [--region x0,y0,x1,y1] [--exclude x0,y0,x1,y1 ...]
        [--keep-lights 0.08] [--cut-in 8,3.5] [--white r,g,b] [--no-dry]

--paints names the paints a mix may use: the transparent paints of the painting's palette, never opaque_white.
--origin is the full-sheet coordinate of the sheet's top-left corner when the sheet is a crop of the reference,
and --crop is that sheet's size. --region and --exclude are then in the cropped sheet's own coordinates.
--white is the colour of the reference's own paper, where it is a scan and not pure white.
--exclude leaves a rectangle untouched: the brush stays half its width outside it.
--keep-lights keeps the brush off a light narrower than the smoothing window (a sail, a mast against a sky), which
the smoothing would otherwise give the tone of its surroundings. It leaves a margin of bare paper round every light
for the smaller brushes to fill, and that margin dries ragged unless it is closed while the wash is wet.
--cut-in does that: in the same pass, rounds of the sizes given lay what the brush could not reach, largest first,
so the wash runs up to the edge of each light as one wet wash. Use it with --no-dry on a first wash.
Without --look the sheet is taken to be bare paper. Give it a look taken after a `dry`: a wet sheet is not yet the
colour it will dry to.

Run it with the Python that the watercolor tool uses; it reads that tool's pigment table.
"""

import argparse
import copy
import functools
import itertools
import json
import math
import random

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter
from torch.nn import functional

# The harness's bare paper as a dry look shows it.
PAPER = np.array([247.0, 244.0, 237.0])
# Painted width as a multiple of size at pressure 0.9.
WIDTH = {"round": 2.0, "mop": 2.1, "oval_wash": 2.1, "cats_tongue": 2.0, "flat": 2.1}

Absorption = dict[str, tuple[float, float, float]]


def paint_absorption(names: list[str]) -> Absorption:
    """Absorption per channel of each named paint, from the harness's own pigment table."""
    try:
        from watercolor.pigments import PIGMENTS
    except ImportError as error:
        raise SystemExit(
            "run this with the Python that the watercolor tool uses: its pigment table is needed"
        ) from error
    unknown = [name for name in names if name not in PIGMENTS]
    if unknown:
        raise SystemExit(f"not in the paint box: {', '.join(unknown)}")
    if "opaque_white" in names:
        raise SystemExit("opaque_white covers, it does not darken: leave it out of --paints")
    return {name: PIGMENTS[name].absorption for name in names}


def absorbance(image: np.ndarray, paper: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(image / paper, 0.004, 1.0))


def pooled(array: np.ndarray, kernel: int, mode: str) -> np.ndarray:
    """Box mean or minimum over a square window, same size out as in."""
    kernel = max(1, kernel | 1)
    tensor = torch.from_numpy(array).permute(2, 0, 1)[None].float()
    padded = functional.pad(tensor, (kernel // 2,) * 4, mode="replicate")
    if mode == "mean":
        result = functional.avg_pool2d(padded, kernel, stride=1)
    else:
        result = -functional.max_pool2d(-padded, kernel, stride=1)
    return result[0].permute(1, 2, 0).numpy()


def footprint_minimum(array: np.ndarray, width: float) -> np.ndarray:
    """The least value under a brush's footprint. The footprint is an octagon (a square widened by a diamond), not a
    square: a square window leaves square-cornered holes round every light, and they dry as white rectangles."""
    radius = width / 2
    square, diamond = round(0.45 * radius), round(0.55 * radius)
    tensor = torch.from_numpy(array).permute(2, 0, 1)[None].float()
    if square:
        padded = functional.pad(tensor, (square,) * 4, mode="replicate")
        tensor = -functional.max_pool2d(-padded, 2 * square + 1, stride=1)
    for _ in range(diamond):
        padded = functional.pad(tensor, (1, 1, 1, 1), mode="replicate")
        across = -functional.max_pool2d(-padded[..., 1:-1, :], (1, 3), stride=1)
        down = -functional.max_pool2d(-padded[..., :, 1:-1], (3, 1), stride=1)
        tensor = torch.minimum(across, down)
    return tensor[0].permute(1, 2, 0).numpy()


@functools.cache
def _mix_matrices(paints: tuple[tuple[str, tuple[float, float, float]], ...]) -> dict[tuple[str, ...], np.ndarray]:
    """One matrix of absorptions for every mix of one, two or three of the paints."""
    table = dict(paints)
    return {
        subset: np.array([table[name] for name in subset]).T
        for count in (1, 2, 3)
        for subset in itertools.combinations(table, count)
    }


def solve_mix(gap: np.ndarray, absorption: Absorption, without: tuple[str, ...] = ()) -> dict[str, float]:
    """The paints, in linear absorbance units, that best give this absorbance."""
    best, best_score = None, None
    for subset, matrix in _mix_matrices(tuple(absorption.items())).items():
        if any(name in without for name in subset):
            continue
        amounts, *_ = np.linalg.lstsq(matrix, gap, rcond=None)
        if (amounts < 0).any():
            continue
        score = float(np.abs(matrix @ amounts - gap).sum()) + 0.02 * float(amounts.sum()) + 0.004 * len(subset)
        if best_score is None or score < best_score:
            best, best_score = dict(zip(subset, amounts)), score
    return best or {}


def to_load(linear: dict[str, float], gain: float, size: float, single: float = 1.0) -> dict[str, float]:
    """Turn linear absorbance units into the amounts to load.

    Measured on filled patches of rows overlapping by 30%: a load of total strength 3 dries with about 1.4 units of
    absorbance from a brush of size 7 or more, 0.95 from size 3.5 and 0.8 from size 1.6, and the units grow as the
    0.75 power of the strength. A stroke laid alone lays less than a filled patch: `single` is its share."""
    total = sum(linear.values())
    if total <= 0:
        return {}
    at_three = min(1.4, max(0.7, 0.62 + 0.11 * size)) * single
    strength = min(7.8, 3.0 * (total / at_three) ** (1.0 / 0.75) * gain)
    return {
        name: round(amount / total * strength, 3)
        for name, amount in linear.items()
        if amount / total * strength >= 0.004
    }


def target_and_sheet(parser: argparse.ArgumentParser, arguments: argparse.Namespace) -> tuple[np.ndarray, np.ndarray]:
    """The reference and the sheet as absorbance, both at the sheet's size: what is wanted and what is there.

    With --origin and --crop the sheet is a crop of the reference. Without --look the sheet is bare paper."""
    sheet_width, sheet_height = (int(value) for value in arguments.sheet.split(","))
    reference = Image.open(arguments.reference).convert("RGB")
    reference = reference.resize((sheet_width, sheet_height), Image.Resampling.LANCZOS)
    if arguments.origin or arguments.crop:
        if not (arguments.origin and arguments.crop):
            # with only one of the two the whole reference would be laid on a sheet the size of the crop
            parser.error("--origin x,y and --crop W,H must be given together")
        x0, y0 = (int(value) for value in arguments.origin.split(","))
        crop_width, crop_height = (int(value) for value in arguments.crop.split(","))
        reference = reference.crop((x0, y0, x0 + crop_width, y0 + crop_height))
    white = np.array([float(value) for value in arguments.white.split(",")])
    target = absorbance(np.asarray(reference).astype(float), white)
    if not arguments.look:
        return target, np.zeros_like(target)
    look = Image.open(arguments.look).convert("RGB").resize(reference.size, Image.Resampling.LANCZOS)
    return target, absorbance(np.asarray(look).astype(float), PAPER)


def mark_covered(covered: Image.Image, actions: list[dict], stroke_width: float) -> None:
    """Draw the strokes of a pass onto a mask at about the width they paint."""
    draw = ImageDraw.Draw(covered)
    radius = stroke_width * 0.45
    for action in actions:
        if action["action"] == "stroke":
            line = [(x, y) for x, y, _ in action["path"]]
            draw.line(line, fill=255, width=int(2 * radius), joint="curve")
            for x, y in line:
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=255)


def build(target: np.ndarray, current: np.ndarray, arguments) -> list[dict]:
    height, width_pixels, _ = target.shape
    stroke_width = WIDTH.get(arguments.brush, 2.0) * arguments.size
    smoothing = max(3, int(stroke_width * arguments.smoothing))
    gap = np.clip(pooled(target, smoothing, "mean") - pooled(current, smoothing, "mean"), 0.0, None)
    if arguments.keep_lights > 0:
        # a light narrower than the smoothing window comes out of the smoothing with the tone of its surroundings,
        # and the brush is laid straight across it; where the reference itself is light, read the gap finely
        fine_target = pooled(target, 5, "mean")
        fine = np.clip(fine_target - pooled(current, 5, "mean"), 0.0, None)
        light = fine_target.max(-1) < arguments.keep_lights
        gap[light] = np.minimum(gap, fine)[light]
    for left, top, right, bottom in arguments.excluded:
        gap[top:bottom, left:right] = 0.0  # nothing is wanted here, so no footprint that reaches in lays anything
    common = footprint_minimum(gap, stroke_width)  # what the whole footprint has in common

    spacing = stroke_width * arguments.overlap
    step = max(2.0, stroke_width / 2)
    angle = math.radians(arguments.angle)
    along = (math.cos(angle), math.sin(angle))
    across = (-along[1], along[0])
    centre = (width_pixels / 2, height / 2)
    reach = math.hypot(width_pixels, height) / 2
    box = arguments.box or (0, 0, width_pixels, height)
    # a region that runs past the sheet would otherwise be read off the end of the gap, or from its far edge
    box = (max(box[0], 0), max(box[1], 0), min(box[2], width_pixels), min(box[3], height))

    actions, strokes = [], 0

    def emit(points, gaps):
        nonlocal strokes
        mean = np.mean(gaps, axis=0)
        if len(points) == 1 and mean.max() < arguments.lone * arguments.least:
            return  # a lone faint touch is speckle, not painting
        pigments = to_load(solve_mix(mean, arguments.absorption, arguments.without), arguments.gain, arguments.size)
        if sum(pigments.values()) < 0.03:
            return
        start, end = points[0], points[-1]
        if len(points) == 1:
            end = (start[0] + along[0] * 2, start[1] + along[1] * 2)
        load = {
            "action": "load",
            "brush": arguments.brush,
            "size": arguments.size,
            "pigments": pigments,
            "water": arguments.water,
        }
        if arguments.hair:
            load["hair"] = arguments.hair
        actions.append(load)
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if arguments.wobble > 0 and length > stroke_width:
            # a hand does not draw a ruled line: let the stroke wander a little and its pressure breathe, and lift
            # at both ends, so that rows do not dry with straight edges and round-ended dots
            pieces = max(2, round(length / (1.5 * stroke_width)))
            path = []
            for index in range(pieces + 1):
                t = index / pieces
                drift = random.uniform(-1, 1) * arguments.wobble * stroke_width if 0 < index < pieces else 0.0
                pressure = arguments.taper if index in (0, pieces) else random.uniform(0.8, 0.95)
                path.append(
                    [
                        round(start[0] + (end[0] - start[0]) * t + across[0] * drift, 1),
                        round(start[1] + (end[1] - start[1]) * t + across[1] * drift, 1),
                        round(pressure, 2),
                    ]
                )
            smooth = True
        else:
            ends = arguments.taper if arguments.wobble > 0 else 0.9
            path = [[round(start[0], 1), round(start[1], 1), ends], [round(end[0], 1), round(end[1], 1), ends]]
            smooth = False
        if strokes % 2:
            path.reverse()
        actions.append({"action": "stroke", "path": path, "speed": arguments.speed, "smooth": smooth})
        strokes += 1

    offset = -reach
    while offset <= reach:
        points, gaps = [], []
        position = -reach
        while position <= reach:
            x = centre[0] + along[0] * position + across[0] * offset
            y = centre[1] + along[1] * position + across[1] * offset
            inside = (
                box[0] <= x < box[2]
                and box[1] <= y < box[3]
                and not any(left <= x < right and top <= y < bottom for left, top, right, bottom in arguments.excluded)
            )
            value = common[int(y), int(x)] if inside else None
            wanted = value is not None and value.max() >= arguments.least
            if wanted and points:
                mean = np.mean(gaps, axis=0)
                different = np.abs(value - mean).max() > arguments.tolerance * (0.25 + mean.max())
                too_long = len(points) * step >= arguments.longest
                if different and value.max() > mean.max():
                    # a darker stroke follows: the lighter one runs on under its first point, so the two overlap
                    # where the gap is the larger, and the darker mix is laid nowhere its footprint did not allow
                    emit([*points, (x, y)], gaps)
                    points, gaps = [], []
                elif different or too_long:
                    emit(points, gaps)
                    # the next stroke starts where this one ended, so the two lifted ends overlap; begun one step
                    # further on, they leave a hole of bare paper at every cut, and the cuts of long even rows
                    # line up from row to row
                    points, gaps = [points[-1]], []
            if wanted:
                points.append((x, y))
                gaps.append(value)
            elif points:
                emit(points, gaps)
                points, gaps = [], []
            position += step
        if points:
            emit(points, gaps)
        offset += spacing

    if arguments.cut_in:
        # in the same wet pass, smaller rounds lay what the brush before them could not reach: the margin round
        # each light and the narrow places between lights
        covered = Image.new("L", (width_pixels, height), 0)
        mark_covered(covered, actions, stroke_width)
        for size in arguments.cut_in:
            keep = int(WIDTH["round"] * size / 2) + 2  # the smaller brush overlaps the wet wash by half its width
            mask = np.asarray(covered.filter(ImageFilter.MinFilter(2 * keep + 1))) > 0
            reached = current.copy()
            reached[mask] = np.maximum(target, current)[mask]
            smaller = copy.copy(arguments)
            smaller.brush, smaller.size, smaller.hair = "round", size, "squirrel"
            smaller.cut_in, smaller.no_dry, smaller.smoothing = [], True, 0.5
            smaller.longest = max(60.0, arguments.longest * size / arguments.size * 2)
            more = build(target, reached, smaller)
            mark_covered(covered, more, WIDTH["round"] * size)
            actions += more
    if not arguments.no_dry:
        actions.append({"action": "dry"})
    return actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="full sheet size the reference is scaled to: W,H")
    parser.add_argument("--paints", required=True, help="the paints a mix may use, comma separated")
    parser.add_argument("--look", default=None)
    parser.add_argument("--origin", default=None, help="x,y of this sheet's corner on the full sheet, with --crop W,H")
    parser.add_argument("--crop", default=None)
    parser.add_argument("--brush", default="round")
    parser.add_argument("--hair", default=None)
    parser.add_argument("--size", type=float, required=True)
    parser.add_argument("--angle", type=float, default=0.0)
    parser.add_argument("--gain", type=float, default=0.8)
    parser.add_argument("--least", type=float, default=0.07)
    parser.add_argument("--water", type=float, default=1.0)
    parser.add_argument("--speed", type=float, default=240)
    parser.add_argument("--longest", type=float, default=140)
    parser.add_argument("--tolerance", type=float, default=0.3)
    parser.add_argument("--overlap", type=float, default=0.7, help="row spacing as a share of the stroke's width")
    parser.add_argument("--region", default=None, help="paint only inside x0,y0,x1,y1 (sheet coordinates)")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="leave x0,y0,x1,y1 untouched (repeatable): eyes, teeth, finished drawing",
    )
    parser.add_argument(
        "--white",
        default="255,255,255",
        help="the colour of the reference's own paper: r,g,b (pure white unless given)",
    )
    parser.add_argument(
        "--smoothing",
        type=float,
        default=0.4,
        help="blur of the gap before it is read, as a share of the stroke's width",
    )
    parser.add_argument(
        "--lone",
        type=float,
        default=2.5,
        help="a single-cell stroke is kept only if its gap is this many times --least",
    )
    parser.add_argument(
        "--wobble",
        type=float,
        default=0.0,
        help="sideways wander of a stroke, as a share of its width (0 rules it straight)",
    )
    parser.add_argument(
        "--taper", type=float, default=0.6, help="pressure at the two ends of a stroke when --wobble is set"
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--cut-in",
        default="",
        help="sizes of rounds that follow in the same wet pass and lay what this brush could not reach: 8,3.5",
    )
    parser.add_argument(
        "--keep-lights",
        type=float,
        default=0.0,
        help="where the reference's absorbance is under this, read the gap unsmoothed, so a narrow light is kept",
    )
    parser.add_argument(
        "--without", default="", help="paints the mix may not use, comma separated (a granulating paint in a deep wash)"
    )
    parser.add_argument("--no-dry", action="store_true")
    arguments = parser.parse_args()

    target, current = target_and_sheet(parser, arguments)
    random.seed(arguments.seed)
    arguments.cut_in = [float(value) for value in arguments.cut_in.split(",") if value]
    arguments.excluded = [tuple(int(value) for value in box.split(",")) for box in arguments.exclude]
    arguments.without = tuple(name for name in arguments.without.split(",") if name)
    arguments.absorption = paint_absorption([name for name in arguments.paints.split(",") if name])
    arguments.box = tuple(int(value) for value in arguments.region.split(",")) if arguments.region else None

    actions = build(target, current, arguments)
    with open(arguments.output, "w") as handle:
        json.dump(actions, handle)
    count = sum(1 for action in actions if action["action"] == "stroke")
    print(f"{arguments.output}: {count} strokes with {arguments.brush} {arguments.size}")


if __name__ == "__main__":
    main()

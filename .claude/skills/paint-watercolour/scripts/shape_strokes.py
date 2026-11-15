"""Shape strokes: paint what the sheet still lacks as strokes that run ALONG each shape, not across it in rows.

measured_layers.py lays rows of short strokes. That gets tone right and leaves no long stroke and no crisp plane.
This tool takes the same gap between reference and sheet and paints it the way a hand would:

  1. The shapes of this pass are the places where the gap is at least a threshold.
  2. Each shape is thinned to its centre line, and the distance from that line to the shape's edge is its half
     width there.
  3. One stroke runs down each centre line. Its pressure follows the half width, so the stroke swells and tapers
     with the shape and its edge lands on the shape's edge.
  4. Where a shape is wider than the brush allows, the stroke takes the middle, the remainder is thinned again, and
     further strokes run beside the first, parallel to the shape's edges, all while the first is wet.
  5. Every stroke lays about the threshold's worth of tone (never more than `--cap` times it), so each pass is one
     flat glaze with a hard edge; a later pass at a higher threshold lays a smaller, darker glaze inside it.

Usage:
    shape_strokes.py <reference> <output pass.json> --sheet W,H --paints cobalt_blue,burnt_sienna,...
        --look <current look> --threshold 0.15
        --widest 8 [--narrowest 1.0] [--cap 1.6] [--gain 1.0] [--peels 3] [--hair squirrel] [--water 0.9]
        [--blur 2] [--region x0,y0,x1,y1] [--exclude x0,y0,x1,y1 ...] [--origin x,y --crop W,H]
        [--white r,g,b] [--no-dry]

--paints and the Python to run it with are as for measured_layers.py. The look must be one taken after a `dry`.
"""

import argparse
import json

import numpy as np
import torch
from measured_layers import PAPER, absorbance, paint_absorption, pooled, solve_mix
from PIL import Image, ImageDraw
from torch.nn import functional


def erode(mask: np.ndarray, times: int = 1) -> np.ndarray:
    tensor = torch.from_numpy(mask.astype(np.float32))[None, None]
    for _ in range(times):
        tensor = -functional.max_pool2d(-functional.pad(tensor, (1, 1, 1, 1), value=0.0), 3, stride=1)
    return tensor[0, 0].numpy() > 0.5


def dilate(mask: np.ndarray, times: int = 1) -> np.ndarray:
    tensor = torch.from_numpy(mask.astype(np.float32))[None, None]
    for _ in range(times):
        tensor = functional.max_pool2d(functional.pad(tensor, (1, 1, 1, 1), value=0.0), 3, stride=1)
    return tensor[0, 0].numpy() > 0.5


def half_width(mask: np.ndarray, limit: int) -> np.ndarray:
    """Distance from each shape pixel to the shape's edge, by counting erosions (alternating cross and square
    neighbourhoods, which approximates a round distance)."""
    distance = np.zeros(mask.shape, dtype=np.float32)
    tensor = torch.from_numpy(mask.astype(np.float32))[None, None]
    for index in range(limit):
        distance += tensor[0, 0].numpy()
        if not tensor.any():
            break
        padded = functional.pad(tensor, (1, 1, 1, 1), value=0.0)
        if index % 2:
            tensor = -functional.max_pool2d(-padded, 3, stride=1)
        else:
            across = -functional.max_pool2d(-padded[..., 1:-1, :], (1, 3), stride=1)
            down = -functional.max_pool2d(-padded[..., :, 1:-1], (3, 1), stride=1)
            tensor = torch.minimum(across, down)
    return distance


def thin(mask: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning: the one-pixel centre line of every shape."""
    image = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p2, p3, p4 = image[:-2, 1:-1], image[:-2, 2:], image[1:-1, 2:]
            p5, p6, p7 = image[2:, 2:], image[2:, 1:-1], image[2:, :-2]
            p8, p9 = image[1:-1, :-2], image[:-2, :-2]
            ring = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            neighbours = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            transitions = sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                rule = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                rule = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            remove = (image[1:-1, 1:-1] == 1) & (neighbours >= 2) & (neighbours <= 6) & (transitions == 1) & rule
            if remove.any():
                image[1:-1, 1:-1][remove] = 0
                changed = True
        if not changed:
            break
    return image[1:-1, 1:-1].astype(bool)


OFFSETS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def centre_lines(skeleton: np.ndarray) -> list[list[tuple[int, int]]]:
    """Follow the thinned shapes into ordered runs of pixels, each from one end or branch point to the next."""
    pixels = set(zip(*np.nonzero(skeleton)))

    def around(pixel):
        return [(pixel[0] + dy, pixel[1] + dx) for dy, dx in OFFSETS if (pixel[0] + dy, pixel[1] + dx) in pixels]

    degree = {pixel: len(around(pixel)) for pixel in pixels}
    visited: set = set()
    lines = []

    def walk(start, first):
        line = [start, first]
        visited.add(first)
        current, previous = first, start
        while degree[current] == 2:
            following = [pixel for pixel in around(current) if pixel != previous and pixel not in visited]
            if not following:
                break
            previous, current = current, following[0]
            visited.add(current)
            line.append(current)
        return line

    nodes = [pixel for pixel in pixels if degree[pixel] != 2]
    for node in nodes:
        visited.add(node)
    for node in nodes:
        if degree[node] == 0:
            lines.append([node])
            continue
        for neighbour in around(node):
            if neighbour not in visited:
                lines.append(walk(node, neighbour))
            elif degree[neighbour] != 2 and node < neighbour:
                lines.append([node, neighbour])
    for pixel in pixels:  # closed loops with no end and no branch
        if pixel not in visited:
            visited.add(pixel)
            neighbours = around(pixel)
            if neighbours:
                lines.append(walk(pixel, neighbours[0]))
    return lines


def build(target: np.ndarray, current: np.ndarray, arguments) -> list[dict]:
    height, width, _ = target.shape
    gap = np.clip(pooled(target, arguments.blur, "mean") - pooled(current, arguments.blur, "mean"), 0.0, None)
    strongest = gap.max(-1)
    mask = strongest >= arguments.threshold
    if arguments.box:
        x0, y0, x1, y1 = arguments.box
        keep = np.zeros_like(mask)
        keep[y0:y1, x0:x1] = True
        mask &= keep
    for x0, y0, x1, y1 in arguments.excluded:
        mask[y0:y1, x0:x1] = False
    specks = max(0, round(arguments.narrowest) - 1)
    mask = dilate(erode(mask, 1 + specks), 1 + specks)  # drop specks and hairs thinner than the brush can draw

    # One neighbourhood, one wet fill: a centre-line stroke and the strokes that run beside it are laid one after
    # another, neighbourhood by neighbourhood across the sheet, so they run together and the shape dries as a
    # single plane with one edge. Laid peel by peel over the whole sheet, the first strokes of a shape are dry
    # before the ones beside them arrive, and every stroke keeps its own rim.
    planned, count = [], 0
    for peel in range(arguments.peels):
        if not mask.any():
            break
        distance = half_width(mask, int(arguments.widest * 4) + 4)
        footprint = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(footprint)
        for line in centre_lines(thin(mask)):
            radii = np.array([min(distance[y, x], arguments.widest) for y, x in line])
            if len(line) < max(3, radii.max() * arguments.spur) and len(line) < 12:
                continue  # a spur shorter than the shape is wide is not a stroke
            stride = max(2, round(radii.mean() * 1.2))
            chosen = list(range(0, len(line), stride))
            if chosen[-1] != len(line) - 1:
                chosen.append(len(line) - 1)
            if len(chosen) == 1:
                chosen = [0, 0]
            size = float(np.clip(radii.max() * 0.95, arguments.narrowest, arguments.widest))
            values = np.array([gap[y, x] for y, x in line]).mean(0)
            amount = min(values.max(), arguments.cap * arguments.threshold)
            if values.max() <= 0:
                continue
            linear = solve_mix(values / values.max() * amount, arguments.absorption)
            total = sum(linear.values())
            if total <= 0:
                continue
            at_three = min(1.4, max(0.7, 0.62 + 0.11 * size)) * arguments.single
            strength = min(7.8, 3.0 * (total / at_three) ** (1.0 / 0.75) * arguments.gain)
            pigments = {
                name: round(value / total * strength, 3)
                for name, value in linear.items()
                if value / total * strength >= 0.004
            }
            if sum(pigments.values()) < 0.03:
                continue
            path = []
            for position, index in enumerate(chosen):
                y, x = line[index]
                pressure = float(np.clip((2.0 * radii[index] / size - 0.54) / 1.63, 0.12, 1.0))
                if position in (0, len(chosen) - 1) and len(chosen) > 2:
                    pressure *= arguments.taper
                path.append([float(x) + 0.5, float(y) + 0.5, round(max(0.1, pressure), 2)])
            if len(chosen) == 2 and chosen[0] == chosen[1]:
                path[1][0] += 1.5
            load = {
                "action": "load",
                "brush": "round",
                "size": round(size, 1),
                "pigments": pigments,
                "water": arguments.water,
            }
            if arguments.hair:
                load["hair"] = arguments.hair
            y0, x0 = line[len(line) // 2]
            planned.append(
                (
                    y0 // arguments.neighbourhood,
                    x0 // arguments.neighbourhood,
                    peel,
                    count,
                    [load, {"action": "stroke", "path": path, "speed": arguments.speed, "smooth": len(path) > 2}],
                )
            )
            count += 1
            for index in range(len(line)):
                y, x = line[index]
                r = max(1.0, radii[index])
                draw.ellipse([x - r, y - r, x + r, y + r], fill=255)
        mask = mask & ~(np.asarray(footprint) > 0)
        mask = dilate(erode(mask, 1 + specks), 1 + specks)

    actions = []
    for *_, pair in sorted(planned, key=lambda item: item[:4]):
        actions += pair
    if not arguments.no_dry:
        actions.append({"action": "dry"})
    print(f"{arguments.output}: {count} shape strokes at threshold {arguments.threshold}, widest {arguments.widest}")
    return actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--paints", required=True, help="the paints a mix may use, comma separated")
    parser.add_argument("--look", required=True)
    parser.add_argument("--origin", default=None)
    parser.add_argument("--crop", default=None)
    parser.add_argument(
        "--threshold", type=float, required=True, help="paint where the gap in absorbance is at least this"
    )
    parser.add_argument("--cap", type=float, default=1.6, help="a stroke lays at most this many times the threshold")
    parser.add_argument("--widest", type=float, default=8.0, help="largest brush size (half the widest stroke)")
    parser.add_argument("--narrowest", type=float, default=1.2, help="smallest brush size")
    parser.add_argument("--gain", type=float, default=1.0)
    parser.add_argument(
        "--single", type=float, default=0.75, help="deposit of one stroke as a share of a filled patch of rows"
    )
    parser.add_argument("--peels", type=int, default=3, help="how many times to thin again what the first strokes left")
    parser.add_argument(
        "--neighbourhood", type=int, default=64, help="strokes are laid tile by tile of this many pixels"
    )
    parser.add_argument("--spur", type=float, default=1.2, help="drop centre lines shorter than this many half widths")
    parser.add_argument("--taper", type=float, default=0.6)
    parser.add_argument("--hair", default=None)
    parser.add_argument("--water", type=float, default=0.9)
    parser.add_argument("--speed", type=float, default=170)
    parser.add_argument("--blur", type=int, default=3)
    parser.add_argument("--region", default=None)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument(
        "--white",
        default="255,255,255",
        help="the colour of the reference's own paper: r,g,b (pure white unless given)",
    )
    parser.add_argument("--no-dry", action="store_true")
    arguments = parser.parse_args()

    sheet_width, sheet_height = (int(value) for value in arguments.sheet.split(","))
    sheet = (sheet_width, sheet_height)
    reference = Image.open(arguments.reference).convert("RGB").resize(sheet, Image.Resampling.LANCZOS)
    if arguments.origin:
        if not arguments.crop:
            parser.error("--origin needs --crop W,H")
        x0, y0 = (int(value) for value in arguments.origin.split(","))
        crop_width, crop_height = (int(value) for value in arguments.crop.split(","))
        reference = reference.crop((x0, y0, x0 + crop_width, y0 + crop_height))
    white = np.array([float(value) for value in arguments.white.split(",")])
    target = absorbance(np.asarray(reference).astype(float), white)
    look = Image.open(arguments.look).convert("RGB").resize(reference.size, Image.Resampling.LANCZOS)
    current = absorbance(np.asarray(look).astype(float), PAPER)
    arguments.box = tuple(int(value) for value in arguments.region.split(",")) if arguments.region else None
    arguments.excluded = [tuple(int(value) for value in box.split(",")) for box in arguments.exclude]
    arguments.absorption = paint_absorption([name for name in arguments.paints.split(",") if name])

    actions = build(target, current, arguments)
    with open(arguments.output, "w") as handle:
        json.dump(actions, handle)


if __name__ == "__main__":
    main()

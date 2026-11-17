"""Trace troughs: paint the dark troughs of choppy water as single tapered strokes traced from the reference.

measured_layers.py fills a choppy sea as rows, which dry as mottle, and shape_strokes.py follows each dark shape's
centre line, which on open water draws looping worms. A painter puts each trough down as one stroke, thick in the
middle and pointed at the ends. This does that:

  1. A trough is a patch of the reference darker than its surroundings (its grey under a blur of `--blur` pixels)
     by at least `--darker` levels out of 255, and at least `--least-length` pixels long.
  2. Each patch is walked column by column, since the troughs of water seen from the shore run across the sheet:
     the stroke passes through the middle of the patch in each column, its pressure follows the patch's height
     there, and both ends taper.
  3. The round's size is the patch's 80th-percentile height over 1.9, between 0.8 and 4, in half steps.
  4. The mix is solved for the mean gap (reference less sheet) over the patch. Run it on a look of the dried sheet
     and it lays only what the sheet still lacks there.

Lay the water's base wash first and a little under strength (measured_layers.py rows, `--gain 0.9`), `dry`, then
run this twice: `--darker 5 --gain 0.55`, paint, look; then `--darker 11 --gain 1.0` on the new look.

Usage:
    trace_troughs.py <reference> <output pass.json> --sheet W,H --paints cobalt_blue,phthalo_green,burnt_sienna
        --look <current look> [--darker 10] [--blur 9] [--least-length 6] [--gain 1.0] [--single 0.6]
        [--water 0.85] [--hair kolinsky_sable] [--region x0,y0,x1,y1] [--origin x,y --crop W,H]
        [--white r,g,b] [--no-dry] [--preview preview.png]

--paints and the Python to run it with are as for measured_layers.py. The look must be one taken after a `dry`.
--region keeps the troughs to a rectangle in the sheet's own coordinates: the open water, not the surf.
"""

import argparse
import json

import numpy as np
from measured_layers import paint_absorption, solve_mix, target_and_sheet, to_load
from PIL import Image, ImageDraw, ImageFilter


def patches(mask: np.ndarray) -> list[np.ndarray]:
    """Connected patches of a boolean mask (4-connected), each as an array of (y, x)."""
    height, width = mask.shape
    seen = np.zeros_like(mask)
    found = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        stack, cells = [(y0, x0)], []
        while stack:
            y, x = stack.pop()
            cells.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        found.append(np.array(cells))
    return found


def build(target: np.ndarray, current: np.ndarray, white: np.ndarray, arguments) -> list[dict]:
    grey = (white * np.exp(-target)).mean(axis=2)
    surround = np.asarray(
        Image.fromarray(grey.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(arguments.blur)),
        dtype=np.float64,
    )
    dark = surround - grey > arguments.darker
    if arguments.region:
        x0, y0, x1, y1 = (int(value) for value in arguments.region.split(","))
        inside = np.zeros_like(dark)
        inside[max(0, y0) : y1, max(0, x0) : x1] = True
        dark &= inside
    gap = np.maximum(target - current, 0.0)
    actions = []
    for patch in patches(dark):
        columns: dict[int, list[int]] = {}
        for y, x in patch:
            columns.setdefault(int(x), []).append(int(y))
        if max(columns) - min(columns) + 1 < arguments.least_length:
            continue
        points = [(x, (min(ys) + max(ys)) / 2.0, max(ys) - min(ys) + 1.0) for x, ys in sorted(columns.items())]
        heights = np.array([p[2] for p in points])
        size = round(float(np.clip(np.percentile(heights, 80) / 1.9, 0.8, 4.0)) * 2) / 2
        step = max(1, len(points) // 12)
        chosen = points[::step]
        if chosen[-1] is not points[-1]:
            chosen.append(points[-1])
        path = []
        for i, (x, y, tall) in enumerate(chosen):
            pressure = float(np.clip((tall / size - 0.54) / 1.63, 0.05, 1.0))
            taper = min(1.0, 3.0 * min(i, len(chosen) - 1 - i) / max(1, len(chosen) - 1) + 0.15)
            path.append([x + 0.5, round(y + 0.5, 1), round(pressure * taper, 3)])
        wanted = gap[patch[:, 0], patch[:, 1]].mean(axis=0)
        if wanted.max() < 0.02:
            continue
        load = to_load(solve_mix(wanted, arguments.absorption), arguments.gain, size, arguments.single)
        if not load:
            continue
        brush = {"action": "load", "brush": "round", "size": size, "pigments": load, "water": arguments.water}
        if arguments.hair:
            brush["hair"] = arguments.hair
        actions.append(brush)
        actions.append({"action": "stroke", "smooth": True, "speed": 140, "path": path})
    if not arguments.no_dry:
        actions.append({"action": "dry"})
    return actions


def preview(target: np.ndarray, white: np.ndarray, actions: list[dict], path: str) -> None:
    picture = Image.fromarray((white * np.exp(-target)).clip(0, 255).astype(np.uint8))
    scale = 3
    picture = picture.resize((picture.width * scale, picture.height * scale))
    draw = ImageDraw.Draw(picture)
    size = 1.0
    for action in actions:
        if action["action"] == "load":
            size = action["size"]
        elif action["action"] == "stroke":
            draw.line(
                [(x * scale, y * scale) for x, y, _ in action["path"]],
                fill=(255, 0, 0),
                width=max(1, round(size * scale)),
            )
    picture.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="full sheet size the reference is scaled to: W,H")
    parser.add_argument("--paints", required=True, help="the paints a mix may use, comma separated")
    parser.add_argument("--look", required=True)
    parser.add_argument("--origin", default=None)
    parser.add_argument("--crop", default=None)
    parser.add_argument("--darker", type=float, default=10.0, help="levels of 255 darker than the surroundings")
    parser.add_argument("--blur", type=float, default=9.0, help="radius of the blur that gives the surroundings")
    parser.add_argument("--least-length", type=int, default=6)
    parser.add_argument("--gain", type=float, default=1.0)
    parser.add_argument(
        "--single", type=float, default=0.6, help="deposit of one stroke as a share of a filled patch of rows"
    )
    parser.add_argument("--water", type=float, default=0.85)
    parser.add_argument("--hair", default="kolinsky_sable")
    parser.add_argument("--region", default=None, help="trace only inside x0,y0,x1,y1 (sheet coordinates)")
    parser.add_argument(
        "--white",
        default="255,255,255",
        help="the colour of the reference's own paper: r,g,b (pure white unless given)",
    )
    parser.add_argument("--no-dry", action="store_true")
    parser.add_argument("--preview", default=None, help="draw the strokes over the reference into this image")
    arguments = parser.parse_args()

    target, current = target_and_sheet(parser, arguments)
    arguments.absorption = paint_absorption([name for name in arguments.paints.split(",") if name])
    white = np.array([float(value) for value in arguments.white.split(",")])
    actions = build(target, current, white, arguments)
    with open(arguments.output, "w") as handle:
        json.dump(actions, handle)
    strokes = sum(1 for action in actions if action["action"] == "stroke")
    print(f"{arguments.output}: {strokes} troughs")
    if arguments.preview:
        preview(target, white, actions, arguments.preview)


if __name__ == "__main__":
    main()

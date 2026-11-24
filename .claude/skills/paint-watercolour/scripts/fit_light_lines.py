"""Fit light lines: whiskers, stays and other thin light lines of a reference, from guides drawn by hand.

A whisker over a dark coat is kept with masking fluid, and it must be masked where it is. Reading a hairline off a
gridded enlargement is good to three or four pixels, which is its own width several times over. So:

  1. Each guide is a few points read off the grid, root first, in a JSON file: {"name": [[x, y], ...], ...}. A
     smooth curve is drawn through them.
  2. Each point of the curve moves up to --reach pixels across the line, to where the reference is lightest against
     its surroundings. The moves are smoothed along the line, since a whisker is smooth, and where no light line is
     found the point stays on the guide.
  3. --paths writes the fitted lines. --mask-pass writes one stroke of masking fluid along each, of --radius at the
     root and tapering to the tip. --without writes the reference with those lines painted out in the colour beside
     them, for the measuring scripts: their washes then run straight across the fluid, and the fluid alone keeps the
     line. Left in the reference, each line is painted round by every stage and dries with a ragged margin.

Look at --preview before the fluid goes on: a guide that fitted itself to the wrong line is plain there.

Usage:
    fit_light_lines.py <reference> <guides.json> --sheet W,H [--paths paths.json] [--mask-pass pass.json]
        [--without reference.png] [--preview preview.png] [--reach 4] [--radius 1.4] [--removal-width 5]

Masking fluid shows pale yellow in a look. After `unmask` a whisker is bare paper at one width from root to tip; tint
its outer third toward the fur with a size 1.5 round so that it thins away (references/animal-portraits.md).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tonal_shapes import blurred

LUMA = np.array([0.2126, 0.7152, 0.0722])
# What a point gives up, in value, for each pixel it moves off its guide: without it a point with no line under it
# wanders to the nearest light hair.
STAY = 0.004


def curve_through(points: np.ndarray, step: float = 2.0) -> np.ndarray:
    """A smooth curve through the points (Catmull-Rom), as points about `step` pixels apart."""
    padded = np.vstack([2 * points[0] - points[1], points, 2 * points[-1] - points[-2]])
    out = []
    for index in range(len(points) - 1):
        a, b, c, d = padded[index : index + 4]
        count = max(2, int(np.linalg.norm(c - b) / step))
        for t in np.linspace(0, 1, count, endpoint=False):
            out.append(
                0.5 * ((2 * b) + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t**3)
            )
    out.append(points[-1])
    return np.array(out)


def sampled(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """The image between pixels, by the four around each point."""
    x = np.clip(x, 0, image.shape[1] - 1.001)
    y = np.clip(y, 0, image.shape[0] - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    top = image[y0, x0] * (1 - fx) + image[y0, x0 + 1] * fx
    bottom = image[y0 + 1, x0] * (1 - fx) + image[y0 + 1, x0 + 1] * fx
    return top * (1 - fy) + bottom * fy


def fitted(guide: np.ndarray, thin_light: np.ndarray, reach: float) -> np.ndarray:
    """The guide's curve, each point moved across it to the lightest thin line within reach."""
    curve = curve_through(guide)
    tangent = np.gradient(curve, axis=0)
    normal = np.stack([-tangent[:, 1], tangent[:, 0]], 1)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-9)
    offsets = np.arange(-reach, reach + 0.25, 0.5)
    found = np.stack(
        [sampled(thin_light, curve[:, 0] + o * normal[:, 0], curve[:, 1] + o * normal[:, 1]) for o in offsets]
    )
    best = offsets[np.argmax(found - STAY * np.abs(offsets)[:, None], axis=0)]
    window = np.exp(-(np.arange(-12, 13) ** 2) / (2 * 4.0**2))
    best = np.convolve(np.pad(best, 12, mode="edge"), window / window.sum(), mode="valid")
    return curve + best[:, None] * normal


def painted_out(reference: np.ndarray, lines: list[np.ndarray], width: int) -> np.ndarray:
    """The reference with each line replaced by the mean of what lies beside it."""
    canvas = Image.new("L", (reference.shape[1], reference.shape[0]), 0)
    for line in lines:
        ImageDraw.Draw(canvas).line([tuple(point) for point in line.round()], fill=255, width=width)
    gone = np.asarray(canvas) > 0
    kept = (~gone).astype(np.float64)
    beside = blurred(reference * kept[..., None], 3.0) / np.maximum(blurred(kept, 3.0), 1e-6)[..., None]
    out = reference.copy()
    out[gone] = beside[gone]
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("guides", help='a JSON file: {"name": [[x, y], ...], ...}, each root first, in sheet pixels')
    parser.add_argument("--sheet", required=True, help="the sheet's size: W,H")
    parser.add_argument("--paths", default=None, help="write the fitted lines here")
    parser.add_argument("--mask-pass", default=None, help="write a pass of masking fluid along them here")
    parser.add_argument("--without", default=None, help="write the reference with the lines painted out here")
    parser.add_argument("--preview", default=None, help="write the fitted lines drawn over the reference here")
    parser.add_argument("--reach", type=float, default=4.0, help="how far a point may move off its guide, in pixels")
    parser.add_argument("--radius", type=float, default=1.4, help="the fluid's radius at the root")
    parser.add_argument("--removal-width", type=int, default=5)
    arguments = parser.parse_args()

    size = tuple(int(value) for value in arguments.sheet.split(","))
    image = Image.open(arguments.reference).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    reference = np.asarray(image).astype(np.float64)
    value = reference @ LUMA / 255
    thin_light = blurred(value, 0.8) - blurred(value, 3.0)
    guides = json.loads(Path(arguments.guides).read_text())
    short = [name for name, guide in guides.items() if len(guide) < 2]
    if short:
        raise SystemExit(f"a guide needs at least two points: {', '.join(short)}")
    lines = {name: fitted(np.array(guide, dtype=float), thin_light, arguments.reach) for name, guide in guides.items()}

    if arguments.paths:
        rounded = {name: [[round(float(x), 1), round(float(y), 1)] for x, y in line] for name, line in lines.items()}
        Path(arguments.paths).write_text(json.dumps(rounded))
    if arguments.mask_pass:
        actions = []
        for line in lines.values():
            points = line[:: max(1, len(line) // 30)]  # a point every few pixels is enough for a smooth stroke
            if not np.array_equal(points[-1], line[-1]):
                points = np.vstack([points, line[-1]])
            pressures = np.linspace(1.0, 0.25, len(points))
            path = [
                [round(float(x), 1), round(float(y), 1), round(float(p), 2)] for (x, y), p in zip(points, pressures)
            ]
            actions.append({"action": "mask", "path": path, "radius": arguments.radius, "smooth": True})
        Path(arguments.mask_pass).write_text(json.dumps(actions))
    if arguments.without:
        out = painted_out(reference, list(lines.values()), arguments.removal_width)
        Image.fromarray(out.round().astype(np.uint8)).save(arguments.without)
    if arguments.preview:
        every = np.vstack(list(lines.values()))
        x0, y0 = np.maximum(every.min(0) - 12, 0).astype(int)
        x1, y1 = np.minimum(every.max(0) + 12, np.array(size) - 1).astype(int)
        zoom = 3
        crop = Image.fromarray((reference * 0.8).astype(np.uint8)).crop((x0, y0, x1, y1))
        crop = crop.resize(((x1 - x0) * zoom, (y1 - y0) * zoom), Image.Resampling.BICUBIC)
        pen = ImageDraw.Draw(crop)
        for number, (name, line) in enumerate(lines.items()):
            colour = [(255, 0, 0), (0, 200, 255), (0, 220, 0), (255, 0, 255)][number % 4]
            scaled = [((x - x0) * zoom, (y - y0) * zoom) for x, y in line]
            pen.line(scaled, fill=colour, width=1)
            pen.text((scaled[-1][0] + 4, scaled[-1][1] + 2), name, fill=colour)
        crop.save(arguments.preview)
    moved = max(
        float(np.abs(line - curve_through(np.array(guides[name], dtype=float))).max()) for name, line in lines.items()
    )
    print(f"{len(lines)} lines fitted; the furthest any point moved off its guide was {moved:.1f} pixels")


if __name__ == "__main__":
    main()

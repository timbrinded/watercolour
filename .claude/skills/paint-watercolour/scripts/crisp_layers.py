"""Crisp layers: lay what the sheet still lacks as hard-edged shapes, each filled with rounds that stay inside it.

measured_layers.py lays the least gap under each footprint, so a passage full of small lights and darks, such as
breaking foam, dries soft and rimmed. This tool cuts the passage into shapes first and fills each one crisply:

  1. The shapes are where the gap (reference less sheet, mean absorbance) is above `--threshold`, inside `--region`
     and, with `--within mask.png`, where that image is white (an image the size of the sheet being painted). Lights
     are left out: wherever the reference's absorbance is under `--lightest` in every channel, in patches of at
     least `--least-light` pixels. `--darkest V` keeps the shapes to where the reference's value is under V. Holes
     and specks smaller than `--holes` and `--specks` pixels are closed.
  2. Each shape is filled with rows of rounds, largest size first. At every point a stroke's radius is held under
     the distance to the shape's edge, so no footprint leaves the shape and the stroke's edge dries on the shape's
     edge. Each smaller size fills what the larger ones could not reach.
  3. A stroke's mix is solved for the mean gap under its footprint, the gap first capped at `--cap` mean absorbance.
     With `--smooth-mix R` the gap is blurred by R pixels inside the shapes only, so neighbouring strokes carry nearly
     the same mix and the passage dries smooth: the face of a wave.

Repeat it from a look taken after each `dry`, with rising thresholds. Breaking foam took five layers, as
threshold/cap pairs 0.05/0.3, 0.1/0.45, 0.2/0.7, 0.3/1.2, 0.3/2.0 (`references/water.md`). The dark water under a
breaking crest took two layers with `--threshold 0 --cap 5 --darkest 0.55 --smooth-mix 3 --holes 6
--sizes 8,4,2,1.2`: the first with no `--look` and `--gain 0.85`, the second from a look of the dried first.

Usage:
    crisp_layers.py <reference> <output pass.json> --sheet W,H --paints cobalt_blue,phthalo_green,burnt_sienna,...
        [--look <current look>] --threshold 0.05 [--cap 0.3] [--sizes 6,2.5,1.2] [--gain 1.0]
        [--lightest 0.12] [--least-light 3] [--darkest V] [--smooth-mix R] [--holes 3] [--specks 6]
        [--region x0,y0,x1,y1] [--within mask.png] [--origin x,y --crop W,H] [--white r,g,b]
        [--hair red_sable] [--water 0.9] [--no-dry] [--preview preview.png]

--paints and the Python to run it with are as for measured_layers.py. A look must be one taken after a `dry`.
Without --look the sheet is taken to be bare paper: on a printed ground (`new --ground`), give a look.
"""

import argparse
import json
import math

import numpy as np
import torch
from measured_layers import paint_absorption, solve_mix, target_and_sheet, to_load
from PIL import Image
from torch.nn import functional


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


def without_small(mask: np.ndarray, least: int) -> np.ndarray:
    """The mask with its patches of fewer than `least` pixels dropped."""
    kept = np.zeros_like(mask)
    for patch in patches(mask):
        if len(patch) >= least:
            kept[patch[:, 0], patch[:, 1]] = True
    return kept


def distance_inside(mask: np.ndarray) -> np.ndarray:
    """Distance in pixels from each pixel of the mask to the nearest pixel outside it, by erosion alternating a
    square and a cross (an octagonal distance). The sheet's edge does not count as outside."""
    current = torch.from_numpy(mask.astype(np.float32))[None, None]
    distance = torch.zeros_like(current)
    cross = torch.tensor([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=torch.float32)[None, None]
    for step in range(60):
        if current.sum() == 0:
            break
        distance += current
        if step % 2 == 0:
            current = -functional.max_pool2d(-current, 3, stride=1, padding=1)
        else:
            current = (functional.conv2d(current, cross, padding=1) >= 5).float()
    return distance[0, 0].numpy()


def blur_inside(values: np.ndarray, mask: np.ndarray, radius: float) -> np.ndarray:
    """Gaussian blur of an H x W x 3 image using only the pixels inside the mask, so nothing outside leaks in."""
    reach = int(3 * radius + 0.5)
    taps = np.exp(-0.5 * (np.arange(-reach, reach + 1) / radius) ** 2)
    taps = torch.tensor(taps / taps.sum(), dtype=torch.float32)

    def blur(image: np.ndarray) -> np.ndarray:
        tensor = torch.from_numpy(image.astype(np.float32))[None, None]
        tensor = functional.conv2d(
            functional.pad(tensor, (reach, reach, 0, 0), mode="replicate"), taps.view(1, 1, 1, -1)
        )
        tensor = functional.conv2d(
            functional.pad(tensor, (0, 0, reach, reach), mode="replicate"), taps.view(1, 1, -1, 1)
        )
        return tensor[0, 0].numpy()

    weight = blur(mask.astype(np.float32))
    blurred = np.stack([blur(values[..., channel] * mask) for channel in range(3)], axis=2)
    return np.where(mask[..., None], blurred / np.maximum(weight, 1e-6)[..., None], 0.0)


def shapes(target: np.ndarray, current: np.ndarray, white: np.ndarray, arguments) -> tuple[np.ndarray, np.ndarray]:
    """The shapes this layer fills, and the gap each pixel of them should receive."""
    height, width = target.shape[:2]
    gap = np.maximum(target - current, 0.0)
    mean = gap.mean(axis=2)
    allowed = np.ones((height, width), bool)
    if arguments.region:
        x0, y0, x1, y1 = (int(value) for value in arguments.region.split(","))
        allowed[:] = False
        allowed[max(0, y0) : y1, max(0, x0) : x1] = True
    if arguments.within:
        within = Image.open(arguments.within).convert("L").resize((width, height), Image.Resampling.NEAREST)
        allowed &= np.asarray(within) > 127
    lights = without_small(target.max(axis=2) < arguments.lightest, arguments.least_light)
    allowed &= ~lights
    if arguments.darkest is not None:
        value = (white * np.exp(-target)).mean(axis=2) / 255.0
        allowed &= value < arguments.darkest
    mask = without_small(allowed & (mean > arguments.threshold), arguments.specks)
    mask = ~without_small(~mask, arguments.holes) & allowed
    wanted = gap * np.minimum(1.0, arguments.cap / np.maximum(mean, 1e-6))[..., None]
    if arguments.smooth_mix:
        wanted = blur_inside(wanted, mask, arguments.smooth_mix)
    return mask, wanted


def rows_inside(mask: np.ndarray, sizes: list[float], longest: int = 140):
    """The strokes of rows of rounds over every shape of the mask, largest size first: each yielded as (size, y,
    points, foot), with points as (x, pressure, radius) and foot the pixels it covers. At every point the round's
    radius is held under the distance to the shape's edge; each smaller size fills what the larger ones left."""
    height, width = mask.shape
    distance = distance_inside(mask)
    remaining = mask.copy()
    rows, columns = np.mgrid[0:height, 0:width]
    for size in sizes:
        widest = size * (0.54 + 1.63 * 0.95)
        narrowest = size * 0.54 / 2 + 0.15
        spacing = max(1.0, 0.62 * widest)
        reach = math.ceil(widest / 2)
        covered = np.zeros_like(mask)
        row, y = 0, spacing / 2
        while y < height:
            yi = round(y)
            if yi >= height:
                break
            near = remaining[max(0, yi - reach) : yi + reach + 1].any(axis=0)
            reachable = np.nonzero((distance[yi] - 0.3 >= narrowest) & near)[0]
            runs = [
                (int(run[0]), int(run[-1]))
                for run in np.split(reachable, np.nonzero(np.diff(reachable) != 1)[0] + 1)
                if len(run)
            ]
            if row % 2:
                runs = [(b, a) for a, b in reversed(runs)]
            for a, b in runs:
                step = 1 if b >= a else -1
                run = list(range(a, b + step, step))
                for first in range(0, len(run), longest):
                    piece = run[first : first + longest]
                    points = []
                    for x in piece[::3] + ([piece[-1]] if (len(piece) - 1) % 3 else []):
                        radius = min(widest / 2, distance[yi, x] - 0.3)
                        pressure = float(np.clip((2 * radius / size - 0.54) / 1.63, 0.0, 0.95))
                        points.append((int(x), pressure, size * (0.54 + 1.63 * pressure) / 2))
                    foot = np.zeros_like(mask)
                    for x, _, radius in points:
                        y0, y1 = int(max(0, yi - radius - 1)), int(min(height - 1, yi + radius + 1))
                        x0, x1 = int(max(0, x - radius - 2)), int(min(width - 1, x + radius + 2))
                        foot[y0 : y1 + 1, x0 : x1 + 1] |= (rows[y0 : y1 + 1, x0 : x1 + 1] - yi) ** 2 + (
                            columns[y0 : y1 + 1, x0 : x1 + 1] - x
                        ) ** 2 <= radius * radius
                    foot &= mask
                    if not foot.any():
                        continue
                    covered |= foot
                    yield size, yi, points, foot
            y += spacing
            row += 1
        remaining &= ~covered


def fill(mask: np.ndarray, wanted: np.ndarray, arguments) -> list[dict]:
    """A pass of rounds over every shape of the mask, each carrying the mix for the mean gap under its footprint."""
    actions = []
    for size, y, points, foot in rows_inside(mask, arguments.sizes, arguments.longest):
        load = to_load(solve_mix(wanted[foot].mean(axis=0), arguments.absorption), arguments.gain, size)
        if not load:
            continue
        actions.append(
            {
                "action": "load",
                "brush": "round",
                "hair": arguments.hair,
                "size": size,
                "pigments": load,
                "water": arguments.water,
            }
        )
        if len(points) == 1:
            x, pressure, _ = points[0]
            actions.append({"action": "stroke", "path": [[x + 0.5, y + 0.5, round(pressure, 3)]], "dwell": 0.2})
        else:
            actions.append(
                {
                    "action": "stroke",
                    "smooth": True,
                    "speed": arguments.speed,
                    "path": [[x + 0.5, y + 0.5, round(p, 3)] for x, p, _ in points],
                }
            )
    return actions


def preview(target: np.ndarray, white: np.ndarray, mask: np.ndarray, path: str) -> None:
    picture = (white * np.exp(-target)).clip(0, 255)
    picture[mask] = picture[mask] * 0.4 + np.array([255.0, 0.0, 0.0]) * 0.6
    image = Image.fromarray(picture.astype(np.uint8))
    image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST).save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="full sheet size the reference is scaled to: W,H")
    parser.add_argument("--paints", required=True, help="the paints a mix may use, comma separated")
    parser.add_argument("--look", default=None)
    parser.add_argument("--origin", default=None)
    parser.add_argument("--crop", default=None)
    parser.add_argument("--threshold", type=float, required=True, help="paint where the mean gap is above this")
    parser.add_argument("--cap", type=float, default=0.3, help="a stroke lays at most this mean absorbance")
    parser.add_argument("--sizes", default="6,2.5,1.2", help="round sizes, largest first")
    parser.add_argument("--gain", type=float, default=1.0)
    parser.add_argument("--lightest", type=float, default=0.12, help="keep as paper where every channel is under this")
    parser.add_argument("--least-light", type=int, default=3, help="smallest light, in pixels, that is kept")
    parser.add_argument(
        "--darkest", type=float, default=None, help="paint only where the reference's value is under this"
    )
    parser.add_argument("--smooth-mix", type=float, default=0.0, help="blur radius of the gap inside the shapes")
    parser.add_argument("--holes", type=int, default=3, help="close holes in a shape smaller than this many pixels")
    parser.add_argument("--specks", type=int, default=6, help="drop shapes smaller than this many pixels")
    parser.add_argument("--region", default=None, help="paint only inside x0,y0,x1,y1 (sheet coordinates)")
    parser.add_argument("--within", default=None, help="paint only where this image is white (the sheet's size)")
    parser.add_argument(
        "--white",
        default="255,255,255",
        help="the colour of the reference's own paper: r,g,b (pure white unless given)",
    )
    parser.add_argument("--hair", default="red_sable")
    parser.add_argument("--water", type=float, default=0.9)
    parser.add_argument("--speed", type=float, default=200)
    parser.add_argument("--longest", type=int, default=140, help="longest stroke, in pixels")
    parser.add_argument("--no-dry", action="store_true")
    parser.add_argument("--preview", default=None, help="draw this layer's shapes over the reference into this image")
    arguments = parser.parse_args()

    arguments.sizes = [float(value) for value in arguments.sizes.split(",")]
    arguments.absorption = paint_absorption([name for name in arguments.paints.split(",") if name])
    target, current = target_and_sheet(parser, arguments)
    white = np.array([float(value) for value in arguments.white.split(",")])
    mask, wanted = shapes(target, current, white, arguments)
    actions = fill(mask, wanted, arguments)
    if not arguments.no_dry:
        actions.append({"action": "dry"})
    with open(arguments.output, "w") as handle:
        json.dump(actions, handle)
    strokes = sum(1 for action in actions if action["action"] == "stroke")
    print(f"{arguments.output}: {strokes} strokes over {int(mask.sum())} pixels")
    if arguments.preview:
        preview(target, white, mask, arguments.preview)


if __name__ == "__main__":
    main()

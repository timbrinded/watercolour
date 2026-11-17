"""Mask lights: masking fluid (harness 0.8.0 or later) over the lights of a reference that a wash must cross.

  1. The lights are where the reference's absorbance is under `--lightest` in every channel, inside `--region` and,
     with `--within mask.png`, where that image is white. With `--streaks C` they also take in thin lines brighter
     than the reference blurred by 4 pixels by C levels out of 255 (and lighter than `--streak-least`): the white
     streaks running down a wave's face.
  2. Only what the fluid can keep is masked. It holds a shape about 2 pixels in radius and more
     (`--least-radius`): every light pixel within that distance of a point at least that far inside the light.
     Narrower lights are not masked; the count of their pixels is printed, and they are for the washes to paint
     round (crisp_layers.py keeps them as paper).
  3. Each light is filled with rows of `mask` strokes whose width at every point stays inside the light, so the
     fluid's edge falls on the light's edge.

The pass holds only `mask` actions, laid on dry paper. Paint over them freely, `dry`, then `{"action": "unmask"}`.
Paint dried on the rubber comes away with it. `--save-mask` writes the masked pixels as an image the size of the
sheet, for `--within` and for checking.

Usage:
    mask_lights.py <reference> <output pass.json> --sheet W,H [--lightest 0.12] [--least-radius 2]
        [--streaks 30 --streak-least 140] [--region x0,y0,x1,y1] [--within mask.png] [--origin x,y --crop W,H]
        [--white r,g,b] [--sizes 6,2.5,1.2] [--save-mask masked.png] [--preview preview.png]

Run it with the Python the harness uses, as for measured_layers.py.
"""

import argparse
import json

import numpy as np
import torch
from crisp_layers import distance_inside, rows_inside
from measured_layers import target_and_sheet
from PIL import Image, ImageFilter
from torch.nn import functional

# The width of a line of masking fluid laid with no pressure, as a share of its full width (watercolor.studio).
LIGHTEST_SHARE = 0.15


def lights(target: np.ndarray, white: np.ndarray, arguments) -> np.ndarray:
    height, width = target.shape[:2]
    found = target.max(axis=2) < arguments.lightest
    if arguments.streaks:
        grey = (white * np.exp(-target)).mean(axis=2)
        surround = np.asarray(
            Image.fromarray(grey.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4)), dtype=np.float64
        )
        found |= (grey - surround > arguments.streaks) & (grey > arguments.streak_least)
    if arguments.region:
        x0, y0, x1, y1 = (int(value) for value in arguments.region.split(","))
        box = np.zeros_like(found)
        box[max(0, y0) : y1, max(0, x0) : x1] = True
        found &= box
    if arguments.within:
        within = Image.open(arguments.within).convert("L").resize((width, height), Image.Resampling.NEAREST)
        found &= np.asarray(within) > 127
    return found


def keepable(found: np.ndarray, least_radius: float) -> np.ndarray:
    """The part of the lights broad enough for the fluid to keep: an opening by `least_radius`."""
    core = distance_inside(found) >= least_radius
    reach = int(np.ceil(least_radius))
    grown = (
        functional.max_pool2d(
            torch.from_numpy(core.astype(np.float32))[None, None], 2 * reach + 1, stride=1, padding=reach
        )[0, 0].numpy()
        > 0
    )
    return grown & found


def mask_pass(masked: np.ndarray, sizes: list[float]) -> list[dict]:
    actions = []
    for size, y, points, _ in rows_inside(masked, sizes):
        full = size * (0.54 + 1.63 * 0.95) / 2
        path = [
            [x + 0.5, y + 0.5, round(float(np.clip((radius / full - LIGHTEST_SHARE) / (1 - LIGHTEST_SHARE), 0, 1)), 3)]
            for x, _, radius in points
        ]
        actions.append({"action": "mask", "radius": round(full, 2), "smooth": True, "path": path})
    return actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="full sheet size the reference is scaled to: W,H")
    parser.add_argument("--origin", default=None)
    parser.add_argument("--crop", default=None)
    parser.add_argument(
        "--lightest", type=float, default=0.12, help="a light is under this absorbance in every channel"
    )
    parser.add_argument("--least-radius", type=float, default=2.0, help="narrowest light the fluid is laid on")
    parser.add_argument(
        "--streaks", type=float, default=0.0, help="also mask lines this many levels above their surround"
    )
    parser.add_argument("--streak-least", type=float, default=140.0, help="a streak is lighter than this (0 to 255)")
    parser.add_argument("--region", default=None, help="mask only inside x0,y0,x1,y1 (sheet coordinates)")
    parser.add_argument("--within", default=None, help="mask only where this image is white (the sheet's size)")
    parser.add_argument(
        "--white",
        default="255,255,255",
        help="the colour of the reference's own paper: r,g,b (pure white unless given)",
    )
    parser.add_argument("--sizes", default="6,2.5,1.2", help="the round sizes whose rows the fluid follows")
    parser.add_argument("--save-mask", default=None)
    parser.add_argument("--preview", default=None, help="the masked lights in cyan over the reference")
    arguments = parser.parse_args()
    arguments.look = None

    target, _ = target_and_sheet(parser, arguments)
    white = np.array([float(value) for value in arguments.white.split(",")])
    found = lights(target, white, arguments)
    masked = keepable(found, arguments.least_radius)
    actions = mask_pass(masked, [float(value) for value in arguments.sizes.split(",")])
    with open(arguments.output, "w") as handle:
        json.dump(actions, handle)
    print(
        f"{arguments.output}: {len(actions)} mask strokes over {int(masked.sum())} pixels; "
        f"{int((found & ~masked).sum())} light pixels too narrow to mask"
    )
    if arguments.save_mask:
        Image.fromarray((masked * 255).astype(np.uint8)).save(arguments.save_mask)
    if arguments.preview:
        picture = (white * np.exp(-target)).clip(0, 255)
        picture[masked] = np.array([0.0, 220.0, 255.0])
        image = Image.fromarray(picture.astype(np.uint8))
        image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST).save(arguments.preview)


if __name__ == "__main__":
    main()

"""Isolate a subject: a photograph's subject alone on paper white, in a high key, at the sheet's size.

A photograph taken indoors is dark, tinted by its lamp and full of things that are not the subject. This makes the
reference a portrait is measured from (references/animal-portraits.md, "From a photograph"):

  1. The photograph and a mask of the subject (white where the subject is, from any tool) are cropped with --crop and
     scaled to the sheet.
  2. The subject's own lightest passage becomes paper: each channel is divided by its --white-percentile inside the
     mask, which also takes off the colour of the lamp. Values are then lifted, ((v - black) / (1 - black)) ** gamma,
     so the middle of a dim photograph lands in a watercolour's key while its darkest darks stay dark.
  3. The subject's colour is carried outward past the mask's edge before that edge is feathered over --feather
     pixels, so the soft edge is the subject's colour and not the room's.
  4. Each --let-go x0,y0,x1,y1 lets the subject fade into the paper along a line, fully kept at the first point and
     gone at the second, with an uneven front (--wander, as a share of the line's length).

With --alpha it also writes how much of the subject is kept at each pixel, which soften_outline.py and coat_hairs.py
read.

Usage:
    isolate_subject.py <photograph> <mask.png> <output.png> --sheet W,H [--crop x0,y0,x1,y1] [--alpha alpha.png]
        [--white-percentile 99.8] [--black 0.03] [--gamma 0.56] [--local-contrast 0.3] [--feather 15]
        [--let-go x0,y0,x1,y1 ...] [--wander 0.4] [--seed 11]

Run it with the Python that the watercolor tool uses.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shape_strokes import erode, half_width
from tonal_shapes import blurred

LUMA = np.array([0.2126, 0.7152, 0.0722])
# The share of the feather that lies outside the mask's edge: fur has a fringe beyond the outline a mask finds.
FEATHER_OUTSIDE = 0.6


def smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def toned(photograph: np.ndarray, subject: np.ndarray, percentile: float, black: float, gamma: float) -> np.ndarray:
    """The photograph with the subject's lightest passage as paper and its values lifted, from 0 to 1."""
    white = np.percentile(photograph[subject], percentile, axis=0)
    balanced = np.clip(photograph / white, 0.0, 1.0)
    value = balanced @ LUMA
    lifted = np.clip((value - black) / (1 - black), 0.0, 1.0) ** gamma
    # Lifting the value alone keeps a colour's full saturation and lifting each channel loses most of it; half of
    # each keeps a coat's colour without making it garish.
    by_ratio = balanced * (lifted / np.maximum(value, 1e-4))[..., None]
    by_channel = np.clip((balanced - black) / (1 - black), 0.0, 1.0) ** gamma
    return np.clip(0.5 * by_ratio + 0.5 * by_channel, 0.0, 1.0)


def carried_outward(colour: np.ndarray, subject: np.ndarray) -> np.ndarray:
    """The subject's colour extended past its edge: each outside pixel takes the mean of the subject near it."""
    inside = erode(subject, 3)
    weight = inside.astype(np.float64)
    out = colour.copy()
    filled = inside.copy()
    for sigma in (5.0, 16.0, 48.0):
        reach = blurred(weight, sigma)
        mean = blurred(colour * weight[..., None], sigma) / np.maximum(reach, 1e-6)[..., None]
        take = ~filled & (reach > 1e-3)
        out[take] = mean[take]
        filled |= take
    out[~filled] = 1.0
    return out


def kept_share(subject: np.ndarray, feather: float) -> np.ndarray:
    """How much of the subject is kept at each pixel: 1 inside, falling to 0 across the feather."""
    limit = int(feather) + 3
    # The mask is carried past the sheet's borders as it stands at them. Otherwise a border counts as an edge of the
    # subject and of the room alike: a subject that runs off the sheet fades at the border, and a faint frame of the
    # subject's colour is kept all round the sheet.
    beyond = np.pad(subject, limit, mode="edge")
    signed = (half_width(beyond, limit) - half_width(~beyond, limit))[limit:-limit, limit:-limit]
    return smoothstep((signed + FEATHER_OUTSIDE * feather) / feather)


def let_go(shape: tuple[int, int], line: tuple[float, float, float, float], wander: np.ndarray) -> np.ndarray:
    """1 where the subject is kept and 0 where it has gone, along the line from (x0, y0) to (x1, y1)."""
    x0, y0, x1, y1 = line
    yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]].astype(np.float64)
    along = ((xx - x0) * (x1 - x0) + (yy - y0) * (y1 - y0)) / ((x1 - x0) ** 2 + (y1 - y0) ** 2)
    return 1.0 - smoothstep(along + wander)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("photograph")
    parser.add_argument("mask", help="white where the subject is, the photograph's size")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="the sheet's size: W,H")
    parser.add_argument("--crop", default=None, help="the part of the photograph to use: x0,y0,x1,y1")
    parser.add_argument("--alpha", default=None, help="write the share of the subject kept at each pixel here")
    parser.add_argument("--white-percentile", type=float, default=99.8)
    parser.add_argument("--black", type=float, default=0.03)
    parser.add_argument("--gamma", type=float, default=0.56)
    parser.add_argument("--local-contrast", type=float, default=0.3)
    parser.add_argument("--feather", type=float, default=15.0)
    parser.add_argument("--let-go", action="append", default=[], help="x0,y0,x1,y1 in sheet pixels (repeatable)")
    parser.add_argument("--wander", type=float, default=0.4)
    parser.add_argument("--seed", type=int, default=11)
    arguments = parser.parse_args()

    width, height = (int(value) for value in arguments.sheet.split(","))
    photograph = Image.open(arguments.photograph).convert("RGB")
    mask = Image.open(arguments.mask).convert("L")
    if mask.size != photograph.size:
        parser.error(f"the mask is {mask.size} and the photograph {photograph.size}: they must be the same size")
    if arguments.crop:
        box = tuple(int(value) for value in arguments.crop.split(","))
        photograph, mask = photograph.crop(box), mask.crop(box)
    if abs(photograph.width / photograph.height - width / height) > 0.02:
        parser.error("the crop and the sheet differ in proportion by more than 2%: give --crop in the sheet's")
    colour = np.asarray(photograph.resize((width, height), Image.Resampling.LANCZOS)).astype(np.float64)
    subject = np.asarray(mask.resize((width, height), Image.Resampling.BOX)) > 127
    if not subject.any():
        parser.error("the mask is empty inside the crop")

    picture = toned(colour, subject, arguments.white_percentile, arguments.black, arguments.gamma)
    if arguments.local_contrast:
        picture = np.clip(picture + arguments.local_contrast * (picture - blurred(picture, 14.0)), 0.0, 1.0)
    picture = carried_outward(picture, subject)

    kept = kept_share(subject, arguments.feather)
    rng = np.random.default_rng(arguments.seed)
    front = blurred(rng.standard_normal((height, width)), 45.0)
    front = arguments.wander * front / np.abs(front).max()
    for entry in arguments.let_go:
        kept = kept * let_go((height, width), tuple(float(value) for value in entry.split(",")), front)

    reference = picture * kept[..., None] + (1.0 - kept[..., None])
    Image.fromarray((reference * 255).round().astype(np.uint8)).save(arguments.output)
    if arguments.alpha:
        Image.fromarray((kept * 255).round().astype(np.uint8)).save(arguments.alpha)
    paper = float((reference.min(axis=2) > 0.98).mean())
    print(f"{arguments.output}: mean value {float((reference @ LUMA).mean()):.2f}, {paper:.0%} of the sheet paper")


if __name__ == "__main__":
    main()

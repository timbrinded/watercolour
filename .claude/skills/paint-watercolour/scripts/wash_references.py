"""The references a layered copy is painted from when one large light is kept under masking fluid.

A wet wash floods: laid from the reference itself, its darks run into the middle tones beside them and the sheet
dries as one dark mass. Laid from a reference in which every light has been spread into its surround, the wet wash
stays as light as the lightest thing near it, and the darks are then built over it on dry paper, where they stay
where they are put (`references/seascapes.md`).

Usage:
    wash_references.py <reference> <output directory> --sheet W,H
        (--shape shape.png | --seed x,y [--lighter-than 0.42] [--warmer-than 0.07])
        [--reach 7] [--margin 24]

Writes into the output directory, each the sheet's size:
    shape.png   the large light's silhouette, white on black: what mask_lights.py lays the fluid on. Given with
                --shape, or grown from --seed: the pixels joined to the seed that are lighter than --lighter-than
                and, with --warmer-than, redder than they are blue by that much. Necks under nine pixels wide are
                cut, so a pale spar touching a sail is left out, and the holes a stain leaves inside it are closed.
    tint.png    the shape's own colour carried --margin pixels past its edge, on white: what a tint laid on bare
                paper before the fluid aims at, so that the tint runs under the fluid's edge everywhere.
    filled.png  the reference with the shape filled in by its surround: what the darks aim at while the fluid is
                on, so that they run up to the fluid and over it.
    ground.png  filled.png with every light spread --reach pixels into its surround: what the first, wet washes
                aim at.

Run it with the Python the harness uses, as for measured_layers.py.
"""

import argparse
from pathlib import Path

import numpy as np
from measured_layers import pooled
from PIL import Image

LUMA = np.array([0.2126, 0.7152, 0.0722])
NECK = 4  # a neck narrower than 2 * NECK + 1 pixels does not join two lights
GLOW = 12  # a reproduction's light spills this far past the shape's edge, and lends no colour to its fill


def soft(array: np.ndarray, reach: float) -> np.ndarray:
    """Near a Gaussian of standard deviation `reach`: a box mean of twice that width laid three times, its edges
    held."""
    kernel = max(3, int(2 * reach) | 1)
    for _ in range(3):
        array = pooled(array, kernel, "mean")
    return array


def grown(mask: np.ndarray, reach: int) -> np.ndarray:
    return ~shrunk(~mask, reach)


def shrunk(mask: np.ndarray, reach: int) -> np.ndarray:
    return pooled(mask[..., None].astype(np.float32), 2 * reach + 1, "min")[..., 0] > 0.5


def joined(allowed: np.ndarray, starts: list[tuple[int, int]]) -> np.ndarray:
    """The allowed pixels that can be reached from the starting points through allowed pixels."""
    height, width = allowed.shape
    found = np.zeros_like(allowed)
    stack = [(x, y) for x, y in starts if allowed[y, x]]
    for x, y in stack:
        found[y, x] = True
    while stack:
        x, y = stack.pop()
        for u, v in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= u < width and 0 <= v < height and allowed[v, u] and not found[v, u]:
                found[v, u] = True
                stack.append((u, v))
    return found


def shape_from_seed(picture: np.ndarray, seed: tuple[int, int], lighter: float, warmer: float | None) -> np.ndarray:
    """The light joined to the seed other than by a narrow neck, with the holes inside it closed."""
    even = soft(picture, 1)
    light = even @ LUMA > lighter
    if warmer is not None:
        light &= even[..., 0] - even[..., 2] > warmer
    body = joined(shrunk(light, NECK), [seed])
    if not body.any():
        raise SystemExit(f"the seed {seed[0]},{seed[1]} is not well inside a light: lower --lighter-than or move it")
    shape = grown(body, NECK) & light
    height, width = shape.shape
    border = [(x, y) for x in range(width) for y in (0, height - 1)] + [
        (x, y) for y in range(height) for x in (0, width - 1)
    ]
    return ~joined(~shape, border)  # what the sheet's border cannot reach round the shape is a hole in it


def carried(picture: np.ndarray, source: np.ndarray, reaches: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    """The colours of the `source` pixels carried over the rest of the picture, the nearest first, and where they
    reached."""
    out, reached = picture.copy(), source.copy()
    held = picture * source[..., None]
    for reach in reaches:
        weight = soft(source[..., None].astype(np.float32), reach)
        here = ~reached & (weight[..., 0] > 0.05)
        out[here] = (soft(held, reach) / np.maximum(weight, 1e-4))[here]
        reached |= here
    return out, reached


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output", type=Path)
    parser.add_argument("--sheet", required=True, help="the sheet's size: W,H")
    parser.add_argument("--shape", default=None, help="the large light's silhouette, white on black")
    parser.add_argument("--seed", default=None, help="x,y of a point on the large light, to grow its silhouette from")
    parser.add_argument(
        "--lighter-than", type=float, default=0.42, help="the least value of the light grown from --seed"
    )
    parser.add_argument(
        "--warmer-than", type=float, default=None, help="its least red less blue, if it is a warm light"
    )
    parser.add_argument("--reach", type=int, default=7, help="how far each light is spread into its surround")
    parser.add_argument("--margin", type=int, default=24, help="how far the tint is carried past the shape")
    arguments = parser.parse_args()
    if (arguments.shape is None) == (arguments.seed is None):
        parser.error("give the large light as --shape or as --seed, one of the two")
    size = tuple(int(value) for value in arguments.sheet.split(","))
    picture = np.asarray(Image.open(arguments.reference).convert("RGB").resize(size, Image.LANCZOS), np.float32) / 255
    if arguments.shape:
        shape = np.asarray(Image.open(arguments.shape).convert("L").resize(size)) > 127
    else:
        seed = tuple(int(value) for value in arguments.seed.split(","))
        shape = shape_from_seed(picture, (seed[0], seed[1]), arguments.lighter_than, arguments.warmer_than)

    inside = shrunk(shape, 3)  # the shape's own colour, clear of its dark edge
    spread, reached = carried(picture, inside, (10,))
    fade = (
        np.clip(soft(grown(shape, arguments.margin)[..., None].astype(np.float32), 6) * 1.6, 0, 1) * reached[..., None]
    )
    tint = np.where(inside[..., None], picture, spread * fade + (1 - fade))

    covered = grown(shape, 5)
    filled, _ = carried(picture, ~grown(shape, GLOW), (10, 25, 60))
    filled = np.where(covered[..., None], filled, picture)

    window = 2 * arguments.reach + 1
    lights = soft(-pooled(-filled, window, "min"), arguments.reach * 0.7)
    ground = np.maximum(filled, lights)

    arguments.output.mkdir(parents=True, exist_ok=True)
    Image.fromarray((shape * 255).astype(np.uint8)).save(arguments.output / "shape.png")
    for name, image in (("tint", tint), ("filled", filled), ("ground", ground)):
        Image.fromarray((np.clip(image, 0, 1) * 255).round().astype(np.uint8)).save(arguments.output / f"{name}.png")
    print(f"{arguments.output}: the shape covers {int(shape.sum())} pixels")


if __name__ == "__main__":
    main()

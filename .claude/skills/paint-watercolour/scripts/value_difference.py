"""Compare a painting with the reference block by block and report where it is too dark, too light or off in colour.

Usage: value_difference.py <painting image> <reference> <output image> --sheet W,H [--block 16]
                           [--region x0,y0,x1,y1]

--sheet is the size of the sheet in its own pixels; the painting image may be any enlargement of it, and --block
and --region are in sheet pixels. The output shows, left to right: the painting, the reference, and a map in which
red marks blocks painted too dark and blue marks blocks painted too light.
"""

import argparse

import numpy as np
from PIL import Image


def luminance(image: np.ndarray) -> np.ndarray:
    return (0.2126 * image[..., 0] + 0.7152 * image[..., 1] + 0.0722 * image[..., 2]) / 255.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("painting")
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="the sheet's size in its own pixels: W,H")
    parser.add_argument("--block", type=int, default=16)
    parser.add_argument("--region", default=None)
    arguments = parser.parse_args()

    sheet_width, sheet_height = (int(value) for value in arguments.sheet.split(","))
    size = (sheet_width, sheet_height)
    painting = Image.open(arguments.painting).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    reference = Image.open(arguments.reference).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    if arguments.region:
        x0, y0, x1, y1 = (int(value) for value in arguments.region.split(","))
        painting, reference = painting.crop((x0, y0, x1, y1)), reference.crop((x0, y0, x1, y1))

    block = arguments.block
    columns, rows = painting.width // block, painting.height // block
    small = (columns, rows)
    painted = np.asarray(painting.resize(small, Image.Resampling.BOX)).astype(float)
    target = np.asarray(reference.resize(small, Image.Resampling.BOX)).astype(float)
    value_gap = luminance(painted) - luminance(target)  # positive: painting lighter than the reference
    colour_gap = np.sqrt(((painted - target) ** 2).sum(-1)) / 255.0

    heat = np.full((rows, columns, 3), 255.0)
    too_dark = np.clip(-value_gap / 0.4, 0, 1)
    too_light = np.clip(value_gap / 0.4, 0, 1)
    heat[..., 1] -= 255 * np.maximum(too_dark, too_light)
    heat[..., 2] -= 255 * too_dark
    heat[..., 0] -= 255 * too_light
    heat_image = Image.fromarray(heat.astype(np.uint8)).resize(painting.size, Image.Resampling.NEAREST)

    canvas = Image.new("RGB", (painting.width * 3 + 16, painting.height), "white")
    canvas.paste(painting, (0, 0))
    canvas.paste(reference, (painting.width + 8, 0))
    canvas.paste(heat_image, (painting.width * 2 + 16, 0))
    canvas.save(arguments.output)

    print(f"mean absolute value gap {np.abs(value_gap).mean():.3f}; mean colour distance {colour_gap.mean():.3f}")
    print(
        f"blocks too light by more than 0.15: {(value_gap > 0.15).mean():.0%}; too dark by more than 0.15: {(value_gap < -0.15).mean():.0%}"
    )

    # crispness: how much fine edge the painting has beside the reference, and whether its edges fall where the
    # reference's do (correlation of gradient magnitude after a light blur)
    def edges(image: Image.Image) -> np.ndarray:
        grey = luminance(
            np.asarray(image.resize((image.width // 2, image.height // 2), Image.Resampling.BOX)).astype(float)
        )
        return np.hypot(np.diff(grey, axis=0)[:, :-1], np.diff(grey, axis=1)[:-1, :])

    painted_edges, target_edges = edges(painting), edges(reference)
    agreement = np.corrcoef(painted_edges.ravel(), target_edges.ravel())[0, 1]
    print(
        f"edge energy: painting {painted_edges.mean():.4f}, reference {target_edges.mean():.4f}; edge agreement {agreement:.2f}"
    )
    fine = np.asarray(painting.resize((painting.width // 4, painting.height // 4), Image.Resampling.BOX)).astype(
        float
    ) - np.asarray(reference.resize((reference.width // 4, reference.height // 4), Image.Resampling.BOX)).astype(float)
    print(f"mean absolute value gap at 4 pixel blocks: {np.abs(luminance(fine)).mean():.3f}")
    print(
        f"darkest block: painting {luminance(painted).min():.2f}, reference {luminance(target).min():.2f}; "
        f"share of sheet lighter than 0.85: painting {(luminance(painted) > 0.85).mean():.0%}, reference {(luminance(target) > 0.85).mean():.0%}"
    )


if __name__ == "__main__":
    main()

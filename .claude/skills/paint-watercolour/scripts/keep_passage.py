"""Keep a passage: give a reference a passage exactly as it stands on the sheet, so no measured stage lays on it.

A passage painted by hand before the measured stages (an eye laid on bare paper, a sky in one wash) must be left as
it is. `--exclude` on the measuring scripts fences off a rectangle, which leaves the corners of the rectangle bare
round a passage of any other shape. This puts the passage into the reference instead: inside each --polygon, grown by
--margin pixels, the reference is replaced by the look. The sheet then lacks nothing there, and the footprint rule of
measured_layers.py keeps each brush off the passage in its own shape, a smaller brush coming closer.

Give the measuring scripts the reference this writes. Take the look plain (no --grid or --region) from the dry sheet,
after the passage is painted.

Usage:
    keep_passage.py <reference> <look> <output.png> --sheet W,H --polygon "x,y x,y x,y ..." [--polygon ...]
        [--margin 3] [--white r,g,b]

--white is the reference's own paper, pure white unless given, as for measured_layers.py.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measured_layers import sheet_paper
from shape_strokes import dilate


def passage(polygons: list[list[tuple[float, float]]], size: tuple[int, int], margin: int) -> np.ndarray:
    """The pixels inside any of the polygons, grown by the margin."""
    canvas = Image.new("L", size, 0)
    for polygon in polygons:
        ImageDraw.Draw(canvas).polygon(polygon, fill=255)
    return dilate(np.asarray(canvas) > 0, margin)


def kept(reference: np.ndarray, look: np.ndarray, inside: np.ndarray, paper: np.ndarray, white: np.ndarray):
    """The reference with the look's colour inside the passage, the sheet's paper carried to the reference's white."""
    out = reference.copy()
    out[inside] = np.clip(look[inside] / paper * white, 0.0, 255.0)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("look")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="the sheet's size: W,H")
    parser.add_argument("--polygon", action="append", required=True, help='"x,y x,y x,y ..." in sheet pixels')
    parser.add_argument("--margin", type=int, default=3)
    parser.add_argument("--white", default="255,255,255", help="the reference's own paper: r,g,b")
    arguments = parser.parse_args()

    size = tuple(int(value) for value in arguments.sheet.split(","))
    polygons = [[tuple(float(v) for v in point.split(",")) for point in entry.split()] for entry in arguments.polygon]
    if any(len(polygon) < 3 for polygon in polygons):
        parser.error("a polygon needs at least three points")
    reference = np.asarray(Image.open(arguments.reference).convert("RGB").resize(size, Image.Resampling.LANCZOS))
    look = np.asarray(Image.open(arguments.look).convert("RGB").resize(size, Image.Resampling.LANCZOS))
    inside = passage(polygons, size, arguments.margin)
    white = np.array([float(value) for value in arguments.white.split(",")])
    out = kept(reference.astype(np.float64), look.astype(np.float64), inside, sheet_paper(arguments.look), white)
    Image.fromarray(out.round().astype(np.uint8)).save(arguments.output)
    print(f"{arguments.output}: {int(inside.sum())} pixels kept as they stand on the sheet")


if __name__ == "__main__":
    main()

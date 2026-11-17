"""Posterise a style target by the bands that will paint it, to judge the planes before any paint goes down.

Each pixel is shaded by how many bands it falls in (white: none, so bare paper; black: all). The face must break into
planes in the skin bands; parallel rings in a smooth passage warn that those bands will paint as a contour map.

Usage: posterise_target.py <target.png> <output.png> --thresholds 0.88,0.76,0.62,0.48,0.32,0.20 [--blur 2]

Run it with the harness's Python, beside tonal_shapes.py.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tonal_shapes import LUMA, PAPER, blurred


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target")
    parser.add_argument("output")
    parser.add_argument("--thresholds", required=True)
    parser.add_argument("--blur", type=float, default=2.0, help="the bands' own --blur")
    arguments = parser.parse_args()
    thresholds = [float(part) for part in arguments.thresholds.split(",")]
    target = np.asarray(Image.open(arguments.target).convert("RGB")).astype(float)
    value = blurred((target @ LUMA) / (PAPER @ LUMA), arguments.blur)
    level = np.sum([value < threshold for threshold in thresholds], axis=0)
    shades = np.linspace(1.0, 0.08, len(thresholds) + 1)
    Image.fromarray((shades[level] * 255).astype(np.uint8)).save(arguments.output)
    shares = [100 * (level >= index + 1).mean() for index in range(len(thresholds))]
    print(
        f"{arguments.output}: share of sheet in each band "
        + ", ".join(f"{t}: {s:.0f}%" for t, s in zip(thresholds, shares))
    )


if __name__ == "__main__":
    main()

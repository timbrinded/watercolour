"""Measure a finished painting of the three given shapes against their outlines: grade_shapes.py <run directory>.

Prints one JSON object: for each shape how much of it is covered, how much paint lies outside it, how far the
painted edge strays from the outline on average, and how even the tone inside is; then how much of the paint lies
away from all three, and the number of strokes on the painting. The statements in `graders/` give the pass marks.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

run = Path(sys.argv[1])
shapes = json.loads((run / "outputs" / "shapes.json").read_text())["shapes"]
picture = Image.open(run / "outputs" / "painting.png").convert("RGB").resize((800, 600))
look = np.asarray(picture, dtype=float)
paper = np.median(look.reshape(-1, 3), axis=0)
tone = np.clip((paper - look).sum(axis=2) / 3, 0, None)  # how much darker than the paper
painted = tone > 12


def mask_of(points):
    image = Image.new("L", (800, 600), 0)
    ImageDraw.Draw(image).polygon([tuple(p) for p in points], fill=255)
    return image


def edge_of(mask):
    inner = mask[1:-1, 1:-1] & ~(mask[:-2, 1:-1] & mask[2:, 1:-1] & mask[1:-1, :-2] & mask[1:-1, 2:])
    ys, xs = np.nonzero(inner)
    return np.stack([xs + 1, ys + 1], axis=1).astype(float)


def nearest(a, b):
    """For each point of a, the distance to the nearest point of b."""
    out = np.empty(len(a))
    for start in range(0, len(a), 400):
        part = a[start : start + 400]
        out[start : start + 400] = np.sqrt(((part[:, None, :] - b[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
    return out


result, near_any = {}, np.zeros((600, 800), dtype=bool)
for name, points in shapes.items():
    image = mask_of(points)
    target = np.asarray(image) > 0
    cell = np.asarray(image.filter(ImageFilter.MaxFilter(81))) > 0  # the shape and 40 pixels round it
    core = np.asarray(image.filter(ImageFilter.MinFilter(25))) > 0  # the shape less 12 pixels at its edge
    near_any |= cell
    mine = painted & cell
    covered = (mine & target).sum() / target.sum()
    outside = (mine & ~target).sum() / target.sum()
    a, b = edge_of(mine), edge_of(target)
    off = float((nearest(a, b).mean() + nearest(b, a).mean()) / 2) if len(a) else 999.0
    inside = tone[core]
    result[name] = {
        "covered": round(float(covered), 3),
        "outside": round(float(outside), 3),
        "edge_off_px": round(off, 2),
        "tone_spread": round(float(inside.std() / max(1.0, inside.mean())), 3),
    }
result["elsewhere"] = round(float((painted & ~near_any).sum() / max(1, painted.sum())), 4)
strokes = sum(
    1
    for path in sorted((run / "outputs" / "passes").glob("*.json"))
    for action in json.loads(path.read_text())
    if action.get("action") == "stroke" and action.get("sheet") != "scrap"
)
result["strokes"] = strokes
print(json.dumps(result, indent=1))

"""Soften an outline: a clean damp brush run along the outside of a wash while it is wet.

A first wash laid by rows ends in a hard, scalloped edge. Run along the outside of that edge within about a minute,
a clean brush drained to 0.45 pulls the edge out into a soft band (SKILL.md, "Soft edge on one side"): the down of a
coat, the far side of a cloud. This writes that run for a whole outline:

  1. The outline is the longest edge of the image where it is lighter than --level: the alpha that isolate_subject.py
     writes, or any image that is white where the wash is.
  2. One run is laid for each of --offsets, that many pixels outside the outline, the nearer first.
  3. No run is laid inside a --keep-crisp rectangle (an ear, a beak, anything that must keep a hard edge), nor off
     the sheet.
  4. The stretches are laid from the top of the sheet down, the order in which rows are laid, so each reaches its
     part of the edge while that part still has a film on it.

Lay the wash with `--no-dry`, read the film along its edge (`look --at`: 0.15 or more), then paint this pass and
`dry`. Under 0.1 a damp brush leaves blooms, not a soft edge.

Usage:
    soften_outline.py <alpha.png> <output pass.json> --sheet W,H [--level 0.3] [--offsets 4,12] [--size 9]
        [--water 0.45] [--keep-crisp x0,y0,x1,y1 ...] [--stretch 260]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tonal_shapes import contours, resampled

STEP = 10.0  # pixels between the points of a run


def outline_and_outward(inside: np.ndarray, step: float = STEP, smoothing: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """The longest closed edge of a mask as points every `step` pixels, and the unit normal at each that points out.
    The edge is averaged over three points `smoothing` times: a row-stepped or furry edge wanders, and a brush
    following it should not."""
    loops = contours(inside)
    if not loops:
        raise SystemExit("nothing in the image is lighter than the level given: there is no outline to follow")
    loop = resampled(max(loops, key=len), step)
    for _ in range(smoothing):
        loop = (np.roll(loop, 1, 0) + loop + np.roll(loop, -1, 0)) / 3
    reach = max(1, round(3 / step))
    tangent = np.roll(loop, -reach, 0) - np.roll(loop, reach, 0)
    normal = np.stack([tangent[:, 1], -tangent[:, 0]], 1)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-9)
    probe = np.round(loop + 4 * normal).astype(int)
    on_sheet = (
        (probe[:, 0] >= 0) & (probe[:, 0] < inside.shape[1]) & (probe[:, 1] >= 0) & (probe[:, 1] < inside.shape[0])
    )
    if inside[probe[on_sheet, 1], probe[on_sheet, 0]].mean() > 0.5:
        normal = -normal
    return loop, normal


def stretches(points: np.ndarray, keep: np.ndarray, longest: float) -> list[np.ndarray]:
    """Runs of consecutive kept points round a closed loop, none longer than `longest` pixels."""
    order = np.roll(np.arange(len(points)), -int(np.argmin(keep))) if not keep.all() else np.arange(len(points))
    out, current = [], []
    for index in order:
        if keep[index]:
            current.append(points[index])
            if len(current) * STEP >= longest:
                out.append(np.array(current))
                current = [points[index]]
        else:
            if len(current) > 2:
                out.append(np.array(current))
            current = []
    if len(current) > 2:
        out.append(np.array(current))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("alpha", help="an image that is white where the wash is")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="the sheet's size: W,H")
    parser.add_argument("--level", type=float, default=0.3)
    parser.add_argument("--offsets", default="4,12", help="pixels outside the outline, one run for each")
    parser.add_argument("--size", type=float, default=9.0)
    parser.add_argument("--water", type=float, default=0.45)
    parser.add_argument("--keep-crisp", action="append", default=[], help="x0,y0,x1,y1 with no softening (repeatable)")
    parser.add_argument("--stretch", type=float, default=260.0, help="the longest run of one brush load, in pixels")
    arguments = parser.parse_args()

    width, height = (int(value) for value in arguments.sheet.split(","))
    image = Image.open(arguments.alpha).convert("L").resize((width, height), Image.Resampling.LANCZOS)
    outline, outward = outline_and_outward(np.asarray(image) > arguments.level * 255)
    crisp = [tuple(float(value) for value in box.split(",")) for box in arguments.keep_crisp]
    soft = np.array([not any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in crisp) for x, y in outline])

    actions = []
    for offset in (float(value) for value in arguments.offsets.split(",")):
        moved = outline + offset * outward
        keep = soft & (moved[:, 0] > 4) & (moved[:, 0] < width - 4) & (moved[:, 1] > 4) & (moved[:, 1] < height - 4)
        runs = sorted(stretches(moved, keep, arguments.stretch), key=lambda run: float(run[:, 1].mean()))
        for run in runs:
            actions.append(
                {"action": "load", "brush": "mop", "size": arguments.size, "pigments": {}, "water": arguments.water}
            )
            path = [[round(float(x), 1), round(float(y), 1), 0.7] for x, y in run]
            actions.append({"action": "stroke", "path": path, "speed": 220, "smooth": True})
    Path(arguments.output).write_text(json.dumps(actions))
    print(f"{arguments.output}: {len(actions) // 2} runs of a damp brush along the outline")


if __name__ == "__main__":
    main()

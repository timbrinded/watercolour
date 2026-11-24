"""Coat hairs: tapered hairs drawn on a dry coat, each in the fur's own colour and lying the way the fur lies.

The measured stages lay a coat as short touches, and a wash edge is a wall. A long coat reads from marks as long as
its hairs (references/animal-portraits.md). Two kinds are written here, both for a sheet that is dry:

  outline   Tufts of one to five hairs along the outline of the coat. Each hair starts inside the coat and leaves it
            on the point of the brush. Tufts stand at uneven gaps: evenly spaced single hairs read as a comb.
  long      Hairs as long as a lock, inside the coat. Each is followed from a seed through the reference's own grain
            (the direction along which the picture changes least), kept to the way the fur lies there, and drawn in
            the colour of the shadows it passes through.

The way the fur lies is given as --lie rules; the first whose rectangle holds the hair is used:

    --lie away:300,350@0,0,520,768     inside that rectangle the fur lies away from the point (a head, a ruff)
    --lie toward:1,0.1                 everywhere else it lies in that direction (a body, swept to the tail)

With no rule that holds, an outline hair leaves square to the outline and a long hair hangs straight down.

The hue of each hair is solved from the reference; its strength is not. A thin stroke at the strength the deposit
rule gives for a dark coat is paste, and dries as wire over bare paper, so the strength runs from the first figure of
--strength for the palest fur to the second for the darkest. White fur against white paper gets no outline hair; a
long hair through it is drawn in a pale grey-buff.

Usage:
    coat_hairs.py outline <reference> <alpha.png> <output pass.json> --sheet W,H --paints a,b,c [--lie RULE ...]
        [--strength 0.4,1.7] [--sizes 1.0,1.2,1.5] [--spacing 4.5] [--length 10,24] [--lean 0.45]
        [--region x0,y0,x1,y1:spacing:least,greatest ...] [--white r,g,b] [--seed 3]
    coat_hairs.py long <reference> <alpha.png> <output pass.json> --sheet W,H --paints a,b,c [--lie RULE ...]
        --zone x0,y0,x1,y1:count:least,greatest [--zone ...] [--keep-off x0,y0,x1,y1 ...] [--strength 0.3,1.05]
        [--sizes 1.2,1.6,2.0] [--white r,g,b] [--seed 7]

A --region gives its own spacing and lengths to the outline inside it; lengths of 0,0 leave that stretch bare (an ear
that keeps a clean edge). A second outline pass at --strength 0.2,0.5 --sizes 1.5,2.0,2.6 with the spacing halved and
the lengths a third longer lays a soft fringe under the first.

The alpha is white where the coat is: the one isolate_subject.py writes. Run it with the Python that the watercolor
tool uses.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measured_layers import absorbance, paint_absorption, solve_mix
from soften_outline import outline_and_outward
from tonal_shapes import blurred

LUMA = np.array([0.2126, 0.7152, 0.0722])
# Fur lighter than this against the reference's paper is white fur: an outline hair there would be drawn on nothing.
WHITE_FUR = 0.93
# The value at which a hair takes the full strength asked for.
DARKEST = 0.15
PALE_SHADOW = np.array([210.0, 200.0, 188.0])  # the grey-buff a lock of white fur is drawn in
Box = tuple[float, float, float, float]


def boxed(text: str) -> Box:
    x0, y0, x1, y1 = (float(value) for value in text.split(","))
    return x0, y0, x1, y1


def holds(box: Box, x: float, y: float) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def lie_rules(entries: list[str]) -> list[tuple[str, np.ndarray, Box | None]]:
    """Each rule as its kind (away or toward), its two numbers, and the rectangle it holds in (none: everywhere)."""
    rules = []
    for entry in entries:
        what, _, where = entry.partition("@")
        kind, _, numbers = what.partition(":")
        if kind not in ("away", "toward"):
            raise SystemExit(
                f"--lie {entry}: a rule is away:x,y or toward:dx,dy, with @x0,y0,x1,y1 after it if it is local"
            )
        rules.append((kind, np.array([float(value) for value in numbers.split(",")]), boxed(where) if where else None))
    return rules


def lie(rules: list, x: float, y: float) -> np.ndarray | None:
    """The unit direction the fur lies in at a point, or None where no rule holds."""
    for kind, numbers, box in rules:
        if box is None or holds(box, x, y):
            direction = np.array([x, y]) - numbers if kind == "away" else numbers
            length = np.linalg.norm(direction)
            return direction / length if length else None
    return None


class Coat:
    """The reference's colour and the paints a hair's hue is solved from."""

    def __init__(self, arguments: argparse.Namespace) -> None:
        self.width, self.height = (int(value) for value in arguments.sheet.split(","))
        size = (self.width, self.height)
        self.white = np.array([float(value) for value in arguments.white.split(",")])
        self.colour = np.asarray(Image.open(arguments.reference).convert("RGB").resize(size, Image.Resampling.LANCZOS))
        self.colour = self.colour.astype(np.float64)
        alpha = Image.open(arguments.alpha).convert("L").resize(size, Image.Resampling.LANCZOS)
        self.kept = np.asarray(alpha).astype(np.float64) / 255
        self.absorption = paint_absorption(arguments.paints.split(","))
        self.weakest, self.strongest = (float(value) for value in arguments.strength.split(","))
        self.sizes = [float(value) for value in arguments.sizes.split(",")]
        self.rules = lie_rules(arguments.lie)
        self.rng = np.random.default_rng(arguments.seed)

    def on_sheet(self, point: np.ndarray, margin: float = 2.0) -> bool:
        return margin < point[0] < self.width - margin and margin < point[1] < self.height - margin

    def value(self, colour: np.ndarray) -> float:
        return float(colour @ LUMA / (self.white @ LUMA))

    def around(self, x: float, y: float, half: int = 2) -> np.ndarray:
        ix, iy = int(np.clip(x, half, self.width - 1 - half)), int(np.clip(y, half, self.height - 1 - half))
        return self.colour[iy - half : iy + half + 1, ix - half : ix + half + 1].reshape(-1, 3).mean(0)

    def load(self, colour: np.ndarray, size: float, spread: tuple[float, float]) -> dict:
        """A brush loaded with the colour's hue at a strength set by how dark the colour is."""
        hue = solve_mix(absorbance(colour, self.white), self.absorption)
        total = sum(hue.values())
        if total <= 0:
            raise SystemExit(f"no mix of --paints gives the colour {colour.round()}: name the paints the coat is in")
        darkness = min(1.0, (1.0 - self.value(colour)) / (1.0 - DARKEST))
        # No hair is stronger than the greatest strength asked for, whatever the variation between hairs.
        varied = (self.weakest + (self.strongest - self.weakest) * darkness) * self.rng.uniform(*spread)
        strength = min(self.strongest, varied)
        pigments = {name: round(float(amount * strength / total), 3) for name, amount in hue.items()}
        return {
            "action": "load",
            "brush": "round",
            "hair": "kolinsky_sable",
            "size": size,
            "pigments": pigments,
            "water": 0.9,
        }


def stroke(points: list[np.ndarray], pressures: tuple[float, ...], speed: float) -> dict:
    path = [[round(float(p[0]), 1), round(float(p[1]), 1), pressure] for p, pressure in zip(points, pressures)]
    return {"action": "stroke", "path": path, "speed": speed, "smooth": True}


def turned(direction: np.ndarray, angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([direction[0] * c - direction[1] * s, direction[0] * s + direction[1] * c])


def outline_hairs(coat: Coat, arguments: argparse.Namespace) -> list[dict]:
    outline, outward = outline_and_outward(coat.kept > 0.5, step=1.0, smoothing=8)
    least, greatest = (float(value) for value in arguments.length.split(","))
    regions = []
    for entry in arguments.region:
        box, spacing, lengths = entry.split(":")
        regions.append((boxed(box), float(spacing), *(float(value) for value in lengths.split(","))))
    rng = coat.rng
    actions: list[dict] = []

    def character(x: float, y: float) -> tuple[float, float, float]:
        for box, spacing, shortest, longest in regions:
            if holds(box, x, y):
                return spacing, shortest, longest
        return arguments.spacing, least, greatest

    def hair(index: int, shortest: float, longest: float, fan: float) -> None:
        x, y = outline[index]
        out = outward[index]
        start = np.array([x, y]) - out * rng.uniform(4, 12)
        colour = coat.around(*start)
        if coat.value(colour) > WHITE_FUR:
            return
        lying = lie(coat.rules, x, y)
        direction = out if lying is None else (1 - arguments.lean) * lying + arguments.lean * out
        if direction @ out < 0.3:  # a hair never leaves the outline inward
            direction = direction + (0.3 - direction @ out) * out
        direction = turned(direction / np.linalg.norm(direction), fan + rng.normal(0, 0.07))
        length = rng.uniform(shortest, longest)
        end = start + direction * (length + 8)
        middle = (start + end) / 2 + np.array([-direction[1], direction[0]]) * rng.normal(0, 0.1) * length
        if not coat.on_sheet(end):
            return
        actions.append(coat.load(colour, float(rng.choice(coat.sizes)), (0.6, 1.0)))
        actions.append(stroke([start, middle, end], (0.75, 0.55, 0.08), 240))

    position = rng.uniform(0, 10)
    while position < len(outline):
        index = int(position)
        spacing, shortest, longest = character(*outline[index])
        tuft = int(rng.choice([1, 2, 3, 3, 4, 5]))
        position += spacing * tuft * rng.uniform(0.5, 1.9)
        if longest <= 0 or not coat.on_sheet(outline[index], 6):
            continue
        reach = rng.uniform(0.75, 1.3)
        for member in range(tuft):
            beside = (index + int(rng.normal(0, 5.0))) % len(outline)
            hair(beside, shortest * reach, longest * reach, (member - (tuft - 1) / 2) * rng.uniform(0.08, 0.16))
    return actions


def grain_of(value: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The angle along which the picture changes least at each pixel, and how far that can be trusted (0 to 1)."""
    down, across = np.gradient(value)
    xx, yy, xy = (blurred(a, 5.0) for a in (across * across, down * down, across * down))
    angle = 0.5 * np.arctan2(2 * xy, xx - yy) + np.pi / 2
    return angle, np.sqrt((xx - yy) ** 2 + 4 * xy**2) / (xx + yy + 1e-9)


def long_hairs(coat: Coat, arguments: argparse.Namespace) -> list[dict]:
    angle, coherence = grain_of(coat.colour @ LUMA / 255)
    keep_off = [boxed(entry) for entry in arguments.keep_off]
    rng = coat.rng
    hanging = np.array([0.0, 1.0])

    def lying_at(x: float, y: float) -> np.ndarray:
        found = lie(coat.rules, x, y)
        return hanging if found is None else found

    def followed(x: float, y: float, length: float) -> list[np.ndarray]:
        points = [np.array([x, y])]
        heading = lying_at(x, y)
        for _ in range(int(length / 4)):
            px, py = points[-1]
            ix, iy = round(px), round(py)
            if not coat.on_sheet(points[-1], 4) or coat.kept[iy, ix] < 0.12:
                break
            along = np.array([np.cos(angle[iy, ix]), np.sin(angle[iy, ix])])
            designed = lying_at(px, py)
            if along @ designed < 0:
                along = -along
            trust = float(np.clip(coherence[iy, ix] * 1.4, 0.0, 0.7))
            wanted = trust * along + (1 - trust) * designed
            heading = 0.6 * heading + 0.4 * wanted / np.linalg.norm(wanted)
            heading /= np.linalg.norm(heading)
            points.append(points[-1] + 4 * heading)
        return points

    actions: list[dict] = []
    for entry in arguments.zone:
        box_text, count, lengths = entry.split(":")
        box = boxed(box_text)
        least, greatest = (float(value) for value in lengths.split(","))
        laid = attempts = 0
        while laid < int(count) and attempts < 40 * int(count) + 200:
            attempts += 1
            x, y = rng.uniform(box[0], box[2]), rng.uniform(box[1], box[3])
            if not coat.on_sheet(np.array([x, y]), 4) or coat.kept[int(y), int(x)] < 0.6:
                continue
            points = followed(x, y, rng.uniform(least, greatest))
            if len(points) < 6 or any(holds(off, p[0], p[1]) for off in keep_off for p in points):
                continue
            colours = np.array([coat.colour[round(p[1]), round(p[0])] for p in points])
            darkest = colours[np.argsort(colours.sum(1))[: max(2, len(colours) // 3)]].mean(0)
            shadow = PALE_SHADOW * coat.white / 255 if coat.value(darkest) > WHITE_FUR else darkest
            chosen = [points[round(i)] for i in np.linspace(0, len(points) - 1, 5)]
            actions.append(coat.load(shadow, float(rng.choice(coat.sizes)), (0.8, 1.2)))
            actions.append(stroke(chosen, (0.15, 0.7, 0.8, 0.5, 0.06), 230))
            laid += 1
    return actions


def main() -> None:
    parser = argparse.ArgumentParser()
    kinds = parser.add_subparsers(dest="kind", required=True)
    for kind, strength, sizes, seed in (
        ("outline", "0.4,1.7", "1.0,1.2,1.5", 3),
        ("long", "0.3,1.05", "1.2,1.6,2.0", 7),
    ):
        sub = kinds.add_parser(kind)
        sub.add_argument("reference")
        sub.add_argument("alpha", help="white where the coat is")
        sub.add_argument("output")
        sub.add_argument("--sheet", required=True, help="the sheet's size: W,H")
        sub.add_argument("--paints", required=True, help="the paints a hair's hue may use, comma separated")
        sub.add_argument("--lie", action="append", default=[], help="away:x,y or toward:dx,dy, @x0,y0,x1,y1 if local")
        sub.add_argument("--strength", default=strength, help="for the palest fur and the darkest: least,greatest")
        sub.add_argument("--sizes", default=sizes, help="the rounds the hairs are drawn with, comma separated")
        sub.add_argument("--white", default="255,255,255", help="the reference's own paper: r,g,b")
        sub.add_argument("--seed", type=int, default=seed)
        if kind == "outline":
            sub.add_argument("--spacing", type=float, default=4.5, help="pixels of outline to a hair, on average")
            sub.add_argument("--length", default="10,24", help="pixels a hair runs past the outline: least,greatest")
            sub.add_argument("--lean", type=float, default=0.45, help="the share of a hair's direction that is outward")
            sub.add_argument("--region", action="append", default=[], help="x0,y0,x1,y1:spacing:least,greatest")
        else:
            sub.add_argument("--zone", action="append", required=True, help="x0,y0,x1,y1:count:least,greatest")
            sub.add_argument("--keep-off", action="append", default=[], help="x0,y0,x1,y1 no hair may cross")
    arguments = parser.parse_args()

    coat = Coat(arguments)
    actions = outline_hairs(coat, arguments) if arguments.kind == "outline" else long_hairs(coat, arguments)
    Path(arguments.output).write_text(json.dumps(actions))
    strengths = sorted(sum(action["pigments"].values()) for action in actions if action["action"] == "load")
    if not strengths:
        raise SystemExit(f"{arguments.output}: no hairs. Is the alpha white where the coat is?")
    print(
        f"{arguments.output}: {len(strengths)} hairs, strength {strengths[0]:.2f} to {strengths[-1]:.2f}, "
        f"median {strengths[len(strengths) // 2]:.2f}"
    )


if __name__ == "__main__":
    main()

"""Scumble lights: lay light over the dried sheet wherever it is darker than the reference, in strokes along the form.

Paint can only darken, so the measuring scripts leave a light that was painted over as it is. Two things lay light
over dark: covering paint (harness 0.11.0 or later) and a dry stick (0.12.0 or later). This tool lays either the way a
painter drags it, along the form:

  1. The gap is the reference's value less the sheet's, where the reference is the lighter. The share of the light's
     own value that must cover a place is the gap over what a full coat would add there (`--top`, the value a full
     coat dries at, less the sheet's value). A light can only be laid as light as its own paint.
  2. Strokes follow the reference's own streaks. The direction at each place is the one along which the reference
     changes least (from its structure tensor, smoothed over `--flow` pixels), so a stroke runs along a crest or a
     line of foam and not across it. Each stroke starts where the gap is greatest and runs both ways until the gap
     closes or `--longest` pixels are drawn.
  3. `--medium body_colour` lays each stroke with a round of the radius given, loaded with the `--stick` paints at
     the strength its light needs: a smooth, half-covering ribbon with no grain in it. Use it for the body of a mass
     of foam or mist.
  4. `--medium pastel` or `coloured_pencil` lays each stroke with a dry stick at the pressure its light needs, from
     a table measured on cold press: pressure 0.12 covers about a sixth of the grain, 0.3 under half, 0.5 three
     quarters and 0.7 nearly all of it. A light touch leaves the dark showing between the tops of the grain: the
     broken light on top of the body. Strokes are gathered into `draw` actions of `--gather` strokes each, nearest
     first, with the stick lifted between them, so some hundreds of strokes cost a few dozen of the stroke budget.

`--ridges V` starts strokes only on the reference's own threads of light (lighter than their surroundings by V), and
`--persist N` lets a stroke run on through N steps where no light is wanted, so a thread is drawn whole. With
`--shortest` and `--press` (the least pressure: 0.6 for an unbroken coloured-pencil line) that gives the fine bright
lines along crests.

Lay the body first and finer marks after, each from a look taken after the last: body colour at `--radius 5`, pastel
at 2.5, then coloured pencil at 1 with `--ridges`. A second coat over the first reaches higher than one coat can.

Usage:
    scumble_lights.py <reference> <output pass.json> --sheet W,H --look <current look>
        [--medium pastel|coloured_pencil|body_colour] [--stick opaque_white:1.7,yellow_ochre:0.3] [--top 0.72]
        [--radius 3] [--threshold 0.04] [--gain 1.0] [--longest 90] [--flow 4] [--gather 24]
        [--ridges V] [--persist N] [--shortest L] [--press P]
        [--region x0,y0,x1,y1] [--within mask.png] [--origin x,y --crop W,H] [--preview preview.png]

The look must be one taken after a `dry`: a stick takes only on dry paper, and covering paint lies over paint only
once it has dried. Run it with the Python the harness uses.
"""

import argparse
import itertools
import json

import numpy as np
from PIL import Image, ImageDraw

VALUE = np.array([0.2126, 0.7152, 0.0722])
# Share of a full coat that pastel lays at each pressure, measured over a dark and over a middle value on cold press.
PRESSURES = np.array([0.0, 0.12, 0.16, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70, 1.00])
SHARES = np.array([0.0, 0.16, 0.25, 0.29, 0.43, 0.46, 0.63, 0.75, 0.95, 1.00])
LIGHTEST_TOUCH = 0.12  # a lighter touch than this marks next to nothing
# Strength at which one stroke of covering paint hides each share of what is under it (body-colour.md: a veil at 1.5,
# one coat at 4.5), and the least share worth a stroke.
BODY_SHARES = np.array([0.0, 0.2, 0.4, 0.64, 0.8])
BODY_STRENGTHS = np.array([0.0, 0.7, 1.5, 4.5, 7.5])
THINNEST_BODY = 0.15


def blurred(array: np.ndarray, radius: float) -> np.ndarray:
    """The array under a Gaussian of the radius given, its edges held."""
    if radius <= 0:
        return array
    reach = max(1, round(3 * radius))
    taps = np.exp(-0.5 * (np.arange(-reach, reach + 1) / radius) ** 2)
    taps /= taps.sum()
    for axis in (0, 1):
        padded = np.pad(array, [(reach, reach) if a == axis else (0, 0) for a in (0, 1)], mode="edge")
        length = array.shape[axis]
        array = sum(weight * np.take(padded, np.arange(i, i + length), axis=axis) for i, weight in enumerate(taps))
    return array


def value_of(path: str, size: tuple[int, int], box: tuple[int, int, int, int] | None) -> np.ndarray:
    image = Image.open(path).convert("RGB").resize(size, Image.LANCZOS)
    if box:
        image = image.crop(box)
    return (np.asarray(image, dtype=float) / 255.0) @ VALUE


def flow_direction(value: np.ndarray, smoothing: float) -> np.ndarray:
    """Angle, at every pixel, of the direction along which the picture changes least."""
    gy, gx = np.gradient(blurred(value, 1.0))
    jxx, jxy, jyy = blurred(gx * gx, smoothing), blurred(gx * gy, smoothing), blurred(gy * gy, smoothing)
    return 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2


def trace(seed, share: np.ndarray, angle: np.ndarray, taken: np.ndarray, least: float, longest: float, persist: int):
    """A stroke through the seed, as (x, y) points two pixels apart, run both ways along the flow."""
    height, width = share.shape
    halves = []
    for sign in (1.0, -1.0):
        x, y = float(seed[0]), float(seed[1])
        heading = angle[seed[1], seed[0]] + (0.0 if sign > 0 else np.pi)
        points, wanting = [], 0
        while len(points) * 2.0 < longest / 2:
            x, y = x + 2.0 * np.cos(heading), y + 2.0 * np.sin(heading)
            ix, iy = round(x), round(y)
            if not (0 <= ix < width and 0 <= iy < height) or taken[iy, ix]:
                break
            wanting = 0 if share[iy, ix] >= 0.7 * least else wanting + 1
            if wanting > persist:
                break
            points.append((x, y))
            ahead = angle[iy, ix]
            # the flow has no sign: keep going the way the stroke is already going
            heading = ahead if np.cos(ahead - heading) >= 0 else ahead + np.pi
        halves.append(points[: len(points) - wanting])  # a stroke does not end out where no light is wanted
    return halves[1][::-1] + [(float(seed[0]), float(seed[1]))] + halves[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True, help="full sheet size the reference is scaled to: W,H")
    parser.add_argument("--look", required=True, help="a look of the dried sheet")
    parser.add_argument("--medium", default="pastel", choices=("pastel", "coloured_pencil", "body_colour"))
    parser.add_argument(
        "--stick", default="opaque_white:1.7,yellow_ochre:0.3", help="the light's paints: name:amount,..."
    )
    parser.add_argument("--top", type=float, default=0.72, help="the value a full coat of the light dries at")
    parser.add_argument("--radius", type=float, default=3.0)
    parser.add_argument("--threshold", type=float, default=0.04, help="leave gaps in value smaller than this")
    parser.add_argument("--gain", type=float, default=1.0)
    parser.add_argument("--longest", type=float, default=90.0, help="longest stroke, in pixels")
    parser.add_argument("--flow", type=float, default=4.0, help="smoothing of the direction field, in pixels")
    parser.add_argument("--gather", type=int, default=24, help="strokes in one draw action")
    parser.add_argument("--ridges", type=float, default=None, help="start strokes only on threads this much lighter")
    parser.add_argument("--persist", type=int, default=0, help="steps a stroke may run where no light is wanted")
    parser.add_argument("--shortest", type=float, default=0.0, help="leave out strokes shorter than this, in pixels")
    parser.add_argument("--press", type=float, default=0.0, help="the least pressure of a dry stroke")
    parser.add_argument("--region", default=None, help="draw only inside x0,y0,x1,y1 (sheet coordinates)")
    parser.add_argument("--within", default=None, help="draw only where this image is white (the sheet's size)")
    parser.add_argument("--origin", default="0,0")
    parser.add_argument("--crop", default=None)
    parser.add_argument("--preview", default=None, help="draw this pass's strokes over the reference into this image")
    arguments = parser.parse_args()

    full = tuple(int(v) for v in arguments.sheet.split(","))
    ox, oy = (int(v) for v in arguments.origin.split(","))
    width, height = (int(v) for v in arguments.crop.split(",")) if arguments.crop else full
    box = (ox, oy, ox + width, oy + height) if arguments.crop else None
    reference = value_of(arguments.reference, full, box)
    sheet = value_of(arguments.look, (width, height), None)
    stick = {name: float(amount) for name, amount in (part.split(":") for part in arguments.stick.split(","))}
    body = arguments.medium == "body_colour"

    gap = blurred(reference, arguments.radius / 3) - blurred(sheet, arguments.radius / 3)
    share = np.clip(arguments.gain * gap / np.maximum(arguments.top - sheet, 0.05), 0.0, 1.0)
    share[gap < arguments.threshold] = 0.0
    if arguments.region:
        x0, y0, x1, y1 = (int(v) for v in arguments.region.split(","))
        outside = np.ones_like(share, dtype=bool)
        outside[y0:y1, x0:x1] = False
        share[outside] = 0.0
    if arguments.within:
        share[np.asarray(Image.open(arguments.within).convert("L").resize((width, height))) <= 127] = 0.0
    least = THINNEST_BODY if body else float(np.interp(LIGHTEST_TOUCH, PRESSURES, SHARES))
    starts = share >= least
    if arguments.ridges is not None:
        starts &= reference - blurred(reference, 3.0) > arguments.ridges
    angle = flow_direction(reference, arguments.flow)

    # Seeds on a grid a stroke's width apart, the greatest gap first. Each stroke holds x, y and the share wanted there.
    step = max(2, round(arguments.radius * 1.5))
    seeds = [(x, y) for y in range(step // 2, height, step) for x in range(step // 2, width, step) if starts[y, x]]
    seeds.sort(key=lambda p: -share[p[1], p[0]])
    taken = Image.new("L", (width, height), 0)
    reach = round(arguments.radius * 1.4)
    strokes = []
    for seed in seeds:
        marked = np.asarray(taken) > 0
        if marked[seed[1], seed[0]]:
            continue
        points = trace(seed, share, angle, marked, least, arguments.longest, arguments.persist)
        if 2.0 * (len(points) - 1) < arguments.shortest:
            continue
        kept = points[:: 2 if len(points) > 4 else 1]
        strokes.append(
            [
                (
                    round(x, 1),
                    round(y, 1),
                    float(share[min(max(round(y), 0), height - 1), min(max(round(x), 0), width - 1)]),
                )
                for x, y in kept
            ]
        )
        pen = ImageDraw.Draw(taken)
        if len(points) > 1:
            pen.line(points, fill=255, width=reach)
        pen.ellipse((seed[0] - reach / 2, seed[1] - reach / 2, seed[0] + reach / 2, seed[1] + reach / 2), fill=255)

    actions = []
    if body:
        # Each stroke is one brush load at the strength its greatest light needs, swelling where the light is.
        total = sum(stick.values())
        for stroke in strokes:
            strength = float(np.interp(max(wanted for _, _, wanted in stroke), BODY_SHARES, BODY_STRENGTHS))
            mix = {name: round(amount / total * strength, 2) for name, amount in stick.items()}
            path = [[x, y, round(0.35 + 0.55 * min(wanted / 0.64, 1.0), 2)] for x, y, wanted in stroke]
            if len(path) > 2:  # a stroke lands and leaves lightly
                path[0][2], path[-1][2] = 0.25, 0.25
            actions.append(
                {"action": "load", "brush": "round", "size": arguments.radius, "pigments": mix, "water": 0.75}
            )
            actions.append({"action": "stroke", "path": path, "speed": 200, "smooth": len(path) > 2})
        actions.append({"action": "dry"})
    else:
        # Strokes gathered into draw actions, each stroke the nearest to where the last one ended.
        remaining = []
        for stroke in strokes:
            path = [
                [x, y, round(max(float(np.interp(wanted, SHARES, PRESSURES)), arguments.press), 2)]
                for x, y, wanted in stroke
            ]
            if len(path) > 2:
                path[0][2], path[-1][2] = round(path[0][2] * 0.6, 2), round(path[-1][2] * 0.6, 2)
            remaining.append(path)
        while remaining:
            group = [remaining.pop(0)]
            while remaining and len(group) < arguments.gather:
                at = group[-1][-1]
                nearest = min(
                    range(len(remaining)),
                    key=lambda i: (remaining[i][0][0] - at[0]) ** 2 + (remaining[i][0][1] - at[1]) ** 2,
                )
                group.append(remaining.pop(nearest))
            path = []
            for stroke in group:
                path += [[stroke[0][0], stroke[0][1], 0.0], *stroke, [stroke[-1][0], stroke[-1][1], 0.0]]
            actions.append(
                {
                    "action": "draw",
                    "medium": arguments.medium,
                    "pigments": stick,
                    "path": path,
                    "radius": arguments.radius,
                    "smooth": False,
                }
            )

    with open(arguments.output, "w") as handle:
        json.dump(actions, handle)
    length = sum(np.hypot(b[0] - a[0], b[1] - a[1]) for stroke in strokes for a, b in itertools.pairwise(stroke))
    short = share >= least
    print(
        f"{arguments.output}: {len(strokes)} strokes ({length:.0f} pixels) in {len(actions)} actions; "
        f"{int(short.sum())} pixels short of light, mean gap {float(gap[short].mean()) if short.any() else 0:.3f}"
    )
    if arguments.preview:
        image = Image.open(arguments.reference).convert("RGB").resize(full, Image.LANCZOS)
        image = image.crop(box) if box else image
        pen = ImageDraw.Draw(image)
        for stroke in strokes:
            if len(stroke) > 1:
                pen.line([(x, y) for x, y, _ in stroke], fill=(255, 60, 40), width=1)
        image.save(arguments.preview)


if __name__ == "__main__":
    main()

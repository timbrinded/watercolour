"""Draw the strokes of one or more passes over the reference, at the width each brush will paint.

Pen lines (`pen`) are drawn in their ink at the width the pen draws them, and pencil in grey. Masking fluid (`mask`) is
drawn in yellow at the width it is laid, so a mask can be checked against the shape it must keep white before it goes
down. Fixative (`fix`) cannot be seen and is not drawn; nor is what a `blot`, `unmask` or `erase` takes away.

Usage: preview_pass.py <reference> <output> --sheet W,H [--origin x,y] [--region x0,y0,x1,y1]
                       [--zoom 2] [--alpha 120] pass.json [pass.json ...]

--origin is the full-sheet coordinate of the pass's own origin (for a study pass on a cropped sheet).
--alpha is how opaque each mark is drawn, from 0 to 255.
The overlay is a planning aid: it shows where paint will land and how wide, not how it will flow.
"""

import argparse
import json
import math

from PIL import Image, ImageDraw

# Painted width as a multiple of size, measured on the harness: width = size * (base + slope * pressure). It is the
# span of the mark, gaps between the hairs included, with the head's usual hair and a flat head laid broad side on.
WIDTH = {
    "spotter": (0.9, 1.2),
    "round": (0.54, 1.63),
    "designer": (0.3, 1.8),
    "rigger": (0.9, 1.2),
    "extended_point": (0.9, 1.2),
    "mop": (1.43, 0.75),
    "stippler": (1.27, 0.49),
    "flat": (1.85, 0.31),
    "bright": (1.87, 0.25),
    "flat_wash": (1.88, 0.31),
    "hake": (1.98, 0.21),
    "comber": (1.33, 0.7),
    "fan": (1.4, 0.65),
    "angular": (1.77, 0.37),
    "dagger": (0.5, 1.6),
    "sword": (0.2, 1.9),
    "filbert": (1.43, 0.75),
    "cats_tongue": (0.9, 1.2),
    "oval_wash": (1.5, 0.67),
}
MASK_COLOUR = (255, 214, 0)
MASK_LIGHTEST_SHARE = 0.15  # the harness lays a mask line at no pressure this share of its full width
PEN_LIGHTEST_SHARE = 0.15  # and draws a pen line at no pressure this share of its full width, but never under a pixel
PENCIL_COLOUR = (90, 90, 90)
PENCIL_RADIUS = 0.9  # the harness's pencil line at full pressure, unless the action gives a radius
STICK_LIGHTEST_SHARE = 0.5  # and a pencil or dry-stick line at no pressure this share of its full width
CLEAR_WATER = (0, 220, 255)
TINT = {
    "french_ultramarine": (60, 60, 200),
    "cobalt_blue": (40, 110, 200),
    "burnt_sienna": (190, 90, 30),
    "cadmium_red": (220, 50, 20),
    "yellow_ochre": (210, 170, 40),
    "burnt_umber": (80, 45, 25),
    "opaque_white": (255, 255, 255),
    "ivory_black": (20, 20, 20),
}


def painted_width(brush: str, size: float, pressure: float) -> float:
    """The width a head of this size paints at this pressure. A head with no measured width is refused: a guessed
    width spaces rows wrongly, leaving seams between them or overlaps."""
    if brush not in WIDTH:
        raise SystemExit(f"no painted width is known for the {brush!r} head: measure it and add it to WIDTH")
    base, slope = WIDTH[brush]
    return size * (base + slope * pressure)


def tint(name: str) -> tuple[int, int, int]:
    """A colour to draw a paint in: a fixed one where given above, otherwise the paint as a middling wash."""
    if name not in TINT:
        try:
            from watercolor.pigments import PIGMENTS

            red, green, blue = (round(250 * math.exp(-1.3 * channel)) for channel in PIGMENTS[name].absorption)
            TINT[name] = (red, green, blue)
        except (ImportError, KeyError):
            TINT[name] = (120, 120, 120)
    return TINT[name]


def mixed_tint(pigments: dict[str, float]) -> tuple[int, int, int]:
    """The colour to draw a mix in: its paints' tints weighted by amount, or cyan for clear water."""
    total = sum(pigments.values())
    if not total:
        return CLEAR_WATER
    red, green, blue = (
        round(sum(tint(name)[k] * amount for name, amount in pigments.items()) / total) for k in range(3)
    )
    return red, green, blue


def half_width(action: dict, brush: str, size: float, pressure: float) -> float:
    """Half the width of the mark an action leaves at this pressure: a stroke's is the brush in hand's."""
    kind = action["action"]
    if kind == "stroke":
        return painted_width(brush, size, pressure) / 2
    if kind == "pen":
        return max(0.5, action["width"] * (PEN_LIGHTEST_SHARE + (1 - PEN_LIGHTEST_SHARE) * pressure) / 2)
    if kind == "mask":
        return action["radius"] * (MASK_LIGHTEST_SHARE + (1 - MASK_LIGHTEST_SHARE) * pressure)
    return action.get("radius", PENCIL_RADIUS) * (STICK_LIGHTEST_SHARE + (1 - STICK_LIGHTEST_SHARE) * pressure)


def catmull_rom(points, steps=8):
    if len(points) < 3:
        return points
    padded = [points[0]] + points + [points[-1]]
    curve = []
    for index in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[index - 1 : index + 3]
        for step in range(steps):
            t = step / steps
            curve.append(
                tuple(
                    0.5
                    * (
                        (2 * p1[k])
                        + (-p0[k] + p2[k]) * t
                        + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t
                        + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t * t * t
                    )
                    for k in range(3)
                )
            )
    curve.append(points[-1])
    return curve


def path_points(action: dict, default_pressure: float, smooth: bool) -> list[tuple[float, float, float]]:
    points = []
    for point in action["path"]:
        if isinstance(point, dict):
            points.append((point["x"], point["y"], point.get("pressure", default_pressure)))
        else:
            points.append((point[0], point[1], point[2] if len(point) > 2 else default_pressure))
    if len(points) > 1 and action.get("smooth", smooth):
        points = catmull_rom(points)
    return points


def trail(view, centres, fill):
    """Draw discs of the given radius at each centre (view pixels) and between neighbours, on a layer over `view`."""
    layer = Image.new("RGBA", view.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    previous = None
    for px, py, radius in centres:
        draw.ellipse([px - radius, py - radius, px + radius, py + radius], fill=fill)
        if previous:
            qx, qy, previous_radius = previous
            steps = max(2, int(((px - qx) ** 2 + (py - qy) ** 2) ** 0.5 / 2))
            for step in range(1, steps):
                t = step / steps
                r = previous_radius + (radius - previous_radius) * t
                cx, cy = qx + (px - qx) * t, qy + (py - qy) * t
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
        previous = (px, py, radius)
    return Image.alpha_composite(view, layer)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("passes", nargs="+")
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--origin", default="0,0")
    parser.add_argument("--region", default=None)
    parser.add_argument("--zoom", type=float, default=2.0)
    parser.add_argument("--alpha", type=int, default=120)
    arguments = parser.parse_args()

    sheet_width, sheet_height = (int(value) for value in arguments.sheet.split(","))
    origin_x, origin_y = (int(value) for value in arguments.origin.split(","))
    x0, y0, x1, y1 = (
        (int(value) for value in arguments.region.split(",")) if arguments.region else (0, 0, sheet_width, sheet_height)
    )
    zoom = arguments.zoom

    reference = (
        Image.open(arguments.reference).convert("RGB").resize((sheet_width, sheet_height), Image.Resampling.LANCZOS)
    )
    view = (
        reference.crop((x0, y0, x1, y1))
        .resize((round((x1 - x0) * zoom), round((y1 - y0) * zoom)), Image.Resampling.LANCZOS)
        .convert("RGBA")
    )

    count = 0
    for path in arguments.passes:
        brush, size, colour = "round", 8, (0, 0, 0)
        with open(path) as handle:
            actions = json.load(handle)
        for action in actions:
            kind = action["action"]
            if kind == "load":
                brush, size = action["brush"], action["size"]
                colour = mixed_tint(action.get("pigments") or {})
                continue
            if kind not in ("stroke", "pen", "mask", "pencil", "draw") or action.get("sheet") == "scrap":
                continue
            count += 1
            if kind == "stroke":
                fill = colour
            elif kind == "pen":
                fill = mixed_tint(action["ink"])
            elif kind == "draw":
                fill = mixed_tint(action["pigments"])
            else:
                fill = MASK_COLOUR if kind == "mask" else PENCIL_COLOUR
            # a path point with no pressure is laid at 0.7 by a brush or a dry stick and at full pressure by the others
            default_pressure = 0.7 if kind in ("stroke", "draw") else 1.0
            # A pencil or dry stick lifted to pressure 0 marks nothing, so one action can hold several separate lines.
            lifts = kind in ("pencil", "draw")
            runs: list[list[tuple[float, float, float]]] = [[]]
            for x, y, pressure in path_points(action, default_pressure, smooth=kind != "draw"):
                if lifts and pressure <= 0:
                    runs.append([])
                    continue
                runs[-1].append(
                    (
                        (x + origin_x - x0) * zoom,
                        (y + origin_y - y0) * zoom,
                        half_width(action, brush, size, pressure) * zoom,
                    )
                )
            for centres in runs:
                view = trail(view, centres, fill + (arguments.alpha,))

    view.convert("RGB").save(arguments.output)
    print(f"{arguments.output}: {count} marks drawn over region {x0},{y0},{x1},{y1}")


if __name__ == "__main__":
    main()

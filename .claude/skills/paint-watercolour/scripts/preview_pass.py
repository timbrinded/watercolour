"""Draw the strokes of one or more passes over the reference, at the width each brush will paint.

Usage: preview_pass.py <reference> <output> --sheet W,H [--origin x,y] [--region x0,y0,x1,y1]
                       [--zoom 2] [--outline] pass.json [pass.json ...]

--origin is the full-sheet coordinate of the pass's own origin (for a study pass on a cropped sheet).
The overlay is a planning aid: it shows where paint will land and how wide, not how it will flow.
"""

import argparse
import json
import math

from PIL import Image, ImageDraw

# Painted width as a multiple of size, measured on the harness: width = size * (base + slope * pressure).
WIDTH = {
    "round": (0.54, 1.63),
    "designer": (0.3, 1.8),
    "spotter": (0.9, 1.2),
    "rigger": (0.9, 1.2),
    "extended_point": (0.9, 1.2),
    "cats_tongue": (0.9, 1.2),
    "dagger": (0.5, 1.6),
    "sword": (0.2, 1.9),
    "mop": (1.43, 0.75),
    "oval_wash": (1.5, 0.67),
    "filbert": (1.43, 0.75),
}
FLAT = (2.1, 0.0)
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
            if action["action"] == "load":
                brush, size = action["brush"], action["size"]
                pigments = action.get("pigments") or {}
                total = sum(pigments.values())
                if total:
                    colour = tuple(
                        round(sum(tint(name)[k] * amount for name, amount in pigments.items()) / total)
                        for k in range(3)
                    )
                else:
                    colour = (0, 220, 255)  # clear water
            elif action["action"] == "stroke" and action.get("sheet") != "scrap":
                count += 1
                points = []
                for point in action["path"]:
                    if isinstance(point, dict):
                        points.append((point["x"], point["y"], point.get("pressure", 0.7)))
                    else:
                        points.append((point[0], point[1], point[2] if len(point) > 2 else 0.7))
                if len(points) > 1 and action.get("smooth", True):
                    points = catmull_rom(points)
                base, slope = WIDTH.get(brush, FLAT)
                layer = Image.new("RGBA", view.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(layer)
                fill = colour + (arguments.alpha,)
                previous = None
                for x, y, pressure in points:
                    radius = size * (base + slope * pressure) / 2 * zoom
                    px, py = (x + origin_x - x0) * zoom, (y + origin_y - y0) * zoom
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
                view = Image.alpha_composite(view, layer)

    view.convert("RGB").save(arguments.output)
    print(f"{arguments.output}: {count} strokes drawn over region {x0},{y0},{x1},{y1}")


if __name__ == "__main__":
    main()

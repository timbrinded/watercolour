"""Scale the reference to the sheet size and draw a labelled coordinate grid over it.

Usage:
    reference_grid.py <reference> <output> --width W --height H
                      [--region x0,y0,x1,y1] [--step 40] [--zoom 2] [--no-grid]

Coordinates on the output are sheet pixels, so they can be used directly in stroke paths.
"""

import argparse

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--region", default=None)
    parser.add_argument("--step", type=int, default=40)
    parser.add_argument("--zoom", type=float, default=1.0)
    parser.add_argument("--no-grid", action="store_true")
    arguments = parser.parse_args()

    sheet = Image.open(arguments.reference).convert("RGB")
    sheet = sheet.resize((arguments.width, arguments.height), Image.Resampling.LANCZOS)

    if arguments.region:
        x0, y0, x1, y1 = (int(value) for value in arguments.region.split(","))
    else:
        x0, y0, x1, y1 = 0, 0, arguments.width, arguments.height

    zoom = arguments.zoom
    view = sheet.crop((x0, y0, x1, y1))
    view = view.resize((round((x1 - x0) * zoom), round((y1 - y0) * zoom)), Image.Resampling.LANCZOS)

    if not arguments.no_grid:
        draw = ImageDraw.Draw(view, "RGBA")
        font = ImageFont.load_default()
        step = arguments.step
        first_x = (x0 // step + (1 if x0 % step else 0)) * step
        first_y = (y0 // step + (1 if y0 % step else 0)) * step
        for x in range(first_x, x1, step):
            position = (x - x0) * zoom
            draw.line([(position, 0), (position, view.height)], fill=(0, 0, 0, 90), width=1)
            draw.rectangle([position + 1, 0, position + 26, 11], fill=(255, 255, 255, 200))
            draw.text((position + 2, 0), str(x), fill=(200, 0, 0, 255), font=font)
        for y in range(first_y, y1, step):
            position = (y - y0) * zoom
            draw.line([(0, position), (view.width, position)], fill=(0, 0, 0, 90), width=1)
            draw.rectangle([0, position + 1, 24, position + 12], fill=(255, 255, 255, 200))
            draw.text((1, position + 1), str(y), fill=(0, 0, 200, 255), font=font)

    view.save(arguments.output)
    print(f"{arguments.output}: region {x0},{y0},{x1},{y1} at zoom {zoom}, size {view.size}")


if __name__ == "__main__":
    main()

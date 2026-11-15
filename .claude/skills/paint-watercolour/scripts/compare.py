"""Place a look of the painting beside the same region of the reference, both at one scale.

Usage: compare.py <look image> <reference> <output> --sheet W,H [--region x0,y0,x1,y1] [--origin x,y]
                  [--zoom 2] [--grid 0]

--sheet is the full sheet size the reference is scaled to. --region is in full-sheet coordinates.
--origin is the full-sheet coordinate of the look image's top-left corner (for a study of a cropped region).
"""

import argparse

from PIL import Image, ImageDraw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("look")
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--region", default=None)
    parser.add_argument("--origin", default="0,0")
    parser.add_argument("--look-width", type=int, default=None, help="width of the painted sheet in its own pixels")
    parser.add_argument("--zoom", type=float, default=2.0)
    parser.add_argument("--grid", type=int, default=0)
    arguments = parser.parse_args()

    sheet_width, sheet_height = (int(value) for value in arguments.sheet.split(","))
    origin_x, origin_y = (int(value) for value in arguments.origin.split(","))
    reference = (
        Image.open(arguments.reference).convert("RGB").resize((sheet_width, sheet_height), Image.Resampling.LANCZOS)
    )
    look = Image.open(arguments.look).convert("RGB")
    look_width = arguments.look_width or sheet_width
    scale = look.width / look_width
    look = look.resize((round(look.width / scale), round(look.height / scale)), Image.Resampling.LANCZOS)

    if arguments.region:
        x0, y0, x1, y1 = (int(value) for value in arguments.region.split(","))
    else:
        x0, y0, x1, y1 = origin_x, origin_y, origin_x + look.width, origin_y + look.height

    zoom = arguments.zoom
    size = (round((x1 - x0) * zoom), round((y1 - y0) * zoom))
    painted = look.crop((x0 - origin_x, y0 - origin_y, x1 - origin_x, y1 - origin_y)).resize(
        size, Image.Resampling.LANCZOS
    )
    target = reference.crop((x0, y0, x1, y1)).resize(size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (size[0] * 2 + 8, size[1]), "white")
    canvas.paste(painted, (0, 0))
    canvas.paste(target, (size[0] + 8, 0))
    if arguments.grid:
        draw = ImageDraw.Draw(canvas, "RGBA")
        for panel in (0, size[0] + 8):
            first_x = (x0 // arguments.grid + 1) * arguments.grid
            for x in range(first_x, x1, arguments.grid):
                position = panel + (x - x0) * zoom
                draw.line([(position, 0), (position, size[1])], fill=(0, 0, 0, 60))
                draw.text((position + 2, 1), str(x), fill=(200, 0, 0, 255))
            first_y = (y0 // arguments.grid + 1) * arguments.grid
            for y in range(first_y, y1, arguments.grid):
                position = (y - y0) * zoom
                draw.line([(panel, position), (panel + size[0], position)], fill=(0, 0, 0, 60))
                draw.text((panel + 2, position + 1), str(y), fill=(0, 0, 200, 255))
    canvas.save(arguments.output)
    print(f"{arguments.output}: painting left, reference right, region {x0},{y0},{x1},{y1}")


if __name__ == "__main__":
    main()

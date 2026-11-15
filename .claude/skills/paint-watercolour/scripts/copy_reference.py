"""Paint the measured stages of a copy: row washes for the masses, then shape strokes for everything smaller.

Usage:
    copy_reference.py <painting directory> <reference> --sheet W,H --paints cobalt_blue,burnt_sienna,...
        [--exclude x0,y0,x1,y1 ...] [--out-of-washes burnt_umber,...] [--bloom x,y ...] [--white r,g,b]
        [--first 1] [--last 13] [--command "uv run watercolor"]

Each stage writes a pass from the reference and the latest look of the painting (measured_layers.py for stages
1 to 4, shape_strokes.py for stages 5 to 13), paints it, and ends dry. The passes are kept beside the painting
directory as <painting>.stage<N>.json. Drawing by hand comes after the last stage and is not part of this script.

--exclude        a rectangle no stage may touch (repeatable): a white too small to survive the layers, a
                 signature or watermark in the reference.
--out-of-washes  paints kept out of the two broadest stages: a granulating paint gathers into specks in a
                 deep wash.
--bloom          a point where clear water is touched into the first wash as its film thins (repeatable).
--white          the colour of the reference's own paper, where it is a scan and not pure white.

The painting must have been started with a stroke budget large enough for every stage (`watercolor new
--stroke-budget`): a sheet 960 pixels wide took about ten thousand strokes.

The sizes, thresholds and blurs below were settled on a sheet 960 pixels wide. Run this with the Python that the
watercolor tool uses.
"""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROWS, SHAPES = "measured_layers.py", "shape_strokes.py"
ROW_HAND = "--wobble 0.12 --tolerance 0.5"
FINEST = "--threshold 0.15 --widest 1.8 --narrowest 1.0 --blur 2 --spur 1.5 --peels 1 --cap 2.0 --hair kolinsky_sable --speed 150"
# (script, arguments, whether --out-of-washes applies)
STAGES = [
    (
        ROWS,
        f"{ROW_HAND} --brush mop --size 18 --gain 0.85 --least 0.05 --longest 220 --speed 280 --smoothing 0.5 --no-dry",
        True,
    ),
    (
        ROWS,
        f"{ROW_HAND} --brush round --hair squirrel --size 14 --gain 1.0 --least 0.2 --angle 35 --longest 220 --smoothing 0.5",
        True,
    ),
    (
        ROWS,
        f"{ROW_HAND} --brush round --hair squirrel --size 8 --gain 0.9 --least 0.08 --angle 20 --longest 200 --smoothing 0.5",
        False,
    ),
    (
        ROWS,
        f"{ROW_HAND} --brush round --hair squirrel --size 8 --gain 1.0 --least 0.12 --angle -25 --longest 200 --smoothing 1.0",
        False,
    ),
    (
        SHAPES,
        "--threshold 0.06 --cap 1.5 --widest 6 --narrowest 2.5 --blur 7 --spur 2.5 --peels 3 --hair squirrel --water 0.85",
        False,
    ),
    (SHAPES, "--threshold 0.12 --widest 5 --narrowest 2 --blur 5 --spur 2.5 --peels 3", False),
    (SHAPES, "--threshold 0.25 --widest 4 --narrowest 1.5 --blur 4 --spur 2 --peels 3", False),
    (SHAPES, "--threshold 0.2 --widest 2.5 --narrowest 1.2 --blur 3 --spur 1.5 --peels 2 --hair kolinsky_sable", False),
    (SHAPES, "--threshold 0.45 --widest 2.5 --narrowest 1.2 --blur 2 --peels 2 --hair kolinsky_sable", False),
    (SHAPES, "--threshold 0.3 --widest 2 --narrowest 1.2 --blur 2 --cap 2.0 --peels 2 --hair kolinsky_sable", False),
    (SHAPES, FINEST, False),
    (
        SHAPES,
        "--threshold 0.06 --cap 1.5 --widest 5 --narrowest 2 --blur 6 --spur 2.5 --peels 3 --hair squirrel --water 0.85",
        False,
    ),
    (SHAPES, FINEST, False),
]


def latest_look(painting: Path) -> Path | None:
    looks = sorted((painting / "looks").glob("*_painting_color.png"))
    return looks[-1] if looks else None


def paint(command: list[str], painting: Path, actions: Path) -> None:
    result = subprocess.run(
        [*command, "paint", str(painting), str(actions)], check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise SystemExit(f"{actions} was not painted:\n{result.stdout}{result.stderr}")


def blooms(points: list[str]) -> list[dict]:
    """Clear water touched into the first wash at each point as its film thins to 0.18, then the dry that ends
    the first stage."""
    actions: list[dict] = []
    if points:
        actions.append({"action": "load", "brush": "round", "size": 7, "pigments": {}, "water": 1.0})
    for index, point in enumerate(points):
        x, y = (float(value) for value in point.split(","))
        actions.append({"action": "wait", "seconds": 120 if index == 0 else 60, "at": [x, y], "film": 0.18})
        actions.append({"action": "stroke", "path": [[x, y, 0.8]], "dwell": 0.6})
    actions.append({"action": "dry"})
    return actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", type=Path)
    parser.add_argument("reference")
    parser.add_argument("--sheet", required=True, help="the sheet's size: W,H")
    parser.add_argument("--paints", required=True, help="the paints a mix may use, comma separated")
    parser.add_argument("--exclude", action="append", default=[], help="leave x0,y0,x1,y1 untouched (repeatable)")
    parser.add_argument("--out-of-washes", default="", help="paints kept out of stages 1 and 2, comma separated")
    parser.add_argument("--bloom", action="append", default=[], help="x,y of a bloom in the first wash (repeatable)")
    parser.add_argument("--white", default=None, help="the reference's own paper white: r,g,b")
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=len(STAGES))
    parser.add_argument(
        "--command", default="watercolor", help="how the harness is run, for example 'uv run watercolor'"
    )
    arguments = parser.parse_args()

    scripts = Path(__file__).resolve().parent
    command = shlex.split(arguments.command)
    painting = arguments.painting
    stem = str(painting).rstrip("/")
    excluded = [word for box in arguments.exclude for word in ("--exclude", box)]

    for number in range(arguments.first, arguments.last + 1):
        script, settings, broad = STAGES[number - 1]
        actions = Path(f"{stem}.stage{number}.json")
        look = latest_look(painting)
        if script == SHAPES and look is None:
            raise SystemExit(f"stage {number} needs a look of the painting, and it has none")
        words = [
            sys.executable,
            str(scripts / script),
            arguments.reference,
            str(actions),
            "--sheet",
            arguments.sheet,
            "--paints",
            arguments.paints,
            *excluded,
            *shlex.split(settings),
        ]
        if look is not None:
            words += ["--look", str(look)]
        if arguments.white:
            words += ["--white", arguments.white]
        if broad and arguments.out_of_washes:
            words += ["--without", arguments.out_of_washes]
        subprocess.run(words, check=True)
        paint(command, painting, actions)
        if number == 1:
            water = Path(f"{stem}.blooms.json")
            water.write_text(json.dumps(blooms(arguments.bloom)))
            paint(command, painting, water)
        print(f"stage {number} done", flush=True)


if __name__ == "__main__":
    main()

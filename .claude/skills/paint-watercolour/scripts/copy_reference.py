"""Paint the measured stages of a copy: row washes for the masses, then shape strokes for everything smaller.

Usage:
    copy_reference.py <painting directory> <reference> --sheet W,H --paints cobalt_blue,burnt_sienna,...
        [--exclude x0,y0,x1,y1 ...] [--out-of-washes burnt_umber,...] [--bloom x,y ...] [--white r,g,b]
        [--even-passages] [--keep-lights 0.08] [--first 1] [--last 13] [--command "uv run watercolor"]

Each stage takes a plain look of the painting, writes a pass from the reference and that look (measured_layers.py
for stages 1 to 4, shape_strokes.py for stages 5 to 13), paints it, and ends dry. The passes are kept beside the
painting directory as <painting>.stage<N>.json. Drawing by hand comes after the last stage and is not part of this
script.

--exclude        a rectangle no stage may touch (repeatable): a white too small to survive the layers, a
                 signature or watermark in the reference, a passage already laid by hand. A row brush stays
                 half its width outside it, so each smaller brush comes closer.
--out-of-washes  paints kept out of the broadest stages (1 and 2; 1 to 3 with --even-passages): a granulating
                 paint gathers into specks in a deep wash.
--bloom          a point where clear water is touched into the first wash as its film thins (repeatable).
--white          the colour of the reference's own paper, where it is a scan and not pure white.
--even-passages  for a reference with large even passages (a sky, water, a plain wall). The first wash is laid at
                 full strength with smaller rounds cutting in round the lights while it is wet, and the mop is
                 laid a second time on the dried wash, so those passages dry as washes and not as patches.
                 Fourteen stages: the row stages are then 1 to 5 and the shape strokes 6 to 14.
--keep-lights    the reference absorbance under which a place counts as a light that the row stages keep off,
                 however narrow it is. 0.08 (near-white) with --even-passages, where the heavier smoothing
                 would otherwise tone every narrow light over; off without it. 0 turns it off.

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


# For a reference with large even passages (--even-passages): the first wash at full strength with the gap
# smoothed over a stroke width and smaller rounds cutting in round the lights while it is wet, then the mop a
# second time, across the first, on the dried wash.
EVEN_MOP = f"{ROW_HAND} --brush mop --size 18 --least 0.05 --longest 220 --speed 280 --smoothing 1.0"
EVEN_FIRST_WASH = (ROWS, f"{EVEN_MOP} --gain 1.1 --cut-in 8,3.5 --no-dry", True)
EVEN_SECOND_WASH = (ROWS, f"{EVEN_MOP} --gain 0.9 --angle 90", True)
LIGHT = 0.08  # the reference absorbance under which a place counts as a light, with --even-passages


def plain_look(command: list[str], painting: Path) -> Path:
    """A fresh look of the whole sheet with no grid on it. The newest look on file may be one the painter took
    with --grid or --region, and a stage built from that would read the grid as paint or the region as the sheet.

    The command names the file it saved. The last name in the directory is not always that file: a look is numbered
    by how many files the directory holds, so once any have been removed a new look sorts before an older one."""
    result = subprocess.run([*command, "look", str(painting)], check=False, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f"no look could be taken of {painting}:\n{result.stdout}{result.stderr}")
    return Path(json.loads(result.stdout)["look"])


def interrupted_pass_file(stem: str, actions_given: int) -> Path | None:
    """The pass of this script that was cut short, told by its number of actions. The newest file does not tell
    it: the blooms are written after stage 1 and before stage 1 is painted."""
    last = len(STAGES) + 1  # --even-passages has one stage more
    passes = [Path(f"{stem}.stage{number}.json") for number in range(1, last + 1)]
    passes.append(Path(f"{stem}.blooms.json"))
    matching = [file for file in passes if file.exists() and len(json.loads(file.read_text())) == actions_given]
    return matching[0] if len(matching) == 1 else None


def refuse_unless_complete_and_dry(command: list[str], painting: Path, stem: str) -> None:
    """A stage is measured from the sheet as it stands and laid on top of it, so the last pass must be complete
    and the sheet dry. A pass that was cut short must first be finished from its own file, and a wet sheet dried."""
    result = subprocess.run([*command, "status", str(painting)], check=False, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f"the state of {painting} could not be read:\n{result.stdout}{result.stderr}")
    state = json.loads(result.stdout)
    stopped = state.get("interrupted_pass")
    if stopped:
        given = stopped["actions_given"]
        file = interrupted_pass_file(stem, given) or f"<the pass of {given} actions that was being painted>"
        raise SystemExit(
            f"a pass on {painting} was cut short. Give the same pass again to finish it: "
            f"`watercolor paint {painting} {file}`. If that was stage 1, paint {stem}.blooms.json after it, which "
            "dries the first wash. Then run this script with --first set to the next stage."
        )
    wetness = state["wetness"]["painting"]
    if wetness["film_deepest"] > 0 or wetness["paper_fullness"] > 0:
        raise SystemExit(
            f"{painting} is wet, and a wet sheet is not yet the colour it will dry to. Dry it before a stage is "
            f'built from it: paint {stem}.blooms.json if the first wash was laid last, or a pass of [{{"action": '
            '"dry"}] otherwise.'
        )


def paint(command: list[str], painting: Path, actions: Path) -> None:
    result = subprocess.run(
        [*command, "paint", str(painting), str(actions)], check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise SystemExit(f"{actions} was not painted:\n{result.stdout}{result.stderr}")


def blooms(points: list[tuple[float, float]]) -> list[dict]:
    """Clear water touched into the first wash at each point as its film thins to 0.18, then the dry that ends
    the first stage."""
    actions: list[dict] = []
    if points:
        actions.append({"action": "load", "brush": "round", "size": 7, "pigments": {}, "water": 1.0})
    for index, (x, y) in enumerate(points):
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
    parser.add_argument(
        "--out-of-washes",
        default="",
        help="paints kept out of stages 1 and 2 (1 to 3 with --even-passages), comma separated",
    )
    parser.add_argument("--bloom", action="append", default=[], help="x,y of a bloom in the first wash (repeatable)")
    parser.add_argument("--white", default=None, help="the reference's own paper white: r,g,b")
    parser.add_argument(
        "--even-passages",
        action="store_true",
        help="lay the first wash at full strength, cut in round the lights, and lay the mop a second time",
    )
    parser.add_argument(
        "--keep-lights",
        type=float,
        default=None,
        help=f"the reference absorbance under which the row stages keep off ({LIGHT} with --even-passages)",
    )
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=None, help="the last stage to run (all of them unless given)")
    parser.add_argument(
        "--command", default="watercolor", help="how the harness is run, for example 'uv run watercolor'"
    )
    arguments = parser.parse_args()

    scripts = Path(__file__).resolve().parent
    command = shlex.split(arguments.command)
    painting = arguments.painting
    stem = str(painting)
    excluded = [word for box in arguments.exclude for word in ("--exclude", box)]
    stages = [EVEN_FIRST_WASH, EVEN_SECOND_WASH, *STAGES[1:]] if arguments.even_passages else STAGES
    last = arguments.last or len(stages)
    if not 1 <= arguments.first <= last <= len(stages):
        # stage 0 would be read from the end of the list, and the finest strokes laid first, on bare paper
        parser.error(f"--first and --last number the stages from 1 to {len(stages)}, the first no later than the last")
    sheet_width, sheet_height = (int(value) for value in arguments.sheet.split(","))
    bloom_points = []
    for point in arguments.bloom:
        x, y = (float(value) for value in point.split(","))
        if not (0 <= x < sheet_width and 0 <= y < sheet_height):
            # the harness refuses the blooms only after the first wash is on the sheet, and the wash is left undried
            parser.error(f"--bloom {point} is off the sheet")
        bloom_points.append((x, y))
    refuse_unless_complete_and_dry(command, painting, stem)
    keep_lights = arguments.keep_lights if arguments.keep_lights is not None else LIGHT * arguments.even_passages

    water = Path(f"{stem}.blooms.json")

    for number in range(arguments.first, last + 1):
        script, settings, broad = stages[number - 1]
        actions = Path(f"{stem}.stage{number}.json")
        look = plain_look(command, painting)
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
            "--look",
            str(look),
        ]
        if arguments.white:
            words += ["--white", arguments.white]
        if script == ROWS and keep_lights:
            words += ["--keep-lights", str(keep_lights)]
        if broad and arguments.out_of_washes:
            words += ["--without", arguments.out_of_washes]
        subprocess.run(words, check=True)
        if number == 1:
            # written before the wash is painted, so that it is there to give by hand if the wash is cut short
            water.write_text(json.dumps(blooms(bloom_points)))
        paint(command, painting, actions)
        if number == 1:
            paint(command, painting, water)
        print(f"stage {number} done", flush=True)


if __name__ == "__main__":
    main()

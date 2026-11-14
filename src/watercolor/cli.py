"""Command-line harness.

    watercolor new    <directory> --prompt "..." [--size 512] [--height 360] [--stroke-budget 150] ...
    watercolor paint  <directory> <actions.json>
    watercolor look   <directory> [--view color|value|wetness] [--region x0,y0,x1,y1] [--grid] [--scrap]
                                  [--at x,y ...]
    watercolor status <directory>
    watercolor finish <directory>
    watercolor --version

There is deliberately no command that previews, rehearses or reverses an action.
One command at a time works on a painting; a second is refused until the first ends.
"""

import argparse
import fcntl
import json
import sys
from pathlib import Path
from typing import IO

from . import ENGINE_VERSION
from .pigments import PIGMENTS
from .session import Configuration, RuleViolation, Session


def _region(text: str) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = (int(part) for part in text.split(","))
    if x1 <= x0 or y1 <= y0:
        raise argparse.ArgumentTypeError("region must be x0,y0,x1,y1 with x1 > x0 and y1 > y0")
    return x0, y0, x1, y1


def _point(text: str) -> tuple[float, float]:
    x, y = (float(part) for part in text.split(","))
    return x, y


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="watercolor")
    parser.add_argument("--version", action="version", version=ENGINE_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    new = commands.add_parser("new", help="start a painting on a fresh sheet")
    new.add_argument("directory", type=Path)
    new.add_argument("--prompt", required=True)
    new.add_argument("--size", type=int, default=512, choices=range(128, 1025), metavar="128..1024")
    new.add_argument("--height", type=int, choices=range(128, 1025), metavar="128..1024", help="if not square")
    new.add_argument("--seed", type=int, default=0)
    new.add_argument("--palette", default=",".join(PIGMENTS), help="comma-separated pigment names")
    new.add_argument("--stroke-budget", type=int, default=150)
    new.add_argument("--no-scrap", action="store_true")
    new.add_argument("--no-pencil", action="store_true")

    paint = commands.add_parser("paint", help="carry out a pass of actions from a JSON file")
    paint.add_argument("directory", type=Path)
    paint.add_argument("actions", type=Path)

    look = commands.add_parser("look", help="save a picture of the sheet")
    look.add_argument("directory", type=Path)
    look.add_argument("--view", default="color")
    look.add_argument("--region", type=_region)
    look.add_argument("--grid", action="store_true")
    look.add_argument("--scrap", action="store_true")
    look.add_argument("--at", type=_point, action="append", default=[], metavar="x,y", help="read the wetness here")

    for name, text in (
        ("status", "report the state of the painting"),
        ("finish", "dry, export and close the painting"),
    ):
        commands.add_parser(name, help=text).add_argument("directory", type=Path)
    return parser


def _hold(directory: Path) -> IO[str]:
    """Keep a painting to this command until the process ends, however it ends.

    Two commands at work on one painting would each break the other's record of it.
    """
    lock = (directory / "lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuleViolation("another command is at work on this painting; wait for it to end") from None
    return lock


def _run(arguments: argparse.Namespace) -> dict:
    if arguments.command == "new":
        configuration = Configuration(
            prompt=arguments.prompt,
            size=arguments.size,
            seed=arguments.seed,
            palette=arguments.palette.split(","),
            stroke_budget=arguments.stroke_budget,
            scrap_allowed=not arguments.no_scrap,
            pencil_allowed=not arguments.no_pencil,
            height=arguments.height,
        )
        return Session.create(arguments.directory, configuration).report()

    held = _hold(arguments.directory)  # noqa: F841 - held for as long as this command runs
    session = Session(arguments.directory)
    if arguments.command == "paint":
        completed = session.paint(json.loads(arguments.actions.read_text()))
        resumed = {} if completed is None else {"resumed_after_action": completed}
        return resumed | session.report() | {"look": str(session.look())}
    if arguments.command == "look":
        sheet = "scrap" if arguments.scrap else "painting"
        seen: dict = {"look": str(session.look(sheet, arguments.view, arguments.region, arguments.grid))}
        if arguments.at:
            seen["wetness"] = session.wetness(arguments.at, sheet)
        return seen
    if arguments.command == "finish":
        picture, video = session.finish()
        return session.report() | {"picture": str(picture), "video": str(video)}
    return session.report()


def main() -> None:
    arguments = _parser().parse_args()
    try:
        print(json.dumps(_run(arguments), indent=2))
    except (RuleViolation, ValueError, FileExistsError) as problem:
        print(f"refused: {problem}", file=sys.stderr)
        sys.exit(1)

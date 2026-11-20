"""A painting kept on disk between commands, with an append-only record of every action.

There is no operation that removes or reverses an action. Each log entry carries
the hash of the entry before it, and each action records a digest of the state
saved after it, so a state file that does not follow from the log is refused.

The state is saved as each action ends and at intervals through a long wait. A
command that is killed part-way therefore loses only the action it was in the
middle of: the next command finds the painting as the last save left it, and the
same pass given again carries on from where it stopped.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import Tensor

from . import ENGINE_VERSION
from .brushes import Brush, validate_journey
from .pigments import PIGMENTS
from .recording import FrameRecorder, encode_video
from .rendering import VIEWS, inspection_image, render, to_image
from .simulation import SUPPORTS, Sheet, support_sheet
from .studio import DAB_DURATION, DEFAULT_STROKE_SPEED, Studio, validate_brush_request, validate_pen_request

SCRAP_SIZE = 256
TOUCHING_ACTIONS = ("stroke", "blot", "pen")  # these put paint on the sheet or take it off
SURFACE_TREATMENTS = ("mask", "unmask", "fix")  # these count against the stroke budget too, but lay no paint
SHEET_ACTIONS = ("stroke", "blot", "pencil", "erase", "tilt", "mask", "unmask", "pen", "fix")
SAVE_INTERVAL = 10.0  # seconds of computing between saves during a long wait
GROUND_FILE = "ground.png"  # the image printed on the sheet, as resampled to it
GROUND_PROPORTION_TOLERANCE = 0.02  # share by which a ground image's proportions may differ from the sheet's


class RuleViolation(Exception):
    """An action that the rules of the painting do not permit."""


@dataclass(frozen=True)
class Interruption:
    """A pass that stopped before its end."""

    digest: str  # of the actions that were given
    given: int
    completed: int
    waited: float  # seconds that had already passed in the action it stopped in


@dataclass(frozen=True)
class Configuration:
    prompt: str
    size: int
    seed: int
    palette: list[str]
    stroke_budget: int
    scrap_allowed: bool
    pencil_allowed: bool
    engine_version: str = ENGINE_VERSION
    height: int | None = None  # the sheet is square unless a height is given; size is then its width
    support: str = "cold_press"  # one of SUPPORTS; a painting begun before there was a choice is on cold press
    ground_digest: str | None = None  # sha256 of ground.png, when an image is printed on the sheet


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _printed_ground(path: Path, height: int, width: int) -> Image.Image:
    """Return the image to print on the sheet, flattened onto white and resampled to the sheet by area."""
    try:
        image = Image.open(path).convert("RGBA")
    except OSError as problem:
        raise ValueError(f"the ground image cannot be read: {problem}") from None
    if abs(image.width * height / (image.height * width) - 1.0) > GROUND_PROPORTION_TOLERANCE:
        raise ValueError(
            f"the ground image is {image.width}x{image.height} and the sheet {width}x{height};"
            " give --size and --height in its proportions"
        )
    flat = Image.new("RGB", image.size, "white")
    flat.paste(image, mask=image.getchannel("A"))
    return flat.resize((width, height), Image.Resampling.BOX)


def _centre(image: Image.Image, size: int) -> Image.Image:
    """Return the middle of a print at its own scale, on white where the print is smaller than the square."""
    square = Image.new("RGB", (size, size), "white")
    square.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
    return square


def _ink(image: Image.Image) -> Tensor:
    """Return a print as RGB in [0, 1] with shape (3, H, W)."""
    return torch.from_numpy(np.asarray(image, dtype=np.float32) / 255.0).permute(2, 0, 1)


class Session:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.configuration = Configuration(**json.loads((directory / "session.json").read_text()))
        self.entries = [json.loads(line) for line in (directory / "log.jsonl").read_text().splitlines()]
        self._verify_log()
        self._verify_configuration()

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        config = self.configuration
        pigments = [PIGMENTS[name] for name in config.palette]
        support = SUPPORTS[config.support]
        printed = Image.open(directory / GROUND_FILE).convert("RGB") if config.ground_digest else None

        def sheet(height: int, width: int, seed: int, print_layer: Image.Image | None) -> Sheet:
            ink = None if print_layer is None else _ink(print_layer)
            return support_sheet(support, height, width, seed, device, pigments, ink)

        sheets = {"painting": sheet(config.height or config.size, config.size, config.seed, printed)}
        if config.scrap_allowed:
            # The scrap is cut from the middle of the same printed sheet.
            scrap_print = None if printed is None else _centre(printed, SCRAP_SIZE)
            sheets["scrap"] = sheet(SCRAP_SIZE, SCRAP_SIZE, config.seed + 1, scrap_print)
        self._recorder = FrameRecorder(directory / "frames")
        self.studio = Studio(sheets, config.palette, self._recorder, seed=config.seed)
        self.studio.while_waiting = self._save_if_due
        self._saved_at = time.monotonic()
        self.strokes_used = 0
        self.paint_applied = False  # the underdrawing can change only until paint touches the painting
        self.sealed = False
        self._restore()

    # --------------------------------------------------------------- creation

    @classmethod
    def create(cls, directory: Path, configuration: Configuration, ground: Path | None = None) -> "Session":
        """Begin a painting; a ground is an image printed on the sheet before any paint."""
        if directory.exists():
            raise FileExistsError(f"{directory} already exists; a painting is never started over")
        for name in configuration.palette:
            if name not in PIGMENTS:
                raise ValueError(f"unknown pigment {name!r}; available: {', '.join(PIGMENTS)}")
        if configuration.support not in SUPPORTS:
            raise ValueError(f"unknown support {configuration.support!r}; available: {', '.join(SUPPORTS)}")
        size = configuration.size
        printed = None if ground is None else _printed_ground(ground, configuration.height or size, size)
        directory.mkdir(parents=True)
        digest = None
        if printed is not None:
            printed.save(directory / GROUND_FILE)
            digest = _digest((directory / GROUND_FILE).read_bytes())
        configuration = replace(configuration, ground_digest=digest)
        (directory / "session.json").write_text(json.dumps(asdict(configuration), indent=2))
        (directory / "log.jsonl").write_text("")
        session = cls(directory)
        session.studio._record()
        session._checkpoint({"action": "begin", "configuration": asdict(configuration)})
        return session

    # ------------------------------------------------------------ persistence

    @property
    def _state_path(self) -> Path:
        return self.directory / "state.pt"

    @property
    def _pending_path(self) -> Path:
        return self.directory / "state.pending.pt"

    def _append(self, body: dict) -> None:
        previous = self.entries[-1]["hash"] if self.entries else ""
        entry = {"index": len(self.entries), "clock": round(self.studio.clock, 3), "previous": previous, **body}
        entry["hash"] = _digest(_canonical(entry))
        self.entries.append(entry)
        with (self.directory / "log.jsonl").open("a") as log:
            log.write(json.dumps(entry) + "\n")

    def _checkpoint(self, body: dict | None = None) -> None:
        """Save the painting as it stands, and record what led to it with the digest of what was saved."""
        studio = self.studio
        state = {
            "sheets": {name: sheet.state() | {"tilt": list(sheet.tilt)} for name, sheet in studio.sheets.items()},
            "brush": asdict(studio.brush) if studio.brush else None,
            "clock": studio.clock,
            "loads": studio.loads,
            "strokes_used": self.strokes_used,
            "paint_applied": self.paint_applied,
            "sealed": self.sealed,
            "frames": self._recorder.count,
        }
        # The new state takes the place of the old only once the log records it, so a command
        # killed at any point here leaves a log and a state that the next command can reconcile.
        torch.save(state, self._pending_path)
        self._append((body or {"action": "checkpoint"}) | {"state": _digest(self._pending_path.read_bytes())})
        self._pending_path.replace(self._state_path)
        self._saved_at = time.monotonic()

    def _save_if_due(self) -> None:
        """Save part-way through a long wait, so that one killed before its end keeps the time already passed."""
        if time.monotonic() - self._saved_at >= SAVE_INTERVAL:
            self._checkpoint()

    def _verify_log(self) -> None:
        previous = ""
        for entry in self.entries:
            body = {key: value for key, value in entry.items() if key != "hash"}
            if entry["previous"] != previous or entry["hash"] != _digest(_canonical(body)):
                raise RuleViolation(f"log entry {entry['index']} does not follow from the entry before it")
            previous = entry["hash"]

    def _verify_configuration(self) -> None:
        """Refuse a session.json or a ground.png that differs from what the painting was begun with.

        Either would silently change the sheet under paint already laid on it. The first entry of the log
        records the configuration; a painting being created has no entries yet.
        """
        config = self.configuration
        if self.entries and Configuration(**self.entries[0]["configuration"]) != config:
            raise RuleViolation("session.json does not match the configuration this painting was begun with")
        ground = self.directory / GROUND_FILE
        if config.ground_digest is not None and (
            not ground.is_file() or _digest(ground.read_bytes()) != config.ground_digest
        ):
            raise RuleViolation(f"{GROUND_FILE} does not match the image this painting was begun on")

    def _restore(self) -> None:
        if not self.entries:
            return
        # Entries after the last recorded save belong to a command that was killed before it saved.
        recorded = next((entry["state"] for entry in reversed(self.entries) if "state" in entry), None)
        pending = self._pending_path
        if pending.exists():
            # A save that the log records but that was not yet put in place is complete; any other is not.
            if recorded == _digest(pending.read_bytes()):
                pending.replace(self._state_path)
            else:
                pending.unlink()
        if recorded != _digest(self._state_path.read_bytes()):
            raise RuleViolation("the saved state does not match the last checkpoint in the log")
        state = torch.load(self._state_path, weights_only=True)
        if "frames" in state:
            self._recorder.rewind(state["frames"])
        for name, sheet in self.studio.sheets.items():
            sheet.load_state(state["sheets"][name])
            sheet.tilt = tuple(state["sheets"][name]["tilt"])
        self.studio.brush = Brush(**state["brush"]) if state["brush"] else None
        self.studio.clock = state["clock"]
        self.studio.loads = state["loads"]
        self.strokes_used = state["strokes_used"]
        self.paint_applied = state["paint_applied"]
        self.sealed = state["sealed"]

    # ------------------------------------------------------------------ rules

    def _validate(self, actions: list[dict]) -> None:
        """Check a whole pass against the rules before any of it touches the sheet."""
        config = self.configuration
        if self.sealed:
            raise RuleViolation("this painting is finished")
        strokes = self.strokes_used
        paint_applied = self.paint_applied
        held = self.studio.brush
        brush_in_hand = (held.type_name, held.size, held.hair) if held else None
        for number, action in enumerate(actions, start=1):
            try:
                kind = action["action"]
                sheet = action.get("sheet", "painting")
                on_painting = sheet == "painting"
                if kind in SHEET_ACTIONS:
                    if sheet == "scrap" and not config.scrap_allowed:
                        raise RuleViolation("this painting has no scrap sheet")
                    if sheet not in ("painting", "scrap"):
                        raise ValueError(f"unknown sheet {sheet!r}")
                if kind in ("stroke", "blot", "pencil", "erase", "mask", "pen") and not action["path"]:
                    raise ValueError("path is empty")
                if kind == "load":
                    hair = action.get("hair", "")
                    validate_brush_request(
                        action["brush"],
                        action["size"],
                        action.get("pigments", {}),
                        action["water"],
                        config.palette,
                        hair,
                    )
                    requested = (action["brush"], action["size"], hair)
                    if not action.get("rinse", True) and brush_in_hand not in (None, requested):
                        raise ValueError("a different brush must be loaded with a rinse")
                    brush_in_hand = requested
                elif kind == "drain":
                    if brush_in_hand is None:
                        raise ValueError("no brush is loaded")
                    if not 0.0 <= action["water"] <= 1.0:
                        raise ValueError("water must be between 0 and 1")
                elif kind == "stroke":
                    if brush_in_hand is None:
                        raise ValueError("no brush is loaded")
                    validate_journey(action["path"])
                    if not 0 < action.get("dwell", DAB_DURATION) <= 10:
                        raise ValueError("dwell must be between 0 and 10 seconds")
                    if action.get("speed", DEFAULT_STROKE_SPEED) <= 0:
                        raise ValueError("speed must be positive")
                elif kind == "blot":
                    if not 1 <= action["radius"] <= 80:
                        raise ValueError("blot radius must be between 1 and 80 pixels")
                elif kind == "mask":
                    if not 0.5 <= action["radius"] <= 40:
                        raise ValueError("mask radius must be between 0.5 and 40 pixels")
                    for point in action["path"]:
                        if len(point) not in (2, 3):
                            raise ValueError("a mask point is [x, y] or [x, y, pressure]")
                        if len(point) == 3 and not 0.0 <= point[2] <= 1.0:
                            raise ValueError("mask pressure must be between 0 and 1")
                elif kind == "pen":
                    speed = action.get("speed", DEFAULT_STROKE_SPEED)
                    validate_pen_request(action["path"], action["width"], action["ink"], speed, config.palette)
                elif kind == "unmask":
                    if ("path" in action) != ("radius" in action):
                        raise ValueError("unmask takes a path and a radius together, or neither")
                    if "path" in action and not action["path"]:
                        raise ValueError("path is empty")
                    if "radius" in action and not 1 <= action["radius"] <= 80:
                        raise ValueError("unmask radius must be between 1 and 80 pixels")
                elif kind == "fix":
                    if ("path" in action) != ("radius" in action):
                        raise ValueError("fix takes a path and a radius together, or neither")
                    if "path" in action:
                        if not action["path"]:
                            raise ValueError("path is empty")
                        if not 1 <= action["radius"] <= 80:
                            raise ValueError("fix radius must be between 1 and 80 pixels")
                        if any(not isinstance(point, list) or len(point) != 2 for point in action["path"]):
                            raise ValueError("a fix point is [x, y]")
                elif kind in ("pencil", "erase"):
                    if not config.pencil_allowed:
                        raise RuleViolation("this painting does not allow a pencil underdrawing")
                    if on_painting and paint_applied:
                        raise RuleViolation("the underdrawing cannot change once paint is on the painting")
                elif kind == "wait":
                    if not 0 < action["seconds"] <= 3600:
                        raise ValueError("seconds must be between 0 and 3600")
                    if "film" in action:
                        if sheet == "scrap" and not config.scrap_allowed:
                            raise RuleViolation("this painting has no scrap sheet")
                        watched = self.studio.sheets[sheet]
                        x, y = action["at"]
                        if not (0 <= x < watched.width and 0 <= y < watched.height):
                            raise ValueError(f"point {x:g},{y:g} is off the sheet")
                        if action["film"] < 0:
                            raise ValueError("film depth cannot be negative")
                elif kind == "tilt":
                    if max(abs(action["x"]), abs(action["y"])) > 0.3:
                        raise ValueError("tilt must be within 0.3 on each axis")
                elif kind != "dry":
                    raise ValueError(f"unknown action {kind!r}")
                if kind in TOUCHING_ACTIONS + SURFACE_TREATMENTS and on_painting:
                    strokes += 1
                    paint_applied = paint_applied or kind in TOUCHING_ACTIONS
                    if strokes > config.stroke_budget:
                        raise RuleViolation(f"the stroke budget of {config.stroke_budget} is spent")
            except KeyError as missing:
                raise ValueError(f"action {number} is missing {missing}") from None
            except (ValueError, RuleViolation) as problem:
                raise type(problem)(f"action {number}: {problem}") from None

    # ---------------------------------------------------------------- actions

    def interruption(self) -> Interruption | None:
        """How far the last pass got, when it stopped before its end."""
        begun = max((entry["index"] for entry in self.entries if entry["action"] == "pass"), default=None)
        if begun is None or self.sealed:
            return None
        given = self.entries[begun]
        carried_out = [entry for entry in self.entries[begun + 1 :] if "detail" in entry]
        if len(carried_out) == given["actions"]:
            return None
        reached = carried_out[-1] if carried_out else given
        waited = max(0.0, self.studio.clock - reached["clock"])  # the log keeps the clock to the millisecond
        return Interruption(given["digest"], given["actions"], len(carried_out), waited)

    def paint(self, actions: list[dict]) -> int | None:
        """Carry out a pass of actions in order. Nothing here can be taken back.

        Each action is saved as it ends. Given again after it was cut short, the same pass
        carries on from the action it stopped in rather than repeating those already on the
        sheet; the number of those is returned, or None for a pass begun afresh.
        """
        digest = _digest(_canonical(actions))
        stopped = self.interruption()
        if stopped is not None and stopped.digest == digest:
            # The remainder was checked against the rules when the pass began.
            completed, waited = stopped.completed, stopped.waited
        else:
            self._validate(actions)
            self._append({"action": "pass", "actions": len(actions), "digest": digest})
            completed, waited = None, 0.0
        for action in actions[completed or 0 :]:
            self._perform(action, waited)
            waited = 0.0
        return completed

    def _perform(self, action: dict, waited: float = 0.0) -> None:
        """Carry out one action; of a wait that was cut short, only the time that had not yet passed."""
        studio = self.studio
        kind = action["action"]
        sheet = action.get("sheet", "painting")
        if kind == "load":
            studio.load_brush(
                action["brush"],
                action["size"],
                action.get("pigments", {}),
                action["water"],
                action.get("rinse", True),
                action.get("hair", ""),
            )
        elif kind == "drain":
            studio.drain(action["water"])
        elif kind == "stroke":
            studio.stroke(
                sheet,
                action["path"],
                action.get("speed", DEFAULT_STROKE_SPEED),
                action.get("smooth", True),
                action.get("dwell", DAB_DURATION),
            )
        elif kind == "blot":
            studio.blot(sheet, action["path"], action["radius"])
        elif kind == "mask":
            studio.mask(sheet, action["path"], action["radius"], action.get("smooth", True))
        elif kind == "unmask":
            studio.unmask(sheet, action.get("path"), action.get("radius"))
        elif kind == "pen":
            studio.pen(
                sheet,
                action["path"],
                action["width"],
                action["ink"],
                action.get("speed", DEFAULT_STROKE_SPEED),
                action.get("smooth", True),
            )
        elif kind == "fix":
            studio.fix(sheet, action.get("path"), action.get("radius"))
        elif kind == "pencil":
            studio.pencil(sheet, action["path"], action.get("darkness", 0.6), action.get("smooth", True))
        elif kind == "erase":
            studio.erase(sheet, action["path"], action.get("radius", 4.0))
        elif kind == "wait" and "film" in action:
            x, y = action["at"]
            studio.wait_for_film(sheet, x, y, action["film"], action["seconds"] - waited)
        elif kind == "wait":
            studio.wait(action["seconds"] - waited)
        elif kind == "tilt":
            studio.tilt(sheet, action["x"], action["y"])
        elif kind == "dry":
            studio.dry()
        if kind in TOUCHING_ACTIONS + SURFACE_TREATMENTS and sheet == "painting":
            self.strokes_used += 1
            self.paint_applied = self.paint_applied or kind in TOUCHING_ACTIONS
        self._checkpoint({"action": kind, "detail": action})

    def look(
        self,
        sheet: str = "painting",
        view: str = "color",
        region: tuple[int, int, int, int] | None = None,
        grid: bool = False,
    ) -> Path:
        """Save a picture of the sheet as it is now. Looking is free and changes nothing."""
        if view not in VIEWS:
            raise ValueError(f"unknown view {view!r}; available: {', '.join(VIEWS)}")
        directory = self.directory / "looks"
        directory.mkdir(exist_ok=True)
        path = directory / f"{sum(1 for _ in directory.iterdir()):04d}_{sheet}_{view}.png"
        inspection_image(self.studio.sheets[sheet], view, region, grid).save(path)
        return path

    def wetness(self, points: list[tuple[float, float]], sheet: str = "painting") -> list[dict[str, float]]:
        """Read how wet the sheet is at each point: the depth of the film on it and how full the paper is."""
        target = self.studio.sheets[sheet]
        readings = []
        for x, y in points:
            if not (0 <= x < target.width and 0 <= y < target.height):
                raise ValueError(f"point {x:g},{y:g} is off the sheet")
            reading = target.wetness_at(x, y)
            readings.append({"x": x, "y": y} | {name: round(value, 3) for name, value in reading.items()})
        return readings

    def finish(self) -> tuple[Path, Path]:
        """Let the painting dry, export it with its time-lapse, and close it for good."""
        if self.sealed:
            raise RuleViolation("this painting is finished")
        self.studio.dry()
        picture = self.directory / "painting.png"
        video = self.directory / "timelapse.mp4"
        to_image(render(self.studio.sheets["painting"])).save(picture)
        encode_video(self.directory / "frames", video)
        self.sealed = True
        self._checkpoint({"action": "finish", "picture": _digest(picture.read_bytes())})
        return picture, video

    def report(self) -> dict:
        studio = self.studio
        brush = studio.brush
        stopped = self.interruption()
        interrupted = {}
        if stopped is not None:
            interrupted["interrupted_pass"] = {
                "actions_completed": stopped.completed,
                "actions_given": stopped.given,
                "seconds_passed_in_next_action": round(stopped.waited, 1),
            }
        return interrupted | {
            "clock_seconds": round(studio.clock, 1),
            "strokes_used": self.strokes_used,
            "stroke_budget": self.configuration.stroke_budget,
            "support": self.configuration.support,
            "ground": self.configuration.ground_digest is not None,
            "brush": None
            if brush is None
            else {
                "type": brush.type_name,
                "hair": brush.hair_type.name,
                "size": brush.size,
                "water_remaining": round(brush.fullness, 2),
                "pigments": {n: c for n, c in zip(studio.palette, brush.concentration) if c > 0},
            },
            "paper": {
                name: {stage: round(share, 3) for stage, share in sheet.stage_fractions().items()}
                for name, sheet in studio.sheets.items()
            },
            "wetness": {
                name: {measure: round(value, 3) for measure, value in sheet.wetness_summary().items()}
                for name, sheet in studio.sheets.items()
            },
            "finished": self.sealed,
        }

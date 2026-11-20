"""The painter's working environment: sheets, one brush in hand, and a clock.

Time passes on every sheet together. A stroke takes time to make, and paint laid
earlier keeps flowing and drying while later strokes are made.
"""

import math
import random
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
import torch
from torch import Tensor

from .brushes import (
    ANGLE,
    BRUSH_TYPES,
    HAIRS,
    PRESSURE,
    STRONGEST_CONCENTRATION,
    TIME,
    TWIST,
    Brush,
    Journey,
    Path,
    arrange_hairs,
    journey_between,
    trace_journey,
    trace_path,
)
from .pigments import PIGMENTS
from .recording import FrameRecorder
from .rendering import render, to_image
from .simulation import Sheet

if TYPE_CHECKING:
    from .together import SharedClock

STROKE_FRAME_INTERVAL = 0.3  # seconds of painting between recorded frames
WAIT_FRAME_COUNT = 40  # frames recorded across one wait
DRYING_FRAME_INTERVAL = 8.0
DRYING_LIMIT = 3600.0
DEFAULT_STROKE_SPEED = 120.0  # pixels per second
DAB_DURATION = 0.3
DRAIN_DURATION = 1.0  # seconds taken to touch the brush to a cloth
FILM_WATCH_INTERVAL = 1.0  # seconds between looks at the film while waiting for it to thin
PENCIL_RADIUS = 0.9
MASK_SPEED = 60.0  # pixels per second at which masking fluid is drawn on
MASK_LIGHTEST_SHARE = 0.15  # width of a line of masking fluid laid with no pressure, as a share of its full width
UNMASK_DURATION = 5.0  # seconds taken to rub masking fluid away
PEN_LIGHTEST_SHARE = 0.15  # width of a pen line drawn with no pressure, as a share of its full width
# A brush never picks up exactly the mix asked for. Spread of pigment and of water from load to load.
PIGMENT_VARIATION = 0.12
WATER_VARIATION = 0.06


class Studio:
    def __init__(
        self,
        sheets: dict[str, Sheet],
        palette: list[str],
        recorder: FrameRecorder | None = None,
        recorded_sheet: str = "painting",
        shared_clock: "SharedClock | None" = None,
        seed: int = 0,
    ) -> None:
        self.sheets = sheets
        self.palette = palette
        self.recorder = recorder
        self.recorded_sheet = recorded_sheet
        self.shared_clock = shared_clock  # set when this studio's sheets are advanced as part of a batch
        self.seed = seed
        self.loads = 0  # how many times a brush has been loaded; with the seed, it fixes each load's variation
        self.brush: Brush | None = None
        self.clock = 0.0
        # Called between the spans of a wait, when nothing is in motion but the paint.
        self.while_waiting: Callable[[], None] = lambda: None
        self._time_step = next(iter(sheets.values())).parameters.time_step
        self._since_frame = 0.0

    @property
    def device(self) -> torch.device:
        return next(iter(self.sheets.values())).tooth.device

    def _tensor(self, values) -> Tensor:
        return torch.as_tensor(values, dtype=torch.float32, device=self.device)

    def _pass_time(self, duration: float) -> None:
        if self.shared_clock is not None:
            self.shared_clock.pass_time(duration)
        else:
            for sheet in self.sheets.values():
                sheet.advance(duration)
        self.clock += duration

    def _record(self, brush: tuple[float, float, float] | None = None) -> None:
        if self.recorder is not None:
            self.recorder.capture(to_image(render(self.sheets[self.recorded_sheet])), brush)

    # ---------------------------------------------------------------- actions

    def load_brush(
        self,
        type_name: str,
        size: float,
        pigments: dict[str, float],
        water: float,
        rinse: bool = True,
        hair: str = "",
    ) -> None:
        """Charge the brush with a mix; without rinsing, the mix joins what the brush already holds."""
        # What the brush picks up differs a little from what was asked for, repeatably for this painting.
        chance = random.Random(f"{self.seed}:{self.loads}")
        self.loads += 1
        pigment_share = min(chance.lognormvariate(0.0, PIGMENT_VARIATION), 1.5)
        water_share = min(max(chance.gauss(1.0, WATER_VARIATION), 0.8), 1.2)
        concentration = [
            min(float(pigments.get(name, 0.0)) * pigment_share, STRONGEST_CONCENTRATION) for name in self.palette
        ]
        # The hairs settle differently each time the brush is charged.
        hairs = arrange_hairs(size, chance.getrandbits(32))
        brush = Brush(type_name, size, concentration, reservoir=0.0, hairs=hairs, hair=hair)
        brush.reservoir = min(water * water_share, 1.0) * brush.capacity
        held = self.brush
        if not rinse and held is not None:
            if (held.type_name, held.size, held.hair) != (type_name, size, hair):
                raise ValueError("a different brush must be loaded with a rinse")
            total = held.reservoir + brush.reservoir
            if total > 0:
                brush.concentration = [
                    (old * held.reservoir + new * brush.reservoir) / total
                    for old, new in zip(held.concentration, concentration)
                ]
            brush.reservoir = min(total, brush.capacity)
        self.brush = brush

    def drain(self, water: float) -> None:
        """Touch the brush to a cloth until it holds no more than this share of what it can.

        The cloth draws out paint as it is, pigment and water together, so the brush keeps its
        colour and strength and loses only fullness. A drained brush lays less, pushes paint
        along and soaks up standing water: it is the damp brush that softens, pulls out and lifts.
        """
        brush = self.brush
        if brush is None:
            raise ValueError("no brush is loaded")
        brush.reservoir = min(brush.reservoir, water * brush.capacity)
        self._pass_time(DRAIN_DURATION)

    def stroke(self, sheet_name: str, path: Journey, speed: float, smooth: bool, dwell: float = DAB_DURATION) -> None:
        """Take the brush on a journey across the sheet.

        Each point may set the pressure, the angle of the brush to the paper and the twist of
        its head. Points that give times are met at those times; without them the brush travels
        at one speed, and a single point is a dab held for the dwell.
        """
        brush = self.brush
        if brush is None:
            raise ValueError("no brush is loaded")
        sheet = self.sheets[sheet_name]
        traced = trace_journey(path, smooth, speed, dwell)
        concentration = self._tensor(brush.concentration)
        hairs = self._tensor(brush.hairs)
        on_tip = torch.zeros_like(concentration)  # wet paint riding on the tip of the brush
        dt = self._time_step
        for step in range(max(1, round(float(traced[-1, TIME]) / dt))):
            piece = journey_between(traced, step * dt, (step + 1) * dt)
            pressure, angle, twist = (float(piece[:, column].mean()) for column in (PRESSURE, ANGLE, TWIST))
            travelled = float(np.linalg.norm(np.diff(piece[:, :2], axis=0), axis=1).sum())
            radii = brush.radius(piece[:, PRESSURE], angle)
            contact = brush.contact(pressure, travelled / dt, angle, twist)
            used, pigment_out, on_tip = sheet.apply_brush(
                self._tensor(piece[:, :2]), self._tensor(radii), contact, concentration, brush.reservoir, hairs, on_tip
            )
            pigment_held = (concentration * brush.reservoir - pigment_out).clamp(min=0)
            brush.reservoir = min(max(brush.reservoir - used, 0.0), brush.capacity)
            concentration = (pigment_held / max(brush.reservoir, 1e-3 * brush.capacity)).clamp(max=20.0)
            brush.concentration = concentration.tolist()
            self._pass_time(dt)
            self._since_frame += dt
            if self._since_frame >= STROKE_FRAME_INTERVAL and sheet_name == self.recorded_sheet:
                self._since_frame = 0.0
                self._record((float(piece[-1, 0]), float(piece[-1, 1]), float(radii[-1])))
        # When the brush leaves the sheet, what its tip still carries is drawn up into its body.
        pigment_held = concentration * brush.reservoir + on_tip
        brush.concentration = (pigment_held / max(brush.reservoir, 1e-3 * brush.capacity)).clamp(max=20.0).tolist()

    def blot(self, sheet_name: str, path: Path, radius: float) -> None:
        samples = trace_path(path, smooth=False)
        radii = torch.full((len(samples),), radius)
        self.sheets[sheet_name].blot(self._tensor(samples[:, :2]), self._tensor(radii))
        self._pass_time(1.0)
        self._record()

    def mask(self, sheet_name: str, path: Path, radius: float, smooth: bool = True) -> None:
        """Lay masking fluid along a path, as with an old brush or a colour shaper: pressed down the line is as
        wide as the radius, lifted it narrows towards a point. A point that gives no pressure is laid at full
        pressure. The line takes the time it takes to draw, and then resists water until it is rubbed away."""
        controls = [list(point) if len(point) > 2 else [point[0], point[1], 1.0] for point in path]
        samples = trace_path(controls, smooth)
        share = MASK_LIGHTEST_SHARE + (1.0 - MASK_LIGHTEST_SHARE) * samples[:, 2]
        self.sheets[sheet_name].apply_mask(self._tensor(samples[:, :2]), self._tensor(radius * share))
        length = float(np.linalg.norm(np.diff(samples[:, :2], axis=0), axis=1).sum()) if len(samples) > 1 else 0.0
        steps = max(1, round(length / MASK_SPEED / self._time_step))
        self._pass_time(steps * self._time_step)
        self._record()

    def unmask(self, sheet_name: str, path: Path | None = None, radius: float | None = None) -> None:
        """Rub masking fluid away: all of it, or along a path with a rubber of the given radius."""
        sheet = self.sheets[sheet_name]
        if path is None or radius is None:
            sheet.remove_mask()
        else:
            samples = trace_path(path, smooth=False)
            radii = torch.full((len(samples),), radius)
            sheet.remove_mask(self._tensor(samples[:, :2]), self._tensor(radii))
        self._pass_time(UNMASK_DURATION)
        self._record()

    def pen(self, sheet_name: str, path: Path, width: float, ink: dict[str, float], speed: float, smooth: bool) -> None:
        """Draw a line in ink, which the pen lays at the same strength from the start of the line to its end.

        Pressed down the line is as wide as the width; lifted it narrows to 0.15 of it, and a point that gives no
        pressure is drawn at full width. The pen travels at one speed, and a single point is a dot held for as long as
        a dab. Time passes on the sheet as the line is drawn. The pen needs no brush and leaves the one in hand as it was.
        """
        sheet = self.sheets[sheet_name]
        controls = [list(point) if len(point) > 2 else [point[0], point[1], 1.0] for point in path]
        traced = trace_journey(controls, smooth, speed, DAB_DURATION)
        amounts = self._tensor([float(ink.get(name, 0.0)) for name in self.palette])
        covered = torch.zeros_like(sheet.water)  # how far this line has already inked each cell
        dt = self._time_step
        # The pen keeps on until the last time step has reached the end of the line.
        for step in range(max(1, math.ceil(float(traced[-1, TIME]) / dt - 1e-6))):
            piece = journey_between(traced, step * dt, (step + 1) * dt)
            radii = 0.5 * width * (PEN_LIGHTEST_SHARE + (1.0 - PEN_LIGHTEST_SHARE) * piece[:, PRESSURE])
            sheet.apply_pen(self._tensor(piece[:, :2]), self._tensor(radii), amounts, covered)
            self._pass_time(dt)
            self._since_frame += dt
            if self._since_frame >= STROKE_FRAME_INTERVAL and sheet_name == self.recorded_sheet:
                self._since_frame = 0.0
                self._record((float(piece[-1, 0]), float(piece[-1, 1]), float(radii[-1])))

    def pencil(self, sheet_name: str, path: Path, darkness: float, smooth: bool = True) -> None:
        samples = trace_path(path, smooth)
        radii = torch.full((len(samples),), PENCIL_RADIUS)
        self.sheets[sheet_name].draw_graphite(self._tensor(samples[:, :2]), self._tensor(radii), darkness)
        self._record()

    def erase(self, sheet_name: str, path: Path, radius: float) -> None:
        samples = trace_path(path, smooth=False)
        radii = torch.full((len(samples),), radius)
        self.sheets[sheet_name].erase_graphite(self._tensor(samples[:, :2]), self._tensor(radii))
        self._record()

    def tilt(self, sheet_name: str, x: float, y: float) -> None:
        self.sheets[sheet_name].tilt = (x, y)

    def wait(self, seconds: float) -> None:
        interval = max(self._time_step, round(seconds / WAIT_FRAME_COUNT, 1))
        remaining = seconds
        while remaining > 1e-9:
            chunk = min(interval, remaining)
            self._pass_time(chunk)
            remaining -= chunk
            self._record()
            self.while_waiting()

    def wait_for_film(self, sheet_name: str, x: float, y: float, film: float, longest: float) -> float:
        """Wait until the film of water about a point has thinned to a depth, and return how long that took.

        This is the painter watching the shine go off a wash. The wait ends at the longest time
        allowed if the film has not thinned by then.
        """
        sheet = self.sheets[sheet_name]
        waited = 0.0
        while waited < longest - 1e-9 and sheet.wetness_at(x, y)["film"] > film:
            chunk = min(FILM_WATCH_INTERVAL, longest - waited)
            self._pass_time(chunk)
            waited += chunk
            self._record()
            self.while_waiting()
        return waited

    def dry(self) -> float:
        """Wait until every sheet is dry and return how long that took."""
        waited = 0.0
        while waited < DRYING_LIMIT and any(sheet.is_drying() for sheet in self.sheets.values()):
            self._pass_time(DRYING_FRAME_INTERVAL)
            waited += DRYING_FRAME_INTERVAL
            self._record()
            self.while_waiting()
        return waited


def validate_brush_request(
    type_name: str, size: float, pigments: dict[str, float], water: float, palette: list[str], hair: str = ""
) -> None:
    if type_name not in BRUSH_TYPES:
        raise ValueError(f"unknown brush {type_name!r}; available: {', '.join(BRUSH_TYPES)}")
    if hair and hair not in HAIRS:
        raise ValueError(f"unknown hair {hair!r}; available: {', '.join(HAIRS)}")
    if not 0.5 <= size <= 80:
        raise ValueError("brush size must be between 0.5 and 80 pixels")
    if not 0.0 <= water <= 1.0:
        raise ValueError("water must be between 0 and 1")
    _validate_mix(pigments, palette)


def validate_pen_request(path: Path, width: float, ink: dict[str, float], speed: float, palette: list[str]) -> None:
    for point in path:
        if len(point) not in (2, 3):
            raise ValueError("a pen point is [x, y] or [x, y, pressure]")
        if len(point) == 3 and not 0.0 <= point[2] <= 1.0:
            raise ValueError("pen pressure must be between 0 and 1")
    if not 0.25 <= width <= 8:
        raise ValueError("pen width must be between 0.25 and 8 pixels")
    if speed <= 0:
        raise ValueError("speed must be positive")
    _validate_mix(ink, palette)
    if sum(ink.values()) <= 0.0:
        raise ValueError("the ink must hold some paint")


def _validate_mix(pigments: dict[str, float], palette: list[str]) -> None:
    for name, amount in pigments.items():
        if name not in PIGMENTS:
            raise ValueError(f"unknown pigment {name!r}")
        if name not in palette:
            raise ValueError(f"pigment {name!r} is not on this painting's palette: {', '.join(palette)}")
        if amount < 0.0:
            raise ValueError("pigment concentration cannot be negative")
    if sum(pigments.values()) > STRONGEST_CONCENTRATION:
        raise ValueError(f"the pigments of a mix can total at most {STRONGEST_CONCENTRATION:g}")

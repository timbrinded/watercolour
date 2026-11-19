"""Scenarios of the calibration suite: small paintings and experiments on the sheet, each returning named measurements.

A painting is a script carried out through Studio on its own 128-pixel sheet. Paintings of one family are painted
together, each on its own sheet of one SheetBatch, as engine_trials does: time passes on all of them for about the
cost of one, and each sheet gets the picture it would have had alone. An experiment sets up its own sheets, sessions
or checks and runs on its own.

Where a gate is measured against the 0.8.0 rig, the 0.8.0 package is taken from git at REFERENCE_REVISION and
imported under the name watercolor_reference. Its renderer pictures any sheet as 0.8.0 would: all paint in one
summed Kubelka-Munk layer.
"""

import dataclasses
import importlib
import importlib.util
import io
import itertools
import math
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import torch
import torch.nn.functional as F
from torch import Tensor

from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.rendering import render_view
from watercolor.simulation import Contact, Sheet, SheetBatch, SimulationParameters
from watercolor.studio import Studio
from watercolor.together import SharedClock

Measurement = float | int | bool | str | None | list
Measurements = dict[str, Measurement]

REPOSITORY = Path(__file__).resolve().parent.parent
# The commit on main that is the 0.8.0 rig, against which the gates are calibrated.
REFERENCE_REVISION = "d1bb128172a533a15fa3ae6cc7ff4cbb31f36d84"
REFERENCE_PACKAGE = "watercolor_reference"

SIZE = 128
SEED = 3
# One paint box for every 128-pixel painting, so that any of them can share a batch. A pigment a sheet never
# receives stays at zero there and takes no part in its physics.
PALETTE = (
    "cadmium_red",
    "french_ultramarine",
    "quinacridone_rose",
    "phthalo_green",
    "cerulean_blue",
    "burnt_umber",
    "opaque_white",
    "yellow_ochre",
)
RED, BLUE, ROSE, PHTHALO, CERULEAN, UMBER, WHITE, OCHRE = range(len(PALETTE))
# New state fields that an approved change may add: the gum of the binder and the two cumulative paint layers.
APPROVED_NEW_FIELDS = ("gum", "underlying", "lowest")
LAYER_FIELDS = ("underlying", "lowest")
VALUE_WEIGHTS = (0.2126, 0.7152, 0.0722)


def default_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ------------------------------------------------------------------------------------------------ the 0.8.0 rig


def reference_source() -> Path:
    """Directory that holds the 0.8.0 package as the directory watercolor, taken from git on first use.

    It is kept outside the repository, where the linters and the type checker do not see it.
    """
    target = Path(tempfile.gettempdir()) / f"watercolor-reference-{REFERENCE_REVISION[:12]}"
    if (target / "watercolor" / "__init__.py").exists():
        return target
    archive = subprocess.run(
        ["git", "-C", str(REPOSITORY), "archive", REFERENCE_REVISION, "src/watercolor"],
        check=True,
        capture_output=True,
    ).stdout
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as staging:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(staging, filter="data")
        unpacked = Path(staging) / "unpacked"
        unpacked.mkdir()
        shutil.move(Path(staging) / "src" / "watercolor", unpacked / "watercolor")
        if not (target / "watercolor" / "__init__.py").exists():
            unpacked.rename(target)
    return target


def reference_module(name: str) -> ModuleType:
    """A module of the 0.8.0 package, imported beside the engine under test."""
    if REFERENCE_PACKAGE not in sys.modules:
        initialiser = reference_source() / "watercolor" / "__init__.py"
        specification = importlib.util.spec_from_file_location(
            REFERENCE_PACKAGE, initialiser, submodule_search_locations=[str(initialiser.parent)]
        )
        if specification is None or specification.loader is None:
            raise ImportError(f"cannot import the 0.8.0 package from {initialiser}")
        package = importlib.util.module_from_spec(specification)
        sys.modules[REFERENCE_PACKAGE] = package
        specification.loader.exec_module(package)
    return importlib.import_module(f"{REFERENCE_PACKAGE}.{name}")


def value(sheet: Sheet) -> Tensor:
    """The value view of the sheet as the engine under test pictures it, shape (H, W)."""
    return render_view(sheet, "value")[0]


def reference_value(sheet: Sheet) -> Tensor:
    """The value view of the same sheet as 0.8.0 pictures it: all its paint in one summed layer."""
    return reference_module("rendering").render_view(sheet, "value")[0]


def composed_value(sheet: Sheet, layers: list[Tensor]) -> Tensor:
    """Value of the sheet with its paint composed by Kubelka and Munk as the given layers, from the paper up.

    Each layer is an amount of every pigment, shape (P, H, W), pictured with the 0.8.0 renderer's own layer
    and paper, so that the composition alone differs from what 0.8.0 shows. The sheet is taken as dry.
    """
    rendering = reference_module("rendering")
    over = rendering._over
    device = sheet.tooth.device
    absorption = torch.tensor([p.absorption for p in sheet.pigments], device=device)
    scattering = torch.tensor([p.scattering for p in sheet.pigments], device=device)
    relief = sheet.tooth - F.avg_pool2d(sheet.tooth[None, None], 5, stride=1, padding=2)[0, 0]
    paper_colour = torch.tensor(rendering.PAPER_COLOR, device=device).reshape(3, 1, 1)
    colour = paper_colour * (1.0 + 0.05 * relief)
    for layer in layers:
        colour = over(layer, absorption, scattering, colour)
    weights = torch.tensor(VALUE_WEIGHTS, device=device).reshape(3, 1, 1)
    return (colour.clamp(0, 1) * weights).sum(0)


def two_layer_value(sheet: Sheet, beneath: Tensor) -> Tensor:
    """Value with the given paint beneath and the rest of the sheet's paint over it."""
    paint = sheet.deposited + sheet.suspended
    beneath = torch.minimum(beneath, paint)
    return composed_value(sheet, [beneath, paint - beneath])


# ------------------------------------------------------------------------------------------------ sheets and checks


Adjustment = Callable[[SimulationParameters], SimulationParameters]


def unchanged(parameters: SimulationParameters) -> SimulationParameters:
    return parameters


def still_water(parameters: SimulationParameters) -> SimulationParameters:
    """Evaporation, absorption and the drying of the paper switched off: the water stays as it was set."""
    return dataclasses.replace(parameters, evaporation_rate=0.0, absorption_rate=0.0, paper_evaporation_rate=0.0)


def nothing_soaks_away(parameters: SimulationParameters) -> SimulationParameters:
    """Evaporation and absorption switched off, as in test_flow_alone_conserves_water."""
    return dataclasses.replace(parameters, evaporation_rate=0.0, absorption_rate=0.0)


def new_sheet(
    height: int = SIZE,
    width: int = SIZE,
    seed: int = SEED,
    device: torch.device | None = None,
    palette: tuple[str, ...] = PALETTE,
    adjust: Adjustment = unchanged,
) -> Sheet:
    paper = generate_paper(height, width, seed, device or default_device())
    return Sheet(paper, [PIGMENTS[name] for name in palette], adjust(SimulationParameters()))


def new_studio(
    seed: int = SEED,
    size: int = SIZE,
    device: torch.device | None = None,
    palette: tuple[str, ...] = PALETTE,
    adjust: Adjustment = unchanged,
) -> Studio:
    sheet = new_sheet(size, size, seed, device, palette, adjust)
    return Studio({"painting": sheet}, list(palette))


def sheet_of(studio: Studio) -> Sheet:
    return studio.sheets["painting"]


def unsound_cells(sheet: Sheet) -> int:
    """Number of values in the sheet's state that are not finite or are negative, and of cells where the paint
    layers are out of order (each layer must lie within the one above it, and all within what is deposited)."""
    bad = 0
    for name in sheet.STATE_FIELDS:
        field = getattr(sheet, name)
        bad += int((~torch.isfinite(field)).sum()) + int((field < 0).sum())
    underlying, lowest = kept(sheet, "underlying"), kept(sheet, "lowest")
    if underlying is not None and lowest is not None:
        bad += int((lowest > underlying).sum()) + int((underlying > sheet.deposited).sum())
    return bad


def state_difference(first: Sheet, second: Sheet) -> float:
    """Largest absolute difference over every state field and the value view of two sheets."""
    worst = 0.0
    for name in first.STATE_FIELDS:
        worst = max(worst, float((getattr(first, name) - getattr(second, name)).abs().max()))
    return max(worst, float((value(first) - value(second)).abs().max()))


def checkerboard(field: Tensor) -> float:
    """How strongly a field alternates from cell to cell, against its mean: the mark of an unstable explicit step."""
    alternate = torch.ones_like(field)
    alternate[::2, 1::2] = -1
    alternate[1::2, ::2] = -1
    local = field - F.avg_pool2d(field[None, None], 3, 1, 1)[0, 0]
    return float((local * alternate)[2:-2, 2:-2].mean().abs() / field.mean())


def least_squares_slope(xs: list[float], ys: list[float]) -> float:
    count = len(xs)
    mean_x, mean_y = sum(xs) / count, sum(ys) / count
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sum((x - mean_x) ** 2 for x in xs)


def rms_width(amount: Tensor) -> float:
    """Root-mean-square spread of an amount summed along its rows, in rows."""
    rows = torch.arange(amount.numel(), dtype=torch.float32, device=amount.device)
    centre = float((amount * rows).sum() / amount.sum())
    return math.sqrt(float((amount * (rows - centre) ** 2).sum() / amount.sum()))


def distance_from(sheet: Sheet, x: float, y: float) -> Tensor:
    return torch.sqrt((sheet._xs - x) ** 2 + (sheet._ys - y) ** 2)


def kept(sheet: Sheet, name: str) -> Tensor | None:
    """A state field that the engine under test may keep and 0.8.0 did not: the gum, and the paint layers."""
    found = vars(sheet).get(name)
    return found if isinstance(found, Tensor) else None


def has_gum(sheet: Sheet) -> bool:
    return kept(sheet, "gum") is not None


# ------------------------------------------------------------------------------------------------ brushwork


def lay_rows(studio: Studio, kind: str, size: float, pigments: dict[str, float], rows=(40, 64, 88)) -> None:
    """Strokes across the sheet from x = 24 to 104, a fresh load for each: the flat wash of the test suite."""
    for y in rows:
        studio.load_brush(kind, size, pigments, 1.0)
        studio.stroke("painting", [[24, y], [104, y]], 120, smooth=False)


def lay_patch(studio: Studio, name: str, strength: float) -> None:
    """Three flat-12 strokes at y = 44, 64 and 84: the patch of the binder study."""
    for y in (44, 64, 84):
        studio.load_brush("flat", 12, {name: strength}, 1.0)
        studio.stroke("painting", [[24, y, 0.9], [104, y, 0.9]], 120, smooth=False)


def reloaded_rows(
    studio: Studio, kind: str, size: float, pigments: dict[str, float], first: float, last: float, spacing: float,
    x0: float = 24, x1: float = 104, speed: float = 140.0,
) -> None:  # fmt: skip
    """Rows of strokes down the sheet, the brush reloaded every third row, as a painter lays a flat wash."""
    y, count = first, 0
    while y < last:
        if count % 3 == 0:
            studio.load_brush(kind, size, pigments, 1.0)
        studio.stroke("painting", [[x0, y, 0.9], [x1, y, 0.9]], speed, smooth=False)
        y += spacing
        count += 1


def lift_across(studio: Studio, x0: float, x1: float) -> None:
    """A damp flat brush passed three times along y = 64, a wait, and tissue pressed along the line."""
    studio.load_brush("flat", 8, {}, 0.8)
    for _ in range(3):
        studio.stroke("painting", [[x0, 64], [x1, 64]], 80, smooth=False)
    studio.wait(10)
    studio.blot("painting", [[x0, 64], [x1, 64]], 10)


def total_of(sheet: Sheet, index: int) -> float:
    return float(sheet.suspended[index].sum() + sheet.deposited[index].sum())


# ------------------------------------------------------------------------------------------------ paintings: one layer


def edge_stroke(name: str, strength: float, gum_scale: float | None = None) -> Callable[[Studio], Measurements]:
    """A flat-14 stroke on dry paper, dried: the darker edge of a wash and the width of the stroke.

    With a gum scale, the gum the stroke laid is multiplied by it at once, before the stroke dries.
    """
    index = PALETTE.index(name)

    def script(studio: Studio) -> Measurements:
        sheet = sheet_of(studio)
        studio.load_brush("flat", 14, {name: strength}, 1.0)
        studio.stroke("painting", [[20, 64, 1.0], [108, 64, 1.0]], 110, smooth=False)
        gum = kept(sheet, "gum")
        if gum_scale is not None and gum is not None:
            gum.mul_(gum_scale)
        drying = studio.dry()
        deposited = sheet.deposited[index]
        across = deposited[48:80, 36:92].mean(dim=1)
        painted = (deposited.sum(dim=1) > 0).nonzero()
        return {
            "edge_ratio": float(across[:6].max()) / float(across[12:20].mean()),
            "painted_rows": int(painted.max() - painted.min() + 1),
            "drying_seconds": drying,
            "gum_present": has_gum(sheet),
        }

    return script


def flat_wash_mop(studio: Studio) -> Measurements:
    """Three overlapping mop-16 strokes of ultramarine 0.6, dried: evenness at the scale of the wash."""
    lay_rows(studio, "mop", 16, {"french_ultramarine": 0.6})
    drying = studio.dry()
    inner = sheet_of(studio).deposited[BLUE, 44:84, 36:92]
    boxes = F.avg_pool2d(inner[None, None], 8)[0, 0]
    return {"box_variation": float(boxes.std() / boxes.mean()), "drying_seconds": drying}


def flat_wash_round(studio: Studio) -> Measurements:
    """Round-12 rows of ultramarine 0.7 every 13.2 px, reloaded every third row, dried (binder study)."""
    reloaded_rows(studio, "round", 12, {"french_ultramarine": 0.7}, 20.0, 108.0, 13.2, 16, 112)
    studio.dry()
    inner = sheet_of(studio).deposited[BLUE, 36:90, 36:90]
    blocks = F.avg_pool2d(inner[None, None], 9)[0, 0]
    return {"block_variation": float(blocks.std() / blocks.mean())}


def flat_wash_flat(studio: Studio) -> Measurements:
    """Flat-12 rows of ultramarine 0.7 every 13 px, reloaded every third row, dried (ordered-layer study)."""
    reloaded_rows(studio, "flat", 12, {"french_ultramarine": 0.7}, 26, 104, 13)
    drying = studio.dry()
    sheet = sheet_of(studio)
    paint = sheet.deposited.sum(0)
    interior = paint[40:90, 40:90]
    # The strongest paint within a few cells inside the left and right edges of each row, against the interior.
    painted = paint > 0.2 * float(interior.mean())
    edges = []
    for row in range(40, 90):
        line = painted[row].nonzero().flatten()
        if line.numel() < 10:
            continue
        left, right = int(line[0]), int(line[-1])
        edges.append(float(paint[row, left : left + 4].max()))
        edges.append(float(paint[row, right - 3 : right + 1].max()))
    return {
        "interior_variation": float(interior.std() / interior.mean()),
        "edge_ratio": sum(edges) / len(edges) / float(interior.mean()),
        "drying_seconds": drying,
        "picture_difference": float((value(sheet) - reference_value(sheet)).abs().max()),
    }


def wet_phase(studio: Studio) -> Measurements:
    """The mop wash of flat_wash_mop watched in 1 s steps: simulated seconds with water standing on the sheet."""
    sheet = sheet_of(studio)
    lay_rows(studio, "mop", 16, {"french_ultramarine": 0.6})
    wet = 0.0
    while sheet.has_surface_water() and wet < 900:
        wet += 1.0
        studio.wait(1.0)
    return {"seconds_with_film": wet}


def patch_drying(studio: Studio) -> Measurements:
    """The binder study's patch of ultramarine 1.0: how long Studio.dry() takes."""
    lay_patch(studio, "french_ultramarine", 1.0)
    return {"drying_seconds": studio.dry()}


def shine(kind: str) -> Callable[[Studio], Measurements]:
    """Three overlapping strokes of ultramarine 0.6: seconds for the film at the centre to thin to 0.3, 0.15 and 0.12."""

    def script(studio: Studio) -> Measurements:
        lay_rows(studio, kind, 16, {"french_ultramarine": 0.6})
        start = sheet_of(studio).wetness_at(64, 64)["film"]
        total, seconds = 0.0, []
        for film in (0.3, 0.15, 0.12):
            total += studio.wait_for_film("painting", 64, 64, film, 400)
            seconds.append(total)
        return {"film_at_start": start, "seconds_to_film": seconds}

    return script


def drying_film_growth(studio: Studio) -> Measurements:
    """A pale mop wash drying for 15 s: its deepest film against the deepest it was laid (no gathering into drops)."""
    sheet = sheet_of(studio)
    lay_rows(studio, "mop", 16, {"french_ultramarine": 0.05})
    deepest = float(sheet.water.max())
    studio.wait(15)
    return {"deepest_over_laid": float(sheet.water.max()) / deepest}


def rows_barely_touching(studio: Studio) -> Measurements:
    """Three mop-22 rows that only just meet, watched for 40 s: the deepest film reached."""
    sheet = sheet_of(studio)
    for y in (20, 60, 100):
        studio.load_brush("mop", 22, {"french_ultramarine": 0.5}, 1.0)
        studio.stroke("painting", [[-10, y, 0.9], [138, y, 0.9]], 280, smooth=False)
    deepest = 0.0
    for _ in range(10):
        studio.wait(4)
        deepest = max(deepest, float(sheet.water.max()))
    return {"deepest_film": deepest}


def tilt_run(studio: Studio) -> Measurements:
    """A loaded passage on a sheet tilted by 0.2 and on a level one: rows further that the run reaches in 30 s."""
    sheet = sheet_of(studio)

    def lowest_wet_row(tilt: float) -> int:
        for field in (sheet.water, sheet.saturation, sheet.suspended, sheet.deposited):
            field.zero_()
        studio.tilt("painting", 0.0, tilt)
        studio.load_brush("round", 8, {"french_ultramarine": 1.0}, 1.0)
        studio.stroke("painting", [[30, 30, 0.9], [98, 30, 0.9]], 110, smooth=False)
        studio.stroke("painting", [[64, 34]], 100, smooth=False, dwell=3.0)
        studio.wait(30)
        return int((sheet.water + sheet.saturation > 0).any(dim=1).nonzero().max())

    return {"run_rows": lowest_wet_row(0.2) - lowest_wet_row(0.0)}


def wet_balance(strength: float) -> Callable[[Studio], Measurements]:
    """Share of quinacridone rose still in suspension 20 s after a patch is laid: the settling balance of a stain."""

    def script(studio: Studio) -> Measurements:
        lay_patch(studio, "quinacridone_rose", strength)
        studio.wait(20)
        sheet = sheet_of(studio)
        return {"suspended_share": float(sheet.suspended[ROSE].sum()) / total_of(sheet, ROSE)}

    return script


def brush_and_sheet(studio: Studio) -> Measurements:
    """A nearly empty brush of strong paint drawn through wet paint: pigment on the sheet plus in the brush."""
    sheet = sheet_of(studio)

    def in_brush() -> float:
        brush = studio.brush
        assert brush is not None
        return sum(brush.concentration) * brush.reservoir

    def on_sheet() -> float:
        return float((sheet.suspended + sheet.deposited).sum())

    studio.load_brush("round", 12, {"cadmium_red": 4.0}, 1.0)
    studio.stroke("painting", [[30, 64], [98, 64]], 120, smooth=False)
    studio.load_brush("round", 12, {"french_ultramarine": 6.0}, 0.03)
    before = on_sheet() + in_brush()
    studio.stroke("painting", [[30, 66], [98, 66]], 120, smooth=False)
    return {"relative_change": abs(on_sheet() + in_brush() - before) / before}


# ------------------------------------------------------------------------------------------------ paintings: wet work


def charge(film: float | None = None, wait: float | None = None, wash: bool = True) -> Callable[[Studio], Measurements]:
    """Cadmium red 4.0 from a drained round 5 drawn into a clear mop wash once its film has thinned to a depth,
    or after a fixed wait, or across dry paper: the width of the charged colour once dry."""

    def script(studio: Studio) -> Measurements:
        sheet = sheet_of(studio)
        if wash:
            lay_rows(studio, "mop", 16, {})
            if film is not None:
                studio.wait_for_film("painting", 64, 64, film, 400)
            elif wait is not None:
                studio.wait(wait)
        at_charge = sheet.wetness_at(64, 64)["film"]
        studio.load_brush("round", 5, {"cadmium_red": 4.0}, 1.0)
        studio.drain(0.6)
        studio.stroke("painting", [[34, 64, 0.8], [94, 64, 0.8]], 110, smooth=False)
        studio.dry()
        return {"rms_width": rms_width(sheet.deposited[RED][:, 44:84].sum(dim=1)), "film_at_charge": at_charge}

    return script


def charge_rose(strength: float) -> Callable[[Studio], Measurements]:
    """A dab of quinacridone rose into a clear wash 10 s old: the second-moment radius of the rose once dry."""

    def script(studio: Studio) -> Measurements:
        sheet = sheet_of(studio)
        for y in (36, 52, 68, 84, 100):
            studio.load_brush("mop", 16, {}, 1.0)
            studio.stroke("painting", [[16, y], [112, y]], 140, smooth=False)
        studio.wait(10)
        studio.load_brush("round", 5, {"quinacridone_rose": strength}, 0.8)
        studio.stroke("painting", [[64, 64]], 100, smooth=False, dwell=0.5)
        studio.dry()
        paint = sheet.deposited[ROSE] + sheet.suspended[ROSE]
        total = float(paint.sum())
        centre_y = float((paint * sheet._ys).sum()) / total
        centre_x = float((paint * sheet._xs).sum()) / total
        spread = (paint * ((sheet._ys - centre_y) ** 2 + (sheet._xs - centre_x) ** 2)).sum() / total
        return {"radius": float(spread) ** 0.5}

    return script


def bloom_mop(studio: Studio) -> Measurements:
    """Clear water dropped into the mop wash as its film is all but gone, dried: a pale bloom with a dark rim."""
    sheet = sheet_of(studio)
    lay_rows(studio, "mop", 16, {"french_ultramarine": 0.6})
    waited = studio.wait_for_film("painting", 64, 64, 0.03, 300)
    studio.load_brush("round", 8, {}, 1.0)
    studio.stroke("painting", [[64, 64]], 100, smooth=False, dwell=0.6)
    studio.dry()
    paint = sheet.deposited[BLUE]
    distance = distance_from(sheet, 64, 64)
    away = float(paint[(distance > 24) & (distance < 30)].mean())
    profile = [float(paint[(distance >= r) & (distance < r + 2)].mean()) for r in range(0, 30, 2)]
    return {
        "centre_over_wash": float(paint[distance < 4].mean()) / away,
        "rim_over_wash": max(profile) / away,
        "waited_for_film": waited,
    }


def bloom_round(studio: Studio) -> Measurements:
    """The binder study's bloom: five round-12 rows of ultramarine 1.0 and a clear dab at film 0.03."""
    sheet = sheet_of(studio)
    for y in (30, 46, 62, 78, 94):
        studio.load_brush("round", 12, {"french_ultramarine": 1.0}, 1.0)
        studio.stroke("painting", [[16, y], [112, y]], 140, smooth=False)
    studio.wait_for_film("painting", 64, 64, 0.03, 300)
    studio.load_brush("round", 8, {}, 1.0)
    studio.stroke("painting", [[64, 64]], 100, smooth=False)
    studio.dry()
    paint = sheet.deposited[BLUE]
    distance = distance_from(sheet, 64, 64)
    profile = torch.stack([paint[(distance >= r) & (distance < r + 1)].mean() for r in range(40)])
    return {"peak_over_inside": float(profile.max()) / float(profile[:4].mean())}


def bloom_umber(studio: Studio) -> Measurements:
    """The ordered-layer study's bloom: round-12 rows of burnt umber 0.6 and a clear dab at film 0.03."""
    sheet = sheet_of(studio)
    reloaded_rows(studio, "round", 12, {"burnt_umber": 0.6}, 30, 100, 13)
    studio.wait_for_film("painting", 64, 64, 0.03, 300)
    studio.load_brush("round", 8, {}, 1.0)
    studio.stroke("painting", [[64, 64]], 100, smooth=False)
    studio.dry()
    paint = sheet.deposited.sum(0)
    distance = distance_from(sheet, 64, 64)
    profile = [float(paint[(distance >= r) & (distance < r + 2)].mean()) for r in range(0, 30, 2)]
    surround = float(paint[(distance >= 26) & (distance < 30)].mean())
    return {
        "centre_share": profile[0] / surround,
        "rim_share": max(profile) / surround,
        "picture_difference": float((value(sheet) - reference_value(sheet)).abs().max()),
    }


def drained_lift(studio: Studio) -> Measurements:
    """A drained round brush drawn twice through a wash losing its shine: the lifted line against the wash."""
    sheet = sheet_of(studio)
    lay_rows(studio, "mop", 16, {"french_ultramarine": 1.5})
    studio.wait_for_film("painting", 64, 64, 0.12, 400)
    for _ in range(2):
        studio.load_brush("round", 3, {}, 1.0)
        studio.drain(0.2)
        studio.stroke("painting", [[64, 36, 0.8], [64, 92, 0.8]], 120, smooth=False)
    brush = studio.brush
    assert brush is not None
    taken = brush.concentration[BLUE] * brush.reservoir
    studio.dry()
    blue = sheet.suspended[BLUE] + sheet.deposited[BLUE]
    return {"lifted_ratio": float(blue[44:86, 63:66].mean()) / float(blue[44:86, 76:84].mean()), "taken": taken}


def wet_in_wet_dab(studio: Studio) -> Measurements:
    """Ultramarine 4.0 dabbed into a bed of clear water 2 s old: the radii at which the dried charge falls to a
    half and to a tenth of its peak above the background."""
    sheet = sheet_of(studio)
    for y in (34, 52, 70, 88):
        studio.load_brush("mop", 12, {}, 1.0)
        studio.stroke("painting", [[20, y, 0.9], [108, y, 0.9]], 140.0, smooth=False)
    studio.wait(2.0)
    film = sheet.wetness_at(64, 61)["film"]
    studio.load_brush("round", 5, {"french_ultramarine": 4.0}, 0.8)
    studio.stroke("painting", [[64, 61]], 100, smooth=False, dwell=0.5)
    studio.dry()
    paint = sheet.deposited[BLUE]
    distance = distance_from(sheet, 64, 61)
    profile = torch.tensor([float(paint[(distance >= r) & (distance < r + 1)].mean()) for r in range(40)])
    above = profile - float(profile[-5:].mean())
    return {
        "film_at_dab": film,
        "half_radius": int((above < float(above[0]) / 2).nonzero().flatten()[0]),
        "tenth_radius": int((above < 0.1 * float(above[0])).nonzero().flatten()[0]),
        "picture_difference": float((value(sheet) - reference_value(sheet)).abs().max()),
    }


def damp_lift(studio: Studio) -> Measurements:
    """Two strokes of quinacridone rose 1.0 lifted as soon as the film has gone, while the paper is still damp:
    the share of the rose under the path that leaves the sheet."""
    sheet = sheet_of(studio)
    for y in (56, 72):
        studio.load_brush("flat", 12, {"quinacridone_rose": 1.0}, 1.0)
        studio.stroke("painting", [[24, y, 0.9], [104, y, 0.9]], 120, smooth=False)
    waited = 0.0
    while bool((sheet.water > 0).any()) and waited < 900:
        studio.wait(2.0)
        waited += 2.0
    fullness = float((sheet.saturation[56:73, 30:98] / sheet.capacity[56:73, 30:98]).mean())
    under = float(sheet.deposited[ROSE, 56:73, 30:98].sum())
    before = total_of(sheet, ROSE)
    lift_across(studio, 30, 98)
    return {"lifted_share": (before - total_of(sheet, ROSE)) / under, "paper_fullness": fullness, "waited": waited}


def unset_mixing(studio: Studio) -> Measurements:
    """Burnt umber charged into the mop wash twice before it has set: once while it shines and once when its film
    has gone but the paper is still damp. Paint that has not set mixes, so no layer may open under either charge
    and the picture must be the one 0.8.0 paints."""
    sheet = sheet_of(studio)
    parameters = sheet.parameters
    lay_rows(studio, "mop", 16, {"french_ultramarine": 0.6})
    first_film = sheet.wetness_at(44, 64)["film"]
    studio.load_brush("round", 5, {"burnt_umber": 3.0}, 0.8)
    studio.stroke("painting", [[44, 64]], 100, smooth=False, dwell=0.5)
    waited = 0.0
    while sheet.wetness_at(84, 64)["film"] > parameters.wet_threshold and waited < 400:
        studio.wait(1.0)
        waited += 1.0
    second = sheet.wetness_at(84, 64)
    studio.load_brush("round", 5, {"burnt_umber": 3.0}, 0.8)
    studio.stroke("painting", [[84, 64]], 100, smooth=False, dwell=0.5)
    studio.dry()
    charged = (sheet.deposited[UMBER] > 0.05) & (
        (distance_from(sheet, 44, 64) < 10) | (distance_from(sheet, 84, 64) < 10)
    )
    layered = 0.0
    for name in LAYER_FIELDS:
        layer = kept(sheet, name)
        if layer is not None:
            layered = max(layered, float(layer.amax(0)[charged].max()))
    return {
        "film_at_first_charge": first_film,
        "film_at_second_charge": second["film"],
        "paper_at_second_charge": second["paper"],
        "second_charge_unset": second["film"] <= parameters.wet_threshold
        and second["paper"] > parameters.damp_threshold,
        "layered_paint": layered,
        "picture_difference": float((value(sheet) - reference_value(sheet)).abs()[charged].max()),
    }


# ------------------------------------------------------------------------------------------------ paintings: over dried paint


def lift(name: str, strength: float) -> Callable[[Studio], Measurements]:
    """Two dried flat-12 strokes lifted with a damp flat brush and tissue: share of the pigment under the path
    that leaves the sheet (binder study)."""
    index = PALETTE.index(name)

    def script(studio: Studio) -> Measurements:
        sheet = sheet_of(studio)
        for y in (56, 72):
            studio.load_brush("flat", 12, {name: strength}, 1.0)
            studio.stroke("painting", [[24, y, 0.9], [104, y, 0.9]], 120, smooth=False)
        studio.dry()
        under = float(sheet.deposited[index, 56:73, 30:98].sum())
        before = total_of(sheet, index)
        lift_across(studio, 30, 98)
        return {"lifted_share": (before - total_of(sheet, index)) / under}

    return script


def lift_under_glaze(studio: Studio) -> Measurements:
    """The lift of dried quinacridone rose 1.0 with a dried glaze of ultramarine 2.0 laid over it first."""
    sheet = sheet_of(studio)
    for y in (56, 72):
        studio.load_brush("flat", 12, {"quinacridone_rose": 1.0}, 1.0)
        studio.stroke("painting", [[24, y, 0.9], [104, y, 0.9]], 120, smooth=False)
    studio.dry()
    for y in (56, 72):
        studio.load_brush("flat", 12, {"french_ultramarine": 2.0}, 1.0)
        studio.stroke("painting", [[24, y, 0.9], [104, y, 0.9]], 120, smooth=False)
    studio.dry()
    under = float(sheet.deposited[ROSE, 56:73, 30:98].sum())
    before = total_of(sheet, ROSE)
    lift_across(studio, 30, 98)
    return {"lifted_share": (before - total_of(sheet, ROSE)) / under}


def glaze_disturbance(strength: float) -> Callable[[Studio], Measurements]:
    """Share of a dried rose patch moved out of place by one glaze of clear water laid over it and dried."""

    def script(studio: Studio) -> Measurements:
        sheet = sheet_of(studio)
        lay_patch(studio, "quinacridone_rose", strength)
        studio.dry()
        before = sheet.deposited[ROSE].clone()
        for y in (40, 64, 88):
            studio.load_brush("mop", 16, {}, 1.0)
            studio.stroke("painting", [[10, y], [118, y]], 140, smooth=False)
        studio.dry()
        after = sheet.deposited[ROSE] + sheet.suspended[ROSE]
        return {"moved_share": float((after - before).abs().sum() / before.sum())}

    return script


def glaze_over_rose(studio: Studio) -> Measurements:
    """A flat glaze of ultramarine 0.7 across a dried rose patch and clean paper: its evenness over the patch,
    and how much more of it the patch holds."""
    sheet = sheet_of(studio)
    lay_patch(studio, "quinacridone_rose", 2.0)
    studio.dry()
    reloaded_rows(studio, "round", 12, {"french_ultramarine": 0.7}, 20.0, 108.0, 13.2, 8, 120)
    studio.dry()
    blue = sheet.deposited[BLUE]
    over_patch = blue[50:78, 40:88]
    means = F.avg_pool2d(over_patch[None, None], 6)[0, 0]
    return {
        "variation_over_patch": float(means.std() / means.mean()),
        "patch_over_paper": float(over_patch.mean()) / float(blue[24:42, 30:90].mean()),
    }


def dried_wash_lift(studio: Studio) -> Measurements:
    """A dried flat wash of ultramarine 1.2, lifted along a line with a damp flat brush and tissue, dried."""
    sheet = sheet_of(studio)
    reloaded_rows(studio, "flat", 12, {"french_ultramarine": 1.2}, 30, 100, 13)
    studio.dry()
    before = float(sheet.deposited[BLUE, 60:69, 40:90].sum())
    value_before = float(value(sheet)[61:68, 40:90].mean())
    lift_across(studio, 20, 108)
    studio.dry()
    return {
        "lifted_share": 1.0 - float(sheet.deposited[BLUE, 60:69, 40:90].sum()) / before,
        "value_gain": float(value(sheet)[61:68, 40:90].mean()) - value_before,
        "picture_difference": float((value(sheet) - reference_value(sheet)).abs().max()),
    }


# ------------------------------------------------------------------------------------------------ paintings: layers

COLUMNS = (20, 46, 72, 98)
BAND = slice(50, 66)
PAPER_ROWS = (slice(8, 22), slice(106, 120))
DARK = {"burnt_umber": 2.0, "french_ultramarine": 1.0}
DARK_PIGMENTS = (UMBER, BLUE)


def dark_band(studio: Studio, pigments: dict[str, float]) -> None:
    """Three flat-10 strokes across the sheet at y = 44, 58 and 72."""
    for y in (44, 58, 72):
        studio.load_brush("flat", 10, pigments, 1.0)
        studio.stroke("painting", [[6, y, 0.9], [122, y, 0.9]], 120, smooth=False)


def column(studio: Studio, x: float, pigments: dict[str, float]) -> None:
    """A round-5 stroke down the sheet at x."""
    studio.load_brush("round", 5, pigments, 1.0)
    studio.stroke("painting", [[x, 6, 0.9], [x, 122, 0.9]], 120, smooth=False)


def over_band(picture: Tensor, rows: slice = BAND) -> list[float]:
    return [float(picture[rows, x - 1 : x + 2].mean()) for x in COLUMNS]


def over_paper(picture: Tensor) -> list[float]:
    return [float(torch.cat([picture[rows, x - 1 : x + 2].flatten() for rows in PAPER_ROWS]).mean()) for x in COLUMNS]


def share_beneath(
    sheet: Sheet, pigments: tuple[int, ...], rows: slice, columns: slice, field: str = "underlying"
) -> float:
    """Share of the given pigments in a patch that lies beneath the top layer (beneath the middle one, for
    'lowest'). An engine that keeps no layers has nothing beneath."""
    layer = kept(sheet, field)
    if layer is None:
        return 0.0
    index = list(pigments)
    held = torch.minimum(layer, sheet.deposited)[index][:, rows, columns].sum()
    return float(held / sheet.deposited[index][:, rows, columns].sum().clamp(min=1e-9))


def white_coats(studio: Studio) -> Measurements:
    """Opaque white at four strengths in round-5 columns over a dried dark band, one coat and then two, each dried.

    For each column and coat the contrast C (the white over the band against the same white over paper) is found
    three ways: as the engine pictures it, as Kubelka-Munk composes the white over the paint beneath it (the paint
    beneath taken, per pigment, as the least of the deposit before and after the coat), and as one summed layer.
    The layering fraction says how far the engine has gone from the summed layer toward the composed one.
    """
    sheet = sheet_of(studio)
    dark_band(studio, DARK)
    studio.dry()

    def contrast(picture: Tensor) -> list[float]:
        return [band / paper for band, paper in zip(over_band(picture), over_paper(picture))]

    fractions, contrasts = [], []
    for _coat in (1, 2):
        before = sheet.deposited.clone()
        for x, strength in zip(COLUMNS, (1.5, 3.0, 4.5, 8.0)):
            column(studio, x, {"opaque_white": strength})
        studio.dry()
        pictured = contrast(value(sheet))
        summed = contrast(reference_value(sheet))
        layered = contrast(two_layer_value(sheet, before))
        for c_sim, c_sum, c_lay in zip(pictured, summed, layered):
            contrasts.append(c_sim)
            fractions.append((c_sim - c_sum) / (c_lay - c_sum) if abs(c_lay - c_sum) > 1e-6 else None)
    return {"layering_fraction": fractions, "contrast": contrasts}


def under_darkness(studio: Studio) -> Measurements:
    """Two coats of white 4.5 across bands of four darknesses: how much the white still shows the band beneath, as
    the slope of its value against the band's, pictured by the engine and by one summed layer."""
    sheet = sheet_of(studio)
    rows = (20, 48, 76, 104)
    for y, strength in zip(rows, (0.75, 1.5, 3.0, 6.0)):
        studio.load_brush("flat", 8, {"burnt_umber": strength * 2 / 3, "french_ultramarine": strength / 3}, 1.0)
        studio.stroke("painting", [[6, y, 0.9], [122, y, 0.9]], 120, smooth=False)
    studio.dry()
    bands = [float(value(sheet)[y - 2 : y + 3, 30:36].mean()) for y in rows]
    for _ in range(2):
        for x in (46, 98):
            column(studio, x, {"opaque_white": 4.5})
        studio.dry()

    def over_bands(picture: Tensor) -> list[float]:
        return [
            sum(float(picture[y - 2 : y + 3, x - 1 : x + 2].mean()) for x in (46, 98)) / 2 for y in rows
        ]  # fmt: skip

    pictured, summed = over_bands(value(sheet)), over_bands(reference_value(sheet))
    slope, summed_slope = least_squares_slope(bands, pictured), least_squares_slope(bands, summed)
    return {"bands": bands, "white_over_bands": pictured, "slope_ratio": slope / summed_slope}


ORDER_PAINTS = ("phthalo_green", "yellow_ochre", "cadmium_red", "opaque_white")
COMMUTING_PAINTS = ("phthalo_green", "french_ultramarine", "quinacridone_rose")


def order(paints: tuple[str, ...], dark_on_top: bool) -> Callable[[Studio], Measurements]:
    """Paint 3.0 in columns and a band of burnt umber 2.0, one dried before the other is laid over it: the value
    where they cross, as the engine pictures it and as Kubelka-Munk composes the later paint over the earlier."""

    def script(studio: Studio) -> Measurements:
        sheet = sheet_of(studio)

        def columns() -> None:
            for x, name in zip(COLUMNS, paints):
                column(studio, x, {name: 3.0})

        def band() -> None:
            dark_band(studio, {"burnt_umber": 2.0})

        first, second = (columns, band) if dark_on_top else (band, columns)
        first()
        studio.dry()
        beneath = sheet.deposited.clone()
        second()
        studio.dry()
        count = len(paints)
        return {
            "pictured": over_band(value(sheet))[:count],
            "summed": over_band(reference_value(sheet))[:count],
            "composed": over_band(two_layer_value(sheet, beneath))[:count],
        }

    return script


def glaze_over_white(studio: Studio) -> Measurements:
    """A glaze of phthalo green 0.8 in columns over a dried band of opaque white 4.5: the chroma of the glaze over
    the white against its chroma over bare paper (a glaze over white keeps its colour)."""
    sheet = sheet_of(studio)
    dark_band(studio, {"opaque_white": 4.5})
    studio.dry()
    for x in COLUMNS:
        column(studio, x, {"phthalo_green": 0.8})
    studio.dry()
    picture = render_view(sheet, "color")
    over_white = [float(chroma(picture[:, 52:64, x - 1 : x + 2]).mean()) for x in COLUMNS]
    over_paper_alone = [float(chroma(picture[:, 10:20, x - 1 : x + 2]).mean()) for x in COLUMNS]
    return {"chroma_ratio": [a / b for a, b in zip(over_white, over_paper_alone)]}


def set_time(studio: Studio) -> Measurements:
    """White 4.5 laid over a fresh dark band at four moments of its drying: while it shines, once its film has
    gone with the paper still damp, at the first look when it reads dry, and 300 s later.

    Paint laid before the band has set mixes with it; paint laid after lies over it.
    """
    sheet = sheet_of(studio)
    p = sheet.parameters
    dark_band(studio, DARK)
    moments = []

    def reading(x: int) -> dict[str, float]:
        return sheet.wetness_at(x, 58)

    def lay(x: int) -> None:
        wetness = reading(x)
        moments.append(
            {
                "clock": studio.clock,
                "film": wetness["film"],
                "paper": wetness["paper"],
                "set": wetness["film"] <= p.wet_threshold and wetness["paper"] <= p.damp_threshold,
            }
        )
        column(studio, x, {"opaque_white": 4.5})

    studio.wait(5.0)
    lay(COLUMNS[0])
    waited = 0.0
    while reading(COLUMNS[1])["film"] > p.wet_threshold and waited < 600:
        studio.wait(1.0)
        waited += 1.0
    lay(COLUMNS[1])
    while not (reading(COLUMNS[2])["film"] <= p.wet_threshold and reading(COLUMNS[2])["paper"] <= p.damp_threshold):
        if waited >= 1200:
            break
        studio.wait(1.0)
        waited += 1.0
    lay(COLUMNS[2])
    studio.wait(300.0)
    lay(COLUMNS[3])
    studio.dry()
    pictured, summed = over_band(value(sheet)), over_band(reference_value(sheet))
    shares = [share_beneath(sheet, DARK_PIGMENTS, BAND, slice(x - 1, x + 2)) for x in COLUMNS]
    unset = [index for index, moment in enumerate(moments) if not moment["set"]]
    settled = [index for index, moment in enumerate(moments) if moment["set"]]
    return {
        "moments": moments,
        "set_columns": settled,
        "dark_beneath_share": shares,
        "over_band": pictured,
        "unset_share_largest": max((shares[i] for i in unset), default=0.0),
        "unset_picture_error_largest": max((abs(pictured[i] - summed[i]) for i in unset), default=0.0),
        "set_share_least": min((shares[i] for i in settled), default=None),
    }


def fine_line(studio: Studio) -> Measurements:
    """A fine line of opaque white 4.5 from a rigger 1.3 over a dried dark wash, in one coat and in two."""
    sheet = sheet_of(studio)
    dark_band(studio, DARK)
    studio.dry()
    for lines in ((40, 88), (88,)):
        for x in lines:
            studio.load_brush("rigger", 1.3, {"opaque_white": 4.5}, 1.0)
            studio.stroke("painting", [[x, 30, 0.9], [x, 86, 0.9]], 120, smooth=False)
        studio.dry()
    picture = value(sheet)
    return {
        "one_coat_peak": float(picture[52:64, 36:45].amax(dim=1).mean()),
        "two_coats_peak": float(picture[52:64, 84:93].amax(dim=1).mean()),
    }


def rewet(studio: Studio) -> Measurements:
    """Dried white 6.0 over the dark band, wetted three times with clear water set on the sheet and dried, with
    ordinary lifting: how much of what the layering adds to the picture survives."""
    sheet = sheet_of(studio)
    dark_band(studio, DARK)
    studio.dry()
    for x in COLUMNS:
        column(studio, x, {"opaque_white": 6.0})
    studio.dry()
    rows = slice(52, 64)

    def mean_over_columns(picture: Tensor) -> float:
        return sum(over_band(picture, rows)) / len(COLUMNS)

    gain_before = mean_over_columns(value(sheet)) - mean_over_columns(reference_value(sheet))
    for _ in range(3):
        sheet.water[40:76, :] += 0.3
        studio.wait(2.0)
        studio.dry()
    gain_after = mean_over_columns(value(sheet)) - mean_over_columns(reference_value(sheet))
    white_in_lowest = max(share_beneath(sheet, (WHITE,), rows, slice(x - 1, x + 2), "lowest") for x in COLUMNS)
    return {
        "layered_gain_before": gain_before,
        "layered_gain_kept": gain_after / gain_before if abs(gain_before) > 1e-6 else None,
        "white_in_lowest_layer": white_in_lowest,
    }


def four_glazes(studio: Studio) -> Measurements:
    """Dark band, white columns, then a phthalo glaze and a cadmium red glaze, each dried: four layers.

    The reference keeps every layer: each is the paint added since the dry before it, the paint beneath each
    taken, per pigment, as the least of what lay there at every later dry.
    """
    sheet = sheet_of(studio)
    snapshots = []
    dark_band(studio, DARK)
    studio.dry()
    snapshots.append(sheet.deposited.clone())
    for x in COLUMNS:
        column(studio, x, {"opaque_white": 4.5})
    studio.dry()
    snapshots.append(sheet.deposited.clone())
    for glaze in ("phthalo_green", "cadmium_red"):
        studio.load_brush("flat", 10, {glaze: 0.8}, 1.0)
        studio.stroke("painting", [[6, 56, 0.9], [122, 56, 0.9]], 120, smooth=False)
        studio.dry()
        if glaze == "phthalo_green":
            snapshots.append(sheet.deposited.clone())
    paint = sheet.deposited + sheet.suspended
    floors, floor = [], paint
    for snapshot in reversed(snapshots):
        floor = torch.minimum(snapshot, floor)
        floors.append(floor)
    floors.reverse()
    layers, below = [], torch.zeros_like(paint)
    for top in [*floors, paint]:
        layers.append(top - below)
        below = top
    rows = slice(52, 60)
    pictured = over_band(value(sheet), rows)
    every_layer = over_band(composed_value(sheet, layers), rows)
    summed = over_band(reference_value(sheet), rows)
    return {
        "pictured": pictured,
        "every_layer_kept": every_layer,
        "one_summed_layer": summed,
        "error_to_every_layer": [abs(a - b) for a, b in zip(pictured, every_layer)],
        "nearer_every_layer": [abs(a - b) < abs(a - c) for a, b, c in zip(pictured, every_layer, summed)],
    }


def drybrush_white(studio: Studio) -> Measurements:
    """Opaque white 4.5 from a round 5, full and drained to 0.45, 0.25 and 0.12, over a dried dark band: wherever
    white lands on set paint, that paint should lie beneath it."""
    sheet = sheet_of(studio)
    dark_band(studio, DARK)
    studio.dry()
    for x, level in zip(COLUMNS, (1.0, 0.45, 0.25, 0.12)):
        studio.load_brush("round", 5, {"opaque_white": 4.5}, 1.0)
        if level < 1.0:
            studio.drain(level)
        studio.stroke("painting", [[x, 6, 0.9], [x, 122, 0.9]], 120, smooth=False)
    studio.dry()
    shares = [share_beneath(sheet, DARK_PIGMENTS, BAND, slice(x - 1, x + 2)) for x in COLUMNS]
    not_layered = 0
    for x in COLUMNS:
        columns = slice(x - 3, x + 4)
        white = sheet.deposited[WHITE, BAND, columns]
        dark = sheet.deposited[list(DARK_PIGMENTS)][:, BAND, columns].sum(0)
        underlying = kept(sheet, "underlying")
        if underlying is not None:
            held = torch.minimum(underlying, sheet.deposited)[list(DARK_PIGMENTS)][:, BAND, columns]
            share = held.sum(0) / dark.clamp(min=1e-9)
        else:
            share = torch.zeros_like(dark)
        not_layered += int((share[white > 0.05] < 0.5).sum())
    return {"dark_beneath_share": shares, "cells_not_layered": not_layered}


def chroma(rgb: Tensor) -> Tensor:
    """CIE 1976 chroma of RGB in [0, 1] with shape (3, ...), taken as linear sRGB against a white of (1, 1, 1)."""
    matrix = torch.tensor([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = torch.einsum("ij,j...->i...", matrix, rgb.cpu()) / matrix.sum(1).reshape(3, *([1] * (rgb.dim() - 1)))
    f = torch.where(xyz > 0.008856, xyz.clamp(min=1e-9) ** (1 / 3), 7.787 * xyz + 16 / 116)
    return ((500 * (f[0] - f[1])) ** 2 + (200 * (f[1] - f[2])) ** 2).sqrt()


# ------------------------------------------------------------------------------------------------ experiments: physics


def levelling_rates() -> Measurements:
    """Decay rate of a 5% cosine ripple (mode 8 across 128 px, wavelength 32 px) on uniform films over dry paper.

    For each depth a level sheet and a rippled sheet of the same paper are advanced together, and the ripple is
    their difference projected onto the cosine, so the paper's own relief cancels. Each rate is the least-squares
    slope of the log amplitude in 0.2 s steps until it has fallen by 0.15. Orchard (1962): at a fixed wavelength
    the rate of a no-slip film goes as the cube of its depth.
    """
    depths = (0.2, 0.45, 0.9, 1.0, 1.3)
    rows, width = 64, 128
    sheets = []
    shape = torch.empty(0)
    for depth in depths:
        level = new_sheet(rows, width, adjust=still_water)
        rippled = new_sheet(rows, width, adjust=still_water)
        xs = torch.arange(width, device=level.water.device, dtype=torch.float32)
        shape = torch.cos(math.pi * 8 * (xs + 0.5) / width).expand(rows, width)
        level.water.fill_(depth)
        rippled.water.copy_(depth * (1.0 + 0.05 * shape))
        sheets += [level, rippled]
    batch = SheetBatch(sheets)
    inner = (slice(24, 40), slice(24, width - 24))

    def amplitude(index: int) -> float:
        difference = (sheets[2 * index + 1].water - sheets[2 * index].water)[inner]
        return float((difference * shape[inner]).sum() / (shape[inner] ** 2).sum())

    records = [([0.0], [math.log(amplitude(index))]) for index in range(len(depths))]
    running = set(range(len(depths)))
    elapsed = 0.0
    while running and elapsed < 60.0 - 1e-9:
        batch.advance(0.2)
        elapsed += 0.2
        for index in sorted(running):
            times, logs = records[index]
            times.append(elapsed)
            logs.append(math.log(amplitude(index)))
            if logs[-1] < logs[0] - 0.15:
                running.discard(index)
    rates = [-least_squares_slope(times, logs) for times, logs in records]
    xs, ys = [math.log(d) for d in depths[:3]], [math.log(r) for r in rates[:3]]
    return {
        "depths": list(depths),
        "rates": rates,
        "exponent": least_squares_slope(xs, ys),
        "local_exponents": [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(2)],
        "rate_full_wash": rates[3],
        "rate_mobility_limit": rates[4],
        "finite": all(bool(torch.isfinite(sheet.water).all()) for sheet in sheets),
    }


def front_power_fit(times: list[float], fronts: list[float]) -> tuple[float, float]:
    """The power n for which front ** n is most nearly a straight line in time, and that line's slope.

    n is searched over [1.5, 7] in steps of 0.001; the fit with the least relative residual (the norm of the
    residual over the norm of front ** n) wins.
    """
    best = (math.inf, 0.0, 0.0)
    for step in range(5501):
        power = 1.5 + 0.001 * step
        ys = [front**power for front in fronts]
        slope = least_squares_slope(times, ys)
        intercept = sum(ys) / len(ys) - slope * sum(times) / len(times)
        residual = math.sqrt(sum((y - intercept - slope * t) ** 2 for t, y in zip(times, ys)))
        relative = residual / math.sqrt(sum(y * y for y in ys))
        if relative < best[0]:
            best = (relative, power, slope)
    return best[1], best[2]


def slope_runs() -> Measurements:
    """A band of water 1.0 deep runs down a tilted sheet over a thin standing film; the same with half the band.

    Huppert (1982): a two-dimensional viscous current on a slope advances as t^(1/3) and as A^(2/3) of its
    cross-section when its flux goes as the cube of its depth, and as t^(1/2) and A^(1/2) when it goes as the square.
    """
    rows, width, top, background = 320, 32, 16, 0.02
    times = (8.0, 16.0, 32.0, 64.0, 96.0)
    sheets = []
    for band_rows in (16, 8):
        sheet = new_sheet(rows, width, adjust=still_water)
        sheet.water.fill_(background)
        sheet.water[top : top + band_rows, :] += 1.0
        sheet.tilt = (0.0, 0.2)
        sheets.append(sheet)
    batch = SheetBatch(sheets)

    def front(sheet: Sheet) -> float:
        excess = (sheet.water[:, 8 : width - 8] - background).mean(dim=1).cpu()
        threshold = 0.1
        last = int((excess > threshold).nonzero().max())
        above, below = float(excess[last]), float(excess[last + 1])
        return last + (above - threshold) / (above - below) - top

    fronts: list[list[float]] = [[], []]
    elapsed = 0.0
    for target in times:
        batch.advance(target - elapsed)
        elapsed = target
        for record, sheet in zip(fronts, sheets):
            record.append(front(sheet))
    power, rate = front_power_fit(list(times), fronts[0])
    half_rate = least_squares_slope(list(times), [x**power for x in fronts[1]])
    late = least_squares_slope([math.log(t) for t in times[2:]], [math.log(x) for x in fronts[0][2:]])
    return {
        "fronts": fronts[0],
        "half_band_fronts": fronts[1],
        "time_exponent": 1.0 / power,
        "volume_exponent": math.log(rate / half_rate) / (power * math.log(2.0)),
        "late_time_exponent": late,
        "unsound_cells": sum(unsound_cells(sheet) for sheet in sheets),
    }


def thick_paint_checkerboard() -> Measurements:
    """Thick wet paint of two colours left 8 s: whether it settles into alternating light and dark cells."""
    sheet = new_sheet()
    sheet.water[24:104, 24:104] = 0.9
    sheet.suspended[RED, 24:104, 24:104] = 1.8
    sheet.suspended[BLUE, 24:104, 24:64] = 1.2
    sheet._used.update((RED, BLUE))
    sheet.advance(8.0)
    return {"checkerboard": checkerboard((sheet.suspended + sheet.deposited).sum(0)[34:94, 34:94])}


def deep_water_on_damp_paper() -> Measurements:
    """Deep water on fully damp paper, left 10 s with nothing drying: the corner of the explicit stability bound,
    where the film is at the mobility limit and wicking is strongest."""
    sheet = new_sheet(adjust=still_water)
    sheet.saturation.copy_(sheet.capacity)
    sheet.water.fill_(0.6)
    sheet.water[40:88, 40:88] = 2.0
    noise = torch.Generator(device="cpu").manual_seed(1)
    sheet.water += 0.02 * torch.rand(sheet.water.shape, generator=noise).to(sheet.water.device)
    total = float(sheet.water.sum())
    for _ in range(10):
        sheet.advance(1.0)
    water = sheet.water
    laplacian = water[1:-1, 1:-1] * 4 - water[:-2, 1:-1] - water[2:, 1:-1] - water[1:-1, :-2] - water[1:-1, 2:]
    return {
        "finite": bool(torch.isfinite(water).all()),
        "water_error": abs(float(water.sum()) - total) / total,
        "roughness": float(laplacian.abs().mean()),
        "unsound_cells": unsound_cells(sheet),
    }


def thin_film_on_damp_paper() -> Measurements:
    """A thin noisy film on fully damp paper, left 10 s: the stiffest corner of the explicit scheme (wicking times
    the pull of wetted paper)."""
    out: Measurements = {}
    unsound = 0
    for film in (0.03, 0.08):
        sheet = new_sheet(adjust=still_water)
        sheet.saturation.copy_(sheet.capacity)
        noise = torch.Generator(device="cpu").manual_seed(2)
        sheet.water.copy_((film * (1 + 0.3 * (torch.rand(SIZE, SIZE, generator=noise) - 0.5))).to(sheet.water.device))
        total, deepest = float(sheet.water.sum()), float(sheet.water.max())
        sheet.advance(10.0)
        water = sheet.water
        out[f"checkerboard_{film:g}"] = checkerboard(water)
        out[f"deepest_over_start_{film:g}"] = float(water.max()) / deepest
        out[f"water_error_{film:g}"] = abs(float(water.sum()) - total) / total
        out[f"finite_{film:g}"] = bool(torch.isfinite(water).all())
        unsound += unsound_cells(sheet)
    out["unsound_cells"] = unsound
    return out


def puddle_drains() -> Measurements:
    """A deep puddle of strong paint draining into a thin film for 5 s: pigment on the sheet."""
    studio = new_studio()
    sheet = sheet_of(studio)
    sheet.water[30:98, 30:98] = 0.05
    sheet.water[58:70, 58:70] = 10.0
    sheet.suspended[RED, 58:70, 58:70] = 60.0
    sheet._used.add(RED)
    before = float((sheet.suspended + sheet.deposited).sum())
    studio.wait(5)
    after = float((sheet.suspended + sheet.deposited).sum())
    return {"pigment_change": abs(after - before) / before, "unsound_cells": unsound_cells(sheet)}


def flow_conserves_water() -> Measurements:
    """Flow alone, with nothing evaporating or soaking in, for 5 s after a mop wash: the water on the sheet.
    Once with pale paint and once with strong paint, which thickens the film."""
    out: Measurements = {}
    for strength in (0.05, 4.0):
        studio = new_studio(adjust=nothing_soaks_away)
        sheet = sheet_of(studio)
        lay_rows(studio, "mop", 16, {"french_ultramarine": strength})
        before = float(sheet.water.sum())
        studio.wait(5)
        out[f"water_change_{strength:g}"] = abs(float(sheet.water.sum()) - before) / before
    return out


def gum_levelling() -> Measurements:
    """Decay of a 15% ripple on a film of depth d over dry paper, with gum dissolved in it at a share c by weight,
    over 0.3 s, with evaporation, absorption and the surface stream off. The effective relative viscosity is the
    rate without gum over the rate with it; in thin-film flow it should not depend on depth or wavelength."""
    cases = [(depth, wavelength) for depth in (0.3, 0.6) for wavelength in (16.0, 32.0)]
    shares = (0.0, 0.05, 0.10, 0.20)
    sheets, shapes = [], []
    inside, band = (slice(32, 96), slice(32, 96)), (slice(48, 80), slice(40, 88))
    gum_present = False
    for depth, wavelength in cases:
        for share in shares:
            sheet = new_sheet(adjust=lambda p: dataclasses.replace(still_water(p), marangoni=0.0))
            ripple = 0.15 * depth * torch.cos(2 * torch.pi * sheet._xs / wavelength)
            sheet.water[inside] = depth + ripple[inside]
            gum = kept(sheet, "gum")
            if gum is not None:
                gum_present = True
                gum[inside] = share * sheet.water[inside]
            sheets.append(sheet)
            shapes.append(torch.cos(2 * torch.pi * sheet._xs[band] / wavelength))

    def amplitude(sheet: Sheet, shape: Tensor) -> float:
        film = sheet.water[band]
        return float(((film - film.mean()) * shape).sum() / (shape * shape).sum())

    starts = [amplitude(sheet, shape) for sheet, shape in zip(sheets, shapes)]
    SheetBatch(sheets).advance(0.3)
    rates = [-math.log(amplitude(sheet, shape) / start) / 0.3 for sheet, shape, start in zip(sheets, shapes, starts)]
    out: Measurements = {"gum_present": gum_present}
    for column, share in enumerate(shares[1:], start=1):
        ratios = [rates[case * len(shares)] / rates[case * len(shares) + column] for case in range(len(cases))]
        out[f"viscosity_{share:g}"] = ratios
        out[f"viscosity_spread_{share:g}"] = max(ratios) / min(ratios)
    return out


# ------------------------------------------------------------------------------------------------ experiments: invariants


def charged_wash(studio: Studio) -> None:
    """The mop wash with a stroke of strong cadmium red drawn into it, left 6 s."""
    lay_rows(studio, "mop", 16, {"french_ultramarine": 0.6})
    studio.load_brush("round", 5, {"cadmium_red": 4.0}, 0.8)
    studio.stroke("painting", [[34, 64, 0.8], [94, 64, 0.8]], 110, smooth=False)
    studio.wait(6)


def pool_and_dab(name: str, y: int) -> Callable[[Studio], None]:
    """A wet band with a strong dab dropped into it, from tests/test_together.py."""

    def script(studio: Studio) -> None:
        studio.load_brush("mop", 14, {name: 0.05}, 1.0)
        studio.stroke("painting", [[16, y], [80, y]], 120, smooth=False)
        studio.wait(2)
        studio.load_brush("round", 8, {name: 6.0}, 0.6)
        studio.stroke("painting", [[48, y]], 100, smooth=False, dwell=0.5)
        studio.wait(4)

    return script


def paint_alone(
    script: Callable[[Studio], None], seed: int, size: int = SIZE, device: torch.device | None = None
) -> Sheet:
    studio = new_studio(seed, size, device)
    script(studio)
    return sheet_of(studio)


def paint_batched(script: Callable[[Studio], None], seeds: tuple[int, ...], size: int = SIZE) -> list[Sheet]:
    sheets = [new_sheet(size, size, seed) for seed in seeds]
    clock = SharedClock(SheetBatch(sheets))
    studios = [Studio({"painting": sheet}, list(PALETTE), shared_clock=clock) for sheet in sheets]
    clock.run([lambda studio=studio: script(studio) for studio in studios])
    return sheets


def determinism_and_batching() -> Measurements:
    """The charged wash painted twice alone on one device, and on two sheets of a batch against each alone; the
    pool and dab of tests/test_together.py the same way at 96 px, and twice alone on the CPU."""
    first, second, other = paint_alone(charged_wash, 3), paint_alone(charged_wash, 3), paint_alone(charged_wash, 4)
    batched = paint_batched(charged_wash, (3, 4))
    pool = [pool_and_dab("cadmium_red", 30), pool_and_dab("french_ultramarine", 62)]
    pooled = [paint_alone(script, seed, 96) for script, seed in zip(pool, (1, 2))]
    together = [new_sheet(96, 96, seed) for seed in (1, 2)]
    clock = SharedClock(SheetBatch(together))
    studios = [Studio({"painting": sheet}, list(PALETTE), shared_clock=clock) for sheet in together]
    clock.run([lambda script=script, studio=studio: script(studio) for script, studio in zip(pool, studios)])
    relative = 0.0
    for alone, sheet in zip(pooled, together):
        for name in ("water", "suspended", "deposited", "gum"):
            expected, found = kept(alone, name), kept(sheet, name)
            if expected is not None and found is not None:
                difference = float((found - expected).abs().mean())
                relative = max(relative, difference / max(float(expected.abs().mean()), 1e-12))
    cpu = torch.device("cpu")
    on_cpu = [paint_alone(pool[0], 1, 96, cpu) for _ in range(2)]
    return {
        "repeat_difference": state_difference(first, second),
        "batched_difference": max(state_difference(batched[0], first), state_difference(batched[1], other)),
        "pool_batched_relative_difference": relative,
        "cpu_repeat_difference": state_difference(on_cpu[0], on_cpu[1]),
        "unsound_cells": sum(unsound_cells(sheet) for sheet in (first, second, other, *batched, *pooled, *together)),
    }


class Interrupted(Exception):
    """Raised to stop a pass part-way through a wait, as a command killed after a save would."""


def session_resume() -> Measurements:
    """White laid over set dark paint and left wet, in a session cut short part-way through its wait and reopened,
    against the same session run without a break; and a sheet's saved state loaded into a fresh sheet."""
    import watercolor.session as session_module
    from watercolor.session import Configuration, Session

    first_pass = [
        {"action": "load", "brush": "flat", "size": 8, "pigments": {"burnt_umber": 3.0}, "water": 1.0},
        {"action": "stroke", "path": [[8, 32], [56, 32]]},
        {"action": "dry"},
    ]
    second_pass = [
        {"action": "load", "brush": "round", "size": 4, "pigments": {"opaque_white": 4.5}, "water": 1.0},
        {"action": "stroke", "path": [[32, 8], [32, 56]]},
        {"action": "wait", "seconds": 12},
    ]
    configuration = Configuration(
        prompt="calibration", size=64, seed=2, palette=["burnt_umber", "opaque_white"],
        stroke_budget=10, scrap_allowed=False, pencil_allowed=False,
    )  # fmt: skip
    saved_interval = session_module.SAVE_INTERVAL
    session_module.SAVE_INTERVAL = 0.0  # save after every span of a wait, so that a break loses nothing
    try:
        with tempfile.TemporaryDirectory() as work:
            whole = Session.create(Path(work) / "whole", configuration)
            whole.paint(first_pass)
            whole.paint(second_pass)
            broken = Session.create(Path(work) / "broken", configuration)
            broken.paint(first_pass)
            spans = 0

            def break_after_saving() -> None:
                nonlocal spans
                broken._save_if_due()
                spans += 1
                if spans == 5:
                    raise Interrupted

            broken.studio.while_waiting = break_after_saving
            try:
                broken.paint(second_pass)
            except Interrupted:
                pass
            reopened = Session(broken.directory)
            resumed_from = reopened.paint(second_pass)
            a, b = whole.studio.sheets["painting"], reopened.studio.sheets["painting"]
            session_difference = state_difference(a, b)
            clocks_equal = abs(whole.studio.clock - reopened.studio.clock) < 1e-9
            # The sheet itself: its state saved and loaded into a fresh sheet, and both carried on alike.
            fresh = new_sheet(64, 64, 2, palette=("burnt_umber", "opaque_white"))
            buffer = io.BytesIO()
            torch.save(a.state(), buffer)
            buffer.seek(0)
            fresh.load_state(torch.load(buffer, weights_only=True))
            fresh.tilt = a.tilt
            loaded_difference = state_difference(a, fresh)
            a.advance(3.0)
            fresh.advance(3.0)
            continued_difference = state_difference(a, fresh)
    finally:
        session_module.SAVE_INTERVAL = saved_interval
    return {
        "resumed_from_action": resumed_from,
        "session_difference": session_difference,
        "clocks_equal": clocks_equal,
        "loaded_difference": loaded_difference,
        "continued_difference": continued_difference,
    }


def layered_scene(studio: Studio) -> None:
    """A burnt umber band, a white line over it, and a phthalo glaze across both, on a 48-pixel sheet."""
    studio.load_brush("flat", 8, {"burnt_umber": 3.0}, 1.0)
    for y in (18, 24, 30):
        studio.stroke("painting", [[4, y], [44, y]], 120, smooth=False)
    studio.dry()
    studio.load_brush("round", 4, {"opaque_white": 4.5}, 1.0)
    studio.stroke("painting", [[24, 4], [24, 44]], 120, smooth=False)
    studio.wait(3.0)
    studio.dry()
    studio.load_brush("flat", 6, {"phthalo_green": 0.6}, 1.0)
    studio.stroke("painting", [[4, 27], [44, 27]], 120, smooth=False)
    studio.wait(4.0)


SCENE_PALETTE = ("burnt_umber", "opaque_white", "phthalo_green")


def advance_conserves_pigment() -> Measurements:
    """The layered scene, part dried, advanced 30 s with no brush: pigment on the sheet, in double precision."""
    studio = new_studio(5, 48, palette=SCENE_PALETTE)
    layered_scene(studio)
    sheet = sheet_of(studio)

    def total() -> float:
        return float((sheet.suspended + sheet.deposited + sheet.mask_pigment).double().sum())

    before = total()
    sheet.advance(30.0)
    return {"pigment_change": abs(total() - before) / before, "unsound_cells": unsound_cells(sheet)}


def flow_onto_set_paint() -> Measurements:
    """A deep pool set beside dried paint, so that the flow and not a brush brings water onto it. In every cell of
    set paint the water reaches, the old paint should lie beneath whatever the water leaves, or have been lifted."""
    studio = new_studio(5, 48, palette=SCENE_PALETTE)
    layered_scene(studio)
    studio.dry()
    sheet = sheet_of(studio)
    set_cells = sheet.water <= 0
    before = sheet.deposited.clone()
    sheet.water[34:46, 18:30] = 1.6
    sheet._used.update({0, 1})
    sheet.advance(4.0)
    reached = set_cells & (sheet.water > 0) & (before.sum(0) > 0.01)
    reached[34:46, 18:30] = False
    underlying = kept(sheet, "underlying")
    if underlying is not None:
        beneath = torch.minimum(underlying, before).sum(0)
    else:
        beneath = torch.zeros_like(sheet.water)
    lifted = (before - sheet.deposited).clamp(min=0).sum(0)
    share = (beneath + lifted) / before.sum(0).clamp(min=1e-9)
    return {"cells_reached": int(reached.sum()), "least_share": float(share[reached].min()) if reached.any() else None}


def deep_puddle_scrubbed() -> Measurements:
    """A deep puddle of strong rose (gum at the strength where it sets, if the engine keeps gum), scrubbed with a
    clean brush while wet, then dried and rewetted: every value of the state finite and non-negative."""
    studio = new_studio()
    sheet = sheet_of(studio)
    sheet.water[30:98, 30:98] = 0.05
    sheet.water[58:70, 58:70] = 6.0
    sheet.suspended[ROSE, 58:70, 58:70] = 40.0
    gum = kept(sheet, "gum")
    if gum is not None:
        simulation = importlib.import_module("watercolor.simulation")
        gum[58:70, 58:70] = simulation.GUM_SET * 6.0
    sheet._used.add(ROSE)
    studio.wait(30)

    def scrub() -> None:
        studio.load_brush("round", 8, {}, 1.0)
        studio.stroke("painting", [[40, 64], [90, 64]], 80, smooth=False)
        studio.wait(5)

    scrub()
    wet = unsound_cells(sheet)
    studio.dry()
    scrub()
    return {"unsound_cells_wet": wet, "unsound_cells_rewetted": unsound_cells(sheet)}


def gum_bookkeeping() -> Measurements:
    """Gum neither appears nor vanishes in the flow, is laid in proportion to the pigment of the paint, and stays
    in the paper under masking fluid. An engine that keeps no gum has nothing to measure."""
    probe = new_sheet(8, 8)
    if not has_gum(probe):
        return {"gum_present": False, "advance_change": None, "wait_change": None, "laid_over_pigment": None,
                "mask_change": None}  # fmt: skip
    simulation = importlib.import_module("watercolor.simulation")
    gum_per_strength = simulation.GUM_PER_STRENGTH

    def gum_total(sheet: Sheet) -> float:
        gum = kept(sheet, "gum")
        assert gum is not None
        return float(gum.double().sum())

    studio = new_studio()
    sheet = sheet_of(studio)
    for y in (48, 64, 80):
        studio.load_brush("round", 10, {"quinacridone_rose": 3.0}, 1.0)
        studio.stroke("painting", [[24, y], [104, y]], 120, smooth=False)
    before = gum_total(sheet)
    sheet.advance(20.0)
    advance_change = abs(gum_total(sheet) - before) / before

    studio = new_studio(adjust=nothing_soaks_away)
    sheet = sheet_of(studio)
    lay_rows(studio, "mop", 16, {"french_ultramarine": 4.0})
    before = gum_total(sheet)
    studio.wait(5)
    wait_change = abs(gum_total(sheet) - before) / before

    studio = new_studio()
    sheet = sheet_of(studio)
    studio.load_brush("round", 10, {"quinacridone_rose": 2.0, "french_ultramarine": 1.0}, 1.0)
    studio.stroke("painting", [[24, 64], [104, 64]], 120, smooth=False)
    laid = gum_total(sheet) / (gum_per_strength * float((sheet.suspended + sheet.deposited).sum()))

    studio = new_studio()
    sheet = sheet_of(studio)
    lay_patch(studio, "quinacridone_rose", 2.0)
    studio.dry()
    before = gum_total(sheet)
    studio.mask("painting", [[20, 64], [108, 64]], 8.0)
    sheet.parameters = dataclasses.replace(sheet.parameters, evaporation_rate=0.0, absorption_rate=0.0)
    lay_rows(studio, "mop", 16, {})
    studio.wait(5)
    studio.unmask("painting")
    mask_change = abs(gum_total(sheet) - before) / before
    return {"gum_present": True, "advance_change": advance_change, "wait_change": wait_change,
            "laid_over_pigment": laid, "mask_change": mask_change}  # fmt: skip


def old_state_loads() -> Measurements:
    """A sheet's state saved without the gum field (as 0.8.0 saves it) loads into a fresh sheet, which rebuilds its
    gum from its pigment if it keeps gum, and painting carries on with every field finite."""
    painted = paint_alone(pool_and_dab("quinacridone_rose", 40), 3, 96)
    state = {name: field for name, field in painted.state().items() if name != "gum"}
    fresh = new_sheet(96, 96, 4)
    rebuilt: bool = True
    gum = kept(fresh, "gum")
    if gum is not None:
        gum.fill_(1.0)
    fresh.load_state(state)
    if gum is not None:
        simulation = importlib.import_module("watercolor.simulation")
        expected = simulation.GUM_PER_STRENGTH * float((fresh.suspended + fresh.deposited).sum())
        rebuilt = abs(float(gum.sum()) - expected) <= 1e-6 * expected
    studio = Studio({"painting": fresh}, list(PALETTE))
    studio.load_brush("round", 6, {"quinacridone_rose": 1.0}, 1.0)
    studio.stroke("painting", [[20, 20], [60, 20]], 120, smooth=False)
    studio.wait(3)
    finite = all(bool(torch.isfinite(getattr(fresh, name)).all()) for name in fresh.STATE_FIELDS)
    return {"gum_rebuilt": rebuilt, "continues_finite": finite}


def rewet_without_moving_paint() -> Measurements:
    """Dried white over a dried dark band, wetted twice with water set on the sheet with lifting switched off, so
    that no pigment moves: the picture of paint that has not moved must not change."""
    studio = new_studio()
    sheet = sheet_of(studio)
    dark_band(studio, DARK)
    studio.dry()
    for x in COLUMNS:
        column(studio, x, {"opaque_white": 6.0})
    studio.dry()
    before = over_band(value(sheet), slice(52, 64))
    deposited = sheet.deposited.clone()
    sheet.parameters = dataclasses.replace(sheet.parameters, resolubility=0.0)
    change = 0.0
    for _ in range(2):
        sheet.water[40:76, :] += 0.3
        studio.wait(2.0)
        studio.dry()
        after = over_band(value(sheet), slice(52, 64))
        change = max(change, max(abs(a - b) for a, b in zip(after, before)))
    return {"value_change": change, "deposit_moved": float((sheet.deposited - deposited).abs().max())}


def non_staining_unchanged() -> Measurements:
    """Non-staining paint (ultramarine and cerulean) through the pool and dab, a drained-brush lift and drying, on
    the CPU with the 0.8.0 engine and the engine under test in one process: the largest relative difference of any
    state field the two share, other than gum."""
    cpu = torch.device("cpu")
    reference = {name: reference_module(name) for name in ("paper", "pigments", "simulation", "studio")}

    def paint(package: dict[str, ModuleType] | None, name: str) -> dict[str, Tensor]:
        palette = ["french_ultramarine", "cerulean_blue"]
        if package is None:
            sheet = new_sheet(96, 96, 3, cpu, tuple(palette))
            studio = Studio({"painting": sheet}, palette)
        else:
            pigments = package["pigments"].PIGMENTS
            paper = package["paper"].generate_paper(96, 96, 3, cpu)
            sheet = package["simulation"].Sheet(paper, [pigments[p] for p in palette])
            studio = package["studio"].Studio({"painting": sheet}, palette)
        pool_and_dab(name, 48)(studio)
        studio.load_brush("round", 3, {}, 1.0)
        studio.drain(0.2)
        studio.stroke("painting", [[48, 28, 0.8], [48, 68, 0.8]], 120, smooth=False)
        studio.dry()
        return {field: getattr(sheet, field).clone() for field in sheet.STATE_FIELDS}

    worst = 0.0
    for name in ("french_ultramarine", "cerulean_blue"):
        old, new = paint(reference, name), paint(None, name)
        for field, expected in old.items():
            if field == "gum" or field not in new:
                continue
            scale = max(float(expected.abs().max()), 1e-12)
            worst = max(worst, float((new[field] - expected).abs().max()) / scale)
    return {"largest_relative_difference": worst}


# ------------------------------------------------------------------------------------------------ experiments: compatibility

BEGIN_WITH_REFERENCE = """
import json, sys
from pathlib import Path
import torch
from watercolor.rendering import render_view
from watercolor.session import Configuration, Session

work = Path(sys.argv[1])
wet = Session.create(work / "wet_wash", Configuration(prompt="calibration", size=128, seed=3,
    palette=["french_ultramarine", "cadmium_red"], stroke_budget=20, scrap_allowed=False, pencil_allowed=False))
wet.paint([{"action": "load", "brush": "mop", "size": 14, "pigments": {"french_ultramarine": 0.6}, "water": 1.0},
           {"action": "stroke", "path": [[20, 40], [108, 40]]}, {"action": "stroke", "path": [[20, 60], [108, 60]]}])
stain = Session.create(work / "rose_stroke", Configuration(prompt="calibration", size=64, seed=1,
    palette=["quinacridone_rose", "french_ultramarine"], stroke_budget=10, scrap_allowed=False, pencil_allowed=False))
stain.paint([{"action": "load", "brush": "round", "size": 6, "pigments": {"quinacridone_rose": 1.0}, "water": 1.0},
             {"action": "stroke", "path": [[10, 32], [54, 32]]}, {"action": "wait", "seconds": 2}])
dried = Session.create(work / "dried_umber", Configuration(prompt="calibration", size=64, seed=2,
    palette=["burnt_umber", "opaque_white"], stroke_budget=10, scrap_allowed=False, pencil_allowed=True))
dried.paint([{"action": "load", "brush": "flat", "size": 8, "pigments": {"burnt_umber": 3.0}, "water": 1.0},
             {"action": "stroke", "path": [[8, 32], [56, 32]]}, {"action": "dry"}])
torch.save(render_view(dried.studio.sheets["painting"], "value")[0].cpu(), work / "dried_umber_value.pt")
"""


def paintings_begun_with_reference() -> Measurements:
    """Three paintings begun and saved by the 0.8.0 rig, opened and carried on by the engine under test: a wet wash
    left wet, a rose stroke, and a dried umber stroke with white then laid over it."""
    from watercolor.session import Session

    out: Measurements = {}
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        subprocess.run(
            [sys.executable, "-c", BEGIN_WITH_REFERENCE, str(work)],
            check=True,
            capture_output=True,
            env=os.environ | {"PYTHONPATH": str(reference_source())},
        )
        # A wet wash: the log verifies, the totals are those saved, and it carries on with sound fields.
        saved = torch.load(work / "wet_wash" / "state.pt", weights_only=True)["sheets"]["painting"]
        session = Session(work / "wet_wash")
        sheet = session.studio.sheets["painting"]
        out["wet_water_equal"] = float(sheet.water.sum()) == float(saved["water"].to(sheet.water.device).sum())
        pigment = saved["suspended"] + saved["deposited"]
        out["wet_pigment_equal"] = float((sheet.suspended + sheet.deposited).sum()) == float(pigment.sum())
        session.paint(
            [
                {"action": "load", "brush": "round", "size": 5, "pigments": {"cadmium_red": 4.0}, "water": 0.8},
                {"action": "stroke", "path": [[30, 50, 0.8], [98, 50, 0.8]]},
                {"action": "wait", "seconds": 20},
            ]
        )
        out["wet_unsound_cells"] = unsound_cells(sheet)
        # A rose stroke: a further pass, and the painting reopens with both strokes counted.
        session = Session(work / "rose_stroke")
        session.paint([{"action": "stroke", "path": [[10, 40], [54, 40]]}, {"action": "wait", "seconds": 2}])
        out["rose_strokes_counted"] = Session(work / "rose_stroke").strokes_used
        # A dried umber stroke: it looks exactly as 0.8.0 saved it, holds no layers yet, and white laid over it
        # shows lighter than the umber.
        session = Session(work / "dried_umber")
        sheet = session.studio.sheets["painting"]
        saved_value = torch.load(work / "dried_umber_value.pt", weights_only=True)
        out["dried_value_difference"] = float((value(sheet).cpu() - saved_value).abs().max())
        out["dried_layer_total"] = sum(
            float(layer.sum()) for name in LAYER_FIELDS if (layer := kept(sheet, name)) is not None
        )
        session.paint(
            [
                {"action": "load", "brush": "round", "size": 4, "pigments": {"opaque_white": 4.5}, "water": 1.0},
                {"action": "stroke", "path": [[32, 8], [32, 56]]},
                {"action": "dry"},
            ]
        )
        reopened = Session(work / "dried_umber")
        sheet = reopened.studio.sheets["painting"]
        picture = value(sheet)
        out["white_over_umber"] = float(picture[30:35, 31:34].mean())
        out["umber_alone"] = float(picture[30:35, 12:20].mean())
        out["white_gain"] = out["white_over_umber"] - out["umber_alone"]
        out["dried_unsound_cells"] = unsound_cells(sheet)
        saved_fields = torch.load(work / "dried_umber" / "state.pt", weights_only=True)["sheets"]["painting"]
        out["saved_fields_complete"] = all(name in saved_fields for name in sheet.STATE_FIELDS)
    return out


REFERENCE_PASSES = (
    [{"action": "load", "brush": "round", "size": 8, "pigments": {"cadmium_red": 1.0}, "water": 1.0},
     {"action": "stroke", "path": [[20, 30], [70, 30]]}, {"action": "wait", "seconds": 4}],
    [{"action": "load", "brush": "comber", "size": 8, "pigments": {}, "water": 0.5}, {"action": "dry"}],
    [{"action": "load", "brush": "round", "size": 8, "pigments": {"cadmium_red": 9.0}, "water": 1.0}],
    [{"action": "load", "brush": "teapot", "size": 8, "pigments": {}, "water": 1.0}],
    [{"action": "stroke", "path": [[20, 30], [70, 30]]}],
    [{"action": "mask", "path": [[20, 30, 0.5], [70, 30]], "radius": 4}, {"action": "unmask"}],
    [{"action": "mask", "path": [[20, 30, 1.5]], "radius": 4}],
    [{"action": "tilt", "x": 0.1, "y": -0.2}, {"action": "blot", "path": [[20, 20]], "radius": 6}],
    [{"action": "tilt", "x": 0.5, "y": 0.0}],
    [{"action": "wait", "seconds": 10, "film": 0.1, "at": [10, 10]}],
    [{"action": "wait", "seconds": 0}],
    [{"action": "pencil", "path": [[10, 10], [40, 40]]}, {"action": "erase", "path": [[10, 10]], "radius": 3}],
    [{"action": "paint"}],
)  # fmt: skip


def vocabulary() -> Measurements:
    """What a painter, a script or a saved painting relies on, against 0.8.0: the session, studio, brush and command
    files, the actions a pass may hold and how they are checked, the command-line arguments, the state fields and
    the names of the simulation parameters."""
    from watercolor import cli, session

    source = reference_source() / "watercolor"
    engine_source = Path(importlib.import_module("watercolor").__file__ or "").parent
    files = ("session.py", "cli.py", "studio.py", "brushes.py")
    changed = [name for name in files if (source / name).read_bytes() != (engine_source / name).read_bytes()]
    old_session, old_cli = reference_module("session"), reference_module("cli")
    old_simulation = reference_module("simulation")
    actions_equal = all(
        getattr(old_session, name) == getattr(session, name)
        for name in ("TOUCHING_ACTIONS", "MASKING_ACTIONS", "SHEET_ACTIONS")
    )

    def verdicts(module: ModuleType, configuration_type: type) -> list[str]:
        out = []
        with tempfile.TemporaryDirectory() as work:
            configuration = configuration_type(
                prompt="calibration", size=128, seed=1, palette=["cadmium_red"], stroke_budget=5,
                scrap_allowed=False, pencil_allowed=True,
            )  # fmt: skip
            painting = module.Session.create(Path(work) / "painting", configuration)
            for actions in REFERENCE_PASSES:
                try:
                    painting._validate(actions)
                    out.append("accepted")
                except Exception as refusal:  # noqa: BLE001 - the kind of refusal is what is compared
                    out.append(type(refusal).__name__)
        return out

    validation_equal = verdicts(old_session, old_session.Configuration) == verdicts(session, session.Configuration)

    def arguments(parser) -> dict[str, list[tuple[str, ...]]]:
        commands = next(action for action in parser._actions if action.dest == "command")
        return {
            name: sorted((*argument.option_strings, argument.dest) for argument in command._actions)
            for name, command in commands.choices.items()
        }

    old_fields = tuple(old_simulation.Sheet.STATE_FIELDS)
    new_fields = [name for name in Sheet.STATE_FIELDS if name not in old_fields]
    parameter_names = [field.name for field in dataclasses.fields(SimulationParameters)]
    old_parameter_names = [field.name for field in dataclasses.fields(old_simulation.SimulationParameters)]
    return {
        "changed_files": changed,
        "actions_equal": actions_equal,
        "validation_equal": validation_equal,
        "arguments_equal": arguments(old_cli._parser()) == arguments(cli._parser()),
        "state_fields_kept": all(name in Sheet.STATE_FIELDS for name in old_fields),
        "new_state_fields": new_fields,
        "new_state_fields_approved": all(name in APPROVED_NEW_FIELDS for name in new_fields),
        "new_state_fields_optional": all(name in Sheet.OPTIONAL_STATE_FIELDS for name in new_fields),
        "parameters_equal": parameter_names == old_parameter_names,
    }


def hygiene() -> Measurements:
    """Lint, formatting and types clean, and no environment variable read anywhere in the engine."""
    tools = Path(sys.executable).parent
    out: Measurements = {}
    for name, command in (
        ("lint_clean", [str(tools / "ruff"), "check", "."]),
        ("format_clean", [str(tools / "ruff"), "format", "--check", "."]),
        ("types_clean", [str(tools / "pyrefly"), "check"]),
    ):
        if not Path(command[0]).exists():
            out[name] = None
            continue
        out[name] = subprocess.run(command, cwd=REPOSITORY, capture_output=True, check=False).returncode == 0
    engine = REPOSITORY / "src" / "watercolor"
    reads = re.compile(r"\bos\.environ\b|\bgetenv\(|\benviron\[")
    out["environment_reads"] = sum(len(reads.findall(path.read_text())) for path in engine.glob("*.py"))
    return out


# ------------------------------------------------------------------------------------------------ extended experiments


def test_suite() -> Measurements:
    """The test suite in tests/, apart from the calibration tests, which run these gates."""
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests", "--ignore=tests/test_calibration.py"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    summary = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else ""
    counts = {word: 0 for word in ("passed", "failed", "error")}
    for number, word in re.findall(r"(\d+) (passed|failed|error)", summary):
        counts[word] += int(number)
    return {"passed": counts["passed"], "failed": counts["failed"] + counts["error"], "summary": summary}


def colour_difference(first: Tensor, second: Tensor) -> Tensor:
    """CIEDE2000 colour difference of two RGB pictures, shape (3, H, W), taken as sRGB-encoded values."""

    def lab(rgb: Tensor) -> Tensor:
        linear = torch.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
        matrix = torch.tensor([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
        xyz = torch.einsum("ij,jhw->ihw", matrix, linear.cpu().double().clamp(0, 1).float())
        white = torch.tensor([0.95047, 1.0, 1.08883]).reshape(3, 1, 1)
        t = xyz / white
        f = torch.where(t > (6 / 29) ** 3, t.clamp(min=1e-12) ** (1 / 3), t / (3 * (6 / 29) ** 2) + 4 / 29)
        return torch.stack((116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])))

    l1, a1, b1 = lab(first)
    l2, a2, b2 = lab(second)
    c1, c2 = torch.hypot(a1, b1), torch.hypot(a2, b2)
    mean_c = (c1 + c2) / 2
    g = 0.5 * (1 - torch.sqrt(mean_c**7 / (mean_c**7 + 25.0**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = torch.hypot(a1p, b1), torch.hypot(a2p, b2)
    h1p = torch.rad2deg(torch.atan2(b1, a1p)) % 360
    h2p = torch.rad2deg(torch.atan2(b2, a2p)) % 360
    dl, dc = l2 - l1, c2p - c1p
    dh = h2p - h1p
    dh = torch.where(dh > 180, dh - 360, torch.where(dh < -180, dh + 360, dh))
    dh = torch.where(c1p * c2p == 0, torch.zeros_like(dh), dh)
    dhh = 2 * torch.sqrt(c1p * c2p) * torch.sin(torch.deg2rad(dh / 2))
    mean_l, mean_cp = (l1 + l2) / 2, (c1p + c2p) / 2
    hsum = h1p + h2p
    mean_h = torch.where(
        c1p * c2p == 0,
        hsum,
        torch.where((h1p - h2p).abs() <= 180, hsum / 2, torch.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2)),
    )
    t = (
        1
        - 0.17 * torch.cos(torch.deg2rad(mean_h - 30))
        + 0.24 * torch.cos(torch.deg2rad(2 * mean_h))
        + 0.32 * torch.cos(torch.deg2rad(3 * mean_h + 6))
        - 0.20 * torch.cos(torch.deg2rad(4 * mean_h - 63))
    )
    sl = 1 + 0.015 * (mean_l - 50) ** 2 / torch.sqrt(20 + (mean_l - 50) ** 2)
    sc, sh = 1 + 0.045 * mean_cp, 1 + 0.015 * mean_cp * t
    rotation = 30 * torch.exp(-(((mean_h - 275) / 25) ** 2))
    rc = 2 * torch.sqrt(mean_cp**7 / (mean_cp**7 + 25.0**7))
    rt = -torch.sin(torch.deg2rad(2 * rotation)) * rc
    return torch.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (dhh / sh) ** 2 + rt * (dc / sc) * (dhh / sh))


# Trials whose glazes are all transparent paints: in "glaze" ultramarine is laid over dried hansa yellow.
TRANSPARENT_GLAZE_TRIALS = ("glaze",)


def technique_trials() -> Measurements:
    """Every technique trial of engine_trials painted as engine_trials paints them; and for the trials glazed only
    with transparent paint, the mean CIEDE2000 difference of the picture from the one 0.8.0 paints of the same sheet."""
    engine_trials = importlib.import_module("engine_trials")
    from watercolor.rendering import render
    from watercolor.together import paint_together

    trials = engine_trials.TRIALS
    sizes = engine_trials.SIZES
    palette = engine_trials.PALETTE
    failures: list[str] = []
    differences: list[float] = []
    for size in sorted({sizes.get(name, engine_trials.SIZE) for name in trials}):
        group = [name for name in trials if sizes.get(name, engine_trials.SIZE) == size]
        try:
            studios = paint_together([trials[name] for name in group], size, palette, seeds=[7] * len(group))
        except Exception:  # noqa: BLE001 - a trial that cannot be painted is counted as failed
            failures.extend(group)
            continue
        old_render = reference_module("rendering").render
        for name, studio in zip(group, studios):
            if name in TRANSPARENT_GLAZE_TRIALS:
                sheet = studio.sheets["painting"]
                differences.append(float(colour_difference(render(sheet), old_render(sheet)).mean()))
    return {"failed_trials": failures, "transparent_glaze_difference": max(differences) if differences else None}


class LayersHeldEmpty(Sheet):
    """A sheet whose paint layers are emptied after every step and every touch of a brush: the engine with its
    layer bookkeeping taken out of the physics."""

    def _empty_layers(self) -> None:
        for name in LAYER_FIELDS:
            layer = kept(self, name)
            if layer is not None:
                layer.zero_()

    def advance(self, duration: float) -> None:
        super().advance(duration)
        self._empty_layers()

    def apply_brush(
        self,
        points: Tensor,
        radii: Tensor,
        contact: Contact,
        concentration: Tensor,
        available_water: float,
        hairs: Tensor,
        on_tip: Tensor,
    ) -> tuple[float, Tensor, Tensor]:
        result = super().apply_brush(points, radii, contact, concentration, available_water, hairs, on_tip)
        self._empty_layers()
        return result


PHYSICS_SCENARIOS = (
    "flat_wash_flat", "bloom_umber", "dried_wash_lift", "wet_in_wet_dab", "white_coats",
    "four_glazes", "drybrush_white", "rewet", "set_time", "under_darkness",
)  # fmt: skip
PHYSICAL_FIELDS = ("water", "saturation", "suspended", "deposited", "mask", "mask_water", "mask_pigment")


def physics_untouched() -> Measurements:
    """The ordered-layer scenarios painted alone by the engine and by the same engine with its layers held empty:
    the layers may only divide what is deposited, never move water or pigment."""
    probe = new_sheet(8, 8)
    if any(kept(probe, name) is None for name in LAYER_FIELDS):
        return {"layers_present": False, "largest_difference": 0.0}
    worst = 0.0
    for name in PHYSICS_SCENARIOS:
        painting = PAINTINGS[name]
        sheets = []
        for kind in (Sheet, LayersHeldEmpty):
            paper = generate_paper(SIZE, SIZE, painting.seed, default_device())
            sheet = kind(paper, [PIGMENTS[p] for p in PALETTE])
            painting.script(Studio({"painting": sheet}, list(PALETTE)))
            sheets.append(sheet)
        for field in PHYSICAL_FIELDS:
            worst = max(worst, float((getattr(sheets[0], field) - getattr(sheets[1], field)).abs().max()))
    return {"layers_present": True, "largest_difference": worst}


# ------------------------------------------------------------------------------------------------ registry


@dataclass(frozen=True)
class Painting:
    """A script painted on its own 128-pixel sheet. Paintings of one family share a batch, and so a clock."""

    family: str
    script: Callable[[Studio], Measurements]
    seed: int = SEED


@dataclass(frozen=True)
class Experiment:
    """A scenario that makes its own sheets, sessions or checks. Experiments of one group run in turn in one process."""

    group: str
    run: Callable[[], Measurements]
    extended: bool = False  # too long for the standard run; selected by name or with --extended


PAINTINGS: dict[str, Painting] = {
    **{
        f"edge_{name}_{strength:g}": Painting("one_layer", edge_stroke(name, strength))
        for name in ("french_ultramarine", "quinacridone_rose")
        for strength in (0.5, 1.0, 4.0)
    },
    **{f"edge_gum_scaled_{k:g}": Painting("one_layer", edge_stroke("french_ultramarine", 1.0, k)) for k in (0.0, 3.0)},
    "flat_wash_mop": Painting("one_layer", flat_wash_mop),
    "flat_wash_round": Painting("one_layer", flat_wash_round),
    "flat_wash_flat": Painting("one_layer", flat_wash_flat),
    "wet_phase": Painting("one_layer", wet_phase),
    "patch_drying": Painting("one_layer", patch_drying),
    "shine_round": Painting("one_layer", shine("round")),
    "shine_mop": Painting("one_layer", shine("mop")),
    "drying_film_growth": Painting("one_layer", drying_film_growth),
    "rows_barely_touching": Painting("one_layer", rows_barely_touching),
    "tilt_run": Painting("one_layer", tilt_run),
    **{f"wet_balance_{s:g}": Painting("one_layer", wet_balance(s)) for s in (1.0, 4.0)},
    "brush_and_sheet": Painting("one_layer", brush_and_sheet),
    **{f"charge_film_{film:g}": Painting("wet_work", charge(film=film)) for film in (0.5, 0.3, 0.15)},
    "charge_dry_paper": Painting("wet_work", charge(wash=False)),
    **{f"charge_wait_{wait:g}": Painting("wet_work", charge(wait=wait)) for wait in (5.0, 20.0, 40.0)},
    **{f"charge_rose_{s:g}": Painting("wet_work", charge_rose(s)) for s in (0.5, 2.0, 6.0)},
    "bloom_mop": Painting("wet_work", bloom_mop),
    "bloom_round": Painting("wet_work", bloom_round),
    "bloom_umber": Painting("wet_work", bloom_umber),
    "drained_lift": Painting("wet_work", drained_lift),
    "wet_in_wet_dab": Painting("wet_work", wet_in_wet_dab),
    "damp_lift": Painting("wet_work", damp_lift),
    "unset_mixing": Painting("wet_work", unset_mixing),
    **{
        f"lift_{name}_{s:g}": Painting("over_dried", lift(name, s))
        for name in ("quinacridone_rose", "phthalo_green", "french_ultramarine", "cerulean_blue")
        for s in (0.25, 1.0, 4.0)
    },
    "lift_under_glaze": Painting("over_dried", lift_under_glaze),
    **{f"glaze_disturbance_{s:g}": Painting("over_dried", glaze_disturbance(s)) for s in (0.5, 2.0)},
    "glaze_over_rose": Painting("over_dried", glaze_over_rose),
    "dried_wash_lift": Painting("over_dried", dried_wash_lift),
    "white_coats": Painting("layers", white_coats),
    "four_glazes": Painting("layers", four_glazes),
    "rewet": Painting("layers", rewet),
    "fine_line": Painting("layers", fine_line),
    "glaze_over_white": Painting("layers", glaze_over_white),
    "drybrush_white": Painting("layers", drybrush_white),
    "under_darkness": Painting("layer_order", under_darkness),
    "order_on_top": Painting("layer_order", order(ORDER_PAINTS, dark_on_top=False)),
    "order_beneath": Painting("layer_order", order(ORDER_PAINTS, dark_on_top=True)),
    "commute_on_top": Painting("layer_order", order(COMMUTING_PAINTS, dark_on_top=False)),
    "commute_beneath": Painting("layer_order", order(COMMUTING_PAINTS, dark_on_top=True)),
    "set_time": Painting("layer_order", set_time),
}

EXPERIMENTS: dict[str, Experiment] = {
    "slope_runs": Experiment("slope", slope_runs),
    "levelling_rates": Experiment("physics", levelling_rates),
    "gum_levelling": Experiment("physics", gum_levelling),
    "thick_paint_checkerboard": Experiment("physics", thick_paint_checkerboard),
    "deep_water_on_damp_paper": Experiment("physics", deep_water_on_damp_paper),
    "thin_film_on_damp_paper": Experiment("physics", thin_film_on_damp_paper),
    "puddle_drains": Experiment("physics", puddle_drains),
    "flow_conserves_water": Experiment("physics", flow_conserves_water),
    "determinism_and_batching": Experiment("determinism", determinism_and_batching),
    "session_resume": Experiment("session", session_resume),
    "advance_conserves_pigment": Experiment("invariants", advance_conserves_pigment),
    "flow_onto_set_paint": Experiment("layer_flow", flow_onto_set_paint),
    "gum_bookkeeping": Experiment("invariants", gum_bookkeeping),
    "old_state_loads": Experiment("invariants", old_state_loads),
    "deep_puddle_scrubbed": Experiment("puddle", deep_puddle_scrubbed),
    "rewet_without_moving_paint": Experiment("rewetting", rewet_without_moving_paint),
    "non_staining_unchanged": Experiment("non_staining", non_staining_unchanged),
    "paintings_begun_with_reference": Experiment("compatibility", paintings_begun_with_reference),
    "vocabulary": Experiment("compatibility", vocabulary),
    "hygiene": Experiment("compatibility", hygiene),
    "test_suite": Experiment("test_suite", test_suite, extended=True),
    "technique_trials": Experiment("technique_trials", technique_trials, extended=True),
    "physics_untouched": Experiment("physics_untouched", physics_untouched, extended=True),
}


def paint_family(names: list[str]) -> dict[str, Measurements]:
    """Paint the named paintings together, each on its own sheet of one batch, and return their measurements.

    A painting whose script fails is recorded with its error and does not stop the others. A sheet whose script
    has ended is cleared of water, so that it no longer holds the batch to the fine time step.
    """
    device = default_device()
    sheets = [new_sheet(seed=PAINTINGS[name].seed, device=device) for name in names]
    clock = SharedClock(SheetBatch(sheets))
    studios = [Studio({"painting": sheet}, list(PALETTE), shared_clock=clock) for sheet in sheets]
    results: dict[str, Measurements] = {}

    def painter(name: str, studio: Studio) -> Callable[[], None]:
        def work() -> None:
            sheet = sheet_of(studio)
            measurements: Measurements
            try:
                measurements = PAINTINGS[name].script(studio)
                measurements["unsound_cells"] = unsound_cells(sheet)
            except Exception:  # noqa: BLE001 - recorded, so that one failing scenario does not stop the rest
                measurements = {"error": traceback.format_exc()}
            for field in (sheet.water, sheet.saturation, sheet.mask_water):
                field.zero_()
            results[name] = measurements

        return work

    clock.run([painter(name, studio) for name, studio in zip(names, studios)])
    return results


def run_experiment(name: str) -> Measurements:
    try:
        return EXPERIMENTS[name].run()
    except Exception:  # noqa: BLE001 - recorded, so that one failing scenario does not stop the rest
        return {"error": traceback.format_exc()}


# ------------------------------------------------------------------------------------------------ derived measurements


def _series(results: dict[str, Measurements], names: list[str], measurement: str) -> list | None:
    """One measurement from each of several scenarios, in order; None if any is missing."""
    values = [results.get(name, {}).get(measurement) for name in names]
    return None if any(value is None for value in values) else values


def _edges(results: dict[str, Measurements]) -> Measurements:
    out: Measurements = {
        name: _series(results, [f"edge_{name}_{s:g}" for s in (0.5, 1.0, 4.0)], "edge_ratio")
        for name in ("french_ultramarine", "quinacridone_rose")
    }
    order = ["edge_gum_scaled_0", "edge_french_ultramarine_1", "edge_gum_scaled_3"]
    out["gum_scaled"] = _series(results, order, "edge_ratio")
    return out


def _lifts(results: dict[str, Measurements]) -> Measurements:
    return {
        name: _series(results, [f"lift_{name}_{s:g}" for s in (0.25, 1.0, 4.0)], "lifted_share")
        for name in ("quinacridone_rose", "phthalo_green", "french_ultramarine", "cerulean_blue")
    }


def _lift_ratios(results: dict[str, Measurements]) -> Measurements:
    out: Measurements = {}
    for name in ("quinacridone_rose", "phthalo_green"):
        shares = _series(results, [f"lift_{name}_{s:g}" for s in (0.25, 1.0, 4.0)], "lifted_share")
        out[f"{name}_steps"] = None if shares is None else [b / a - 1.0 for a, b in itertools.pairwise(shares)]
    alone = _series(results, ["lift_quinacridone_rose_1"], "lifted_share")
    damp = _series(results, ["damp_lift"], "lifted_share")
    glazed = _series(results, ["lift_under_glaze"], "lifted_share")
    out["damp_over_dry"] = None if alone is None or damp is None else damp[0] / alone[0]
    out["under_glaze_over_alone"] = None if alone is None or glazed is None else glazed[0] / alone[0]
    return out


def _charges(results: dict[str, Measurements]) -> Measurements:
    widths = _series(results, [f"charge_film_{film:g}" for film in (0.5, 0.3, 0.15)], "rms_width")
    dry = _series(results, ["charge_dry_paper"], "rms_width")
    return {
        "widths": widths,
        "widths_over_dry": None if widths is None or dry is None else [w / dry[0] for w in widths],
        "film_0.5_over_dry": None if widths is None or dry is None else widths[0] / dry[0],
        "waited_widths": _series(results, [f"charge_wait_{wait:g}" for wait in (5, 20, 40)], "rms_width"),
        "rose_radii": _series(results, [f"charge_rose_{s:g}" for s in (0.5, 2.0, 6.0)], "radius"),
    }


def _order(results: dict[str, Measurements]) -> Measurements:
    """Order asymmetry A = V(paint over the umber) - V(umber over the paint), pictured and composed."""
    on_top, beneath = results.get("order_on_top", {}), results.get("order_beneath", {})
    top_pictured, top_composed = on_top.get("pictured"), on_top.get("composed")
    under_pictured, under_composed = beneath.get("pictured"), beneath.get("composed")
    if not (
        isinstance(top_pictured, list)
        and isinstance(top_composed, list)
        and isinstance(under_pictured, list)
        and isinstance(under_composed, list)
    ):
        return {"white_margin": None, "signs_agree": None}
    pictured = [a - b for a, b in zip(top_pictured, under_pictured)]
    composed = [a - b for a, b in zip(top_composed, under_composed)]
    white = ORDER_PAINTS.index("opaque_white")
    return {
        "asymmetry": pictured,
        "composed_asymmetry": composed,
        "white_margin": pictured[white] - max(0.10, 0.5 * composed[white]),
        "signs_agree": all((a > 0) == (k > 0) for a, k in zip(pictured, composed) if abs(k) >= 0.03),
    }


def _commute(results: dict[str, Measurements]) -> Measurements:
    """The order asymmetry of transparent paint as pictured, and the part of it that the picture adds to what 0.8.0
    shows of the same sheets. The paint itself settles a little differently on dried umber than on bare paper,
    which 0.8.0 shows too; only the rest comes from how the layers are composed."""
    on_top, beneath = results.get("commute_on_top", {}), results.get("commute_beneath", {})
    over, under = on_top.get("pictured"), beneath.get("pictured")
    over_summed, under_summed = on_top.get("summed"), beneath.get("summed")
    if not (
        isinstance(over, list)
        and isinstance(under, list)
        and isinstance(over_summed, list)
        and isinstance(under_summed, list)
    ):
        return {"differences": None, "optical_differences": None}
    pictured = [a - b for a, b in zip(over, under)]
    summed = [a - b for a, b in zip(over_summed, under_summed)]
    return {
        "differences": [abs(a) for a in pictured],
        "summed_differences": [abs(a) for a in summed],
        "optical_differences": [abs(a - b) for a, b in zip(pictured, summed)],
    }


SOUNDNESS_SOURCES = (
    "puddle_drains", "deep_water_on_damp_paper", "thin_film_on_damp_paper", "slope_runs", "deep_puddle_scrubbed",
)  # fmt: skip


def _soundness(results: dict[str, Measurements]) -> Measurements:
    """Unsound values counted at the end of every scenario of the run, whatever else it measured."""
    total = 0
    for measurements in results.values():
        for name, measured in measurements.items():
            if "unsound_cells" in name and isinstance(measured, int):
                total += measured
    return {"unsound_cells": total}


DERIVED: dict[str, tuple[tuple[str, ...], Callable[[dict[str, Measurements]], Measurements]]] = {
    "edges": (
        (
            *(f"edge_{n}_{s:g}" for n in ("french_ultramarine", "quinacridone_rose") for s in (0.5, 1.0, 4.0)),
            "edge_gum_scaled_0",
            "edge_gum_scaled_3",
        ),
        _edges,
    ),
    "lifts": (
        tuple(f"lift_{n}_{s:g}" for n in ("french_ultramarine", "cerulean_blue") for s in (0.25, 1.0, 4.0)),
        _lifts,
    ),
    "lift_ratios": (
        (
            *(f"lift_{n}_{s:g}" for n in ("quinacridone_rose", "phthalo_green") for s in (0.25, 1.0, 4.0)),
            "damp_lift",
            "lift_under_glaze",
        ),
        _lift_ratios,
    ),
    "charges": (
        (
            *(f"charge_film_{f:g}" for f in (0.5, 0.3, 0.15)),
            "charge_dry_paper",
            *(f"charge_wait_{w:g}" for w in (5, 20, 40)),
            *(f"charge_rose_{s:g}" for s in (0.5, 2.0, 6.0)),
        ),
        _charges,
    ),
    "order": (("order_on_top", "order_beneath"), _order),
    "commute": (("commute_on_top", "commute_beneath"), _commute),
    "soundness": (SOUNDNESS_SOURCES, _soundness),
}

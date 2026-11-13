"""Physical invariants of the engine. Each of these was broken at some point during development."""

import dataclasses

import pytest
import torch

from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.studio import Studio

SIZE = 128
PALETTE = ["cadmium_red", "french_ultramarine"]


@pytest.fixture
def studio() -> Studio:
    from watercolor.simulation import Sheet

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pigments = [PIGMENTS[name] for name in PALETTE]
    sheet = Sheet(generate_paper(SIZE, SIZE, 3, device), pigments)
    return Studio({"painting": sheet}, PALETTE)


def pigment_on_sheet(studio: Studio) -> float:
    sheet = studio.sheets["painting"]
    return float((sheet.suspended + sheet.deposited).sum())


def pigment_in_brush(studio: Studio) -> float:
    brush = studio.brush
    assert brush is not None
    return sum(brush.concentration) * brush.reservoir


def lay_wet_patch(studio: Studio) -> None:
    for y in (40, 64, 88):
        studio.load_brush("mop", 16, {"french_ultramarine": 0.05}, 1.0)
        studio.stroke("painting", [[24, y], [104, y]], 120, smooth=False)


def test_pigment_is_conserved_as_a_deep_puddle_drains(studio: Studio) -> None:
    # Fast flow and the surface stream leave the same cells at once; together they once
    # removed more pigment than the cells held, and the shortfall was made up from nothing.
    sheet = studio.sheets["painting"]
    sheet.water[30:98, 30:98] = 0.05
    sheet.water[58:70, 58:70] = 10.0
    sheet.suspended[0, 58:70, 58:70] = 60.0
    sheet._used.add(0)
    before = pigment_on_sheet(studio)
    studio.wait(5)
    assert pigment_on_sheet(studio) == pytest.approx(before, rel=1e-4)


def test_flow_alone_conserves_water(studio: Studio) -> None:
    sheet = studio.sheets["painting"]
    sheet.parameters = dataclasses.replace(sheet.parameters, evaporation_rate=0.0, absorption_rate=0.0)
    lay_wet_patch(studio)
    before = float(sheet.water.sum())
    studio.wait(5)
    assert float(sheet.water.sum()) == pytest.approx(before, rel=1e-4)


def test_a_drying_film_does_not_gather_into_drops(studio: Studio) -> None:
    lay_wet_patch(studio)
    deepest = float(studio.sheets["painting"].water.max())
    studio.wait(15)
    assert float(studio.sheets["painting"].water.max()) <= 1.1 * deepest


def test_brush_and_sheet_together_conserve_pigment(studio: Studio) -> None:
    studio.load_brush("round", 12, {"cadmium_red": 4.0}, 1.0)
    studio.stroke("painting", [[30, 64], [98, 64]], 120, smooth=False)
    studio.load_brush("round", 12, {"french_ultramarine": 6.0}, 0.03)  # nearly empty: it can give very little
    before = pigment_on_sheet(studio) + pigment_in_brush(studio)
    studio.stroke("painting", [[30, 66], [98, 66]], 120, smooth=False)
    assert pigment_on_sheet(studio) + pigment_in_brush(studio) == pytest.approx(before, rel=0.01)


@pytest.mark.parametrize(("start", "end", "sign"), [(40, 100, 1), (88, 28, -1)])
def test_a_stroke_carries_wet_paint_the_way_it_travels(studio: Studio, start: int, end: int, sign: int) -> None:
    studio.load_brush("round", 10, {"cadmium_red": 4.0}, 1.0)
    studio.stroke("painting", [[64, 64]], 100, smooth=False, dwell=0.6)
    sheet = studio.sheets["painting"]

    def centre_of_paint() -> float:
        paint = sheet.suspended[0] + sheet.deposited[0]
        return float((paint * sheet._xs).sum() / paint.sum())

    before = centre_of_paint()
    studio.load_brush("flat", 9, {}, 0.4)
    studio.stroke("painting", [[start, 64, 0.9], [end, 64, 0.9]], 120, smooth=False)
    assert sign * (centre_of_paint() - before) > 2.0


def test_brush_running_dry_leaves_streaks_along_the_stroke(studio: Studio) -> None:
    # Without hairs a dry brush skipped on the grain of the paper only, which leaves speckle
    # with no direction: every line along the stroke carried about the same paint.
    studio.load_brush("flat", 14, {"french_ultramarine": 3.0}, 0.3)
    studio.stroke("painting", [[16, 64, 0.8], [112, 64, 0.8]], 140, smooth=False)
    studio.dry()
    paint_by_line = studio.sheets["painting"].deposited[1, 54:75, 40:104].mean(dim=1)
    assert float(paint_by_line.min()) < 0.25 * float(paint_by_line.max())


def test_streaky_film_from_a_brush_running_low_does_not_gather_into_deep_drops(studio: Studio) -> None:
    # Wicking along damp paper once answered to surface tension as well as to depth, and in a
    # thin film broken by the gaps between hairs it pumped water into drops several washes deep.
    studio.load_brush("round", 9, {"french_ultramarine": 0.5}, 0.6)
    for x in (40, 55, 70, 85):
        studio.stroke("painting", [[x, 12, 0.9], [x + 3, 116, 0.9]], 100, smooth=False)
    sheet = studio.sheets["painting"]
    deepest_laid = float(sheet.water.max())
    for _ in range(10):
        studio.wait(4)
        assert float(sheet.water.max()) <= 1.1 * deepest_laid


def test_wash_rows_that_barely_touch_do_not_pile_into_deep_drops(studio: Studio) -> None:
    # Uneven sizing leaves thin dry lines between rows that only just meet. Pool-scale surface
    # tension, measured across those lines, once pumped the wash into drops twenty washes deep.
    sheet = studio.sheets["painting"]
    for y in (20, 60, 100):
        studio.load_brush("mop", 22, {"french_ultramarine": 0.5}, 1.0)
        studio.stroke("painting", [[-10, y, 0.9], [138, y, 0.9]], 280, smooth=False)
    for _ in range(10):
        studio.wait(4)
        assert float(sheet.water.max()) < 2.0


def test_flat_brush_ends_its_stroke_square(studio: Studio) -> None:
    # A flat brush once left the same round-ended mark as a round one, so no plane could have a corner.
    studio.load_brush("flat", 10, {"french_ultramarine": 1.0}, 1.0)
    studio.stroke("painting", [[40, 64, 1.0], [80, 64, 1.0]], 120, smooth=False)
    water = studio.sheets["painting"].water
    assert float(water[64 + 7, 78]) > 0.1  # the full width is laid right up to the end of the stroke
    assert float(water[64, 80 + 7]) == 0.0  # and nothing beyond it, where a round tip would reach


def test_loaded_passage_runs_down_a_tilted_sheet(studio: Studio) -> None:
    # Tilt once only biased the flow inside a puddle; its lower edge held as firmly as on a level sheet.
    def lowest_painted_row(tilt: float) -> int:
        sheet = studio.sheets["painting"]
        for field in (sheet.water, sheet.saturation, sheet.suspended, sheet.deposited):
            field.zero_()
        studio.tilt("painting", 0.0, tilt)
        studio.load_brush("round", 8, {"french_ultramarine": 1.0}, 1.0)
        studio.stroke("painting", [[30, 30, 0.9], [98, 30, 0.9]], 110, smooth=False)
        studio.stroke("painting", [[64, 34]], 100, smooth=False, dwell=3.0)
        studio.wait(30)
        return int((sheet.water + sheet.saturation > 0).any(dim=1).nonzero().max())

    assert lowest_painted_row(0.2) >= lowest_painted_row(0.0) + 6


def test_thick_wet_paint_does_not_settle_into_a_checkerboard(studio: Studio) -> None:
    # The surface stream spreads thick paint fast. Unlimited, it overshot from cell to cell in each
    # substep and left alternate cells light and dark across every passage of strong colour.
    sheet = studio.sheets["painting"]
    sheet.water[24:104, 24:104] = 0.9
    sheet.suspended[0, 24:104, 24:104] = 1.8
    sheet.suspended[1, 24:104, 24:64] = 1.2
    sheet._used.update((0, 1))
    sheet.advance(8.0)
    paint = (sheet.suspended + sheet.deposited).sum(0)[34:94, 34:94]
    alternate = torch.ones_like(paint)
    alternate[::2, 1::2] = -1
    alternate[1::2, ::2] = -1
    local = paint - torch.nn.functional.avg_pool2d(paint[None, None], 3, 1, 1)[0, 0]
    assert float((local * alternate)[2:-2, 2:-2].mean().abs() / paint.mean()) < 0.01


def test_stroke_on_dry_paper_dries_darker_at_its_edge(studio: Studio) -> None:
    # Water must keep reaching the edge of a wash as it dries there, carrying pigment with it.
    # With too little of that flow a stroke dried as a flat stamp, paler at its edge than its middle.
    studio.load_brush("flat", 14, {"french_ultramarine": 1.0}, 1.0)
    studio.stroke("painting", [[20, 64, 1.0], [108, 64, 1.0]], 110, smooth=False)
    studio.dry()
    across = studio.sheets["painting"].deposited[1, 48:80, 36:92].mean(dim=1)
    assert float(across[:6].max()) > 1.15 * float(across[12:20].mean())


def laid_water(studio: Studio, kind: str, hair: str = "") -> torch.Tensor:
    """Water left by one level stroke of a full brush, from x = 40 to x = 88 at y = 64."""
    sheet = studio.sheets["painting"]
    for field in (sheet.water, sheet.saturation, sheet.suspended, sheet.deposited):
        field.zero_()
    studio.load_brush(kind, 10, {"french_ultramarine": 1.0}, 1.0, hair=hair)
    studio.stroke("painting", [[40, 64, 1.0], [88, 64, 1.0]], 120, smooth=False)
    return sheet.water.clone()


def test_shape_of_the_head_sets_how_a_stroke_ends(studio: Studio) -> None:
    # Every flat head once ended the same way. Just past the end of the stroke, at the corner
    # of the head: a square end reaches it, a rounded end does not, and a slanted end reaches
    # it on one side of the stroke only.
    upper, lower = (64 - 9, 90), (64 + 9, 90)
    flat = laid_water(studio, "flat")
    assert float(flat[upper]) > 0.1 and float(flat[lower]) > 0.1
    filbert = laid_water(studio, "filbert")
    assert float(filbert[upper]) < 0.5 * float(flat[upper]) and float(filbert[lower]) < 0.5 * float(flat[lower])
    angular = laid_water(studio, "angular")
    assert (float(angular[upper]) > 0.1) != (float(angular[lower]) > 0.1)


def test_comber_leaves_bare_lines_even_when_full(studio: Studio) -> None:
    # A comber's hairs stand apart whatever it holds; a flat brush of the same size lays an unbroken band.
    def emptiest_line(kind: str) -> float:
        across = laid_water(studio, kind)[56:73, 48:80].mean(dim=1)
        return float(across.min() / across.max())

    assert emptiest_line("flat") > 0.6
    assert emptiest_line("comber") < 0.3


def test_squirrel_carries_a_wash_further_than_synthetic(studio: Studio) -> None:
    # The hair decides how much water a brush of a given size holds, and so how far it paints.
    def left_in_brush(hair: str) -> float:
        laid_water(studio, "round", hair)
        brush = studio.brush
        assert brush is not None
        for _ in range(4):
            studio.stroke("painting", [[20, 30, 1.0], [108, 30, 1.0]], 120, smooth=False)
        return brush.fullness

    assert left_in_brush("squirrel") > left_in_brush("red_sable") > left_in_brush("golden_synthetic")

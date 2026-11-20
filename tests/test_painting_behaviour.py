"""What a painter relies on from the engine, which a change to the physics could quietly lose.

Each bound is the behaviour itself, with the margin a painter would still accept. 0.8.0's own value is given
beside each, so that a change which moves it a long way is seen in review even when the test still passes.
"""

import torch
import torch.nn.functional as F

from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.simulation import Sheet
from watercolor.studio import Studio

PALETTE = ["cadmium_red", "french_ultramarine"]
RED, BLUE = 0, 1


def new_studio() -> Studio:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sheet = Sheet(generate_paper(128, 128, 3, device), [PIGMENTS[name] for name in PALETTE])
    return Studio({"painting": sheet}, PALETTE)


def lay_wash(studio: Studio, pigments: dict[str, float]) -> None:
    """Three overlapping mop-16 strokes across the middle of the sheet, a fresh load for each."""
    for y in (40, 64, 88):
        studio.load_brush("mop", 16, pigments, 1.0)
        studio.stroke("painting", [[24, y], [104, y]], 120, smooth=False)


def width_across(amount: torch.Tensor) -> float:
    """Root-mean-square spread, in rows, of an amount given for each row."""
    rows = torch.arange(amount.numel(), dtype=torch.float32, device=amount.device)
    return float(torch.cov(rows, correction=0, aweights=amount).sqrt())


def test_a_flat_wash_dries_evenly_in_its_usual_time() -> None:
    """Ultramarine 0.6 laid in three overlapping mop strokes dries without blotches, and in about the time the
    painting skill's timings assume. 0.8.0: variation between 8-pixel boxes 0.075, dry after 280 s."""
    studio = new_studio()
    lay_wash(studio, {"french_ultramarine": 0.6})
    drying = studio.dry()
    boxes = F.avg_pool2d(studio.sheets["painting"].deposited[BLUE, 44:84, 36:92][None, None], 8)[0, 0]
    assert float(boxes.std() / boxes.mean()) <= 0.11
    assert 210 <= drying <= 350


def test_clear_water_dropped_into_a_wash_losing_its_shine_dries_as_a_bloom() -> None:
    """Water dropped into a wash whose film has all but gone pushes the paint outward, so the drop dries paler than
    the wash inside a darker rim: a backrun (Curtis et al. 1997). 0.8.0: centre 0.60 of the wash, rim 1.19."""
    studio = new_studio()
    sheet = studio.sheets["painting"]
    lay_wash(studio, {"french_ultramarine": 0.6})
    studio.wait_for_film("painting", 64, 64, 0.03, 300)
    assert sheet.wetness_at(64, 64)["film"] <= 0.03  # the drop must land on a wash that has lost its shine
    studio.load_brush("round", 8, {}, 1.0)
    studio.stroke("painting", [[64, 64]], 100, smooth=False, dwell=0.6)
    studio.dry()
    paint = sheet.deposited[BLUE]
    distance = torch.hypot(sheet._xs - 64, sheet._ys - 64)
    wash = float(paint[(distance > 24) & (distance < 30)].mean())
    # The rim is looked for between the pale centre and the wash it is compared with: the innermost rings hold a
    # few cells each, and on a wash with no drop at all they can read far above the wash by the grain alone.
    rim = max(float(paint[(distance >= r) & (distance < r + 2)].mean()) for r in range(4, 22, 2))
    assert float(paint[distance < 4].mean()) / wash <= 0.8
    assert rim / wash >= 1.1


def test_paint_charged_into_a_shining_wash_spreads_to_twice_its_width_on_dry_paper() -> None:
    """Strong paint drawn into a wash whose film is still 0.5 deep spreads to twice its width on dry paper or more,
    as the painting skill's spread table says. 0.8.0: 8.2 rows against 2.3, 3.6 times."""
    widths = []
    for wet in (True, False):
        studio = new_studio()
        if wet:
            lay_wash(studio, {})
            studio.wait_for_film("painting", 64, 64, 0.5, 400)
            assert studio.sheets["painting"].wetness_at(64, 64)["film"] <= 0.5
        studio.loads = 0  # the same load, and so the same variation of paint and hairs, for both strokes
        studio.load_brush("round", 5, {"cadmium_red": 4.0}, 1.0)
        studio.drain(0.6)
        studio.stroke("painting", [[34, 64, 0.8], [94, 64, 0.8]], 110, smooth=False)
        studio.dry()
        widths.append(width_across(studio.sheets["painting"].deposited[RED][:, 44:84].sum(dim=1)))
    assert widths[0] >= 2 * widths[1]


def dried_band(fixed: bool) -> tuple[Studio, torch.Tensor]:
    """A sheet with a band of dried ultramarine across its middle, fixed over the whole sheet or not, and the paint
    on the paper as it was before anything touched the band. Dried paint is settled pigment with no water about it;
    once water stands on it again it lies in the buried layer, beneath whatever settles out of that water."""
    studio = new_studio()
    sheet = studio.sheets["painting"]
    sheet.deposited[BLUE, 36:93, 20:109] = 1.0
    sheet._used.add(BLUE)
    if fixed:
        studio.fix("painting")
    return studio, sheet.deposited.clone()


def test_dried_paint_on_fixed_paper_does_not_lift_into_a_clear_wash() -> None:
    """A clear wash laid over dried ultramarine takes some of it back into the water; on paper fixed first it takes
    none, and leaves the dried paint exactly as it was. Measured: 6.2% of it in the water after 10 s, and none when
    fixed."""

    def lifted(fixed: bool) -> tuple[float, bool]:
        studio, dried = dried_band(fixed)
        sheet = studio.sheets["painting"]
        lay_wash(studio, {})
        studio.wait(10)
        return float(sheet.suspended[BLUE].sum() / dried[BLUE].sum()), torch.equal(
            sheet.deposited + sheet.buried, dried
        )

    assert lifted(False)[0] >= 0.03
    assert lifted(True) == (0.0, True)


def test_a_stiff_drained_brush_scrubs_nothing_from_fixed_paper() -> None:
    """Four passes of a bright on golden synthetic, loaded with clear water and drained to 0.2, scrub dried ultramarine
    off bare paper, and leave it exactly as it was on paper fixed first. Measured: 37.9% of it loosened from under the
    passes on bare paper."""

    def scrubbed(fixed: bool) -> tuple[float, bool]:
        studio, dried = dried_band(fixed)
        sheet = studio.sheets["painting"]
        studio.load_brush("bright", 6, {}, 1.0, hair="golden_synthetic")
        studio.drain(0.2)
        for _ in range(4):
            studio.stroke("painting", [[40, 64, 0.9], [88, 64, 0.9]], 120, smooth=False)
        under = (slice(59, 70), slice(44, 85))
        settled = sheet.deposited + sheet.buried
        left = float(settled[BLUE][under].sum() / dried[BLUE][under].sum())
        return 1.0 - left, torch.equal(settled, dried)

    assert scrubbed(False)[0] >= 0.2
    assert scrubbed(True) == (0.0, True)


def test_paint_charged_into_a_wash_on_fixed_paper_spreads_as_on_bare_paper() -> None:
    """Fixative holds paint only once it has settled, so strong paint drawn into a shining wash laid on fixed paper
    spreads as far as on bare paper. Measured: 8.22 rows against 8.26."""
    widths = []
    for fixed in (False, True):
        studio = new_studio()
        if fixed:
            studio.fix("painting")
        lay_wash(studio, {})
        studio.wait_for_film("painting", 64, 64, 0.5, 400)
        studio.load_brush("round", 5, {"cadmium_red": 4.0}, 1.0)
        studio.drain(0.6)
        studio.stroke("painting", [[34, 64, 0.8], [94, 64, 0.8]], 110, smooth=False)
        studio.dry()
        widths.append(width_across(studio.sheets["painting"].deposited[RED][:, 44:84].sum(dim=1)))
    assert 0.9 <= widths[1] / widths[0] <= 1.1

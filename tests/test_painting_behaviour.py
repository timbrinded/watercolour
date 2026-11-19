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
    studio.load_brush("round", 8, {}, 1.0)
    studio.stroke("painting", [[64, 64]], 100, smooth=False, dwell=0.6)
    studio.dry()
    paint = sheet.deposited[BLUE]
    distance = torch.hypot(sheet._xs - 64, sheet._ys - 64)
    wash = float(paint[(distance > 24) & (distance < 30)].mean())
    rim = max(float(paint[(distance >= r) & (distance < r + 2)].mean()) for r in range(0, 30, 2))
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
        studio.load_brush("round", 5, {"cadmium_red": 4.0}, 1.0)
        studio.drain(0.6)
        studio.stroke("painting", [[34, 64, 0.8], [94, 64, 0.8]], 110, smooth=False)
        studio.dry()
        widths.append(width_across(studio.sheets["painting"].deposited[RED][:, 44:84].sum(dim=1)))
    assert widths[0] >= 2 * widths[1]

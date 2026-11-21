"""Coloured pencil, pastel and pencil drawn over paper and dried paint: each mark lies over what is already there and
under whatever is painted later."""

import torch
from torch import Tensor

from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.rendering import render_view
from watercolor.simulation import Sheet
from watercolor.studio import Studio

SIZE = 128
PALETTE = ["french_ultramarine", "burnt_umber", "opaque_white", "ivory_black", "quinacridone_rose", "cobalt_blue"]
DARK = {"french_ultramarine": 3.0, "burnt_umber": 3.0}
PATCH = (slice(48, 80), slice(48, 80))


def new_studio() -> Studio:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sheet = Sheet(generate_paper(SIZE, SIZE, 3, device), [PIGMENTS[name] for name in PALETTE])
    return Studio({"painting": sheet}, PALETTE)


def value(studio: Studio) -> Tensor:
    return render_view(studio.sheets["painting"], "value")[0]


def lay_rows(studio: Studio, mix: dict[str, float], rows: range, brush: str = "mop", size: float = 16) -> None:
    for y in rows:
        studio.load_brush(brush, size, mix, 1.0)
        studio.stroke("painting", [[8, y], [120, y]], 140, smooth=False)


def draw_patch(studio: Studio, medium: str, pigments: dict[str, float], pressure: float) -> None:
    """Rows of a stick 4 pixels in radius across the middle of the sheet, back and forth."""
    path = []
    for row, y in enumerate(range(44, 86, 6)):
        ends = (40, 88) if row % 2 == 0 else (88, 40)
        path += [[ends[0], y, pressure], [ends[1], y, pressure]]
    studio.draw("painting", medium, pigments, path, 4.0)


def test_light_pastel_covers_a_dark_dried_wash_evenly() -> None:
    """White pastel at strength 2 and full pressure, in overlapping rows, over a dried dark. No paint beside a mark lies
    over it, so the rows and the pieces of each row join without a seam. Measured: the dark 0.044, the pastel over it
    0.73, and no row of it varying by more than 0.003 (0.08 when the paint beside each piece lay over it)."""
    studio = new_studio()
    lay_rows(studio, DARK, range(16, 116, 12))
    studio.dry()
    draw_patch(studio, "pastel", {"opaque_white": 2.0}, 1.0)
    pastel = value(studio)[PATCH]
    assert float(pastel.mean()) > 0.65
    assert float((pastel.amax(1) - pastel.amin(1)).max()) < 0.02


def test_light_pressure_marks_only_the_peaks_of_the_grain() -> None:
    """Black pastel over white paper. At pressure 0.3 the peaks of the grain take far more of it than the hollows; at
    full pressure the hollows fill as well. Measured: the peaks darkened about 160 times as much as the hollows at 0.3,
    and 1.02 times as much at 1."""
    darkened = []
    for pressure in (0.3, 1.0):
        studio = new_studio()
        sheet = studio.sheets["painting"]
        bare = value(studio)
        draw_patch(studio, "pastel", {"ivory_black": 4.0}, pressure)
        change = (bare - value(studio))[PATCH]
        height = ((sheet.tooth - sheet.valley) / sheet.grain_depth)[PATCH]
        darkened.append(float(change[height > 0.75].mean()) / float(change[height < 0.25].mean()))
    light, full = darkened
    assert light > 4.0
    assert full < 1.3


def test_a_stick_lifted_to_pressure_zero_marks_nothing() -> None:
    """Two lines joined by a stretch drawn at pressure 0: the stretch between them stays paper."""
    studio = new_studio()
    bare = value(studio)
    path = [[20, 40, 0.8], [100, 40, 0.8], [100, 40, 0.0], [20, 88, 0.0], [20, 88, 0.8], [100, 88, 0.8]]
    studio.draw("painting", "coloured_pencil", {"french_ultramarine": 2.0}, path, 1.5)
    marked = (bare - value(studio)).abs()
    assert float(marked[40, 30:90].mean()) > 0.1 and float(marked[88, 30:90].mean()) > 0.1
    assert float(marked[52:76, 40:80].max()) < 0.01


def test_a_mark_drawn_later_lies_on_top_of_an_earlier_one() -> None:
    """Blue pastel over white, and white over blue, on the same cells. Measured: 0.34 and 0.77."""
    values = []
    for first, second in (("opaque_white", "french_ultramarine"), ("french_ultramarine", "opaque_white")):
        studio = new_studio()
        draw_patch(studio, "pastel", {first: 2.0}, 1.0)
        draw_patch(studio, "pastel", {second: 2.0}, 1.0)
        values.append(float(value(studio)[PATCH].mean()))
    blue_on_top, white_on_top = values
    assert white_on_top > blue_on_top + 0.2


def test_a_wash_laid_after_a_dry_mark_lies_over_it() -> None:
    """White pastel on white paper, then a cobalt glaze across it and beside it. The glaze lies over the pastel as over
    the paper. Measured: the pastel 0.96, glazed 0.63, against 0.65 for the glaze on paper."""
    studio = new_studio()
    draw_patch(studio, "pastel", {"opaque_white": 2.0}, 1.0)
    lay_rows(studio, {"cobalt_blue": 0.8}, range(36, 96, 12))
    studio.dry()
    glazed_pastel, glazed_paper = float(value(studio)[PATCH].mean()), float(value(studio)[40:46, 20:30].mean())
    assert glazed_pastel < 0.8
    assert abs(glazed_pastel - glazed_paper) < 0.06


def test_dry_media_take_nothing_where_a_film_stands_or_on_masking_fluid() -> None:
    """A stick drawn across a band of clear water and a band of masking fluid leaves both as paper once the water has
    dried and the fluid is rubbed away. Measured: the paper 0.96, the mark on dry paper 0.09, on the water's band 0.96
    and under the fluid 0.96."""
    studio = new_studio()
    studio.mask("painting", [[20, 88], [108, 88]], 8.0)
    studio.load_brush("mop", 16, {}, 1.0)
    studio.stroke("painting", [[8, 40], [120, 40]], 140, smooth=False)
    paper = float(value(studio)[16:24, 40:88].mean())
    studio.draw("painting", "pastel", {"ivory_black": 3.0}, [[64, 16, 1.0], [64, 112, 1.0]], 3.0)
    studio.dry()
    studio.unmask("painting")
    picture = value(studio)
    assert float(picture[20, 62:67].mean()) < paper - 0.3
    assert float(picture[38:43, 62:67].mean()) > paper - 0.02
    assert float(picture[86:91, 62:67].mean()) > paper - 0.02


def test_a_fine_coloured_pencil_line_breaks_on_the_grain_only_under_light_pressure() -> None:
    """A line of radius 0.9 along the sheet. Measured: at pressure 0.6 no column of it is paler than 0.85; at 0.3,
    0.41 of them are."""
    broken = []
    for pressure in (0.6, 0.3):
        studio = new_studio()
        path = [[10, 64, pressure], [118, 64, pressure]]
        studio.draw("painting", "coloured_pencil", {"quinacridone_rose": 2.0}, path, 0.9)
        line = value(studio)[56:73, 20:108].min(dim=0).values
        broken.append(float((line > 0.85).float().mean()))
    firm, light = broken
    assert firm == 0.0
    assert light > 0.2


def test_pencil_marks_drawn_over_one_another_build_tone() -> None:
    """A pencil line, then a crossing line and the same line again. Measured: 0.67 after one pass, 0.48 after two."""
    studio = new_studio()
    studio.pencil("painting", [[20, 64], [108, 64]], 0.8)
    once = float(value(studio)[64, 30:50].mean())
    studio.pencil("painting", [[64, 20], [64, 108]], 0.8)
    studio.pencil("painting", [[20, 64], [108, 64]], 0.8)
    assert float(value(studio)[64, 30:50].mean()) < once - 0.1


def test_pencil_drawn_over_dried_paint_lies_on_it_and_under_paint_laid_later() -> None:
    """A pencil line on a dried cobalt wash, then white paint over it. Measured: the wash 0.71, the line on it 0.52;
    under the white the line reads 0.75 against 0.82 for the white beside it."""
    studio = new_studio()
    lay_rows(studio, {"cobalt_blue": 0.6}, range(36, 96, 12))
    studio.dry()
    wash = float(value(studio)[58:70, 40:88].mean())
    studio.pencil("painting", [[20, 64], [108, 64]], 0.8)
    assert float(value(studio)[64, 40:88].mean()) < wash - 0.1
    lay_rows(studio, {"opaque_white": 4.5}, range(56, 76, 8), brush="round", size=8)
    studio.dry()
    line, beside = float(value(studio)[64, 50:78].mean()), float(value(studio)[60, 50:78].mean())
    assert beside - line < 0.1


def test_the_eraser_reaches_pencil_on_bare_paper_and_not_pencil_under_paint() -> None:
    """A pencil line with a cobalt glaze dried over its right half, then rubbed out along its whole length. Measured:
    the bare half goes from 0.74 to 0.92, the paper being 0.96; under the glaze the line stays at 0.61, against 0.78
    for the glaze beside it."""
    studio = new_studio()
    studio.pencil("painting", [[16, 64], [112, 64]], 0.6)
    bare = float(value(studio)[64, 20:56].mean())
    for y in (52, 64, 76):
        studio.load_brush("mop", 10, {"cobalt_blue": 0.6}, 1.0)
        studio.stroke("painting", [[72, y], [120, y]], 140, smooth=False)
    studio.dry()
    glazed = float(value(studio)[64, 84:108].mean())
    studio.erase("painting", [[8, 64], [120, 64]], 4.0)
    picture = value(studio)
    assert float(picture[64, 20:56].mean()) > bare + 0.1
    assert abs(float(picture[64, 84:108].mean()) - glazed) < 0.005

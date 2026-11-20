"""Paint laid over paint that has dried lies over it as a new layer; paint laid into wet paint mixes with it."""

from collections.abc import Iterable

import torch
from torch import Tensor

from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS, Pigment
from watercolor.rendering import render, render_view
from watercolor.simulation import Sheet
from watercolor.studio import Studio

SIZE = 128
PALETTE = ["burnt_umber", "french_ultramarine", "opaque_white", "burnt_sienna"]
DARK = {"burnt_umber": 3.0, "french_ultramarine": 3.0}
PATCH = (slice(58, 70), slice(48, 80))
# A paint that neither absorbs nor scatters: laying it changes the layers and nothing that can be seen.
INVISIBLE = Pigment("invisible", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.03, 1.0, 0.0)


def new_studio(pigments: list[Pigment] | None = None) -> Studio:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pigments = pigments or [PIGMENTS[name] for name in PALETTE]
    sheet = Sheet(generate_paper(SIZE, SIZE, 3, device), pigments)
    return Studio({"painting": sheet}, [pigment.name for pigment in pigments])


def value(studio: Studio) -> Tensor:
    return render_view(studio.sheets["painting"], "value")[0]


def pigment(studio: Studio, name: str) -> Tensor:
    sheet = studio.sheets["painting"]
    index = studio.palette.index(name)
    return sheet.suspended[index] + sheet.deposited[index] + sheet.buried[index]


def lay_rows(studio: Studio, mix: dict[str, float], rows: Iterable[int] = range(24, 108, 12)) -> None:
    for y in rows:
        studio.load_brush("mop", 16, mix, 1.0)
        studio.stroke("painting", [[16, y], [112, y]], 120, smooth=False)


def lay_white_patch(studio: Studio) -> None:
    studio.load_brush("round", 8, {"opaque_white": 4.5}, 1.0)
    for y in (54, 64, 74):
        studio.stroke("painting", [[40, y], [88, y]], 60, smooth=False)


def test_white_laid_on_a_dried_dark_covers_it_and_white_laid_into_the_wet_dark_mixes_with_it() -> None:
    """One coat of white over a dark of 0.043, laid once the dark has dried and laid while it is still wet.
    Measured: 0.55 over the dried dark (0.31 on 0.10.0, which mixed it in) and 0.38 in the wet dark. Over the dried
    dark the white still takes up some of it, which lifts easily."""
    dried, wet = new_studio(), new_studio()
    for studio in (dried, wet):
        lay_rows(studio, DARK)
    dried.dry()
    for studio in (dried, wet):
        lay_white_patch(studio)
        studio.dry()
    over_dried, into_wet = float(value(dried)[PATCH].mean()), float(value(wet)[PATCH].mean())
    assert over_dried > 0.5
    assert into_wet < over_dried - 0.1


def test_white_charged_into_clear_water_over_a_dried_dark_still_lies_over_it() -> None:
    """Clear water wets the dried dark again without making it wet paint: white charged into the water lies over the
    dark, though it takes up more of it than on the dried dark, being wet for longer. Measured: 0.47, against 0.55
    on the dried dark directly and 0.38 in the dark while it was still wet."""
    studio = new_studio()
    lay_rows(studio, DARK)
    studio.dry()
    studio.load_brush("mop", 16, {}, 1.0)
    for y in (54, 64, 74):
        studio.stroke("painting", [[36, y], [92, y]], 120, smooth=False)
    lay_white_patch(studio)
    studio.dry()
    assert float(value(studio)[PATCH].mean()) > 0.44


def test_a_coloured_wash_lifts_the_dried_paint_under_it_as_clear_water_does() -> None:
    """The water in a glaze wets the dried paint beneath as clear water does; the paint it carries does not seal
    what is under it. Measured: a clear mop row moved 0.073 of a dried ultramarine wash and a burnt sienna row 0.064. On
    0.10.0 the sienna row moved 0.57, because the dried grains rolled in its water."""
    moved = []
    for mix in ({}, {"burnt_sienna": 0.6}):
        studio = new_studio()
        lay_rows(studio, {"french_ultramarine": 2.0}, range(40, 92, 12))
        studio.dry()
        laid = pigment(studio, "french_ultramarine").clone()
        studio.load_brush("mop", 16, mix, 1.0)
        studio.stroke("painting", [[24, 64], [104, 64]], 120, smooth=False)
        studio.dry()
        region = (slice(56, 72), slice(36, 92))
        change = (pigment(studio, "french_ultramarine") - laid)[region].abs().sum()
        moved.append(float(change / laid[region].sum()))
    clear, glaze = moved
    assert clear > 0.05
    assert 0.5 * clear < glaze < 2.0 * clear


def test_clear_water_still_lifts_dried_paint() -> None:
    """A stiff flat at full water scrubs a dried ultramarine wash, then drained lifts it. Measured: 0.24 of the paint
    under the scrub, as on 0.10.0."""
    studio = new_studio()
    lay_rows(studio, {"french_ultramarine": 2.0}, range(40, 92, 12))
    studio.dry()
    region = (slice(54, 74), slice(40, 88))
    laid = float(pigment(studio, "french_ultramarine")[region].sum())
    studio.load_brush("flat", 9, {}, 1.0)
    studio.stroke("painting", [[40, 64, 0.9], [88, 64, 0.9], [40, 64, 0.9], [88, 64, 0.9]], 120, smooth=False)
    studio.wait(3)
    studio.drain(0.1)
    studio.stroke("painting", [[40, 64, 0.9], [88, 64, 0.9]], 120, smooth=False)
    studio.dry()
    assert 1.0 - float(pigment(studio, "french_ultramarine")[region].sum()) / laid > 0.2


def test_a_transparent_glaze_over_a_dried_shape_looks_as_the_two_paints_mixed() -> None:
    """Transparent layers nearly commute, so a glaze over a dried shape must look almost as the same paint lying in one
    layer, edges included: the skill's measured glazes depend on it. The two paints scatter a little, so order counts
    for a little. Measured: they differ by at most 0.013."""
    studio = new_studio()
    studio.load_brush("round", 10, {"burnt_sienna": 2.0}, 1.0)
    studio.stroke("painting", [[40, 50], [88, 78]], 60, smooth=False)
    studio.dry()
    lay_rows(studio, {"french_ultramarine": 1.0}, range(36, 96, 12))
    studio.dry()
    sheet = studio.sheets["painting"]
    layered = render(sheet)
    sheet.deposited += sheet.buried
    sheet.buried.zero_()
    assert float((layered - render(sheet)).abs().max()) < 0.02


def test_paint_pressed_beneath_two_newer_layers_keeps_its_colour() -> None:
    """A dried stroke, white brushed over it and dried, then a broad line of an invisible pen ink over both. White over
    the stroke looks different from the two mixed, so the line presses the stroke into the colour beneath as it goes,
    giving each cell it inks a crisp edge. The picture must not change, at the stroke's edges either. Measured:
    under 0.0001."""
    studio = new_studio([PIGMENTS["burnt_sienna"], PIGMENTS["opaque_white"], INVISIBLE])
    studio.load_brush("round", 4, {"burnt_sienna": 3.0}, 1.0)
    studio.stroke("painting", [[30, 64], [98, 64]], 60, smooth=False)
    studio.dry()
    studio.load_brush("round", 8, {"opaque_white": 2.0}, 1.0)
    studio.stroke("painting", [[24, 64], [104, 64]], 60, smooth=False)
    studio.dry()
    sheet = studio.sheets["painting"]
    before = render(sheet)
    studio.pen("painting", [[16, 64], [112, 64]], 16.0, {"invisible": 1.0}, 120, smooth=False)
    assert float(sheet.substrate_change.abs().sum()) > 0.0
    assert float((render(sheet) - before).abs().max()) < 0.002


def test_pencil_lies_under_the_paint() -> None:
    """A pencil line drawn before any paint, then two coats of white over it: the white hides most of it, where pencil
    drawn over the paint would show at full strength. Measured: 0.197 darker than the paper beside it before the white,
    0.081 darker than the white beside it after."""
    studio = new_studio()
    studio.pencil("painting", [[20, 64], [108, 64]], 0.6)

    def darkening() -> float:
        return float(value(studio)[60, 48:80].mean()) - float(value(studio)[64, 48:80].mean())

    on_paper = darkening()
    for _ in range(2):
        lay_white_patch(studio)
        studio.dry()
    assert darkening() < 0.6 * on_paper


def test_a_sheet_saved_before_layers_existed_knows_which_paint_has_dried() -> None:
    """A sheet saved before layers existed has no record of which paint has dried; it is worked out from the water, so
    paint laid on a dried band lies over it and paint charged into a wet one mixes with it."""
    studio = new_studio()
    lay_rows(studio, DARK, [30])
    studio.dry()
    lay_rows(studio, DARK, [90])
    sheet = studio.sheets["painting"]
    state = {name: field for name, field in sheet.state().items() if name not in ("buried", "dried_paint")}
    sheet.dried_paint.zero_()
    sheet.load_state(state)
    assert bool(sheet.dried_paint[30, 64]) and not bool(sheet.dried_paint[90, 64])

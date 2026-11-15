"""How water shows in the picture: a small lamp beside the camera, mirrored only where the water's surface is tilted."""

import torch
from torch import Tensor

from watercolor.paper import Paper, generate_paper, generate_tooth
from watercolor.pigments import PIGMENTS
from watercolor.rendering import render, render_view, sheen
from watercolor.simulation import Sheet
from watercolor.studio import Studio

SIZE = 96
CENTRE = SIZE // 2
PALETTE = ["cobalt_blue"]
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
LIT = 0.5  # light that shows plainly against any paint, as a share of white
UNLIT = 0.02  # light too faint to see


def sheet_of(paper: Paper) -> Sheet:
    return Sheet(paper, [PIGMENTS[name] for name in PALETTE])


def lying_flat(tooth: Tensor) -> Paper:
    """Paper with the given grain and no buckling."""
    return Paper(tooth=tooth, cockle=torch.zeros_like(tooth), sizing=torch.full_like(tooth, 0.5))


def pool_on_level_paper() -> Sheet:
    """A round pool of clear water, level in the middle and shelving to nothing at its rim, on paper with no grain."""
    sheet = sheet_of(lying_flat(torch.full((SIZE, SIZE), 0.5, device=DEVICE)))
    rows, columns = torch.meshgrid(torch.arange(SIZE, device=DEVICE), torch.arange(SIZE, device=DEVICE), indexing="ij")
    from_centre = ((rows - CENTRE) ** 2 + (columns - CENTRE) ** 2).float().sqrt()
    sheet.water = (0.6 * (30.0 - from_centre) / 8.0).clamp(0, 0.6)
    return sheet


def test_a_wash_shows_the_lamp_while_it_is_wet_and_not_once_it_is_dry() -> None:
    sheet = sheet_of(generate_paper(SIZE, SIZE, 3, DEVICE))
    studio = Studio({"painting": sheet}, PALETTE)
    for y in (30, 48, 66):
        studio.load_brush("mop", 14, {"cobalt_blue": 0.5}, 1.0)
        studio.stroke("painting", [[16, y], [80, y]], 120, smooth=False)
    light = sheen(sheet)
    assert float(light.max()) > LIT
    # Most of the wash keeps its colour: the lamp is a highlight on it, not a veil over it.
    assert float(light[sheet.water > 0].median()) < UNLIT
    studio.dry()
    assert float(sheen(sheet).max()) == 0.0


def test_a_level_pool_shows_the_lamp_only_on_the_rim_that_faces_it() -> None:
    light = sheen(pool_on_level_paper())
    assert float(light[:CENTRE, :CENTRE].max()) > LIT  # the lamp stands to the upper left
    assert float(light[CENTRE:, CENTRE:].max()) < UNLIT
    assert float(light[CENTRE - 10 : CENTRE + 10, CENTRE - 10 : CENTRE + 10].max()) < UNLIT


def test_a_thin_film_glitters_in_points_over_the_grain() -> None:
    # The sheet lies flat, so the points come from the grain alone and not from a buckle that happens to face the lamp.
    sheet = sheet_of(lying_flat(generate_tooth(SIZE, SIZE, 3, DEVICE)))
    sheet.water[24:72, 24:72] = 0.08
    light = sheen(sheet)[24:72, 24:72]
    assert float((light > LIT).float().mean()) > 0.01
    assert float(light.median()) < UNLIT


def test_the_value_view_leaves_out_the_light_of_the_lamp() -> None:
    sheet = pool_on_level_paper()
    row, column = divmod(int(sheen(sheet).argmax()), SIZE)
    assert float(render(sheet)[:, row, column].min()) > 0.99
    assert float(render_view(sheet, "value")[0, row, column]) < 0.97

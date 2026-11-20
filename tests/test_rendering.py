"""How water shows in the picture: a small lamp beside the camera, mirrored where the water's surface is tilted
and gathered on the paper where the water stands proud."""

import torch
from torch import Tensor

from watercolor.paper import Paper, generate_paper, generate_tooth
from watercolor.pigments import PIGMENTS
from watercolor.rendering import render, render_view, sheen, transmitted
from watercolor.simulation import MASK_SEALED, Sheet
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


RIM = 30.0  # distance of a pool's edge from its centre, in cells
SHELF = 5.0  # width of the slope from the edge of a pool standing proud up to its level middle
ROWS, COLUMNS = torch.meshgrid(torch.arange(SIZE, device=DEVICE), torch.arange(SIZE, device=DEVICE), indexing="ij")
FROM_CENTRE = ((ROWS - CENTRE) ** 2 + (COLUMNS - CENTRE) ** 2).float().sqrt()
# Distance from the centre along the way the lamp's light travels, from the upper left to the lower right.
ALONG_THE_LIGHT = ((ROWS - CENTRE) + (COLUMNS - CENTRE)) / 2.0**0.5
SLOPE = (FROM_CENTRE > RIM - SHELF) & (FROM_CENTRE < RIM)
NEAR_SLOPE = SLOPE & (ALONG_THE_LIGHT < -15)  # the slope nearest the lamp
FAR_SLOPE = SLOPE & (ALONG_THE_LIGHT > 15)
# Where the slope of a pool standing proud turns over into its level middle, and where it meets the paper.
SHOULDER = (FROM_CENTRE > RIM - SHELF - 1.5) & (FROM_CENTRE < RIM - SHELF + 1.5)
EDGE = (FROM_CENTRE > RIM - 1.5) & (FROM_CENTRE < RIM + 0.5)


def pool_on_level_paper(depth: float = 0.6, shelf: float = 8.0) -> Sheet:
    """A round pool of clear water, level in the middle and shelving to nothing at its rim, on paper with no grain."""
    sheet = sheet_of(lying_flat(torch.full((SIZE, SIZE), 0.5, device=DEVICE)))
    sheet.water = (depth * (RIM - FROM_CENTRE) / shelf).clamp(0, depth)
    return sheet


def pool_standing_proud() -> Sheet:
    """A pool three times as deep as a flooded wash, with a steep slope at its rim."""
    return pool_on_level_paper(depth=2.0, shelf=SHELF)


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


def test_the_paper_is_lit_as_if_dry_under_level_water_and_under_none() -> None:
    sheet = sheet_of(lying_flat(generate_tooth(SIZE, SIZE, 3, DEVICE)))
    assert torch.allclose(transmitted(sheet), torch.ones(SIZE, SIZE, device=DEVICE))
    sheet.water[:] = 1.5
    assert torch.allclose(transmitted(sheet), torch.ones(SIZE, SIZE, device=DEVICE), atol=1e-5)


def test_a_pool_standing_proud_is_darker_under_the_slope_nearest_the_lamp_than_under_the_far_one() -> None:
    light = transmitted(pool_standing_proud())
    assert float(light[NEAR_SLOPE].mean()) < 0.95
    assert float(light[FAR_SLOPE].mean()) > float(light[NEAR_SLOPE].mean()) + 0.08


def test_a_pool_standing_proud_gathers_light_under_its_shoulder_and_loses_it_at_its_edge() -> None:
    light = transmitted(pool_standing_proud())
    # Taken all the way round the pool, so that the slant of the lamp's light cancels.
    assert float(light[SHOULDER].mean()) > 1.05
    assert float(light[EDGE].mean()) < 0.97
    assert float((light[FROM_CENTRE < 15] - 1.0).abs().max()) < 1e-3  # the level middle is lit as if dry


def test_the_colour_picture_shows_the_gathered_light_and_the_value_view_leaves_it_out() -> None:
    sheet = pool_standing_proud()
    sheet.deposited[:] = 1.0  # an even wash under the pool: bare paper is too near white to show a gain
    weights = torch.tensor([0.2126, 0.7152, 0.0722], device=DEVICE).reshape(3, 1, 1)
    shown = (weights * render(sheet)).sum(0)
    measured = render_view(sheet, "value")[0]
    far, near = SHOULDER & (ALONG_THE_LIGHT > 10), SHOULDER & (ALONG_THE_LIGHT < -10)
    # The far side faces away from the lamp, so nothing is mirrored there and the two differ only by the lens.
    assert float((shown / measured)[far].mean()) > 1.08
    assert abs(float(measured[far].mean()) - float(measured[near].mean())) < 0.005


def studio_with(paint: str) -> Studio:
    """A 128 px sheet with one paint."""
    sheet = Sheet(generate_paper(128, 128, 3, DEVICE), [PIGMENTS[paint]])
    return Studio({"painting": sheet}, [paint])


def test_a_pen_line_one_cell_wide_is_dark_and_leaves_its_neighbours_as_paper() -> None:
    """carbon_ink at 2 along one row. Measured: the line reads 0.003 and its neighbours exactly as bare paper; with
    every cell's paint shared with its neighbours they read 0.46."""
    studio = studio_with("carbon_ink")
    sheet = studio.sheets["painting"]
    bare = render_view(sheet, "value")[0].clone()
    studio.pen("painting", [[20, 64], [108, 64]], 1.0, {"carbon_ink": 2.0}, 120, smooth=False)
    value = render_view(sheet, "value")[0]
    assert float(value[64, 20:109].max()) < 0.02
    assert float((value[[63, 65], 20:109] - bare[[63, 65], 20:109]).abs().max()) < 0.01


def test_a_reserve_of_the_finest_masking_fluid_stays_white_beside_a_dark_wash() -> None:
    """Fluid at the smallest radius along one row, dark paint dried against it, then the fluid rubbed away. Measured:
    the reserve reads 0.943 at its darkest beside a wash of 0.29; with every cell's paint shared with its neighbours it
    read 0.62."""
    studio = studio_with("french_ultramarine")
    sheet = studio.sheets["painting"]
    studio.mask("painting", [[20, 64], [108, 64]], 0.5)
    sealed = sheet.mask >= MASK_SEALED
    sheet.deposited[0][~sealed] = 2.0
    studio.unmask("painting")
    assert float(render_view(sheet, "value")[0][sealed].min()) > 0.9

"""Painting in a batch must give each sheet the picture it would have had alone."""

import torch

from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.simulation import Sheet
from watercolor.studio import Studio
from watercolor.together import paint_together

SIZE = 96
PALETTE = ["cadmium_red", "french_ultramarine"]


def pool_and_dab(pigment: str, y: int):
    """A wet band with a strong dab dropped into it, on paper fixed about the dab, so the paint settled there is
    locked and the paint beside it is not; below the band, a stroke laid across a dry pen line as a new layer over it,
    and three pen lines of ink laid over one another, the last pressing the first down. Scripts made this way take
    the same time."""

    def script(studio: Studio) -> None:
        studio.pen("painting", [[20, y + 20], [76, y + 20]], 1.0, {pigment: 1.0}, 120, smooth=False)
        # Three layers of ink over the same cells: the second covers the first, and the third presses it down.
        for ink in ("cadmium_red", "french_ultramarine", "cadmium_red"):
            studio.pen("painting", [[20, y + 26], [76, y + 26]], 3.0, {ink: 2.0}, 120, smooth=False)
        studio.fix("painting", [[48, y]], 12)
        studio.load_brush("mop", 14, {pigment: 0.05}, 1.0)
        studio.stroke("painting", [[16, y], [80, y]], 120, smooth=False)
        studio.wait(2)
        studio.load_brush("round", 8, {pigment: 6.0}, 0.6)
        studio.stroke("painting", [[48, y]], 100, smooth=False, dwell=0.5)
        studio.load_brush("round", 4, {pigment: 2.0}, 1.0)
        studio.stroke("painting", [[40, y + 16], [56, y + 26]], 120, smooth=False)
        studio.wait(4)

    return script


def paint_alone(script, seed: int) -> Studio:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pigments = [PIGMENTS[name] for name in PALETTE]
    sheet = Sheet(generate_paper(SIZE, SIZE, seed, device), pigments)
    studio = Studio({"painting": sheet}, PALETTE)
    script(studio)
    return studio


def test_sheets_painted_together_match_sheets_painted_alone() -> None:
    scripts = [pool_and_dab("cadmium_red", 30), pool_and_dab("french_ultramarine", 62)]
    together = paint_together(scripts, SIZE, PALETTE, seeds=[1, 2])
    for script, seed, studio in zip(scripts, [1, 2], together):
        alone = paint_alone(script, seed).sheets["painting"]
        batched = studio.sheets["painting"]
        assert float(alone.buried.sum()) > 0.0 and float(alone.substrate_change.abs().sum()) > 0.0
        for name in ("water", "suspended", "deposited", "buried", "fixative", "substrate_change"):
            expected = getattr(alone, name)
            assert float((getattr(batched, name) - expected).abs().mean()) < 1e-3 * float(expected.abs().mean()), name
        assert bool((batched.dried_paint == alone.dried_paint).all())

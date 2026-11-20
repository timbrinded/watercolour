"""What the support a painting is begun on changes, and that the default, cold press, changes nothing.

Each bound is the behaviour itself, with the margin a painter would still accept. The value measured when the
supports were added is given beside each.
"""

import json
from pathlib import Path

import pytest
import torch
import torch.nn.functional as F
from PIL import Image

from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.rendering import render, render_view
from watercolor.session import Configuration, Session
from watercolor.simulation import SUPPORTS, Sheet, SimulationParameters, support_sheet
from watercolor.studio import Studio

SIZE = 128
SEED = 3
PALETTE = ["french_ultramarine"]
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
INK = (60, 90, 150)


def sheet_on(support: str) -> Sheet:
    return support_sheet(SUPPORTS[support], SIZE, SIZE, SEED, DEVICE, [PIGMENTS[name] for name in PALETTE])


def configuration(scrap_allowed: bool = False) -> Configuration:
    return Configuration(
        prompt="test",
        size=SIZE,
        seed=SEED,
        palette=PALETTE,
        stroke_budget=10,
        scrap_allowed=scrap_allowed,
        pencil_allowed=True,
    )


def drained_stroke(sheet: Sheet) -> None:
    """A drained round laid over and dragged fast across the middle of the sheet: a dry-brush stroke."""
    studio = Studio({"painting": sheet}, PALETTE)
    studio.load_brush("round", 8, {"french_ultramarine": 4.0}, 0.45)
    path = [{"x": 14, "y": 64, "pressure": 0.5, "angle": 55}, {"x": 114, "y": 64, "pressure": 0.5, "angle": 55}]
    studio.stroke("painting", path, 250, smooth=False)


def painted_share(sheet: Sheet) -> float:
    """Share of the core of the dry-brush stroke that took paint."""
    paint = (sheet.deposited + sheet.suspended)[0, 60:69, 30:100]
    return float((paint > 0.25 * paint.max()).float().mean())


def bare_grain(sheet: Sheet) -> float:
    """Spread of the bare sheet's value about its 5-pixel mean: the grain as an even light shows it."""
    value = render_view(sheet, "value")[0]
    fine = value - F.avg_pool2d(value[None, None], 5, stride=1, padding=2)[0, 0]
    return float(fine[4:-4, 4:-4].std())


def test_cold_press_is_the_sheet_every_earlier_painting_was_painted_on() -> None:
    """The default support is the paper generate_paper has always made, with the parameters always used.

    Its grain spans exactly 0 to 1, so the brush, the pencil and a thin film, which are measured down from the peak
    and up from the valley, meet it as they did before. When supports were added, a session on cold press was
    compared with 0.9.0 field by field and in its rendering, after a wash, a dry-brush stroke, a lift and a pencil
    line: it was the same to the bit.
    """
    on_support = sheet_on("cold_press")
    plain = Sheet(generate_paper(SIZE, SIZE, SEED, DEVICE), on_support.pigments)
    assert on_support.parameters == SimulationParameters()
    assert (on_support.peak, on_support.valley) == (1.0, 0.0)
    for sheet in (on_support, plain):
        drained_stroke(sheet)
    for name in ("tooth", "cockle", "sizing", "water", "suspended", "deposited"):
        assert torch.equal(getattr(on_support, name), getattr(plain, name)), name
    assert torch.equal(render(on_support), render(plain))


def test_bare_hot_press_shows_little_grain_and_bare_rough_shows_more_than_cold_press() -> None:
    """Measured: cold press 0.0080, hot press 0.0025, rough 0.0145."""
    cold_press = bare_grain(sheet_on("cold_press"))
    assert bare_grain(sheet_on("hot_press")) < 0.4 * cold_press
    assert bare_grain(sheet_on("rough")) > 1.5 * cold_press


def test_a_drained_brush_breaks_up_less_on_hot_press_than_on_rough() -> None:
    """The hairs reach a fixed depth below the highest peak. On hot press's shallow grain that is most of the
    surface, so the stroke is a tone mottled by the grain and broken where the hairs part; on rough it is only the
    broad tops, and the pits stay white. Measured share of the stroke's core painted: hot press 0.72, rough 0.34."""
    shares = {}
    for support in ("hot_press", "rough"):
        sheet = sheet_on(support)
        drained_stroke(sheet)
        shares[support] = painted_share(sheet)
    assert shares["hot_press"] > 1.5 * shares["rough"]


def test_a_printed_ground_tints_the_bare_sheet(tmp_path: Path) -> None:
    """White leaves the support as it is and ink multiplies it, on the painting and on the scrap cut from the middle
    of the same print. Measured: the inked half within 0.0001 of the ink's own colour, the white half unchanged."""
    printed = Image.new("RGB", (2 * SIZE, 2 * SIZE), "white")
    printed.paste(INK, (0, 0, SIZE, 2 * SIZE))  # the left half of the image, and so of the sheet
    printed.save(tmp_path / "print.png")
    plain = Session.create(tmp_path / "plain", configuration(scrap_allowed=True))
    grounded = Session.create(tmp_path / "grounded", configuration(scrap_allowed=True), tmp_path / "print.png")
    ink = torch.tensor(INK, device=DEVICE).reshape(3, 1, 1) / 255.0
    for sheet, inked, white in (
        ("painting", (slice(None), slice(0, SIZE // 2)), (slice(None), slice(SIZE // 2, None))),
        # The scrap is twice the painting's width: the print lies in its middle, on white.
        ("scrap", (slice(SIZE // 2, 3 * SIZE // 2), slice(SIZE // 2, SIZE)), (slice(None), slice(3 * SIZE // 2, None))),
    ):
        tint = render(grounded.studio.sheets[sheet]) / render(plain.studio.sheets[sheet])
        assert float((tint[:, *inked] - ink).abs().max()) < 0.01, sheet
        assert float((tint[:, *white] - 1.0).abs().max()) < 1e-6, sheet
    printed.resize((2 * SIZE, SIZE)).save(tmp_path / "wide.png")
    with pytest.raises(ValueError, match="proportions"):
        Session.create(tmp_path / "wide", configuration(), tmp_path / "wide.png")


def test_a_painting_begun_before_supports_existed_resumes_on_cold_press(tmp_path: Path) -> None:
    session = Session.create(tmp_path / "painting", configuration())
    session.paint([{"action": "load", "brush": "round", "size": 8, "pigments": {}, "water": 1.0}])
    written = json.loads((session.directory / "session.json").read_text())
    del written["support"], written["ground_digest"]
    (session.directory / "session.json").write_text(json.dumps(written))
    resumed = Session(session.directory)
    assert resumed.configuration.support == "cold_press"
    assert torch.equal(resumed.studio.sheets["painting"].tooth, generate_paper(SIZE, SIZE, SEED, DEVICE).tooth)

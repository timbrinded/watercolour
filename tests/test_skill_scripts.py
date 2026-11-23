"""The painting skill's measuring and planning scripts."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from measured_layers import PAPER
from passbuilder import budgeted
from PIL import Image
from preview_pass import painted_width
from style_target import remap_values

from watercolor.brushes import BRUSH_TYPES
from watercolor.session import BUDGETED_ACTIONS

SCRIPTS = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "paint-watercolour" / "scripts"


def test_a_flat_area_remaps_to_one_value_and_distinct_values_keep_their_order() -> None:
    value = np.full((100, 100), 0.5)
    value[58:, :] = 0.0  # a crushed shadow over 42% of the picture
    value[:10, :10] = 0.8
    remapped = remap_values(value, [(0.0, 0.0), (1.0, 1.0)])
    shadow, middle, light = remapped[58:, :], remapped[value == 0.5], remapped[:10, :10]
    assert shadow.max() == shadow.min()
    assert middle.max() == middle.min()
    assert shadow.max() < middle.min() < light.min()


@pytest.mark.parametrize("head", sorted(BRUSH_TYPES))
def test_every_head_of_the_harness_has_a_painted_width(head: str) -> None:
    assert painted_width(head, 10.0, 0.9) > 0


def test_a_head_without_a_painted_width_is_refused() -> None:
    with pytest.raises(SystemExit):
        painted_width("toothbrush", 10.0, 0.9)


def signature(*arguments: str) -> dict[str, str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "style_signature.py"), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    header, row = result.stdout.splitlines()
    return dict(zip(header.split(), row.split()))


def test_a_painting_with_no_bare_paper_is_measured_against_the_harness_paper(tmp_path: Path) -> None:
    session = tmp_path / "painting"
    (session / "looks").mkdir(parents=True)
    (session / "session.json").write_text(json.dumps({"prompt": "test"}))
    # paint everywhere, at half the paper's lightness: its lightest 1% is paint, not paper
    look = session / "looks" / "0000_painting_color.png"
    Image.new("RGB", (64, 48), (124, 122, 118)).save(look)
    copied = tmp_path / "copied.png"
    Image.new("RGB", (64, 48), (124, 122, 118)).save(copied)

    in_session = signature(str(look))
    given = signature("--white", "247,244,237", str(copied))

    assert in_session["white"] == "rig"
    assert float(in_session["p50"]) == pytest.approx(0.5, abs=0.01)
    assert float(given["p50"]) == pytest.approx(0.5, abs=0.01)


def test_a_pass_counts_what_the_session_counts_against_the_stroke_budget() -> None:
    counted = [{"action": kind, "path": [[10, 10]]} for kind in BUDGETED_ACTIONS]
    on_scrap = [dict(action, sheet="scrap") for action in counted]
    free = [{"action": kind} for kind in ("load", "drain", "wait", "dry", "tilt", "pencil", "erase")]
    assert budgeted(counted + on_scrap + free) == len(counted)


def test_a_preview_draws_a_pen_line_at_the_width_the_pen_draws_it(tmp_path: Path) -> None:
    reference, preview, actions = tmp_path / "reference.png", tmp_path / "preview.png", tmp_path / "pass.json"
    Image.new("RGB", (64, 48), (255, 255, 255)).save(reference)
    actions.write_text(
        json.dumps([{"action": "pen", "path": [[8, 24], [56, 24]], "width": 2, "ink": {"carbon_ink": 1}}])
    )
    subprocess.run(
        [sys.executable, str(SCRIPTS / "preview_pass.py"), str(reference), str(preview), str(actions)]
        + ["--sheet", "64,48", "--zoom", "1"],
        check=True,
        capture_output=True,
    )
    drawn = np.asarray(Image.open(preview).convert("L")).astype(float)
    assert drawn[24, 32] < 160
    assert drawn[27, 32] == 255
    assert drawn[24, 4] == 255


def test_a_painting_on_a_printed_ground_is_measured_against_the_page_it_was_printed_on(tmp_path: Path) -> None:
    session = tmp_path / "painting"
    (session / "looks").mkdir(parents=True)
    (session / "session.json").write_text(json.dumps({"prompt": "test"}))
    # a found page in a warm tone, with a printed black band over a quarter of it
    page = np.full((48, 64, 3), (230.0, 218.0, 186.0))
    page[:12] = 20.0
    Image.fromarray(page.astype(np.uint8)).save(session / "ground.png")
    # the unpainted sheet, as a look shows it: the harness's paper under the print
    look = session / "looks" / "0000_painting_color.png"
    Image.fromarray(np.round(PAPER * page / 255.0).astype(np.uint8)).save(look)

    measured = signature(str(look))

    assert measured["white"] == "rig"
    assert float(measured["p50"]) == pytest.approx(1.0, abs=0.01)
    assert float(measured["paper%"]) == pytest.approx(75.0, abs=3.0)


def scumble(tmp_path: Path, *options: str) -> list[dict]:
    """The pass scumble_lights.py writes for a dark sheet and a reference holding one slanting band of light."""
    reference = np.full((120, 160), 20, dtype=np.uint8)
    for x in range(20, 140):
        y = 20 + (x - 20) * 2 // 3  # the band falls two pixels in every three across
        reference[y - 4 : y + 5, x] = 200
    Image.fromarray(reference).convert("RGB").save(tmp_path / "reference.png")
    Image.new("RGB", (160, 120), (20, 20, 20)).save(tmp_path / "look.png")
    command = [
        sys.executable,
        str(SCRIPTS / "scumble_lights.py"),
        str(tmp_path / "reference.png"),
        str(tmp_path / "pass.json"),
    ]
    subprocess.run(
        [*command, "--sheet", "160,120", "--look", str(tmp_path / "look.png"), *options],
        check=True,
        capture_output=True,
    )
    return json.loads((tmp_path / "pass.json").read_text())


def test_lights_are_scumbled_along_a_band_of_light_and_nowhere_else(tmp_path: Path) -> None:
    actions = scumble(tmp_path, "--radius", "3")
    pressed = [point for action in actions for point in action["path"] if point[2] > 0]
    assert all(action["action"] == "draw" for action in actions)
    assert len(pressed) > 20
    assert all(abs(y - (20 + (x - 20) * 2 / 3)) < 8 for x, y, _ in pressed)  # every mark lies on the band
    runs = [(a, b) for action in actions for a, b in zip(action["path"], action["path"][1:]) if a[2] > 0 and b[2] > 0]
    along = [
        abs((b[0] - a[0]) * 3 + (b[1] - a[1]) * 2) / (13**0.5 * np.hypot(b[0] - a[0], b[1] - a[1])) for a, b in runs
    ]
    assert np.mean(along) > 0.95  # strokes run along the band, not across it


def test_body_colour_lights_are_brush_strokes_of_the_strength_the_light_needs(tmp_path: Path) -> None:
    actions = scumble(
        tmp_path, "--radius", "3", "--medium", "body_colour", "--stick", "opaque_white:1.0,yellow_ochre:1.0"
    )
    loads = [action for action in actions if action["action"] == "load"]
    strokes = [action for action in actions if action["action"] == "stroke"]
    assert len(loads) == len(strokes) > 0
    assert actions[-1] == {"action": "dry"}
    strengths = [sum(load["pigments"].values()) for load in loads]
    assert all(load["pigments"]["opaque_white"] == pytest.approx(load["pigments"]["yellow_ochre"]) for load in loads)
    assert max(strengths) > 4.5  # the middle of the band, far lighter than the sheet, takes paint that covers
    assert max(strengths) <= 7.5  # and no load is stronger than a brush can hold

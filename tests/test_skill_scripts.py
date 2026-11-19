"""The painting skill's measuring and planning scripts."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from preview_pass import painted_width
from style_target import remap_values

from watercolor.brushes import BRUSH_TYPES

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

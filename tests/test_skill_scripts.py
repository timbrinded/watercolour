"""The painting skill's measuring and planning scripts."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from measured_layers import PAPER
from passbuilder import budgeted
from PIL import Image, ImageDraw
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


def run_script(name: str, *arguments: object) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / name), *(str(argument) for argument in arguments)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def strokes_of(actions: Path) -> list[list[list[float]]]:
    return [action["path"] for action in json.loads(actions.read_text()) if action["action"] == "stroke"]


def disc(size: tuple[int, int], centre: tuple[float, float], radius: float) -> np.ndarray:
    yy, xx = np.mgrid[0 : size[1], 0 : size[0]]
    return (xx - centre[0]) ** 2 + (yy - centre[1]) ** 2 <= radius**2


def test_a_passage_kept_from_the_look_is_left_alone_by_a_measured_layer(tmp_path: Path) -> None:
    # the reference is a middle grey everywhere; on the sheet a pale yellow iris is already painted on bare paper
    reference, look, kept = tmp_path / "reference.png", tmp_path / "look.png", tmp_path / "kept.png"
    Image.new("RGB", (160, 120), (128, 128, 128)).save(reference)
    sheet = np.tile(PAPER, (120, 160, 1))
    iris = disc((160, 120), (80, 60), 26)
    sheet[iris] = (236, 222, 160)
    Image.fromarray(sheet.round().astype(np.uint8)).save(look)
    layer = ["--sheet", "160,120", "--paints", "cobalt_blue,burnt_sienna", "--brush", "round", "--size", "4"]

    run_script("measured_layers.py", reference, tmp_path / "plain.json", *layer, "--look", look)
    polygon = " ".join(f"{80 + 26 * np.cos(a):.1f},{60 + 26 * np.sin(a):.1f}" for a in np.linspace(0, 6.2, 24))
    run_script("keep_passage.py", reference, look, kept, "--sheet", "160,120", "--polygon", polygon)
    run_script("measured_layers.py", kept, tmp_path / "kept.json", *layer, "--look", look)

    def strokes_through_the_iris(actions: Path) -> int:
        """Strokes whose centre line passes over the iris, each line walked a pixel at a time."""
        through = 0
        for path in strokes_of(actions):
            line = np.array([point[:2] for point in path], dtype=float)
            steps = np.linspace(0, len(line) - 1, 4 * int(np.hypot(*np.diff(line, axis=0).T).sum()) + 2)
            xs = np.interp(steps, np.arange(len(line)), line[:, 0]).round().astype(int).clip(0, 159)
            ys = np.interp(steps, np.arange(len(line)), line[:, 1]).round().astype(int).clip(0, 119)
            through += bool(iris[ys, xs].any())
        return through

    assert strokes_through_the_iris(tmp_path / "plain.json") > 0  # measured against the grey, it is painted over
    assert strokes_through_the_iris(tmp_path / "kept.json") == 0
    assert len(strokes_of(tmp_path / "kept.json")) > 10  # and the rest of the sheet is still painted


def test_an_isolated_subject_leaves_the_borders_paper_and_stays_whole_where_it_runs_off_the_sheet(
    tmp_path: Path,
) -> None:
    photograph, mask = tmp_path / "photograph.png", tmp_path / "mask.png"
    room = np.full((120, 160, 3), 40, dtype=np.uint8)  # a dark room
    subject = np.zeros((120, 160), dtype=bool)
    subject[40:120, 50:110] = True  # stands clear of three borders and runs off the bottom
    room[subject] = (150, 120, 90)
    Image.fromarray(room).save(photograph)
    Image.fromarray((subject * 255).astype(np.uint8)).save(mask)

    run_script(
        "isolate_subject.py",
        photograph,
        mask,
        tmp_path / "out.png",
        "--sheet",
        "160,120",
        "--alpha",
        tmp_path / "a.png",
    )

    kept = np.asarray(Image.open(tmp_path / "a.png"))
    reference = np.asarray(Image.open(tmp_path / "out.png").convert("RGB"))
    assert kept[0].max() == 0 and kept[:, 0].max() == 0 and kept[:, -1].max() == 0
    assert (reference[0] == 255).all() and (reference[:, 0] == 255).all()
    assert kept[119, 80] == 255


def test_a_guide_drawn_beside_a_light_line_is_fitted_onto_it_and_the_line_is_painted_out(tmp_path: Path) -> None:
    reference, guides = tmp_path / "reference.png", tmp_path / "guides.json"
    fur = Image.new("RGB", (120, 100), (110, 100, 90))
    ImageDraw.Draw(fur).line([(20, 30), (100, 70)], fill=(250, 250, 250), width=2)  # a whisker, slope one half
    fur.save(reference)
    guides.write_text(json.dumps({"whisker": [[21.3, 27.3], [61.3, 47.3], [101.3, 67.3]]}))  # 3 pixels to one side

    run_script("fit_light_lines.py", reference, guides, "--sheet", "120,100", "--paths", tmp_path / "paths.json")
    run_script("fit_light_lines.py", reference, guides, "--sheet", "120,100", "--without", tmp_path / "without.png")

    fitted = np.array(json.loads((tmp_path / "paths.json").read_text())["whisker"])
    off_the_whisker = np.abs((fitted[:, 0] - 20) * 0.5 - (fitted[:, 1] - 30)) / np.hypot(0.5, 1.0)
    assert off_the_whisker.max() < 1.0
    without = np.asarray(Image.open(tmp_path / "without.png").convert("L"))
    assert without[50, 60] < 125  # the whisker's own pixel, now the colour of the fur


@pytest.fixture
def coat_on_paper(tmp_path: Path) -> tuple[Path, Path]:
    """A dark round coat on white paper, 60 pixels in radius at the middle of a 240 by 200 sheet, and its alpha."""
    coat = disc((240, 200), (120, 100), 60)
    picture = np.full((200, 240, 3), 255, dtype=np.uint8)
    picture[coat] = (70, 55, 40)
    Image.fromarray(picture).save(tmp_path / "reference.png")
    Image.fromarray((coat * 255).astype(np.uint8)).save(tmp_path / "alpha.png")
    return tmp_path / "reference.png", tmp_path / "alpha.png"


def test_every_outline_hair_leaves_the_coat_and_none_is_stronger_than_asked(
    coat_on_paper: tuple[Path, Path], tmp_path: Path
) -> None:
    reference, alpha = coat_on_paper
    hairs = tmp_path / "hairs.json"

    paints = ["--sheet", "240,200", "--paints", "cobalt_blue,burnt_umber,burnt_sienna"]
    run_script("coat_hairs.py", "outline", reference, alpha, hairs, *paints, "--strength", "0.4,1.7")
    actions = json.loads(hairs.read_text())

    from_the_middle = [[np.hypot(x - 120, y - 100) for x, y, *_ in path] for path in strokes_of(hairs)]
    assert len(from_the_middle) > 40
    assert all(distances[0] < 60 < distances[-1] for distances in from_the_middle)
    assert max(sum(action["pigments"].values()) for action in actions if action["action"] == "load") <= 1.7


def test_no_long_hair_crosses_a_rectangle_it_must_keep_off(coat_on_paper: tuple[Path, Path], tmp_path: Path) -> None:
    reference, alpha = coat_on_paper
    hairs = tmp_path / "hairs.json"
    paints = ["--sheet", "240,200", "--paints", "cobalt_blue,burnt_umber,burnt_sienna"]

    run_script(
        "coat_hairs.py",
        "long",
        reference,
        alpha,
        hairs,
        *paints,
        "--zone",
        "60,40,180,160:60:20,50",
        "--keep-off",
        "100,80,140,120",
    )

    points = [(x, y) for path in strokes_of(hairs) for x, y, *_ in path]
    assert len(strokes_of(hairs)) == 60
    assert not any(100 <= x <= 140 and 80 <= y <= 120 for x, y in points)


def test_a_softening_run_stays_outside_the_wash_and_out_of_what_must_keep_a_crisp_edge(
    coat_on_paper: tuple[Path, Path], tmp_path: Path
) -> None:
    _, alpha = coat_on_paper
    runs = tmp_path / "soften.json"

    run_script("soften_outline.py", alpha, runs, "--sheet", "240,200", "--keep-crisp", "60,20,180,70")

    points = [(x, y) for path in strokes_of(runs) for x, y, *_ in path]
    assert len(points) > 20
    assert all(np.hypot(x - 120, y - 100) > 60 for x, y in points)
    assert not any(60 <= x <= 180 and 20 <= y <= 70 for x, y in points)

"""Rules of a painting session: nothing is taken back, and the limits hold."""

import shutil
from pathlib import Path

import pytest

from watercolor.session import Configuration, RuleViolation, Session

STROKE = [
    {"action": "load", "brush": "round", "size": 8, "pigments": {"cobalt_blue": 1.0}, "water": 1.0},
    {"action": "stroke", "path": [[20, 30], [70, 30]]},
]


def new_session(directory: Path, stroke_budget: int = 10) -> Session:
    configuration = Configuration(
        prompt="test",
        size=96,
        seed=1,
        palette=["cobalt_blue"],
        stroke_budget=stroke_budget,
        scrap_allowed=False,
        pencil_allowed=True,
    )
    return Session.create(directory / "painting", configuration)


def test_restoring_an_earlier_state_is_refused(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    session.paint(STROKE)
    shutil.copy(session.directory / "state.pt", tmp_path / "earlier.pt")
    session.paint(STROKE)
    shutil.copy(tmp_path / "earlier.pt", session.directory / "state.pt")
    with pytest.raises(RuleViolation):
        Session(session.directory)


def test_a_pass_over_the_stroke_budget_is_refused_whole(tmp_path: Path) -> None:
    session = new_session(tmp_path, stroke_budget=1)
    session.paint(STROKE)
    with pytest.raises(RuleViolation):
        session.paint(STROKE)
    assert Session(session.directory).strokes_used == 1


def test_a_finished_painting_accepts_nothing_more(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    session.paint(STROKE)
    picture, video = session.finish()
    assert picture.exists() and video.exists()
    with pytest.raises(RuleViolation):
        Session(session.directory).paint(STROKE)


def test_stroke_whose_times_run_backward_is_refused(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    backward = [{"x": 10, "y": 10, "t": 0.0}, {"x": 40, "y": 10, "t": 1.0}, {"x": 70, "y": 10, "t": 0.5}]
    with pytest.raises(ValueError, match="backward"):
        session.paint([STROKE[0], {"action": "stroke", "path": backward}])
    assert session.strokes_used == 0


def test_draining_the_brush_lowers_its_fullness_and_keeps_its_strength(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    session.paint([STROKE[0]])
    loaded = session.studio.brush
    assert loaded is not None
    strength = list(loaded.concentration)
    session.paint([{"action": "drain", "water": 0.4}])
    drained = Session(session.directory).studio.brush
    assert drained is not None
    assert drained.fullness == pytest.approx(0.4, abs=0.01)
    assert drained.concentration == pytest.approx(strength)


def test_draining_cannot_fill_a_brush(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    session.paint([STROKE[0] | {"water": 0.3}])
    held = session.studio.brush
    assert held is not None
    before = held.reservoir
    session.paint([{"action": "drain", "water": 0.9}])
    assert held.reservoir == before


def test_draining_with_no_brush_in_hand_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no brush"):
        new_session(tmp_path).paint([{"action": "drain", "water": 0.4}])


def test_wetness_is_read_on_continuous_scales(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    session.paint(STROKE)
    painted, bare = session.wetness([(45, 30), (45, 80)])
    assert painted["film"] > 0.05
    assert bare == {"x": 45, "y": 80, "film": 0.0, "paper": 0.0}
    session.paint([{"action": "wait", "seconds": 8}])
    later = session.wetness([(45, 30)])[0]
    # The film thins as the paper beneath it fills: neither is a step from one named state to another.
    assert 0.0 < later["film"] < painted["film"]
    assert later["paper"] > painted["paper"]
    with pytest.raises(ValueError, match="off the sheet"):
        session.wetness([(200, 30)])


def test_waiting_for_the_film_to_thin_ends_when_it_has(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    session.paint(STROKE)
    started = session.studio.clock
    depth = session.wetness([(45, 30)])[0]["film"]
    session.paint([{"action": "wait", "seconds": 600, "at": [45, 30], "film": depth / 2}])
    assert session.wetness([(45, 30)])[0]["film"] <= depth / 2
    assert session.studio.clock - started < 600
    # Bare paper has no film to wait for, and a point off the sheet is refused.
    before = session.studio.clock
    session.paint([{"action": "wait", "seconds": 600, "at": [45, 80], "film": 0.1}])
    assert session.studio.clock == before
    with pytest.raises(ValueError, match="off the sheet"):
        session.paint([{"action": "wait", "seconds": 5, "at": [200, 30], "film": 0.1}])

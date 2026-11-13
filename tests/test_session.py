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

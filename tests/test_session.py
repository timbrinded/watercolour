"""Rules of a painting session: nothing is taken back, and the limits hold."""

import json
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from watercolor.cli import main
from watercolor.session import Configuration, RuleViolation, Session

STROKE = [
    {"action": "load", "brush": "round", "size": 8, "pigments": {"cobalt_blue": 1.0}, "water": 1.0},
    {"action": "stroke", "path": [[20, 30], [70, 30]]},
]
STROKE_THEN_WAIT = [*STROKE, {"action": "wait", "seconds": 4}]
# Two strokes, then a wait far longer than a test: a command given this is still at work when it is killed.
UNENDING_PASS = [*STROKE, STROKE[1], {"action": "wait", "seconds": 3600}]


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


def start_paint_command(session: Session, actions: list[dict]) -> subprocess.Popen:
    """Run the paint command on a painting as a process of its own, as a painter's tool would."""
    given = session.directory.parent / "pass.json"
    given.write_text(json.dumps(actions))
    command = [
        sys.executable,
        "-c",
        "from watercolor.cli import main; main()",
        "paint",
        str(session.directory),
        str(given),
    ]
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_for_strokes(command: subprocess.Popen, session: Session, count: int) -> None:
    """Wait until the running command has recorded this many strokes in the painting's log."""
    deadline = time.monotonic() + 120
    while (session.directory / "log.jsonl").read_text().count('"detail": {"action": "stroke"') < count:
        assert command.poll() is None, "the paint command ended before it could be interrupted"
        assert time.monotonic() < deadline, "the paint command recorded no strokes"
        time.sleep(0.05)


def kill(command: subprocess.Popen) -> None:
    command.send_signal(signal.SIGKILL)  # what a tool's timeout sends: it cannot be caught
    command.wait()


def cut_short_while_waiting(session: Session, spans_saved: int) -> None:
    """Make the session's next wait end as a kill would, once this many of its spans have been saved."""
    save = session.studio.while_waiting
    spans = iter(range(spans_saved))

    def save_until_killed() -> None:
        if next(spans, None) is None:
            raise KeyboardInterrupt
        save()

    session.studio.while_waiting = save_until_killed


def test_a_paint_command_killed_part_way_leaves_the_painting_usable(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    command = start_paint_command(session, UNENDING_PASS)
    try:
        wait_for_strokes(command, session, 2)
    finally:
        kill(command)
    survivor = Session(session.directory)
    assert survivor.strokes_used == 2
    stopped = survivor.report()["interrupted_pass"]
    assert (stopped["actions_completed"], stopped["actions_given"]) == (3, 4)


def test_a_second_command_is_refused_while_one_is_at_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session = new_session(tmp_path)
    monkeypatch.setattr(sys, "argv", ["watercolor", "status", str(session.directory)])
    command = start_paint_command(session, UNENDING_PASS)
    try:
        wait_for_strokes(command, session, 1)
        with pytest.raises(SystemExit):
            main()
        assert "another command is at work" in capsys.readouterr().err
    finally:
        kill(command)
    main()
    assert json.loads(capsys.readouterr().out)["strokes_used"] >= 1


def test_a_pass_cut_short_carries_on_from_where_it_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("watercolor.session.SAVE_INTERVAL", 0.0)
    whole = new_session(tmp_path / "whole")
    whole.paint(STROKE_THEN_WAIT)

    session = new_session(tmp_path / "cut")
    cut_short_while_waiting(session, spans_saved=3)
    with pytest.raises(KeyboardInterrupt):
        session.paint(STROKE_THEN_WAIT)
    frames = session.directory / "frames"
    recorded = len(list(frames.iterdir()))

    resumed = Session(session.directory)
    # The frame recorded after the last save shows time that was not kept.
    assert len(list(frames.iterdir())) == recorded - 1
    stopped = resumed.interruption()
    assert stopped is not None
    assert (stopped.completed, stopped.given) == (2, 3)
    assert 0 < stopped.waited < 4
    # The stroke is not laid twice, and the wait lasts in all what was asked of it.
    assert resumed.paint(STROKE_THEN_WAIT) == 2
    assert resumed.strokes_used == 1
    assert resumed.studio.clock == pytest.approx(whole.studio.clock, abs=0.01)
    assert resumed.interruption() is None


def test_a_pass_cut_short_in_its_first_action_is_begun_again_whole(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    session.paint(STROKE)
    started = session.studio.clock
    wait = [{"action": "wait", "seconds": 5}]
    cut_short_while_waiting(session, spans_saved=0)
    with pytest.raises(KeyboardInterrupt):
        session.paint(wait)
    reopened = Session(session.directory)
    assert reopened.studio.clock == started
    assert reopened.paint(wait) == 0
    assert reopened.studio.clock == pytest.approx(started + 5)


def test_a_save_the_log_records_is_used_though_it_was_not_yet_put_in_place(tmp_path: Path) -> None:
    session = new_session(tmp_path)
    shutil.copy(session.directory / "state.pt", tmp_path / "earlier.pt")
    session.paint(STROKE)
    # The files as they stand when a command is killed between recording a save and putting it in place.
    shutil.move(session.directory / "state.pt", session.directory / "state.pending.pt")
    shutil.copy(tmp_path / "earlier.pt", session.directory / "state.pt")
    assert Session(session.directory).strokes_used == 1

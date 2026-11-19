"""The global gates of the calibration suite as tests, run with pytest --calibration.

They hold every change to the engine to ordinary watercolour behaviour, its invariants and its compatibility with
paintings begun on 0.8.0, against the baseline recorded on 0.8.0 in trials/calibration_baseline.json. The scenarios
run once, in parallel, through trials/calibration.py; each gate is reported as its own test, and only the gates of
the tests selected are painted (pytest --calibration -k I-determinism paints that gate's scenarios alone).
Repainting them takes several times as long as the rest of the tests, so the ordinary test command skips them. The
gates of a change not yet built, and the long ones, run through trials/calibration.py alone.
"""

import pytest
from calibration import describe, run_gates, select_gates
from calibration_gates import Gate

pytestmark = pytest.mark.calibration

GLOBAL_GATES = select_gates(["global"])


@pytest.fixture(scope="module")
def outcome(request: pytest.FixtureRequest) -> dict:
    selected: set[str] = set()
    for item in request.session.items:
        gate = (
            item.callspec.params.get("gate")
            if isinstance(item, pytest.Function) and hasattr(item, "callspec")
            else None
        )
        if isinstance(gate, Gate):
            selected.add(gate.id)
    return run_gates([gate for gate in GLOBAL_GATES if gate.id in selected])["gates"]


@pytest.mark.parametrize("gate", GLOBAL_GATES, ids=lambda gate: gate.id)
def test_gate(outcome: dict, gate: Gate) -> None:
    assert outcome[gate.id]["status"] == "pass", describe(gate, outcome[gate.id])

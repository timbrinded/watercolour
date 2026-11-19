"""The global gates of the calibration suite, under the ordinary test command.

They hold every change to the engine to ordinary watercolour behaviour, its invariants and its compatibility with
paintings begun on 0.8.0, against the baseline recorded on 0.8.0 in trials/calibration_baseline.json. The scenarios
run once, in parallel, through trials/calibration.py; each gate is reported as its own test. The gates of a change
not yet built, and the long ones, run through trials/calibration.py alone.
"""

import pytest
from calibration import describe, run_gates
from calibration_gates import GATES, Gate

GLOBAL_GATES = [gate for gate in GATES if gate.item == "global" and not gate.extended]


@pytest.fixture(scope="module")
def outcome() -> dict:
    return run_gates(GLOBAL_GATES)["gates"]


@pytest.mark.parametrize("gate", GLOBAL_GATES, ids=lambda gate: gate.id)
def test_gate(outcome: dict, gate: Gate) -> None:
    assert outcome[gate.id]["status"] == "pass", describe(gate, outcome[gate.id])

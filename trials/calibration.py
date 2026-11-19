"""The calibration suite: run the scenarios that the chosen gates need, evaluate the gates, and compare with the
baseline recorded on the 0.8.0 rig.

    PYTHONPATH=src:trials python trials/calibration.py [--item ITEM ...] [--kind KIND ...] [--gate ID ...]
        [--extended] [--jobs N] [--output RESULTS.json] [--baseline BASELINE.json] [--record] [--list]

With no selection every gate of the standard run is evaluated. Paintings of one family are painted together in one
batch, and families and experiments run in parallel processes, so the standard run takes a few minutes on the GPU.
The command exits with status 1 if any selected gate fails. With --record the run is written as the baseline, and
the command fails instead if any gate does not do what it is expected to do on the baseline.

Performance gates are evaluated by trials/benchmark.py, which must run alone on the machine.
"""

import argparse
import hashlib
import itertools
import json
import math
import multiprocessing
import os
import subprocess
import sys
import time
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import torch
from calibration_gates import GATES, GATES_BY_ID, ITEMS, KINDS, Check, Gate
from calibration_scenarios import (
    DERIVED,
    EXPERIMENTS,
    PAINTINGS,
    REPOSITORY,
    Measurement,
    Measurements,
    default_device,
    paint_family,
    reference_source,
    run_experiment,
)

import watercolor

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "calibration_baseline.json"
DEFAULT_JOBS = 8
Results = dict[str, Measurements]
Job = tuple[str, str, tuple[str, ...]]  # ("family" or "group", its name, the scenarios in it)


# ------------------------------------------------------------------------------------------------ selection


def select_gates(
    items: Iterable[str] = (), kinds: Iterable[str] = (), ids: Iterable[str] = (), extended: bool = False
) -> list[Gate]:
    """Gates chosen by id, or else by item and kind. Extended gates come only by id or with extended."""
    ids = list(ids)
    if ids:
        unknown = [gate_id for gate_id in ids if gate_id not in GATES_BY_ID]
        if unknown:
            raise SystemExit(f"unknown gate {', '.join(unknown)}")
        return [GATES_BY_ID[gate_id] for gate_id in ids]
    items, kinds = set(items), set(kinds)
    return [
        gate
        for gate in GATES
        if (not items or gate.item in items)
        and (not kinds or gate.kind in kinds)
        and (extended or not gate.extended)
        and gate.kind != "performance"
    ]


def split_metric(metric: str) -> tuple[str, str]:
    """The scenario and the measurement a metric names. Scenario names may hold a point (glaze_disturbance_0.5), so
    the longest scenario name that the metric begins with is taken; scenarios measured by the benchmark are
    named 'benchmark'."""
    known = [name for name in (*PAINTINGS, *EXPERIMENTS, *DERIVED, "benchmark") if metric.startswith(f"{name}.")]
    if not known:
        raise KeyError(f"no scenario provides {metric}")
    scenario = max(known, key=len)
    return scenario, metric[len(scenario) + 1 :]


def scenario_of(metric: str) -> str:
    return split_metric(metric)[0]


def required_scenarios(gates: Iterable[Gate]) -> set[str]:
    """The scenarios the gates measure, with every painting of each family they touch.

    What a painting measures in a batch can depend, by rounding, on the paintings beside it: on 0.8.0 the commute
    paintings differ by 3e-8 between the standard run and a run of the global gates alone. Families are therefore
    always painted whole, so that any selection of gates measures exactly what the baseline did.
    """
    needed: set[str] = set()
    for gate in gates:
        for check in gate.checks:
            name = scenario_of(check.metric)
            if name in DERIVED:
                needed.update(DERIVED[name][0])
            elif name in PAINTINGS or name in EXPERIMENTS:
                needed.add(name)
            else:
                raise KeyError(f"gate {gate.id} measures {check.metric}, which no scenario provides")
    families = {PAINTINGS[name].family for name in needed if name in PAINTINGS}
    needed.update(name for name, painting in PAINTINGS.items() if painting.family in families)
    return needed


def plan_jobs(scenarios: set[str], timings: dict[str, float]) -> list[Job]:
    """Families of paintings and groups of experiments, longest first by the times of an earlier run."""
    jobs: dict[tuple[str, str], list[str]] = {}
    for name in sorted(scenarios):
        if name in PAINTINGS:
            jobs.setdefault(("family", PAINTINGS[name].family), []).append(name)
        else:
            jobs.setdefault(("group", EXPERIMENTS[name].group), []).append(name)
    planned = [(kind, name, tuple(members)) for (kind, name), members in jobs.items()]
    return sorted(planned, key=lambda job: -timings.get(job[1], 60.0))


# ------------------------------------------------------------------------------------------------ running


def _start_worker(threads: int) -> None:
    torch.set_num_threads(threads)


def perform(job: Job) -> tuple[Results, float]:
    """Run one job in a worker process: a family painted together, or a group of experiments in turn."""
    kind, _, members = job
    started = time.perf_counter()
    if kind == "family":
        results = paint_family(list(members))
    else:
        results = {}
        for name in members:
            began = time.perf_counter()
            results[name] = run_experiment(name) | {"wall_seconds": round(time.perf_counter() - began, 1)}
    return results, time.perf_counter() - started


def run_scenarios(scenarios: set[str], workers: int, timings: dict[str, float]) -> tuple[Results, dict[str, float]]:
    """Run the scenarios, each job in its own process, and return their measurements and the time each job took."""
    reference_source()  # taken from git once, before the workers start
    jobs = plan_jobs(scenarios, timings)
    workers = max(1, min(workers, len(jobs)))
    threads = max(1, (os.cpu_count() or 1) // workers)
    results: Results = {}
    seconds: dict[str, float] = {}
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(workers, mp_context=context, initializer=_start_worker, initargs=(threads,)) as pool:
        futures = {pool.submit(perform, job): job for job in jobs}
        for future, job in futures.items():
            measured, elapsed = future.result()
            results.update(measured)
            seconds[job[1]] = round(elapsed, 1)
            print(f"  {job[1]:<20s} {elapsed:6.1f} s  ({len(job[2])} scenarios)", file=sys.stderr, flush=True)
    # A measurement is derived only in a run that holds every scenario it is derived from, so that a run of some
    # gates never records one made from part of its sources.
    for name, (sources, derive) in DERIVED.items():
        if all(source in results for source in sources):
            results[name] = derive(results)
    return results, seconds


# ------------------------------------------------------------------------------------------------ evaluation


def lookup(results: Results, metric: str) -> Measurement:
    scenario, measurement = split_metric(metric)
    found = results.get(scenario)
    if found is None or "error" in found:
        return None
    return found.get(measurement)


def _numbers(value: Measurement) -> list[float] | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, list) and all(isinstance(v, int | float) and not isinstance(v, bool) for v in value):
        return [float(v) for v in value]
    return None


def _scaled(bound: float, check: Check, base: float | None) -> float | None:
    if check.scale == "absolute":
        return bound
    if base is None:
        return None
    return bound * base if check.scale == "baseline" else base + bound


def check_passes(check: Check, value: Measurement, baseline: Measurement) -> bool:
    """Whether a measurement meets a check; a missing measurement or baseline never does."""
    if check.op == "==" and (check.bound is None or isinstance(check.bound, bool | tuple | str)):
        expected = list(check.bound) if isinstance(check.bound, tuple) else check.bound
        return value is not None and value == expected
    values = _numbers(value)
    if values is None or any(math.isnan(v) for v in values):
        return False
    if check.op in ("increasing", "decreasing", "nondecreasing"):
        pairs = list(itertools.pairwise(values))
        if check.op == "increasing":
            return all(b > a for a, b in pairs)
        if check.op == "decreasing":
            return all(b < a for a, b in pairs)
        return all(b >= a for a, b in pairs)
    bases: list[float | None] = [None] * len(values)
    if check.scale != "absolute" or check.op == "near":
        base_values = _numbers(baseline)
        if base_values is None or len(base_values) != len(values):
            return False
        bases = list(base_values)
    for v, base in zip(values, bases):
        if check.op == "near":
            if base is None or not isinstance(check.bound, int | float) or abs(v - base) > check.bound:
                return False
            continue
        if check.op == "between":
            if not isinstance(check.bound, tuple) or len(check.bound) != 2:
                raise TypeError(f"{check.metric}: 'between' needs a pair")
            low, high = (_scaled(float(edge), check, base) for edge in check.bound)
            if low is None or high is None or not low <= v <= high:
                return False
            continue
        if not isinstance(check.bound, int | float):
            raise TypeError(f"{check.metric}: '{check.op}' needs a number")
        limit = _scaled(float(check.bound), check, base)
        if limit is None:
            return False
        if not {"<=": v <= limit, "<": v < limit, ">=": v >= limit, ">": v > limit, "==": v == limit}[check.op]:
            return False
    return True


def evaluate(gates: Iterable[Gate], results: Results, baseline: Results) -> dict[str, dict]:
    """Every check of every gate, with the value, the baseline value and whether it passed."""
    outcome = {}
    for gate in gates:
        checks = []
        for check in gate.checks:
            value, base = lookup(results, check.metric), lookup(baseline, check.metric)
            checks.append(
                {
                    "metric": check.metric,
                    "op": check.op,
                    "bound": list(check.bound) if isinstance(check.bound, tuple) else check.bound,
                    "scale": check.scale,
                    "value": value,
                    "baseline": base,
                    "passed": check_passes(check, value, base),
                }
            )
        errors = {
            scenario_of(check.metric): results[scenario_of(check.metric)]["error"]
            for check in gate.checks
            if "error" in results.get(scenario_of(check.metric), {})
        }
        outcome[gate.id] = {
            "status": "pass" if all(c["passed"] for c in checks) else "fail",
            "item": gate.item,
            "kind": gate.kind,
            "expected_on_baseline": gate.expected_on_baseline,
            "checks": checks,
            **({"errors": errors} if errors else {}),
        }
    return outcome


def _short(value: Measurement) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, list):
        return "[" + ", ".join(_short(v) for v in value[:8]) + (", ..." if len(value) > 8 else "") + "]"
    return str(value)


def describe(gate: Gate, outcome: dict) -> str:
    """One line per check: what was measured against what bound."""
    lines = [f"{gate.id} ({gate.item}, {gate.kind}): {outcome['status']}"]
    for check in outcome["checks"]:
        bound = check["bound"]
        if check["scale"] == "baseline":
            bound = f"{_short(bound)} x baseline"
        elif check["scale"] == "baseline_plus":
            bound = f"baseline + {_short(bound)}"
        mark = "ok  " if check["passed"] else "FAIL"
        lines.append(
            f"  {mark} {check['metric']} = {_short(check['value'])} {check['op']} {_short(bound)}"
            f"  (baseline {_short(check['baseline'])})"
        )
    for scenario, error in outcome.get("errors", {}).items():
        lines.append(f"  error in {scenario}: {error.strip().splitlines()[-1]}")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ the run as a whole


def load_baseline(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def revision() -> str:
    run = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return run.stdout.strip()


def engine_digest() -> str:
    """Digest of the engine's source, which says whether two runs measured the same engine."""
    source = Path(watercolor.__file__).parent
    digest = hashlib.sha256()
    for path in sorted(source.glob("*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def run_gates(gates: list[Gate], baseline_path: Path = BASELINE, workers: int = DEFAULT_JOBS) -> dict:
    """Run what the gates need and evaluate them against the baseline; the record of the run."""
    baseline = load_baseline(baseline_path)
    started = time.perf_counter()
    results, seconds = run_scenarios(required_scenarios(gates), workers, baseline.get("timings", {}))
    return {
        "revision": revision(),
        "engine_digest": engine_digest(),
        "engine_version": watercolor.ENGINE_VERSION,
        "device": str(default_device()),
        "torch": torch.__version__,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "timings": seconds,
        "measurements": results,
        "gates": evaluate(gates, results, baseline.get("measurements", {})),
    }


def merged(baseline: dict, record: dict) -> dict:
    """The baseline with a new recording laid over it, so that gates recorded in separate runs (the standard run
    and the extended one) share one file. Both must have measured the same engine. Each scenario's entry is
    replaced whole, so that a measurement a scenario no longer takes leaves the baseline with it."""
    if baseline.get("engine_digest") != record["engine_digest"]:
        return record
    combined = dict(record)
    for part in ("timings", "measurements", "gates"):
        combined[part] = baseline.get(part, {}) | record[part]
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--item", nargs="*", default=[], choices=(*ITEMS, "global"))
    parser.add_argument("--kind", nargs="*", default=[], choices=[kind for kind in KINDS if kind != "performance"])
    parser.add_argument("--gate", nargs="*", default=[], metavar="ID")
    parser.add_argument("--extended", action="store_true", help="include the gates too long for the standard run")
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS, help="worker processes")
    parser.add_argument("--output", type=Path, help="write the run as JSON here")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--record", action="store_true", help="write the run as the baseline")
    parser.add_argument("--list", action="store_true", help="list the selected gates and stop")
    arguments = parser.parse_args()

    gates = select_gates(arguments.item, arguments.kind, arguments.gate, arguments.extended)
    if arguments.list:
        for gate in gates:
            print(f"{gate.id:42s} {gate.item:15s} {gate.kind:14s} {gate.threshold}")
        return
    print(f"{len(gates)} gates, {len(required_scenarios(gates))} scenarios", file=sys.stderr, flush=True)
    record = run_gates(gates, arguments.baseline, arguments.jobs)
    if arguments.record:
        # On the baseline every relative bound is measured against the run itself.
        record["gates"] = evaluate(gates, record["measurements"], record["measurements"])
    for gate in gates:
        print(describe(gate, record["gates"][gate.id]))
    failed = [gate.id for gate in gates if record["gates"][gate.id]["status"] == "fail"]
    unexpected = [
        gate.id for gate in gates if record["gates"][gate.id]["status"] != gate.expected_on_baseline
    ]  # fmt: skip
    print(f"\n{len(gates) - len(failed)} of {len(gates)} gates pass in {record['elapsed_seconds']} s")
    if arguments.output:
        arguments.output.write_text(json.dumps(record, indent=1) + "\n")
    if arguments.record:
        if unexpected:
            print(f"not as expected on the baseline: {', '.join(unexpected)}")
            sys.exit(1)
        arguments.baseline.write_text(json.dumps(merged(load_baseline(arguments.baseline), record), indent=1) + "\n")
        return
    if failed:
        print(f"failing: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

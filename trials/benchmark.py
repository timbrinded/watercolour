"""What the engine costs: wall time per simulated second of the wet phase and of the drying phase, render time, and
checkpoint time and size, on a 770x540 sheet, with the further measurements the performance gates need. Each time
is taken after a warm-up, over several repeats, and written with its spread.

    PYTHONPATH=src:trials python trials/benchmark.py [--repeats 5] [--sections NAME ...] [--output RESULTS.json]
        [--baseline trials/benchmark_baseline.json] [--record]

Run it alone on the machine: other work on the graphics card makes the times meaningless. The performance gates of
trials/calibration_gates.py are evaluated against the baseline recorded on the 0.8.0 rig, and the command exits
with status 1 if any fails, or if the card or the processors were busy when it began, since its times then bind
nothing. With --record the sections run are written into the baseline instead, which is refused on a busy machine.
"""

import argparse
import io
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import torch
from calibration import describe, engine_digest, evaluate, load_baseline, revision
from calibration_gates import GATES
from calibration_scenarios import Measurements, levelling_rates, slope_runs, thin_film_on_damp_paper
from torch import Tensor
from torch.profiler import ProfilerActivity, profile

import watercolor
from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.recording import FrameRecorder
from watercolor.rendering import render
from watercolor.session import Configuration, Session
from watercolor.simulation import Sheet
from watercolor.studio import Studio

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "benchmark_baseline.json"
HEIGHT, WIDTH = 540, 770
SIX = ("french_ultramarine", "burnt_umber", "quinacridone_rose", "phthalo_green", "cadmium_red", "opaque_white")
THREE = ("cadmium_red", "french_ultramarine", "burnt_umber")
# The machine counts as idle when the card is busy no more than this share of the time before the run, and the
# processors' one-minute load average is below this. Other agents' processor load once slowed a recording by 5-20%.
IDLE_CARD_UTILISATION = 10
IDLE_LOAD_AVERAGE = 2.0
WET_SECONDS = 2.0
DRY_SECONDS = 40.0
# A dry advance is quick, so each sample of it is the sum of several, to keep the timer's own noise out of it.
DRY_ADVANCES = 5
Metrics = Measurements


def device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def synchronise() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def timed(action: Callable[[], object]) -> float:
    synchronise()
    started = time.perf_counter()
    action()
    synchronise()
    return time.perf_counter() - started


def summary(name: str, samples: list[float]) -> Metrics:
    """The median of the samples under the name, and their spread beside it."""
    middle = statistics.median(samples)
    return {
        name: middle,
        f"{name}_spread": (max(samples) - min(samples)) / middle if middle else None,
        f"{name}_samples": samples,
    }


def new_sheet(height: int, width: int, palette: tuple[str, ...], on: torch.device | None = None) -> Sheet:
    return Sheet(generate_paper(height, width, 5, on or device()), [PIGMENTS[name] for name in palette])


# Fields the approved items add, by item. Each item's allowance of memory is held against its own fields, so that
# in one pull request the fields of the others do not count against it. Beside its two layers the ordered-layer
# design keeps a transient flag of the paint that has set, which its prototype names _set.
GUM_FIELDS = ("gum",)
LAYER_FIELDS = ("underlying", "lowest", "_set")
NEW_FIELDS = GUM_FIELDS + LAYER_FIELDS


def tensor_bytes(sheet: Sheet, leaving_out: tuple[str, ...] = ()) -> int:
    return sum(
        value.numel() * value.element_size()
        for name, value in vars(sheet).items()
        if isinstance(value, Tensor) and name not in leaving_out
    )


def saved_bytes(state: object) -> int:
    buffer = io.BytesIO()
    torch.save(state, buffer)
    return buffer.getbuffer().nbytes


def state_bytes(sheet: Sheet, leaving_out: tuple[str, ...] = ()) -> int:
    return saved_bytes({name: field for name, field in sheet.state().items() if name not in leaving_out})


def lay_wash(sheet: Sheet) -> None:
    """A wash over most of the sheet set directly, in bands of each pigment, over a dried earlier layer of umber,
    with strong dabs of the last pigments dropped into it. Set rather than painted, so that it is the same every
    time and costs nothing to make."""
    height, width = sheet.height, sheet.width
    noise = torch.Generator(device="cpu").manual_seed(11)
    rows, columns = slice(height // 12, height - height // 12), slice(width // 12, width - width // 12)
    sheet.deposited[1 % len(sheet.pigments), : height // 2, columns] = 0.6
    sheet.water[rows, columns] = 0.8 + 0.1 * torch.rand(height, width, generator=noise)[rows, columns].to(sheet.water)
    count = len(sheet.pigments)
    band = (rows.stop - rows.start) // count
    for index in range(count):
        top = rows.start + index * band
        sheet.suspended[index, top : top + band, columns] = 0.5 * sheet.water[top : top + band, columns]
    distance = torch.hypot(sheet._xs - width / 2, sheet._ys - height / 2)
    sheet.suspended[count - 1] += 3.0 * sheet.water * (distance < height / 8)
    sheet._used.update(range(count))


def wet_and_dry_cost(repeats: int) -> Metrics:
    """The 770x540 sheet with six pigments: wet advance from the laid wash, dry advance with the film removed and
    the paper at 0.8 of its capacity, rendering, saving and loading its state, and memory."""
    allocated = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
    sheet = new_sheet(HEIGHT, WIDTH, SIX)
    resident = torch.cuda.memory_allocated() - allocated if torch.cuda.is_available() else None
    lay_wash(sheet)
    laid = {name: field.clone() for name, field in sheet.state().items()}
    wash = sheet.water > 0

    def to_laid() -> None:
        sheet.load_state(laid)

    def to_damp() -> None:
        sheet.load_state(laid)
        sheet.water.zero_()
        sheet.saturation.copy_(0.8 * sheet.capacity * wash)

    to_laid()
    sheet.advance(0.5)
    to_damp()
    sheet.advance(2.0)
    wet, dry = [], []
    for _ in range(repeats):
        to_laid()
        wet.append(timed(lambda: sheet.advance(WET_SECONDS)) / WET_SECONDS)
        spent = 0.0
        for _ in range(DRY_ADVANCES):
            to_damp()
            spent += timed(lambda: sheet.advance(DRY_SECONDS))
        dry.append(spent / (DRY_ADVANCES * DRY_SECONDS))
    out: Metrics = {**summary("wet_seconds_per_second", wet), **summary("dry_seconds_per_second", dry)}

    peak = None
    if torch.cuda.is_available():
        to_laid()
        synchronise()
        before = torch.cuda.memory_allocated()
        torch.cuda.reset_peak_memory_stats()
        sheet.advance(1.0)
        synchronise()
        peak = torch.cuda.max_memory_allocated() - before
    out |= {"sheet_bytes": tensor_bytes(sheet), "resident_bytes": resident, "peak_wet_bytes": peak}

    to_laid()
    sheet.advance(1.0)
    render(sheet)
    out |= summary("render_seconds", [timed(lambda: render(sheet)) for _ in range(9)])
    to_damp()
    sheet.advance(DRY_SECONDS)
    out |= summary("dry_render_seconds", [timed(lambda: render(sheet)) for _ in range(9)])

    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "state.pt"
        saving = [timed(lambda: torch.save(sheet.state(), path)) for _ in range(repeats)]
        loading = [timed(lambda: sheet.load_state(torch.load(path, weights_only=True))) for _ in range(repeats)]
        out |= summary("checkpoint_seconds", saving) | summary("load_seconds", loading)
        out["checkpoint_bytes"] = path.stat().st_size

    # Processor time of this process, sampled as the wall times are: a dry sample is the sum of several advances, so
    # that a few milliseconds of other work in the process do not swamp it.
    wet_process, dry_process = [], []
    for _ in range(repeats):
        to_laid()
        started = time.process_time()
        timed(lambda: sheet.advance(WET_SECONDS))
        wet_process.append((time.process_time() - started) / WET_SECONDS)
        spent = 0.0
        for _ in range(DRY_ADVANCES):
            to_damp()
            started = time.process_time()
            timed(lambda: sheet.advance(DRY_SECONDS))
            spent += time.process_time() - started
        dry_process.append(spent / (DRY_ADVANCES * DRY_SECONDS))
    out |= summary("wet_process_seconds_per_second", wet_process) | summary(
        "dry_process_seconds_per_second", dry_process
    )
    for phase, prepare, seconds in (("wet", to_laid, 1.0), ("dry", to_damp, 10.0)):
        prepare()
        kernels, device_seconds = device_work(lambda seconds=seconds: sheet.advance(seconds))
        out[f"{phase}_kernels_per_second"] = None if kernels is None else kernels / seconds
        out[f"{phase}_device_seconds_per_second"] = None if device_seconds is None else device_seconds / seconds
    return out


def device_work(action: Callable[[], object]) -> tuple[int | None, float | None]:
    """Number of operations the graphics card ran during the action, and the seconds it spent on them."""
    if not torch.cuda.is_available():
        return None, None
    with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as profiler:
        action()
        synchronise()
    events = profiler.events() or []
    on_device = [event for event in events if event.device_type == torch.autograd.DeviceType.CUDA]
    return len(on_device), sum(event.device_time for event in on_device) / 1e6


def sizes() -> Metrics:
    """Tensor bytes of a sheet, and bytes of its saved state, for the sheets the memory gates name: in all, and
    leaving out the fields of the binder, of the ordered layers, or of both."""
    out: Metrics = {}
    cpu = torch.device("cpu")
    for height, width, label, palette in (
        (256, 256, "256_3", THREE),
        (256, 256, "256_6", SIX),
        (HEIGHT, WIDTH, "770_6", SIX),
        (HEIGHT, WIDTH, "770_13", tuple(PIGMENTS)),
    ):
        sheet = new_sheet(height, width, palette, cpu)
        for suffix, leaving_out in (
            ("", ()),
            ("_kept", NEW_FIELDS),
            ("_without_gum", GUM_FIELDS),
            ("_without_layers", LAYER_FIELDS),
        ):
            out[f"sheet_bytes_{label}{suffix}"] = tensor_bytes(sheet, leaving_out)
            out[f"state_bytes_{label}{suffix}"] = state_bytes(sheet, leaving_out)
    return out


def session_state() -> Metrics:
    """state.pt of a 64-pixel painting after two strokes and a wait."""
    with tempfile.TemporaryDirectory() as work:
        configuration = Configuration(
            prompt="benchmark", size=64, seed=1, palette=["quinacridone_rose", "french_ultramarine"],
            stroke_budget=10, scrap_allowed=False, pencil_allowed=False,
        )  # fmt: skip
        session = Session.create(Path(work) / "painting", configuration)
        session.paint(
            [
                {"action": "load", "brush": "round", "size": 6, "pigments": {"quinacridone_rose": 1.0}, "water": 1.0},
                {"action": "stroke", "path": [[10, 32], [54, 32]]},
                {"action": "stroke", "path": [[10, 40], [54, 40]]},
                {"action": "wait", "seconds": 2},
            ]
        )
        saved = torch.load(session.directory / "state.pt", weights_only=True)
        for state in saved["sheets"].values():
            for name in LAYER_FIELDS:
                state.pop(name, None)
        return {
            "session_state_bytes": (session.directory / "state.pt").stat().st_size,
            "session_state_bytes_without_layers": saved_bytes(saved),
        }


def strokes(repeats: int) -> Metrics:
    """Wall time per Studio.stroke at 256 px: four round-10 strokes of rose 2.0 and one clear flat-8 lifting stroke."""
    palette = ["quinacridone_rose", "french_ultramarine"]
    sheet = new_sheet(256, 256, tuple(palette))
    empty = sheet.state()
    studio = Studio({"painting": sheet}, palette)

    def five_strokes() -> None:
        for y in (90, 110, 130, 150):
            studio.load_brush("round", 10, {"quinacridone_rose": 2.0}, 1.0)
            studio.stroke("painting", [[40, y], [216, y]], 120, smooth=False)
        studio.load_brush("flat", 8, {}, 0.5)
        studio.stroke("painting", [[128, 70], [128, 170]], 80, smooth=False)

    sheet.load_state(empty)
    five_strokes()
    samples = []
    for _ in range(repeats):
        sheet.load_state(empty)
        samples.append(timed(five_strokes) / 5)
    return summary("stroke_seconds", samples)


def cpu_wet_cost(repeats: int) -> Metrics:
    """Wet advance per simulated second of a 128-pixel sheet on the CPU."""
    sheet = new_sheet(128, 128, THREE, torch.device("cpu"))
    lay_wash(sheet)
    laid = sheet.state()
    sheet.advance(0.5)
    samples = []
    for _ in range(repeats):
        sheet.load_state(laid)
        started = time.perf_counter()
        sheet.advance(WET_SECONDS)
        samples.append((time.perf_counter() - started) / WET_SECONDS)
    return summary("cpu_wet_seconds_per_second", samples)


def wash_drying(repeats: int) -> Metrics:
    """Studio.dry() from one laid 256 px wash of mop rows with strong colour charged in (three pigments)."""
    size = 256
    sheet = new_sheet(size, size, THREE)
    studio = Studio({"painting": sheet}, list(THREE))
    y = 0.1 * size
    while y < 0.9 * size:
        studio.load_brush("mop", size / 12, {"french_ultramarine": 0.6}, 1.0)
        studio.stroke("painting", [[0.1 * size, y, 0.9], [0.9 * size, y, 0.9]], 200, smooth=False)
        y += size / 12
    studio.load_brush("round", size / 40, {"cadmium_red": 4.0}, 0.8)
    studio.stroke("painting", [[0.2 * size, 0.5 * size], [0.8 * size, 0.5 * size]], 120, smooth=False)
    laid = sheet.state()
    samples = []
    for _ in range(repeats):
        sheet.load_state(laid)
        samples.append(timed(studio.dry))
    return summary("wash_drying_seconds", samples)


def layered_pass(repeats: int) -> Metrics:
    """A pass across layered paint at 256 px with six pigments: a dark band and white columns dried first, then three
    glaze strokes recorded every 0.3 s, then dried; and render() of the result, on the device and on the CPU."""
    size = 256
    sheet = new_sheet(size, size, SIX)
    studio = Studio({"painting": sheet}, list(SIX))
    for y in (100, 128, 156):
        studio.load_brush("flat", 20, {"burnt_umber": 2.0, "french_ultramarine": 1.0}, 1.0)
        studio.stroke("painting", [[12, y, 0.9], [244, y, 0.9]], 200, smooth=False)
    studio.dry()
    for x in (40, 92, 144, 196):
        studio.load_brush("round", 10, {"opaque_white": 4.5}, 1.0)
        studio.stroke("painting", [[x, 12, 0.9], [x, 244, 0.9]], 200, smooth=False)
    studio.dry()
    prepared = sheet.state()
    samples = []
    with tempfile.TemporaryDirectory() as work:
        for repeat in range(repeats):
            sheet.load_state(prepared)
            recording = Studio({"painting": sheet}, list(SIX), FrameRecorder(Path(work) / f"frames_{repeat}"))

            def glaze(painter: Studio = recording) -> None:
                for y in (110, 128, 146):
                    painter.load_brush("flat", 16, {"phthalo_green": 0.8}, 1.0)
                    painter.stroke("painting", [[12, y, 0.9], [244, y, 0.9]], 160, smooth=False)
                painter.dry()

            samples.append(timed(glaze))
    out = summary("end_to_end_seconds", samples)
    render(sheet)
    out |= summary("layered_render_seconds", [timed(lambda: render(sheet)) for _ in range(9)])
    on_cpu = new_sheet(size, size, SIX, torch.device("cpu"))
    on_cpu.load_state(sheet.state())
    render(on_cpu)
    out |= summary("layered_render_seconds_cpu", [timed(lambda: render(on_cpu)) for _ in range(9)])
    return out


def new_test_time() -> Metrics:
    """Wall time of the scenarios behind the film-mobility tests, run one after another."""
    return {"new_test_seconds": timed(lambda: (levelling_rates(), slope_runs(), thin_film_on_damp_paper()))}


SECTIONS: dict[str, Callable[[int], Metrics]] = {
    "cost": wet_and_dry_cost,
    "sizes": lambda _: sizes(),
    "session": lambda _: session_state(),
    "strokes": strokes,
    "cpu": cpu_wet_cost,
    "wash_drying": lambda repeats: wash_drying(min(repeats, 3)),
    "layered_pass": lambda repeats: layered_pass(min(repeats, 3)),
    "new_tests": lambda _: new_test_time(),
}


def card_utilisation(samples: int = 5) -> list[int]:
    """Percentage of the time the graphics card was busy, read a few times over about a second before the run."""
    readings = []
    for _ in range(samples):
        try:
            listing = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
        except FileNotFoundError:
            return []
        readings.extend(int(line) for line in listing.split() if line.strip().isdigit())
        time.sleep(0.2)
    return readings


def other_work_on_the_card() -> list[str]:
    """Processes besides this one that hold a context on the graphics card. The desktop's own graphics clients
    appear here even when idle, so this is a record, not a test; card_utilisation is the test."""
    try:
        listing = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except FileNotFoundError:
        return []
    others = []
    for line in listing.splitlines():
        pid, _, command = line.partition(",")
        if pid.strip() and pid.strip() != str(os.getpid()):
            others.append(f"{pid.strip()} {Path(command.strip().split(' ')[0]).name}")
    return others


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--sections", nargs="*", default=list(SECTIONS), choices=list(SECTIONS))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--record", action="store_true", help="write the sections run into the baseline")
    arguments = parser.parse_args()

    started = time.perf_counter()
    others = other_work_on_the_card()
    utilisation = card_utilisation()
    load = os.getloadavg()[0]
    idle = max(utilisation, default=0) <= IDLE_CARD_UTILISATION and load < IDLE_LOAD_AVERAGE
    if arguments.record and not idle:
        sys.exit(f"not recorded: the machine is busy (card {utilisation} %, load average {load:.2f})")
    metrics: Metrics = {}
    seconds = {}
    for name in arguments.sections:
        began = time.perf_counter()
        metrics |= SECTIONS[name](arguments.repeats)
        seconds[name] = round(time.perf_counter() - began, 1)
        print(f"  {name:<14s} {seconds[name]:6.1f} s", file=sys.stderr, flush=True)
    record = {
        "revision": revision(),
        "engine_digest": engine_digest(),
        "engine_version": watercolor.ENGINE_VERSION,
        "device": torch.cuda.get_device_name() if torch.cuda.is_available() else "cpu",
        "torch": torch.__version__,
        "repeats": arguments.repeats,
        "other_processes_on_the_card": others,
        "card_utilisation_before": utilisation,
        "load_average_before": round(load, 2),
        "idle": idle,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "timings": seconds,
    }
    measurements = {"benchmark": metrics}
    gates = [gate for gate in GATES if gate.kind == "performance"]
    baseline = load_baseline(arguments.baseline)
    if arguments.record:
        # Sections recorded on the same engine join the baseline; on another engine the baseline starts afresh.
        if baseline.get("engine_digest") == record["engine_digest"]:
            metrics = baseline.get("measurements", {}).get("benchmark", {}) | metrics
            measurements = {"benchmark": metrics}
            record["timings"] = baseline.get("timings", {}) | seconds
        reference = measurements
    else:
        reference = baseline.get("measurements", {})
    outcome = evaluate(gates, measurements, reference)
    record |= {"measurements": measurements, "gates": outcome}
    for gate in gates:
        print(describe(gate, outcome[gate.id]))
    if others:
        print(f"graphics clients holding the card: {others}")
    text = json.dumps(record, indent=1) + "\n"
    if arguments.output:
        arguments.output.write_text(text)
    if arguments.record:
        arguments.baseline.write_text(text)
        return
    failed = [gate.id for gate in gates if outcome[gate.id]["status"] == "fail"]
    if failed:
        print(f"failing: {', '.join(failed)}")
    if not idle:
        print(f"the machine was busy when the run began (card {utilisation} %, load average {load:.2f}): not binding")
    if failed or not idle:
        sys.exit(1)


if __name__ == "__main__":
    main()

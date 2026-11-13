"""Painting several sheets at once.

Each painter runs its own script in its own thread. Whenever a painter lets time pass,
it waits; once every painter is waiting, the shortest wait is served by advancing all the
sheets together, and the painters whose wait is over carry on. Only the passing of time
is shared: every painter has its own sheet, brush and script.
"""

import threading
from collections.abc import Callable, Sequence

import torch

from .paper import generate_paper
from .pigments import PIGMENTS
from .simulation import Sheet, SheetBatch
from .studio import Studio


class SharedClock:
    def __init__(self, batch: SheetBatch) -> None:
        self._batch = batch
        self._condition = threading.Condition()
        self._owed: dict[int, float] = {}  # time each waiting painter has still to wait
        self._painting = 0

    def pass_time(self, duration: float) -> None:
        """Called by a painter: wait until this much time has passed on the sheets."""
        painter = threading.get_ident()
        with self._condition:
            self._owed[painter] = duration
            self._condition.notify_all()
            self._condition.wait_for(lambda: painter not in self._owed)

    def run(self, painters: Sequence[Callable[[], None]]) -> None:
        """Run every painter to the end of its script."""
        failures: list[BaseException] = []

        def work(painter: Callable[[], None]) -> None:
            try:
                painter()
            except BaseException as problem:  # noqa: BLE001 - kept and raised again by run()
                failures.append(problem)
            finally:
                with self._condition:
                    self._painting -= 1
                    self._condition.notify_all()

        self._painting = len(painters)
        threads = [threading.Thread(target=work, args=(painter,)) for painter in painters]
        for thread in threads:
            thread.start()
        with self._condition:
            while True:
                self._condition.wait_for(lambda: len(self._owed) == self._painting)
                if self._painting == 0:
                    break
                step = min(self._owed.values())
                self._batch.advance(step)
                for painter in list(self._owed):
                    self._owed[painter] -= step
                    if self._owed[painter] <= 1e-9:
                        del self._owed[painter]
                self._condition.notify_all()
        for thread in threads:
            thread.join()
        if failures:
            raise failures[0]


# Measured on an RTX 3080 with 384-pixel sheets: eight sheets together take about 3.6 times
# less time than one after another. More than that saturates the card and gains nothing.
LARGEST_BATCH = 8


def paint_together(
    scripts: Sequence[Callable[[Studio], None]], size: int, palette: list[str], seeds: Sequence[int]
) -> list[Studio]:
    """Run each script on its own sheet and return their studios.

    Sheets are painted in batches that share one clock. Scripts of similar length batch best,
    because a sheet that has finished still costs time while its batch runs on.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pigments = [PIGMENTS[name] for name in palette]
    studios: list[Studio] = []
    for start in range(0, len(scripts), LARGEST_BATCH):
        sheets = [
            Sheet(generate_paper(size, size, seed, device), pigments) for seed in seeds[start : start + LARGEST_BATCH]
        ]
        clock = SharedClock(SheetBatch(sheets))
        batch = [Studio({"painting": sheet}, palette, shared_clock=clock) for sheet in sheets]
        painters = [
            lambda script=script, studio=studio: script(studio)
            for script, studio in zip(scripts[start : start + LARGEST_BATCH], batch)
        ]
        clock.run(painters)
        studios.extend(batch)
    return studios

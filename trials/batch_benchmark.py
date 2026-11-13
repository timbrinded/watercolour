"""How much does painting together save? The same script on N sheets, alone and then together.

uv run python trials/batch_benchmark.py
"""

import time

from engine_trials import PALETTE, SIZE, dabs_into_pale_wash

from watercolor.together import paint_together


def main() -> None:
    paint_together([dabs_into_pale_wash], SIZE, PALETTE, seeds=[0])  # first run pays for start-up
    started = time.perf_counter()
    paint_together([dabs_into_pale_wash], SIZE, PALETTE, seeds=[0])
    alone = time.perf_counter() - started
    print(f" 1 sheet : {alone:6.1f} s")
    for count in (4, 8, 16):
        started = time.perf_counter()
        paint_together([dabs_into_pale_wash] * count, SIZE, PALETTE, seeds=list(range(count)))
        together = time.perf_counter() - started
        print(
            f"{count:2d} sheets: {together:6.1f} s together, {alone * count:6.1f} s one after another ({alone * count / together:.1f}x)"
        )


if __name__ == "__main__":
    main()

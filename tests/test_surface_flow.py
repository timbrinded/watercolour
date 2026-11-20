"""The law the film of water on the paper flows by."""

import dataclasses
import math
import statistics

import torch

from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.simulation import Sheet, SheetBatch, SimulationParameters

# The film neither evaporates nor soaks away, so only its flow changes it.
STILL = dataclasses.replace(
    SimulationParameters(), evaporation_rate=0.0, absorption_rate=0.0, paper_evaporation_rate=0.0
)


def test_a_ripple_levels_at_a_rate_that_goes_as_the_cube_of_the_film_depth() -> None:
    """A film flowing over paper it does not slip on carries h^3 per unit of pressure gradient, so at a fixed
    wavelength a ripple levels at a rate in proportion to the cube of the film's depth (Orchard 1962). 0.8.0 used
    the square: an exponent of 2.0, where this gives 3.0.

    The law shows at the scale of a pool on dry paper, so the ripple is a 5% cosine 32 px long. For each depth a
    level and a rippled sheet of the same paper are advanced together and the ripple is read from their difference,
    so the paper's own relief cancels. The depths stay below a full wash, above which the mobility is capped.
    """
    depths = (0.2, 0.45, 0.9)
    rows, width = 64, 128
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sheets = []
    for depth in depths:
        level, rippled = (
            Sheet(generate_paper(rows, width, 3, device), [PIGMENTS["french_ultramarine"]], STILL) for _ in range(2)
        )
        level.water.fill_(depth)
        sheets += [level, rippled]
    columns = torch.arange(width, device=device, dtype=torch.float32)
    ripple = torch.cos(math.pi * 8 * (columns + 0.5) / width).expand(rows, width)
    for index, depth in enumerate(depths):
        sheets[2 * index + 1].water.copy_(depth * (1.0 + 0.05 * ripple))
    batch = SheetBatch(sheets)
    inner = (slice(24, 40), slice(24, width - 24))

    def amplitude(index: int) -> float:
        difference = (sheets[2 * index + 1].water - sheets[2 * index].water)[inner]
        return float((difference * ripple[inner]).sum() / (ripple[inner] ** 2).sum())

    # Each rate is the slope of the logarithm of the amplitude, followed until it has fallen by 0.15.
    times = [[0.0] for _ in depths]
    logs = [[math.log(amplitude(index))] for index in range(len(depths))]
    elapsed = 0.0
    while elapsed < 60.0 and any(log[-1] > log[0] - 0.15 for log in logs):
        batch.advance(0.2)
        elapsed += 0.2
        for index, log in enumerate(logs):
            if log[-1] > log[0] - 0.15:
                times[index].append(elapsed)
                log.append(math.log(amplitude(index)))
    rates = [-statistics.linear_regression(t, log).slope for t, log in zip(times, logs)]
    exponents = [
        (math.log(rates[i + 1]) - math.log(rates[i])) / (math.log(depths[i + 1]) - math.log(depths[i]))
        for i in range(2)
    ]
    overall = statistics.linear_regression([math.log(d) for d in depths], [math.log(r) for r in rates]).slope
    # The bounds reach a quarter of the way from the cube toward the square: the square's 2.0 is far outside them.
    assert 2.75 <= overall <= 3.25
    assert all(2.75 <= exponent <= 3.25 for exponent in exponents)

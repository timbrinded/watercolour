"""Procedural cold-press paper."""

from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import Tensor

# Grain cell sizes in pixels and their weights. Grain is fixed in pixels, so a
# smaller sheet is a smaller piece of the same paper.
GRAIN_OCTAVES = ((2, 0.45), (4, 0.40), (8, 0.15))


# Broad, shallow undulation of the sheet, which lets a wash settle unevenly.
COCKLE_OCTAVES = ((32, 0.6), (72, 0.4))

# Unevenness of the sizing, the gelatin that makes paper resist water. It varies in patches
# larger than the grain, which is why a wet edge creeps forward in lobes and not as a smooth curve.
SIZING_OCTAVES = ((3, 0.25), (7, 0.35), (16, 0.25), (36, 0.15))


@dataclass(frozen=True)
class Paper:
    tooth: Tensor  # surface height in [0, 1]; 1 is a peak, 0 a valley
    cockle: Tensor  # broad undulation of the sheet in [0, 1]
    sizing: Tensor  # resistance to wetting in [0, 1]


def _noise(height: int, width: int, octaves: tuple[tuple[int, float], ...], generator: torch.Generator) -> Tensor:
    surface = torch.zeros(height, width)
    for cell, weight in octaves:
        coarse = torch.randn(1, 1, height // cell + 3, width // cell + 3, generator=generator)
        octave = F.interpolate(coarse, scale_factor=cell, mode="bicubic", align_corners=False)
        surface += weight * octave[0, 0, cell : cell + height, cell : cell + width]
    # Rank-normalise so that the heights are uniformly distributed.
    order = surface.flatten().argsort().argsort().float()
    return (order / (order.numel() - 1)).reshape(height, width)


def generate_cockle(height: int, width: int, seed: int, device: torch.device) -> Tensor:
    """Return the broad undulation of the sheet in [0, 1]."""
    return _noise(height, width, COCKLE_OCTAVES, torch.Generator().manual_seed(seed + 7919)).to(device)


def generate_tooth(height: int, width: int, seed: int, device: torch.device) -> Tensor:
    """Return the paper surface height in [0, 1]; 1 is a peak, 0 a valley."""
    return _noise(height, width, GRAIN_OCTAVES, torch.Generator().manual_seed(seed)).to(device)


def generate_paper(height: int, width: int, seed: int, device: torch.device) -> Paper:
    """Return a sheet of paper; the same seed always gives the same sheet."""
    sizing = _noise(height, width, SIZING_OCTAVES, torch.Generator().manual_seed(seed + 104729)).to(device)
    return Paper(generate_tooth(height, width, seed, device), generate_cockle(height, width, seed, device), sizing)

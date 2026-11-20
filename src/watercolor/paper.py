"""Procedural paper: its grain, its broad undulation and the unevenness of its sizing."""

from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import Tensor

# Colour of the bare sheet under an even light.
PAPER_COLOR = (0.97, 0.96, 0.93)

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
    tooth: Tensor  # surface height about a mean of 0.5; on cold press it spans [0, 1], 1 a peak and 0 a valley
    cockle: Tensor  # broad undulation of the sheet in [0, 1]
    sizing: Tensor  # resistance to wetting in [0, 1]
    ground: Tensor | None = None  # colour of the bare sheet, (3, 1, 1) or (3, H, W); None is PAPER_COLOR
    relief_shading: float = 0.05  # how strongly the relief of the grain shades the bare sheet
    # Highest and lowest points of the grain. The brush and the pencil reach down from the peak and a thin film
    # fills the grain up from the valley, so on a shallow grain each meets the paper almost evenly.
    peak: float = 1.0
    valley: float = 0.0


@dataclass(frozen=True)
class Grain:
    """How the tooth of a support is made."""

    octaves: tuple[tuple[int, float], ...] = GRAIN_OCTAVES  # cell sizes in pixels and their weights
    depth: float = 1.0  # height from valley to peak, as a share of cold press's
    # Power applied to the evenly spread heights. Below 1 it raises most of the surface into broad tops and
    # leaves a few deep pits. The heights are then moved back to a mean of 0.5, about which every threshold
    # that reads the tooth was set.
    plateaus: float = 1.0


COLD_PRESS_GRAIN = Grain()


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


def generate_tooth(height: int, width: int, seed: int, device: torch.device, grain: Grain = COLD_PRESS_GRAIN) -> Tensor:
    """Return the surface height of the sheet; on cold press it spans [0, 1], 1 a peak and 0 a valley."""
    tooth = _noise(height, width, grain.octaves, torch.Generator().manual_seed(seed))
    if grain.plateaus != 1.0:
        tooth = tooth**grain.plateaus
        tooth = tooth - (tooth.mean() - 0.5)
    if grain.depth != 1.0:
        tooth = 0.5 + grain.depth * (tooth - 0.5)
    return tooth.to(device)


def generate_paper(height: int, width: int, seed: int, device: torch.device, grain: Grain = COLD_PRESS_GRAIN) -> Paper:
    """Return a sheet of paper; the same seed always gives the same sheet."""
    sizing = _noise(height, width, SIZING_OCTAVES, torch.Generator().manual_seed(seed + 104729)).to(device)
    tooth = generate_tooth(height, width, seed, device, grain)
    cockle = generate_cockle(height, width, seed, device)
    return Paper(tooth, cockle, sizing, peak=float(tooth.max()), valley=float(tooth.min()))

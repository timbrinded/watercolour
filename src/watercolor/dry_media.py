"""Dry media: coloured pencil and pastel, and how a dry stick meets the grain of the paper."""

from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import Tensor

from .optics import TINTING_STRENGTH, layer_of

# A dry stick meets the grain as a brush does: pressure p reaches down from the peaks by this share of cold press's
# grain height times p, so light pressure marks only the peaks of cold press and full pressure fills nearly all its
# hollows, while on a shallower grain the same touch reaches further down it. A fine point presses harder on what it
# touches than the broad side of a stick, and reaches deeper by up to half as much again.
GRIP_HEAVIEST = 1.15
# The paper is rough below the size of a cell as well, at the scale of its fibres, so the stick does not stop touching
# at one height: it coats a falling share of the surface over this spread, in grain heights.
GRIP_SOFTNESS = 0.10
# The grain is one height per cell, but the paper between cell centres rises and falls between them. A stick meets
# that surface, so the share of a cell it touches is found on the grain interpolated this many times along each side.
GRIP_SUBCELLS = 4
STRONGEST_STICK = 4.0  # most paint a stick may hold, in all


@dataclass(frozen=True)
class DryMedium:
    """A dry stick drawn over paper or dried paint: its paints, bound by wax or chalk, lie on the surface."""

    name: str
    laydown: float  # share of the stick's strength one full mark leaves on the sheet
    extender: float  # scattering of the binder and filler (wax, chalk) per unit of the stick's paint, in every channel

    def layer(self, laid: Tensor, strength: Tensor, absorption: Tensor, scattering: Tensor) -> tuple[Tensor, Tensor]:
        """Reflectance and transmittance, each (3, rows, columns), of the mark the stick leaves where it has laid the
        share given of a full mark. Strength holds the stick's amount of each pigment, and absorption and scattering
        the pigments' coefficients, (pigments, 3)."""
        amount = TINTING_STRENGTH * self.laydown * laid
        absorbing = strength @ absorption
        scattering_of = strength @ scattering + self.extender * strength.sum()
        return layer_of(amount * absorbing[:, None, None], amount * scattering_of[:, None, None])


DRY_MEDIA: dict[str, DryMedium] = {
    medium.name: medium
    for medium in (
        DryMedium("coloured_pencil", laydown=0.5, extender=0.2),
        DryMedium("pastel", laydown=1.0, extender=0.4),
    )
}


def touched_share(tooth: Tensor, peak: float, pressure: Tensor, radius: Tensor) -> Tensor:
    """Share of each cell of the grain given, (rows, columns), that a dry stick touches, for each pressure and radius
    of its point given, (segments, rows, columns). The surface between cell centres is the grain interpolated between
    them, so a cell between a peak and a hollow is touched in part; at pressure 0 the stick touches nothing."""
    n = GRIP_SUBCELLS
    level = peak - GRIP_HEAVIEST * pressure * (1.0 + 1.0 / (1.0 + radius))
    surface = F.interpolate(tooth[None, None], scale_factor=n, mode="bilinear", align_corners=False)[0, 0]
    fine_level = level.repeat_interleave(n, dim=-2).repeat_interleave(n, dim=-1)
    touched = F.avg_pool2d(torch.sigmoid((surface - fine_level) / GRIP_SOFTNESS), n)
    return touched * (pressure > 0)

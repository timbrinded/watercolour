"""Brushes, and the conversion of a drawn path into contact with the sheet."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .simulation import Contact

# A drawn path: points of [x, y] or [x, y, pressure].
Path = Sequence[Sequence[float]]


@dataclass(frozen=True)
class BrushType:
    name: str
    softness: float  # soft edge as a fraction of the radius
    taper: float  # how far the width shrinks as pressure falls to zero
    holding: float  # water capacity relative to a round brush of the same size
    depth: float  # water depth a full brush leaves at full pressure
    firmness: float  # how much the hairs disturb pigment already on the paper
    sweep: float  # share of the brush's speed imparted to wet paint, at full pressure with an empty brush
    clumping: float  # how readily the hairs part into clumps as the brush runs dry
    tip: float = 1.0  # depth of the tip along its travel as a fraction of its radius; a flat brush has a chisel edge


BRUSH_TYPES: dict[str, BrushType] = {
    brush.name: brush
    for brush in (
        BrushType("round", softness=0.12, taper=0.8, holding=1.0, depth=1.0, firmness=0.05, sweep=0.9, clumping=0.6),
        BrushType(
            "flat", softness=0.06, taper=0.1, holding=1.0, depth=0.9, firmness=0.15, sweep=0.95, clumping=1.0, tip=0.3
        ),
        BrushType("mop", softness=0.35, taper=0.3, holding=2.5, depth=1.3, firmness=0.01, sweep=0.3, clumping=0.35),
        BrushType("rigger", softness=0.2, taper=0.6, holding=2.0, depth=0.8, firmness=0.02, sweep=0.6, clumping=0.2),
    )
}

# Water a full round brush holds, in depth x pixels squared, per squared pixel of radius.
CAPACITY_PER_SQUARE_RADIUS = 250.0

# Paint is a mixture: pigment and binder take up room in the brush that water would otherwise
# have. At this concentration half of what the brush holds is solids.
HALF_SOLIDS_CONCENTRATION = 3.5
# The strongest paint a brush can carry: paste straight from the pan.
STRONGEST_CONCENTRATION = 8.0


@dataclass
class Brush:
    type_name: str
    size: float  # largest radius in pixels
    concentration: list[float]  # pigment per unit of water, in palette order
    reservoir: float  # water remaining
    hairs: list[float]  # how closely the hairs hold together at each position across the brush, in [0, 1]

    @property
    def brush_type(self) -> BrushType:
        return BRUSH_TYPES[self.type_name]

    @property
    def solids(self) -> float:
        """Share of the brush's load that is pigment and binder, not water."""
        strength = sum(self.concentration)
        return strength / (strength + HALF_SOLIDS_CONCENTRATION)

    @property
    def capacity(self) -> float:
        """Water the brush can hold. Strong paint leaves less room for it."""
        return CAPACITY_PER_SQUARE_RADIUS * self.size**2 * self.brush_type.holding * (1.0 - self.solids) ** 1.5

    @property
    def fullness(self) -> float:
        return self.reservoir / self.capacity

    def radius(self, pressure: np.ndarray) -> np.ndarray:
        return self.size * (1.0 - self.brush_type.taper * (1.0 - pressure))

    def contact(self, pressure: float, speed: float) -> Contact:
        kind = self.brush_type
        fullness = self.fullness
        haste = max(0.0, speed / 150.0 - 1.0)
        # Thick paint leaves a shallower film of water and catches on the grain of the paper.
        thin = 1.0 - self.solids
        return Contact(
            softness=kind.softness,
            tip=kind.tip,
            target_depth=kind.depth * fullness**0.6 * (0.6 + 0.4 * pressure) * (0.4 + 0.6 * thin),
            # However dry or thick, a brush pressed to the paper still catches the highest grain.
            contact_level=max(0.15, 0.1 + 1.8 * fullness + 0.2 * pressure - 0.15 * haste - 2.2 * self.solids**2),
            exchange=0.5 * min(1.0, 2.0 * fullness),
            scrub=kind.firmness,
            release=0.08 * kind.depth * fullness * (0.5 + 0.5 * pressure) * thin,
            thirst=0.4 * (1.0 - fullness),
            # A full brush rides on its own bead of paint; a damp one pressed to the paper sweeps it along.
            push=kind.sweep * (0.3 + 0.7 * pressure) * (1.0 - 0.7 * fullness),
            # A brush with water in it is held to a single body. As it runs dry, or is hurried,
            # or carries thick paint, the hairs part; pressing them to the paper closes them a little.
            splay=kind.clumping
            * min(0.9, max(0.0, 0.95 - 2.0 * fullness + 0.25 * haste + 0.6 * self.solids - 0.2 * pressure)),
            streaking=0.3 * kind.clumping,
        )


HAIR_POSITIONS = 64
# Width in pixels of the clumps into which hairs gather, and the weight of each scale.
CLUMP_WIDTHS = ((6.0, 0.5), (2.5, 0.5))


def arrange_hairs(size: float, seed: int) -> list[float]:
    """Return how closely the hairs hold together across a brush of this size.

    The values are evenly spread over [0, 1], so a splay of 0.3 parts the loosest 30% of the width.
    """
    chance = np.random.default_rng(seed)
    positions = np.linspace(0.0, 1.0, HAIR_POSITIONS)
    profile = np.zeros(HAIR_POSITIONS)
    for width, weight in CLUMP_WIDTHS:
        clumps = max(2, round(2.0 * size / width))
        profile += weight * np.interp(positions, np.linspace(0.0, 1.0, clumps + 1), chance.standard_normal(clumps + 1))
    ranks = profile.argsort().argsort()
    return (ranks / (HAIR_POSITIONS - 1)).tolist()


def trace_path(control_points: Path, smooth: bool, spacing: float = 1.5) -> np.ndarray:
    """Return evenly spaced (x, y, pressure) samples along a path.

    Control points are [x, y] or [x, y, pressure]; pressure defaults to 0.7.
    A smooth path is a Catmull-Rom spline through the control points.
    """
    controls = np.array([[p[0], p[1], p[2] if len(p) > 2 else 0.7] for p in control_points], dtype=np.float64)
    if len(controls) == 1:
        return controls
    if smooth and len(controls) > 2:
        padded = np.vstack((controls[:1], controls, controls[-1:]))
        t = np.linspace(0.0, 1.0, 24, endpoint=False)[:, None]
        pieces = []
        for i in range(len(controls) - 1):
            p0, p1, p2, p3 = padded[i : i + 4]
            pieces.append(
                0.5
                * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t**2 + (3 * p1 - p0 - 3 * p2 + p3) * t**3)
            )
        dense = np.vstack((*pieces, controls[-1:]))
    else:
        dense = controls
    lengths = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(dense[:, :2], axis=0), axis=1))))
    if lengths[-1] == 0.0:
        return dense[:1]
    stations = np.linspace(0.0, lengths[-1], max(2, int(lengths[-1] / spacing) + 1))
    samples = np.stack([np.interp(stations, lengths, dense[:, axis]) for axis in range(3)], axis=1)
    samples[:, 2] = samples[:, 2].clip(0.0, 1.0)
    return samples

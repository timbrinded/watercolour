"""Brushes, and the conversion of a drawn path into contact with the sheet."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .simulation import Contact

# A drawn path: points of [x, y] or [x, y, pressure].
Path = Sequence[Sequence[float]]


@dataclass(frozen=True)
class Hair:
    """What a brush is made of. Every value is relative to red sable."""

    name: str
    holding: float  # water the hair holds
    release: float  # how freely it gives that water up to the paper
    softness: float  # softness it adds to the edge of a mark, as a fraction of the radius
    spring: float  # how firmly the hairs recover and carry wet paint along
    firmness: float  # how much they disturb pigment already settled on the paper
    clumping: float  # how readily they part into clumps as the brush runs dry
    point: float  # how fine a point the hair takes, which scales how far the brush narrows


# The maker's descriptions give the order of these properties (Kolinsky holds the most and takes
# the finest point; red sable holds more than golden synthetic; squirrel and goat are soft hairs
# for washes). The numbers themselves are estimates.
HAIRS: dict[str, Hair] = {
    hair.name: hair
    for hair in (
        Hair("kolinsky_sable", holding=1.15, release=1.0, softness=0.0, spring=1.05, firmness=1.0, clumping=0.85, point=1.05),
        Hair("red_sable", holding=1.0, release=1.0, softness=0.0, spring=1.0, firmness=1.0, clumping=1.0, point=1.0),
        Hair("sable_blend", holding=0.85, release=0.95, softness=0.0, spring=1.05, firmness=1.5, clumping=1.15, point=0.95),
        Hair("squirrel", holding=2.2, release=1.3, softness=0.15, spring=0.33, firmness=0.2, clumping=0.6, point=0.95),
        Hair("goat", holding=1.8, release=1.3, softness=0.2, spring=0.25, firmness=0.4, clumping=1.0, point=0.5),
        Hair("badger", holding=0.6, release=0.7, softness=0.1, spring=0.7, firmness=2.0, clumping=1.5, point=0.3),
        Hair("golden_synthetic", holding=0.7, release=1.1, softness=0.0, spring=1.15, firmness=2.4, clumping=1.35, point=0.95),
        Hair("synthetic_sable", holding=0.9, release=1.0, softness=0.0, spring=1.05, firmness=1.6, clumping=1.1, point=1.0),
        Hair("synthetic_squirrel", holding=1.8, release=1.25, softness=0.12, spring=0.45, firmness=0.4, clumping=0.7, point=0.95),
    )
}  # fmt: skip


@dataclass(frozen=True)
class BrushType:
    """The shape of a brush's head: its section, the length of its hair and the form of its end.

    The values are for a head of red sable; the hair it is actually made of scales them.
    """

    name: str
    softness: float  # soft edge as a fraction of the radius
    taper: float  # how far the width shrinks as pressure falls to zero
    holding: float  # water capacity relative to a round brush of the same size
    depth: float  # water depth a full brush leaves at full pressure
    firmness: float  # how much the hairs disturb pigment already on the paper
    sweep: float  # share of the brush's speed imparted to wet paint, at full pressure with an empty brush
    clumping: float  # how readily the hairs part into clumps as the brush runs dry
    tip: float = 1.0  # depth of the tip along its travel as a fraction of its radius; below 1.0 it is a flat head
    rounded: bool = False  # a flat head with a rounded end, as a filbert has
    slant: float = 0.0  # how far the end of a flat head is cut at an angle, as a fraction of its width
    gaps: float = 0.0  # share of the width where the hairs never meet the paper, as in a fan or a comber
    hair: str = "red_sable"  # what a head of this shape is usually made of


BRUSH_TYPES: dict[str, BrushType] = {
    brush.name: brush
    for brush in (
        # Round heads, from short to long.
        BrushType("spotter", 0.10, 0.60, 0.45, 0.90, 0.08, 1.00, 0.60),
        BrushType("round", 0.12, 0.80, 1.00, 1.00, 0.05, 0.90, 0.60),
        BrushType("designer", 0.12, 0.90, 1.10, 0.95, 0.04, 0.75, 0.50),
        BrushType("rigger", 0.20, 0.60, 2.00, 0.80, 0.02, 0.60, 0.20),
        BrushType("extended_point", 0.20, 0.55, 3.20, 0.85, 0.02, 0.55, 0.20),
        BrushType("mop", 0.20, 0.316, 1.136, 1.00, 0.05, 0.909, 0.583, hair="squirrel"),
        BrushType("stippler", 0.15, 0.20, 0.30, 0.60, 0.25, 1.00, 1.00, gaps=0.6, hair="badger"),
        # Flat heads with a square end.
        BrushType("flat", 0.06, 0.10, 1.00, 0.90, 0.15, 0.95, 1.00, tip=0.3),
        BrushType("bright", 0.06, 0.08, 0.60, 0.85, 0.20, 1.00, 1.00, tip=0.35),
        BrushType("flat_wash", 0.15, 0.10, 0.90, 1.10, 0.05, 0.90, 0.70, tip=0.3, hair="squirrel"),
        BrushType("hake", 0.10, 0.05, 1.00, 1.10, 0.05, 0.90, 0.90, tip=0.2, hair="goat"),
        BrushType("comber", 0.08, 0.10, 0.70, 0.85, 0.12, 0.95, 1.00, tip=0.3, gaps=0.5),
        BrushType("fan", 0.20, 0.05, 0.35, 0.70, 0.10, 0.90, 1.00, tip=0.12, gaps=0.45),
        # Flat heads cut at an angle.
        BrushType("angular", 0.06, 0.15, 0.90, 0.90, 0.12, 0.95, 0.90, tip=0.3, slant=0.5),
        BrushType("dagger", 0.08, 0.75, 1.20, 0.90, 0.06, 0.80, 0.60, tip=0.3, slant=0.6, hair="sable_blend"),
        BrushType("sword", 0.10, 0.90, 1.60, 0.90, 0.03, 0.60, 0.40, tip=0.3, slant=0.8, hair="kolinsky_sable"),
        # Flat heads with a rounded end.
        BrushType("filbert", 0.10, 0.25, 1.00, 0.95, 0.10, 0.90, 0.80, tip=0.45, rounded=True),
        BrushType("cats_tongue", 0.10, 0.60, 1.00, 0.95, 0.08, 0.90, 0.70, tip=0.45, rounded=True),
        BrushType("oval_wash", 0.20, 0.30, 0.60, 1.10, 0.04, 0.90, 0.60, tip=0.5, rounded=True, hair="squirrel"),
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
    hair: str = ""  # what the head is made of; empty means the usual hair for its shape

    @property
    def brush_type(self) -> BrushType:
        return BRUSH_TYPES[self.type_name]

    @property
    def hair_type(self) -> Hair:
        return HAIRS[self.hair or self.brush_type.hair]

    @property
    def taper(self) -> float:
        return min(0.95, self.brush_type.taper * self.hair_type.point)

    @property
    def clumping(self) -> float:
        return self.brush_type.clumping * self.hair_type.clumping

    @property
    def solids(self) -> float:
        """Share of the brush's load that is pigment and binder, not water."""
        strength = sum(self.concentration)
        return strength / (strength + HALF_SOLIDS_CONCENTRATION)

    @property
    def capacity(self) -> float:
        """Water the brush can hold. Strong paint leaves less room for it."""
        return (
            CAPACITY_PER_SQUARE_RADIUS
            * self.size**2
            * self.brush_type.holding
            * self.hair_type.holding
            * (1.0 - self.solids) ** 1.5
        )

    @property
    def fullness(self) -> float:
        return self.reservoir / self.capacity

    def radius(self, pressure: np.ndarray) -> np.ndarray:
        return self.size * (1.0 - self.taper * (1.0 - pressure))

    def contact(self, pressure: float, speed: float) -> Contact:
        kind, hair = self.brush_type, self.hair_type
        fullness = self.fullness
        depth = kind.depth * hair.release
        haste = max(0.0, speed / 150.0 - 1.0)
        # Thick paint leaves a shallower film of water and catches on the grain of the paper.
        thin = 1.0 - self.solids
        # A brush with water in it is held to a single body. As it runs dry, or is hurried,
        # or carries thick paint, the hairs part; pressing them to the paper closes them a little.
        parting = min(0.9, max(0.0, 0.95 - 2.0 * fullness + 0.25 * haste + 0.6 * self.solids - 0.2 * pressure))
        return Contact(
            softness=min(0.6, kind.softness + hair.softness),
            tip=kind.tip,
            rounded=kind.rounded,
            slant=kind.slant,
            target_depth=depth * fullness**0.6 * (0.6 + 0.4 * pressure) * (0.4 + 0.6 * thin),
            # However dry or thick, a brush pressed to the paper still catches the highest grain.
            contact_level=max(0.15, 0.1 + 1.8 * fullness + 0.2 * pressure - 0.15 * haste - 2.2 * self.solids**2),
            exchange=0.5 * min(1.0, 2.0 * fullness),
            scrub=min(0.6, kind.firmness * hair.firmness),
            release=0.08 * depth * fullness * (0.5 + 0.5 * pressure) * thin,
            thirst=0.4 * (1.0 - fullness),
            # A full brush rides on its own bead of paint; a damp one pressed to the paper sweeps it along.
            push=min(1.0, kind.sweep * hair.spring) * (0.3 + 0.7 * pressure) * (1.0 - 0.7 * fullness),
            # A fan or a comber has gaps between its hairs however full it is.
            splay=min(0.9, max(kind.gaps, self.clumping * parting)),
            streaking=min(0.5, 0.3 * self.clumping),
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

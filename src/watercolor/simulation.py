"""Watercolor sheet simulation.

The model follows Curtis, Anderson, Seims, Fleischer and Salesin,
"Computer-Generated Watercolor" (SIGGRAPH 1997): a film of surface water that
carries suspended pigment, a layer of pigment deposited on the paper, and water
held inside the paper. Surface flow is a thin-film flux driven by the height of
the water surface instead of the paper's staggered-grid velocity solver.

Lengths are in pixels, time in seconds, water depth in arbitrary units where 1.0
is a full wash.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import Tensor

from .paper import Paper
from .pigments import Pigment


@dataclass(frozen=True)
class SimulationParameters:
    time_step: float = 0.1
    coarse_time_step: float = 1.0  # used when only the paper itself is drying
    flow_rate: float = 7.0
    flow_substeps: int = 12
    surface_tension: float = 30.0  # square of the capillary length, in pixels
    pool_scale: float = 4.0  # smoothing radius, in pixels, that separates ripples from the shape of a pool
    pool_speed: float = 8.0  # how much faster water moves at the scale of a pool than between neighbouring cells
    wetting_strength: float = 0.5  # pull of wetted paper on a thin film, which pins the edge of a puddle
    wetting_depth: float = 0.15  # film depth over which that pull fades
    wettable_saturation: float = 0.3  # share of capacity at which paper is fully wettable
    wicking: float = 0.3  # mobility of water along the surface of damp paper; it feeds the drying edge of a wash
    marangoni: float = 10.0  # strength of the surface stream from paint-rich toward clear water
    thickness_limit: float = 8.0
    stream_minimum_depth: float = 0.35  # film depth below which there is no surface stream
    dry_advance_depth: float = 1.2  # depth at which a puddle creeps onto dry paper
    damp_advance_depth: float = 0.03  # depth at which it creeps onto damp paper
    mobility_depth_limit: float = 1.3
    sizing_unevenness: float = 1.2  # how much harder, in powers of e, the most heavily sized dry paper is to wet
    wicking_unevenness: float = 1.6  # spread, in powers of e, of how readily damp paper carries water along its surface
    tooth_pressure: float = 0.02  # how strongly water pools in the valleys of the grain
    cockle_pressure: float = 0.04  # how strongly water pools in the broad hollows of the sheet
    viscosity: float = 1.2  # how much dissolved paint slows the flow
    wet_threshold: float = 0.01  # surface water above this depth can flow
    damp_threshold: float = 0.6  # paper saturation fraction that admits surface water
    pigment_diffusion: float = 2.0
    resolubility: float = 0.4  # scale of lifting relative to settling
    granulation_strength: float = 0.4
    settling_rate: float = 0.5  # scale of both settling and lifting
    evaporation_rate: float = 0.005
    edge_evaporation: float = 4.0  # extra evaporation at the edge of a wet area
    edge_radius: int = 4
    absorption_rate: float = 0.02
    absorbed_pigment: float = 0.3  # share of the pigment in absorbed water that the fibres keep
    capacity_minimum: float = 0.35
    capacity_maximum: float = 0.5
    capillary_diffusion: float = 0.03
    paper_evaporation_rate: float = 0.002


@dataclass(frozen=True)
class Contact:
    """One instant of a brush touching the sheet."""

    softness: float  # width of the soft edge as a fraction of the radius
    tip: float  # depth of the brush's tip along its travel, as a fraction of its radius; 1.0 is a round tip
    rounded: bool  # whether a flat head ends in a curve, as a filbert does, and not square
    slant: float  # how far the end of a flat head is cut at an angle, as a fraction of its width
    target_depth: float  # water depth the brush tries to leave behind
    contact_level: float  # below about 1.0 the brush touches only the paper's peaks
    exchange: float  # how strongly the brush mixes with paint already on the sheet
    scrub: float  # how strongly the brush disturbs deposited pigment
    release: float  # water depth a resting brush adds per time step
    thirst: float  # how strongly the brush soaks up standing water
    push: float  # share of the brush's speed that it imparts to the wet paint under its hairs
    splay: float  # share of the brush's width where the hairs have parted and do not touch the paper
    streaking: float  # how unevenly paint is held across the hairs


Region = tuple[slice, slice]

# Damping of the surface-tension flux. Levelling and surface tension share one explicit
# update: with levelling using at most 0.15 of the stable range per substep, this value
# keeps their sum inside it.
SURFACE_TENSION_DAMPING = 160.0

# How readily the brush takes up paint from the sheet, relative to how readily it gives it.
PICKUP_SHARE = 0.25

# Share of the brush's push on pigment that also applies to the water.
WATER_PUSH_SHARE = 0.3

# Length in pixels of each short move of the sweep.
PUSH_MOVE = 3.0

# How far the hairs wander sideways as they are dragged, as a share of the brush's radius.
HAIR_DEFLECTION = 0.2

# How much a unit of tilt lowers the depth at which the downhill edge of a puddle advances.
TILT_RELEASE = 3.0

# Largest share of the difference between two cells that the surface stream may even out in one substep.
STABLE_SPREADING = 0.12

# A resting brush stops releasing water once the puddle beneath it is this deep.
MAXIMUM_DEPTH = 2.0


def _faces(field: Tensor, axis: int) -> tuple[Tensor, Tensor]:
    """Return the two cells on either side of each interior face along an axis."""
    if axis == 0:
        return field[..., :-1, :], field[..., 1:, :]
    return field[..., :, :-1], field[..., :, 1:]


def _transport(field: Tensor, flux_y: Tensor, flux_x: Tensor) -> None:
    """Move quantity across faces; positive flux goes toward the higher index."""
    field[..., :-1, :] -= flux_y
    field[..., 1:, :] += flux_y
    field[..., :, :-1] -= flux_x
    field[..., :, 1:] += flux_x


def _laplacian(field: Tensor, inside: Tensor) -> Tensor:
    """Curvature of the film measured within the puddle only.

    Neighbours outside the puddle are ignored, which is the boundary condition of a
    film that wets the paper completely: its edge is not pulled back by surface tension.
    """
    padded = F.pad(field, (1, 1, 1, 1))
    present = F.pad(inside, (1, 1, 1, 1)).float()
    total = torch.zeros_like(field)
    for rows, columns in (
        (slice(0, -2), slice(1, -1)),
        (slice(2, None), slice(1, -1)),
        (slice(1, -1), slice(0, -2)),
        (slice(1, -1), slice(2, None)),
    ):
        total += present[..., rows, columns] * (padded[..., rows, columns] - field)
    return total


def _translate(field: Tensor, dx: float, dy: float) -> Tensor:
    """Shift a field by a whole or fractional number of cells, conserving its total.

    Whatever is shifted beyond the border of the field is lost.
    """
    whole_x, whole_y = math.floor(dx), math.floor(dy)
    part_x, part_y = dx - whole_x, dy - whole_y
    pad = max(abs(whole_x), abs(whole_y)) + 2
    padded = F.pad(field, (pad, pad, pad, pad))
    result = torch.zeros_like(padded)
    for step_y, weight_y in ((0, 1.0 - part_y), (1, part_y)):
        for step_x, weight_x in ((0, 1.0 - part_x), (1, part_x)):
            shifted = torch.roll(padded, shifts=(whole_y + step_y, whole_x + step_x), dims=(-2, -1))
            result += weight_y * weight_x * shifted
    return result[..., pad:-pad, pad:-pad]


def _smooth_within(field: Tensor, inside: Tensor, radius: float) -> tuple[Tensor, Tensor]:
    """Gaussian smoothing of a field using only values inside the puddle.

    Also returns the share of each cell's surroundings that is inside the puddle. Where
    that share is small there is too little water to average over and the result is not smooth.
    """
    reach = int(3 * radius)
    offsets = torch.arange(-reach, reach + 1, device=field.device, dtype=field.dtype)
    kernel = torch.exp(-0.5 * (offsets / radius) ** 2)
    kernel = kernel / kernel.sum()
    present = inside.to(field.dtype)
    stacked = torch.stack((field * present, present)).reshape(-1, 1, *field.shape[-2:])
    stacked = F.conv2d(stacked, kernel.reshape(1, 1, -1, 1), padding=(reach, 0))
    stacked = F.conv2d(stacked, kernel.reshape(1, 1, 1, -1), padding=(0, reach))
    smoothed, coverage = stacked.reshape(2, *field.shape)
    return torch.where(inside, smoothed / coverage.clamp(min=1e-6), field), coverage


@dataclass(frozen=True)
class _Film:
    """The fields that determine the water flux during one substep."""

    water: Tensor
    pressure: Tensor  # depth, paper relief and the pull of wetted paper
    curvature: Tensor  # curvature of the water surface, on which surface tension acts
    pool_pressure: Tensor  # pressure of the smoothed film: depth and surface tension at the scale of the pool
    body: Tensor  # 1 in the body of a pool, falling to 0 where the film is patchy
    thickness: Tensor  # total pigment concentration, which thickens the paint and lowers its surface tension
    wet: Tensor
    advance: Tensor  # depth a puddle must reach before its edge moves onto each cell
    wicking: Tensor  # mobility of water along the surface of damp paper


def _water_flux(film: _Film, p: "SimulationParameters", rate: float, axis: int, pull: float | Tensor) -> Tensor:
    """Water crossing each face in one substep; positive toward the higher index."""
    depth_lower, depth_upper = _faces(film.water, axis)
    depth = (0.5 * (depth_lower + depth_upper)).clamp(max=p.mobility_depth_limit)
    thick_lower, thick_upper = _faces(film.thickness, axis)
    slowed = rate / (1.0 + p.viscosity * 0.5 * (thick_lower + thick_upper))
    mobility = slowed * depth**2
    # Damp paper also carries a little water along its own surface, however thin the film. That
    # water answers to depth and to the pull of the paper, not to the shape of a free surface:
    # given surface tension to act on, it pumps a thin broken film into deep drops.
    wicking = slowed * torch.minimum(*_faces(film.wicking, axis))

    lower, upper = _faces(film.pressure, axis)
    flux = (mobility + wicking) * (lower - upper + pull)

    # Surface tension drives water toward where the surface is more concave. The term is
    # stiff, so it is damped to keep the explicit update stable (after Vantzos et al. 2018);
    # the cost is that it acts fully at small scales and only slowly at large ones.
    curve_lower, curve_upper = _faces(film.curvature, axis)
    flux = flux + mobility * p.surface_tension * (curve_upper - curve_lower) / (
        1.0 + SURFACE_TENSION_DAMPING * mobility * p.surface_tension
    )

    # At the scale of the pool neither levelling nor surface tension is stiff, so water
    # moves at a rate much nearer its true one.
    pool_lower, pool_upper = _faces(film.pool_pressure, axis)
    flux = flux + p.pool_speed * mobility * (pool_lower - pool_upper) * torch.minimum(*_faces(film.body, axis))

    # The edge of a puddle holds until the water behind it is deep enough to advance.
    wet_lower, wet_upper = _faces(film.wet, axis)
    advance_lower, advance_upper = _faces(film.advance, axis)
    # On a tilted sheet the weight of the water bears on its lower edge, which gives way sooner
    # there (and later at the upper edge): this is what lets a loaded passage run.
    downhill = TILT_RELEASE * torch.as_tensor(pull, device=film.water.device)
    open_upward = wet_upper | (depth_lower > advance_upper * (1.0 - downhill).clamp(0.1, 2.0))
    open_downward = wet_lower | (depth_upper > advance_lower * (1.0 + downhill).clamp(0.1, 2.0))
    return torch.where(flux > 0, flux * open_upward, flux * open_downward)


def _surface_stream(film: _Film, p: "SimulationParameters", rate: float, axis: int) -> Tensor:
    """Volume of surface water streaming across each face in one substep, toward clearer water."""
    depth_lower, depth_upper = _faces(film.water, axis)
    depth = (0.5 * (depth_lower + depth_upper)).clamp(max=p.mobility_depth_limit)
    thick_lower, thick_upper = _faces(film.thickness, axis)
    wet_lower, wet_upper = _faces(film.wet, axis)
    # A surface stream needs a film deep enough to have a free surface: it runs in shiny
    # water and dies away as the film thins to a moist sheen.
    free = ((depth - p.stream_minimum_depth) / p.stream_minimum_depth).clamp(0, 1)
    # The stream spreads paint as diffusion does, the faster the thicker the paint. One explicit
    # substep can carry only so much: beyond that the paint would overshoot from cell to cell and
    # settle into a checkerboard, so the stream is held to the fastest rate that stays smooth.
    spreading = rate * depth * torch.maximum(thick_lower, thick_upper)
    held = STABLE_SPREADING / spreading.clamp(min=STABLE_SPREADING)
    return rate * held * free * depth**2 * (thick_lower - thick_upper) * (wet_lower & wet_upper)


def _outflow(flux_y: Tensor, flux_x: Tensor, like: Tensor) -> Tensor:
    """Total leaving each cell across its four faces."""
    outflow = torch.zeros_like(like)
    outflow[..., :-1, :] += flux_y.clamp(min=0)
    outflow[..., 1:, :] += (-flux_y).clamp(min=0)
    outflow[..., :, :-1] += flux_x.clamp(min=0)
    outflow[..., :, 1:] += (-flux_x).clamp(min=0)
    return outflow


def _limit_outflow(flux_y: Tensor, flux_x: Tensor, available: Tensor) -> tuple[Tensor, Tensor]:
    """Scale fluxes down so that no cell gives away more than is available to it."""
    share = (available / (_outflow(flux_y, flux_x, available) + 1e-9)).clamp(max=1.0)
    flux_y = torch.where(flux_y > 0, flux_y * share[..., :-1, :], flux_y * share[..., 1:, :])
    flux_x = torch.where(flux_x > 0, flux_x * share[..., :, :-1], flux_x * share[..., :, 1:])
    return flux_y, flux_x


def _pigment_flux(concentration: Tensor, water: Tensor, wet: Tensor, flux: Tensor, spread: float, axis: int) -> Tensor:
    """Pigment carried by the water flux, plus diffusion through the film."""
    lower, upper = _faces(concentration, axis)
    carried = torch.where(flux > 0, flux * lower, flux * upper)
    wet_lower, wet_upper = _faces(wet, axis)
    depth_lower, depth_upper = _faces(water, axis)
    depth = torch.minimum(depth_lower, depth_upper).clamp(max=1.0) * (wet_lower & wet_upper)
    # Pigment in a thin film lies against the paper and spreads little.
    return carried + spread * depth * depth * (lower - upper)


class Sheet:
    """A sheet of paper and everything on it.

    The simulation itself does not care how many sheets it is given: its fields may carry
    leading dimensions, which is how SheetBatch advances several sheets in one pass. The
    tools (brush, blot, graphite) work on a single sheet.
    """

    STATE_FIELDS = ("water", "saturation", "suspended", "deposited", "graphite")

    def __init__(
        self,
        paper: Paper,
        pigments: Sequence[Pigment],
        parameters: SimulationParameters | None = None,
    ) -> None:
        parameters = parameters or SimulationParameters()
        self.parameters = parameters
        tooth, cockle = paper.tooth, paper.cockle
        self.tooth = tooth
        self.cockle = cockle
        self.sizing = paper.sizing
        self.pigments = tuple(pigments)
        device = tooth.device
        span = parameters.capacity_maximum - parameters.capacity_minimum
        # Absorbency varies broadly across the sheet and only slightly with the grain.
        self.capacity = parameters.capacity_minimum + span * (1.0 - 0.8 * cockle - 0.2 * tooth)
        self.water = torch.zeros_like(tooth)
        self.saturation = torch.zeros_like(tooth)
        self.suspended = torch.zeros(len(pigments), *tooth.shape, device=device)
        self.deposited = torch.zeros(len(pigments), *tooth.shape, device=device)
        self.graphite = torch.zeros_like(tooth)
        self.tilt: tuple[float | Tensor, float | Tensor] = (0.0, 0.0)  # downhill pull along x and y
        self._used: set[int] = set()  # pigments that have ever been on this sheet

        def column(values: list[float]) -> Tensor:
            return torch.tensor(values, device=device).reshape(-1, 1, 1)

        self._density = column([p.density for p in pigments])
        self._staining = column([p.staining for p in pigments])
        self._granulation = column([p.granulation for p in pigments])
        ys, xs = torch.meshgrid(
            torch.arange(self.height, device=device, dtype=torch.float32),
            torch.arange(self.width, device=device, dtype=torch.float32),
            indexing="ij",
        )
        self._ys, self._xs = ys, xs

    @property
    def height(self) -> int:
        return self.tooth.shape[-2]

    @property
    def width(self) -> int:
        return self.tooth.shape[-1]

    # ------------------------------------------------------------------ state

    def state(self) -> dict[str, Tensor]:
        return {name: getattr(self, name).cpu() for name in self.STATE_FIELDS}

    def load_state(self, state: dict[str, Tensor]) -> None:
        for name in self.STATE_FIELDS:
            getattr(self, name).copy_(state[name])
        present = (self.suspended + self.deposited).flatten(1).any(dim=1)
        self._used = set(present.nonzero().flatten().tolist())

    def has_surface_water(self) -> bool:
        return bool((self.water > 0).any())

    def is_drying(self) -> bool:
        return self.has_surface_water() or bool((self.saturation > 0).any())

    def stage_fractions(self) -> dict[str, float]:
        """Share of the sheet at each working stage of the paper."""
        p = self.parameters
        shiny = self.water > 0.15
        moist = (self.water > p.wet_threshold) & ~shiny
        damp = ~shiny & ~moist & (self.saturation > p.damp_threshold * self.capacity)
        total = self.water.numel()
        fractions = {
            "shiny": float(shiny.sum()) / total,
            "moist": float(moist.sum()) / total,
            "damp": float(damp.sum()) / total,
        }
        fractions["dry"] = 1.0 - sum(fractions.values())
        return fractions

    # ------------------------------------------------------------- simulation

    def advance(self, duration: float) -> None:
        """Advance the sheet by a duration that is a multiple of the time step."""
        p = self.parameters
        remaining = duration
        while remaining > 1e-9:
            region = self._active_region()
            if region is None:
                return
            # Work on copies of the pigments actually in use, within the active region only.
            used = sorted(self._used)
            suspended = self.suspended[used][..., *region]
            deposited = self.deposited[used][..., *region]
            if bool((self.water[..., *region] > 0).any()):
                self._flow(region, p.time_step, suspended)
                self._settle(region, p.time_step, suspended, deposited, used)
                self._dry(region, p.time_step, suspended, deposited)
                remaining -= p.time_step
            else:
                dt = min(p.coarse_time_step, remaining)
                self._dry(region, dt, suspended, deposited)
                remaining -= dt
            for position, index in enumerate(used):
                self.suspended[index][..., *region] = suspended[position]
                self.deposited[index][..., *region] = deposited[position]

    def _active_region(self) -> Region | None:
        """Bounding box of everything wet or damp, with room for the edge filter."""
        active = ((self.water > 0) | (self.saturation > 0)).reshape(-1, self.height, self.width).any(dim=0)
        rows = active.any(dim=1).nonzero()
        columns = active.any(dim=0).nonzero()
        if rows.numel() == 0:
            return None
        margin = 2 * self.parameters.edge_radius + 2
        return (
            slice(max(int(rows[0]) - margin, 0), min(int(rows[-1]) + margin + 1, self.height)),
            slice(max(int(columns[0]) - margin, 0), min(int(columns[-1]) + margin + 1, self.width)),
        )

    def _flow(self, region: Region, dt: float, suspended: Tensor) -> None:
        """Move the water film and the pigment in it.

        The film obeys a thin-film equation: flux is mobility times the gradient of a
        pressure made of depth, the relief of the paper, surface tension (the
        curvature of the water surface) and the pull of wetted paper on a thin film. Paint lowers surface tension, so water is
        also drawn from paint-rich areas toward clear water. Pigment is a separate
        quantity carried by that flux and diffusing through the film.
        """
        p = self.parameters
        water = self.water[..., *region]
        tooth = self.tooth[..., *region]
        relief = p.tooth_pressure * tooth + p.cockle_pressure * self.cockle[..., *region]
        # Paper counts as fully wettable once it has taken up a modest share of its capacity.
        dampness = (self.saturation[..., *region] / (p.wettable_saturation * self.capacity[..., *region])).clamp(0, 1)
        # Sizing is uneven: where it is heavy, dry paper is harder to wet and damp paper carries
        # water more slowly, so a wet edge is held in some places and let through in others.
        sizing = self.sizing[..., *region]
        # Depth a puddle must reach before its edge advances onto a neighbouring cell: high on
        # dry paper, falling to almost nothing as the paper becomes damp. Sizing heavier than
        # average raises it and lighter sizing does not lower it, so an ordinary stroke keeps its
        # edge everywhere while a flooded one creeps forward in lobes.
        advance = (
            p.damp_advance_depth
            + p.dry_advance_depth
            * (0.7 + 0.6 * tooth)
            * torch.exp(p.sizing_unevenness * (2.0 * sizing - 1.0).clamp(min=0))
            * (1.0 - dampness) ** 2
        )
        wicking = p.wicking * dampness * torch.exp(p.wicking_unevenness * (1.0 - 2.0 * sizing))
        rate = p.flow_rate * dt / p.flow_substeps
        spread = p.pigment_diffusion * dt / p.flow_substeps
        surface_rate = p.marangoni * dt / p.flow_substeps

        for _ in range(p.flow_substeps):
            wet = water > p.wet_threshold
            concentration = suspended / water.clamp(min=1e-6)
            thickness = concentration.sum(dim=0).clamp(max=p.thickness_limit)
            wetting = p.wetting_strength * dampness * torch.exp(-water / p.wetting_depth)
            smooth, coverage = _smooth_within(water, wet, p.pool_scale)
            pool = smooth - p.surface_tension * _laplacian(smooth, wet)
            # Pool-scale forces act only where everything within reach of the smoothing is wet.
            # Near a rim, or beside even a thin dry line left inside a wash, the smoothing is
            # one-sided and its pressure is false: it once drove such washes into deep drops.
            body = ((coverage - 0.98) / 0.02).clamp(0, 1)
            fine = water + relief - wetting
            film = _Film(
                water, fine, _laplacian(water, wet), pool, body, thickness, wet, advance, wicking
            )  # fmt: skip
            flux_y = _water_flux(film, p, rate, 0, self.tilt[1])
            flux_x = _water_flux(film, p, rate, 1, self.tilt[0])

            # A cell cannot give away more water than it holds.
            flux_y, flux_x = _limit_outflow(flux_y, flux_x, water)

            # Paint lowers surface tension, so the surface of the film streams from paint-rich
            # water toward clear water while clear water returns beneath it (the Marangoni
            # effect). Pigment is carried across the pool; the depth of the water is unchanged.
            stream_y = _surface_stream(film, p, surface_rate, 0)
            stream_x = _surface_stream(film, p, surface_rate, 1)
            stream_y, stream_x = _limit_outflow(stream_y, stream_x, 0.5 * water)

            pigment_y = _pigment_flux(concentration, water, wet, flux_y + stream_y, spread, 0)
            pigment_x = _pigment_flux(concentration, water, wet, flux_x + stream_x, spread, 1)
            # Flow, stream and diffusion together must not take more of a pigment than a cell holds.
            pigment_y, pigment_x = _limit_outflow(pigment_y, pigment_x, suspended)
            _transport(water, flux_y, flux_x)
            _transport(suspended, pigment_y, pigment_x)
            water.clamp_(min=0)
            suspended.clamp_(min=0)

    def _settle(self, region: Region, dt: float, suspended: Tensor, deposited: Tensor, used: list[int]) -> None:
        """Exchange pigment between suspension and the paper (Curtis section 4.5)."""
        p = self.parameters
        tooth = self.tooth[..., *region]
        per_pigment = (-1, *([1] * (suspended.dim() - 1)))
        density = self._density[used].reshape(per_pigment)
        staining = self._staining[used].reshape(per_pigment)
        granulation = p.granulation_strength * self._granulation[used].reshape(per_pigment)
        dt = dt * p.settling_rate
        down = suspended * (1.0 - tooth * granulation) * density * dt
        up = deposited * (1.0 + (tooth - 1.0) * granulation) * (density / staining) * (p.resolubility * dt)
        transfer = (down - up) * (self.water[..., *region] > p.wet_threshold)
        transfer = torch.maximum(torch.minimum(transfer, suspended), -deposited)
        suspended -= transfer
        deposited += transfer

    def _dry(self, region: Region, dt: float, suspended: Tensor, deposited: Tensor) -> None:
        p = self.parameters
        water = self.water[..., *region]
        saturation = self.saturation[..., *region]
        interior = (water > p.wet_threshold).float().reshape(-1, 1, *water.shape[-2:])
        for _ in range(2):
            interior = F.avg_pool2d(interior, 2 * p.edge_radius + 1, stride=1, padding=p.edge_radius)
        evaporation = p.evaporation_rate * dt * (1.0 + p.edge_evaporation * (1.0 - interior.reshape(water.shape)))
        had_water = water > 0
        water.sub_(evaporation).clamp_(min=0)

        room = (self.capacity[..., *region] - saturation).clamp(min=0)
        absorbed = torch.minimum(water, p.absorption_rate * dt * room)
        # Water soaking into the paper draws pigment into the fibres with it.
        drawn = suspended * (p.absorbed_pigment * absorbed / water.clamp(min=1e-6))
        suspended -= drawn
        deposited += drawn
        water -= absorbed
        saturation += absorbed

        seep_y = p.capillary_diffusion * dt * torch.sub(*_faces(saturation, 0))
        seep_x = p.capillary_diffusion * dt * torch.sub(*_faces(saturation, 1))
        _transport(saturation, seep_y, seep_x)
        saturation.sub_(p.paper_evaporation_rate * dt * (water <= 0)).clamp_(min=0)

        # Pigment left behind by water that has gone stays on the paper.
        stranded = had_water & (water <= 1e-5)
        deposited += suspended * stranded
        suspended *= ~stranded

    # ----------------------------------------------------------------- tools

    def _coverage(
        self,
        points: Tensor,
        radii: Tensor,
        softness: float,
        irregular: bool = False,
        margin: float = 0.0,
        tip: float = 1.0,
        rounded: bool = False,
        slant: float = 0.0,
    ) -> tuple[slice, slice, Tensor]:
        """Soft coverage in [0, 1] of a swept path of circles, within its bounding box.

        An irregular edge follows the grain and the undulation of the sheet, as a wet edge does.
        A tip shallower than 1.0 is a flat head: the mark ends square (or in a curve if rounded, or
        at an angle if slanted) and a brush held still leaves a bar across the sheet.
        """
        reach = float(radii.max()) * (1.0 + abs(slant)) + 2.0 + margin
        x0 = max(int(float(points[:, 0].min()) - reach), 0)
        x1 = min(int(float(points[:, 0].max()) + reach) + 1, self.width)
        y0 = max(int(float(points[:, 1].min()) - reach), 0)
        y1 = min(int(float(points[:, 1].max()) + reach) + 1, self.height)
        rows, columns = slice(y0, max(y1, y0)), slice(x0, max(x1, x0))
        pixel = torch.stack((self._xs[rows, columns], self._ys[rows, columns]), dim=-1)
        if len(points) == 1:
            points, radii = points.repeat(2, 1), radii.repeat(2)
            if tip < 1.0:
                points = points + torch.tensor([[0.0, -0.01], [0.0, 0.01]], device=points.device)
        start, end = points[:-1, None, None, :], points[1:, None, None, :]
        along = end - start
        offset = pixel[None] - start
        length = along.norm(dim=-1)
        position = (offset * along).sum(-1) / (length * length + 1e-9)
        fraction = position.clamp(0, 1)
        distance = (offset - fraction[..., None] * along).norm(dim=-1)
        if tip < 1.0:
            # Across the head, signed, and along the stroke in pixels. A slanted end moves along
            # the stroke in proportion to the position across it.
            across = (along[..., 0] * offset[..., 1] - along[..., 1] * offset[..., 0]) / (length + 1e-9)
            travelled = position * length + slant * across
            fraction = (travelled / (length + 1e-9)).clamp(0, 1)
            # Beyond either end of a segment the mark reaches only as far as the tip is deep.
            beyond = (travelled - travelled.clamp(min=0).minimum(length)).abs() / tip
            distance = torch.hypot(across, beyond) if rounded else torch.maximum(across.abs(), beyond)
        radius = radii[:-1, None, None] + fraction * (radii[1:, None, None] - radii[:-1, None, None])
        if irregular:
            roughness = (radius / 8.0).clamp(max=1.0) * 2.0  # fine marks keep a clean edge
            radius = radius * (0.94 + 0.12 * self.cockle[rows, columns]) + roughness * (self.tooth[rows, columns] - 0.5)
        edge = (softness * radius).clamp(min=1.0)
        coverage = ((radius - distance) / edge).clamp(0, 1).amax(dim=0)
        return rows, columns, coverage

    def apply_brush(
        self,
        points: Tensor,
        radii: Tensor,
        contact: Contact,
        concentration: Tensor,
        available_water: float,
        hairs: Tensor,
    ) -> tuple[float, Tensor]:
        """Work the brush along a short piece of a stroke.

        The hairs are a profile in [0, 1] across the width of the brush: how closely the hairs
        at each position hold together. Returns the net water and the net amount of each pigment that left the brush.
        Either can be negative: a brush takes up wet paint as well as laying it down.
        """
        travel = points[-1] - points[0]
        distance = float(travel.norm())
        rows, columns, coverage = self._coverage(
            points,
            radii,
            contact.softness,
            irregular=True,
            margin=distance,
            tip=contact.tip,
            rounded=contact.rounded,
            slant=contact.slant,
        )
        if coverage.numel() == 0:
            return 0.0, torch.zeros_like(concentration)
        tooth = self.tooth[rows, columns]
        touching = torch.sigmoid((tooth - (1.0 - contact.contact_level)) / 0.06)
        # Position of each cell across the width of the brush, and the hairs that pass over it.
        # They keep their places along a stroke, so whatever they do is drawn out into streaks.
        heading = travel / distance if distance > 0 else torch.tensor([1.0, 0.0], device=points.device)
        across = (self._ys[rows, columns] - points[0, 1]) * heading[0] - (
            self._xs[rows, columns] - points[0, 0]
        ) * heading[1]
        # The hairs are deflected a little by the surface they are dragged over, so the streaks wander.
        across = across / radii.max() + HAIR_DEFLECTION * (2.0 * self.sizing[rows, columns] - 1.0)
        place = ((across * 0.5 + 0.5).clamp(0, 1) * (len(hairs) - 1)).long()
        hair = hairs[place]
        # As a brush runs dry its hairs part into clumps, and the gaps between them leave the paper bare.
        touching = touching * ((hair - contact.splay) / 0.1 + 1.0).clamp(0, 1)
        footprint = coverage * touching
        water = self.water[rows, columns]
        suspended = self.suspended[:, rows, columns]
        deposited = self.deposited[:, rows, columns]
        paint = concentration.reshape(-1, 1, 1) * (1.0 + contact.streaking * (2.0 * hair - 1.0))
        self._used.update((concentration > 0).nonzero().flatten().tolist())

        # The hairs sweep wet paint along in the direction the brush travels.
        if distance > 0 and contact.push > 0:
            # The sweep is made in short moves so that the paint is drawn out evenly. In each move
            # the paint under the hairs advances by the push, its share of the brush's own speed.
            moves = math.ceil(distance / PUSH_MOVE)
            step = travel / moves
            radius = radii[0]
            edge = (contact.softness * radius).clamp(min=1.0)
            for move in range(moves):
                centre = points[0] + step * move
                offset = torch.hypot(self._xs[rows, columns] - centre[0], self._ys[rows, columns] - centre[1])
                under = ((radius - offset) / edge).clamp(0, 1) * touching * (coverage > 0)
                # Water passes between the hairs more easily than the paint it carries.
                for field, share in ((water, WATER_PUSH_SHARE * contact.push), (suspended, contact.push)):
                    carried = field * (share * under)
                    field -= carried
                    field += _translate(carried, float(step[0]), float(step[1]))

        # The hairs stir up pigment that has settled.
        loosened = deposited * (contact.scrub * footprint * (water > 0)) / self._staining
        deposited -= loosened
        suspended += loosened

        # Paint in the brush and paint on the sheet mix where they meet.
        mixed = contact.exchange * footprint * (paint * water - suspended)
        # Paint passes from brush to sheet readily; only the tip of the brush takes paint back up.
        mixed = torch.where(mixed < 0, PICKUP_SHARE * mixed, mixed)
        suspended += mixed
        pigment_out = mixed.sum(dim=(1, 2))

        # A brush that is not full soaks up standing water and the paint in it.
        soaked = contact.thirst * footprint * (water - contact.target_depth).clamp(min=0)
        taken = suspended * (soaked / water.clamp(min=1e-6))
        suspended -= taken
        water -= soaked
        pigment_out -= taken.sum(dim=(1, 2))

        # The brush fills the paper to its target depth, and keeps releasing while it rests.
        fill = (contact.target_depth * footprint - water).clamp(min=0) * 0.7
        added = torch.maximum(fill, contact.release * footprint * (water < MAXIMUM_DEPTH))
        used = float(added.sum())
        if used > available_water:
            added *= available_water / used
            used = available_water
        water += added
        suspended += added * paint
        pigment_out += (added * paint).sum(dim=(1, 2))
        return used - float(soaked.sum()), pigment_out

    def blot(self, points: Tensor, radii: Tensor) -> None:
        """Press absorbent tissue onto the sheet."""
        rows, columns, coverage = self._coverage(points, radii, 0.3)
        self.water[rows, columns] *= 1.0 - 0.9 * coverage
        self.suspended[:, rows, columns] *= 1.0 - 0.9 * coverage
        self.saturation[rows, columns] *= 1.0 - 0.3 * coverage

    def draw_graphite(self, points: Tensor, radii: Tensor, darkness: float) -> None:
        rows, columns, coverage = self._coverage(points, radii, 1.0)
        mark = coverage * (0.35 + 0.65 * self.tooth[rows, columns]) * darkness
        self.graphite[rows, columns] = torch.maximum(self.graphite[rows, columns], mark)

    def erase_graphite(self, points: Tensor, radii: Tensor) -> None:
        rows, columns, coverage = self._coverage(points, radii, 0.5)
        self.graphite[rows, columns] *= 1.0 - coverage


class SheetBatch:
    """Several sheets of the same size and paint box, advanced together in one pass.

    Each sheet keeps its own paper, brush work and tilt. Their water and pigment are held
    in one stack, of which each sheet sees its own slice, so time passes on all of them
    for about the cost of one.
    """

    def __init__(self, sheets: Sequence[Sheet]) -> None:
        first = sheets[0]
        for sheet in sheets:
            if (sheet.tooth.shape, sheet.pigments, sheet.parameters) != (
                first.tooth.shape,
                first.pigments,
                first.parameters,
            ):
                raise ValueError("sheets in a batch must share their size, pigments and parameters")
        self.sheets = tuple(sheets)
        paper = Paper(
            *(torch.stack([getattr(sheet, name) for sheet in sheets]) for name in ("tooth", "cockle", "sizing"))
        )
        self._stack = Sheet(paper, first.pigments, first.parameters)
        for index, sheet in enumerate(sheets):
            for name in ("water", "saturation"):
                held = getattr(self._stack, name)[index]
                held.copy_(getattr(sheet, name))
                setattr(sheet, name, held)
            for name in ("suspended", "deposited"):
                held = getattr(self._stack, name)[:, index]
                held.copy_(getattr(sheet, name))
                setattr(sheet, name, held)

    def advance(self, duration: float) -> None:
        """Advance every sheet by a duration that is a multiple of the time step."""
        stack = self._stack
        stack._used = set().union(*(sheet._used for sheet in self.sheets))
        device = stack.tooth.device
        stack.tilt = (
            torch.tensor([float(sheet.tilt[0]) for sheet in self.sheets], device=device).reshape(-1, 1, 1),
            torch.tensor([float(sheet.tilt[1]) for sheet in self.sheets], device=device).reshape(-1, 1, 1),
        )
        stack.advance(duration)

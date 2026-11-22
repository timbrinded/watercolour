"""Watercolor sheet simulation.

The model follows Curtis, Anderson, Seims, Fleischer and Salesin,
"Computer-Generated Watercolor" (SIGGRAPH 1997): a film of surface water that
carries suspended pigment, a layer of pigment deposited on the paper, and water
held inside the paper. Surface flow is a thin-film flux driven by the height of
the water surface instead of the paper's staggered-grid velocity solver.

Paint laid over paint that has dried forms a new layer, as Curtis's glazes do. The
top layer and the dried layer under it are kept as pigment, and water lifts from
both. A third layer merges the two older ones where that changes nothing visible;
elsewhere the oldest is kept only as the colour it shows.

Lengths are in pixels, time in seconds, water depth in arbitrary units where 1.0
is a full wash.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from functools import cached_property

import torch
import torch.nn.functional as F
from torch import Tensor

from . import dry_media
from .optics import GRAPHITE_SHADE, lay_over, layer, under
from .paper import COLD_PRESS_GRAIN, PAPER_COLOR, Grain, Paper, generate_paper
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
    # Deepest film whose depth adds to the surface stream. Its square is the fastest the film may flow, which the
    # explicit substep must contain.
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
    sedimentation: float = 22.0  # how fast a granulating pigment in deep water rolls down the grain
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
    twist: float  # how far the edge of a flat head is turned from square to its travel, in radians
    target_depth: float  # water depth the brush tries to leave behind
    draw_depth: float  # depth of film below which the brush no longer soaks water up
    contact_level: float  # how far below the highest peak the hairs reach; short of the grain's depth, only peaks
    exchange: float  # how strongly the brush mixes with paint already on the sheet
    scrub: float  # how strongly the brush disturbs deposited pigment
    release: float  # water depth a resting brush adds per time step
    thirst: float  # how strongly the brush soaks up standing water
    push: float  # share of the brush's speed that it imparts to the wet paint under its hairs
    carry: float  # share of the wet paint under the hairs that the tip takes up and carries along
    uptake: float  # share of what the hairs loosen or carry that is drawn up into the body of the brush
    splay: float  # share of the brush's width where the hairs have parted and do not touch the paper
    streaking: float  # how unevenly paint is held across the hairs


Region = tuple[slice, slice]

# Depth of film that stands over the peaks of the grain. A deeper film is an unbroken, shining
# surface; a thinner one lies in the valleys and is broken up by the grain.
SHINE_DEPTH = 0.15

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

# Distance, in widths of the brush, over which its tip gives back the wet paint it has carried off,
# and the share it gives back in one time step when it is resting.
CARRY_REACH = 2.5
RESTING_SHED = 0.1

# Depth of film below which settled pigment does not roll at all, and the depth at which it
# rolls freely. A granulating paint in an ordinary wash stays where it settles; charged into
# deep water it gathers in the hollows of the grain.
SEDIMENT_ONSET_DEPTH = 0.5
SEDIMENT_FREE_DEPTH = 1.0

# How readily settled grains roll, as a share of how readily grains in suspension drift.
SETTLED_ROLLING = 0.1

# Depth of film at which water already on the sheet joins the hairs to the paper across the whole grain.
BRIDGING_FILM = 0.05

# Masking fluid: a cell this fully covered is sealed, so no water crosses into it or out of it.
MASK_SEALED = 0.5
# Softness of the edge of a line of masking fluid, as a share of its radius: it dries with a crisp edge.
MASK_EDGE_SOFTNESS = 0.15
# Narrowest radius of masking fluid, after any taper. The finest line then seals an unbroken band one to two cells wide
# at every angle; a thinner one sealed only along rows and columns and broke into dashes at other angles.
MASK_SMALLEST_RADIUS = 1.25

# A brush or pen reaches a cell where it covers more than this share of it.
LAYER_FOOTPRINT = 0.02
# A cell holds paint when it has more than this much pigment.
LAYER_PIGMENT = 1e-3
# When a third layer begins, the two older ones are merged into one where that changes the cell's colour by no more than
# this in any channel, as it does not for transparent glazes or the same paint twice; elsewhere, as under covering
# paint, the oldest is pressed into the colour beneath.
LAYER_MERGE_ERROR = 0.005
# Below this share of the light reaching through both layers of paint, the colour beneath them cannot be told from
# the picture, and is left as it was when paint moves between the layers.
LAYER_THROUGH = 1e-3


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


def _along(values: Tensor, fraction: Tensor) -> Tensor:
    """Values given at each point of a swept path, read at each cell of each of its segments (Sheet._sweep). A single
    point's value holds along the one segment a dab is swept as."""
    if len(values) == 1:
        values = values.repeat(2)
    return values[:-1, None, None] + fraction * (values[1:, None, None] - values[:-1, None, None])


def _turned_head(along: Tensor, across: Tensor, length: Tensor, tip: float, rounded: bool, twist: float) -> Tensor:
    """Distance from each cell to a flat head, turned by an angle, at the place on its path nearest that cell.

    The head is a bar: wide across its edge and shallow through its depth (the tip). Distance is
    measured so that the bar's outline is at one radius. The head may stand anywhere along the
    segment; the best place is found among the few where the distance can be least.
    """
    sine, cosine = math.sin(twist), math.cos(twist)

    def measure(ahead: Tensor) -> Tensor:
        # How far the cell lies ahead of the head, resolved along the head's edge and through its depth.
        edge = -ahead * sine + across * cosine
        depth = (ahead * cosine + across * sine) / tip
        return torch.hypot(edge, depth) if rounded else torch.maximum(edge.abs(), depth.abs())

    # Places where the distance can be least: where the cell is level with the edge or the depth of
    # the head, where the two measures are equal, and where their combined square is least.
    places = [torch.zeros_like(across)]
    if abs(sine) > 1e-6:
        places.append(across * cosine / sine)
    if abs(cosine) > 1e-6:
        places.append(-across * sine / cosine)
    for sign in (1.0, -1.0):
        slope = -sine - sign * cosine / tip
        if abs(slope) > 1e-6:
            places.append(across * (sign * sine / tip - cosine) / slope)
    places.append(across * sine * cosine * (1.0 - 1.0 / tip**2) / (sine**2 + cosine**2 / tip**2))
    # The head stays on its segment, so the cell is ahead of it by between (along - length) and along.
    return torch.stack([measure(torch.maximum(torch.minimum(place, along), along - length)) for place in places]).amin(
        0
    )


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
    # A film flowing over paper it does not slip on carries h^3/(3 viscosity) per unit of pressure
    # gradient (lubrication theory). The roughness of the paper moves the no-slip plane into the
    # grain and holds a film that lies within it, so it slows thin films rather than letting them
    # slip: the mobility is the cube of the depth, with no square term. It is taken relative to a
    # full wash, at which the flow rates were set, so a full wash flows as before. The cube is held
    # at the square of the depth limit, the fastest flow the explicit substep was built to contain,
    # so every film deeper than about 1.19 moves at that one rate.
    mobility = slowed * (depth**3).clamp(max=p.mobility_depth_limit**2)
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
    # A stream driven by a stress on the surface, not by a pressure, carries h^2/(2 viscosity):
    # it stays a square of the depth where the pressure-driven film flow is a cube.
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


def _sediment_flux(suspended: Tensor, water: Tensor, wet: Tensor, downhill: Tensor, axis: int) -> Tensor:
    """Pigment rolling down the grain across each face: a share of what the higher cell holds.

    It rolls only where there is depth of water to carry it. In the film of an ordinary wash
    it stays where it settled; in deep water a granulating paint gathers in the hollows.
    """
    lower, upper = _faces(suspended, axis)
    wet_lower, wet_upper = _faces(wet, axis)
    depth = torch.minimum(*_faces(water, axis)) * (wet_lower & wet_upper)
    freedom = ((depth - SEDIMENT_ONSET_DEPTH) / (SEDIMENT_FREE_DEPTH - SEDIMENT_ONSET_DEPTH)).clamp(0, 1)
    return torch.where(downhill > 0, downhill * lower, downhill * upper) * freedom * freedom


class Sheet:
    """A sheet of paper and everything on it.

    The simulation itself does not care how many sheets it is given: its fields may carry
    leading dimensions, which is how SheetBatch advances several sheets in one pass. The
    tools (brush, blot, graphite) work on a single sheet.
    """

    # Fields that a painting begun before masking fluid, crisp marks, fixative or layers of paint existed has no record
    # of; they start empty, except that which paint has dried is worked out from the water (load_state).
    OPTIONAL_STATE_FIELDS = (
        "mask",
        "mask_water",
        "mask_pigment",
        "crisp",
        "fixative",
        "buried",
        "substrate_change",
        "dried_paint",
    )
    STATE_FIELDS = ("water", "saturation", "suspended", "deposited", "graphite", *OPTIONAL_STATE_FIELDS)

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
        self.ground = (
            torch.tensor(PAPER_COLOR, device=device).reshape(3, 1, 1) if paper.ground is None else paper.ground
        )
        self.relief_shading = paper.relief_shading
        self.peak, self.valley = paper.peak, paper.valley
        span = parameters.capacity_maximum - parameters.capacity_minimum
        # Absorbency varies broadly across the sheet and only slightly with the grain.
        self.capacity = parameters.capacity_minimum + span * (1.0 - 0.8 * cockle - 0.2 * tooth)
        self.water = torch.zeros_like(tooth)
        self.saturation = torch.zeros_like(tooth)
        self.suspended = torch.zeros(len(pigments), *tooth.shape, device=device)
        self.deposited = torch.zeros(len(pigments), *tooth.shape, device=device)
        self.graphite = torch.zeros_like(tooth)
        # Masking fluid on the paper (0 to 1), and the water and paint that have landed on top of it. They
        # sit on the rubber, not in the paper, and come away with it.
        self.mask = torch.zeros_like(tooth)
        self.mask_water = torch.zeros_like(tooth)
        self.mask_pigment = torch.zeros(len(pigments), *tooth.shape, device=device)
        # Cells whose paint ends at a crisp edge: paper sealed by masking fluid, and ink a pen laid on dry paper. The
        # picture shares no paint between such a cell and one beside it that is not crisp. A cell stays crisp for good.
        self.crisp = torch.zeros_like(tooth, dtype=torch.bool)
        # Fixative (0 to 1), alum size or acrylic medium, which locks the paint settled on the paper under it.
        self.fixative = torch.zeros_like(tooth)
        # Layers of paint. `suspended` and `deposited` are the top layer. `buried` is the dried layer under it, which
        # water lifts from as from the top. Paint further down is kept only as the reflectance it adds to the bare
        # sheet and its pencil marks, and can no longer be lifted or moved.
        self.buried = torch.zeros(len(pigments), *tooth.shape, device=device)
        self.substrate_change = torch.zeros(3, *tooth.shape, device=device)
        # Cells whose top layer holds paint that has dried. Paint laid there begins a new layer over it, even where clear
        # water has wet it again; paint laid on paint that has not dried mixes with it.
        self.dried_paint = torch.zeros_like(tooth, dtype=torch.bool)
        self.tilt: tuple[float | Tensor, float | Tensor] = (0.0, 0.0)  # downhill pull along x and y
        self._used: set[int] = set()  # pigments that have ever been on this sheet
        # Sheets whose layers this sheet's time steps open: itself, or the sheets a batch's stack holds.
        self._painted_sheets: tuple[Sheet, ...] = (self,)

        def column(values: list[float]) -> Tensor:
            return torch.tensor(values, device=device).reshape(-1, 1, 1)

        self._density = column([p.density for p in pigments])
        self._staining = column([p.staining for p in pigments])
        self._granulation = column([p.granulation for p in pigments])
        self.pigment_absorption = torch.tensor([p.absorption for p in pigments], device=device)
        self.pigment_scattering = torch.tensor([p.scattering for p in pigments], device=device)
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

    @property
    def grain_depth(self) -> float:
        """Height of the grain from valley to peak; 1 on cold press."""
        return self.peak - self.valley

    @cached_property
    def paper_reflectance(self) -> Tensor:
        """Colour of the bare sheet under an even light, its grain shaded by its relief, with shape (3, H, W)."""
        relief = self.tooth - F.avg_pool2d(self.tooth[None, None], 5, stride=1, padding=2)[0, 0]
        return self.ground * (1.0 + self.relief_shading * relief)

    def beneath_paint(self, rows: slice = slice(None), columns: slice = slice(None)) -> Tensor:
        """Reflectance of what lies under the paint still kept as pigment: the sheet, the pencil drawn on it, and the
        paint and dry marks pressed down, with shape (3, H, W) or that of the rows and columns given."""
        through = (1.0 - GRAPHITE_SHADE * self.graphite[rows, columns]).clamp(0.0, 1.0)
        paper = self.paper_reflectance[:, rows, columns] * through
        return paper + self.substrate_change[:, rows, columns]

    # ----------------------------------------------------------------- layers

    def _open_layer(self, rows: slice, columns: slice, reaching: Tensor, reached: Tensor) -> None:
        """Begin a new layer in the cells a tool first reaches with water or paint, where the top layer holds dried
        paint. Reached records, over the whole sheet, the cells the tool's line has reached so far; a line opens a cell
        once. Where the top layer holds paint that has not dried, the new paint mixes into it."""
        opening = reaching & ~reached[rows, columns] & self.dried_paint[rows, columns]
        reached[rows, columns] |= reaching
        if bool(opening.any()):
            self._begin_layer(rows, columns, opening)

    def _open_under_water(self, region: Region) -> None:
        """Begin a new layer wherever water stands on dried paint, clear or carrying paint: the dried paint lies beneath
        whatever settles out of that water, and the water lifts from it as from the top layer. A batch's stack opens the
        layers of each sheet it holds, as that sheet would alone."""
        rows, columns = region
        opening = self.dried_paint[..., rows, columns] & (
            self.water[..., rows, columns] > self.parameters.wet_threshold
        )
        if not bool(opening.any()):
            return
        for sheet, own in zip(self._painted_sheets, opening.reshape(-1, *opening.shape[-2:])):
            cells = own.nonzero()
            if cells.numel() == 0:
                continue
            (top, left), (bottom, right) = cells.amin(0).tolist(), (cells.amax(0) + 1).tolist()
            sheet._begin_layer(
                slice(rows.start + top, rows.start + bottom),
                slice(columns.start + left, columns.start + right),
                own[top:bottom, left:right],
            )

    def _keep_picture(
        self,
        rows: slice,
        columns: slice,
        move: Callable[[tuple[slice, slice], tuple[slice, slice], Tensor, Tensor, Tensor], Tensor],
    ) -> None:
        """Move paint between the layers in the rows and columns without changing the picture.

        Move does it, given the cells worked on, the rows and columns within them, and the colour beneath, the colour of
        the buried layer over it and the colour seen, each over the cells worked on; it returns the colour beneath for
        cells no light reaches. Every cell shares a little of its neighbours' paint, so moving paint changes the colour of the
        cells beside it as well; each of them, like each cell in the rows and columns, keeps the colour it showed, the
        colour beneath taking up the difference.
        """
        # The cells whose colour can change are those in the rows and columns and one more on every side. Their colours
        # depend on one cell further out.
        (top, bottom, _), (left, right, _) = rows.indices(self.height), columns.indices(self.width)
        changing = (
            slice(max(top - 1, 0), min(bottom + 1, self.height)),
            slice(max(left - 1, 0), min(right + 1, self.width)),
        )
        around = (
            slice(max(top - 2, 0), min(bottom + 2, self.height)),
            slice(max(left - 2, 0), min(right + 2, self.width)),
        )
        within = tuple(slice(c.start - a.start, c.stop - a.start) for c, a in zip(changing, around))
        moved = (
            slice(top - around[0].start, bottom - around[0].start),
            slice(left - around[1].start, right - around[1].start),
        )
        absorption, scattering = self.pigment_absorption, self.pigment_scattering

        def colours() -> tuple[tuple[Tensor, Tensor], tuple[Tensor, Tensor]]:
            crisp = self.crisp[around]
            top_layer = self.deposited[:, *around] + self.suspended[:, *around]
            return layer(top_layer, absorption, scattering, crisp), layer(
                self.buried[:, *around], absorption, scattering, crisp
            )

        beneath = self.beneath_paint(*around)
        (top_reflectance, top_transmittance), (buried_reflectance, buried_transmittance) = colours()
        shown = lay_over(buried_reflectance, buried_transmittance, beneath)
        seen = lay_over(top_reflectance, top_transmittance, shown)
        hidden = move(around, moved, beneath, shown, seen)

        # The colour beneath that gives each changing cell the colour it showed, where any light reaches it.
        (top_reflectance, top_transmittance), (buried_reflectance, buried_transmittance) = colours()
        solved = under(buried_reflectance, buried_transmittance, under(top_reflectance, top_transmittance, seen))
        reaching = top_transmittance * buried_transmittance > LAYER_THROUGH
        background = torch.where(reaching, solved.clamp(0.0, 1.0), hidden)
        self.substrate_change[:, *changing] += (background - beneath)[:, *within]

    def _begin_layer(self, rows: slice, columns: slice, opening: Tensor) -> None:
        """Move the top layer's settled paint in the opening cells, within the rows and columns, onto the buried layer,
        keeping the picture. Where the two look the same mixed as layered, they are merged and stay liftable; elsewhere
        the buried layer is pressed into the colour beneath, where nothing can lift or move it any more, and the top
        layer's paint takes its place."""

        def move(
            around: tuple[slice, slice], moved: tuple[slice, slice], beneath: Tensor, shown: Tensor, seen: Tensor
        ) -> Tensor:
            absorption, scattering = self.pigment_absorption, self.pigment_scattering
            # Merging changes a cell's colour where the top layer's settled paint over the buried layer differs from
            # the two mixed; there the buried layer is pressed down. Where no light reaches the colour beneath, a cell
            # pressed down takes the colour of its pressed paint.
            settled_paint = self.deposited[:, *around]
            crisp = self.crisp[around]
            settled = layer(settled_paint, absorption, scattering, crisp)
            mixed = layer(settled_paint + self.buried[:, *around], absorption, scattering, crisp)
            changed = (lay_over(*settled, shown) - lay_over(*mixed, beneath)).abs().amax(0) > LAYER_MERGE_ERROR
            pressed = opening & changed[moved]
            buried, deposited = self.buried[:, rows, columns], self.deposited[:, rows, columns]
            buried.copy_(torch.where(pressed, deposited, buried + deposited * opening))
            deposited *= ~opening
            self.dried_paint[rows, columns] &= ~opening
            hidden = beneath.clone()
            hidden[:, *moved] = torch.where(pressed, shown[:, *moved], beneath[:, *moved])
            return hidden

        self._keep_picture(rows, columns, move)

    def _press_down(self, rows: slice, columns: slice, cells: Tensor) -> None:
        """Press all the paint in the cells given, within the rows and columns, into the colour beneath, keeping the
        picture: what is laid on them next lies over it. The cells take a crisp edge, so the paint beside them, which
        every cell otherwise shows a little of, does not lie over what is laid on them."""

        def move(
            around: tuple[slice, slice], moved: tuple[slice, slice], beneath: Tensor, shown: Tensor, seen: Tensor
        ) -> Tensor:
            for field in (self.suspended, self.deposited, self.buried):
                field[:, rows, columns] *= ~cells
            self.dried_paint[rows, columns] &= ~cells
            self.crisp[rows, columns] |= cells
            hidden = beneath.clone()
            hidden[:, *moved] = torch.where(cells, seen[:, *moved], beneath[:, *moved])
            return hidden

        self._keep_picture(rows, columns, move)

    def _lay_on_top(
        self, rows: slice, columns: slice, cells: Tensor, reflectance: Tensor, transmittance: Tensor
    ) -> None:
        """Lay a dry mark of the reflectance and transmittance given on the cells, within the rows and columns: over
        the paint already there, which is pressed into the colour beneath, and under any paint laid later."""
        if bool((self._paint_in(rows, columns) > 0).any()):
            self._press_down(rows, columns, cells)
        beneath = self.beneath_paint(rows, columns)
        covered = lay_over(reflectance, transmittance, beneath)
        self.substrate_change[:, rows, columns] += torch.where(cells, covered - beneath, 0.0)

    def _dry_surface(self, water: Tensor, saturation: Tensor, capacity: Tensor) -> Tensor:
        """Cells with no film standing on them and paper no fuller than damp: paint there has dried, and a dry stick
        or pencil takes there."""
        p = self.parameters
        return (water <= p.wet_threshold) & (saturation <= p.damp_threshold * capacity)

    def _dry_paper(self, rows: slice, columns: slice) -> Tensor:
        """The dry cells within the rows and columns."""
        return self._dry_surface(
            self.water[rows, columns], self.saturation[rows, columns], self.capacity[rows, columns]
        )

    def _dried(self, water: Tensor, saturation: Tensor, capacity: Tensor, deposited: Tensor) -> Tensor:
        """Cells whose settled paint has dried."""
        return self._dry_surface(water, saturation, capacity) & (deposited.sum(0) > LAYER_PIGMENT)

    def mark_dried_paint(self) -> None:
        """Record the settled paint wherever the sheet is dry as dried paint, as drying would have: for a sheet saved
        before the record existed, or whose paint was set directly."""
        self.dried_paint |= self._dried(self.water, self.saturation, self.capacity, self.deposited)

    # ------------------------------------------------------------------ state

    def state(self) -> dict[str, Tensor]:
        return {name: getattr(self, name).cpu() for name in self.STATE_FIELDS}

    def load_state(self, state: dict[str, Tensor]) -> None:
        for name in self.STATE_FIELDS:
            if name in state:
                getattr(self, name).copy_(state[name])
            elif name in self.OPTIONAL_STATE_FIELDS:
                getattr(self, name).zero_()
            else:
                raise KeyError(name)
        if "dried_paint" not in state:
            self.mark_dried_paint()
        present = (self.suspended + self.deposited + self.buried).flatten(1).any(dim=1)
        self._used = set(present.nonzero().flatten().tolist())

    def has_surface_water(self) -> bool:
        return bool((self.water > 0).any()) or bool((self.mask_water > 0).any())

    def is_drying(self) -> bool:
        return self.has_surface_water() or bool((self.saturation > 0).any())

    def stage_fractions(self) -> dict[str, float]:
        """Share of the sheet at each working stage of the paper."""
        p = self.parameters
        shiny = self.water > SHINE_DEPTH * self.grain_depth
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

    def wetness_at(self, x: float, y: float, radius: int = 2) -> dict[str, float]:
        """How wet the sheet is about a point, on two continuous scales.

        The film is the depth of water standing on the surface; the paper is how full of water
        the sheet itself is, from 0 (dry) to 1 (it can take up no more).
        """
        rows = slice(max(round(y) - radius, 0), min(round(y) + radius + 1, self.height))
        columns = slice(max(round(x) - radius, 0), min(round(x) + radius + 1, self.width))
        fullness = (self.saturation / self.capacity).clamp(0, 1)
        return {"film": float(self.water[rows, columns].mean()), "paper": float(fullness[rows, columns].mean())}

    def wetness_summary(self) -> dict[str, float]:
        """The film at its deepest and at its usual depth where there is one, and how full the damp paper is."""
        film = self.water[self.water > self.parameters.wet_threshold]
        fullness = (self.saturation / self.capacity).clamp(0, 1)
        damp = fullness[fullness > 0.01]
        return {
            "film_deepest": float(film.max()) if film.numel() else 0.0,
            "film_typical": float(film.median()) if film.numel() else 0.0,
            "paper_fullness": float(damp.mean()) if damp.numel() else 0.0,
        }

    # ------------------------------------------------------------- simulation

    def advance(self, duration: float) -> None:
        """Advance the sheet by a duration that is a multiple of the time step."""
        p = self.parameters
        remaining = duration
        while remaining > 1e-9:
            region = self._active_region()
            if region is None:
                return
            self._open_under_water(region)
            # Work on copies of the pigments actually in use, within the active region only.
            used = sorted(self._used)
            suspended_region, deposited_region = self.suspended[..., *region], self.deposited[..., *region]
            suspended, deposited = suspended_region[used], deposited_region[used]
            if bool((self.water[..., *region] > 0).any()):
                buried_region = self.buried[..., *region]
                buried = buried_region[used]
                self._flow(region, p.time_step, suspended, used)
                self._settle(region, p.time_step, suspended, deposited, buried, used)
                self._dry(region, p.time_step, suspended, deposited)
                buried_region[used] = buried
                remaining -= p.time_step
            else:
                dt = min(p.coarse_time_step, remaining)
                self._dry(region, dt, suspended, deposited)
                remaining -= dt
            suspended_region[used] = suspended
            deposited_region[used] = deposited

    def _active_region(self) -> Region | None:
        """Bounding box of everything wet or damp, with room for the edge filter."""
        active = (self.water > 0) | (self.saturation > 0) | (self.mask_water > 0)
        active = active.reshape(-1, self.height, self.width).any(dim=0)
        rows = active.any(dim=1).nonzero()
        columns = active.any(dim=0).nonzero()
        if rows.numel() == 0:
            return None
        margin = 2 * self.parameters.edge_radius + 2
        return (
            slice(max(int(rows[0]) - margin, 0), min(int(rows[-1]) + margin + 1, self.height)),
            slice(max(int(columns[0]) - margin, 0), min(int(columns[-1]) + margin + 1, self.width)),
        )

    def _flow(self, region: Region, dt: float, suspended: Tensor, used: list[int]) -> None:
        """Move the water film and the pigment in it.

        The film obeys a thin-film equation: flux is mobility, the cube of the depth, times
        the gradient of a pressure made of depth, the relief of the paper, surface tension
        (the curvature of the water surface) and the pull of wetted paper on a thin film.
        Paint lowers surface tension, so water is also drawn from paint-rich areas toward
        clear water. Pigment is a separate quantity carried by that flux and diffusing
        through the film.
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
        # Masking fluid seals the paper: no water crosses a face with a sealed cell on either side, so a
        # wash meets the rubber as it meets a wall, and its paint gathers along the edge.
        sealed = self.mask[..., *region] >= MASK_SEALED
        open_y = ~torch.logical_or(*_faces(sealed, 0))
        open_x = ~torch.logical_or(*_faces(sealed, 1))
        rate = p.flow_rate * dt / p.flow_substeps
        spread = p.pigment_diffusion * dt / p.flow_substeps
        surface_rate = p.marangoni * dt / p.flow_substeps
        # Heavy pigment sinks through the film and rolls down the slopes of the grain into its
        # hollows. The paper's own relief is fixed, so its slope across each face is too. Only a
        # paint that really granulates does this: the effect falls away as the square of the tendency.
        per_pigment = (-1, *([1] * (suspended.dim() - 1)))
        drift = p.sedimentation * dt / p.flow_substeps * self._granulation[used].reshape(per_pigment) ** 2
        downhill_y = drift * torch.sub(*_faces(tooth, 0))
        downhill_x = drift * torch.sub(*_faces(tooth, 1))

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
            flux_y = _water_flux(film, p, rate, 0, self.tilt[1]) * open_y
            flux_x = _water_flux(film, p, rate, 1, self.tilt[0]) * open_x

            # A cell cannot give away more water than it holds.
            flux_y, flux_x = _limit_outflow(flux_y, flux_x, water)

            # Paint lowers surface tension, so the surface of the film streams from paint-rich
            # water toward clear water while clear water returns beneath it (the Marangoni
            # effect). Pigment is carried across the pool; the depth of the water is unchanged.
            stream_y = _surface_stream(film, p, surface_rate, 0) * open_y
            stream_x = _surface_stream(film, p, surface_rate, 1) * open_x
            stream_y, stream_x = _limit_outflow(stream_y, stream_x, 0.5 * water)

            pigment_y = _pigment_flux(concentration, water, wet, flux_y + stream_y, spread, 0)
            pigment_x = _pigment_flux(concentration, water, wet, flux_x + stream_x, spread, 1)
            pigment_y = pigment_y + _sediment_flux(suspended, water, wet, downhill_y, 0)
            pigment_x = pigment_x + _sediment_flux(suspended, water, wet, downhill_x, 1)
            # Flow, stream and diffusion together must not take more of a pigment than a cell holds.
            pigment_y, pigment_x = _limit_outflow(pigment_y, pigment_x, suspended)
            _transport(water, flux_y, flux_x)
            _transport(suspended, pigment_y, pigment_x)
            water.clamp_(min=0)
            suspended.clamp_(min=0)

    def _settle(
        self, region: Region, dt: float, suspended: Tensor, deposited: Tensor, buried: Tensor, used: list[int]
    ) -> None:
        """Exchange pigment between suspension and the paper (Curtis section 4.5).

        Water lifts from the buried layer as from the top one; what it lifts settles back into the top layer.
        """
        p = self.parameters
        tooth = self.tooth[..., *region]
        per_pigment = (-1, *([1] * (suspended.dim() - 1)))
        density = self._density[used].reshape(per_pigment)
        staining = self._staining[used].reshape(per_pigment)
        granulation = p.granulation_strength * self._granulation[used].reshape(per_pigment)
        water = self.water[..., *region]
        wet = water > p.wet_threshold
        # Paint settled on fixed paper is locked: only the share that no fixative holds can roll or lift.
        unfixed = 1.0 - self.fixative[..., *region]
        # Under deep water the grains of a granulating paint that have settled go on rolling
        # into the hollows of the grain, and there they stay: nothing spreads them out again. Grains that have dried
        # are held by the gum: water that wets them again lifts them, below, but does not set them rolling.
        rolling = SETTLED_ROLLING * p.sedimentation * dt * self._granulation[used].reshape(per_pigment) ** 2
        loose = deposited * unfixed * ~self.dried_paint[..., *region]
        roll_y = _sediment_flux(loose, water, wet, rolling * torch.sub(*_faces(tooth, 0)), 0)
        roll_x = _sediment_flux(loose, water, wet, rolling * torch.sub(*_faces(tooth, 1)), 1)
        _transport(deposited, *_limit_outflow(roll_y, roll_x, loose))
        dt = dt * p.settling_rate
        loose = deposited * unfixed
        lifting = (1.0 + (tooth - 1.0) * granulation) * (density / staining) * (p.resolubility * dt)
        down = suspended * (1.0 - tooth * granulation) * density * dt
        up = loose * lifting
        transfer = (down - up) * wet
        transfer = torch.maximum(torch.minimum(transfer, suspended), -loose)
        suspended -= transfer
        deposited += transfer
        risen = (buried * unfixed * lifting * wet).clamp(max=buried)
        buried -= risen
        suspended += risen

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
        # Paint has dried once no film stands on it and the paper is no fuller than damp. Paint laid on it later is a
        # new layer, even if clear water wets it again first.
        self.dried_paint[..., *region] |= self._dried(water, saturation, self.capacity[..., *region], deposited)

        # Beads of paint on masking fluid dry where they stand: the rubber takes up nothing, so they only
        # evaporate, and as fast as the edge of a wash. Their paint dries on the rubber.
        on_mask = self.mask_water[..., *region]
        on_mask.sub_(p.evaporation_rate * dt * (1.0 + p.edge_evaporation)).clamp_(min=0)

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
        twist: float = 0.0,
    ) -> tuple[slice, slice, Tensor]:
        """Soft coverage in [0, 1] of a swept path of circles, within its bounding box.

        An irregular edge follows the grain and the undulation of the sheet, as a wet edge does.
        A tip shallower than 1.0 is a flat head: the mark ends square (or in a curve if rounded, or
        at an angle if slanted) and a brush held still leaves a bar across the sheet. A flat head
        whose edge is turned toward its direction of travel draws a narrower mark, down to a line.
        """
        rows, columns, reached, _ = self._sweep(points, radii, softness, irregular, margin, tip, rounded, slant, twist)
        return rows, columns, reached.amax(dim=0)

    def _sweep(
        self,
        points: Tensor,
        radii: Tensor,
        softness: float,
        irregular: bool = False,
        margin: float = 0.0,
        tip: float = 1.0,
        rounded: bool = False,
        slant: float = 0.0,
        twist: float = 0.0,
    ) -> tuple[slice, slice, Tensor, Tensor]:
        """The coverage of each segment of a swept path, (segments, rows, columns), within its bounding box, and how
        far along its segment each cell lies, for reading values given at each point with _along."""
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
            if twist:
                flat = _turned_head(position * length, across, length, tip, rounded, twist)
            else:
                flat = torch.hypot(across, beyond) if rounded else torch.maximum(across.abs(), beyond)
            # A step with no length has no direction to be flat across: there the head is taken as a point.
            distance = torch.where(length > 1e-6, flat, distance)

        radius = _along(radii, fraction)
        if irregular:
            roughness = (radius / 8.0).clamp(max=1.0) * 2.0  # fine marks keep a clean edge
            radius = radius * (0.94 + 0.12 * self.cockle[rows, columns]) + roughness * (self.tooth[rows, columns] - 0.5)
        edge = (softness * radius).clamp(min=1.0)
        return rows, columns, ((radius - distance) / edge).clamp(0, 1), fraction

    def apply_brush(
        self,
        points: Tensor,
        radii: Tensor,
        contact: Contact,
        concentration: Tensor,
        available_water: float,
        hairs: Tensor,
        on_tip: Tensor,
        reached: Tensor,
    ) -> tuple[float, Tensor, Tensor]:
        """Work the brush along a short piece of a stroke.

        The hairs are a profile in [0, 1] across the width of the brush: how closely the hairs
        at each position hold together. The other argument is the amount of each pigment riding on the tip
        of the brush, taken up from wet paint earlier in the stroke. Returns the net water and
        the net amount of each pigment that left the body of the brush, and what the tip now
        carries. The first two can be negative: a brush takes up wet paint as well as laying it down. Reached records
        the cells the stroke has reached: where the brush first reaches paint that has dried, it begins a new layer.
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
            twist=contact.twist,
        )
        if coverage.numel() == 0:
            return 0.0, torch.zeros_like(concentration), on_tip
        tooth = self.tooth[rows, columns]
        water = self.water[rows, columns]
        touching = torch.sigmoid((tooth - (self.peak - contact.contact_level)) / 0.06)
        # A dry or thick load catches only the peaks of dry paper. Where water already stands on
        # the sheet it bridges the grain, and the hairs meet it everywhere they pass.
        touching = torch.maximum(touching, (water / BRIDGING_FILM).clamp(0, 1))
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
        # The share of each cell that is open paper; the rest is masking fluid, which the brush meets instead.
        masked = self.mask[rows, columns]
        on_paper = footprint * (1.0 - masked)
        if available_water > 0:
            self._open_layer(rows, columns, on_paper > LAYER_FOOTPRINT, reached)
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
                under = ((radius - offset) / edge).clamp(0, 1) * touching * (coverage > 0) * (1.0 - masked)
                # Water passes between the hairs more easily than the paint it carries.
                for field, share in ((water, WATER_PUSH_SHARE * contact.push), (suspended, contact.push)):
                    carried = field * (share * under)
                    field -= carried
                    field += _translate(carried, float(step[0]), float(step[1]))

        # The hairs stir up pigment that has settled. A brush with room in it wipes up much of
        # what it loosens, which is how a drained brush lifts paint; a full one only stirs it.
        # A paint that stains less readily than the brush scrubs gives up all that lies loose on the paper, and no
        # more. Paint settled on fixed paper is locked, and the hairs loosen only the share no fixative holds.
        # The buried layer gives up paint to the hairs as the top one does.
        unfixed = 1.0 - self.fixative[rows, columns]
        scrubbing = contact.scrub * on_paper * (water > 0) / self._staining
        loosened = torch.zeros_like(suspended)
        for settled in (deposited, self.buried[:, rows, columns]):
            loose = settled * unfixed
            taken = torch.minimum(loose * scrubbing, loose)
            settled -= taken
            loosened += taken
        wiped = contact.uptake * loosened
        suspended += loosened - wiped

        # Paint in the brush and paint on the sheet mix where they meet.
        mixed = contact.exchange * on_paper * (paint * water - suspended)
        # Paint passes from brush to sheet readily; only the tip of the brush takes paint back up.
        mixed = torch.where(mixed < 0, PICKUP_SHARE * mixed, mixed)
        suspended += mixed
        pigment_out = (mixed - wiped).sum(dim=(1, 2))

        # A brush that is not full soaks up standing water and the paint in it, and the emptier
        # the brush the thinner the film it can draw from.
        soaked = contact.thirst * on_paper * (water - contact.draw_depth).clamp(min=0)
        taken = suspended * (soaked / water.clamp(min=1e-6))
        suspended -= taken
        water -= soaked
        pigment_out -= taken.sum(dim=(1, 2))

        # The brush fills the paper to its target depth, and keeps releasing while it rests. It
        # gives water only to paper drier than itself: a film deep enough for the brush to draw
        # from is left as it is, so a drained brush wipes a moist wash and does not wet it.
        fill = (contact.target_depth * on_paper - water).clamp(min=0) * 0.7 * (water <= contact.draw_depth)
        added = torch.maximum(fill, contact.release * on_paper * (water < MAXIMUM_DEPTH))
        # Over masking fluid the brush leaves beads of paint on the rubber.
        beads = self.mask_water[rows, columns]
        bead_fill = (contact.target_depth * footprint * masked - beads).clamp(min=0) * 0.7
        beaded = torch.maximum(bead_fill, contact.release * footprint * masked * (beads < MAXIMUM_DEPTH))
        used = float(added.sum() + beaded.sum())
        if used > available_water:
            added *= available_water / used
            beaded *= available_water / used
            used = available_water
        water += added
        suspended += added * paint
        beads += beaded
        self.mask_pigment[:, rows, columns] += beaded * paint
        pigment_out += (added * paint).sum(dim=(1, 2)) + (beaded * paint).sum(dim=(1, 2))

        # The tip carries off some of the wet paint it passes through and gives it back along the
        # next stretch of the stroke. This is what draws one colour out into another, pulls paint
        # from the edge of a wash, and mixes two colours stirred together in standing water.
        kept = math.exp(-distance / (CARRY_REACH * 2.0 * float(radii.max()))) * (1.0 - RESTING_SHED)
        released = on_tip * (1.0 - kept)
        # The emptier the brush, the more of what its tip carries is drawn up into its body and
        # the less goes back onto the sheet: a damp brush blends, a drained one lifts.
        drawn_up = contact.uptake * released
        on_tip = on_tip - drawn_up
        pigment_out -= drawn_up
        # The tip takes paint up as it sweeps through it: a brush at rest takes none.
        swept = min(1.0, distance / float(radii.max()))
        taken_up = (contact.carry * swept) * on_paper * suspended
        suspended -= taken_up
        receiving = on_paper * (water > 0)
        if float(receiving.sum()) > 0:
            shed = released - drawn_up
            suspended += shed.reshape(-1, 1, 1) * (receiving / receiving.sum())
            on_tip = on_tip - shed
        # Paint the hairs swept onto a sealed cell cannot stay on the paper there: it stands on the rubber.
        self._shed_onto_mask(rows, columns)
        return used - float(soaked.sum()), pigment_out, on_tip + taken_up.sum(dim=(1, 2))

    def _shed_onto_mask(self, rows: slice, columns: slice) -> None:
        sealed = self.mask[rows, columns] >= MASK_SEALED
        water = self.water[rows, columns]
        suspended = self.suspended[:, rows, columns]
        self.mask_water[rows, columns] += water * sealed
        self.mask_pigment[:, rows, columns] += suspended * sealed
        water *= ~sealed
        suspended *= ~sealed

    def apply_mask(self, points: Tensor, radii: Tensor) -> None:
        """Lay masking fluid along a path. It forms its skin only on paper with no film standing on it: put
        into wet paint, it mixes with the water and seals nothing. Paper it seals keeps a crisp edge in the picture."""
        radii = radii.clamp(min=MASK_SMALLEST_RADIUS)
        rows, columns, coverage = self._coverage(points, radii, MASK_EDGE_SOFTNESS, irregular=True)
        dry = (self.water[rows, columns] <= self.parameters.wet_threshold).float()
        mask = torch.maximum(self.mask[rows, columns], coverage * dry)
        self.mask[rows, columns] = mask
        self.crisp[rows, columns] |= mask >= MASK_SEALED

    def apply_pen(
        self, points: Tensor, radii: Tensor, amounts: Tensor, covered: Tensor, reached: Tensor, inked: Tensor
    ) -> None:
        """Draw a short piece of a pen line, laying the amount of each pigment on every cell the line covers fully.

        A cell is covered as far as its centre lies within the line, with a ramp one cell wide centred on the line's
        true edge, and no line is taken as narrower than one cell: a finer one lays a cell's worth of ink along its path
        rather than fading. Covered holds how far this line has already inked each cell, so where its pieces overlap or
        it crosses itself it lays no more; reached holds the cells it has reached, and inked those it has inked on dry
        paper, which keep a crisp edge once the line ends (end_pen_line). On dry paper the ink goes onto the paper and keeps a crisp edge; where a film
        stands it goes into the water and spreads with it; on masking fluid it stays on the rubber. On paint that has
        dried it begins a new layer, as a brush does.
        """
        rows, columns, coverage = self._coverage(points, radii.clamp(min=0.5) + 0.5, 0.0)
        masked = self.mask[rows, columns]
        self._open_layer(rows, columns, coverage * (1.0 - masked) > LAYER_FOOTPRINT, reached)
        laid = (coverage - covered[rows, columns]).clamp(min=0)
        covered[rows, columns] = torch.maximum(covered[rows, columns], coverage)
        ink = amounts.reshape(-1, 1, 1) * laid
        self.mask_pigment[:, rows, columns] += ink * masked
        on_paper = ink * (1.0 - masked)
        wet = self.water[rows, columns] > self.parameters.wet_threshold
        self.suspended[:, rows, columns] += on_paper * wet
        self.deposited[:, rows, columns] += on_paper * ~wet
        # Ink on dry paper is dry as it lands, so paint laid over it later lies over it.
        dry_ink = ~wet & (laid > 0) & (masked < 1.0)
        self.dried_paint[rows, columns] |= dry_ink
        inked[rows, columns] |= dry_ink
        self._used.update((amounts > 0).nonzero().flatten().tolist())

    def end_pen_line(self, inked: Tensor) -> None:
        """Give the cells a pen line inked on dry paper their crisp edge. It is given once the line has ended, so that
        layers the line begins as it goes are worked out with the edges the picture had, and keep their colour."""
        self.crisp |= inked

    def remove_mask(self, points: Tensor | None = None, radii: Tensor | None = None) -> None:
        """Rub masking fluid away, all of it or along a path. Paint dried on the rubber comes away with it;
        paint still wet on it is smeared onto the paper as it is rubbed, and over paint that has dried there it begins
        a new layer."""
        if points is None or radii is None:
            rows, columns = slice(None), slice(None)
            removed = self.mask.clone()
        else:
            rows, columns, coverage = self._coverage(points, radii, 0.3)
            removed = self.mask[rows, columns] * coverage
        mask = self.mask[rows, columns]
        share = (removed / mask.clamp(min=1e-6)).clamp(0, 1) * (mask > 0)
        beads = self.mask_water[rows, columns]
        on_rubber = self.mask_pigment[:, rows, columns]
        wet = beads > 0
        smeared = (share > 0) & wet
        self._open_layer(rows, columns, smeared, torch.zeros_like(self.dried_paint))
        self.water[rows, columns] += beads * share
        self.suspended[:, rows, columns] += on_rubber * share * wet
        beads *= 1.0 - share
        on_rubber *= 1.0 - share
        mask -= removed
        mask.clamp_(min=0)

    def apply_fixative(self, points: Tensor | None = None, radii: Tensor | None = None) -> None:
        """Lay fixative, alum size or acrylic medium, over the whole sheet or along a path. It dries clear and
        cannot be removed. Paint settled on the paper under it, and paint that settles there later, can no longer
        be lifted, rolled or scrubbed; wet paint on it flows as on bare paper. It takes only on paper with no film
        standing on it, and not on masking fluid, with which it would come away."""
        if points is None or radii is None:
            rows, columns = slice(None), slice(None)
            coverage = torch.ones_like(self.fixative)
        else:
            rows, columns, coverage = self._coverage(points, radii, 0.3)
        bare = (self.water[rows, columns] <= self.parameters.wet_threshold) & (self.mask[rows, columns] < MASK_SEALED)
        # Written in place: in a batch the sheet's fixative is a view of the batch's own.
        self.fixative[rows, columns] = torch.maximum(self.fixative[rows, columns], coverage * bare)

    def blot(self, points: Tensor, radii: Tensor) -> None:
        """Press absorbent tissue onto the sheet."""
        rows, columns, coverage = self._coverage(points, radii, 0.3)
        self.water[rows, columns] *= 1.0 - 0.9 * coverage
        self.suspended[:, rows, columns] *= 1.0 - 0.9 * coverage
        self.saturation[rows, columns] *= 1.0 - 0.3 * coverage
        # Tissue takes up the beads standing on masking fluid too, and the wet paint in them.
        wet = self.mask_water[rows, columns] > 0
        self.mask_pigment[:, rows, columns] *= 1.0 - 0.9 * coverage * wet
        self.mask_water[rows, columns] *= 1.0 - 0.9 * coverage

    def draw_graphite(self, points: Tensor, radii: Tensor, darkness: Tensor) -> None:
        """Draw pencil along a path, at a darkness given for each point. Marks build tone where they overlap a mark
        drawn before. On paper with no paint the graphite lies on the paper, under any paint laid later, and can be
        erased; on paint that has dried it lies on that paint, under any paint laid later, and cannot be. It takes
        nowhere paint is still wet."""
        rows, columns, reached, fraction = self._sweep(points, radii, 1.0)
        coverage = (reached * _along(darkness, fraction)).amax(dim=0)
        on_paper = 1.0 - self.mask[rows, columns]  # pencil on masking fluid comes away with the rubber
        mark = coverage * (0.35 + 0.65 * (self.tooth[rows, columns] + (1.0 - self.peak))) * on_paper
        through = (1.0 - GRAPHITE_SHADE * mark).clamp(0.0, 1.0)  # share of the light the mark lets through
        painted = self._painted(rows, columns)
        graphite = self.graphite[rows, columns]
        lit = (1.0 - GRAPHITE_SHADE * graphite).clamp(0.0, 1.0)
        graphite.copy_(torch.where(painted, graphite, (1.0 - lit * through) / GRAPHITE_SHADE))
        on_paint = painted & self._dry_paper(rows, columns) & (mark > 0)
        if bool(on_paint.any()):
            self._lay_on_top(rows, columns, on_paint, torch.zeros_like(through)[None], through.sqrt()[None])

    def draw_dry(
        self,
        points: Tensor,
        radii: Tensor,
        pressures: Tensor,
        strength: Tensor,
        medium: dry_media.DryMedium,
        covered: Tensor,
    ) -> None:
        """Draw a short piece of a line with a dry stick: coloured pencil or pastel.

        Pressures, one per point, decide how deep into the grain the stick reaches; strength holds the stick's amount of
        each pigment. The stick takes only on paper with no film standing on it and no fuller than damp, and never on
        masking fluid. Each mark lies over the paint and the marks already there and under any paint laid later; no
        water moves it. Covered holds how far this line has already marked each cell, so where its pieces overlap or it
        crosses itself it lays no more.
        """
        radii = radii.clamp(min=0.5) + 0.5  # no line is drawn narrower than a cell, as with the pen
        rows, columns, reached, fraction = self._sweep(points, radii, 0.0)
        if reached.numel() == 0:  # the piece lies wholly off the sheet
            return
        touched = dry_media.touched_share(
            self.tooth[rows, columns], self.peak, _along(pressures, fraction), _along(radii, fraction)
        )
        coverage = (reached * touched).amax(dim=0)
        weight = coverage * (1.0 - self.mask[rows, columns]) * self._dry_paper(rows, columns)
        laid = (weight - covered[rows, columns]).clamp(min=0)
        covered[rows, columns] = torch.maximum(covered[rows, columns], weight)
        cells = laid > 1e-4
        if not bool(cells.any()):
            return
        mark = medium.layer(laid, strength, self.pigment_absorption, self.pigment_scattering)
        self._lay_on_top(rows, columns, cells, *mark)

    def erase_graphite(self, points: Tensor, radii: Tensor) -> None:
        """Rub pencil off the paper. Pencil under paint, or drawn on paint, is out of the eraser's reach."""
        rows, columns, coverage = self._coverage(points, radii, 0.5)
        self.graphite[rows, columns] *= 1.0 - coverage * ~self._painted(rows, columns)

    def _paint_in(self, rows: slice, columns: slice) -> Tensor:
        """Amount of paint kept as pigment in each cell within the rows and columns, in every layer."""
        return (
            self.suspended[:, rows, columns] + self.deposited[:, rows, columns] + self.buried[:, rows, columns]
        ).sum(0)

    def _painted(self, rows: slice, columns: slice) -> Tensor:
        """Cells within the rows and columns that hold paint, or whose colour paint or marks pressed beneath it has
        visibly changed."""
        pressed = self.substrate_change[:, rows, columns].abs().amax(0) > LAYER_MERGE_ERROR
        return (self._paint_in(rows, columns) > LAYER_PIGMENT) | pressed


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
        tooth, cockle, sizing = (
            torch.stack([getattr(sheet, name) for sheet in sheets]) for name in ("tooth", "cockle", "sizing")
        )
        paper = Paper(tooth, cockle, sizing)
        self._stack = Sheet(paper, first.pigments, first.parameters)
        self._stack._painted_sheets = self.sheets
        for index, sheet in enumerate(sheets):
            for name in ("water", "saturation", "mask", "mask_water", "fixative", "dried_paint"):
                held = getattr(self._stack, name)[index]
                held.copy_(getattr(sheet, name))
                setattr(sheet, name, held)
            for name in ("suspended", "deposited", "buried", "mask_pigment"):
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


@dataclass(frozen=True)
class Support:
    """What a painting is painted on, chosen once when it is begun and regenerated from the seed on every command.

    SUPPORTS names the presets. An option that changes one aspect of the sheet, such as its colour, replaces
    that field of the preset it is given with, so every option describes the same sheet and none stands apart.
    """

    grain: Grain = COLD_PRESS_GRAIN
    color: tuple[float, float, float] = PAPER_COLOR
    relief_shading: float = 0.05  # how strongly the relief of the grain shades the bare sheet
    parameters: SimulationParameters = SimulationParameters()


SUPPORTS = {
    "cold_press": Support(),
    # Pressed smooth: a fine grain a fifth as deep, and a surface that keeps the film on top longer, lifts more
    # easily and dries its edges harder.
    "hot_press": Support(
        grain=Grain(octaves=((1, 0.5), (2, 0.5)), depth=0.2),
        parameters=SimulationParameters(
            absorption_rate=0.01,
            capacity_maximum=0.42,
            absorbed_pigment=0.2,
            sizing_unevenness=0.6,
            wicking_unevenness=0.8,
            resolubility=0.6,
        ),
    ),
    # Unpressed: a coarse grain of broad tops and deep pits, which hold water and coarse granulation. The bare
    # sheet is shaded only by the grain finer than about 5 pixels, so its relief is shaded more strongly.
    "rough": Support(
        grain=Grain(octaves=((3, 0.2), (6, 0.35), (12, 0.45)), plateaus=0.6),
        relief_shading=0.45,
        parameters=SimulationParameters(tooth_pressure=0.15, granulation_strength=0.55, sedimentation=30.0),
    ),
}


def support_sheet(
    support: Support,
    height: int,
    width: int,
    seed: int,
    device: torch.device,
    pigments: Sequence[Pigment],
    printed: Tensor | None = None,
) -> Sheet:
    """Return a sheet of the support; the same seed always gives the same sheet.

    A printed ground, RGB in [0, 1] with shape (3, H, W), multiplies the colour of the support as ink does.
    """
    ground = torch.tensor(support.color).reshape(3, 1, 1)
    if printed is not None:
        ground = ground * printed
    paper = replace(
        generate_paper(height, width, seed, device, support.grain),
        ground=ground.to(device),
        relief_shading=support.relief_shading,
    )
    return Sheet(paper, pigments, support.parameters)

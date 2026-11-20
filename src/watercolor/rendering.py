"""Turning a sheet into pictures: the painting itself and the views used to inspect it."""

import math
from itertools import pairwise

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw
from torch import Tensor

from .paper import PAPER_COLOR  # noqa: F401 - kept importable from here, where it was defined before supports
from .simulation import SHINE_DEPTH, Sheet

# Masking fluid is tinted so that it can be seen on white paper: a pale yellow skin that lets what is under it show.
MASK_TINT = (0.98, 0.94, 0.72)
VIEWS = ("color", "value", "wetness")
MINIMUM_VIEW_SIZE = 768
# Optical strength of one unit of pigment: a brush concentration of 1.0 is a mid-strength wash.
TINTING_STRENGTH = 0.4
GRID_MARGIN = 30
# Share of a cell's paint seen at the cell itself and at each neighbour along one axis.
EDGE_BLEND = (0.12, 0.76, 0.12)
# Colour of damp paper that can take up no more water, in the wetness view.
PAPER_FULL = (0.62, 0.85, 0.70)
# Colours of the wetness view at landmark depths of the film of water on the surface.
FILM_SCALE = (
    (0.02, (0.80, 0.93, 1.00)),
    (0.15, (0.50, 0.76, 1.00)),
    (0.40, (0.22, 0.48, 0.96)),
    (0.80, (0.08, 0.20, 0.78)),
    (1.50, (0.40, 0.08, 0.62)),
    (2.50, (0.72, 0.05, 0.38)),
)
LEGEND_HEIGHT = 34  # pixels, for the scale beneath the wetness view

# The sheet is pictured by a camera looking straight down, lit by a small lamp beside it.
LAMP_ANGLE = 10.0  # degrees between the lamp and the camera as seen from the sheet; the lamp stands to the upper left
WATER_REFRACTIVE_INDEX = 1.333
SURFACE_ROUGHNESS = 0.022  # spread of the slopes of the water's surface within one cell
GRAIN_HEIGHT = 0.5  # height of the grain of the paper from valley to peak, in cells
COCKLE_HEIGHT = 1.2  # height of the broad buckling of the sheet, in cells
# Height, in cells, of one unit of film: water level with the peaks of the grain averages half the grain's height.
FILM_HEIGHT = GRAIN_HEIGHT / (2.0 * SHINE_DEPTH)
GRAIN_FOLLOWED = 0.6  # share of the grain's slope that the surface of the thinnest film takes on
SURFACE_BLEND = (0.25, 0.5, 0.25)  # surface tension evens the film's surface between neighbouring cells
# Water can gather the lamp's light on the paper to at most this many times its strength, or spread it to that
# share of it. Beyond that the rays cross, and following each ray singly no longer says how bright the paper is.
GREATEST_GATHERING = 2.0


def render(sheet: Sheet) -> Tensor:
    """Return the sheet as the camera sees it, as RGB in [0, 1] with shape (3, H, W)."""
    return (_paint(sheet) * transmitted(sheet) + sheen(sheet)).clamp(0, 1)


def transmitted(sheet: Sheet) -> Tensor:
    """Return how strongly the lamp lights the paper through the water, against a dry sheet, with shape (H, W).

    Water that stands proud of the sheet is a lens. Its sloping surface bends the lamp's light towards
    the deeper water, so the paper under the shoulder of a pool is lit more than a dry sheet and the
    paper under its very edge less. The lamp stands to one side, so its light also crosses the water
    at a slant: the rim nearest the lamp is the darker and the far rim the brighter. Under level water,
    however deep, the paper is lit as if it were dry.

    Each ray is followed from the surface to the paper, where it lands a little aside from the point
    below its entry; the paper is brighter where the landings crowd together and darker where they
    part.
    """
    depth = _film_height(sheet)
    down, across = torch.gradient(depth + COCKLE_HEIGHT * sheet.cockle)
    # The lamp's light travels to the lower right, and less steeply so once it is inside the water.
    refraction = math.asin(math.sin(math.radians(LAMP_ANGLE)) / WATER_REFRACTIVE_INDEX)
    slant = math.tan(refraction) / math.sqrt(2.0)
    # A sloping surface turns the light towards its uphill side by this share of the slope.
    bending = 1.0 - 1.0 / WATER_REFRACTIVE_INDEX
    landing_down, landing_across = depth * (slant + bending * down), depth * (slant + bending * across)
    down_by_down, down_by_across = torch.gradient(landing_down)
    across_by_down, across_by_across = torch.gradient(landing_across)
    # The area of paper that takes the light entering one cell of the surface.
    spread = (1.0 + down_by_down) * (1.0 + across_by_across) - down_by_across * across_by_down
    return (1.0 / spread.clamp(min=1.0 / GREATEST_GATHERING)).clamp(min=1.0 / GREATEST_GATHERING)


def sheen(sheet: Sheet) -> Tensor:
    """Return the light of the lamp that water on the sheet mirrors into the camera, with shape (H, W).

    It is measured against a white surface under the same lamp, like the colours of the paint.
    Level water mirrors the ceiling, not the lamp, so the middle of a pool keeps its colour.
    The lamp shows where the surface is tilted towards it: along the edge of a pool, where the
    sheet buckles, and in points where a thin film follows the grain. Paper with no film on it
    mirrors nothing.

    Each cell is a rough mirror in the manner of Beckmann and of Cook and Torrance: its surface
    has slopes spread about their mean, and it is as bright as the share of them that turn the
    lamp into the camera.
    """
    water, tooth = sheet.water, sheet.tooth
    # Water lies level in the valleys of the grain and reaches higher up it as the film deepens. Both are
    # measured in heights of the grain, so a thin film covers a shallow grain whole.
    depth = sheet.grain_depth
    level = (water / (SHINE_DEPTH * depth)).sqrt()
    covered = ((level - (tooth - sheet.valley) / depth) / 0.1 + 0.5).clamp(0, 1) * (water > 0)
    # The surface slopes with the shape of the pool and the buckling of the sheet and, while the
    # film is thin, with the grain beneath it.
    down, across = torch.gradient(_film_height(sheet) + COCKLE_HEIGHT * sheet.cockle)
    grain_down, grain_across = torch.gradient(GRAIN_HEIGHT * tooth)
    following = GRAIN_FOLLOWED * torch.exp(-water / SHINE_DEPTH)
    down, across = down + following * grain_down, across + following * grain_across
    # The slope that turns the lamp into the camera rises away from the lamp, to the lower right.
    mirroring = math.tan(math.radians(LAMP_ANGLE) / 2.0) / math.sqrt(2.0)
    departure = (across - mirroring) ** 2 + (down - mirroring) ** 2
    return _lamp_strength() * torch.exp(-departure / (2.0 * SURFACE_ROUGHNESS**2)) * covered


def _film_height(sheet: Sheet) -> Tensor:
    """Height of the water's surface above the paper beneath it, in cells, with shape (H, W)."""
    return FILM_HEIGHT * _blend(sheet.water[None], SURFACE_BLEND)[0]


def _lamp_strength() -> float:
    """Brightness of the lamp in water that mirrors it squarely, against a white surface under the same lamp."""
    lamp = math.radians(LAMP_ANGLE)
    incidence = lamp / 2.0
    refraction = math.asin(math.sin(incidence) / WATER_REFRACTIVE_INDEX)
    # Fresnel's share of unpolarised light mirrored at this incidence.
    mirrored = 0.5 * (
        (math.sin(incidence - refraction) / math.sin(incidence + refraction)) ** 2
        + (math.tan(incidence - refraction) / math.tan(incidence + refraction)) ** 2
    )
    return mirrored / (8.0 * SURFACE_ROUGHNESS**2 * math.cos(lamp))


def _blend(layers: Tensor, shares: tuple[float, float, float]) -> Tensor:
    """Share each cell of every layer, shape (N, H, W), with its neighbours along both axes."""
    weights = torch.tensor(shares, device=layers.device)
    layers = F.conv2d(F.pad(layers[:, None], (0, 0, 1, 1), mode="replicate"), weights.reshape(1, 1, 3, 1))
    return F.conv2d(F.pad(layers, (1, 1, 0, 0), mode="replicate"), weights.reshape(1, 1, 1, 3))[:, 0]


def _paint(sheet: Sheet) -> Tensor:
    """Return the paint and paper as an even light shows them, as RGB with shape (3, H, W).

    What the water does to the lamp's light, mirroring some and gathering the rest, is left out.
    """
    device = sheet.tooth.device
    absorption = torch.tensor([p.absorption for p in sheet.pigments], device=device)
    scattering = torch.tensor([p.scattering for p in sheet.pigments], device=device)
    relief = sheet.tooth - F.avg_pool2d(sheet.tooth[None, None], 5, stride=1, padding=2)[0, 0]
    paper = sheet.ground * (1.0 + sheet.relief_shading * relief)
    color = _over(sheet.deposited + sheet.suspended, absorption, scattering, paper)

    # Masking fluid is a translucent tinted skin over whatever is under it, and paint that landed on it
    # lies on top of the skin until the fluid is rubbed away.
    if bool((sheet.mask > 0).any()):
        mask = sheet.mask.clamp(0, 1)[None]
        skin = color * torch.tensor(MASK_TINT, device=device).reshape(3, 1, 1)
        on_skin = _over(sheet.mask_pigment, absorption, scattering, skin)
        color = color * (1.0 - mask) + on_skin * mask

    dampness = (sheet.saturation / sheet.capacity).clamp(0, 1)
    color = color * (1.0 - 0.05 * dampness - 0.04 * sheet.water.clamp(0, 1))
    color = color * (1.0 - 0.6 * sheet.graphite)
    return color.clamp(0, 1)


def _over(pigment: Tensor, absorption: Tensor, scattering: Tensor, background: Tensor) -> Tensor:
    """Colour of a layer of paint, shape (P, H, W), over a background, by Kubelka and Munk."""
    # Paint does not stop dead at the boundary of a cell. Each cell shares a little with its
    # neighbours, which turns the stepped outline of the grid into the smooth edge of a wash.
    amount = _blend(TINTING_STRENGTH * pigment, EDGE_BLEND)
    k = torch.einsum("phw,pc->chw", amount, absorption) + 1e-6
    s = torch.einsum("phw,pc->chw", amount, scattering) + 1e-4
    a = 1.0 + k / s
    b = (a * a - 1.0).sqrt()
    thickness = (b * s).clamp(max=20.0)
    denominator = a * thickness.sinh() + b * thickness.cosh()
    reflectance = thickness.sinh() / denominator
    transmittance = b / denominator
    return reflectance + transmittance**2 * background / (1.0 - reflectance * background)


def render_view(sheet: Sheet, view: str) -> Tensor:
    if view == "color":
        return render(sheet)
    # The other views measure the paint, so they leave out what the water does to the lamp's light.
    color = _paint(sheet)
    weights = torch.tensor([0.2126, 0.7152, 0.0722], device=color.device).reshape(3, 1, 1)
    value = (color * weights).sum(0, keepdim=True).expand(3, -1, -1)
    if view == "value":
        return value
    # Wetness, on two continuous scales: the paper turns from grey to green as it fills with
    # water, and the film standing on it runs from pale blue through deep blue to violet.
    fullness = (sheet.saturation / sheet.capacity).clamp(0, 1)
    base = 0.5 + 0.5 * value
    base = base + 0.6 * fullness * (_colors(PAPER_FULL, color.device) - base)
    film = _ramp(sheet.water, FILM_SCALE)
    cover = (sheet.water / FILM_SCALE[0][0]).clamp(0, 1) * 0.92
    return base + cover * (film - base)


def _colors(color: tuple[float, float, float], device: torch.device) -> Tensor:
    return torch.tensor(color, device=device).reshape(3, 1, 1)


def _ramp(depth: Tensor, scale: tuple[tuple[float, tuple[float, float, float]], ...]) -> Tensor:
    """Colour of each cell on a scale of landmark depths, blended between neighbouring landmarks."""
    picture = _colors(scale[0][1], depth.device).expand(3, *depth.shape).clone()
    for (lower, start), (upper, end) in pairwise(scale):
        share = ((depth - lower) / (upper - lower)).clamp(0, 1)
        picture = picture + share * (_colors(end, depth.device) - _colors(start, depth.device))
    return picture


def _wetness_legend(width: int) -> Image.Image:
    """A strip that reads the wetness view: the colour of the film at each depth, and of the paper as it fills."""
    legend = Image.new("RGB", (width, LEGEND_HEIGHT), "white")
    draw = ImageDraw.Draw(legend)
    deepest = FILM_SCALE[-1][0]
    span = int(width * 0.68)
    depths = torch.linspace(0.0, deepest, span).reshape(1, -1)
    strip = to_image(_ramp(depths, FILM_SCALE).expand(3, 14, span))
    legend.paste(strip, (40, 4))
    draw.text((4, 5), "film", fill="black")
    for depth, _ in FILM_SCALE:
        x = 40 + int(span * depth / deepest)
        draw.line((x, 4, x, 22), fill="black")
        draw.text((x + 2, 20), f"{depth:g}", fill="black")
    start = 40 + span + 60
    grey, full = torch.tensor(0.75), _colors(PAPER_FULL, depths.device)
    shares = torch.linspace(0.0, 1.0, width - start - 6).reshape(1, 1, -1)
    paper = grey + 0.6 * shares * (full - grey)
    legend.paste(to_image(paper.expand(3, 14, -1)), (start, 4))
    draw.text((start - 38, 5), "paper", fill="black")
    draw.text((start, 20), "dry", fill="black")
    draw.text((width - 28, 20), "full", fill="black")
    return legend


def to_image(picture: Tensor) -> Image.Image:
    array = (picture.permute(1, 2, 0) * 255.0).round().byte().cpu().numpy()
    return Image.fromarray(np.ascontiguousarray(array), "RGB")


def _grid_spacing(extent: int) -> int:
    for spacing in (8, 16, 32, 64, 128, 256):
        if extent / spacing <= 9:
            return spacing
    return 256


def inspection_image(
    sheet: Sheet,
    view: str = "color",
    region: tuple[int, int, int, int] | None = None,
    grid: bool = False,
) -> Image.Image:
    """Return a view of the sheet or of one region, enlarged, optionally with a pixel grid."""
    x0, y0, x1, y1 = region or (0, 0, sheet.width, sheet.height)
    picture = to_image(render_view(sheet, view)).crop((x0, y0, x1, y1))
    scale = max(1, round(MINIMUM_VIEW_SIZE / max(x1 - x0, y1 - y0)))
    if scale > 1:
        picture = picture.resize((picture.width * scale, picture.height * scale), Image.Resampling.BICUBIC)
    if not grid:
        return _with_legend(picture, view)
    framed = Image.new("RGB", (picture.width + GRID_MARGIN, picture.height + GRID_MARGIN), "white")
    framed.paste(picture, (GRID_MARGIN, GRID_MARGIN))
    draw = ImageDraw.Draw(framed, "RGBA")
    spacing = _grid_spacing(max(x1 - x0, y1 - y0))
    for x in range(-(-x0 // spacing) * spacing, x1 + 1, spacing):
        position = GRID_MARGIN + (x - x0) * scale
        draw.line((position, GRID_MARGIN, position, framed.height), fill=(0, 0, 0, 70))
        draw.text((position - 10, 8), str(x), fill=(0, 0, 0, 255))
    for y in range(-(-y0 // spacing) * spacing, y1 + 1, spacing):
        position = GRID_MARGIN + (y - y0) * scale
        draw.line((GRID_MARGIN, position, framed.width, position), fill=(0, 0, 0, 70))
        draw.text((2, position - 5), str(y), fill=(0, 0, 0, 255))
    return _with_legend(framed, view)


def _with_legend(picture: Image.Image, view: str) -> Image.Image:
    """Put the scale of the wetness view beneath it; the other views need none."""
    if view != "wetness":
        return picture
    framed = Image.new("RGB", (picture.width, picture.height + LEGEND_HEIGHT), "white")
    framed.paste(picture, (0, 0))
    framed.paste(_wetness_legend(picture.width), (0, picture.height))
    return framed

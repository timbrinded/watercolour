"""Turning a sheet into pictures: the painting itself and the views used to inspect it."""

from itertools import pairwise

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw
from torch import Tensor

from .simulation import Sheet

PAPER_COLOR = (0.97, 0.96, 0.93)
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


def render(sheet: Sheet) -> Tensor:
    """Return the sheet as it appears, as RGB in [0, 1] with shape (3, H, W)."""
    device = sheet.tooth.device
    amount = TINTING_STRENGTH * (sheet.deposited + sheet.suspended)
    # Paint does not stop dead at the boundary of a cell. Each cell shares a little with its
    # neighbours, which turns the stepped outline of the grid into the smooth edge of a wash.
    blend = torch.tensor(EDGE_BLEND, device=device)
    amount = F.conv2d(F.pad(amount[:, None], (0, 0, 1, 1), mode="replicate"), blend.reshape(1, 1, 3, 1))
    amount = F.conv2d(F.pad(amount, (1, 1, 0, 0), mode="replicate"), blend.reshape(1, 1, 1, 3))[:, 0]
    absorption = torch.tensor([p.absorption for p in sheet.pigments], device=device)
    scattering = torch.tensor([p.scattering for p in sheet.pigments], device=device)
    k = torch.einsum("phw,pc->chw", amount, absorption) + 1e-6
    s = torch.einsum("phw,pc->chw", amount, scattering) + 1e-4

    # Kubelka-Munk reflectance and transmittance of the paint layer, over the paper.
    a = 1.0 + k / s
    b = (a * a - 1.0).sqrt()
    thickness = (b * s).clamp(max=20.0)
    denominator = a * thickness.sinh() + b * thickness.cosh()
    reflectance = thickness.sinh() / denominator
    transmittance = b / denominator

    relief = sheet.tooth - F.avg_pool2d(sheet.tooth[None, None], 5, stride=1, padding=2)[0, 0]
    paper = torch.tensor(PAPER_COLOR, device=device).reshape(3, 1, 1) * (1.0 + 0.05 * relief)
    color = reflectance + transmittance**2 * paper / (1.0 - reflectance * paper)

    dampness = (sheet.saturation / sheet.capacity).clamp(0, 1)
    color = color * (1.0 - 0.05 * dampness - 0.04 * sheet.water.clamp(0, 1))
    color = color * (1.0 - 0.6 * sheet.graphite)
    return color.clamp(0, 1)


def render_view(sheet: Sheet, view: str) -> Tensor:
    color = render(sheet)
    if view == "color":
        return color
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

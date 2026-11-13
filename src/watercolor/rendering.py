"""Turning a sheet into pictures: the painting itself and the views used to inspect it."""

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
    # Wetness: surface water in strong blue, damp paper in pale blue, dry paper grey.
    p = sheet.parameters
    base = 0.5 + 0.5 * value
    damp = (sheet.saturation > p.damp_threshold * sheet.capacity).float() * 0.45
    surface = (sheet.water / 0.8).clamp(0, 1) * 0.6 + (sheet.water > p.wet_threshold) * 0.3
    pale = torch.tensor([0.62, 0.82, 1.0], device=color.device).reshape(3, 1, 1)
    strong = torch.tensor([0.10, 0.35, 0.95], device=color.device).reshape(3, 1, 1)
    base = base + damp * (pale - base)
    return base + surface * (strong - base)


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
        return picture
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
    return framed

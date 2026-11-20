"""How paint on the sheet reflects an even light, by Kubelka and Munk.

The picture uses it to show the paint, and the sheet uses it to keep the colour of paint that dries under a new layer.
"""

import torch
import torch.nn.functional as F
from torch import Tensor

# Optical strength of one unit of pigment: a brush concentration of 1.0 is a mid-strength wash.
TINTING_STRENGTH = 0.4
# Share of a cell's paint seen at the cell itself and at each neighbour along one axis.
EDGE_BLEND = (0.12, 0.76, 0.12)
# Share of the light that a full pencil mark takes from the paper it lies on.
GRAPHITE_SHADE = 0.6


def blend(layers: Tensor, shares: tuple[float, float, float]) -> Tensor:
    """Share each cell of every layer, shape (N, H, W), with its neighbours along both axes."""
    weights = torch.tensor(shares, device=layers.device)
    layers = F.conv2d(F.pad(layers[:, None], (0, 0, 1, 1), mode="replicate"), weights.reshape(1, 1, 3, 1))
    return F.conv2d(F.pad(layers, (1, 1, 0, 0), mode="replicate"), weights.reshape(1, 1, 1, 3))[:, 0]


def edge_blend(layers: Tensor, crisp: Tensor) -> Tensor:
    """Share each cell of every layer, shape (N, H, W), with its neighbours by EDGE_BLEND, except across a face
    between a crisp cell and one that is not: a crisp mark keeps its paint and takes none from beside it.

    Along the rows and then the columns, each open face passes the neighbour's share of the difference between its two
    cells. That is the separable blend itself, whose replicated border is a face with nothing passing across it.
    """
    if not bool(crisp.any()):
        return blend(layers, EDGE_BLEND)
    share = EDGE_BLEND[0]
    passed = share * (layers[..., :-1, :] - layers[..., 1:, :]) * (crisp[:-1, :] == crisp[1:, :])
    layers = layers - F.pad(passed, (0, 0, 0, 1)) + F.pad(passed, (0, 0, 1, 0))
    passed = share * (layers[..., :, :-1] - layers[..., :, 1:]) * (crisp[:, :-1] == crisp[:, 1:])
    return layers - F.pad(passed, (0, 1)) + F.pad(passed, (1, 0))


def over(pigment: Tensor, absorption: Tensor, scattering: Tensor, background: Tensor, crisp: Tensor) -> Tensor:
    """Colour of a layer of paint, shape (P, H, W), over a background, by Kubelka and Munk."""
    # Paint does not stop dead at the boundary of a cell. Each cell shares a little with its
    # neighbours, which turns the stepped outline of the grid into the smooth edge of a wash.
    # The edge of a crisp mark, a pen line or paper kept white by masking fluid, is not shared.
    amount = edge_blend(TINTING_STRENGTH * pigment, crisp)
    k = torch.einsum("phw,pc->chw", amount, absorption) + 1e-6
    s = torch.einsum("phw,pc->chw", amount, scattering) + 1e-4
    a = 1.0 + k / s
    b = (a * a - 1.0).sqrt()
    thickness = (b * s).clamp(max=20.0)
    denominator = a * thickness.sinh() + b * thickness.cosh()
    reflectance = thickness.sinh() / denominator
    transmittance = b / denominator
    return reflectance + transmittance**2 * background / (1.0 - reflectance * background)

"""The paint box: the paints a painting has unless it names others, and the colours the named paints are for."""

import json
import math
import sys
from pathlib import Path

import pytest
import torch
from torch import Tensor

from watercolor.cli import main
from watercolor.paper import Paper
from watercolor.pigments import PIGMENTS
from watercolor.rendering import render
from watercolor.simulation import Sheet

# The paints of engine 0.8.0 and 0.9.0, in their order. A painting begun without --palette that had any other paints,
# or these in another order, would not replay as it was painted.
STANDARD_PAINTS = [
    "french_ultramarine",
    "cerulean_blue",
    "phthalo_green",
    "hookers_green",
    "hansa_yellow",
    "quinacridone_rose",
    "cadmium_red",
    "burnt_umber",
    "cobalt_blue",
    "burnt_sienna",
    "yellow_ochre",
    "opaque_white",
    "ivory_black",
]


def test_a_painting_begun_without_a_palette_has_the_standard_paints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "painting"
    monkeypatch.setattr(sys, "argv", ["watercolor", "new", str(directory), "--prompt", "x", "--size", "128"])
    main()
    assert json.loads((directory / "session.json").read_text())["palette"] == STANDARD_PAINTS


# sRGB to CIE XYZ (D65), and the two steps from linear sRGB to Oklab (Ottosson 2020).
TO_XYZ = torch.tensor([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
WHITE_XYZ = torch.tensor([0.95047, 1.0, 1.08883])
TO_LMS = torch.tensor([[0.4122, 0.5363, 0.0514], [0.2119, 0.6807, 0.1074], [0.0883, 0.2817, 0.6300]])
TO_OKLAB = torch.tensor([[0.2105, 0.7936, -0.0041], [1.9780, -2.4286, 0.4506], [0.0259, 0.7828, -0.8087]])


def linear_light(rgb: Tensor) -> Tensor:
    return torch.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def oklab_chroma_and_hue(rgb: Tensor) -> tuple[float, float]:
    _, a, b = TO_OKLAB @ (TO_LMS @ linear_light(rgb)).pow(1 / 3)
    return math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def cielab_lightness_and_chroma(rgb: Tensor) -> tuple[float, float]:
    ratio = TO_XYZ @ linear_light(rgb) / WHITE_XYZ
    f = torch.where(ratio > (6 / 29) ** 3, ratio.pow(1 / 3), ratio / (3 * (6 / 29) ** 2) + 4 / 29)
    return float(116 * f[1] - 16), math.hypot(500 * (f[0] - f[1]), 200 * (f[1] - f[2]))


def dried_colour(mix: dict[str, float]) -> Tensor:
    """Colour of the mix lying evenly on dry paper with no grain, as sRGB."""
    tooth = torch.full((16, 16), 0.5)
    sheet = Sheet(Paper(tooth, torch.zeros_like(tooth), torch.full_like(tooth, 0.5)), [PIGMENTS[name] for name in mix])
    for index, amount in enumerate(mix.values()):
        sheet.deposited[index] = amount
    return render(sheet)[:, 4:-4, 4:-4].mean((1, 2))  # the border is lit as though the grain fell away beyond it


@pytest.mark.parametrize(
    ("mix", "hues", "least_chroma"),
    [
        ({"phthalo_blue": 3.0}, (250, 270), 0.20),  # measured 0.230 at hue 264
        ({"phthalo_turquoise": 1.0}, (165, 200), 0.14),  # 0.157 at 174
        ({"dioxazine_violet": 1.0}, (295, 325), 0.20),  # 0.247 at 311
        ({"viridian": 1.0}, (165, 195), 0.09),  # 0.105 at 180
    ],
)
def test_a_staining_or_clear_paint_reaches_the_hue_and_chroma_it_is_for(
    mix: dict[str, float], hues: tuple[float, float], least_chroma: float
) -> None:
    """By Oklab chroma: turquoise and a smooth staining blue and violet, which no mix of the standard paints reaches
    (0.08, 0.15 and 0.14 at best), and viridian's clear cool green. At turquoise's hue no colour on a display that is
    no lighter than the paper passes about 0.16."""
    chroma, hue = oklab_chroma_and_hue(dried_colour(mix))
    assert hues[0] <= hue <= hues[1]
    assert chroma >= least_chroma


@pytest.mark.parametrize(
    ("mix", "lightness", "least_chroma"),
    [
        ({"fluorescent_pink": 1.0}, (50, 62), 80),  # measured L55.3 C84.8
        ({"fluorescent_yellow": 1.0}, (91, 100), 85),  # L93.4 C90.7
        ({"fluorescent_pink": 0.5, "fluorescent_yellow": 1.5}, (52, 64), 85),  # orange, L57.4 C86.9
        ({"fluorescent_yellow": 2.0, "phthalo_turquoise": 0.75}, (80, 100), 108),  # lime, L82.1 C110.5
    ],
)
def test_the_fluorescent_paints_reach_neon_chroma_alone_and_mixed(
    mix: dict[str, float], lightness: tuple[float, float], least_chroma: float
) -> None:
    """Opera pink about L56 C85, acid lemon about L95 C90, orange-red about L61 C86 and lime about L88 C115, in
    CIELAB, corrected for what a colour no lighter than the paper (L96.5) can reach: lemon at C90 tops out near L94,
    and the lime corner near L84.6. The standard paints reach C61 in quinacridone rose and C47 at L90 in hansa yellow.
    """
    found_lightness, chroma = cielab_lightness_and_chroma(dried_colour(mix))
    assert lightness[0] <= found_lightness <= lightness[1]
    assert chroma >= least_chroma

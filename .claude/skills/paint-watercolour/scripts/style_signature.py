"""Measure the style signature of watercolour images: value key, reserved paper, temperature, edge character.

Usage: style_signature.py [--white rig|auto|R,G,B] painting.png [name=path ...]

Each image is scaled to 768 pixels on its long side and divided by the colour of its paper. --white sets that colour:
  rig    the harness's bare paper. The default for a picture of a painting session (a look, or the finished
         painting.png), which may have little or no bare paper left.
  auto   the mean colour of the image's lightest 1%. The default for any other image, such as a photograph of a
         painting. It is wrong for a painting on a toned ground or with almost no paper left: its lightest 1% is
         paint, and every measure is read lighter than it is.
  R,G,B  the paper's colour from 0 to 255, for a scan or photograph whose paper is known.
The columns: p05 to p75 (value percentiles), paper% (near-white and unpainted), dark<0.2% (deep darks),
warm/chromatic% (warm share of the coloured pixels), hard_edge% (pixels on a crisp edge), edge_hardness_p75, and
regions/1e5px (separate shapes of one value band, a measure of a mosaic of puddles), then the white used. The
targets for a style are in its style file.
"""

import argparse
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from measured_layers import PAPER
from PIL import Image

LONG_SIDE = 768


def is_rig_painting(path: Path) -> bool:
    """A picture of a painting session: the finished painting.png in the session's directory, or a look in its looks/."""
    folder = path.resolve().parent
    if folder.name == "looks":
        folder = folder.parent
    return (folder / "session.json").is_file()


def paper_colour(rgb: np.ndarray, white: str) -> np.ndarray:
    """The colour of the image's paper, from 0 to 1, as --white names it."""
    if white == "rig":
        return PAPER / 255.0
    if white == "auto":
        luminance = rgb @ np.array([0.2126, 0.7152, 0.0722])
        return rgb[luminance >= np.percentile(luminance, 99.0)].mean(0)
    return np.array([float(part) for part in white.split(",")]) / 255.0


def load(path: str, white: str) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    scale = LONG_SIDE / max(image.size)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    rgb = np.asarray(image).astype(np.float64) / 255.0
    return np.clip(rgb / paper_colour(rgb, white), 0.0, 1.0)


def gaussian(array: np.ndarray, sigma: float) -> torch.Tensor:
    radius = int(3 * sigma) + 1
    x = torch.arange(-radius, radius + 1, dtype=torch.float64)
    kernel = torch.exp(-(x**2) / (2 * sigma**2))
    kernel /= kernel.sum()
    tensor = torch.from_numpy(array)[None, None]
    tensor = F.conv2d(F.pad(tensor, (radius, radius, 0, 0), mode="replicate"), kernel.view(1, 1, 1, -1))
    tensor = F.conv2d(F.pad(tensor, (0, 0, radius, radius), mode="replicate"), kernel.view(1, 1, -1, 1))
    return tensor[0, 0]


def gradient(array: torch.Tensor) -> torch.Tensor:
    gy, gx = torch.gradient(array)
    return torch.sqrt(gx**2 + gy**2)


def region_count(value: np.ndarray, levels: int = 6, minimum_area: int = 40) -> int:
    """Connected regions of one quantised value band, a proxy for a mosaic of separate hard-edged shapes."""
    smoothed = gaussian(value, 1.5).numpy()
    bands = np.clip((smoothed * levels).astype(int), 0, levels - 1)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    total = 0
    height, width = value.shape
    for band in range(levels):
        mask = torch.from_numpy(bands == band).to(device)
        if not mask.any():
            continue
        big = height * width + 1
        labels = torch.where(mask, torch.arange(height * width, device=device).view(height, width), big).double()
        while True:
            pooled = -F.max_pool2d(-labels[None, None], 3, 1, 1)[0, 0]
            updated = torch.where(mask, torch.minimum(labels, pooled), labels)
            if torch.equal(updated, labels):
                break
            labels = updated
        _, counts = torch.unique(labels[mask], return_counts=True)
        total += int((counts >= minimum_area).sum())
    return total


def measure(path: str, white: str) -> dict[str, float]:
    rgb = load(path, white)
    value = rgb @ np.array([0.2126, 0.7152, 0.0722])
    chroma = rgb.max(2) - rgb.min(2)
    chromatic = chroma > 0.08
    warm = chromatic & (rgb[..., 0] > rgb[..., 2])
    fine = gradient(gaussian(value, 1.5))
    coarse = gradient(gaussian(value, 6.0))
    transition = coarse > 0.012
    hardness = (fine[transition] / coarse[transition]).numpy()
    area = value.size / 1e5
    return {
        "p05": np.percentile(value, 5),
        "p25": np.percentile(value, 25),
        "p50": np.percentile(value, 50),
        "p75": np.percentile(value, 75),
        "paper%": 100 * ((value > 0.88) & (chroma < 0.07)).mean(),
        "dark<0.2%": 100 * (value < 0.20).mean(),
        "chromatic%": 100 * chromatic.mean(),
        "warm/chromatic%": 100 * warm.sum() / max(chromatic.sum(), 1),
        "hard_edge%": 100 * (fine > 0.06).numpy().mean(),
        "edge_hardness_p75": float(np.percentile(hardness, 75)) if hardness.size else 0.0,
        "regions/1e5px": region_count(value) / area,
    }


def white_argument(text: str) -> str:
    if text in ("rig", "auto"):
        return text
    parts = text.split(",")
    try:
        valid = len(parts) == 3 and all(0.0 < float(part) <= 255.0 for part in parts)
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError("--white must be rig, auto, or R,G,B with each from 0 to 255")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("images", nargs="+", metavar="[name=]path")
    parser.add_argument(
        "--white",
        type=white_argument,
        help="rig, auto or R,G,B (default: rig for a picture of a painting session, auto otherwise)",
    )
    arguments = parser.parse_args()
    results, whites = {}, {}
    for argument in arguments.images:
        name, path = argument.split("=", 1) if "=" in argument else (Path(argument).parent.name or argument, argument)
        whites[name] = arguments.white or ("rig" if is_rig_painting(Path(path)) else "auto")
        results[name] = measure(path, whites[name])
    keys = list(next(iter(results.values())).keys())
    print(f"{'image':<22}" + "".join(f" {key:>16}" for key in keys) + "  white")
    for name, row in results.items():
        print(f"{name:<22}" + "".join(f"{row[key]:>17.3f}" for key in keys) + f"  {whites[name]}")


if __name__ == "__main__":
    main()

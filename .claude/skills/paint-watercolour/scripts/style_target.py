"""Style target: turn a photograph into the picture a style would make of it, before any paint is planned.

A painter in a given style does not copy the photograph's tones or colours. Donna Stiles's rule is that tone is
relative: the order of lights and darks is kept, their spread is the painter's. So the photograph's values are
remapped, rank for rank, onto the value distribution measured from paintings in the style, and each value is given
the colour the style's limited palette gives it there. Cool places in the photograph (a wall, an iris) take the
style's cool mix instead of the warm ramp.

Usage:
    style_target.py <photo> <output target.png> --sheet W,H [--crop x0,y0,x1,y1]
        [--quantiles 0:0.03,0.05:0.04,0.25:0.20,0.5:0.60,0.75:0.82,0.91:0.89,1:1]
        [--warm-ramp layered-shape-chiaroscuro] [--coolness 0.05] [--preview preview.png]

--quantiles  share of the sheet : value at that share. The default is the signature measured from a Donna Stiles
             portrait (5% below 0.04, a quarter below 0.20, half below 0.60, 9% left as near-white paper).
--coolness   how much bluer than red a place of the photograph must be (0 to 1 scale) to take the cool mix fully.

Run it with the Python that the watercolor tool uses; it reads that tool's pigment table.
"""

import argparse

import numpy as np
from PIL import Image, ImageFilter

PAPER = np.array([247.0, 244.0, 237.0])
LUMA = np.array([0.2126, 0.7152, 0.0722])

# Paint proportions of the warm ramp, keyed by the value they are used at, and of the cool mix.
RAMPS = {
    "layered-shape-chiaroscuro": {
        "warm": [
            (0.00, {"cobalt_blue": 0.62, "burnt_umber": 0.38}),
            (0.14, {"cobalt_blue": 0.55, "burnt_umber": 0.45}),
            (0.30, {"burnt_sienna": 0.45, "burnt_umber": 0.35, "cobalt_blue": 0.20}),
            (0.55, {"burnt_sienna": 0.68, "yellow_ochre": 0.32}),
            (0.80, {"yellow_ochre": 0.72, "burnt_sienna": 0.28}),
            (1.00, {"yellow_ochre": 0.80, "burnt_sienna": 0.20}),
        ],
        "cool": {"cobalt_blue": 0.70, "burnt_sienna": 0.30},
    }
}


def absorption_of(mix: dict[str, float]) -> np.ndarray:
    from watercolor.pigments import PIGMENTS

    vector = sum(np.array(PIGMENTS[name].absorption) * amount for name, amount in mix.items())
    return vector / (vector @ LUMA)


def remap_values(value: np.ndarray, quantiles: list[tuple[float, float]]) -> np.ndarray:
    """Give each pixel the value at its rank in the target distribution, so the photograph's order is kept.

    Equal values share the mean of their ranks: ranked one by one, in the order the pixels are stored, a flat area
    (a crushed shadow, a blown sky) would come out as a gradient from its top to its bottom."""
    flat = value.ravel()
    _, inverse, counts = np.unique(flat, return_inverse=True, return_counts=True)
    ends = np.cumsum(counts)
    ranks = ((ends - (counts + 1) / 2) / max(flat.size - 1, 1))[inverse]
    shares, values = zip(*quantiles)
    return np.interp(ranks, shares, values).reshape(value.shape)


def colour_for(value: np.ndarray, coolness: np.ndarray, ramp: dict) -> np.ndarray:
    """The colour on the harness's paper that has this value and the ramp's mix at it."""
    keys = [key for key, _ in ramp["warm"]]
    vectors = np.array([absorption_of(mix) for _, mix in ramp["warm"]])
    direction = np.stack([np.interp(value, keys, vectors[:, channel]) for channel in range(3)], -1)
    cool = absorption_of(ramp["cool"])
    weight = (coolness * np.clip((value - 0.12) / 0.2, 0.0, 1.0))[..., None]
    direction = direction * (1 - weight) + cool * weight
    direction /= (direction @ LUMA)[..., None]
    paper_luma = PAPER @ LUMA
    low, high = np.zeros(value.shape), np.full(value.shape, 8.0)
    for _ in range(40):
        middle = (low + high) / 2
        luma = (PAPER * np.exp(-middle[..., None] * direction)) @ LUMA / paper_luma
        darker = luma < value
        high = np.where(darker, middle, high)
        low = np.where(darker, low, middle)
    return PAPER * np.exp(-((low + high) / 2)[..., None] * direction)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photo")
    parser.add_argument("output")
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--crop")
    parser.add_argument("--quantiles", default="0:0.03,0.05:0.04,0.25:0.20,0.5:0.60,0.75:0.82,0.91:0.89,1:1")
    parser.add_argument("--warm-ramp", default="layered-shape-chiaroscuro", choices=sorted(RAMPS))
    parser.add_argument("--coolness", type=float, default=0.05)
    parser.add_argument("--denoise", type=int, default=7, help="median filter size before ranking (odd)")
    parser.add_argument(
        "--background-blur",
        type=float,
        default=0.0,
        help="Gaussian radius applied to the cool background before banding (try 14 at 768 px)",
    )
    parser.add_argument(
        "--cool-lift",
        type=float,
        default=0.0,
        help="share (0 to 1) by which a cool background is lifted toward paper after the remap",
    )
    parser.add_argument("--preview")
    parser.add_argument("--sheet-photo", help="also write the cropped photograph at sheet size, for grids and previews")
    arguments = parser.parse_args()

    width, height = (int(part) for part in arguments.sheet.split(","))
    photo = Image.open(arguments.photo).convert("RGB")
    if arguments.crop:
        x0, y0, x1, y1 = (int(part) for part in arguments.crop.split(","))
        photo = photo.crop((x0, y0, x1, y1))
    photo = photo.resize((width, height), Image.Resampling.LANCZOS)
    if arguments.sheet_photo:
        # reference_grid.py and preview_pass.py scale whatever image they are given to the sheet: give them this one
        photo.save(arguments.sheet_photo)
    # Ranking spreads a near-black, noisy passage (hair, a dark room) over the whole value range, so the noise is
    # removed first: a median takes out the grain, a light blur the steps it leaves.
    quiet = photo.filter(ImageFilter.MedianFilter(arguments.denoise)).filter(ImageFilter.GaussianBlur(1.5))
    rgb = np.asarray(quiet).astype(np.float64) / 255.0
    quantiles = [
        (float(share), float(level)) for share, level in (pair.split(":") for pair in arguments.quantiles.split(","))
    ]
    value = remap_values(rgb @ LUMA, quantiles)

    smooth = np.asarray(photo.filter(ImageFilter.GaussianBlur(4.0))).astype(np.float64) / 255.0
    coolness = np.clip(((smooth[..., 1] + smooth[..., 2]) / 2 - smooth[..., 0]) / arguments.coolness, 0.0, 1.0)
    if arguments.background_blur:
        # Her backgrounds are loose. Detail there (a screen's text, a wall's texture) bands into stripes, so the
        # cool background is blended toward a heavy blur of itself before the bands are cut from it.
        soft = (
            np.asarray(
                Image.fromarray((value * 255).astype(np.uint8)).filter(
                    ImageFilter.GaussianBlur(arguments.background_blur)
                )
            ).astype(np.float64)
            / 255.0
        )
        weight = (
            np.asarray(Image.fromarray((coolness * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))).astype(
                np.float64
            )
            / 255.0
        )
        value = value * (1 - weight) + soft * weight
    if arguments.cool_lift:
        # Her backgrounds are loose and pale. A dark cool wall behind the sitter is lifted toward paper, by the
        # given share of its distance from white, so the darks of the remap stay on the figure.
        lift = arguments.cool_lift * np.clip(coolness, 0.0, 1.0)
        value = 1.0 - (1.0 - value) * (1.0 - lift)
    target = colour_for(value, coolness, RAMPS[arguments.warm_ramp])
    Image.fromarray(np.clip(target, 0, 255).astype(np.uint8)).save(arguments.output)

    if arguments.preview:
        both = Image.new("RGB", (width * 2 + 8, height), "white")
        both.paste(photo, (0, 0))
        both.paste(Image.open(arguments.output), (width + 8, 0))
        both.save(arguments.preview)
    print(
        f"{arguments.output}: value p05 {np.percentile(value, 5):.2f}, p50 {np.percentile(value, 50):.2f}, "
        f"cool share {100 * (coolness > 0.5).mean():.1f}%"
    )


if __name__ == "__main__":
    main()

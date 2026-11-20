"""Hand marks for layered-shape chiaroscuro: the marks laid by hand after the tonal bands, as functions that return
lists of harness actions. Coordinates are sheet pixels; read them off `reference_grid.py` grids of the photograph at
sheet scale, and check every pass with `preview_pass.py` before painting it.

    import sys; sys.path.insert(0, "<this directory>")
    from hand_marks import *
    actions = smoky_lid(LASH) + [DRY] + pupil(298, 255, 9.0) + fringed_line(OVER_IRIS, 3.0, 3.0) + [DRY]

Every function here was tested in the style trials, the eye functions on 0.8.0 (they need masking fluid); the
numbers are the ones that worked.
"""

import math

import numpy as np
from PIL import Image, ImageDraw
from tonal_shapes import contours, inset, resampled

BLUE_BLACK = {"cobalt_blue": 1.55, "burnt_umber": 0.95}
WARM_DARK = {"burnt_sienna": 0.9, "burnt_umber": 0.7, "cobalt_blue": 0.2}
BROWN_IRIS = {"burnt_umber": 0.9, "burnt_sienna": 0.5, "cobalt_blue": 0.15}
GREY_GREEN_IRIS = {"yellow_ochre": 0.5, "cobalt_blue": 0.35, "burnt_umber": 0.25}
RUN_MIX = {"burnt_sienna": 1.1, "burnt_umber": 0.55, "yellow_ochre": 0.25}
DRY = {"action": "dry"}


def scaled(mix: dict, total: float) -> dict:
    current = sum(mix.values())
    return {name: round(amount * total / current, 3) for name, amount in mix.items()}


def load(size, pigments, water=0.9, hair="kolinsky_sable", brush="round"):
    return {"action": "load", "brush": brush, "hair": hair, "size": size, "pigments": pigments, "water": water}


def stroke(points, speed=120, smooth=True):
    return {"action": "stroke", "path": [list(point) for point in points], "speed": speed, "smooth": smooth}


def dab(x, y, pressure=1.0, dwell=0.4):
    return {"action": "stroke", "path": [[x, y, pressure]], "dwell": dwell}


def polygon_mask(points, sheet):
    canvas = Image.new("L", sheet, 0)
    ImageDraw.Draw(canvas).polygon([tuple(point) for point in points], fill=255)
    return np.asarray(canvas) > 0


def puddle(mask, mix, cut=2.5, fill=5.0, water=0.95, stripe=70):
    """One flat puddle on dry paper: its contour (and every hole's) cut with a small squirrel round set in by its
    radius, the inside flooded with rows one radius apart, so it dries as one wash with a crisp rim. It is worked a
    stripe at a time (cut, then flood, then the next stripe) so a large shape's cut is still wet when the flood meets
    it, and the rows start at the shape's own top so no dry hairline opens between the cut and the first row."""
    from tonal_shapes import runs_of_stripe

    actions = []
    loops = [resampled(loop) for loop in contours(inset(mask, cut))]
    inside = inset(mask, fill)
    rows_at = np.nonzero(inside.any(1))[0]
    shape_rows = np.nonzero(mask.any(1))[0]
    if not len(shape_rows):
        return actions
    top, bottom = int(shape_rows.min()), int(shape_rows.max()) + 1
    row_ys = np.arange(rows_at.min(), rows_at.max() + 1, fill * 0.95) if len(rows_at) else np.array([])
    forward, travelled = True, 1e9
    for stripe_top in range(top, bottom, stripe):
        stripe_bottom = stripe_top + stripe
        for loop in loops:
            for piece in runs_of_stripe(loop, stripe_top, stripe_bottom):
                actions += [
                    load(cut, mix, water, "squirrel"),
                    stroke([[round(float(x), 1), round(float(y), 1), 0.9] for x, y in piece], speed=160),
                ]
        for y in row_ys[(row_ys >= stripe_top) & (row_ys < stripe_bottom)]:
            row = inside[round(y)]
            edges = np.flatnonzero(np.diff(np.concatenate([[0], row.astype(np.int8), [0]])))
            for start, end in zip(edges[::2], edges[1::2]):
                if travelled > 400:
                    actions.append(load(fill, mix, water, "squirrel"))
                    travelled = 0
                a, b = (start, end - 1) if forward else (end - 1, start)
                actions.append(stroke([[float(a), float(y), 0.9], [float(b), float(y), 0.9]], speed=240, smooth=False))
                travelled += abs(b - a)
            forward = not forward
    return actions


def charged_puddle(mask, mix, charge_path, charge_mix, charge_size=3.0):
    """A feature as two values in one wet shape (a lip, a nose's cast shadow): the puddle, then a darker mix touched
    along its shadow side from a brush drained to 0.6. Flat one-value puddles read as stickers."""
    return puddle(mask, mix) + [load(charge_size, charge_mix, 0.6, "squirrel"), stroke(charge_path, speed=90)]


def fringed_line(
    path, core_size, core_strength, fringe_size=5.0, fringe_strength=4.0, mix=BLUE_BLACK, offset=-2.0, angle=62
):
    """A brow or lash: a wet core line, then a drained brush laid over its upper side at an angle, so the crisp line
    breaks into dry-brush texture above. `path` is [(x, y, pressure), ...]. Dry-brush alone left only specks; a
    smooth full stroke alone dried like eyeliner."""
    fringe = [{"x": x, "y": y + offset, "pressure": min(0.75, p), "angle": angle} for x, y, p in path]
    return [
        load(core_size, scaled(mix, core_strength), 0.85),
        stroke(path, speed=120),
        load(fringe_size, scaled(mix, fringe_strength), 0.9),
        {"action": "drain", "water": 0.45},
        {"action": "stroke", "path": fringe, "speed": 210, "smooth": True},
    ]


MASK_LIGHTEST_SHARE = 0.15  # the harness's width of a mask line laid with no pressure, as a share of its full width
LID_SHADOW = {"cobalt_blue": 0.3, "burnt_sienna": 0.12}
SHADED_WHITE = {"cobalt_blue": 0.55, "burnt_sienna": 0.3}


def eye_white_mask(upper, lower, inset=1.5, step=4.0):
    """Masking fluid for the white of an eye, laid before any paint: one stroke along the midline between the lids,
    its pressure following the opening's half-height, so it tapers into both corners as the eye does.

    `upper` and `lower` are the lid edges as [(x, y), ...] from one corner to the other, both starting and ending at
    the corners. The whole opening is masked, iris and all: after the fluid is rubbed away the iris is painted onto
    the clean paper and its own round edge cuts the white, and the lash line drawn along the top edge sits on it.
    `inset` keeps the fluid that far inside the lids so no white shows above the lash line."""
    upper, lower = np.array(upper, float), np.array(lower, float)
    xs = np.arange(upper[0, 0], upper[-1, 0] + 0.01, step)
    top = np.interp(xs, upper[:, 0], upper[:, 1])
    bottom = np.interp(xs, lower[:, 0], lower[:, 1])
    half = np.clip((bottom - top) / 2 - inset, 0, None)
    radius = float(half.max())
    pressure = np.clip((half / radius - MASK_LIGHTEST_SHARE) / (1 - MASK_LIGHTEST_SHARE), 0, 1)
    path = [
        [round(float(x), 1), round(float((t + b) / 2), 1), round(float(p), 3)]
        for x, t, b, p in zip(xs, top, bottom, pressure)
    ]
    return {"action": "mask", "path": path, "radius": round(radius, 2)}


def catchlight_masks(points, radius=2.6):
    """Masking fluid dots for the catchlights, laid on the clean white after the eye masks are rubbed away and before
    the iris. Keep each one inside the opening, clear of the upper lid. On 0.10.0, under the iris, lid and pupil, dots
    of 2.6 stayed at paper (0.95 to 0.96) and dots of 2.0 and 1.5 greyed to 0.70 to 0.94: the eye mask sealed this
    paper once already, and the picture still shares paint across the edge of a later reserve there."""
    return [{"action": "mask", "path": [[x, y]], "radius": radius} for x, y in points]


def shade_lit_white(shadow_path, soften_path):
    """A lit eye's white: a cool grey under the upper lid across its top (`shadow_path`, corner to corner, just under
    the lid), softened downward at once with a clean brush drained to 0.45 along `soften_path`, about 5 px lower.
    Points are (x, y, pressure); light pressure at the corners."""
    return [
        load(4.0, LID_SHADOW, 0.85, "squirrel"),
        stroke(shadow_path),
        load(4.0, {}, 0.45, "squirrel"),
        stroke(soften_path),
    ]


def shade_shadowed_white(path):
    """An eye in shadow (the look's value round it under about 0.3): its whole white at a middle value, laid along
    the middle of the opening, darker under the lid."""
    return [load(5.0, SHADED_WHITE, 0.85, "squirrel"), stroke(path, speed=100)]


def visible_iris(x0, x1, y, half_height, mix=BROWN_IRIS, strength=2.2):
    """Only the visible part of an iris: a short level stroke from (x0, y) to (x1, y) of a round sized to the
    opening's half-height at the iris, at full pressure, slowly. Its round ends cut the white as the iris does, and
    the lids clip it. Put x0 and x1 one radius inside the iris's sides. A full disc of the iris's own radius spilt
    onto the lower lid as a brown crescent."""
    return [load(half_height, scaled(mix, strength), 0.85), stroke([(x0, y, 1.0), (x1, y, 1.0)], speed=20)]


def lid_shadow_over_iris(path):
    """The upper lid's shadow across the iris's top third: a short arc [(x, y, pressure), ...] over the iris, light
    at its ends."""
    return [load(4.0, scaled(BLUE_BLACK, 1.4), 0.85), stroke(path, speed=50)]


def limbal_arcs(cx, cy, radius, top, bottom):
    """The dark ring of the iris at its two sides: thin arcs of the iris's circle (centre and radius), kept between
    the lids (`top` and `bottom` are the opening's y at the iris)."""

    def arc(start, end):
        points = [
            (cx + radius * math.cos(math.radians(a)), cy + radius * math.sin(math.radians(a)))
            for a in range(start, end + 1, 10)
        ]
        return [(round(x, 1), round(y, 1), 0.6) for x, y in points if top <= y <= bottom]

    return [load(1.5, scaled(BLUE_BLACK, 1.8), 0.85), stroke(arc(145, 215), speed=50), stroke(arc(-35, 35), speed=50)]


def lower_lid(path):
    """A thin warm line along the lower lid, under the white: [(x, y, pressure), ...], light at the corners."""
    return [load(1.3, scaled(WARM_DARK, 1.2), 0.85), stroke(path, speed=90)]


def brow(path):
    """A brow as a heavy fringed line. The blind trial found `fringed_line(path, 3.4, 2.6, 5.5, 4.2)` dried as a thin
    line with almost no fringe; these values gave a heavy, textured brow. For a pale (silver) brow halve both
    strengths."""
    return fringed_line(path, 4.5, 2.2, 6.5, 5.0, angle=50, offset=-3.0)


def smoky_lid(lash_path):
    """The lid's smudge: a blue-black stroke along the lid and a thin dark core charged into it while it is wet, so
    the core bleeds soft. (A bed of clear water under it dried as a second crisp stripe; softening with a damp brush
    left a graphic arc.) Follow with `DRY`, then `pupil` and a short `fringed_line` over the iris only."""
    return [
        load(5.5, scaled(BLUE_BLACK, 1.6), 0.9, "squirrel"),
        stroke([(x, y - 2, 0.85) for x, y, _ in lash_path], speed=160),
        load(2.6, scaled(BLUE_BLACK, 3.2), 0.6, "squirrel"),
        stroke([(x, y, max(0.3, p)) for x, y, p in lash_path], speed=110),
    ]


def pupil(x, y, radius, strength=3.0):
    """Lay twice, with a dry between: the pupil is the darkest dark of the picture."""
    return [
        load(radius, scaled(BLUE_BLACK, strength), 0.8),
        {"action": "stroke", "path": [[x, y, 1.0], [x, y + 1, 1.0]], "speed": 20},
    ]


def run(x, y0, length, size=2.5, wander=(0, 0.8, -0.6, 1.3, 0.4, -1.1, -0.3), mix=RUN_MIX):
    """A painted run straight down from inside a wet pool, ending in a bead: 35 px a second, pressure 0.75 falling to
    0.45 and rising to 0.58, then the same mix at 1.3 times the size, full, dwelt 1.8 s at the end."""
    points = []
    for index in range(7):
        fraction = index / 6
        pressure = [0.75, 0.55, 0.48, 0.45, 0.47, 0.5, 0.58][index]
        points.append(
            {
                "x": round(x + wander[index], 1),
                "y": round(y0 + fraction * length, 1),
                "pressure": pressure,
                "t": round(fraction * length / 35.0, 2),
            }
        )
    return [
        load(size, mix, 0.9),
        {"action": "stroke", "path": points, "smooth": True},
        load(round(size * 1.3, 2), mix, 1.0),
        dab(points[-1]["x"], points[-1]["y"], 0.95, 1.8),
    ]


def tear(pool_path, runs, pool_mix=None):
    """A pool (e.g. along a lower lid) and its runs, then tilt 0.18 for 45 s so the pool throws a short physical comb.
    Everything else on the sheet must be dry. `runs` is [(x, y0, length, size), ...], at most three, of different
    lengths, each starting inside the pool. Runs only read over pale paint: never lay them over a near-black mass."""
    pool_mix = pool_mix or {"burnt_sienna": 0.45, "yellow_ochre": 0.2, "burnt_umber": 0.1}
    actions = [load(4.5, pool_mix, 1.0, "squirrel"), stroke(pool_path, speed=60)]
    for x, y0, length, size in runs:
        actions += run(x, y0, length, size)
    return actions + [
        {"action": "tilt", "x": 0, "y": 0.18},
        {"action": "wait", "seconds": 45},
        {"action": "tilt", "x": 0, "y": 0},
        DRY,
    ]


def cool_background(target, close=41):
    """The cool counterpoint: a clear-water bed over the target's cool, light background, closed into one region (or
    detail behind the sitter beds as stripes), kept 6 px off the figure, with greyed cobalt charged in at up to eight
    points to spread soft. `target` is the style target as an RGB array at sheet size."""
    import torch
    from torch.nn import functional

    value = target.mean(-1) / 255
    cool = (target[..., 2] > target[..., 0]) & (value > 0.4)
    tensor = torch.from_numpy(cool.astype(np.float32))[None, None]
    tensor = -functional.max_pool2d(-functional.max_pool2d(tensor, close, 1, close // 2), close, 1, close // 2)
    cool = (tensor[0, 0].numpy() > 0.5) & (value > 0.4) & (target[..., 2] >= target[..., 0] - 3)
    cool = inset(cool, 6)
    actions = puddle(cool, {}, cut=4.0, fill=10.0, water=0.95)
    ys, xs = np.nonzero(inset(cool, 16))
    if len(xs):
        rng = np.random.default_rng(9)
        for index in rng.choice(len(xs), size=min(8, len(xs)), replace=False):
            x, y = int(xs[index]), int(ys[index])
            actions += [
                load(8.0, {"cobalt_blue": 1.1, "burnt_sienna": 0.25}, 0.6, "squirrel"),
                stroke([(x, y - 14, 0.6), (x + 2, y + 14, 0.9)], speed=110),
            ]
    return actions + [DRY]

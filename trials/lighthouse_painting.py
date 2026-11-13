"""A lighthouse on a headland, painted through a session.

A study after Michele Clamp's lighthouse watercolour and the order of work in her tutorial:
https://micheleclamp.com/lighthouse-watercolor-tutorial/
The composition is hers. The positions of its shapes were measured from her painting.

    python trials/lighthouse_painting.py <directory> [stage ...]

With no stages named, the whole painting is made and finished. Naming stages paints only
those, which is how a single passage is studied on a sheet of its own.
"""

import math
import random
import sys
from collections.abc import Callable, Sequence
from itertools import pairwise
from pathlib import Path

from watercolor.brushes import Journey
from watercolor.pigments import PIGMENTS
from watercolor.session import Configuration, Session

WIDTH, HEIGHT = 768, 544
HORIZON = 397.0
Action = dict[str, object]
Points = Journey

# The tower, measured from the reference: body, gallery, the collar under the lantern room,
# the lantern room, its dome and the cupola on top.
BODY_TOP, BODY_BASE = 177.0, 424.0
BAND_TOP, BAND_BASE = 267.0, 348.0
GALLERY_TOP, COLLAR_TOP = 160.0, 147.0
LANTERN_TOP, DOME_TOP, CUPOLA_TOP = 103.0, 79.0, 57.0
AXIS = 324.0
LANTERN_HALF, COLLAR_HALF, CUPOLA_HALF = 29.5, 33.0, 10.5
GALLERY_LEFT, GALLERY_RIGHT = 265.0, 385.0


def tower_left(y: float) -> float:
    return 274.0 - 4.0 * (y - BODY_TOP) / (BODY_BASE - BODY_TOP)


def tower_right(y: float) -> float:
    return 380.0 + 7.0 * (y - BODY_TOP) / (BODY_BASE - BODY_TOP)


def dome_half(y: float) -> float:
    """Half the width of the dome at a height: a half ellipse standing on the lantern room."""
    rise = (LANTERN_TOP - y) / (LANTERN_TOP - DOME_TOP + 2.0)
    return max(CUPOLA_HALF, LANTERN_HALF * math.sqrt(max(0.0, 1.0 - rise * rise)))


def silhouette(y: float) -> tuple[float, float] | None:
    """Left and right limits of the lighthouse at a height, or None above it."""
    if y < CUPOLA_TOP or y >= BODY_BASE:
        return None
    if y < DOME_TOP:
        return AXIS - CUPOLA_HALF, AXIS + CUPOLA_HALF
    if y < LANTERN_TOP:
        return AXIS - dome_half(y), AXIS + dome_half(y)
    if y < COLLAR_TOP:
        return AXIS - LANTERN_HALF, AXIS + LANTERN_HALF
    if y < GALLERY_TOP:
        return AXIS - COLLAR_HALF, AXIS + COLLAR_HALF
    if y < BODY_TOP:
        return GALLERY_LEFT, GALLERY_RIGHT
    return tower_left(y), tower_right(y)


def load(brush: str, size: float, pigments: dict[str, float], water: float = 1.0, rinse: bool = True) -> Action:
    return {"action": "load", "brush": brush, "size": size, "pigments": pigments, "water": water, "rinse": rinse}


def stroke(path: Points, speed: float = 120.0, smooth: bool = False) -> Action:
    return {"action": "stroke", "path": path, "speed": speed, "smooth": smooth}


def dab(x: float, y: float, dwell: float = 0.3) -> Action:
    return {"action": "stroke", "path": [[x, y, 0.8]], "dwell": dwell}


def pencil(path: Points, darkness: float = 0.35) -> Action:
    return {"action": "pencil", "path": path, "darkness": darkness, "smooth": False}


def wait(seconds: float) -> Action:
    return {"action": "wait", "seconds": seconds}


DRY: Action = {"action": "dry"}


def tilt(y: float) -> Action:
    """Raise the top of the board: positive values pull the paint down the sheet."""
    return {"action": "tilt", "x": 0.0, "y": y}


# ------------------------------------------------------------------ stages


def drawing() -> list[Action]:
    """A line drawing with no shading: only the edges that separate one passage from another."""
    lines = [
        [[tower_left(BODY_TOP), BODY_TOP], [tower_left(BODY_BASE), BODY_BASE]],
        [[tower_right(BODY_TOP), BODY_TOP], [tower_right(BODY_BASE), BODY_BASE]],
        [[tower_left(BAND_TOP), BAND_TOP], [tower_right(BAND_TOP), BAND_TOP]],
        [[tower_left(BAND_BASE), BAND_BASE], [tower_right(BAND_BASE), BAND_BASE]],
        [[GALLERY_LEFT, GALLERY_TOP], [GALLERY_RIGHT, GALLERY_TOP], [GALLERY_RIGHT, BODY_TOP], [GALLERY_LEFT, BODY_TOP], [GALLERY_LEFT, GALLERY_TOP]],
        [[AXIS - COLLAR_HALF, GALLERY_TOP], [AXIS - COLLAR_HALF, COLLAR_TOP], [AXIS + COLLAR_HALF, COLLAR_TOP], [AXIS + COLLAR_HALF, GALLERY_TOP]],
        [[AXIS - LANTERN_HALF, COLLAR_TOP], [AXIS - LANTERN_HALF, LANTERN_TOP], [AXIS + LANTERN_HALF, LANTERN_TOP], [AXIS + LANTERN_HALF, COLLAR_TOP]],
        [[AXIS - dome_half(y), y] for y in (103, 97, 91, 85, 80)] + [[AXIS + dome_half(y), y] for y in (80, 85, 91, 97, 103)],
        [[AXIS - CUPOLA_HALF, DOME_TOP], [AXIS - CUPOLA_HALF, CUPOLA_TOP], [AXIS + CUPOLA_HALF, CUPOLA_TOP], [AXIS + CUPOLA_HALF, DOME_TOP]],
        [[0, HORIZON], [270, HORIZON]],
        [[387, HORIZON], [640, HORIZON]],
        [[68, 489], [91, 474], [92, 460], [106, 449], [177, 443], [214, 427], [270, 424]],
        [[387, 421], [556, 424]],
        [[635, 438], [635, 365], [768, 362]],
        [[572, 440], [588, 544]],
        [[602, 458], [680, 544]],
    ]  # fmt: skip
    return [pencil(line) for line in lines]


def sky_mix(y: float, strength: float) -> dict[str, float]:
    """A greyed cobalt blue that weakens toward the horizon, where ochre and a little red turn it to cream."""
    low = y / HORIZON
    warm = max(0.0, low - 0.4)
    return {
        "cobalt_blue": strength * (1.0 - 0.9 * low) ** 1.3,
        "burnt_sienna": 0.33 * strength * (1.0 - 0.6 * low),
        "yellow_ochre": 0.32 * strength * warm,
        "cadmium_red": 0.09 * strength * warm,
    }


WALL_LEFT, WALL_TOP = 635.0, 365.0


def sky_right(y: float) -> float:
    """How far right a row of the sky runs: it stops short of the wall, which stays paper."""
    return WIDTH + 10.0 if y + 20.0 < WALL_TOP else WALL_LEFT - 16.0


def cut_in(top: float, base: float, strength: float, cutter: float) -> list[Action]:
    """The sky on both sides of one part of the lighthouse, each edge drawn in a single stroke."""
    mix = sky_mix(0.5 * (top + base), strength)
    actions: list[Action] = []
    steps = max(6, round((base - top) / 4.0))
    rows = [top + (base - top) * step / steps for step in range(steps + 1)]
    for side, sign in ((0, -1.0), (1, 1.0)):
        for inset in (0.0, 9.0):
            edge = [
                [limit[side] + sign * (cutter + 0.5 + inset), row, 1.0] for row in rows if (limit := silhouette(row))
            ]
            actions += [load("round", cutter, mix), stroke(edge, 160)]
    return actions


def sky(strength: float = 0.72) -> list[Action]:
    """A graded wash laid in rows from the top, cut in around the lighthouse so that it stays white."""
    actions: list[Action] = []
    mop, cutter = 22.0, 7.0
    # Parts of the lighthouse, top to bottom, each cut in as the wash reaches it.
    parts = [
        (CUPOLA_TOP, GALLERY_TOP - cutter),
        (GALLERY_TOP + 4, BODY_TOP - 4),
        (BODY_TOP + cutter, 300.0),
        (300.0, BODY_BASE - 1),
    ]
    y = 14.0
    while y < HORIZON + 8:
        mix = sky_mix(y, strength)
        while parts and parts[0][0] < y + 14:
            top, base = parts.pop(0)
            actions += cut_in(top, base, strength, cutter)
            if base == GALLERY_TOP - cutter:
                # The ledges of the gallery, which is wider than the lantern room above it.
                ledge = GALLERY_TOP - cutter - 0.5
                reach = AXIS - COLLAR_HALF - cutter
                actions += [
                    load("round", cutter, mix),
                    stroke([[GALLERY_LEFT - 10, ledge, 1.0], [reach, ledge, 1.0]], 160),
                ]
                reach = AXIS + COLLAR_HALF + cutter
                actions += [stroke([[reach, ledge, 1.0], [GALLERY_RIGHT + 10, ledge, 1.0]], 160)]
        limits = [limit for row in (y - 12, y, y + 12) if (limit := silhouette(row))]
        if not limits:
            actions += [load("mop", mop, mix), stroke([[-10, y, 0.9], [sky_right(y), y, 0.9]], 280)]
        else:
            left = min(limit[0] for limit in limits) - cutter - mop + 2
            right = max(limit[1] for limit in limits) + cutter + mop - 2
            actions += [load("mop", mop, mix), stroke([[-10, y, 0.9], [left, y, 0.9]], 280)]
            actions += [load("mop", mop, mix), stroke([[right, y, 0.9], [sky_right(y), y, 0.9]], 280)]
        y += 24.0
    # The strip of sky just above the wall, which the broad rows stop short of.
    actions += [
        load("round", 8, sky_mix(WALL_TOP - 18.0, strength)),
        stroke([[WALL_LEFT - 12, WALL_TOP - 18, 1.0], [WIDTH + 8, WALL_TOP - 20, 1.0]], 160),
    ]
    edge = WALL_TOP - 7.0
    actions += [
        load("round", 6, sky_mix(edge, strength)),
        stroke([[WALL_LEFT - 2, edge, 1.0], [WIDTH + 8, edge - 3, 1.0]], 160),
    ]
    # While it is all still wet, pull streaks down through it: darker on the left, and clear water on the right.
    for x in (28.0, 92.0, 168.0):
        actions += [
            load("mop", 12, scaled(sky_mix(100.0, strength), 1.3)),
            stroke([[x, 6, 0.8], [x + 6, 250, 0.6]], 300),
        ]
    for x in (432.0, 500.0, 566.0, 640.0, 716.0):
        actions += [load("mop", 12, {}, 0.6), stroke([[x, 16, 0.7], [x - 70, 290, 0.5]], 300)]
    return [*actions, DRY]


GREY = {"cobalt_blue": 0.30, "burnt_sienna": 0.28}


def tower_shadow() -> list[Action]:
    """A light grey down the shadow side, right to the edge, softened inward with a damp brush so the tower turns."""
    actions: list[Action] = []
    top, base = BODY_TOP + 9, BODY_BASE - 6
    for offset in (7.5, 20.0):
        actions.append(load("round", 9, GREY))
        actions.append(stroke([[tower_right(top) - offset, top, 0.9], [tower_right(base) - offset, base, 0.9]], 140))
    actions.append(load("round", 9, {}, 0.4))
    actions.append(stroke([[tower_right(top) - 32, top, 0.9], [tower_right(base) - 34, base, 0.9]], 100))
    # The gallery and the lantern room are in shadow on the same side.
    middle = 0.5 * (GALLERY_TOP + BODY_TOP)
    actions += [load("round", 5, GREY), stroke([[AXIS + 26, middle, 0.9], [GALLERY_RIGHT - 6, middle, 0.9]], 80)]
    actions += [
        load("round", 4, GREY),
        stroke([[AXIS + 21, LANTERN_TOP + 5, 0.9], [AXIS + 24, GALLERY_TOP - 5, 0.9]], 80),
    ]
    return [*actions, DRY]


RED = {"cadmium_red": 2.6, "hansa_yellow": 0.6}
DARK_RED = {"cadmium_red": 2.8, "quinacridone_rose": 0.9, "burnt_sienna": 0.5, "ivory_black": 0.12}


def red_band() -> list[Action]:
    """Vermilion wrapped right across the tower with a flat brush, then a darker red dropped into the shadow side."""
    actions: list[Action] = []
    rows = (BAND_TOP + 8.5, BAND_TOP + 24.5, BAND_TOP + 40.5, BAND_TOP + 56.5, BAND_BASE - 8.5)
    for coat in range(2):
        for y in rows:
            # The flat brush ends its stroke square, so the band meets both edges of the tower cleanly.
            actions += [
                load("flat", 8.5, RED),
                stroke([[tower_left(y) + 1.5, y, 1.0], [tower_right(y) - 1.5, y, 1.0]], 90),
            ]
        if coat == 0:
            actions.append(wait(4))
    for offset in (8.0, 20.0):
        actions.append(load("round", 7, DARK_RED))
        actions.append(stroke([[tower_right(BAND_TOP) - offset, BAND_TOP + 8, 0.9], [tower_right(BAND_BASE) - offset, BAND_BASE - 8, 0.9]], 80))  # fmt: skip
    return [*actions, DRY]


def land_left(y: float) -> float:
    """Where the headland meets the sea on the left, at a height."""
    corners = (
        (HORIZON, 270.0),
        (BODY_BASE, 262.0),
        (427.0, 214.0),
        (443.0, 177.0),
        (449.0, 106.0),
        (460.0, 92.0),
        (474.0, 91.0),
        (489.0, 68.0),
        (508.0, 64.0),
        (HEIGHT + 20.0, 65.0),
    )
    for (y0, x0), (y1, x1) in pairwise(corners):
        if y <= y1:
            return x0 + (x1 - x0) * (y - y0) / (y1 - y0)
    return corners[-1][1]


SEA = {"cobalt_blue": 1.2, "french_ultramarine": 0.35, "burnt_sienna": 0.15}


def sea() -> list[Action]:
    """A mid-value blue with a straight horizon, a little deeper toward the bottom of the sheet."""
    actions: list[Action] = []
    y = HORIZON + 8.5
    while y < HEIGHT + 8:
        deep = (y - HORIZON) / (HEIGHT - HORIZON)
        mix = SEA | {"cobalt_blue": 1.0 + 0.7 * deep, "french_ultramarine": 0.3 + 0.5 * deep}
        actions += [load("round", 9, mix), stroke([[-8, y, 0.9], [land_left(y) - 8, y, 0.9]], 110)]
        y += 13.0
    # The strip of sea seen beyond the headland, to the right of the tower.
    actions.append(load("round", 6, SEA))
    for y in (402.0, 412.0):
        actions.append(stroke([[tower_right(y) + 7, y, 0.9], [WALL_LEFT - 8, y, 0.9]], 110))
    return [*actions, DRY]


def foreground_wash() -> list[Action]:
    """One pale warm wash over the whole headland, whatever is drawn there."""
    mix = {"burnt_sienna": 0.07, "yellow_ochre": 0.15}
    actions: list[Action] = []
    y = 436.0
    while y < HEIGHT + 10:
        actions += [load("mop", 16, mix), stroke([[land_left(y) + 14, y, 0.9], [WIDTH + 10, y, 0.9]], 140)]
        y += 20.0
    # The wall on the right stands above the horizon.
    wall = {"yellow_ochre": 0.42, "burnt_sienna": 0.16}
    for y in (375.0, 393.0, 411.0, 429.0):
        actions += [load("round", 10, wall), stroke([[WALL_LEFT + 10, y, 0.9], [WIDTH + 10, y, 0.9]], 120)]
    # A warmer patch low on its near end, dropped in while the wash is wet.
    actions += [
        load("round", 8, {"yellow_ochre": 0.9, "burnt_sienna": 0.4}),
        stroke([[650, 398, 0.8], [700, 404, 0.9]], 100),
    ]
    return [*actions, DRY]


OLIVE = {"hansa_yellow": 2.0, "ivory_black": 0.7, "french_ultramarine": 0.25}
RUST = {"burnt_sienna": 2.2, "cadmium_red": 0.7, "hansa_yellow": 0.5}
OCHRE = {"yellow_ochre": 1.6, "burnt_sienna": 0.5}
ROCK_SHADOW = {"burnt_umber": 0.55, "cobalt_blue": 0.3, "ivory_black": 0.08}
ROCK_DARK = {"burnt_umber": 1.3, "cobalt_blue": 0.6, "ivory_black": 0.4}
UMBER = {"burnt_umber": 1.8, "yellow_ochre": 0.6}
UMBER_DARK = {"burnt_umber": 2.4, "french_ultramarine": 0.5}
DARK = {"french_ultramarine": 1.5, "burnt_sienna": 1.9, "ivory_black": 0.7}


def facet(
    path: Sequence[Sequence[float]], mix: dict[str, float], size: float = 5.0, twist: float = 0.0
) -> list[Action]:
    """One crisp-edged plane of shadow, laid with a flat brush on dry paper.

    Turning the edge of the brush a little gives the plane slanted ends, so it reads as a face
    seen at an angle and not as a bar.
    """
    points = [{"x": x, "y": y, "pressure": 0.9, "twist": twist} for x, y in path]
    return [load("flat", size, mix), stroke(points, 110)]


def dragged(
    spine: Sequence[tuple[float, float]],
    depth: float,
    count: int,
    mixes: Sequence[tuple[dict[str, float], float]],
    seed: int,
    sizes: tuple[float, float] = (5.0, 9.0),
) -> list[Action]:
    """Dry-brush: the side of a round brush dragged lightly and quickly along the strata.

    Laid over, the brush rides on the grain of the paper and leaves a broken, sparkling mark,
    which is how rough rock is given its texture without being filled in.
    """
    chance = random.Random(seed)
    (x0, y0), (x1, y1) = spine[0], spine[-1]
    actions: list[Action] = []
    for _ in range(count):
        share = chance.random()
        x, y = x0 + (x1 - x0) * share, y0 + (y1 - y0) * share + chance.triangular(-1.0, 1.0, 0.0) * depth
        reach, slope = chance.uniform(14.0, 34.0), chance.uniform(-0.15, 0.15)
        mix = chance.choices([mix for mix, _ in mixes], [weight for _, weight in mixes])[0]
        hold = {"angle": chance.uniform(78.0, 90.0), "pressure": chance.uniform(0.35, 0.7)}
        path = [{"x": x - reach, "y": y - reach * slope, **hold}, {"x": x + reach, "y": y + reach * slope, **hold}]
        actions += [load("round", chance.uniform(*sizes), mix, 0.7), stroke(path, chance.uniform(200.0, 320.0))]
    return actions


def flicks(
    roots: Sequence[tuple[float, float]], mix: dict[str, float], seed: int, brush: str = "comber", size: float = 4.0
) -> list[Action]:
    """Grasses and stems: each one pressed at its root and flicked upward, fast, as the pressure lifts."""
    chance = random.Random(seed)
    actions: list[Action] = []
    for x, y in roots:
        lean, height = chance.uniform(-7.0, 7.0), chance.uniform(9.0, 16.0)
        path = [
            {"x": x, "y": y, "pressure": 0.9, "t": 0.0},
            {"x": x + 0.4 * lean, "y": y - 0.5 * height, "pressure": 0.6, "t": 0.25},
            {"x": x + lean, "y": y - height, "pressure": 0.05, "t": 0.34},
        ]
        actions += [load(brush, size, mix, 0.8), stroke(path, 120, smooth=True)]
    return actions


def broken(path: Sequence[Sequence[float]], mix: dict[str, float], size: float = 3.0) -> list[Action]:
    """A dragged, half-dry line that skips on the grain."""
    return [load("round", size, mix, 0.3), stroke([[x, y, 0.6] for x, y in path], 240)]


def touches(
    spine: Sequence[tuple[float, float]],
    depth: float,
    count: int,
    mixes: Sequence[tuple[dict[str, float], float]],
    seed: int,
    sizes: tuple[float, float] = (3.5, 7.0),
    lean: float = 0.7,
    brush: str = "round",
) -> list[Action]:
    """Many short, varied touches along a spine, laid wet into each other.

    Each touch has its own length, direction, pressure, speed and colour (mixes are given with
    weights). Those in the body are made with the belly of the brush; those at the fringe with
    its side, laid over and nearly dry, which leaves a ragged edge.
    """
    chance = random.Random(seed)
    lengths = [math.dist(a, b) for a, b in pairwise(spine)]
    actions: list[Action] = []
    for _ in range(count):
        along = chance.uniform(0.0, sum(lengths))
        for (x0, y0), (x1, y1), length in zip(spine, spine[1:], lengths):
            if along <= length:
                break
            along -= length
        share = along / max(length, 1e-6)
        across = chance.triangular(-1.0, 1.0, 0.0)
        x, y = x0 + (x1 - x0) * share, y0 + (y1 - y0) * share + across * depth
        mix = chance.choices([mix for mix, _ in mixes], [weight for _, weight in mixes])[0]
        size = chance.uniform(*sizes)
        reach, angle = chance.uniform(0.6, 1.6) * size, chance.uniform(-lean, lean)
        dx, dy = reach * math.cos(angle), reach * math.sin(angle)
        fringe = abs(across) > 0.6
        actions.append(load(brush, size, mix, 0.5 if fringe else 0.95))
        hold = chance.uniform(75.0, 90.0) if fringe else chance.uniform(25.0, 45.0)
        path = [
            {"x": x - dx, "y": y - dy, "pressure": chance.uniform(0.3, 0.7), "angle": hold},
            {"x": x, "y": y, "pressure": 1.0, "angle": hold},
            {"x": x + dx, "y": y + dy, "pressure": chance.uniform(0.2, 0.6), "angle": hold},
        ]
        actions.append(stroke(path, chance.uniform(110.0, 240.0)))
    return actions


def inset(corners: Sequence[tuple[float, float]], distance: float) -> list[tuple[float, float]] | None:
    """A convex outline moved inward by a distance, or None where it is too small to survive that."""
    count = len(corners)
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(corners, [*corners[1:], corners[0]]))
    turn = 1.0 if area > 0 else -1.0
    edges = []
    for (x0, y0), (x1, y1) in zip(corners, [*corners[1:], corners[0]]):
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 1e-6:
            return None
        normal = (-(y1 - y0) / length * turn, (x1 - x0) / length * turn)
        edges.append(((x0 + normal[0] * distance, y0 + normal[1] * distance), (x1 - x0, y1 - y0)))
    moved = []
    for index in range(count):
        (px, py), (dx, dy) = edges[index - 1]
        (qx, qy), (ex, ey) = edges[index]
        cross = dx * ey - dy * ex
        if abs(cross) < 1e-6:
            return None
        along = ((qx - px) * ey - (qy - py) * ex) / cross
        moved.append((px + dx * along, py + dy * along))
    inner = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(moved, [*moved[1:], moved[0]]))
    return moved if inner * turn > 4.0 * distance * distance else None


def plane(
    corners: Sequence[tuple[float, float]],
    mix: dict[str, float],
    seed: int,
    brush: float = 3.5,
    accent: dict[str, float] | None = None,
) -> list[Action]:
    """An angular shape of any convex outline: each edge drawn with one stroke along it, then flooded.

    Because a stroke runs along every edge, a slanted side is as clean as a level one. The corners
    are placed a little unevenly, and a darker accent can be touched in while it is wet.
    """
    chance = random.Random(seed)
    corners = [(x + chance.uniform(-1.5, 1.5), y + chance.uniform(-1.5, 1.5)) for x, y in corners]
    core = inset(corners, brush)
    while core is None and brush > 1.6:
        brush *= 0.75
        core = inset(corners, brush)
    if core is None:
        return [load("round", 1.5, mix), stroke([[x, y, 1.0] for x, y in [*corners, corners[0]]], 90)]
    closed = [*core, core[0]]
    actions: list[Action] = [load("round", brush, mix), stroke([[x, y, 1.0] for x, y in closed], 110)]
    spans: list[tuple[float, float, float]] = []
    top, base = min(y for _, y in core), max(y for _, y in core)
    y = top + 1.2 * brush
    while y < base - 0.6 * brush:
        crossings = sorted(
            x0 + (x1 - x0) * (y - y0) / (y1 - y0) for (x0, y0), (x1, y1) in pairwise(closed) if (y0 - y) * (y1 - y) < 0
        )
        if len(crossings) >= 2 and crossings[-1] - crossings[0] > brush:
            spans.append((crossings[0], crossings[-1], y))
        y += 1.4 * brush
    for left, right, y in spans:
        actions += [load("round", brush, mix), stroke([[left, y, 1.0], [right, y, 1.0]], 110)]
    # The tip goes round the outline last, which takes the paint into the corners.
    tip = inset(corners, 1.3)
    if tip is not None:
        actions += [load("round", 1.3, mix), stroke([[x, y, 1.0] for x, y in [*tip, tip[0]]], 90)]
    if accent is not None:
        actions.append(load("round", 0.8 * brush, accent))
        for _ in range(2):
            index = chance.randrange(len(core))
            (x0, y0), (x1, y1) = core[index], core[index - 1]
            share = chance.uniform(0.2, 0.8)
            actions.append(dab(x0 + (x1 - x0) * share, y0 + (y1 - y0) * share, 0.4))
    return actions


def scaled(mix: dict[str, float], strength: float) -> dict[str, float]:
    return {name: strength * amount for name, amount in mix.items()}


def foreground() -> list[Action]:
    """Darks over the dry wash, each shape copied from the reference at its own size and laid with a brush to suit."""
    actions: list[Action] = []
    dark_green = {"hansa_yellow": 1.4, "ivory_black": 1.3, "french_ultramarine": 0.4}
    foliage = ((dark_green, 5.0), (OLIVE, 3.0), (RUST, 1.0), (OCHRE, 0.5))
    hedge = ((OLIVE, 3.5), (dark_green, 3.0), (RUST, 2.5), (OCHRE, 1.0))
    orange_red = {"burnt_sienna": 1.8, "cadmium_red": 1.0, "hansa_yellow": 0.6}
    scrub = ((RUST, 5.0), (orange_red, 2.5), (UMBER_DARK, 2.0), (OLIVE, 1.5))
    ochre_brown = {"burnt_sienna": 0.7, "yellow_ochre": 1.2}
    neutral = {"ivory_black": 0.5, "french_ultramarine": 0.3, "burnt_umber": 0.3}
    rock_grey = {"ivory_black": 0.55, "french_ultramarine": 0.5, "burnt_umber": 0.35}
    # The ochre bank at the head of the cliff: a thin band rising to the right, in one stroke of a flat brush.
    actions += facet([[96, 469], [176, 449]], {"yellow_ochre": 1.5, "burnt_sienna": 0.7}, 6.0)
    # The rock the tower stands on: an angular wedge welded to its base, darkest under the tower's shadow.
    rock = [(270, 425), (336, 425), (352, 452), (346, 466), (300, 468), (272, 466)]
    actions += plane(rock, rock_grey, seed=50, brush=6.0, accent=ROCK_DARK)
    actions += [
        load("round", 6, scaled(rock_grey, 1.6)),
        stroke([[300, 436, 0.6], [322, 442, 1.0], [338, 452, 0.7]], 90, smooth=True),
    ]
    actions += [load("round", 5, scaled(rock_grey, 0.6)), stroke([[258, 430, 0.8], [262, 462, 0.9]], 90)]
    # Foliage, painted wet on a tilted sheet so that the darkest green runs from its lower edge.
    actions.append(tilt(0.16))
    actions += touches([(96, 482), (168, 474)], 4, 26, foliage, seed=2, sizes=(3.0, 5.5))
    actions += touches([(176, 470), (254, 469)], 8, 46, foliage, seed=12, sizes=(4.0, 7.5), brush="cats_tongue")
    actions.append(tilt(0.28))
    for x, y, dwell in ((114.0, 487.0, 7.0), (160.0, 484.0, 4.0), (178.0, 482.0, 4.0)):
        actions += [load("mop", 4, {"hansa_yellow": 0.9, "ivory_black": 0.8}), dab(x, y, dwell)]
    actions += [wait(20), tilt(0.0)]
    actions += touches(
        [(364, 456), (440, 452), (524, 456)], 11, 100, hedge, seed=3, sizes=(3.5, 7.5), brush="cats_tongue"
    )
    actions += touches([(590, 423), (636, 425)], 11, 44, foliage, seed=4, sizes=(4.0, 7.5))
    right_mass = ((UMBER_DARK, 3.0), (dark_green, 3.0), (OLIVE, 1.5), (ochre_brown, 1.0))
    # The dark mass below the wall, laid in strokes that climb to the right so that light shows between them.
    slopes = random.Random(72)
    for index in range(16):
        x, y = 680.0 + slopes.uniform(0.0, 30.0), 418.0 + 3.2 * index + slopes.uniform(-2.0, 2.0)
        reach = slopes.uniform(40.0, 86.0)
        mix = slopes.choices([mix for mix, _ in right_mass], [weight for _, weight in right_mass])[0]
        hold = slopes.uniform(35.0, 80.0)
        path = [
            {"x": x, "y": y, "pressure": 0.8, "angle": hold},
            {"x": x + 0.5 * reach, "y": y - 0.2 * reach, "pressure": 1.0, "angle": hold},
            {"x": x + reach, "y": y - 0.4 * reach, "pressure": 0.5, "angle": hold},
        ]
        actions += [load("filbert", slopes.uniform(3.5, 6.5), mix), stroke(path, slopes.uniform(120.0, 260.0))]
    actions += touches([(354, 526), (450, 523), (546, 526)], 15, 130, scrub, seed=6, sizes=(4.0, 8.0))
    actions += touches([(216, 538), (228, 537)], 4, 6, foliage, seed=10, sizes=(4.0, 7.0))
    actions += touches([(270, 538), (292, 537)], 4, 8, foliage, seed=11, sizes=(4.0, 7.0))
    actions.append(DRY)
    # A second layer over the dry first one: the undersides of the foliage.
    under = ((dark_green, 3.0), (UMBER_DARK, 1.0))
    actions += touches([(180, 478), (250, 477)], 4, 22, under, seed=21, sizes=(3.0, 5.5))
    actions += touches([(370, 464), (440, 461), (520, 464)], 4, 30, under, seed=22, sizes=(3.0, 5.5))
    actions += touches([(592, 431), (634, 432)], 5, 20, under, seed=23, sizes=(3.0, 5.5))
    actions += touches(
        [(360, 536), (450, 534), (544, 536)], 6, 36, ((UMBER_DARK, 3.0), (RUST, 2.0)), seed=35, sizes=(3.5, 6.5)
    )
    # The texture of the rock: pale ochre and grey dragged over it with the side of the brush.
    rough = (
        ({"yellow_ochre": 0.6, "burnt_sienna": 0.3}, 3.0),
        (scaled(neutral, 0.7), 2.0),
        ({"burnt_sienna": 0.6}, 1.0),
    )
    actions += dragged([(96, 512), (232, 518)], 22, 30, rough, seed=81)
    actions += dragged([(250, 536), (350, 534)], 8, 8, rough, seed=82)
    actions += dragged([(366, 482), (560, 478)], 10, 18, rough, seed=83)
    actions += dragged([(392, 432), (548, 434)], 5, 10, rough, seed=84, sizes=(4.0, 6.0))
    actions += dragged([(676, 500), (704, 500)], 30, 8, rough, seed=85, sizes=(4.0, 6.0))
    actions += dragged([(280, 444), (344, 448)], 12, 10, ((ROCK_DARK, 1.0),), seed=86, sizes=(5.0, 8.0))
    actions.append(DRY)
    # The cliff: grey planes of shadow on the pale face, each one stroke of a flat brush whose edge
    # is turned a little so the plane ends on a slant; the darkest at its foot.
    for path, mix, size, twist in (
        ([[240, 485], [342, 484]], scaled(neutral, 1.5), 7.5, 28.0),
        ([[241, 506], [304, 505]], scaled(neutral, 0.8), 10.5, -22.0),
        ([[241, 521], [318, 520]], scaled(neutral, 1.8), 5.5, 30.0),
        ([[171, 518], [236, 518]], scaled(neutral, 1.5), 8.5, 0.0),
        ([[406, 500], [427, 499]], scaled(neutral, 1.5), 6.5, 15.0),
    ):
        actions += facet(path, mix, size, twist)
    # Smaller marks in the rock: a pale wedge beside the shadowed face, dashes under the rock, hairline runs.
    actions += plane([(320, 500), (346, 498), (344, 512), (322, 514)], scaled(neutral, 0.6), seed=48, brush=3.0)
    actions += plane([(382, 496), (404, 495), (404, 507), (384, 508)], scaled(neutral, 0.7), seed=52, brush=3.0)
    for path in ([[346, 466], [366, 468]], [[352, 472], [370, 473]], [[232, 470], [252, 472]]):
        actions += broken(path, scaled(neutral, 2.0), 2.0)
    for x, y in ((140.0, 492.0), (150.0, 494.0), (192.0, 490.0)):
        actions += line([[x, y], [x + 1, y + 14]], scaled(OLIVE, 0.7), 0.8)
    actions += line([[70, 492], [66, 512], [68, 544]], neutral, 1.0)
    actions += line([[152, 538], [170, 526]], neutral, 0.9)
    actions += line([[388, 421], [556, 424]], neutral, 0.9)
    # The terrace: an orange wall in a single stroke of a flat brush, with a bench below it and rails at its foot.
    actions += facet([[406, 489], [524, 465]], {"burnt_sienna": 1.6, "hansa_yellow": 0.7, "cadmium_red": 0.2}, 4.5)
    actions += facet([[490, 499], [543, 498]], DARK, 2.0)
    for x in (494, 540):
        actions += line([[x, 500], [x, 508]], DARK, 0.9)
    for x in (356, 364, 373, 381):
        actions += line([[x, 498], [x + 1, 512]], DARK, 0.9)
    actions += [load("round", 3, DARK), dab(563, 442, 0.4)]
    # The path's shadow: one stroke of a very large round brush, with the fence posts standing along its edge.
    path_shadow = scaled(neutral, 1.5)
    actions += [
        load("dagger", 19, path_shadow),
        stroke([[580, 440, 0.1], [584, 480, 0.45], [589, 548, 1.0]], 90, smooth=True),
    ]
    for index in range(9):
        y = 448.0 + 11.0 * index
        actions += line([[573 - 0.5 * index, y], [569 - 0.8 * index, y - 1]], DARK, 0.9 + 0.05 * index)
    # Shadows cast across the path: the steps, the rails, and the two figures.
    for path in (
        [[604, 482], [626, 482]],
        [[664, 482], [704, 481]],
        [[606, 502], [624, 502]],
        [[610, 524], [700, 522]],
        [[632, 510], [662, 546]],
        [[652, 508], [686, 546]],
        [[604, 462], [612, 546]],
    ):
        actions += line(path, scaled(neutral, 1.3), 1.2)
    actions += [
        load("round", 3.5, scaled(neutral, 1.6)),
        stroke([[638, 509, 0.9], [668, 507, 0.7], [698, 503, 0.3]], 80),
    ]
    # The salmon wall at the head of the path, in one stroke.
    actions += facet([[590, 447], [674, 447]], {"burnt_sienna": 0.5, "cadmium_red": 0.12, "yellow_ochre": 0.5}, 9.0)
    # The terraces to the right: close-set steps of ochre and dark brown climbing to the right.
    steps = random.Random(70)
    for step in range(15):
        x, y = 690.0 + steps.uniform(0.0, 16.0), 470.0 + 5.6 * step + steps.uniform(-1.5, 1.5)
        reach = steps.uniform(50.0, 80.0)
        mix = UMBER_DARK if step % 2 == 0 else steps.choice((ochre_brown, UMBER, scaled(OLIVE, 0.8)))
        path = [
            {"x": x, "y": y, "pressure": 0.9, "twist": 0.0, "t": 0.0},
            {"x": x + 0.6 * reach, "y": y - 0.27 * reach, "pressure": 0.8, "twist": 35.0, "t": 0.45},
            {"x": x + reach, "y": y - 0.45 * reach, "pressure": 0.5, "twist": 70.0, "t": 0.6},
        ]
        actions += [
            load("flat", steps.uniform(3.0, 5.0), mix, steps.uniform(0.6, 0.95)),
            stroke(path, 180, smooth=True),
        ]
    # Grasses flicked up from the scrub, the hedge and the head of the cliff.
    actions += flicks([(x, 513.0) for x in range(366, 540, 19)], scaled(RUST, 0.8), seed=91)
    actions += flicks([(x, 446.0) for x in range(374, 520, 24)], scaled(OLIVE, 0.9), seed=92)
    actions += flicks([(x, 464.0) for x in range(182, 252, 17)], scaled(OLIVE, 0.9), seed=93)
    actions += facet([[730, 494], [735, 514]], UMBER_DARK, 5.0)
    actions += facet([[716, 478], [720, 518]], UMBER_DARK, 3.0)
    actions += facet([[752, 490], [757, 546]], UMBER_DARK, 5.0)
    return [*actions, DRY]


def line(path: Sequence[Sequence[float]], mix: dict[str, float], size: float = 1.2) -> list[Action]:
    return [load("rigger", size, mix), stroke([[x, y, 0.7] for x, y in path], 70)]


FIGURES = ((635.0, 458.0, DARK), (655.0, 455.0, {"burnt_sienna": 2.2, "ivory_black": 0.5}))


def details() -> list[Action]:
    """Windows, the lantern room, the gallery, the lamp post and two figures."""
    actions: list[Action] = []
    glass = {"cobalt_blue": 0.85, "burnt_sienna": 0.7}
    deep_glass = {"cobalt_blue": 1.7, "burnt_sienna": 1.5}
    left, right = AXIS - LANTERN_HALF, AXIS + LANTERN_HALF
    # Lantern room: even grey glass in three broad strokes, darker where it turns from the light.
    middle = 0.5 * (LANTERN_TOP + COLLAR_TOP)
    for y in (LANTERN_TOP + 9, middle, COLLAR_TOP - 9):
        actions += [load("round", 8, glass), stroke([[left + 8, y, 1.0], [right - 8, y, 1.0]], 80)]
    actions += [
        load("round", 6, deep_glass),
        stroke([[AXIS + 16, LANTERN_TOP + 7, 0.9], [AXIS + 21, COLLAR_TOP - 7, 0.9]], 80),
    ]
    # The dome: one curved stroke of pale grey, a darker one on its shadow side; the cupola likewise.
    pale = scaled(glass, 0.5)
    actions += [
        load("round", 8, pale),
        stroke(
            [[AXIS - 17, LANTERN_TOP - 7, 0.9], [AXIS, DOME_TOP + 9, 1.0], [AXIS + 17, LANTERN_TOP - 7, 0.9]],
            70,
            smooth=True,
        ),
    ]
    actions += [load("round", 5, glass), stroke([[AXIS + 7, DOME_TOP + 7, 0.7], [AXIS + 20, LANTERN_TOP - 6, 1.0]], 70)]
    actions += [load("round", 6, pale), stroke([[AXIS - 3, CUPOLA_TOP + 7, 1.0], [AXIS - 3, DOME_TOP - 4, 1.0]], 60)]
    actions += [load("round", 3, glass), stroke([[AXIS + 5, CUPOLA_TOP + 5, 0.9], [AXIS + 6, DOME_TOP - 3, 0.9]], 60)]
    actions += [
        load("round", 5, pale),
        stroke([[AXIS - 27, COLLAR_TOP + 6.5, 0.9], [AXIS + 27, COLLAR_TOP + 6.5, 0.9]], 80),
    ]
    actions.append(DRY)
    # Its frame, drawn with the rigger.
    frame = {"french_ultramarine": 1.2, "burnt_sienna": 1.4, "ivory_black": 0.4}
    for path in (
        [[left, COLLAR_TOP], [left, LANTERN_TOP], [right, LANTERN_TOP], [right, COLLAR_TOP]],
        [[AXIS - COLLAR_HALF, COLLAR_TOP], [AXIS + COLLAR_HALF, COLLAR_TOP]],
        [[AXIS - CUPOLA_HALF, DOME_TOP], [AXIS + CUPOLA_HALF, DOME_TOP]],
        [[AXIS, CUPOLA_TOP], [AXIS, 42]],
        [[AXIS - 9, 40], [AXIS + 8, 38], [AXIS + 8, 43]],
    ):
        actions += line(path, frame, 0.8)
    actions += [load("round", 2.2, frame), dab(AXIS, 50, 0.3)]
    # Gallery: a balcony standing out from the tower on brackets, with its rail and the shadow under its floor.
    actions += line([[GALLERY_LEFT, GALLERY_TOP + 1], [GALLERY_RIGHT, GALLERY_TOP + 1]], frame, 0.8)
    for x in range(int(GALLERY_LEFT) + 2, int(GALLERY_RIGHT), 12):
        actions += line([[x, GALLERY_TOP + 1], [x, BODY_TOP - 5]], frame, 0.7)
    actions += [
        load("round", 2.8, DARK),
        stroke([[GALLERY_LEFT + 1, BODY_TOP - 2, 0.9], [GALLERY_RIGHT - 1, BODY_TOP - 2, 0.9]], 70),
    ]
    for x, inward in ((GALLERY_LEFT + 2, 1.0), (GALLERY_RIGHT - 2, -1.0)):
        actions += line([[x, BODY_TOP - 1], [x + 9 * inward, BODY_TOP + 9]], DARK, 1.2)
    # Windows: small dark squares, narrower on the side that turns away.
    for x, y, size, height in (
        (299.5, 229.0, 4.5, 9.0),
        (301.0, 304.0, 4.5, 9.0),
        (373.0, 229.0, 3.0, 9.0),
        (381.0, 376.0, 2.2, 7.0),
        (383.0, 396.0, 2.2, 8.0),
    ):
        actions += [load("flat", size, DARK), stroke([[x, y, 1.0], [x, y + height, 1.0]], 50)]
    # Lamp post with its hooked head, the top of the wall and its rail.
    post = {"french_ultramarine": 1.6, "burnt_sienna": 1.5}
    actions += line([[679, 363], [679, 286], [672, 282], [668, 286]], post)
    actions += [load("round", 2.2, DARK), dab(667, 288, 0.3)]
    actions += line([[637, 364], [768, 361]], post, 0.9)
    for x in range(730, 766, 5):
        actions += line([[x, 365], [x, 378]], {"burnt_sienna": 1.8, "cadmium_red": 0.5}, 0.8)
    # Two figures walking down the path: heads, arms and striding legs; a bag between them.
    skin = {"burnt_sienna": 2.2, "cadmium_red": 0.4, "burnt_umber": 0.6}
    for (x, top, hair), stride in zip(FIGURES, (1.0, -1.0)):
        actions += [load("round", 2.8, skin), dab(x, top, 0.3)]
        actions += [load("round", 2.0, hair), dab(x, top - 3.5, 0.2)]
        actions += line([[x - 5, top + 8], [x - 7 - stride, top + 22]], skin, 1.0)
        actions += line([[x + 5, top + 8], [x + 7 - stride, top + 21]], skin, 1.0)
        actions += line([[x - 2, top + 31], [x - 2 - 3 * stride, top + 49]], skin, 1.1)
        actions += line([[x + 2, top + 31], [x + 2 + 3 * stride, top + 48]], skin, 1.1)
        for foot in (x - 2 - 3 * stride, x + 2 + 3 * stride):
            actions += [load("round", 1.5, DARK), dab(foot, top + 51, 0.2)]
    actions += [load("round", 2.4, DARK), dab(645, 478, 0.3)]
    return [*actions, DRY]


WHITE = {"opaque_white": 4.5}


def white_details() -> list[Action]:
    """Opaque white for what could not be left as paper: glints on the lantern glass, and the figures' clothes."""
    actions: list[Action] = []
    # The diamond lattice of the glazing, pale against the grey glass, in two coats.
    bars = [AXIS - LANTERN_HALF + 2.0 + 11.0 * index for index in range(6)]
    middle = 0.5 * (LANTERN_TOP + COLLAR_TOP)
    for _ in range(2):
        for near, far in pairwise(bars):
            for top, base in ((LANTERN_TOP + 2.0, middle), (middle, COLLAR_TOP - 2.0)):
                actions += line([[near, top], [far, base]], WHITE, 1.0)
                actions += line([[near, base], [far, top]], WHITE, 1.0)
    # The rail along the ledge, light against the grey plane behind it.
    rail = random.Random(60)
    for x in (176, 186, 195, 206, 216, 228):
        actions += line(
            [[x, 511 + rail.uniform(-1, 1)], [x + rail.uniform(-1, 1), 519 + rail.uniform(0, 2)]], WHITE, 0.8
        )
    actions += line([[172, 511], [234, 510]], WHITE, 0.7)
    actions += line([[152, 435], [214, 427], [262, 425]], WHITE, 0.8)
    # A white vehicle parked by the hedge at the head of the path.
    for _ in range(2):
        actions += [load("round", 5, WHITE), stroke([[640, 430, 1.0], [654, 430, 1.0]], 40)]
    actions += line([[636, 436], [658, 436]], scaled(ROCK_SHADOW, 2.0), 1.0)
    # The figures' clothes, in two coats so they stand out crisply.
    # A thin shadow down the right of each figure, so the white reads against the pale path.
    for x, top, _ in FIGURES:
        actions += line([[x + 5.5, top + 10], [x + 5.5, top + 29]], scaled(ROCK_SHADOW, 2.0), 0.8)
    for x, top, _ in FIGURES:
        for _ in range(2):
            actions += [load("round", 4.5, WHITE), stroke([[x, top + 9, 1.0], [x, top + 29, 1.0]], 40)]
    return [*actions, DRY]


STAGES: dict[str, Callable[[], list[Action]]] = {
    stage.__name__: stage
    for stage in (drawing, sky, tower_shadow, red_band, sea, foreground_wash, foreground, details, white_details)
}


def main() -> None:
    directory = Path(sys.argv[1])
    names = sys.argv[2:] or list(STAGES)
    configuration = Configuration(
        prompt="A red and white lighthouse on a rocky headland in strong sunlight, after Michele Clamp",
        size=WIDTH,
        height=HEIGHT,
        seed=11,
        palette=list(PIGMENTS),
        stroke_budget=5000,
        scrap_allowed=False,
        pencil_allowed=True,
    )
    session = Session.create(directory, configuration)
    for name in names:
        session.paint(STAGES[name]())
        print(f"{name}: {session.report()['strokes_used']} strokes, look saved to {session.look()}")
    if not sys.argv[2:]:
        picture, video = session.finish()
        print(f"finished: {picture} and {video}")


if __name__ == "__main__":
    main()

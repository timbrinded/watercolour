"""Organic marks: shapes made the way a round-headed brush makes them, as lists of harness actions.

One press is a disc. One smoothed stroke that swells and tapers is a leaf, a pebble or a crescent. A larger blob is
filled by one brush that goes round just inside its outline and keeps going round inward to the middle, so its edge
is a single smooth stroke and not the stepped ends of rows. `references/shapes-and-fills.md` says when to use which.

    import sys; sys.path.insert(0, "<this directory>")
    from organic_marks import follow_inward, load, press, swelling
    actions = [load("round", 20, MIX)] + press(300, 300)                        # a disc
    actions += [load("round", 26, MIX)] + swelling([(80, 500), (120, 497), (160, 500)], (0.35, 1.0, 0.35))  # a pebble
    actions += follow_inward(outline, "mop", 22, MIX)                           # loads the brush itself, every turn

Coordinates and sizes are sheet pixels.
"""

import math

from preview_pass import painted_width


def load(brush: str, size: float, mix: dict[str, float], water: float = 0.9, hair: str | None = None) -> dict:
    action: dict = {"action": "load", "brush": brush, "size": round(size, 1), "pigments": mix, "water": water}
    if hair:
        action["hair"] = hair
    return action


def press(x: float, y: float, pressure: float = 1.0, dwell: float | None = None) -> list[dict]:
    """One press of the loaded brush: from a round or a mop at full pressure, a disc of about the brush's size in radius."""
    action: dict = {"action": "stroke", "path": [[round(x, 1), round(y, 1), pressure]]}
    if dwell is not None:
        action["dwell"] = dwell
    return [action]


def swelling(
    points: list[tuple[float, float]], pressures: tuple[float, ...] = (0.12, 1.0, 0.12), speed: float = 200
) -> list[dict]:
    """One smooth stroke through the points, the pressures spread along it: pressed in the middle and lifted at the
    ends it is a leaf on a straight path and a crescent on a curved one; pressed at one end only, a teardrop."""
    path = []
    for i, (x, y) in enumerate(points):
        along = i / max(1, len(points) - 1) * (len(pressures) - 1)
        lower = min(int(along), len(pressures) - 2)
        pressure = pressures[lower] + (pressures[lower + 1] - pressures[lower]) * (along - lower)
        path.append([round(x, 1), round(y, 1), round(pressure, 2)])
    return [{"action": "stroke", "path": path, "speed": speed, "smooth": True}]


def _depths(outline: list[tuple[float, float]]) -> list[tuple[float, float, float]]:
    """For each point of an outline, the direction straight into the shape there and how far that way its middle lies."""
    count = len(outline)
    turning = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1], strict=True))
    side = 1.0 if turning > 0 else -1.0
    edges = list(zip(outline, outline[1:] + outline[:1], strict=True))  # edge i runs from point i to the next

    def clear(x: float, y: float, some: list[tuple[tuple[float, float], tuple[float, float]]]) -> float:
        """The distance from a point to the nearest of some edges."""
        nearest = math.inf
        for (ax, ay), (bx, by) in some:
            run = (bx - ax) ** 2 + (by - ay) ** 2
            along = 0.0 if run == 0 else min(1.0, max(0.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / run))
            nearest = min(nearest, math.hypot(x - ax - along * (bx - ax), y - ay - along * (by - ay)))
        return nearest

    depths = []
    for i, (x, y) in enumerate(outline):
        (px, py), (qx, qy) = outline[i - 1], outline[(i + 1) % count]
        long = math.hypot(qx - px, qy - py) or 1.0
        nx, ny = -(qy - py) / long * side, (qx - px) / long * side
        own = [edges[i - 1], edges[i]]  # the two edges that meet at this point
        rest = [edge for j, edge in enumerate(edges) if j not in ((i - 1) % count, i)]
        deep = 0.0
        while True:  # walk in until some other part of the outline is nearer than the part walked in from
            ahead = x + nx * (deep + 1.0), y + ny * (deep + 1.0)
            if clear(*ahead, rest) < clear(*ahead, own):
                break
            deep += 1.0
        depths.append((nx, ny, deep))
    return depths


def follow_inward(
    outline: list[tuple[float, float]],
    brush: str,
    size: float,
    mix: dict[str, float],
    water: float = 0.9,
    overlap: float = 0.3,
    speed: float = 240,
    pressure: float = 0.9,
) -> list[dict]:
    """Fill a shape the way a hand does: the brush goes once round just inside the outline, which makes the edge,
    and keeps going round, each turn further in and overlapping the last, until it reaches the shape's middle.

    `outline` is the shape's edge as (x, y) points in order, either way round, in as few or as many points as
    describe it. Every turn is set in from the edge along the edge's own normal and stops at the middle of the
    shape, and the last turn runs along the middle, so a long shape is filled as truly as a round one. The shape
    must be wider than the brush paints; give a thinner one a swelling stroke down its length. The brush is loaded
    afresh for every turn, so no turn runs dry."""
    half = painted_width(brush, size, pressure) / 2
    pitch = 2 * half * (1 - overlap)
    depths = _depths(outline)
    deepest = max(deep for _, _, deep in depths)
    actions = []
    count = len(outline)
    turn = 0
    while True:
        begins = half + pitch * max(0, turn - 1)  # how far in this turn starts
        path = []
        for i in range(count + 2):  # a little past the start, so the turn closes
            (x, y), (nx, ny, deep) = outline[i % count], depths[i % count]
            inset = min(deep, begins + (pitch * i / count if turn else 0.0))
            path.append([round(x + nx * inset, 1), round(y + ny * inset, 1), pressure])
        actions.append(load(brush, size, mix, water))
        actions.append({"action": "stroke", "path": path, "speed": speed, "smooth": True})
        if begins >= deepest:  # this turn ran along the middle from its first point to its last
            return actions
        turn += 1

"""Helpers for composing a pass (a list of harness actions) in Python and writing it as JSON."""

import json

# The actions that count against the stroke budget when they are on the painting and not the scrap sheet: session.py's
# TOUCHING_ACTIONS, SURFACE_TREATMENTS and DRAWING_ACTIONS, mirrored so that these helpers need only the standard library.
BUDGETED_ACTIONS = ("stroke", "blot", "pen", "mask", "unmask", "fix", "draw")


def scaled(mix: dict[str, float], total: float) -> dict[str, float]:
    """Return the mix with its proportions kept and its amounts summing to `total`."""
    current = sum(mix.values())
    return {name: round(amount * total / current, 4) for name, amount in mix.items()}


def load(brush, size, pigments, water=0.9, hair=None, rinse=True):
    action = {"action": "load", "brush": brush, "size": size, "pigments": pigments, "water": water}
    if hair:
        action["hair"] = hair
    if not rinse:
        action["rinse"] = False
    return action


def stroke(path, speed=None, smooth=True, sheet=None):
    action = {"action": "stroke", "path": path, "smooth": smooth}
    if speed is not None:
        action["speed"] = speed
    if sheet:
        action["sheet"] = sheet
    return action


def pen(path, width, ink, speed=None, smooth=True, sheet=None):
    """A line in ink: `width` is the full width at full pressure, `ink` maps paints to the amount laid per pixel."""
    action = {"action": "pen", "path": path, "width": width, "ink": ink, "smooth": smooth}
    if speed is not None:
        action["speed"] = speed
    if sheet:
        action["sheet"] = sheet
    return action


def draw(medium, pigments, path, radius, sheet=None):
    """A line with a dry stick (`coloured_pencil` or `pastel`). Points at pressure 0 lift the stick, so one action can
    hold a whole hatch patch (see hatch)."""
    action = {"action": "draw", "medium": medium, "pigments": pigments, "path": path, "radius": radius}
    if sheet:
        action["sheet"] = sheet
    return action


def hatch(lines, pressure=0.6):
    """The path of a hatch patch: each line is ((x0, y0), (x1, y1)), drawn at the pressure, with the stick lifted
    between lines."""
    path = []
    for (x0, y0), (x1, y1) in lines:
        path += [[x0, y0, 0.0], [x0, y0, pressure], [x1, y1, pressure], [x1, y1, 0.0]]
    return path


def fix(path=None, radius=None, sheet=None):
    """Fixative along a path at a radius, or over the whole sheet when neither is given."""
    if (path is None) != (radius is None):
        raise ValueError("fixative takes a path and a radius together, or neither")
    action: dict[str, object] = {"action": "fix"}
    if path is not None:
        action["path"], action["radius"] = path, radius
    if sheet:
        action["sheet"] = sheet
    return action


def dab(x, y, pressure=0.7, dwell=0.3):
    return {"action": "stroke", "path": [[x, y, pressure]], "dwell": dwell}


def rows(x0, y0, x1, y1, spacing, pressure=0.9, speed=260):
    """Horizontal rows filling a rectangle, alternating direction, as one wash."""
    strokes, y, forward = [], y0, True
    while y <= y1:
        start, end = (x0, x1) if forward else (x1, x0)
        strokes.append(stroke([[start, y, pressure], [end, y, pressure]], speed=speed, smooth=False))
        y += spacing
        forward = not forward
    return strokes


def wait(seconds, at=None, film=None):
    action = {"action": "wait", "seconds": seconds}
    if at is not None:
        if film is None:
            raise ValueError("a wait at a point needs the film depth to wait for")
        action["at"], action["film"] = at, film
    return action


DRY = {"action": "dry"}


def budgeted(actions) -> int:
    """How many of the actions count against the painting's stroke budget."""
    return sum(1 for action in actions if action["action"] in BUDGETED_ACTIONS and action.get("sheet") != "scrap")


def write(actions, path):
    with open(path, "w") as handle:
        json.dump(actions, handle, indent=1)
    print(f"{path}: {len(actions)} actions, {budgeted(actions)} against the stroke budget")


def offset_path(points, distance):
    """Move a polyline sideways by `distance` pixels: positive is to the right of travel (screen coordinates)."""
    result = []
    for index, point in enumerate(points):
        before = points[max(index - 1, 0)]
        after = points[min(index + 1, len(points) - 1)]
        dx, dy = after[0] - before[0], after[1] - before[1]
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        moved = [round(point[0] - dy / length * distance, 1), round(point[1] + dx / length * distance, 1)]
        result.append(moved + list(point[2:]))
    return result


def with_pressure(points, pressure, ends=None):
    """Give every point one pressure, with lighter `ends` if set."""
    result = [[point[0], point[1], pressure] for point in points]
    if ends is not None and len(result) > 1:
        result[0][2] = ends
        result[-1][2] = ends
    return result


def translate(actions, dx, dy):
    """Shift every path and wait point: used to rehearse a region of the full sheet on a smaller study sheet."""
    moved = []
    for action in actions:
        action = dict(action)
        if "path" in action:
            path = []
            for point in action["path"]:
                if isinstance(point, dict):
                    point = dict(point, x=point["x"] + dx, y=point["y"] + dy)
                else:
                    point = [point[0] + dx, point[1] + dy] + list(point[2:])
                path.append(point)
            action["path"] = path
        if "at" in action:
            action["at"] = [action["at"][0] + dx, action["at"][1] + dy]
        moved.append(action)
    return moved


def fill_spans(spans, size, pressure=0.9, speed=220, inset=None):
    """Rows that fill a region given as (y, x_left, x_right) boundary spans, one stroke per span.

    Each row is drawn between the span's ends moved inward by the stroke's half width (about `size`
    at pressure 0.9), so the paint stops on the boundary. Space the spans 1.4 times `size` apart or closer:
    rows at the full painted width, twice `size`, leave a hairline of dry paper between them.
    """
    inset = size * 0.95 if inset is None else inset
    strokes, forward = [], True
    for y, left, right in spans:
        a, b = left + inset, right - inset
        if b <= a:
            a = b = (left + right) / 2
            strokes.append(dab(round(a, 1), y, pressure, 0.25))
        else:
            start, end = (a, b) if forward else (b, a)
            strokes.append(
                stroke([[round(start, 1), y, pressure], [round(end, 1), y, pressure]], speed=speed, smooth=False)
            )
        forward = not forward
    return strokes


def stages_of(actions):
    """The stages of a pass: each run of actions between one `dry` and the next, without the `dry`."""
    stages, current = [], []
    for action in actions:
        if action["action"] == "dry":
            stages.append(current)
            current = []
        else:
            current.append(action)
    if current:
        stages.append(current)
    return stages


def merge_stages(*passes):
    """Run several passes that work on separate areas as one: all their first stages, one dry, all their second
    stages, one dry, and so on. A stage is the run of actions between one `dry` and the next."""
    staged = [stages_of(actions) for actions in passes]
    merged = []
    for index in range(max(len(stages) for stages in staged)):
        for stages in staged:
            if index < len(stages):
                merged += stages[index]
        merged.append(DRY)
    return merged


def stage(actions, number):
    """The actions of one stage of a pass (stages are separated by `dry`), without the `dry`. The first stage is 0."""
    return stages_of(actions)[number]

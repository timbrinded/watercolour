"""What a run's passes are made of: inspect_passes.py <run directory>. Prints the count of strokes, the brush heads
loaded and how many strokes each made, and how many strokes lie in runs of straight level rows (four or more
two-point level strokes in a row from one head), which is how a shape is filled by scanning."""

import json
import sys
from collections import Counter
from pathlib import Path

FLAT_HEADS = {"flat", "bright", "flat_wash", "hake", "comber", "fan", "angular"}
run = Path(sys.argv[1])
heads, strokes, rows, streak, head = Counter(), 0, 0, 0, None
for path in sorted((run / "outputs" / "passes").glob("*.json")):
    for action in json.loads(path.read_text()):
        kind = action.get("action")
        if kind == "load":
            if action.get("brush") != head:  # a reload of the same head does not end a run of rows
                streak = 0
            head = action.get("brush")
        elif kind == "stroke" and action.get("sheet") != "scrap":  # trials on the scrap sheet are not the painting
            strokes += 1
            heads[head] += 1
            points = [(p["x"], p["y"]) if isinstance(p, dict) else (p[0], p[1]) for p in action["path"]]
            level = (
                len(points) >= 2
                and max(y for _, y in points) - min(y for _, y in points) < 2.5
                and abs(points[-1][0] - points[0][0]) > 12
            )
            streak = streak + 1 if level else 0
            if streak == 4:
                rows += 4
            elif streak > 4:
                rows += 1
print(
    json.dumps(
        {
            "strokes": strokes,
            "heads": dict(heads),
            "strokes_from_flat_heads": sum(n for h, n in heads.items() if h in FLAT_HEADS),
            "strokes_in_level_rows": rows,
        },
        indent=1,
    )
)

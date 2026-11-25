# Test cases for the skill

Each folder is one task for a fresh painter, in the layout `claude plugin eval` reads: `prompt.md` is the brief,
`case.yaml` says what a good result looks like, and each file in `graders/` is one statement to check against the
result. Run a case twice, once with this skill and once with the skill as it was before a change, and compare.

Two scripts do the checks that can be measured. Both take a run directory holding `outputs/painting.png` and
`outputs/passes/*.json`:

- `grade_shapes.py <run>` measures `fills-three-given-shapes`: for each outline (`outputs/shapes.json`), the share of
  it painted, the paint outside it, how far the painted edge strays from it, and how even the tone is.
- `inspect_passes.py <run>` counts a run's strokes by brush head, the strokes from flat-headed brushes, and the
  strokes laid as runs of level rows.

Statements about how a picture looks are graded blind: give a separate grader only the pictures, each under a
random letter, and the statements, and ask it also which picture of each pair is the better painting. A picture
can pass every statement about its edges and still be the worse painting.

Keep a run's copy of the skill free of this folder, so the painter cannot read what is expected of it.

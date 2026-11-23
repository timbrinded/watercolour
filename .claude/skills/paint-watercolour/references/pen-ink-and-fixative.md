# Pen, ink and fixative

Read this before drawing with the pen or laying fixative. Both need 0.10.0 or later; `actions.md` has their fields. Everything here was measured on 0.10.0, on cold press, paper seed 3, sheets of 128 to 256 pixels. Values are the value view, where bare paper reads 0.96.

## When to reach for the pen

The pen lays the same ink on every pixel it covers, from the start of a line to its end, and never draws narrower than one pixel. A brush line that fine comes out pale instead: SKILL.md's fine line, a rigger of size 1 at full water, dried at 0.29 from `ivory_black` at 4 and 0.12 from `carbon_ink` at 4, where a pen line of `carbon_ink` at 1 dried at 0.047 with paper either side. All three were one pixel wide at half their contrast.

- **Use it for** a drawing that the washes go over or under (line and wash), hatching, lettering, rigging, window bars and other ruled detail, and the few darks too fine for any brush.
- **Do not use it for** a line that should change in value along its length, fade out or be lost into a wash. Its weight changes with pressure; its value does not.
- **Keep to one manner.** A drawing in ink with washes is a manner of its own. In this skill's manner, a pen mark is for the few marks a brush cannot make narrow enough.

## Which ink

Both inks are on a painting only when `--palette` names them.

| Measured | `carbon_ink` | `soluble_ink` |
|---|---|---|
| One-pixel line on dry paper, at 0.5 / 1 / 2 | 0.21 / 0.047 / 0.003 | 0.43 / 0.19 / 0.04 |
| A clear mop wash over the dried line, then dried | Unchanged: 0.99 of the ink stays on its line | The line at 2 becomes 0.75 inside a grey haze (0.85 two pixels out); a tenth of the ink stays on the line |
| A burnt sienna wash at 0.6 over it (0.735 alone) | Unchanged; the wash beside it 0.72 | The line at 2 becomes 0.55; the wash beside it 0.65 |
| Four passes of a stiff brush drained to 0.2, and a blot | 0.995 of the ink stays | Not measured; a damp brush pulls it out (`actions.md`) |

- **`carbon_ink` when the drawing must stay as drawn.** Draw first, then wash over it as freely as the passage needs. Fixative adds nothing to it: scrubbed, it kept 0.995 of its ink unfixed and all of it fixed.
- **`soluble_ink` when a wash should turn the drawing into soft shading.** Every wash over the line dissolves most of it, so the line survives only where no later water reaches it. To keep part of a drawing crisp, fix it first: a line at 2 fixed along half its length stayed at 0.041 there under a clear wash, and spread to 0.77 on the other half.
- **Load enough ink.** At 1 a carbon line is near black; a soluble line needs 2 to be as dark.

## Line first, or wash first

**Line, then washes** is the usual order for line and wash: pencil if wanted, the pen drawing, then the washes over it. Once a carbon line is down it does not move, so the washes need no care near it.

**Wash, then line.** On a dried wash the line is as crisp as on paper: `carbon_ink` at 1 over a burnt sienna wash of 0.74 dried at 0.038. Drawn into a wash that is still wet, the ink goes into the water and spreads with it. A line of `carbon_ink` at 1 across a burnt sienna wash, dried:

| Film where the line was drawn | Core of the line | Rows darker than halfway to the core | It reads as |
|---|---|---|---|
| 0.50 | 0.62 against the wash's 0.71 | 11 | A soft grey smudge |
| 0.29 | 0.56 (0.41 from ink at 2) | 8 (9) | A soft, feathered line |
| 0.12 | 0.34 | 4 | A soft line |
| 0.04 | 0.09 | 1 | A line with a slightly soft edge |
| Dry | 0.038 | 1 | A crisp line |

A feathered line in a wet passage (a branch in mist, a reflection) is drawn at film 0.12 to 0.3; read the film with `look --at` first. Everything that must stay crisp waits for `dry`.

## Width, pressure and pixels

- **Pressure sets the width, never the value.** A line is `width` × (0.15 + 0.85 × pressure) wide, and never under one pixel. Measured on a line of width 6 swelling from no pressure to full and back: 1.0, 2.1, 3.5, 4.8 and 5.9 pixels at pressure 0, 0.25, 0.5, 0.75 and 1, with its darkest value between 0.046 and 0.068 all along. For a paler line, lay less ink.
- **Whole pixels are crispest.** A line along a row or column on whole-pixel coordinates covers one pixel; drawn between pixel centres it is shared between two and reads paler on each (`actions.md`). A slanting line covers about one and a half pixels.
- **A stroke of the pen is one line.** It is counted like a brush stroke, so a hatched passage of forty lines is forty strokes; where a stroke budget is set at `new`, allow for them. `scripts/passbuilder.py` writes pen lines and fixative with `pen` and `fix`, and counts both against the budget.

## Hatching

Parallel one-pixel lines of `carbon_ink` at 1. The mean value is the tone the hatching gives at a distance; line to gap is how far a line stands from the paper beside it.

| Hatching | Pitch 2 | 3 | 4 | 6 | 8 |
|---|---|---|---|---|---|
| Along rows or columns | 0.50 | 0.67 | 0.73 | 0.82 | 0.85 |
| At 45 degrees | 0.22 | 0.48 | 0.61 | 0.71 | |
| Crossed, rows and columns | | | 0.56 | 0.70 | |

- Lines along rows or columns stay separate at every pitch (line to gap 0.93). At 45 degrees they stay separate from pitch 3 (0.86) and merge at pitch 2 into a flat dark of 0.22.
- **The pitch sets the tone, not the ink.** At pitch 4, ink at 2 gave 0.72 against 0.73 at 1. Lighter ink makes a softer hatching rather than a much paler one: at 0.5 and pitch 3 the mean was 0.73 with line to gap 0.77.
- To build a value scale in line, choose the pitch from the table, then cross the hatching where it must go darker.

## Fixative

`fix` locks paint that has settled under it, whether it settled before the fix or after: no later wash, scrub, blot or pour moves it. Paint still in the water flows as on bare paper (a charge into a wash on fixed paper spread 8.22 rows against 8.26 on bare), but locks as it settles, so a lift from a wash on fixed paper takes less. It is laid only where no film stands, so `dry` first. It takes 5 seconds, counts against the stroke budget and does not end the underdrawing, so it can be laid before the first paint.

Measured on 0.10.0, on a dried wash of burnt sienna, yellow ochre and a little cobalt blue (value 0.661, spread of values 0.018). From 0.11.0 a second wash lies over the first as a layer of its own and leaves only slight speckle unfixed (spread 0.027 against 0.023 fixed, `glazing-and-economy.md`); the lifts are unchanged:

| Then | Not fixed | Fixed |
|---|---|---|
| The same wash again at full water (0.95), dried | 0.474, spread 0.031: coarse speckle | 0.472, spread 0.019: clean |
| The same wash drained to 0.55 | 0.533, spread 0.020 | 0.532, spread 0.019 |
| Four passes of a stiff bright drained to 0.2, and a blot | 0.650 lifted to 0.799 | 0.650, untouched |
| On clean paper, fixed or not: an ultramarine wash, lifted at film 0.12 with a round 4 drained to 0.2, twice | 0.29 of the colour lifted | 0.17 |

When to fix:

- **Before a broad wash goes over finished work.** A correcting glaze, a second wash to deepen a passage, or a wet wash over drawn detail. The new wash's water lifts from unfixed paint beneath it, clear or coloured, and carries what it lifts; fixed, nothing beneath moves. Fixed, a full brush darkens the passage cleanly and by more than a drained one does from the same load (0.188 against 0.128 above).
- **Over soluble ink, or any paint, that must stay exactly as it is** while washes go over it.
- **After the lifting, not before.** Lift lights, soften edges and blot while the paper is unfixed. A wash laid on fixed paper still charges and blends, but gives up less to a lift (0.17 of the colour against 0.29), and once settled nothing comes off it.
- **Fix the whole passage that a full-water wash will cross.** The same wash at full water laid across a fixed band 40 pixels deep dried clean on the band (spread 0.017) and speckled on either side of it (0.032), so the edge of the fixative showed as a change of texture; the value differed by about 0.01 more than on a sheet fixed all over or not at all. Drained to 0.55, the wash dried alike on both sides (0.017 and 0.018).

Fixative cannot be seen and cannot be removed. Fixing the whole sheet (`{"action": "fix"}`) is the simple choice; fix along a path (`radius` up to 80) only when part of the sheet must stay liftable.

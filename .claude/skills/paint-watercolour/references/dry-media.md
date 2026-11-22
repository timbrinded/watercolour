# Dry media: coloured pencil, pastel and pencil over paint

Read this before drawing with `draw` (coloured pencil, pastel, crayon, chalk, charcoal) or with `pencil` once paint is on the sheet. Reach for dry media only when the brief asks for pencil, pastel, crayon or mixed media, or a style file calls for them: this skill's own manner is pure watercolour. Everything here needs 0.12.0 or later and was measured on it, on cold press, paper seed 3, sheets of 128 pixels. Values are the value view, where bare paper reads 0.96.

## How a dry mark behaves

- **It lies on top.** A mark lies over the paint and the marks already there, and under any paint laid later. A wash laid over it lies over it as it would over paper: a cobalt glaze over white pastel dried at 0.63, against 0.65 for the same glaze on paper. Pastel does not dissolve and wax does not resist the wash.
- **It takes only on dry paper.** Nothing takes where a film of water stands or the paper is fuller than damp (0.6 as `look --at` reads it), and nothing takes on masking fluid. Black pastel across a band of clear water and a band of masking fluid left both at paper (0.96) and read 0.09 on the dry paper between. `dry` before drawing.
- **It fixes the paint under it.** Paint under a mark can no longer be lifted or moved, so lift what must be lifted before drawing over it.
- **Water never moves it.** No wash, scrub, blot or tilt shifts a mark.
- **Pressure decides how deep into the grain it reaches.** Light pressure marks only the peaks of the grain, leaving the paper or the wash showing in the hollows; full pressure fills the hollows. At 0.3, black pastel darkened the peaks 7.4 times as much as the hollows; at 1 the hollows took almost as much as the peaks. The paper rises and falls within each pixel too, so a light touch covers part of most pixels it reaches: it reads as a broken veil, not as solid specks.
- **Pressure 0 lifts the stick.** One `draw` action can hold a whole patch of hatching, its lines joined by points at pressure 0. `scripts/passbuilder.py` writes the path with `hatch(lines, pressure)`.
- **Within one action it lays once.** Where one line crosses itself or its pieces overlap, it lays no more. A second action over the same place adds a coat.
- **Each `draw` is one stroke against the budget, and it does not end the underdrawing.** A patch of hatching is one stroke, so a drawn painting needs no larger budget than its number of patches and lines.
- The stick travels at 80 pixels per second, and the paint keeps drying while it does.

## The two media

| Medium | What it is | Character |
|---|---|---|
| `coloured_pencil` | wax or oil pencil, crayon | Translucent: a coat over a colour tints it, and lights over a dark build in coats. Holds a fine line. |
| `pastel` | soft pastel, chalk; with `ivory_black` it is charcoal | Chalky: it covers in one coat what coloured pencil covers in two, and is softer and broader. |

`pigments` is the stick's strength, more than 0 and at most 4 in all, from the painting's palette. Add `opaque_white` for tints and white, and name it in `--palette`. Deep colours and charcoal carry no white.

Patches of back-and-forth rows, radius 4 at a pitch of 6:

| | coloured pencil | pastel |
|---|---|---|
| `ivory_black` 4 at pressure 0.3 | 0.57 | 0.47 |
| at 0.6 | 0.16 | 0.11 |
| at 1 | 0.08 | 0.09 |
| `french_ultramarine` 1 at 0.7 | 0.72 | 0.56 |
| at 2 | 0.56 | 0.37 |
| at 4 | 0.35 | 0.24 |

## Lights over darks

`opaque_white` 2 at full pressure over a dried dark of 0.044:

| Coats | coloured pencil | pastel |
|---|---|---|
| 1 | 0.57 | 0.73 |
| 2 | 0.72 | 0.84 |
| 3 | 0.79 | 0.89 |

Over a middle value of 0.69 one coat reads 0.78 in coloured pencil and 0.83 in pastel. Light pastel is the strongest light that can go over a dark: `opaque_white` paint at 4.5 took a lighter dark (0.16) to 0.63 in one coat (`body-colour.md`). A light dry mark breaks on the grain like any other, so at pressure below about 0.6 the dark shows between its specks.

A later mark lies over an earlier one: blue pastel over white read 0.34 and white over blue 0.77.

## Lines and hatching

- **A fine line:** coloured pencil at radius 0.9 is unbroken at pressure 0.6 or more. At 0.4 about a tenth of its length breaks to paper on the grain, and at 0.3 a little over a quarter: use that for a dry, sparkling line (grass, a rim of light, fur).
- **Radius** is the half-width at full pressure, 0.5 to 20, narrowing to half as the stick lifts: about 0.6 to 1.2 for a pencil point, 1.5 to 3 for the point of a pastel, 5 to 15 for the side of the stick.
- **Hatching** in `coloured_pencil`, `ivory_black` 2, radius 0.9, pressure 0.6, lines along rows:

| Pitch (pixels) | 2 | 3 | 4 | 8 |
|---|---|---|---|---|
| Value | 0.48 | 0.56 | 0.66 | 0.81 |

Cross-hatch with a second action across the first. Give `"smooth": false` (the default for `draw`) so that the lifts between lines stay where they are put.

## The order

- **Washes first, then `dry`, then dry media.** A wash over a dry mark goes over it, as a glaze would, so a wash after the drawing tints the drawing as well.
- **Pastel:** dark to light, the lights and whites last.
- **Coloured pencil:** light coats first, building to the darkest last, then lights and whites over the darks.

## Pencil

`pencil` takes `darkness` (more than 0, at most 2.5), `radius` (0.5 to 10, default 0.9) and an optional pressure on each point: lifted, the line narrows to half and fades with the pressure. A point with no pressure is drawn at full pressure.

| Darkness | 0.3 | 0.6 (default) | 1.2 | 2.5 |
|---|---|---|---|---|
| The middle of a line at radius 0.9 | 0.86 | 0.75 | 0.55 | 0.18 |

A band of radius 3 at 2.5 averages 0.41 across its width: broad charcoal or black chalk. Lines drawn over one another build tone: a line at 0.8 read 0.67, and 0.48 once it was crossed and drawn again.

**Pencil after paint.** By default pencil is the underdrawing and is refused once paint is on the painting. Start the painting with `--pencil-after-paint` to draw pencil at any time, as in a sketchbook or an urban sketch. Drawn on dried paint it lies on the paint, under any paint laid later: a line on a cobalt wash of 0.71 read 0.52, and after white paint went over it 0.75 against 0.82 beside it. Drawn on paper it lies on the paper as before. It takes nowhere paint is still wet. `erase` is still refused once paint is on the painting; on the scrap sheet it removes pencil from bare paper only, never from under or on top of paint.

## What does not exist

- No smudging or blending with a finger or a stump.
- Pastel does not dissolve or darken under a wash, and wax does not resist one.
- No watercolour pencil: a stick that dissolves when water reaches it.
- Paint under a dry mark cannot be lifted, and pencil drawn on paint cannot be erased.
- The grain is the paper's: there is no sanded or toned pastel paper, so pastel reads as on cold press.

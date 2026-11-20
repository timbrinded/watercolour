# Supports and printed grounds

Read this when choosing what to paint on: `new --support cold_press|hot_press|rough` and `new --ground <image>`, both 0.10.0 or later. The support is fixed for the whole painting and its scrap sheet. Every other figure in this skill was measured on cold press, the default.

## Choosing the support

| Support | Choose it for | Not for |
|---|---|---|
| `cold_press` | Anything. It is the sheet the skill's strengths, film depths and recipes were measured on. | |
| `hot_press` | Line and wash, and fine detail, where the washes round the drawing should show no grain; flat and graded washes and skies; an even pencil line. | Dry-brush sparkle: a drained brush paints a tone mottled by the grain, not broken marks. |
| `rough` | Dry-brush sparkle, rock, bark, glitter on water, coarse granulation, a sheet whose relief shows. | Smooth skies and skin, which mottle. |

## What each changes

Measured on 128 pixel sheets when the supports were added:

| | `cold_press` | `hot_press` | `rough` |
|---|---|---|---|
| Dry brush, share of the stroke painted | 0.19 | 0.72 | 0.34 |
| Flat wash, variation between 8 pixel boxes | 0.080 | 0.038 | 0.168 |
| Pencil line, variation along it | 0.30 | 0.04 | 0.16 |

- **Hot press** holds less water and its film sinks in more slowly, so the shine lasts longer but the sheet dries sooner. Blooms and tide lines dry harder, and dried paint lifts more easily.
- **Rough** holds water in its pits, 1.8 times what its peaks hold, so a flat wash dries mottled. A dry brush paints the broad tops and leaves fewer, larger white pits than on cold press.
- `status` counts a hot-press film as shiny from 0.03, not 0.15. Act on the film's depth, as everywhere else.
- A pen line is even on every support: a one-pixel `carbon_ink` line at 1 read 0.047 on cold and hot press and 0.046 on rough, varying along its length by 1%, 0.2% and 2.5%.

## Film and drying times on each

Measured on 0.10.0, 128 pixel sheets, paper seed 3: rows of a round 8 (cobalt blue 0.5, rows 8 pixels apart, speed 280) and a mop wash (three mop 16 rows, ultramarine 0.6) laid once and twice. The film is read at the middle of the wash as the last row ends; then the seconds until it has thinned to each depth, and until the sheet is dry.

| Wash | Support | Film | To 0.3 | To 0.12 | To 0.06 | To 0.03 | Dry | Dried value |
|---|---|---|---|---|---|---|---|---|
| Round rows | `cold_press` | 0.76 | 43 s | 65 s | 73 s | 77 s | 261 s | 0.798 |
| | `hot_press` | 0.77 | 56 s | 81 s | 89 s | 93 s | 221 s | 0.802 |
| | `rough` | 0.77 | 43 s | 65 s | 72 s | 76 s | 260 s | 0.799 |
| Mop, once | `cold_press` | 0.92 | 55 s | 78 s | 87 s | 91 s | 283 s | 0.719 |
| | `hot_press` | 0.93 | 69 s | 94 s | 103 s | 107 s | 243 s | 0.724 |
| | `rough` | 0.92 | 55 s | 78 s | 86 s | 90 s | 282 s | 0.725 |
| Mop, twice | `cold_press` | 1.09 | 71 s | 97 s | 106 s | 111 s | 319 s | 0.665 |
| | `hot_press` | 1.10 | 86 s | 112 s | 122 s | 126 s | 270 s | 0.673 |
| | `rough` | 1.09 | 71 s | 97 s | 106 s | 110 s | 318 s | 0.674 |

- **On hot press the film takes 13 to 16 seconds longer** to thin to every depth, and the sheet is dry 40 to 50 seconds sooner. A `wait` on `film` takes care of the first; a wait given in seconds does not, so wait on the film.
- **On rough the timings are those of cold press** within two seconds.
- **The same load dries to the same value on all three**, within 0.01, so the strength bands carry over for washes. The film took 9 to 10 seconds to go from 0.10 to 0.03 on every support.

**Blooms keep their window.** Clear water from a round 8 held for 0.6 seconds in the mop wash above, then dried; centre and darkest ring as multiples of the wash around (the reading of the repository's behaviour test, not the table in `wet-in-wet.md`):

| Film when the water went in | `cold_press` | `hot_press` | `rough` |
|---|---|---|---|
| 0.02 to 0.03 | 0.62 / 1.18 | 0.48 / 1.27 | 0.45 / 1.10 |
| 0.05 to 0.06 | 0.60 / 1.39 | 0.47 / 1.50 | 0.45 / 1.14 |
| 0.09 to 0.10 | 0.59 / 1.34 | 0.47 / 1.42 | 0.44 / 1.19 |
| 0.17 to 0.18 | 0.58 / 1.19 | 0.48 / 1.19 | 0.43 / 1.06 |

- The depths `wet-in-wet.md` gives for a rimmed bloom, 0.06 to 0.10, hold on hot press, where the rim is darker and the centre paler. On rough the centre is as pale, but the rim stays faint at every depth.

**Lifting.** From a wet wash the share lifted is the same on all three: a round 4 drained to 0.2, twice along a line at film 0.12, took 0.28 to 0.29 of the colour. Dried paint gives up more on hot press and rough: four passes of a stiff `bright` drained to 0.2 and a blot raised a dried wash from 0.650 to 0.799 on cold press, from 0.654 to 0.825 on hot press and from 0.655 to 0.817 on rough.

## A printed ground

`--ground <image>` prints an image on the sheet before any paint. White leaves the support as it is; darker values multiply it, as ink does. The print lies under every wash and never lifts or moves.

- **Use it when the brief puts something on the sheet before the paint:** colour laid over a print or a printed line drawing (a hand-coloured engraving, a colouring of a printed outline), or a toned sheet. Print only what the brief asks for: a reference or tracing printed as a guide stays in the finished painting and cannot be taken out.
- **Give the sheet the image's proportions** with `--size` and `--height`; an image whose proportions differ by more than 2% is refused. The scrap sheet carries the middle of the print, at the painting's scale.
- **A wash darkens by the ground's tone.** Through the command, on a tan ground of value 0.66 beside plain paper: a cobalt blue stroke at 0.5 from a mop dried at 0.56 on the ground and 0.80 on the paper.
- **On a toned ground the lights are opaque white, and they do not reach paper.** Two coats of `opaque_white` at 4.5 brought the tan ground from 0.66 to 0.84, where the same coats on plain paper stayed at its 0.96. Plan the value range from 0.84 down.
- **The measuring scripts need a look of the sheet on a ground.** `measured_layers.py`, `crisp_layers.py` and `tonal_shapes.py` take the sheet to be white paper unless given `--look`, and then paint over the print as if it were not there. Give them a look even before the first paint.

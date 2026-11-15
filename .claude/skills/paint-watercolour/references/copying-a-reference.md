# Copying a reference: painting what the sheet still lacks

Read this when a painting must come close to a picture that already exists: a copy, a study after another painter, a likeness from a photograph. It replaces planning by eye with measuring, and it needs the scripts in `scripts/` beside this directory.

Everything here was worked out on one picture (a loose, high-contrast watercolour portrait of a boy carrying a white goat, copied on a 960 by 680 sheet) with harness 0.5.2 and one palette of six paints. The method should carry to other pictures; the numbers may not. Run the two charts in step 3 again on another version or palette before trusting them.

It was run once more, unchanged, on a landscape photograph (a city beyond vineyards under a clear sky, 768 by 594, harness 0.6.0, five other paints). Twelve mixes solved from samples dried within 0.04 of their sampled values on the first try. The thirteen stages took 8,300 strokes and 41 minutes and reached a value gap of 0.049 and a colour distance of 0.110, where a sheet painted by eye had scored 0.126 and 0.275 and one painted by hand from solved mixes 0.072 and 0.184. Edge agreement reached only 0.16, because a photograph has fine texture everywhere, and the clear sky came out worst of all (see the end of this file).

## What to expect

| Method | Value gap | Colour distance | Edge agreement |
|---|---|---|---|
| A blank sheet | 0.273 | 0.485 | |
| 250 strokes planned by hand from a gridded reference | 0.154 | 0.283 | 0.20 |
| Measured rows only, then drawing by hand (6,800 strokes, 48 minutes) | 0.042 | 0.083 | 0.35 |
| Rows for the masses, shape strokes for the rest, then drawing by hand (10,500 strokes, 70 minutes) | 0.029 | 0.060 | 0.49 |

The figures are from `scripts/value_difference.py`: mean difference in value over 16 pixel blocks, mean distance in colour, and how far the sheet's edges fall where the reference's do (1 is identical). The best sheet reads at once as the same picture and is still softer than the original at close range. This is the opposite of the stroke economy the rest of the skill teaches, and it costs an hour of computing. Use it when matching matters; paint from an idea, in 50 to 75 strokes, when it does not.

**Do not plan a copy stroke by stroke from the grid.** Two whole sheets and five face studies went that way. Each stroke read as a separate object with paper between it and the next, each carried one colour where the reference changes continuously, and with nothing measured between plan and paper the darks came out twice too dark and the pale passages were left white.

## The scripts

Run them with the Python the harness uses, because two of them read its pigment table: `uv run python` inside a clone, or `$(dirname "$(readlink -f "$(which watercolor)")")/python` for an installed tool. They need Pillow, NumPy and PyTorch, which that Python has.

| Script | What it gives |
|---|---|
| `reference_grid.py` | The reference scaled to the sheet, with a labelled grid, whole or as an enlarged crop. Read every coordinate off this. |
| `measure.py` | Mean colour and value at sheet coordinates in any image: the reference, a `look`, a study. |
| `preview_pass.py` | The strokes of a pass drawn over the reference at the width each will paint, clear water in cyan. |
| `compare.py` | A `look` beside the same region of the reference at one scale. |
| `value_difference.py` | The sheet against the reference: a map (red where it is too dark, blue where too light) and the three scores. |
| `measured_layers.py` | A pass of rows laying, with one brush, what the sheet still lacks. |
| `shape_strokes.py` | A pass of strokes that each run along one shape the sheet still lacks. |
| `copy_reference.py` | Runs the thirteen measured stages below, one after another. |
| `passbuilder.py` | Helpers for writing a pass in Python: `scaled`, `load`, `stroke`, `dab`, `rows`, `offset_path`, `translate`, `merge_stages`. |

## Step 1: grid and sample the reference

Give the sheet the reference's proportions and enough pixels that a face is 250 to 320 across. Grid the whole reference, then every passage that carries likeness at four to seven times its size:

```bash
python scripts/reference_grid.py reference.png grid_face.png --width 960 --height 680 --region 370,100,730,440 --step 20 --zoom 4
python scripts/measure.py reference.png 960 40,200,8 300,200,8 740,200,8
```

Sample twenty or thirty points and decide from the numbers where the darkest dark is, how large it is, and how much of the sheet is lighter than 0.85. Impressions were wrong three times here: a background that looked dark all over was lighter than middle grey over three quarters of the sheet; a blue that looked like French ultramarine was cobalt greyed with umber; and skin that the portrait guidance would paint at 0.05 to 0.15 needed washes of 2.6 and charges of 5 to 7, because it was brown skin in strong light and not pale skin in a high key.

Sample the reference's own white as well, and pass it as `--white r,g,b` to `copy_reference.py`, or to the two measuring scripts when they are run alone. A scan's paper is rarely the harness's paper, and without `--white` the scripts take pure white to be paper and tone the whole sheet to the scan's colour.

## Step 2: solve the colours

A thin layer of paint darkens each channel in proportion to the paint's absorption in that channel, and layers add. So work in absorbance, `-ln(channel / paper)`, and the ratio of a colour's three absorbances says which paints made it. The paints' absorptions are the first triple of each entry in `watercolor/pigments.py`.

Worked example: a deep background blue sampled at RGB 15, 29, 58 has absorbances in the ratio 1 : 0.76 : 0.50. French ultramarine is 1 : 1.00 : 0.07, so it cannot give that colour and dries violet beside it. Cobalt blue (1 : 0.56 : 0.19) with a fifth of its amount in burnt umber (1 : 2.1 : 2.8) gives 1 : 0.73 : 0.5, and painted it dried at 12, 27, 55.

Solve the four or five colours that cover most of the picture, and start the painting with `--palette` naming only the paints those mixes use, plus `opaque_white`. The measuring scripts solve a mix for every stroke from the paints you give them in `--paints`; the mixes you solve by hand are for the drawing at the end. The solving ignores scattering, so a paint that scatters strongly (cerulean blue, hansa yellow) may come out differently from what is predicted; check it on the swatch chart.

## Step 3: two charts

**A swatch chart.** One stroke of each solved mix on a small sheet, `dry`, then `measure.py` on each. It confirms the hues.

**A deposit chart.** One mix at three strengths, laid the way it will be laid in the painting. Measured here, a cobalt and umber blue:

| Method | Strength | Dried value |
|---|---|---|
| Rows of an `oval_wash` 22 on dry paper | 1.5 / 3.0 / 6.0 | 0.44 / 0.27 / 0.10 |
| The same, two layers | 1.5 twice / 3.0 twice | 0.24 / 0.08 |
| Charged from a brush at 0.6 into a wet wash of 0.8 | 4.0 / 6.0 / 8.0 | 0.40 / 0.29 / 0.23 |
| Dropped from a brush at 0.6 into clear water | 2.5 / 7.0 | 0.63 to 0.80 / 0.35 to 0.64, by how much is dropped |

- The darkest dark of a picture is one wash at strength 6 on dry paper, or 3 laid twice. It is not reached by charging.
- Paint dropped into clear water dries far lighter than the same paint on dry paper, and never reaches a dark.
- A single stroke lays less than a filled wash of the same mix: one stroke of a size 14 round at strength 5 dried no darker than rows of a wash brush at strength 3. `shape_strokes.py` allows for it (`--single 0.75`), and the next pass measures whatever is still short.
- A small brush lays less than a large one. Rows at strength 3 dried with 1.4 units of the mix's absorption from a mop of 14 or a round of 7, 0.95 from a round of 3.5 and 0.8 from a round of 1.6. Absorbance grows as about the 0.75 power of strength. These figures are built into the two measuring scripts. A second measurement, on 0.6.0, put a round of 7 nearer two thirds of a large wash brush, so a layer from a middling round may come up short; the next pass measures what it left.

Stroke widths, measured on dry paper, in multiples of `size`: a `round` is 1.35 at pressure 0.5 and 2.0 at pressure 0.9; a `mop` or `oval_wash` 1.8 and 2.1; a `flat` 2.1 at any pressure. The spot a round leaves at a single point has a radius of 0.6 times its `size` at pressure 0.5, 0.77 at 0.7 and 1.0 at full pressure.

## Step 4: the masses, in rows

`measured_layers.py` lays one layer with one brush.

1. **The gap** is the reference's absorbance minus the sheet's, clipped at zero. Paint can only darken, so where the sheet is already too dark nothing is done.
2. **A brush lays the least gap under its footprint.** Whatever a brush lays goes on its whole width, so the most it may lay without burying a light is the smallest gap anywhere beneath it. A broad brush therefore lays only the pale tone a whole region has in common, and each smaller brush finds more in the darker, narrower places. This rule reserves the whites with no mask and no drawing.
3. **Rows** cross the sheet at one angle, spaced at 0.7 of the stroke's width. A stroke runs for as long as the gap beneath it stays about the same, and a new stroke with a newly solved mix begins where it changes.
4. `dry`, `look`, and the next brush.

The first layer goes onto bare paper while its last row is still wet and dries as one soft variegated wash. Every later layer is a glaze on dry paper.

Rows get tone and not edges. Used alone, down to a size 2 round, they gave the right values with only a third of the edges in place: no stroke longer than a few brush widths and no plane with a clean edge. Use them for the masses only.

## Step 5: everything smaller, as shape strokes

`shape_strokes.py` takes the same gap and paints it as a hand paints a shape, with one stroke down its length.

1. The shapes of a pass are the places where the gap, lightly blurred, is at least a threshold.
2. Each shape is thinned to its centre line. One stroke runs down that line, its `size` the shape's greatest half width and its pressure at each point set so that the stroke is as wide as the shape is there.
3. Where a shape is wider than the largest brush allowed, further strokes run beside the first (`--peels`).
4. Strokes are laid tile by tile across the sheet, so a stroke and its neighbours go down within a second or two of each other.
5. Every stroke lays about the threshold's worth of tone. One pass is one flat glaze with a hard edge, and the next pass, at a higher threshold, is a smaller, darker glaze inside it.

The lids, the brows, the line of a mouth and the edge of a fringe appeared from this alone, before any drawing.

## The thirteen stages

```bash
watercolor new paintings/copy --prompt "..." --size 960 --height 680 --stroke-budget 12000 \
    --palette cobalt_blue,burnt_umber,yellow_ochre,cadmium_red,burnt_sienna,opaque_white
python scripts/copy_reference.py paintings/copy reference.png --sheet 960,680 \
    --paints cobalt_blue,burnt_umber,yellow_ochre,cadmium_red,burnt_sienna --white 244,246,240 \
    --out-of-washes burnt_umber --exclude 514,300,608,318 --bloom 884,176 --bloom 700,80
```

Start the painting with a stroke budget to match. The default of 150 is spent in the first stage, and a pass that would overrun the budget is refused. `--first` and `--last` run part of the sequence. The sizes are for a sheet about 960 pixels wide; on a much smaller or larger sheet, scale the sizes and blurs with it (this was not tried).

| Stage | Tool | Brush | Threshold | Lays |
|---|---|---|---|---|
| 1 | rows | `mop` 18, wet, then clear water touched in as the film thins to 0.18 | 0.05 | The first wash, with blooms |
| 2 | rows | `round` squirrel 14, at 35 degrees | 0.20 | Dark cores |
| 3 | rows | `round` squirrel 8, at 20 degrees | 0.08 | Middle masses |
| 4 | rows | `round` squirrel 8, at -25 degrees, gap smoothed over a stroke width | 0.12 | Middle masses, corrected |
| 5 | shapes | up to size 6, squirrel, blur 7 | 0.06 | The pale tints |
| 6 | shapes | up to size 5, blur 5 | 0.12 | First glaze |
| 7 | shapes | up to size 4, blur 4 | 0.25 | Second glaze |
| 8 | shapes | up to size 2.5, Kolinsky, blur 3 | 0.20 | Small shapes |
| 9 | shapes | up to size 2.5, Kolinsky, blur 2 | 0.45 | Their darks |
| 10 | shapes | up to size 2, Kolinsky, blur 2 | 0.30 | Correction |
| 11 | shapes | up to size 1.8, Kolinsky, blur 2 | 0.15 | The finest edges |
| 12 | shapes | up to size 5, squirrel, blur 6 | 0.06 | Pale tints again |
| 13 | shapes | up to size 1.8, Kolinsky, blur 2 | 0.15 | Finest edges again |

Score after each stage (step 7). Then draw by hand (step 6).

## Rules the failed sheets taught

- **Paint the pale tints.** What reads as white in a reference is often a tint: the warm cream of a lit cheek, the ochre in white fur. Any threshold of 0.10 or more skips them. Laying them (stages 5 and 12) was the largest single gain in value and colour, taking the value gap from 0.037 to 0.031. "Leave the lit side as paper" holds only for what measures as paper.
- **Never lay a broad wet wash over finished small work.** A corrective mop glaze re-wet the fine layers, blurred every feature and left the sheet sandy. Corrections after the fine layers are small glazes on dry paper, a size 8 round at the largest.
- **Keep granulating paint out of the deep washes** (`--out-of-washes`). Burnt umber in a mop wash gathered into dark specks. Burnt sienna greys cobalt blue with a fifteenth of the specks; at the same proportion it dries a little lighter and bluer, so solve the mix again with it.
- **Use each size twice.** The first use lays what that size may, a little under strength (gain 0.85 to 0.9); the second, at a higher threshold, touches only what is still well short. Gains under 1 on every layer with no second use left a quarter of the tone missing.
- **Smooth the gap for corrections.** A reference has grain, and the least gap under a footprint is the gap at its lightest speck, so broad even passages read low and stay pale. Smoothing the gap over a full stroke width (`--smoothing 1.0`) on the later, smaller layers found the missing middle tones (0.053 to 0.040 on one sheet). Keep it off small lights and features.
- **Let the rows wander** (`--wobble 0.12 --tolerance 0.5`), and change the row angle with every layer. Ruled strokes at one pressure dried as straight bars with round-ended dots, and layers all at one angle read as scan lines.
- **Match the blur to the brush** in shape strokes: about as many pixels as the largest size of the pass. With a blur of 3 at size 9, grain broke the broad shapes into hundreds of spots.
- **Do not use shape strokes for the masses.** A background that is one connected shape has a centre line like a river system. Rows cover it evenly.
- **Fence off what must stay as it is** (`--exclude`). Teeth, and any white too small for the footprint rule to protect, are toned to cream by the layers unless their rectangle is excluded from every stage. So is a signature or watermark, which the layers will otherwise copy as a smudge. Exclude the eyes and mouth from any layer laid after they are drawn.
- **Build each pass from a look taken after `dry`.** A wet sheet is not the colour it will dry to, and from 0.6.0 its picture also carries the light of the lamp on the water, which the scripts would read as paper.
- **Small strokes cost time.** A sixth to a third of a second of computing each, more with a larger palette: a layer of 2,000 took twelve minutes here. Confine the finest brush with `--region` where only part of the sheet needs it.

## Step 6: the hand

The measured stages do not draw, do not make a stroke longer than a shape is, do not choose which edges to lose, and cannot lighten. What is left is done by hand, on a dry sheet, in this order with a `dry` between each:

1. **Gestures.** The long strokes that are one movement of the arm: hair from crown to fringe, the length of a hanging ear, a contour restated against a finished background. One stroke each of three or four points, pressure 0.15, 0.8, 0.9, 0.15. Make them lighter than seems right (strength 1 to 1.7): on the sheet where everything else was within 0.04 of the reference, every red patch in the difference map was a hand stroke a third too wide and half as strong again as the original's.
2. **Small whites** that could not be reserved, in `opaque_white`, before the darks that will sit beside them.
3. **The drawing**: every crisp dark mark, measured from an enlargement and checked with `preview_pass.py`, which must show each within two pixels.
4. **Glints.**

`faces-and-detail.md` has the marks of a face.

## Step 7: score, and act on the largest fault

```bash
python scripts/value_difference.py paintings/copy/looks/<last>_painting_color.png reference.png difference.png --sheet 960,680
```

Score a blank sheet once for the baseline. Read the map before the picture: a large red area is a wash too strong or laid twice, a large blue area is paper left bare that the reference covers. Fix the largest area first, since one wrong wash outweighs every detail. Value gap says whether the tone is right and edge agreement whether the drawing is; a sheet scored 0.042 on the first with only 0.35 on the second and looked out of focus. Neither says whether a stroke is beautiful, so look at the sheet as well.

To rehearse a passage, give both measuring scripts `--origin x,y --crop W,H` and paint onto a sheet of that size. A 360 by 340 crop of a head took seven layers in about eight minutes.

## What this does not reach

- The copy is softer than the original. Broad single-stroke washes with one clean edge are built here from many small strokes, and it shows at close range.
- Blooms and dry-brush are faint on this engine, so back-runs and broken edges are only suggested.
- A large even gradation, such as a clear sky, is broken up. The rows give each stroke its own mix and lay it into the stroke before, and over a passage with no shapes in it that dries as patches with hard edges and back-runs, with hairlines of paper between some rows. A sky like that is better laid first by hand as one graded wash and left to dry, so that the stages find little lacking there (this follows from the landscape and was not tried).
- Two ideas were not tried: laying the second layer's darks into the first wash while it is wet (`--no-dry` on stage 1, a look, then stage 2 with `--water 0.6`), and measuring what laying strokes tile by tile contributes on its own.

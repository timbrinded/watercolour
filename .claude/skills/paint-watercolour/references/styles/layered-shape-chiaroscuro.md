# Style: layered-shape chiaroscuro (after Donna Stiles)

This is one manner among several, not the way portraits are painted. Read it only when the brief asks for it: it names
the style or Donna Stiles, or it asks for a close, dramatic, low-key portrait built from hard-edged tonal shapes. A
portrait brief that does not ask for it is painted in the skill's own manner, with `faces-and-detail.md`.

Where this file and the rest of the skill disagree, this file wins for this painting only.

It needs engine 0.8.0 or later, because the whites of the eyes are masked.

## What the style is

- **Crop.** Extremely close: the face fills the sheet, the eyes sit in the upper third, and the frame cuts the crown
  and the chin. A gesture (a hand at the face) carries the feeling.
- **Value.** A middle-to-low key. About a quarter of the sheet is below value 0.20 (hair, the deepest shadow), and
  half is below 0.60. Only 5 to 12% is bare paper: lit skin is a pale ochre tint, and pure paper is kept for
  catchlights, the white of an eye, a highlight on a nose or a nail.
- **Colour.** Three or four paints. About nine tenths of the coloured area is warm: yellow ochre for lit skin, burnt
  sienna with ochre for the half-tones, a near-neutral blue-black for the darks. One cool counterpoint, a greyed
  cobalt in the background.
- **Construction.** The skin is a mosaic of flat, irregular puddles laid wet on dry paper in four to six layers, each
  drying with a crisp, slightly darker rim. Planes are tonal shapes, not modelled gradients.
- **Edges.** Lost and found. A dark mass is hard against a lit plane and feathered elsewhere. The background is soft.
- **Marks.** Backruns inside skin planes, a run or two of paint (tear tracks, a dark mass spilling), heavy brow and
  lid marks that break into texture.
- **Focus.** The eyes are the most resolved passage and the only place where the darkest dark meets near-white.
  Nostrils and mouth are kept a tone lighter.

## Defaults this style overrides

| Default elsewhere in the skill | In this style |
|---|---|
| Leave 60 to 80% of a lit face bare paper; skin washes 0.05 to 0.15 | 5 to 12% bare paper; lit skin a pale ochre tint, half-tones a full sienna wash |
| Rims and seams inside a shadow are faults ("ribbon disease") | Rims on plane boundaries are the structure; they are still faults inside one plane |
| Paint from an idea in 50 to 75 strokes | The planes come from a measured value map: about 2,000 strokes of bands, then about 100 by hand |
| The measured copy (`copying-a-reference.md`) | Not for this style: it gets the values right and loses every hard edge |

## The scripts

All are in `scripts/`. Run them with the harness's Python: `uv run python` inside a clone, or
`$(dirname "$(readlink -f "$(which watercolor)")")/python` for an installed tool.

| Script | What it does |
|---|---|
| `style_target.py` | Turns the photograph into the picture this style would make of it |
| `posterise_target.py` | Shows the target cut into the bands, before any paint |
| `tonal_shapes.py` | Writes one band's pass: each shape a cut-and-flooded puddle |
| `paint_bands.sh` | Paints every band in order, each measured from the last dry look |
| `hand_marks.py` | Functions that return the hand stage's actions: eyes, brows, features, runs, background |
| `style_signature.py` | Measures a finished painting against the style's numbers |

They work beside the skill's own `reference_grid.py`, `preview_pass.py` and `measure.py`.

## Method

### 1. Choose the photograph

Choose a photograph lit by one soft directional source (window light, Rembrandt or split lighting) that turns the face
from light into shadow. Both eyes should be open and readable, ideally with a hand or other gesture, cropped close.

- **A licensed photograph or the user's own,** never one of her paintings.
- **Avoid cast-shadow patterns:** blinds, the shadow of a hand, dappled or striped sunlight. The bands paint them
  faithfully as stripes across the face, and they describe no form.
- **Avoid flat frontal light:** it leaves no chiaroscuro to design with.
- **Split light, half the face in shadow, makes the strongest picture.** But that half becomes one flat dark, and the
  hard-edge density falls to half of hers. A three-quarter light gives more edges.

### 2. Make the style target, not a copy of the photograph

The painter keeps the order of the photograph's tones but not their spread, and not their colours:

```bash
python scripts/style_target.py photo.jpg target.png --sheet 768,576 --crop x0,y0,x1,y1 --preview target_preview.png \
    --sheet-photo photo_sheet.png [--background-blur 14]
```

- **What it does.** It remaps the photograph's values onto this style's distribution, rank for rank. Each value takes
  the colour of the warm ramp at that value, or the greyed-cobalt mix where the photograph is cool.
- **`--sheet-photo`.** It writes the cropped photograph at sheet size. Give that file, not the original photograph, to
  `reference_grid.py` and `preview_pass.py`: they scale whatever image they get to the sheet.
- **The crop.** Cut the crown and the chin and put the eyes in the upper third. Where the gesture is a hand under the
  chin, keep the hand and cut below it rather than cutting the chin.
- **Detail behind the sitter.** Use `--background-blur 14` when there is any. A computer screen's blurred text was
  painted by the bands as horizontal grey bars.
- **Do not use `--cool-lift` where there is dark hair:** it turned the hair a muddy grey-green.

### 3. Choose the bands and look at them

```bash
python scripts/posterise_target.py target.png posterised.png --thresholds 0.88,0.76,0.62,0.48,0.32,0.20
```

Look at the posterised target before painting:

- The face must break into planes in the skin bands: socket, nose side, cheek plane, lip plane.
- If the face is one blob, move the skin thresholds into its own value range.

On every portrait trial these thresholds worked: skin bands at 0.88, 0.76, 0.62 and 0.48, then dark masses at 0.32
and 0.20.

### 4. Mask the whites of the eyes, before any paint

The bands tone the white of an eye like the skin round it, because in a photograph the white sits in the socket's
shadow. Opaque white laid back afterwards dries grey. So mask each eye's whole opening first, iris and all, as
`faces-and-detail.md` describes under "The white of the eye":

- Grid the photograph round each eye (`reference_grid.py` on the sheet photograph, zoom 4) and read the upper and
  lower lid edges, corner to corner.
- `eye_white_mask(upper, lower)` writes one tapered `mask` stroke along the opening's midline.
- Draw it over the sheet photograph with `preview_pass.py` (masks show in yellow) and check it fills the opening and
  stops short of the lash line.

Paint it as its own pass. The bands then go straight over it.

### 5. Paint the bands, dry between each, each measured from the last dry look

```bash
PYTHON=<harness python> scripts/paint_bands.sh paintings/<name> target.png 768,576 \
    yellow_ochre,burnt_sienna,cobalt_blue 1 \
    "0.88:--variegated --cap 0.3 --blur 2" "0.76:--blur 2" \
    "0.62:--blur 2 --backruns 2 --backrun-region <face box> --backrun-floor 0.48" \
    "0.48:--blur 2 --backruns 2 --backrun-region <face box> --backrun-floor 0.32" \
    "0.32:--variegated --percentile 35 --water 0.85 --max-strength 3.5" \
    "0.20:--variegated --percentile 40 --water 0.85 --max-strength 3.5"
```

Add `--exclude x0,y0,x1,y1` to every band for anything in the frame that must not be painted.

The bands took 2,100 to 2,600 strokes on a 768 by 576 sheet, and 3,400 strokes (43 minutes) on 768 by 736. Run
`paint_bands.sh` in the background, or a band at a time: its fifth argument is the index of the first band, and
each call finds the last dry look itself.

**How each skin shape is laid.** `tonal_shapes.py`:
1. cuts the shape's contour (and every hole's) with a size 3.5 squirrel round, set in by its radius
2. floods the inside with a size 8 round, a stripe at a time, so the cut is still wet when the flood meets it
3. softens the edge with a clean brush drained to 0.45 only where the target turns gently

**Why each setting:**

| Setting | Why |
|---|---|
| `--blur 2` on the skin bands | More small planes than blur 3: hard-edge density rose from 2.9% to 3.2%. |
| One variegated wet mass for the darks (0.32), and at most one more (0.20) | Nested floods stacked as five to seven parallel rims, a contour map, where she lays one mass. |
| `--percentile 35` to `40` | At 50 the mass over-darkened its lighter parts by 0.1. |
| `--max-strength 3.5` | Loads of 4.7 to 7.8 dried as paste speckle. |
| No burnt umber in the bands | In a deep squirrel flood it granulates into noise. Cobalt with burnt sienna gives the same blue-black. |
| `--backruns` with `--backrun-floor` set to the next threshold | A backrun only shows where its band is the last layer; a later band buries it. |
| `--variegated --cap 0.3` on the first band | One pale wet wash whose colour changes across the sheet. |

### 6. Measure the features and preview the hand stage

- Grid the sheet photograph (`reference_grid.py`) around the eyes, brows, nose, mouth and hand, and read coordinates
  off the grids.
- Then draw every hand pass over the sheet photograph with `preview_pass.py` before painting it. On the trials, the
  preview caught a brow 12 px high, the edge of a cheek against a hand 10 px inside the cheek, an iris 10 px off,
  runs laid over black hair (where they cannot show), and a background bed that would have painted stripes.
- After the bands are down, look again. Use `measure.py` on the last look at each planned feature. A feature already
  within 0.05 of the target's value there (a nasolabial fold already drawn as a dark slash, a nostril) gets no hand
  stroke on top.

### 7. The hand stage, on the dry sheet, with `dry` between passes

Use `hand_marks.py`. In this order:

1. **`cool_background(target)`.** A clear-water bed over the cool background with greyed cobalt charged in. The bands
   alone dry it neutral grey. Skip it if the background is dark.
2. **The whites.**
   - `{"action": "unmask"}` rubs the eye masks away: a clean almond of paper in each eye.
   - `catchlight_masks([(x, y), ...])` masks each catchlight, radius 2.6 (a smaller dot greys), inside the opening and clear of the lid.
   - Shade each white:
     - **A lit eye:** `shade_lit_white(shadow_path, soften_path)`, a cool grey under the upper lid, softened downward.
     - **An eye in shadow** (the look's value round it under about 0.3): `shade_shadowed_white(path)`, the whole
       white at a middle value.
   - `DRY`.
3. **Irises and brows.**
   - **The visible part of each iris:** `visible_iris(x0, x1, y, half_height)`, a short level stroke of a round
     sized to the opening's half-height at the iris. The mix is `BROWN_IRIS`, or `GREY_GREEN_IRIS` with
     `mix=GREY_GREEN_IRIS`. A full disc of the iris's own radius spilt onto the lower lid.
   - **Each brow:** `brow(path)`, a heavy fringed line (core size 4.5, strength 2.2; fringe size 6.5, strength 5.0,
     angle 50). For a pale (silver) brow, halve both strengths.
     - The blind trial found the lighter `fringed_line(path, 3.4, 2.6, 5.5, 4.2)` dried as a thin line with almost
       no fringe.
     - Dry-brush alone left only specks, and a smooth stroke dried like eyeliner.
   - `DRY`.
   - **The lid's shadow and the limbal ring:** `lid_shadow_over_iris(path)` across the iris's top third, then
     `limbal_arcs(cx, cy, radius, top, bottom)` at its sides. `DRY`.
4. **Lids, pupils and lashes.**
   - `smoky_lid(lash_path)` for each eye, then `DRY`.
   - Twice, with a `DRY` after each: `pupil` for each eye, and a short `fringed_line` over each iris only.
   - `lower_lid(path)`, then `DRY`.
   - `{"action": "unmask"}` rubs the catchlight masks away.

   Rejected alternatives for the lid:
   - A damp brush softening the lid left a graphic arc.
   - A clear-water bed under it dried as a second stripe.
   - Short lash flicks across the line read as stitches.
5. **Features as `charged_puddle`.** The mixes that worked:

   | Feature | Puddle | Charged along its shadow side |
   |---|---|---|
   | Upper lip | burnt sienna 0.6, burnt umber 0.15 | `WARM_DARK` 1.6 |
   | Lower lip | burnt sienna 0.4, yellow ochre 0.1 | burnt sienna 0.9, burnt umber 0.3 |
   | Cast shadow under the nose | `WARM_DARK` 1.5 | (none) |

   Then, once they are dry:
   - the mouth's parting line and the nostril as single strokes of `WARM_DARK` at about 2.0
   - the edge where cheek meets hand as one crisp `WARM_DARK` stroke

   Flat one-value lips read as stickers. A nose shadow laid as a puddle still read as a sticker in the blind trial;
   lay it smaller than the photograph's, or not at all if the bands already carry it.
6. **`tear(pool, runs)`, optional.** It is her mark, but it adds a mood: one per picture unless the sitter is
   crying.
   - A tear goes under an eye, crossing pale cheek.
   - A dark mass spilling into a pale background takes a blue-black pool and runs.
   - Runs never go over near-black.
7. **Lit skin.** The bands leave the brightest plane as one bare-paper shape. Her lit skin is a pale ochre tint with
   paper only at the highlights. A tint pass at strength 0.25 (dried value 0.91) over the lit plane read better on the
   blind trial. But with paper kept only where the target was above 0.95, bare paper fell to 4.2%, below her 8.7%.
   Keep paper wherever the target is above about 0.93 (untested between those two thresholds).

## Runs: what the engine does (17 trials on 0.7.1)

| Setup on dry paper (pool film 1.2 to 2) | Result |
|---|---|
| `tilt` y 0.15 to 0.24, 60 s | A comb of 3 to 8 runs, 8 to 30 px; 180 s adds nothing, the tips dry |
| A pale wash at water 0.82, tilt 0.20 | 8 runs of 19 to 51 px, square-ended |
| Tilt 0.26 or more | The whole lower edge slides as one lobe; no runs |
| Damp or wet paper below the pool | A broad spread, no runs |
| A clear-water track below | The track dries before the paint arrives |

So a run longer than about 30 px is painted (`run`), and the tilt at the end of `tear` adds a short physical comb along
the pool's edge.

## Validation

```bash
python scripts/style_signature.py paintings/<name>/painting.png
```

Her painting measured: p05 0.041, deep darks 25.3%, paper 8.7%, warm 89%, hard-edge density 4.2%, 39 shapes per
10⁵ px.

| Measure | Target |
|---|---|
| p05 | under 0.06 |
| Share below 0.20 | 20 to 30% |
| Bare paper | 5 to 12% |
| Warm share of coloured pixels | over 80% |
| Hard-edge density | 3.5% or more |
| Shapes per 10⁵ px | 30 or more |

Then look at an enlargement: separate rimmed puddles, no parallel rims in the darks, eyes the only place of peak
contrast.

## Trials and what is still short

| Trial | Subject | Strokes | Deep darks | Paper | Hard edges | Shapes | Read |
|---|---|---|---|---|---|---|---|
| 1 | Woman, cast-shadow bars (wrong photo) | 2,230 | 22.7% | 7.5% | 2.4% | 30 | Posterised illustration: contour rings, sticker lips |
| 2 | Woman, window light, hand at cheek | 2,766 | 26.6% | 9.5% | 2.9% | 33 | Portrait reads; dark masses whole; smoky socket |
| 3 | Same, revised hand stage, blur 2 | 2,809 | 26.6% | 9.6% | 3.2% | 36 | Softer lids, heavier brows, cool counterpoint; eyes without whites |
| 4 | Older man, split light | 2,302 | 26.4% | 16.3% | 1.8% | 36 | Strongest picture; lit half a dense mosaic; bare-paper background |
| 5 | Woman, three-quarter, hand at chin; **blind** (a fresh agent with only this file and the scripts) | 3,643 | 24.7% | 4.2% | 2.3% | 35 | Same family as 2 to 4: rimmed mosaic, an eye that reads, a tear; flat hair; lozenge lips and nose shadow |
| 6 | Trial 3's photograph and bands, eye whites masked (0.8.0) | 2,819 | 26.5% | 9.9% | 3.45% | 38 | Both eyes have whites and the gaze reads; the lit eye's white is stark, ringed by a heavy lid |

The blind trial is the test of this file. An agent with nothing else reached the same result as the trials it was
written from, with the same faults. So the method is written down, and what is still short is short in the method
itself. Its list of unclear points was folded into the steps above.

Trial 6 repainted trial 3 from this file with the eye whites masked. The white of the lit eye dried at 0.93 where
trial 3's dried at 0.56, the shaded eye's at 0.62 to 0.81 where trial 3's was 0.37 to 0.65, and both catchlights
(radius 2.6) survived. The rest of the signature barely moved (bare paper 9.6% to 9.9%, hard edges 3.2% to
3.45%, shapes 36 to 38 per 10⁵ px): masking changes the eyes and nothing else.

Still short of her:
- **Lids.** `smoky_lid` still dries as a crisp, even arc; the core does not bleed soft enough. Above a masked white
  it is starker still: a bright almond ringed in near-black, where her whites are small and sit in the socket's tone.
- **Peak contrast.** It also falls outside the eyes, where a light forehead meets a dark background or under the
  chin. Nothing in the method holds it to the eyes.
- **A dark photograph.** With 60% of the crop below 0.2, the remap spreads the black into streaky mid-tones.
- **Hard-edge density:** best 3.45% (trial 6) against 4.2%. Her edges are spread over the whole sheet, including inside the
  darks.
- **Darks:** hers carry warm modulation inside; these trials dry them as one flat mass.
- **Warm share:** 97 to 100%, against her 89%. The cool counterpoint is small unless the background is large and
  light.
- **Drawing:** her features are drawn with more variety of mark than a fixed recipe gives.
- **Bare paper:** a light background left as paper (trial 4) pushes the share above 12%. Tint it with the cool bed.

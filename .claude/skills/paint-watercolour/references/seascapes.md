# Seascapes: a sea that is the subject, after Turner

Read this before painting a sea in weather: a storm, a wreck, boats in a gale, surf at night. It is a study of six sea pictures by J. M. W. Turner and of how to get their effects from the harness, worked out by copying *The Shipwreck* (1805). `water.md` is about copying a photograph of surf; this file is about making a sea picture hold together, and about laying light over dark, which that file does not reach.

It needs 0.12.0 or later. The trials were on cold press, on a 1024 by 736 sheet and 400 by 300 crops of it at the same scale. Values are the value view, where paper reads 0.96.

## What the pictures have in common

Measured on reproductions of six pictures, each scaled to 640 pixels:

| Picture | Mean value | Median | Lighter than 0.5 | Lighter than 0.7 | Lightest 7% centred at (x, y) | Hard edges | Mean chroma |
|---|---|---|---|---|---|---|---|
| The Shipwreck, 1805 (the copy's reference) | 0.21 | 0.15 | 7% | 2.5% | 0.56, 0.63 | 4.7% | 0.06 |
| The Shipwreck, a gallery photograph | 0.20 | 0.19 | 4% | 0% | 0.57, 0.62 | 2.5% | 0.17 |
| Calais Pier, 1803 | 0.50 | 0.52 | 53% | 22% | 0.41, 0.56 | 14% | 0.20 |
| Dutch Boats in a Gale, 1801 | 0.34 | 0.30 | 26% | 2.9% | 0.65, 0.47 | 0.9% | 0.10 |
| Fishermen at Sea, 1796 | 0.12 | 0.07 | 3% | 0.3% | 0.40, 0.42 | 0.9% | 0.04 |
| Snow Storm: Steam-Boat off a Harbour's Mouth, 1842 | 0.47 | 0.48 | 46% | 7% | 0.69, 0.50 | 0.3% | 0.08 |

"Hard edges" is the share of pixels where the value changes by more than 0.15 in one pixel. "Chroma" is the mean difference between the strongest and weakest channel.

- **The sea is the picture.** The boats are small, tilted, cut off by waves and half lost in them. Nothing is an object set in front of a backdrop. A ship drawn whole and upright on a tidy wave is an illustration of a ship, however well it is modelled.
- **A low key with very little light.** Four of the six have a median under 0.31, and in all but Calais Pier under a twelfth of the picture is lighter than 0.7. The Shipwreck's darks sit at 0.05 to 0.15 and its foam at 0.4 to 0.6: what reads as white foam is a middle value made bright by the dark round it.
- **One pool of light.** The lightest passages lie together, off centre, and the corners fall away dark. In The Shipwreck the light is the foam in the middle of the sea, lighter than any sky above it.
- **A warm light against the darkest dark.** One sail, the largest flat light in the picture, is set against the blackest sky. A smaller sail repeats it further off.
- **Almost no colour.** The Shipwreck is a warm black and one ochre. Its darks are near neutral (absorbance about 0.94 : 0.91 : 1.00, red to blue) and every light is the same ochre (0.23 : 0.43 : 1.00). Ivory black with a little hansa yellow gives the olive of the water; no green or blue paint is in it.
- **Few hard edges, spent on purpose.** Under 5% of the picture in five of the six. They belong to the sail, the spar and the boat. The water has none: its lights are dragged, broken strokes that follow the surface of each wave, with the dark showing through them.
- **Diagonals.** Spar, sail, wave backs and the line of the boats all lean. The horizon is high and nearly lost.

## Why reserving the foam fails

The obvious way to paint foam in watercolour is to keep it as paper: mask it, wash the sea over it, rub the mask away. On three sheets that gave white shapes with cut edges lying on a flat sea, and every one read as a diagram. The foam of these pictures is not a shape. It is light laid over dark in strokes that follow the form, thick in one place and scraped thin in the next.

So the order is the oil painter's: dark first, light over it. The harness has two ways to lay light over dark, and the sea needs both:

- **Body colour** (`opaque_white` with `yellow_ochre`, from 0.11.0): a smooth, half-covering ribbon. It is the body of the foam.
- **A dry stick** (pastel or coloured pencil, from 0.12.0): at a light touch it catches the tops of the grain and leaves the dark between them. It is the broken light on top.

`scripts/scumble_lights.py` lays either from a reference: wherever the dried sheet is darker than the reference it draws strokes along the reference's own streaks, each as strong as the light missing under it.

## The method

1. **The dark ground, as measured washes.** The row stages of `copy_reference.py` with `--even-passages`, stopped before the shape strokes:

   ```bash
   python scripts/copy_reference.py paintings/sea reference.png --sheet 1024,736 --even-passages --last 5 \
       --paints ivory_black,burnt_umber,burnt_sienna,hansa_yellow --out-of-washes burnt_umber
   ```

   It dries as one soft olive-black mass with the large lights (a sail) reserved, darker than the reference wherever the foam lies. That is what is wanted: a ground for the lights. Do not go on to the shape strokes over the water; they cut it into hard-edged patches.
2. **The darks of the boats, as measured shapes.** `shape_strokes.py` with `--region` round each boat, three passes (threshold 0.12 widest 5 blur 5; 0.25, 4, 4; 0.2, 2.5, 3), each from a look of the dried sheet. The hulls and the dark heads come from the reference, not from the hand.
3. **The body of the lights, in body colour.** Two passes, each from a look of the dried sheet:

   ```bash
   python scripts/scumble_lights.py reference.png body.json --sheet 1024,736 --look <look> --medium body_colour \
       --radius 5 --threshold 0.05 --longest 120 --stick opaque_white:1.0,yellow_ochre:1.1,burnt_sienna:0.08 --top 0.6
   # then --radius 3 --threshold 0.07 --longest 90 --stick opaque_white:1.0,yellow_ochre:0.7 --top 0.68
   ```

   Covering white picks up some of the dark beneath and dries grey, so the mix carries as much ochre as white. `--top` is the value a full coat of that mix dries at; set it too high and every stroke comes out too thin.
4. **A warm glaze over the lights.** One measured layer of a size 8 round in transparent paint, which tints the body colour and joins it to the dark:

   ```bash
   python scripts/measured_layers.py reference.png glaze.json --sheet 1024,736 --look <look> --brush round --size 8 \
       --hair squirrel --paints hansa_yellow,burnt_sienna,ivory_black --gain 0.7 --least 0.05 --smoothing 1.0 --wobble 0.12 --tolerance 0.5
   ```

5. **The broken light, with dry sticks.** Pastel at `--radius 2.5`, then coloured pencil along the reference's bright threads:

   ```bash
   python scripts/scumble_lights.py reference.png top.json --sheet 1024,736 --look <look> --medium pastel \
       --radius 2.5 --threshold 0.06 --longest 80 --stick opaque_white:1.3,yellow_ochre:0.7 --top 0.7
   python scripts/scumble_lights.py reference.png threads.json --sheet 1024,736 --look <look> --medium coloured_pencil \
       --radius 1 --threshold 0.06 --longest 140 --stick opaque_white:1.3,yellow_ochre:0.6 --top 0.8 \
       --ridges 0.05 --persist 3 --shortest 14 --press 0.45
   ```

6. **The hand, and very little of it.** The spar, two ropes, a mast and a red cap or two, on the dry sheet from coordinates read off `reference_grid.py` and checked with `preview_pass.py`.

**Keep the lights to the sea.** Give every `scumble_lights.py` pass `--within` an image that is white over the water and black over the sky and the sail. In a sky the reference has no streaks to follow, so the strokes wander: on the first full sheet they dried as pale worms across the clouds. The sky is the soft wash of step 1 and nothing more. The sail is the wash's reserve; a dry stick over it speckles it.

## What each step did, on a crop

A 400 by 300 crop of the boat and the foam beside it, at the full sheet's scale. Scores are from `value_difference.py`.

| After | Value gap | Colour distance | What the sheet looked like |
|---|---|---|---|
| The washes | 0.082 | 0.144 | A soft dark mass, the sail reserved; no foam |
| Pastel only, three passes (the first trial) | 0.042 to 0.045 | 0.091 to 0.098 | Light in the right places, but as cold white flecks: the grain, not the wave, set their shape |
| Body colour at radius 5 (the second trial) | 0.049 | 0.093 | Ribbons of light running along the waves |
| Body colour at radius 2.5 | 0.050 | 0.097 | Finer ribbons between them |
| A measured glaze of a size 8 round | 0.055 | 0.107 | Softer and more of a piece; a little darker than it should be |
| Pastel and pencil threads on top | 0.056 | 0.109 | Sparse broken lights and thin bright lines |

- **The score does not see what matters here.** Pastel alone scored best and looked worst: flecks with no direction. Body colour dragged along the form scored a little lower and looked like water. Judge the sheet enlarged.
- **Coloured-pencil threads laid everywhere made it worse** (0.048 to 0.058): 3,190 strokes two pixels long. With `--ridges`, `--persist` and `--shortest` they are a few hundred long lines on the crests.
- **A full-strength glaze darkens the lights it is meant to warm.** Keep its gain under 1 and its paints mostly yellow.

## The full sheet

*The Shipwreck* on a 1024 by 736 sheet, with eight paints named (`ivory_black`, `burnt_umber`, `burnt_sienna`, `hansa_yellow`, `yellow_ochre`, `opaque_white`, `cadmium_red`, `carbon_ink`). A blank sheet scores 0.750 and 1.309.

| After | Strokes | Value gap | Colour distance |
|---|---|---|---|
| The washes (five row stages) | 1,022 | 0.059 | 0.103 |
| The boats' darks (nine passes of shape strokes) | 1,091 | 0.058 | 0.102 |
| Body colour at radius 5, on the sea only | 1,000 | 0.039 | 0.071 |
| Body colour at radius 3 | 1,682 | 0.038 | 0.069 |
| The glaze | 202 | 0.039 | 0.070 |
| Pastel at radius 2.5 (1,356 strokes in 57 actions) | 57 | 0.039 | 0.070 |
| Pencil threads (831 strokes in 35 actions) | 35 | 0.041 | 0.074 |
| The hand: spar, two ropes, a mast, three red caps | 7 | 0.041 | 0.074 |

Finished: 0.041 and 0.074, with an edge agreement of 0.50, in 5,098 strokes of the budget and about 95 minutes. The first sheet, with the lights laid over the sky as well, reached 0.031 and 0.058 before it was spoiled; the difference is the sky's own faint lights, which this sheet leaves to the wash.

What it reads as: the dark sea and sky, the one pool of broken light, the sail against black, the foam running with the waves. What it does not have: the sail's cut edge (the wash leaves it soft and blunt), the figures (the boats are dark jumbles with a red note), and Turner's warmth in the foam.

- **The second body-colour pass is the slow one**: 1,682 strokes for 0.001. On another sheet, raise its threshold or leave it out.
- **The boats' darks hardly move the score** (0.059 to 0.058) and are what makes the boats sit in the water.

## Rules the first full sheet taught

The measured sequence brought the first sheet to a value gap of 0.031 and it read as the picture. Three corrections by hand then spoiled it (0.065):

- **A dark glaze over the sky to sink the stray scumbles** (ivory black 1.1 in rows of a mop) dried as one flat black slab with a ruled lower edge. A sky that is already at its value takes no more paint. Keep the scumbles out of it instead.
- **A warm glaze over the sail in six rows** dried as six stripes: the rows did not overlap. A glaze is laid as a wash (rows a radius apart, laid wet together) or not at all.
- **Hulls and figures drawn in pen and charcoal** read as marks on top of the painting. The boats of these pictures are part of the water; measure them (step 2).

So: when the measured sheet reads, stop. What it still lacks is rarely worth the risk of a correction.

## How much light each stroke lays

Pale pastel (`opaque_white` 1.7, `yellow_ochre` 0.3, radius 3, rows 5 pixels apart) over a dried wash:

| Pressure | 0.12 | 0.16 | 0.2 | 0.25 | 0.3 | 0.4 | 0.5 | 0.7 | 1.0 |
|---|---|---|---|---|---|---|---|---|---|
| Over a dark of 0.065, one coat | 0.17 | 0.24 | 0.27 | 0.36 | 0.38 | 0.49 | 0.56 | 0.68 | 0.69 |
| The same, two coats | 0.26 | 0.32 | 0.37 | 0.40 | 0.43 | 0.64 | 0.71 | 0.78 | 0.79 |
| Over a middle value of 0.32, one coat | 0.39 | 0.42 | 0.43 | 0.49 | 0.50 | 0.57 | 0.62 | 0.71 | 0.72 |
| The same, two coats | 0.44 | 0.47 | 0.50 | 0.52 | 0.54 | 0.68 | 0.73 | 0.79 | 0.80 |

So pressure is a continuous control from a breath of light to a covering coat, and no dry light is lighter than about 0.8. A light that must be lighter than that is paper, kept by the first wash.

## What this does not reach

- The lights are cooler and greyer than Turner's. Covering white takes up the dark it crosses, and the glaze that warms it also darkens it.
- Body-colour strokes have even edges. Turner's paint is thick in one place and scraped thin in the next within one stroke; nothing here varies a stroke's cover along its length except its width.
- The scripts copy a picture that exists. They do not compose one. Painting a sea from an idea still means deciding the pool of light, the one warm light and the diagonals first; the six pictures above are the pattern.
- Figures, rigging and the drawing of the boat are by hand, and are as good as the hand.

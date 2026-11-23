# Seascapes: a sea that is the subject, after Turner

Read this before painting a sea in weather: a storm, a wreck, boats in a gale, surf at night. It is a study of six sea pictures by J. M. W. Turner and of how to get their effects from the harness, worked out by copying *The Shipwreck* (1805) on four sheets. `water.md` is about copying a photograph of surf; this file is about making a sea picture hold together: a low key, a sea of middle tones, one hard-edged light, and light laid over dark.

It needs 0.12.0 or later. The trials were on cold press, on 1024 by 736 sheets and 400 by 300 crops at the same scale. Values are the value view, where paper reads 0.96.

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
- **The water is middle tone, not dark.** A wave's face in The Shipwreck is one continuous olive mass at 0.35 to 0.45, with fine lighter streaks and fine darker lines running down it. Only the troughs and the far sea are black.
- **One pool of light.** The lightest passages lie together, off centre, and the corners fall away dark. In The Shipwreck the light is the foam in the middle of the sea, lighter than any sky above it.
- **A warm light against the darkest dark.** One sail, the largest flat light in the picture and the one shape with a cut edge all round, is set against the blackest sky. A smaller sail repeats it further off.
- **Almost no colour.** The Shipwreck is a warm black and one ochre. Its darks are near neutral (absorbance about 0.94 : 0.91 : 1.00, red to blue) and every light is the same ochre (0.23 : 0.43 : 1.00). Ivory black with a little hansa yellow gives the olive of the water; no green or blue paint is in it.
- **Few hard edges, spent on purpose.** Under 5% of the picture in five of the six. They belong to the sail, the spar and the boat. The water has none.
- **Diagonals.** Spar, sail, wave backs and the line of the boats all lean. The horizon is high and nearly lost.

## Three ways that fail

- **Foam kept as paper.** Mask the foam, wash the sea over it, rub the mask away: on three sheets that gave white shapes with cut edges lying on a flat sea, and every one read as a diagram. The foam of these pictures is not a shape.
- **A dark ground with every light laid over it.** The first study of The Shipwreck laid the row stages of `copy_reference.py --even-passages` from the picture itself and then dragged body colour over them. At arm's length it read as the picture. Close up the wave faces were flat cream ribbons on black, two values where the picture has a mass of middle tone. The cause is the wet wash: laid from the picture, its darks run into the middle tones beside them. On a crop the passages the picture has above 0.5 dried at 0.27, its middle tones at 0.25 and its darks at 0.15, one tone for all three. Every light then has to be covering paint, and thin white over black dries cool and grey (red less blue 0.137 where the picture has 0.179).
- **Fixative under the body colour.** It was tried in case the white was taking up the dark beneath it. It changed nothing (the lights at 0.445 fixed against 0.438 unfixed): the grey is the white's own thinness, not the ground.

## The method: a light ground, the darks in dry layers, the lights last

The wet washes are laid from a reference in which every light has been spread into its surround, so they dry no darker anywhere than the lightest thing near by. The darks are then built over them on dry paper, where they stay where they are put. The sail is tinted first and kept under masking fluid until the darks are done. Covering paint is left for the fine lights.

1. **The references.** `scripts/wash_references.py` writes four images from the picture and one point on the sail:

   ```bash
   python scripts/wash_references.py reference.png plate --sheet 1024,736 --seed 660,320 --warmer-than 0.07
   ```

   `plate/shape.png` is the sail's silhouette, `tint.png` its colour carried past its edge on white, `filled.png` the picture with the sail filled in by the sky round it, and `ground.png` the filled picture with every light spread 7 pixels into its surround.
2. **The sail: its tint, then fluid.** Three measured layers of a size 10 round from `tint.png` on the bare paper, each from a look of the dried sheet; then `mask_lights.py plate/shape.png` lays fluid on the silhouette.

   ```bash
   python scripts/measured_layers.py plate/tint.png tint.json --sheet 1024,736 --look <look> --brush round --hair squirrel \
       --size 10 --paints yellow_ochre,burnt_sienna,burnt_umber --gain 0.9 --least 0.03 --smoothing 0.5 --wobble 0.12 --tolerance 0.5
   python scripts/mask_lights.py plate/shape.png mask.json --sheet 1024,736
   ```

   The tint runs under the fluid's edge everywhere, so the sail comes out with no rim of white paper and no ring of pooled paint, and every wash after it dries against the rubber with a cut edge. Painting the sail after the fluid comes off, in strokes kept inside the silhouette, left both: a hairline of paper along the edge and a burnt ring inside it.
3. **The ground, wet.** Stages 1 and 2 of `copy_reference.py --even-passages`, from `ground.png`:

   ```bash
   python scripts/copy_reference.py paintings/sea plate/ground.png --sheet 1024,736 --even-passages --last 2 \
       --paints ivory_black,burnt_umber,burnt_sienna,hansa_yellow --out-of-washes burnt_umber
   ```

   It dries as a pale sea under a dark sky, with nothing drawn.
4. **The darks, in rows on dry paper.** Stages 3 to 5 from `filled.png` (`--first 3 --last 5`), then the size 8 round twice more across them:

   ```bash
   python scripts/measured_layers.py plate/filled.png rows.json --sheet 1024,736 --look <look> --brush round --hair squirrel \
       --size 8 --angle 60 --paints ivory_black,burnt_umber,burnt_sienna,hansa_yellow --gain 1.0 --least 0.08 --smoothing 0.5 --wobble 0.12 --tolerance 0.5
   # and again with --angle -60
   ```

   Each row lays only what its whole footprint lacks, so the wave faces keep their middle tone and the troughs and the sky go dark round them.
5. **The darks, as shapes.** Stages 6 to 8 from `filled.png` (`--first 6 --last 8`): the troughs between the foam, the hulls, the dark heads. Then one finer pass of `shape_strokes.py` (`--threshold 0.2 --widest 2.5 --blur 3`) with `--region` round each boat.
6. **The fluid off.** `[{"action": "unmask"}]` on the dry sheet.
7. **The lights, and few of them.** `scumble_lights.py` lays light wherever the dried sheet is still darker than the picture, in strokes that follow the picture's own streaks. Each pass is built from a look of the dried sheet:

   ```bash
   # the streaks of the water, in body colour
   python scripts/scumble_lights.py reference.png body.json --sheet 1024,736 --look <look> --medium body_colour \
       --radius 3 --threshold 0.08 --longest 120 --stick opaque_white:1.0,yellow_ochre:0.7 --top 0.68 --within water.png
   # the lights of the boats and figures, as dabs
   python scripts/scumble_lights.py reference.png dabs.json ... --radius 2.5 --threshold 0.08 --longest 14 --within boats.png
   # broken light, with pastel; then the brightest threads, with coloured pencil
   python scripts/scumble_lights.py reference.png top.json ... --medium pastel --radius 2.5 --threshold 0.06 --longest 80 \
       --stick opaque_white:1.3,yellow_ochre:0.7 --top 0.7 --within water.png
   python scripts/scumble_lights.py reference.png threads.json ... --medium coloured_pencil --radius 1 --threshold 0.06 \
       --longest 140 --stick opaque_white:1.2,yellow_ochre:0.8 --top 0.8 --ridges 0.08 --persist 3 --shortest 20 --press 0.4 --within water.png
   ```

   The options left out (`...`) are those of the first command. `--top` is the value a full coat of that mix dries at; set it too high and every stroke comes out too thin.
8. **The hand, and very little of it.** The spar, a rope, a mast and a red cap or two, on the dry sheet from coordinates read off `reference_grid.py` and checked with `preview_pass.py`. A spar that is lighter than the sky behind it is a coloured pencil of ochre and umber, not a pen line.

**Keep the lights to the water.** Give every `scumble_lights.py` pass `--within` an image that is white where it may work: `water.png` white over the sea and black over the sky, the sail and a rectangle round each boat, `boats.png` white in those rectangles. In a sky the picture has no streaks to follow, so the strokes wander: on the first full sheet they dried as pale worms across the clouds. Among figures they curl into outlines; there the lights are dabs (`--longest 14`). On the sail a dry stick speckles the wash.

## What each step did, on a crop

A 400 by 300 crop of the sail's foot, the rowing boat and the foam beside it, at the full sheet's scale, painted both ways from the same reference. Scores are from `value_difference.py`; the three columns after them are the mean value of the passages the picture has above 0.5, between 0.25 and 0.5, and under 0.15 (in the picture 0.59, 0.35 and 0.09).

| After | Value gap | Colour distance | Lights | Middles | Darks |
|---|---|---|---|---|---|
| **A dark ground:** the five row stages from the picture | 0.083 | 0.145 | 0.27 | 0.25 | 0.15 |
| Body colour at radius 5 over it | 0.047 | 0.086 | 0.44 | 0.35 | 0.15 |
| A measured glaze | 0.046 | 0.084 | 0.44 | 0.35 | 0.15 |
| **Layered:** the ground, wet, from `ground.png` (sail under fluid) | | | 0.67 | 0.61 | 0.42 |
| Stages 3 to 5 from `filled.png` | | | 0.45 | 0.36 | 0.17 |
| The size 8 round twice more | | | 0.45 | 0.36 | 0.16 |
| Stages 6 to 8 | | | 0.44 | 0.33 | 0.12 |
| The fluid off | 0.019 | 0.038 | 0.44 | 0.33 | 0.12 |
| Body colour at radius 3 | 0.018 | 0.037 | 0.50 | 0.35 | 0.12 |
| Pastel | 0.018 | 0.038 | | | |
| Pencil threads | 0.025 | 0.050 | 0.54 | 0.37 | 0.13 |

- **The layered sheet is at 0.019 before any covering paint goes on**, against 0.046 for the dark ground with all of its lights. The lights of the layered sheet are transparent wash over paper, and warmer for it (red less blue 0.157 against 0.137; the picture has 0.179).
- **The darks must come from the picture, not from the lightened reference.** With all five row stages laid from a lightened reference the darks stopped at 0.20 to 0.25 and the sheet scored 0.10 to 0.12.
- **A sky gains as much as the sea.** On a crop of the upper left, the row stages from the picture alone left the sky one dark tone (0.058 and 0.099). With stages 1 and 2 from the lightened reference its clouds kept their tones (0.023 and 0.042). So `ground.png` spreads the lights over the whole picture, not the water only.
- **Pencil threads cost score every time** (0.018 to 0.025 here, 0.015 to 0.017 on the full sheet) and read as fine wires. Pastel does not. Raise `--ridges`, or leave the pencil out.
- **The score does not see everything.** On the first study pastel alone scored best and looked worst: flecks with no direction. Judge the sheet enlarged, beside the picture.

## The full sheets

*The Shipwreck* on 1024 by 736, with eight paints named (`ivory_black`, `burnt_umber`, `burnt_sienna`, `hansa_yellow`, `yellow_ochre`, `opaque_white`, `cadmium_red`, `carbon_ink`), from a reproduction 1077 pixels wide. A blank sheet scores 0.748 and 1.305. While the fluid is on, the dark paint standing on it counts against the sheet, so the scores before it comes off are about 0.015 too high.

The whole picture:

| After | Strokes | Value gap | Colour distance |
|---|---|---|---|
| The sail's tint (three layers) and the fluid | 320 | | |
| The ground, wet (stages 1 and 2 from `ground.png`) | 261 | 0.191 | 0.327 |
| The darks in rows (stages 3 to 5 from `filled.png`) | 1,762 | 0.045 | 0.080 |
| The size 8 round twice more | 912 | 0.041 | 0.074 |
| The darks as shapes (stages 6 to 8) | 4,447 | 0.032 | 0.060 |
| Finer shapes round the three boats | 694 | 0.032 | 0.060 |
| The fluid off | | 0.018 | 0.036 |
| Body colour: streaks on the water | 1,397 | 0.016 | 0.033 |
| Body colour: dabs on the boats | 720 | 0.015 | 0.031 |
| Pastel (800 strokes in 34 actions) | 34 | 0.015 | 0.031 |
| Pencil threads (616 strokes in 26 actions) | 26 | 0.017 | 0.035 |
| The hand: yard, stay, sprit, a sliver of sail, a mast, a rope, three touches of red | 11 | 0.017 | 0.035 |

Finished: **0.017 and 0.035, edge agreement 0.55**, in 10,947 strokes and 108 minutes of the sheet's clock. The first study, by the dark ground, finished at 0.041, 0.074 and 0.47 against the same reproduction.

A detail, the two boats and the sea between them at 1.77 times the scale (the same steps, the brushes for the lights half as large again): 0.018 and 0.037 when the fluid came off, 0.016 and 0.035 after the lights and the hand. Its boats were still soft blots, so two finer passes of `shape_strokes.py` round each boat (`--threshold 0.3 --widest 2 --narrowest 1.2 --blur 2 --cap 2.0 --peels 2`, then `--threshold 0.15 --widest 1.8 --narrowest 1.0 --blur 2 --spur 1.5 --peels 1 --cap 2.0`, both `--hair kolinsky_sable`) and smaller dabs of light (`--radius 2.4 --threshold 0.06 --longest 15`) followed: 2,041 strokes of dark and 1,224 of light, after which the hull's frames, the oars and separate figures could be told apart. Finished: **0.015 and 0.032, edge agreement 0.51**, in 13,424 strokes and 123 minutes.

What they read as: the dark sky with its clouds, the one pool of olive and cream water, the sail cut out against black, the waves running with their streaks, the boats low in the water. What they do not have: Turner's figures, the weave and stain of his sail, and the thick paint of his foam.

- **Nearly all of the picture is on the sheet before the lights.** The lights and the hand took 0.018 to 0.017. They are what makes the water look wet, and they are where the risk is.
- **Stages 6 to 8 are the slow ones**: 4,447 strokes, about half the sheet. They are also what turns the row washes into waves.
- **At the whole picture's scale a boat is thirty pixels of blots and stays so.** Figures need the sheet: on the detail a figure is twenty to forty pixels high, and the finer passes found it.
- **Scale the silhouette on the sheet it is for.** The detail's fluid was laid from a silhouette enlarged 1.77 times, and the sail's upper edge dried in steps. Run `wash_references.py` on the reference at the sheet's own size.
- **Close only bare paper.** A wash can leave a speck or a dash of bare paper in a dark sky, and a dab of dark closes it. A pass that dabbed dark wherever the sheet was lighter than the picture by 0.25 also peppered the edges of the foam with 361 dots, which still show close up. The test is the sheet above 0.75 where the picture is under 0.3.
- **Two sheets on one graphics card took three hours and twenty minutes.** Run the sequence detached from the shell and wait on its log; a command left in the background is cut off at thirty minutes.

## Rules the first full sheet taught

The measured sequence brought the first sheet to a value gap of 0.031 and it read as the picture. Three corrections by hand then spoiled it (0.065):

- **A dark glaze over the sky to sink the stray scumbles** (ivory black 1.1 in rows of a mop) dried as one flat black slab with a ruled lower edge. A sky that is already at its value takes no more paint. Keep the scumbles out of it instead.
- **A warm glaze over the sail in six rows** dried as six stripes: the rows did not overlap. A glaze is laid as a wash (rows a radius apart, laid wet together) or not at all.
- **Hulls and figures drawn in pen and charcoal** read as marks on top of the painting. The boats of these pictures are part of the water; measure them (step 5).

So: when the measured sheet reads, stop. What it still lacks is rarely worth the risk of a correction.

## How much light each stroke lays

Pale pastel (`opaque_white` 1.7, `yellow_ochre` 0.3, radius 3, rows 5 pixels apart) over a dried wash:

| Pressure | 0.12 | 0.16 | 0.2 | 0.25 | 0.3 | 0.4 | 0.5 | 0.7 | 1.0 |
|---|---|---|---|---|---|---|---|---|---|
| Over a dark of 0.065, one coat | 0.17 | 0.24 | 0.27 | 0.36 | 0.38 | 0.49 | 0.56 | 0.68 | 0.69 |
| The same, two coats | 0.26 | 0.32 | 0.37 | 0.40 | 0.43 | 0.64 | 0.71 | 0.78 | 0.79 |
| Over a middle value of 0.32, one coat | 0.39 | 0.42 | 0.43 | 0.49 | 0.50 | 0.57 | 0.62 | 0.71 | 0.72 |
| The same, two coats | 0.44 | 0.47 | 0.50 | 0.52 | 0.54 | 0.68 | 0.73 | 0.79 | 0.80 |

So pressure is a continuous control from a breath of light to a covering coat, and no dry light is lighter than about 0.8. A light that must be lighter than that is paper, kept under fluid.

## What this does not reach

- The lights are still a little cooler than Turner's (red less blue 0.158 on the full sheet where the picture has 0.179), and the darks a little lighter (0.12 where it has 0.09).
- The sail is one flat tint with the marks of its three layers in it. The picture's sail has a weave, a stain and a shadowed foot.
- Body-colour strokes have even edges, and the pencil's threads are wires. Turner's paint is thick in one place and scraped thin in the next within one stroke; nothing here varies a stroke's cover along its length except its width.
- The sheet is softer than the picture (edge energy 0.043 against 0.052). Its darks are built from many small touches with soft borders.
- The scripts copy a picture that exists. They do not compose one. Painting a sea from an idea still means deciding the pool of light, the one warm light and the diagonals first; the six pictures above are the pattern, and a value sketch made to that pattern can stand in for the reference.
- Figures are suggested, not drawn. What the measured stages cannot find at the sheet's scale is not there.

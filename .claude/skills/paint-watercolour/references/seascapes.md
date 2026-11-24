# Seascapes: a sea in weather

Read this before painting a sea in weather: a storm, a wreck, a ship in a gale, surf at night. `water.md` is about copying a photograph of surf passage by passage. This file is about making a sea picture: its key, where its light lies, how foam and spray are painted, and how a hard object sits in it.

There are two jobs here and they are not done the same way.

- **A sea of your own** is painted directly: planned in numbers, then laid in a few hundred strokes that use what water does. "Painting a sea directly" below.
- **A copy of a sea picture that exists**, a study after a painter, is measured and built in layers. "Copying a sea picture" below.

It rests on six sea pictures by J. M. W. Turner, measured; six small studies of one breaking crest, four sheets of single effects and two full sheets, all painted directly; two copies of Turner's *Shipwreck* (1805); and five painters' liners, measured. Three sheets of a liner in a storm were also copied from rendered designs before the direct ones: that was the wrong way to make an original, and what it taught is under "What copying a render taught". It needs 0.12.0 or later. Everything was on cold press, on sheets 1024 pixels wide and on 440 by 330 studies at the same scale. Values are the value view, where paper reads 0.96.

## The rules, in brief

1. **The sea is the picture.** A low key, one mass of light off centre, dark corners, few hard edges, almost no colour.
2. **An original is painted, not copied.** Plan it in numbers. Do not render a reference and reproduce it: three sheets made that way took about 5,700 strokes each and read as copies of a render. The same picture painted directly took 722.
3. **Every large light is paper.** Foam is the paper the sea's own upper edge leaves, shaded afterwards. Nothing laid afterwards is lighter than about 0.8.
4. **A light has a shape only against a dark.** Bring the dark sky down behind the foam and beside the bow.
5. **Soft comes from water, not from small strokes.** Lay a bed of clear water and charge colour into it. The colour dries crisp where it reaches the bed's boundary and fades where it does not, so an edge is found or lost by how near to it the colour is put.
6. **Foam on the water is covering white charged into the wet sea**, as its shine goes. On dry paint it is a wire.
7. **Mask only what must be firm**: a bow, flecks of spray. A masked edge stays cut.
8. **A hard object is brushed, not ruled**, and lost at one end.
9. **Try each passage on a small sheet, rehearse the whole at half size, and copy the painting's directory before each pass.**
10. **A copy of an existing picture** takes a light ground laid wet and its darks in dry layers.

## What the picture needs

Measured on reproductions of six pictures by Turner, each scaled to 640 pixels:

| Picture | Mean value | Median | Lighter than 0.5 | Lighter than 0.7 | Lightest 7% centred at (x, y) | Hard edges | Mean chroma |
|---|---|---|---|---|---|---|---|
| The Shipwreck, 1805 (the copy's reference) | 0.21 | 0.15 | 7% | 2.5% | 0.56, 0.63 | 4.7% | 0.06 |
| The Shipwreck, a gallery photograph | 0.20 | 0.19 | 4% | 0% | 0.57, 0.62 | 2.5% | 0.17 |
| Calais Pier, 1803 | 0.50 | 0.52 | 53% | 22% | 0.41, 0.56 | 14% | 0.20 |
| Dutch Boats in a Gale, 1801 | 0.34 | 0.30 | 26% | 2.9% | 0.65, 0.47 | 0.9% | 0.10 |
| Fishermen at Sea, 1796 | 0.12 | 0.07 | 3% | 0.3% | 0.40, 0.42 | 0.9% | 0.04 |
| Snow Storm: Steam-Boat off a Harbour's Mouth, 1842 | 0.47 | 0.48 | 46% | 7% | 0.69, 0.50 | 0.3% | 0.08 |

"Hard edges" is the share of pixels where the value changes by more than 0.15 in one pixel. "Chroma" is the mean difference between the strongest and weakest channel.

- **The sea is the picture.** The boats are small, tilted, cut off by waves and half lost in them. A ship set whole and upright in front of a tidy sea is an illustration of a ship.
- **A low key with little light.** Four of the six have a median under 0.31. The Shipwreck's darks sit at 0.05 to 0.15 and its foam at 0.4 to 0.6: what reads as white foam there is a middle value made bright by the dark round it.
- **The water is middle tone, not dark.** A wave's face in The Shipwreck is one continuous olive mass at 0.35 to 0.45. Only the troughs and the far sea are black.
- **One pool of light**, off centre, with the corners falling away dark, and **one light set against the darkest dark**.
- **Almost no colour.** The Shipwreck is a warm black and one ochre. Ivory black with a little hansa yellow gives its olive water; for a cool sea the same black takes cobalt blue.
- **Few hard edges, spent on purpose**: under 5% of the picture in five of the six. The water has none.
- **Diagonals.** Spar, sail, wave backs and the line of the boats all lean.

## Painting a sea directly

A cruise liner coming level through a storm, a great wave breaking over her bow, on 1024 by 768. The figures are that sheet's; a study at 440 pixels took them divided by 2.3.

### Plan it in numbers, not as a picture

Write the composition down as a few functions of x: the crest's upper edge, how deep the foam lies under it, the foam's uneven lower edge, and the way the water runs down the face. An object that must be in perspective (the liner) is a silhouette projected from a model, used as a drawing is used: for its outline and where its decks lie, never as a picture to match. Then:

- **Draw the plan and the strokes over it** with `preview_pass.py` on a blank sheet before any paint. It shows a gap between strokes or a wash that crosses the foam.
- **Rehearse the whole at half size.** Scale places, brush sizes and speeds together and leave the waits alone: the film dries at the same rate on any sheet. One rehearsal showed a bare gap where two strokes drew apart, a hull shadow that dried as a blob, and too many trails in what should be empty water.
- **Copy the painting's directory before each pass.** It is the only way back. On the first full sheet one pass was taken back from a copy, and the sheet was started again twice.
- **Shape matters more than finish.** A crest that rose to a peak with sky on both sides read as a snowy mountain, however it was painted. A crest that enters at the top corner and runs down to the ship reads as a wall of water.

### The order

1. **Fluid.** The forward part of the liner (`mask_lights.py` on her silhouette) and forty to fifty flecks of spray about the lip, radius 1.3 to 3, a third of them drawn out downwind.
2. **The sky, into a bed of clear water.** A mop 40 lays the bed: one stroke along the crest and one along the liner, each with its lower side on the edge, then level rows 36 apart over the rest. Into it, at once:
   - grey (`ivory_black` 2.0, `cobalt_blue` 1.5, `burnt_sienna` 0.4, water 0.65, mop 28) in three strokes parallel to the crest, 64, 116 and 176 above it, and lifted 70 to 90 higher wherever spray is to leave the lip;
   - the dark of the storm (`ivory_black` 5.0, `cobalt_blue` 2.0, water 0.6, mop 32) across the top, behind the liner's upper decks and down beside her bow.

   Where grey lies within about 65 of the bed's boundary the crest is found against it. Where it is 130 or more away the paper stays pale and the edge is lost: that is the spray, and nothing else paints it. With plumes 200 wide the whole crest was lost; at 90 to 120 wide it is found between them.
3. **The sea, in one wet pass.**
   - Its upper edge first, which draws the foam's lower edge: a round 15 of pale sea (`cobalt_blue` 0.8, `hansa_yellow` 0.45, `ivory_black` 0.55, water 0.95) with its centre 11 below the edge.
   - Then the water in strokes that follow it down the face: a mop 34 (`cobalt_blue` 1.1, `hansa_yellow` 0.6, `ivory_black` 0.9, water 1.0), 44 apart, each starting 30 below the edge at half pressure. Every stroke bends by the same rule of y alone, so strokes side by side stay side by side. At 520 pixels a second the wash is unbroken; at 900 the brush skipped on the grain and speckled the whole sea.
   - Then the dark of the hollow (`ivory_black` 4.2, `cobalt_blue` 1.4, `hansa_yellow` 0.7, water 0.6, mop 34) charged into the wet sea in seven strokes low on the sheet, and with a round 18 under the heaviest of the foam.
   - Where the foam's edge should be lost, wet the foam side first (a round 22 of clear water 20 and 50 above the edge): the sea runs up into it.
4. **Foam on the water, while the sea is wet.** `opaque_white` 6.0 at water 0.55. Take the sheet a third at a time, each with its own `wait` on the film at a point in it:
   - at film 0.30, tongues: a round 8 to 17 that starts 10 inside the foam and runs 60 to 300 down the face, its pressure falling away;
   - at film 0.16, trails: a round 5 to 7.5 that starts 150 to 330 below the edge and runs 170 to 320.

   Give each its own length, wobble and bend (0.55 to 1.5 of the water's). Leave the hollow empty.
5. **Dry, then shade the foam.** Clear water inside the white (a mop 26 at 0.88, 0.72 and 0.56 of the foam's depth, the lowest kept 10 inside the lower edge), then cool grey (`cobalt_blue` 0.9, `burnt_sienna` 0.45, `ivory_black` 0.25, water 0.6, round 15) along a line 26 inside the lower edge. It climbs into the bed and fades, so the shadow has no upper edge and the top of the foam stays paper. A deeper touch (1.6, 0.8, 0.5) goes under the heaviest parts while the bed is wet. For a billow higher in the mass, lay a bed of three strokes (a round 18 at 18, 44 and 68 above the top of the billow below) and charge grey at 0.6 to 0.7 strength 11 above its lower boundary.
6. **The fluid off, and the object.** "A hard object in the sea".
7. **The last lights, few.** `opaque_white` 4.5 at water 0.7 on the dry sheet, two coats, over the first two fifths of the larger tongues where they leave the foam; a broken line along a second crest; flecks of 1.6 to 4.

The second full sheet took 722 strokes and 56 minutes of the sheet's clock: fluid 290, sky 28, sea 81, foam 21, the liner 261 (198 of them lamps), lights 40. Its foam measures 0.95 at its lightest tenth, 0.88 at its median and 0.68 at its darkest tenth; its sea has a median of 0.14 and its sky 0.04; 1.7% of it is hard edge.

### What the trials showed

Ten study sheets, 440 by 330, forty to a hundred and sixty strokes and about ten minutes each, and what went wrong on the full sheets.

| Tried | Result |
|---|---|
| Sky and face laid at full strength in level rows, cut to the slope | Flat slabs with a stair-stepped edge |
| The face dragged up into the foam with a half-dry flat or hake | Dotted columns, like a bar code |
| The face as pointed strokes pulled down from the foam | A fence |
| **The sky charged into a bed of clear water, grey near the crest and far from it** | The edge found and lost; plumes of spray |
| **The foam's lower edge drawn by the sea's upper edge, uneven** | Lobes of foam. Even scallops read as a curtain |
| The dark under the foam added as the wash lost its shine (film 0.14) | A black wire along the foam |
| **The same dark charged in at once, into the wet sea** | A soft hollow |
| Strips of paper left between the strokes of the face | White bars |
| **The foam side wetted before the sea's edge is laid** | The edge lost; the sea bleeds up softly |
| Stippled dabs along the edge | Dashes |
| Streaks lifted three times with a drained round at film 0.25 | Soft and faint: good for far trails |
| **Covering white charged in at film 0.36; at 0.15** | Broad and faint; clear and soft-edged, the best trail |
| Drops of clear water at film 0.08; a streak of it at 0.10 | Blobs and streaks with dark rims |
| Covering white on the dry wash, two coats | A crisp broken line: for a few accents only |
| **Grey charged into a tall bed along the underside of the foam** | A rolling mass, white above |
| Grey charged into narrow beds, 75 deep, along the crest | Hard grey sausages in the sky: the colour reached every boundary |
| A stroke of sea laid on the dry sea to close a gap | A dark-rimmed patch. Wet the place and charge white into it |
| The sea laid at 900 pixels a second | Speckled with bare paper |
| A crest rising to a peak, with sky on both sides | A snowy mountain |

### What these sheets do not reach

- A fifth of the sheet is lighter than 0.7, where Turner's storms have a fortieth. The foam and the ship together are a larger light than his pictures carry.
- Two thirds of the foam carries some shadow, so it reads a little as snow or cloud. It wants more paper and fewer billows.
- The trails are grey and too alike, and the wave's face is a dark slope with no light coming through it under the lip.
- No lace: the net of fine foam on a face was not tried by hand.

## A hard object in the sea

A ship, a pier or a lighthouse is the one thing in such a picture with straight edges, and painters do not rule it. Five paintings of liners, each ship scaled to 540 pixels long, beside the liner of the copied sheets:

| Ship | Width of a strong edge (quartiles) | Hard steps in the ship | Hard lines run unbroken (90th centile) |
|---|---|---|---|
| Jacobsen, Lusitania, 1908 (ship portrait) | 3.5 px (3.1 to 4.1) | 3.6% | 14 px |
| Pansing, Olympic, c. 1911 (ship portrait) | 3.3 px (2.8 to 4.1) | 3.4% | 6 px |
| Stöwer, Titanic sinking, 1912 (wash illustration) | 2.6 px (2.2 to 3.1) | 11.4% | 3 px |
| Wilkinson, Lusitania, 1907 (oil) | 3.0 px (2.5 to 3.8) | 7.1% | 4 px |
| Wyllie, Carmania, 1914 (watercolour) | 3.1 px (2.7 to 3.6) | 2.7% | 4 px |
| The liner, all of her under fluid, deck bands ruled with the pen | 2.7 px (2.6 to 2.8) | 9.2% | 15 px |
| The same, her bands brushed instead | 2.7 px (2.5 to 3.0) | 5.7% | 10 px |
| Only her forward part under fluid | 2.8 px (2.6 to 3.0) | 4.4% | 11 px |

The width of an edge is its step in value divided by its steepest slope, over the strongest 3% of edges in the ship's box; a hard step is a change of more than 0.15 from one pixel to the next. A painter's edges vary by about a pixel within one ship, the hard lines break, detail thins with distance, the far end goes into smoke or haze, the waterline is lost in foam, and lit ports are uneven dabs.

- **Mask only what must be firm.** The fluid's edge stays cut whatever is done afterwards. The fluid covered the liner forward of a line 112 metres aft of her stem, its outline blurred by 2.5 pixels before it was cut so that the steps of her decks lost their corners. Her after end was left to the sky.
- **Put the dark behind what is to be seen.** With pale spray behind her bow the bow was lost in it. With the storm's dark brought down beside it, her stem stands white.
- **Lose the far end in rain.** After the fluid comes off: clear water over her after end and the sky beyond, grey charged in from the far side in slanting strokes, weaker towards her (1.0, 0.9, 0.7, 0.45 of the sky's grey).
- **The shadow on her side goes into a bed.** A stroke of grey on the dry hull dried as a blob. Clear water over the lower hull (a mop 15 at 14, 36 and 56 above her foot) and grey (`cobalt_blue` 0.8, `burnt_sienna` 0.38, `ivory_black` 0.22, round 9) 12 above her foot fades upward. Its upper contour still shows; a taller bed would lose it.
- **No pen and no `crisp_layers.py` for her detail.** Bands ruled with the pen read as a technical drawing, and carbon ink cannot be softened once dry. Three crisp layers inside the silhouette took 4,266 strokes for the first alone and turned her side into a grey smudge.
- **Bands with a small round on dry paper.** Size about half the band's width, `ivory_black` 0.85 and `cobalt_blue` 0.65 at water 0.75, each point up to a third of a pixel off the line, the pressure falling towards the far end, and about one point in five lifted (pressure 0) so that the line breaks. On damp paper the same strokes bloomed.
- **Lamps as uneven dabs.** One dab of covering paint (`opaque_white` 3.0, `yellow_ochre` 2.0, `hansa_yellow` 0.6, `cadmium_red` 0.18) for each lit window, each moved up to a pixel, sized 0.85 to 1.4 times, an eighth of them left out at the near end rising to two fifths at the far end.
- **To lose an edge that was cut, wet it and charge it.** A clean damp brush run along a dried cut edge changed nothing. Clear water along the edge and then dark of strength about 6 (`ivory_black` 4.5, `cobalt_blue` 1.5, water 0.6) on the edge itself runs into the object over about 15 pixels. Dark charged beside the edge never reaches it. Not masking the edge is the better answer.
- **Rehearse on the CPU when the graphics card is busy**: `CUDA_VISIBLE_DEVICES= uv run watercolor ...`. A 300 by 270 sheet takes about half a minute a pass.

## Copying a sea picture

For a study after a painter. *The Shipwreck* was copied this way to a value gap of 0.017.

Two ways failed first. Foam and sails kept as paper under fluid, with a flat sea washed over them, gave white shapes with cut edges. A dark ground with every light laid over it in covering paint read as the picture at arm's length and as flat cream ribbons on black close up: laid from a low-key picture, a wet wash runs its darks into the middle tones beside them (on a crop the picture's lights dried at 0.27, its middle tones at 0.25, its darks at 0.15), and thin white over black dries cool and grey. Fixative under the white changed nothing (0.445 fixed, 0.438 unfixed).

So the wet washes are laid from a reference in which every light has been spread into its surround, the darks are built over them on dry paper, and a light with a firm edge is tinted and kept under fluid until the darks are done.

1. **A crop first.** 400 by 300 at the sheet's scale, where the picture is hardest, painted by steps 2 to 7. Several run at once, each changing one thing.
2. **The references.** `wash_references.py` writes `ground.png` (the picture with every light spread 7 pixels into its surround) and, for one light to keep under fluid, its `shape.png`, its `tint.png` (its colour carried past its edge on white) and `filled.png` (the picture with the shape filled in by its surround):

   ```bash
   python scripts/wash_references.py reference.png plate --sheet 1024,736 --seed 660,320 --warmer-than 0.07
   ```

   Run it on the reference at the sheet's own size: fluid laid from a silhouette enlarged 1.77 times dried in steps.
3. **The firm light: its tint, then fluid.** Three measured layers of a size 10 round from `tint.png` on the bare paper, each from a look of the dried sheet, then fluid on the silhouette. The tint runs under the fluid's edge, so the light comes out with no rim of paper and no ring of pooled paint; painting it after the fluid comes off left both. For an object with light and dark parts the tint is its lights only: from the whole of it, the layers laid a middle grey.

   ```bash
   python scripts/measured_layers.py plate/tint.png tint.json --sheet 1024,736 --look <look> --brush round --hair squirrel \
       --size 10 --paints yellow_ochre,burnt_sienna,burnt_umber --gain 0.9 --least 0.03 --smoothing 0.5 --wobble 0.12 --tolerance 0.5
   python scripts/mask_lights.py plate/shape.png mask.json --sheet 1024,736
   ```

4. **The ground, wet.** Stages 1 and 2 of `copy_reference.py --even-passages`, from `ground.png`:

   ```bash
   python scripts/copy_reference.py paintings/sea plate/ground.png --sheet 1024,736 --even-passages --last 2 \
       --paints ivory_black,burnt_umber,burnt_sienna,hansa_yellow --out-of-washes burnt_umber
   ```

5. **The darks, on dry paper.** Stages 3 to 5 from `filled.png` (`--first 3 --last 5`), then a size 8 round twice more across them, then stages 6 to 8 (`--first 6 --last 8`). The darks must come from the picture: laid from the lightened reference they stopped at 0.20 to 0.25. Round a small boat, one finer pass of `shape_strokes.py` (`--threshold 0.2 --widest 2.5 --blur 3 --region ...`).

   ```bash
   python scripts/measured_layers.py plate/filled.png rows.json --sheet 1024,736 --look <look> --brush round --hair squirrel \
       --size 8 --angle 60 --paints ivory_black,burnt_umber,burnt_sienna,hansa_yellow --gain 1.0 --least 0.08 --smoothing 0.5 --wobble 0.12 --tolerance 0.5
   # and again with --angle -60
   ```

6. **Close the specks, then take the fluid off.** Before any light goes on, a small light patch in a dark passage is bare paper, and a dab of dark closes it: where the sheet is above 0.5 and the picture under 0.22, in patches of 90 pixels or fewer. A looser test (lighter than the picture by 0.25) peppered the edges of the foam with 361 dots.
7. **The lights, few.** `scumble_lights.py` lays light where the dried sheet is still darker than the picture, in strokes that follow the picture's streaks:

   ```bash
   python scripts/scumble_lights.py reference.png body.json --sheet 1024,736 --look <look> --medium body_colour \
       --radius 3 --threshold 0.08 --longest 120 --stick opaque_white:1.0,yellow_ochre:0.7 --top 0.68 --within water.png
   python scripts/scumble_lights.py reference.png dabs.json ... --radius 2.5 --threshold 0.08 --longest 14 --within boats.png
   ```

   `--top` is the value a full coat of the mix dries at. Give every pass `--within` an image that is white only where the picture is streaked: in a sky or on smooth water the strokes wander into worms and loops, and among figures they curl into outlines. Cream for a warm sea; on a cool one it dried as warm patches, and pure `opaque_white` (`--stick opaque_white:1.2 --top 0.82`) did not. Pencil threads cost score every time (0.018 to 0.025 on a crop) and read as wires.
8. **The hand, very little, and stop.** On the first Shipwreck sheet the measured sequence reached 0.031 and three corrections by hand took it to 0.065: a dark glaze over the sky dried as a flat slab, a glaze over the sail in six rows dried as six stripes, and hulls drawn in pen read as marks on top of the painting.

**Each step, on a crop.** Scores are from `value_difference.py`: the value gap, then the colour distance. The last three columns are the mean value of the passages the picture has above 0.5, between 0.25 and 0.5, and under 0.15 (in the picture 0.59, 0.35 and 0.09).

| After | Value gap | Colour distance | Lights | Middles | Darks |
|---|---|---|---|---|---|
| **A dark ground:** the five row stages from the picture | 0.083 | 0.145 | 0.27 | 0.25 | 0.15 |
| Body colour at radius 5 over it | 0.047 | 0.086 | 0.44 | 0.35 | 0.15 |
| **Layered:** the ground, wet, from `ground.png` | | | 0.67 | 0.61 | 0.42 |
| Stages 3 to 5 from `filled.png` | | | 0.45 | 0.36 | 0.17 |
| Stages 6 to 8 | | | 0.44 | 0.33 | 0.12 |
| The fluid off | 0.019 | 0.038 | 0.44 | 0.33 | 0.12 |
| Body colour at radius 3 | 0.018 | 0.037 | 0.50 | 0.35 | 0.12 |
| Pencil threads | 0.025 | 0.050 | 0.54 | 0.37 | 0.13 |

**The sheets.** *The Shipwreck* whole, 1024 by 736: 0.018 and 0.036 when the fluid came off, **0.017 and 0.035, edge agreement 0.55**, in 10,947 strokes (the dark shapes of stages 6 to 8 are half of them) and 108 minutes of the sheet's clock. A detail at 1.77 times the scale: **0.015 and 0.032**, in 13,424 strokes; figures need that scale, and a boat on the whole picture is thirty pixels of blots. The first study, by the dark ground: 0.041, 0.074 and 0.47. Run a sheet detached from the shell and wait on its log: a command left in the background is cut off at thirty minutes.

**How much light a dry stroke lays.** Pale pastel (`opaque_white` 1.7, `yellow_ochre` 0.3, radius 3, rows 5 pixels apart) over a dried wash:

| Pressure | 0.12 | 0.16 | 0.2 | 0.25 | 0.3 | 0.4 | 0.5 | 0.7 | 1.0 |
|---|---|---|---|---|---|---|---|---|---|
| Over a dark of 0.065, one coat | 0.17 | 0.24 | 0.27 | 0.36 | 0.38 | 0.49 | 0.56 | 0.68 | 0.69 |
| The same, two coats | 0.26 | 0.32 | 0.37 | 0.40 | 0.43 | 0.64 | 0.71 | 0.78 | 0.79 |
| Over a middle value of 0.32, one coat | 0.39 | 0.42 | 0.43 | 0.49 | 0.50 | 0.57 | 0.62 | 0.71 | 0.72 |
| The same, two coats | 0.44 | 0.47 | 0.50 | 0.52 | 0.54 | 0.68 | 0.73 | 0.79 | 0.80 |

**What the copies do not reach.** Their lights are a little cooler than Turner's (red less blue 0.158 where the picture has 0.179) and their darks a little lighter (0.12 for 0.09). The sail is one flat tint. The sheets are softer than the picture (edge energy 0.043 against 0.052), and figures are suggested, not drawn.

## What copying a render taught

Three sheets of the liner were made by rendering a design (a modelled sea and ship) and copying it with the method above, each scored against its own design (0.035 and 0.062; 0.041 and 0.071; 0.035 and 0.060). The scores say how like the render each sheet is. They say nothing about whether it is a painting, and a fourth, with foam painted into the render, was stopped. What they showed about paint still holds:

- **Light carried in thin lines comes back as wire.** The first design's foam was lines; so was the sheet's.
- **A crest added afterwards stays grey.** Body colour and pastel over the dried sea gave a pale band flecked with chalk. Left as paper against a dark sky it measured 0.75 where its design had 0.77.
- **Nine trials of marks laid on a copied crest** (covering white on dry, into re-wetted paint, dragged, and on rough paper; pastel; dark cells for lace; veins under fluid; lifting from a glaze) left its foam at 0.73 to 0.78 and read as grey marks, chalk, fish scales or wires.
- **A blemish in a dark sea is sunk by a glaze laid along the wave**, into clear water, not in level rows; measured dark touches did nothing to it.

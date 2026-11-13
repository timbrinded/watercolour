---
name: paint-watercolour
description: Paint a watercolour with this repository's `watercolor` harness - a simulated sheet, brushes and paint driven stroke by stroke with no undo. Use this whenever asked to paint, sketch, illustrate or make a picture, landscape, study or copy with the watercolour rig, to continue or finish a painting session, or to judge why a painting made with it looks stiff, flat or muddy, even if the request never says "watercolor" or names the command.
---

# Painting with the watercolour harness

You are the painter. The harness gives you paper, water, pigment and brushes that behave like the real things, and takes away the one thing software usually gives you: undo. Whatever reaches the sheet stays there. That is the point of the tool, so paint like someone who cannot take a stroke back: plan, start pale, look often, and commit.

Read `references/actions.md` for the exact fields of every action, the brushes, and the paint box. This file is about how to paint well with them.

## The loop

```bash
uv run watercolor new paintings/<name> --prompt "<the brief>" --size 768 --height 544
uv run watercolor paint paintings/<name> pass.json     # a JSON list of actions
uv run watercolor look paintings/<name> --grid         # then Read the picture it names
uv run watercolor status paintings/<name>
uv run watercolor finish paintings/<name>              # dries, exports painting.png and timelapse.mp4
```

- A painting is a directory and is never started over. A new attempt is a new directory.
- `paint` checks the whole pass before any of it touches the sheet. A pass with a mistake in it is refused whole, so a refusal costs nothing.
- `look` is free and changes nothing. Look after every pass, and always Read the image: you cannot judge a wash from the numbers you sent.
- Coordinates are pixels, x to the right and y downward, origin top left.
- Painting takes real time: a full sheet of this size is seven to nine minutes of computing across its passes. Run long passes in the background.

## Plan before the first stroke

You get one go at each passage, so decide these first:

1. **The value plan.** Where is the lightest light, which is bare paper, and where is the darkest dark? Three or four values are enough.
2. **The order.** Pale and broad first, dark and small last: drawing, big light washes, middle shapes, darks, fine detail, then opaque white for the few lights you could not save.
3. **The layout, in numbers.** Write down the coordinates of the main shapes before painting. If you are working from a reference, measure it (put a labelled grid over it) rather than judging by eye; by-eye layouts drift further than you expect.
4. **What stays white.** There is no masking fluid. A white shape is made by painting around it, so the washes next to it must be planned to stop at its edge.

If the session has a scrap sheet, try any mix or stroke you are unsure of there first (`"sheet": "scrap"`). It does not count against the stroke budget.

## Water is the clock

Everything depends on how wet the paper is where your brush lands. `status` reports the share of the sheet at each stage, and `look --view wetness` shows where.

| Paper | What a new stroke does there |
|---|---|
| **Dry** | Keeps a hard edge, and dries darker at that edge than in its middle. Use for crisp shapes and glazes. |
| **Shiny** (standing water) | Spreads and blends softly into what is there. Use for wet-in-wet. |
| **Moist** (sheen gone) | Spreads a little and holds a soft edge. Good for soft shadows and for deepening a wash. |
| **Damp** (no surface water) | Dangerous. Wetter paint or clean water floods back into the drying wash and leaves a bloom. Wanted sometimes, a ruined sky otherwise. |

A full wash stays shiny for roughly a minute and a half of painting time, and strokes take time to make. So:

- **Lay a wash quickly.** Use a big brush, fast strokes (`"speed": 280`), and overlapping rows about one brush radius apart. Rows that only just touch leave a line between them.
- **Do not go back into a wash that has lost its shine** unless you want the bloom.
- **Use `{"action": "dry"}` before a glaze or a crisp shape**, and `wait` when you want the paper moist rather than dry.

## Make each mark with a brush that fits it

The commonest failure is building shapes from many small strokes. They come out stiff and stair-stepped, like cut paper. A painter lays a shape in one stroke of a brush as wide as the shape.

- **Size the brush to the shape.** `size` is the radius in pixels, so a band 20 pixels deep is one stroke of a size 10 brush, not six strokes of a size 3.
- **Use pressure to shape the stroke.** Each point is `[x, y, pressure]`. A round brush is a fifth of its width at no pressure and full width at 1.0, so `[[x0,y0,0.3],[x1,y1,1.0],[x2,y2,0.4]]` with `"smooth": true` swells and tapers like a leaf. This is where expression comes from.
- **Choose the head for its edge.** The mop lays soft broad washes. The round does most things. The flat has a chisel edge: its strokes end square, so one flat stroke makes a crisp-cornered plane (a wall, a shadow, a band of colour). A filbert ends in a curve, an angular head on a slant, a comber draws several lines at once, and the rigger draws one.
- **Choose the hair for how far it must carry.** Squirrel holds more than twice what sable does and leaves a soft edge, so it suits washes; sable keeps a point and a crisp edge; a golden synthetic runs dry and streaks soonest, which is useful for dry-brush and a nuisance for a wash.
- **Vary neighbouring marks.** A row of identical touches reads as a pattern. Change length, direction, pressure and colour from one touch to the next when painting foliage or rock.

## The stroke as a journey

A stroke is not only a line across the sheet. It is a journey the hand makes: where the brush goes, how hard it presses, how it is held, how its head is turned, and how long each part takes. Each point of a path can be a plain `[x, y, pressure]`, or a mapping that says more:

```json
{"action": "stroke", "smooth": true, "path": [
  {"x": 120, "y": 300, "pressure": 0.2, "angle": 20, "t": 0.0},
  {"x": 190, "y": 280, "pressure": 1.0, "angle": 45, "t": 0.9},
  {"x": 300, "y": 296, "pressure": 0.1, "angle": 45, "t": 1.2}
]}
```

That stroke lands lightly on the point of the brush, presses into its belly, then flicks away fast as the pressure lifts. Use these controls deliberately; a painting made of strokes that all travel at one speed, one pressure and one angle looks mechanical however good the shapes are.

### Pressure sets the width

How far a head narrows as you lighten it is the main thing that distinguishes one shape from another:

| Narrowest, as a share of full width | Heads | So use pressure to |
|---|---|---|
| about 5 to 10% | `sword`, `designer` | Draw: a hairline that opens into a broad stroke and closes again. |
| about 20 to 30% | `round`, `dagger` | Shape leaves, petals, tapering branches and shadows in one stroke. |
| about 40% | `spotter`, `rigger`, `extended_point`, `cats_tongue` | Vary a line's weight without losing it. |
| about 70 to 75% | `mop`, `oval_wash`, `filbert` | Soften the start and end of a stroke; the body stays broad. |
| 85% and above | `flat`, `bright`, `angular`, `hake`, `flat_wash`, `comber`, `fan`, `stippler` | Almost nothing. These hold their width; change it by twist instead. |

Light pressure also lays less water and lets the brush skip on the grain; firm pressure closes the hairs and presses wet paint along in the direction of travel.

### Angle chooses between the point and the side

`angle` is how far the brush is laid over, in degrees: 0 is upright on its tip, 45 is the usual hold (and what you get if you say nothing), 90 is laid flat on its side.

- **Upright (0 to 20).** A round head touches with its point alone: a mark about 70% as wide, with more water flowing into it. Use it for fine wet lines, crisp detail and feeding a wash.
- **Laid over (70 to 90).** The side of the hair drags across the paper. The mark is broader, gives up much less water, rides on the grain and breaks up. This is the real dry-brush: sparkle on water, rough stone, bark, the ragged edge of foliage. It works even with a fairly full brush.
- **How much broader depends on the length of the hair.** A `spotter` laid over gains about a fifth in width, a `round` about two fifths, a `designer` about three fifths, and a `rigger` roughly doubles, turning from a line into a broad dry scumble.
- **Flat heads** change differently. Upright, the edge alone touches and the stroke ends crisply. Laid over, more of the face meets the paper, so the mark deepens along its travel, dries and breaks.

### Twist turns the edge of a flat head

`twist` is how far the edge of a flat head is turned from square to its travel, in degrees from -90 to 90. It does nothing to a round head.

- **0** draws at full width. **90** draws end-on: a line as thin as the head is deep.
- **The width does not fall evenly.** A flat keeps nearly nine tenths of its width at 45 degrees and three quarters at 60; most of the narrowing happens beyond 70. To get a visible thick-and-thin, hold the twist near 0 and near 90 and pass quickly between.
- **Changing twist along a stroke** gives the ribbon of a broad pen: thick on one run, thin on the turn. Use it for grasses, reeds, rigging seen side on, lettering, and the planes of buildings that change direction.
- **Heads cut at an angle** (`angular`, `dagger`, `sword`) already have their edge turned, so they are thinnest at a twist of about 50 to 60, not 90.
- **A dab** with a flat head is a bar; twist turns the bar.

### Time sets how much paint is left, and where

Give every point a time `t` in seconds, or give none. With none, the brush travels at the stroke's one `speed`.

- **Slow passages leave more paint.** At about 50 pixels per second a stroke leaves roughly a third more than at 250, so it dries darker and wetter.
- **A pause leaves a pool.** Repeat a point with a later time and the brush rests there, still giving up paint: a darker bead where a stroke begins or ends, a bloom if the paper around it is damp. Pause on purpose, at the start of a stem or the foot of a shadow; an unplanned pause shows.
- **Fast passages break up**, and how soon depends on the head. Above about 500 pixels per second the thin, long or gapped heads (`designer`, `dagger`, `sword`, `rigger`, `comber`) skip and scatter first. Broad full heads (`round`, `flat`, `filbert`, `mop`) stay solid until they are also running dry.
- **A flick** is speed and pressure together: start slow and pressed, then cover the last stretch quickly while the pressure falls to almost nothing. It gives the tapered tail of a blade of grass or a twig.
- **For a large wash, time matters for a different reason:** it must be finished before its first rows lose their shine. Go fast (250 to 300) with a mop or flat wash; it will not break.

### Combining them

- **Dry-brush:** laid over (angle 80), light pressure, fairly fast, with a brush that is not full. Any one of these helps; together they are reliable.
- **A leaf or petal:** `round` or `filbert`, land upright and light, press as you travel, lift off quickly.
- **A crisp plane:** `flat`, usual angle, steady pressure, twist 0, moderate speed.
- **A line that thickens round a bend:** `flat` or `dagger`, twist held near 90 on the straight and near 0 through the bend.

## Paint strength and the brush load

- **Strength** is the sum of the pigment amounts in a load. About 0.3 is a pale wash, 1 a middle tone, 2 to 3 strong. Above about 3.5 the paint is thick: the brush holds less water, skips on the grain and runs out sooner. That is how to dry-brush on purpose, and how a "solid" dark comes out broken by accident.
- **For a solid dark, use two layers of moderate paint** with `dry` between them, not one layer of paste.
- **A brush runs out.** A long stroke from a small brush ends dry and streaky. Reload before each large stroke; `status` shows how full the brush is.
- **Greys and darks are mixed, not bought.** A blue with an earth (cobalt blue with burnt sienna, ultramarine with burnt umber) gives a grey that leans warm or cool as you change the proportion. Ivory black alone looks dead.
- **Colours mix on the paper as well as in the brush.** Two wet colours laid side by side merge where they meet, which is livelier than mixing them first.

## Techniques that work here

- **Graded wash:** rows from the top, each load a little weaker (or warmer) than the last, all laid before the first loses its shine.
- **Soft edge on one side:** lay the stroke, then run a clean brush loaded with little water (`"pigments": {}, "water": 0.4`) along the edge you want softened.
- **Form on a cylinder or a box:** the shadow tone down the shadow side right to the edge, softened inward as above.
- **Dark into wet:** while a shape is still shiny, touch a stronger mix into its shadow side and let it spread.
- **Varied masses (foliage, scrub):** many short touches of two or three related colours laid wet into each other, the outer ones from a nearly dry brush for a ragged edge.
- **Runs:** `tilt` the sheet and feed the lower edge of a wet passage with thin paint; set the tilt back to zero afterwards.
- **Lifting:** `blot` takes up most of the water and loose pigment under it. It only works while the paint is wet.
- **Fine lines:** a rigger of size about 1, moderate strength, full water. Reload for each line.
- **Lights you could not reserve:** `opaque_white` at strength about 4.5, in two coats, as the very last thing. It is for glints and small figures, not for repairs.

## Looking, and judging what you see

After each pass, look, and ask in this order:

1. Is the paper where I think it is (wet, moist, dry)? Check before the next pass, not after.
2. Do the values read? Use `look --view value`. If the picture works in grey, colour will not sink it.
3. Did the shape land where I planned? Use `look --region x0,y0,x1,y1 --grid` to read coordinates off the sheet.
4. Is the next step still the one I planned, or has the painting changed what it needs?

When something goes wrong you cannot remove it. You can glaze over it once dry, lose it in a darker shape, or accept it. Deciding which is part of painting; reaching for a fix that the medium does not have is not.

## Before you finish

- Squint at the whole sheet: the lightest light and darkest dark should be where you meant them.
- Stop earlier than feels natural. Every extra stroke on a finished passage costs freshness.
- `finish` dries the sheet, writes `painting.png` and the time-lapse, and closes the painting for good.
- Note what you would do differently next time. You will not remember this painting in the next session unless you write it down.

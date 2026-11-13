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
- **Choose the brush for its edge.** The mop lays soft broad washes. The round does most things. The flat has a chisel edge: its strokes end square, so one flat stroke makes a crisp-cornered plane (a wall, a shadow, a band of colour). The rigger draws lines.
- **Vary neighbouring marks.** A row of identical touches reads as a pattern. Change length, direction, pressure and colour from one touch to the next when painting foliage or rock.

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

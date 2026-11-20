---
name: paint-watercolour
description: Paint a watercolour with the `watercolor` harness (github.com/timbrinded/watercolour) - a simulated sheet, brushes and paint driven stroke by stroke with no undo. Use this whenever asked to paint, sketch, illustrate or make a picture, landscape, study or copy with the watercolour rig, to continue or finish a painting session, or to judge why a painting made with it looks stiff, flat or muddy, even if the request never says "watercolor" or names the command.
metadata:
  version: "0.10.0"
---

# Painting with the watercolour harness

You are the painter. The harness gives you paper, water, pigment and brushes that behave like the real things, and takes away the one thing software usually gives you: undo. Whatever reaches the sheet stays there. That is the point of the tool, so paint like someone who cannot take a stroke back: plan, start pale, look often, and commit.

Supporting references in this skill directory:

- `references/actions.md` — Read before writing any pass: the exact fields of every action, the nineteen brush heads, the nine hairs, and the paint box.
- `references/wet-in-wet.md` — Read before any passage where colours must run into one another or an edge must be softened: charging a colour into a wet wash, a variegated wash inside a crisp shape, blending a join, pulling out an edge, lifting a pale line. It gives the film depths and brush fullness each one needs.
- `references/glazing-and-economy.md` — Read when planning transparent layered washes, painting white or pale subjects against bare paper, working to a tight stroke count, or diagnosing why an attempt looks opaque, stripey, or overworked.
- `references/water.md` — Read before painting the sea, waves, surf, foam, spray or a wet beach, from an idea or from a photograph: which method suits each passage (row washes, traced troughs, crisp foam layers, negative lace, masking fluid), in what order, and what failed.
- `references/faces-and-detail.md` — Read before painting portraits, faces, figures, or intricate focal passages: bare-paper skin washes, proportion and plumb-line checks, brush-radius inset, eye and expression mechanics, negative-space noses and mouths, hair masses, crisp adjacent trim, and the crisp marks drawn last over finished washes.
- `references/copying-a-reference.md` — Read when the painting must match a picture that already exists (a copy, a study after another painter, a likeness from a photograph): measuring the reference, solving its colours from the pigment table, calibrating how dark a load dries, and laying what the sheet still lacks in measured layers. It uses the scripts in `scripts/`, which also grid a reference, preview a pass over it and score a sheet against it.
- `references/styles/` — A style is a different manner from this skill's own, studied from one painter. Read a style file only when the brief asks for that style; see "The skill's manner, and styles on request" below.

## Getting the command

The harness is the repository https://github.com/timbrinded/watercolour. Before painting, find out how to run it, in this order:

1. If you are inside a clone of the repository (it has `src/watercolor/`), run `uv sync` once and put `uv run` before every command: `uv run watercolor ...`. That runs the clone's own version, which may be newer than an installed one.
2. Otherwise, if `watercolor --help` works, the command is installed; use it as written below, from any directory.
3. Otherwise it is not available. Tell the user, and offer to install it with `uv tool install git+https://github.com/timbrinded/watercolour`. It needs Python 3.13 or newer and `ffmpeg`, and the first install downloads PyTorch, which is several gigabytes, so do not start it without saying so.

Check the version with `watercolor --version`. Reading wetness as numbers (`look --at`), waiting on the film, and the `drain` action need 0.5.0 or later; if the flag is refused or the version is older, say so and offer `uv tool upgrade watercolor`. Carrying on after a command is cut short needs 0.5.2 or later: on an older version a `paint` killed part-way leaves the painting refusing every later command, so upgrade before painting anything that matters. Water showing as light in the picture needs 0.6.0 or later: on an older version a wet wash and a dry one look almost alike. The lit rim of a pool that stands proud needs 0.7.0. Masking fluid (`mask`, `unmask`) needs 0.8.0. The pen and its inks, fixative (`fix`), hot-press and rough paper (`--support`), a printed ground and the paints that must be named in `--palette` need 0.10.0.

A painting is just a directory, so it can live anywhere; `paintings/` in the current directory is the usual place. The brush guide with a chart of every mark is `docs/brushes.md` in the repository.

## The loop

```bash
watercolor new paintings/<name> --prompt "<the brief>" --size 768 --height 544
watercolor paint paintings/<name> pass.json     # a JSON list of actions
watercolor look paintings/<name> --grid         # then Read the picture it names
watercolor status paintings/<name>
watercolor finish paintings/<name>              # dries, exports painting.png and timelapse.mp4
```

- A painting is a directory and is never started over. A new attempt is a new directory.
- `paint` checks the whole pass before any of it touches the sheet. A pass with a mistake in it is refused whole, so a refusal costs nothing.
- `look` is free and changes nothing. Look after every pass, and always Read the image: you cannot judge a wash from the numbers you sent.
- Coordinates are pixels, x to the right and y downward, origin top left. A `look` image can be an enlargement of the sheet (a 360 pixel sheet gives a 720 pixel look), so divide by its width over the sheet's width before reading a coordinate or sampling a colour off it; `scripts/measure.py` does this.
- Painting takes real time: about half a second of computing for every second painted on a sheet of this size with a graphics card, and `dry` and `finish` each paint five minutes or more. A pass that ends in `dry` therefore takes three to five minutes. Each stroke also costs a sixth to a third of a second however short it is (the more paints in the palette the more, because the painting is saved after every action), so a pass of 2,000 small strokes takes six to twelve minutes. `load` takes no time on the sheet's clock, so a wash of many short strokes, each with its own mix, stays wet as easily as one of a few long ones.
- **A `paint` or `finish` command that is cut short can be given again.** The painting is saved as each action ends and every few seconds through a long wait, so a command killed part-way, by a tool's timeout for instance, loses only the action it was in the middle of. Run exactly the same command again and it carries on from where it stopped: actions already on the sheet are not repeated, and a wait runs only for the time it still had left. `status` shows how far the pass got, under `interrupted_pass`. Do not edit the actions file first: a changed pass counts as a new one and starts from its first action, on top of whatever the interrupted pass had already laid. To abandon the rest of an interrupted pass, send a different pass. Still give these two commands a timeout of several minutes, or run them in the background, because every restart costs some seconds and whatever was computed since the last save.
- **One command at a time works on a painting.** A second is refused with `another command is at work on this painting` until the first ends, so wait for a `paint` running in the background before you look.

## Plan before the first stroke

You get one go at each passage, so decide these first:

1. **The idea, in a sentence.** What the picture is of (its subject, what the subject is doing or holding, what lies behind), the feeling it should carry, and the one manner it will be painted in: this skill's own, unless the brief asks for a style. Everything after this is judged against that sentence, and detail that does not serve it is left out.
2. **A few paints.** Choose three to five pigments and start the painting with `--palette` naming only those (plus `opaque_white` if you will need final lights), so nothing else can be loaded. Every mix then comes from the same few paints and the picture holds together. A different pigment for each object does the opposite.
3. **The size of the sheet.** Give the focal subject enough pixels. A face needs to be about 200 pixels across before eyes and a mouth can be painted into it; at 90 it cannot hold them. If the thing that matters most would come out smaller than that, use a larger sheet or crop closer.
4. **The value plan.** Where is the lightest light, which is bare paper, and where is the darkest dark? Three or four values are enough.
5. **The order.** Pale and broad first, dark and small last: drawing, big light washes, middle shapes, darks, fine detail, then opaque white for the few lights you could not save.
6. **The layout, in numbers.** Write down the coordinates of the main shapes before painting. If you are working from a reference, measure it (put a labelled grid over it with `scripts/reference_grid.py`) rather than judging by eye; by-eye layouts drift further than you expect. Values and colours judged by eye drift as far: sample them (`scripts/measure.py`). If the painting must match the reference, do not plan it stroke by stroke at all; `references/copying-a-reference.md` has the method that worked after that one failed.
7. **What stays white.** A white shape is made by painting around it, so the washes next to it must be planned to stop at its edge, or, on 0.8.0 or later, by masking it first: lay masking fluid on the dry paper (`mask`), wash freely over it, and rub it away once dry (`unmask`). Paint around large, simple shapes; mask what a wash must cross, what is too small or too fine to paint around (eye whites, catchlights, strands, rigging), and a light that must keep a tint already laid.
8. **How few strokes will carry it.** Aim for roughly 50 to 75 strokes for a single subject, with 15 to 20 in the first wet wash. Look after that base pass: if the light and big values do not already read, adding a hundred small strokes on top will only muddy the sheet.

**Plan coverage, not centre lines.** A wash is an area. A shadow planned as a stroke for the nose and a stroke for the cheek paints as a stick figure, because a stroke at pressure 0.9 is only about twice its `size` wide. Before a pass with shapes that must be filled or contours that must be met, draw it over the reference or the last look with `scripts/preview_pass.py` and check that every shape is covered and every contour stroke sits on the right side of its contour.

**Rehearse the hard passage before the sheet that matters.** Paint the one or two things you are least sure of (an eye, a hand, the sky, a blend of two colours) on small sheets of their own, as many times as it takes to get them. A study costs a few minutes; a passage that fails on the full sheet costs the sheet. For a single mix or stroke, the scrap sheet is enough (`"sheet": "scrap"`); it does not count against the stroke budget.

## The skill's manner, and styles on request

Everything in this file describes one manner: transparent washes in a high key, the light carried by bare paper, few strokes, colours meeting wet in wet. Paint in it unless the brief asks for something else.

A style file in `references/styles/` describes a different manner, with defaults of its own that override some of this file's. Read one only when the brief asks for it: it names the style or the painter it is studied from, or it asks for what the style is. A brief of the same kind is not a request for a style; a portrait is painted in this skill's manner unless the brief asks for more. Keep to one manner in a painting: do not borrow one style's marks for a painting in another.

| Style | Reach for it when the brief asks for | File |
|---|---|---|
| Layered-shape chiaroscuro, after Donna Stiles | A close, dramatic, low-key portrait built as a mosaic of hard-edged tonal shapes, or names her or the style | `references/styles/layered-shape-chiaroscuro.md` |

## Water is the clock

Everything depends on how wet the paper is where your brush lands, and wetness is a scale, not a set of states. The harness gives it as two numbers: `film`, the depth of water standing on the surface, and `paper`, how full the sheet itself is, from 0 to 1. Read them where you are about to paint, before you paint there:

```bash
watercolor look paintings/<name> --view wetness --at 240,180 --at 400,300
```

| Where the brush lands | What a new stroke does there |
|---|---|
| **Paper dry, no film** | Keeps a hard edge, and dries darker at that edge than in its middle. Use for crisp shapes and glazes. |
| **Film of 0.5 and deeper** (a wash just laid, or laid twice) | Spreads to twice its width or more and blends softly into what is there; strong paint is diluted to half its strength or less. Wet-in-wet at its loosest. |
| **Film of 0.15 to 0.5** (the shine is still on) | Spreads to about one and a half times its width and holds a soft edge. Good for soft shadows, for deepening a wash and for accents that must stay put. |
| **Film under about 0.1** (the shine is going) | Dangerous. Paint or water from a brush wetter than the paper floods back into the drying wash and leaves a bloom. Wanted sometimes, a ruined sky otherwise. |
| **Paper damp, no film** (`paper` above about 0.6) | The same danger, with a ragged edge. Wait for `dry`. |

`status` also names four stages (shiny, moist, damp, dry). They are only landmarks on these scales: shiny is a film over 0.15, moist a thinner one, damp is no film on paper more than 0.6 full. Act on the numbers.

**The picture shows the water.** The colour picture is taken from straight above with a small lamp beside the camera, and water mirrors that lamp wherever its surface is tilted. So every colour `look`, and the one `paint` returns, shows where the sheet is wet:

| In the picture | What it means |
|---|---|
| A bright line along the upper-left edge of a wash, or a soft bright patch on it, with the colour clear between | A deep film: the shine is on, and wet-in-wet will work here. |
| Many fine bright points scattered over a wash | A thin film breaking up over the grain: the dangerous stage. |
| A blob with a brighter rim on its lower right and a darker one on its upper left | Water standing proud of dry paper: a pool with a film over about 1.2 and a steep edge. The same water on a wet wash spreads level and shows no rim. |
| No light at all | No film. The paper may still be damp, which the picture does not show; read `paper` with `--at`. |

The lights are water, not paint. They go as the film goes, a finished painting has none, and the value and wetness views leave them out. The picture tells a deep film from a thin one and from none. It does not tell 0.3 from 0.6, so read the depth with `--at` where the amount matters.

**The sheet's clock runs only while an action is carried out.** A wash does not dry while you look at it or think. So when the next strokes depend on the film (a charge, a blend, a softened edge), end the pass while the wash is still wet, look at the picture that comes back, and send those strokes as the next pass. A pass that ends in `dry` returns a picture with no water in it, and by then the wet work can no longer be done.

A wash laid once with a round starts with a film of about 0.5 (about 0.8 from a mop) and is down to 0.12 in about a minute; laid twice over it starts at 0.6 to 1.2 and lasts a minute and a half or more. Strokes take time to make, and that time comes out of it. So:

- **Lay a wash quickly.** Use a big brush, fast strokes (`"speed": 280`), and overlapping rows about one brush radius apart. Rows that only just touch leave a line between them: spaced at the full painted width they left a hairline of dry paper that pigment would not cross, and spaced at 1.4 times `size` or closer they closed every time.
- **Time the next stroke by the film, not by a guess at the seconds.** `{"action": "wait", "seconds": 300, "at": [240, 180], "film": 0.12}` waits until the film at that point has thinned to 0.12, or 300 seconds at most. It is the painter watching the shine go off.
- **Do not go back into a wash whose film is under about 0.1** with a wet brush unless you want the bloom.
- **Use `{"action": "dry"}` before a glaze or a crisp shape.**
- **The brush has a scale too.** `{"action": "drain", "water": 0.6}` touches it to a cloth: it keeps its colour and loses fullness. Full, it floods; at about 0.6 it gives colour to a wet wash and blends a join; at about 0.45 it pulls out an edge; at 0.2 it lifts paint. The brush must never be wetter than the paper it touches. `references/wet-in-wet.md` has the method for each.

## Make each mark with a brush that fits it

The commonest failure is building shapes from many small strokes. They come out stiff and stair-stepped, like cut paper. A painter lays a shape in one stroke of a brush as wide as the shape.

- **Size the brush to the shape.** `size` is the radius in pixels (up to 80), so a band 20 pixels deep is one stroke of a size 10 brush, not six strokes of a size 3, and the body of a subject on a 768 to 960 pixel sheet is one sweep of an `oval_wash` or `mop` of size 35 to 55. Every stroke on dry paper dries with a darker capillary ring around its perimeter: five medium strokes inside one shadow leave ten internal seams, whereas one wide stroke leaves a single crisp edge along a real turn of form.
- **Know how wide the mark is.** On dry paper a `round` paints about 1.35 times its `size` at pressure 0.5 and twice its `size` at 0.9; a `mop` or `oval_wash` 1.8 and 2.1 times; a `flat` 2.1 times at any pressure. So the centre line of a stroke at pressure 0.9 runs `size` pixels inside the edge it is to meet. The spot a round leaves at a single point grows with pressure: its radius is about 0.6 times `size` at pressure 0.5, 0.77 times at the default 0.7, and equal to `size` at 1.0. For a round spot of a known radius, such as an iris, set `size` to that radius and press fully: a dab at pressure 1.0, or a stroke two to four pixels long at pressure 1.0, slowly (`"speed": 20`).
- **Use pressure to shape the stroke.** Each point is `[x, y, pressure]`. A round brush is a fifth of its width at no pressure and full width at 1.0, so `[[x0,y0,0.3],[x1,y1,1.0],[x2,y2,0.4]]` with `"smooth": true` swells and tapers like a leaf. When glazing on dry paper, start and end at light pressure (`0.10` to `0.15` on a `cats_tongue`, `sword`, or `round`) so the ends feather to a point rather than stamp a bevel. This is where expression comes from.
- **Choose the head for its edge.** The mop lays soft broad washes. The round does most things. The flat has a chisel edge: its strokes end square, so one flat stroke makes a crisp-cornered plane (a wall, a shadow, a band of colour). A filbert ends in a curve, an angular head on a slant, a comber draws several lines at once, and the rigger draws one.
- **Choose the hair for how far it must carry.** Squirrel holds more than twice what sable does and leaves a soft edge, so it suits washes; sable keeps a point and a crisp edge; a golden synthetic runs dry and streaks soonest, which is useful for dry-brush and a nuisance for a wash.
- **Vary neighbouring marks.** A row of identical touches reads as a pattern. Change length, direction, pressure and colour from one touch to the next when painting foliage or rock. Vary their spacing as well: towers, posts or trees set at even intervals read as a fence, where overlapping some and leaving wider gaps between others reads as a place.

## Edges, and what makes a thing read

- **Hard edges belong to things; soft edges belong to light.** The outline of an object, the overlap of one thing in front of another and a cast shadow get a crisp edge, laid on dry paper. Shadow turning round a form, distance and air get a soft one, laid wet-in-wet or softened along one side. A tonal map of a photograph shows where the shadow is, not where the hard edges go: painted as hard-edged islands of tone it gives a picture by numbers.
- **Neighbouring things meet.** Where two objects touch, their washes touch or overlap. A hairline of paper between two shapes is fine; a gap a brush wide reads as a hole, and white paper is for light, not for keeping things apart. When you inset a shape's path by the brush radius, inset it only where it borders bare paper.
- **A group of small things is one wash first.** Roofs, stones, a skyline, a mass of foliage: lay one pale wash over the whole group, `dry`, then paint the darks between and beneath its members. Painted one at a time they keep white cracks between them, and patching the cracks afterwards leaves rings.
- **A thing reads when it has a light side, a dark side and at least one crisp edge.** Soft pale washes everywhere read as mist, however well each is laid. Keep them for the distance, and give the foreground the strongest contrast, the hardest edges and the roughest texture (dry-brush set against smooth wash).

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

- **Dry-brush:** laid over (angle 80), light pressure, fairly fast, with a brush that is not full. Any one of these helps; together they are reliable. Try it on the scrap sheet first, because the mark depends on all of these together. A round at angle 50, pressure 0.75, fullness 0.45, strength 5, speed 220 left a clear broken streak. Laid over to 80 or 90 with the rest unchanged, the streak was a third as strong; with light pressure (0.3) as well, it left only specks too pale to read; and from a full brush (0.9) the mark was not broken at all. For a strand of hair that must read as a line, a thin wet stroke of a small round (size 2.4, pressure 0.2 to 0.9 to 0.2) was more dependable.
- **A leaf or petal:** `round` or `filbert`, land upright and light, press as you travel, lift off quickly.
- **A crisp plane:** `flat`, usual angle, steady pressure, twist 0, moderate speed.
- **A line that thickens round a bend:** `flat` or `dagger`, twist held near 90 on the straight and near 0 through the bend.

## Paint strength and the brush load

- **Strength** is the sum of the pigment amounts in a load, and sets **concentration per unit of water** — raising `water` to `1.0` fills the reservoir with more of that mix rather than diluting it. Watercolour gets its life from the white of the sheet shining up through thin layers, not from covering power. Keep first washes around `0.25` to `0.65` for landscapes and bold subjects (**`0.05` to `0.15` for sunlit skin and bare-paper portraits**), and dry glazes around `0.75` to `1.25` (`0.20` to `0.45` on pale skin): the paper grain stays luminous and each transparent overlap builds depth like stained glass. Reserve `1.4` to `2.0` for small focal darks in deep crevices. Broad passages above `2.5` smother the paper and look like gouache or acrylic; above `3.5` the paint is thick paste, holds less water, skips on the grain and runs out sooner.
- **For a rich dark, layer transparent washes** (`0.5` then `1.0`) with `dry` between them and touch `1.5` to `1.8` only into the deepest core — not one coat of paste.
- **Those ranges are for a picture in a high key. Where a value must be matched, measure.** How dark a load dries depends on the brush and the method as much as on its strength. Measured on 0.5.2 with a cobalt and umber blue: rows of a wash brush on dry paper dried at value 0.44, 0.27 and 0.10 for strengths 1.5, 3 and 6, and two layers at 3 dried a little darker still, at 0.08; the same paint dropped into clear water dried far lighter than on dry paper, by an amount that depended on how much was dropped as well as on its strength (0.63 to 0.80 at strength 2.5, 0.35 to 0.64 at 7); a round of size 1.6 laid about three quarters of the tone that a round of 7 did from the same load, and a round of 7 about two thirds of what a large wash brush did; and one stroke lays less than a filled wash. A brown face in strong sunlight needed a shadow wash of 2.6, where pale skin takes 0.05 to 0.15. A deposit chart on a small sheet (the mix at three strengths, laid the way it will be laid) takes a minute; `references/copying-a-reference.md` has the tables.
- **A brush runs out.** A long stroke from a small brush ends dry and streaky. Reload before each large stroke; `status` shows how full the brush is.
- **Greys and darks are mixed, not bought.** A blue with an earth (cobalt blue with burnt sienna, ultramarine with burnt umber) gives a grey that leans warm or cool as you change the proportion. Ivory black alone looks dead. For the dark of a pupil or a lash line, burnt umber 3 to French ultramarine 1.2; with more ultramarine than that a thin stroke dries violet.
- **A colour can be solved, not guessed.** Each paint darkens red, green and blue in fixed proportions (its absorption in `watercolor/pigments.py`), so the ratio of `-ln(channel / paper)` across the three channels of a sampled colour says which paints give it. A blue that looked like French ultramarine solved to cobalt blue 5 to burnt umber 1; ultramarine dried violet beside it. The worked example is in `references/copying-a-reference.md`.
- **A solved mix is for bare paper.** Over a wash that is already there, solve what the sheet still lacks: the sampled colour's absorbance less the sheet's at that place. Accents solved for bare paper and laid over a first wash took one landscape from 0.065 to 0.081 away from its reference in value, and every one of them had to be painted again on a new sheet.
- **Colours mix on the paper as well as in the brush.** Two wet colours laid side by side merge where they meet, which is livelier than mixing them first.

## Techniques that work here

- **Graded wash:** rows from the top, each load a little weaker (or warmer) than the last, all laid before the first loses its shine.
- **A sky:** one wet pass from edge to edge, in three or four broad strokes of a large mop, strongest at the top, and then left alone. Going back to wet part of it again dries with a watermark across the sky. For a warm glow under the blue, lay that first as its own pale graded wash and `dry` it, so that the blue glazes over it and does not mix with it into green; then wet the whole sky with clear water and lay the blue into that. Clouds are lifted out of the wet wash with `blot` (radius about 60, their edges then softened with a mop drained to 0.55) or left as bare paper; clouds painted on as extra patches make a blotchy sky. French ultramarine and cerulean gather into specks in a wash this deep, so use cobalt blue where the sky should be smooth.
- **Cutting in round a shape, then filling:** cut the edge with a small brush and flood the rest from it at once, a stretch at a time, while the cut edge still has a film on it (read it: 0.3 or more). An edge left to dry before the fill reaches it blooms at the join, and an edge tidied afterwards with strokes over dry paint dries with a darker tramline along it. Wetting the area with clear water first also works, but stop the water exactly at any contour that must stay crisp: carried past it, it turns that edge to fog.
- **Soft edge on one side:** lay the stroke, then run a clean brush drained to about 0.45 (`"pigments": {}, "water": 0.45`) along the edge you want softened, just touching it. Repeat a little further out for a longer fade.
- **Form on a cylinder or a box:** the shadow tone down the shadow side right to the edge, softened inward as above.
- **Dark into wet (charging):** while a shape still has a film of 0.3 or more, touch a stronger mix into it with a brush drained to 0.6, in two or three strokes, and leave it to spread. Do not stir. Deeper film, further spread; see `references/wet-in-wet.md`.
- **Several colours in one shape (a variegated wash):** lay the whole shape pale and deep, then each colour over its own part as patches that touch, then a few much stronger touches once the film is down to 0.3. The full method, with a leaf as its example, is in `references/wet-in-wet.md`.
- **Varied masses (foliage, scrub):** many short touches of two or three related colours laid wet into each other, the outer ones from a nearly dry brush for a ragged edge.
- **Gravity pooling and runs:** a gentle `tilt` (`0.05` to `0.08`) on a high-water pale wash (`"water": 0.80` to `0.84`) drains the sunlit upper edge airy while settling pigment cleanly toward the shadow side, often saving a separate clear-water grid pass. Tilts above `0.18` break into visible vertical runs and drips. A tilt moves everything that is wet anywhere on the sheet, so tilt only while the passages that must stay put (a face, a crisp edge) are dry or not yet painted. Set the tilt back to zero before drying.
- **Contact shadow into a wet ground wash:** sweep a fast `hake` ground stroke first and touch the darker contact shadow under feet, paws, or a base directly into it while it is still wet; laid onto dry paper later, a narrow contact line dries as an isolated grey worm.
- **Lifting:** a brush drained to 0.2, twice along the same line while the film is between 0.3 and 0.1, takes off a third or more of the colour: veins, a highlight on water, the light side of a stem. `blot` takes up most of the water and loose pigment under it. Neither works once the film has gone.
- **Fine lines:** a rigger of size about 1, moderate strength, full water. Reload for each line.
- **Lights you could not reserve:** `opaque_white` at strength about 4.5, in two coats, as the very last thing. It is for glints and small figures, not for repairs. A fine white line (a whisker, a thread) needs a rigger of size 1.3 or more and two coats, and even then it dries pale grey over a dark wash, not white, and over a middle value it does not show at all; a finer brush or a single coat barely shows, and drawing it slowly does not help. Where a fine light matters, plan to leave it as paper. Laid over dark lines that are already drawn (teeth inside a drawn mouth), two coats dried a middle grey tinted by the dark beneath (value about 0.6), not white; laid on dry pale washes before the darks beside it are drawn (the white of an eye each side of the iris), it stayed white. On 0.8.0 or later, mask such lights first instead: under one dark wash (value 0.27), masked shapes stayed at paper (0.96) where three coats of opaque white reached 0.65, and a masked line 0.8 pixels in radius read at 0.64 where an opaque white line of the same size reached 0.34.
- **Paint stops at the edge of water.** Colour dropped into a film travels to the film's boundary and dries there as a crisp edge. A bed of clear water with an accidental straight side therefore shows as a hard line across a soft passage, and a bed laid in a deliberate shape gives a crisp outline with a soft inside. `references/glazing-and-economy.md` uses this to reserve a white shape.
- **A wood, a hedge or a crown of leaves is one connected wash.** Lay it wet with strokes that overlap, break its outline with small touches while it is wet, and charge its darks into it. Touches laid one by one on dry paper stay separate dots or leaf shapes however many there are, and read as a pattern, not as foliage. Narrow things that need a crisp edge (a hedgerow, a line of trees) are the exception: wet-in-wet spreads them well beyond their width, so draw them on dry paper as one unbroken stroke of varying pressure.
- **Clear water and drops are for small or broken passages.** Over a large area that must be covered, a few drops into a bed of water dry as islands with paper between them, and never darker than a middle value. Lay a covered, varied background as rows of colour, each row mixed for its place and laid while the last is wet.

## Faces, likeness and fine detail

Portraits and close detail magnify small errors in value, proportion and brush width that a landscape forgives. Read `references/faces-and-detail.md` before starting one; the core rules are:

- **Let bare paper carry the lit skin.** Leave 60 to 80% of a sunlit face unpainted — forehead, nose bridge and ball, lit cheekbone, lip highlight, chin boss — and link the shaded side in one whisper-pale wash (`0.06` to `0.15`) so the viewer's eye completes the form. These figures are for pale skin in a high key; from a reference, sample first. What reads as white there is often a pale tint that should be painted, and the shadow side of a brown face in strong light needed a wash of 2.6.
- **Lock one axis, drop plumb lines, and slim close-up perspective.** Rotate reference measurements to a single cranial axis before transferring points. Drop vertical plumb lines from the pupils rather than trusting high-contrast tonal maps where adjacent shadows merge (lip corners stop near the pupils, with clean cheek space before any smile fold). Close-up lenses widen faces and bare white cheeks expand optically into a white margin; match long-lens skull width (`~0.75` to `0.85×` horizontal on close-up photos) and contain the lit temple or cheekbone with a whisper `0.06` to `0.09` inward-softened turning wash or external counterchange.
- **Inset for the brush radius, and flood or one-side-soften concave planes.** Tracing *on* a jawline or nose edge with a `size 24` brush bloats the form by `24` pixels on every side. Inset paths by the effective radius; for tight concave shadow shapes, trace the inset boundary with a pointed squirrel `round` (`size 7` to `10`) and flood the interior within the shiny window, or lay a one-sided dry glaze and immediately melt its form-turning edge with damp clean hair (`"pigments": {}, "water": 0.30`).
- **Save peak contrast for the eyes, and drive expression with geometry.** Reserve your deepest dark (`1.3` to `2.0` in two dried passes) meeting bare paper or a pinpoint `size 1.5` `opaque_white` glint strictly for the pupils and upper lash blades, keeping nostrils and lip fissures a step softer (`0.45` to `0.85`). Expression comes from a few pixels of lid, iris, pupil and brow geometry — not from heavier washes across the face.

## Looking, and judging what you see

After each pass, look, and ask in this order:

1. Is the paper as wet as I think it is? The picture shows where the film is (a bright line or patch on a deep film, fine points on a thin one, nothing where there is none). Read its depth where the next strokes go (`look --at x,y`) before the pass, not after.
2. Do the values read? Use `look --view value`. If the picture works in grey, colour will not sink it.
3. Did the shape land where I planned? Use `look --region x0,y0,x1,y1 --grid` to read coordinates off the sheet.
4. Is the next step still the one I planned, or has the painting changed what it needs?
5. Does the sheet still say what the idea said: one subject, one manner, the feeling you meant?

When there is a reference, score the sheet against it as well: `scripts/value_difference.py` gives a map of where the sheet is too dark and too light, a figure for tone and a figure for how far its edges fall where the reference's do. Fix the largest area in the map first; one wrong wash outweighs every detail. The figures do not see texture (a sky of rimmed patches scores like a sky in one wash), so look at the sheet enlarged as well. A fault you can name is a fault to work on in the next pass or the next sheet, not one to list at the end.

When something goes wrong you cannot remove it. You can glaze over it once dry, lose it in a darker shape, or accept it. Deciding which is part of painting; reaching for a fix that the medium does not have is not.

The same holds across attempts. When a picture has been through several sheets, each answering the criticisms of the last, look at the newest one whole. Corrections applied one by one can leave a painting in which every fault was answered and nothing holds together: several manners at once, detail without a subject. Do not patch that again. Go back to the sentence you started with and paint a fresh sheet from it, keeping what the earlier sheets taught about how, and dropping what they accumulated.

## Before you finish

- Squint at the whole sheet: the lightest light and darkest dark should be where you meant them.
- Stop earlier than feels natural. Every extra stroke on a finished passage costs freshness.
- `finish` dries the sheet, writes `painting.png` and the time-lapse, and closes the painting for good.
- Note what you would do differently next time. You will not remember this painting in the next session unless you write it down.

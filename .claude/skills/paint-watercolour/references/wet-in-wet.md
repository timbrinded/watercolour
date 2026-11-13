# Wet in wet: charging, variegated washes and blending

Read this before any passage where colours must run into each other: a sky, a variegated leaf or petal, a colour touched into a wet wash, an edge softened or pulled out, a pale line lifted.

Everything here turns on two things you control: how deep the film of water on the paper is when the brush lands, and how full the brush is. Both are continuous scales. Measure them; do not guess them.

## The paper: a film of water with a depth

The harness reports wetness as two numbers, not as named states.

- **`film`** is the depth of water standing on the surface. Rows of a full round leave about 0.5, rows of a mop or wash brush about 0.8. A second pass over the same rows makes it 0.6 (a small round) to 1.2 (a mop). It thins as the paper drinks it and the air takes it.
- **`paper`** is how full the sheet itself is, from 0 (dry) to 1 (it can take up no more).

Three ways to read them:

```bash
watercolor look paintings/<name> --view wetness --at 240,180 --at 400,300
```

prints `film` and `paper` at each point and saves a picture with its scale beneath it (pale blue is a trace of film, deep blue about 0.8, violet 1.5; bare damp paper turns from grey to green as it fills). `status` gives the film at its deepest and at its usual depth. And a `wait` can watch the film for you:

```json
{"action": "wait", "seconds": 300, "at": [240, 180], "film": 0.12}
```

ends as soon as the film at that point is no deeper than 0.12. This is the painter watching the shine go off a wash. Use it instead of guessing seconds: a leaf-sized wash laid twice over takes about a minute and a half to thin from 0.6 to 0.12, and strokes you make in the meantime use that time up.

What one charge of strong paint does at each depth of film (see the chart `charging_by_wetness` in the repository's `docs/images/`):

| Film when the brush lands | What the charge does |
|---|---|
| **0.7 and deeper** | Spreads furthest, to about two and a half times the width of the stroke, with the softest edge. It is also diluted most: it dries at well under half the strength the same stroke has on dry paper. Only at this depth does a granulating paint gather into specks. |
| **about 0.5** | Spreads to about twice the stroke's width. The usual depth for a variegated wash. |
| **0.15 to 0.3** | Spreads to about one and a half times its width, holds a soft edge and keeps more of its strength. Use it for a darker accent that must stay where it is put. |
| **0.05 and thinner** | The edge turns blotchy and uneven. If the brush is wetter than the paper, its water runs back into the wash and leaves a bloom. |
| **none, paper damp** | A bloom with a ragged edge. Wanted sometimes; otherwise wait for dry. |
| **none, paper dry** | A hard edge at the full strength of the paint. Thick paint on a brush that is not full skips on the grain. |

## The brush: how full it is

`drain` touches the brush to a cloth. It keeps its colour and its strength and loses only fullness:

```json
{"action": "load", "brush": "round", "size": 9, "pigments": {"cerulean_blue": 4.0, "cobalt_blue": 2.5}, "water": 1.0},
{"action": "drain", "water": 0.6}
```

Loading with `"water": 0.6` does the same for a fresh load; `drain` is the only way to do it to a brush that already holds paint.

| Fullness | What the brush does to wet paint |
|---|---|
| **1.0, full** | Lays water. In a wash thinner than itself it floods and blooms. Right for laying the wash, wrong for touching into it. |
| **about 0.6, damp** | Gives its colour to the film without flooding it, and carries wet paint on its tip: stroked across a join it draws each colour into the other. The brush for charging and for blending a join. |
| **about 0.45** | Pulls paint out of the edge of a wet stroke into a fade. |
| **0.2 and less, drained** | Draws paint up and adds no water of its own to a wash that still has a film. It lifts a pale line or shape out of the wash, as long as that film is still there. |

The rule that covers all of it: **the brush must not be wetter than the paper it touches.** Paint for a charge should be thicker than the wash it goes into (strength 3 to 6 into a wash of 0.3 to 0.6) on a brush at about 0.6.

Before version 0.5 thick paint on a drained brush skipped on the grain even on a wet wash and left beads. It no longer does: where a film stands on the paper the brush meets it across its whole width.

## Charging a colour into a wet wash

The picture to aim for: a wash of one colour with a second colour spreading into it on its own, a soft band of their mixture between them, and a grainy front where the second colour thins out.

1. **Lay the wash deep.** Rows of a mop, oval wash or flat wash, then the same rows again at once. Read the film: 0.8 to 1.2 is right for a charge that should travel.
2. **Load the second colour strong and drain the brush to 0.6.** A granulating paint (cerulean blue, French ultramarine, burnt umber) dries as fine dark specks over the blend, thinning toward its front, but only in a film deeper than about 0.7; a staining paint (phthalo green, quinacridone rose) gives a smooth blend at any depth.
3. **Touch it in with two to four strokes and stop.** Each load gives up most of its colour in one stroke, so reload for each. Spread the strokes over the area the colour is to fill: put side by side they leave most of it as the mixture, which is the look of the real thing. One further load into one place keeps a streak of the second colour unmixed; three in one place leave a dense blot.
4. **Leave it.** Do not stir, do not go back. The paint moves for a minute or more. `dry` when you are done with the whole passage.

```json
[
  {"action": "load", "brush": "oval_wash", "size": 20, "pigments": {"hansa_yellow": 0.45}, "water": 1.0},
  {"action": "stroke", "path": [[110, 120, 0.9], [274, 120, 0.9]], "speed": 200, "smooth": false},
  {"action": "load", "brush": "round", "size": 9, "pigments": {"cerulean_blue": 4.0, "cobalt_blue": 2.5}, "water": 1.0},
  {"action": "drain", "water": 0.6},
  {"action": "stroke", "path": [[100, 266, 0.5], [92, 204, 0.9], [116, 142, 0.9], [172, 104, 0.9]], "speed": 90}
]
```

(One row of the wash is shown; lay them all, twice, before the charge.)

Swirling the brush through a charge does not make this picture. It makes the next one down: an even mixture. Painters' advice is the same: two or three strokes, then let the water do it.

## A variegated wash inside a crisp shape

The picture to aim for: a leaf, petal or fruit whose outline is hard against dry paper while its colours change softly inside it, with no line between one colour and the next.

1. **Lay the whole shape in a pale wash, deep.** Draw its edge first with the point of a small round (size 3 to 4, lighter pressure at each tip so points stay sharp), then fill the middle with rows of a larger round, twice. Keep the second pass back from the edge by about a brush width: water added at the edge creeps out and blunts the points. Aim for a film of about 0.6 in the middle.
2. **Lay each colour over its own part of the shape, as patches that touch and overlap.** Use a round about as wide as a lobe (size 9 to 12) and run each stroke from the middle out to the edge, lightening the pressure where it ends in a tip. Colour must meet colour: where two patches touch, neither should have the first wash between them. Separate strokes of colour on a pale ground dry as stripes, not as a variegated wash.
3. **Make the patches unequal.** Vary their size, their strength (from half strength, about 1.5, to full, 3 to 4.5) and how full the brush is (0.55 to 0.75: the wetter ones travel further). Leave one or two parts of the first pale wash alone as the lightest passages. Patches of one size and strength give transitions of one width, which looks sprayed.
4. **Run the local colour along the edge** with a size 5 round a few pixels inside the outline, except where the edge is meant to stay pale. Otherwise the first wash shows as a halo all round the shape.
5. **Wait for the film to thin to 0.3, then put in a few much stronger touches** (strength 6 to 8, water 0.5, a size 6 round) where the picture needs its darks: the shadowed edge of a lobe, a tip, the deepest red. At this depth they soften but stay put, which gives the picture two kinds of transition and a wider range of value.
6. **As the film reaches 0.2, touch clear water into one or two places** from a full size 5 round held still for 0.4 seconds. Each pushes the paint around it outward and leaves a pale bloom. This is the one place where the brush should be wetter than the paper, and it is what breaks up an even blend. Leave it out if the passage should stay smooth.
7. **Wait for the film to thin to 0.12, then lift the veins** with a size 2.5 round drained to 0.2: twice along the main ones, once along the rest, so they differ in strength. Start each vein a little way out from where they meet, or the lifting piles up there into a pale blot. Earlier than this the wash flows back and closes the line; once the film has gone, nothing lifts. A stiff flat brush turned end-on lifts a thinner, whiter line; three passes of one looked scratched, not lifted.
8. `dry`.

Work quickly through steps 2 to 4: every stroke uses up the minute and a half the film lasts. Loading with `"water": 0.6` instead of load-then-drain saves a second a stroke. Read the film at the end of step 4; if it is already under 0.3, go straight to the accents.

The trial `variegated_leaf` in the repository's `trials/engine_trials.py` is this method written out, about 160 strokes.

## The other blends

Each of these is on the chart `blending_methods` in the repository's `docs/images/`.

- **Two colours on wet paper.** Wet the area with clear water (one pass), lay one colour at each side with a brush at 0.7, bring them just together, and leave them. The join is a band about a brush width across; deeper water makes it broader.
- **A join stroked with a damp brush.** Two wet colours side by side. A clean brush drained to 0.6 run up and down along the join, three times, carries each into the other. Rinse and drain again between passes. At 0.4 or less the same brush lifts the paint instead and leaves a pale band.
- **Pulling out an edge.** Lay a strong stroke. Rinse, drain to 0.45, and run the brush along just below it, touching its edge; repeat a little further out each time. The edge fades from full strength to nothing.
- **Lifting.** A brush drained to 0.2, two passes, while the film is between 0.3 and 0.1, takes off 30 to 40% of the colour. A soft round gives a broad soft line. A stiff hair (`bright` in `golden_synthetic`, turned end-on with `"twist": 90`) gives a thin one and loosens more of the paint that has already settled. Staining paints (phthalo green, quinacridone rose) hardly lift.
- **Stirring in deep water.** With a film of 1.0 or more, a brush at 0.6 swirled through two colours drags each round into the other along its path. A few turns marble them; many turns make one flat mixture, which is rarely what a painting wants.
- **Wetting a dry wash again.** `dry`, lay clear water over the shape with a soft mop in one pass, and charge into that. Earth and granulating paints lift a little as they are wetted, so do not scrub.

## What goes wrong

- **A bloom where you wanted a blend.** The brush was wetter than the paper: the film had thinned under about 0.1, or the brush was full. Read the film first, and drain the brush.
- **The charge is pale.** Deep water dilutes it. Use stronger paint, put more than one load in the same place, and expect it to dry lighter.
- **Stripes instead of a blend.** Strokes of colour laid apart on a pale ground. Make them touch.
- **Mud.** Three or more colours stirred together, or complements (a red into a green) worked with the brush. Let colours meet; do not mix them on the sheet with the brush.
- **Blunt tips and filled notches.** Too much water at the edge of the shape. Keep the second pass of the first wash inside the outline.
- **Nothing lifts.** The film has gone, or the paint stains. Lift earlier, or use a stiffer hair.
- **Speckle you did not want.** A granulating paint in a film deeper than about 0.6. Lay the wash once, not twice, or use a paint that does not granulate (cobalt blue instead of cerulean or ultramarine).

# Translucency, glazing and stroke economy

Watercolour differs from opaque paint in two ways that reinforce each other: the white of the sheet is your only light source, and every stroke laid on dry paper leaves a darker capillary rim around its perimeter. Painting well with few strokes means working with both facts rather than fighting them.

## Letting the paper shine through

The engine renders deposited pigment over the paper with Kubelka-Munk optical mixing. At heavy loads (`2.5` to `3.8` total pigment), reflectance from the paper beneath collapses: darks turn flat and chalky like gouache or acrylic, granulating blues lose their sparkle, and small gaps left unpainted glare like pinholes that tempt you into patching them.

At translucent loads (`0.25` to `1.25`), the cream tooth of the sheet shines up through every passage, and depth comes from **how many dried washes overlap** at a given point:

1. **Pass 1 — Gossamer wet volumes (`0.25` to `0.65` strength, `"water": 0.80` to `0.84`).**
   Use a brush wide enough to span the whole mass in one or two sweeps (`oval_wash` or `mop`, `size` 35 to 56 on a 768 to 960 pixel sheet) with a gentle `tilt` (`0.05` to `0.08` toward the shadow side). A pale high-water colour wash *is* your wet bed — you rarely need a separate multi-row clear-water pass first. Drop warm and cool first washes into each other while shiny so they merge without internal seams, let gravity settle pigment toward the turning edge for 15 to 20 seconds, level the sheet (`"x": 0, "y": 0`), and `dry`.
2. **Pass 2 — Anatomical dry glazes (`0.75` to `1.25` strength, `"water": 0.74` to `0.78`).**
   Once dry, lay **one continuous sweeping stroke per major shadow plane** (`cats_tongue`, `sword`, or `round`, `size` 18 to 32), leaving generous windows of Pass 1 untouched as sunlit mid-tone. Start and end at light pressure (`0.10` to `0.15`) with explicit `t` timing so the ends feather to a point rather than stamp a square bevel, and place the outer edge of the stroke along a real turn of form so its single capillary ring reads as volume rather than a stripe.
3. **Pass 3 — Selective focal darks (`1.4` to `2.0` strength, 5 to 8 small strokes).**
   Touch stronger darks only into the deepest crevices — an ear canal, behind a lit edge, a crossed limb crease, the underside of a resting weight — so the picture has a firm dark anchor without sacrificing the glow of the larger washes.

## White and pale subjects on bare paper

When a subject has white fur, white cloth, or sunlit stone along its outer contour, leaving bare paper inside *and* bare paper outside dissolves the silhouette, whereas drawing a dark line round it looks stiff, and painting a narrow pale stroke onto dry paper inside the white shape dries with two hard edges like a grey ribbon.

Use one of three clean constructions instead:

- **Internal pearl turn (simplest, fewest strokes).** Run a single whisper-pale cool-warm stroke (`0.12` to `0.20` total pigment, such as `cobalt_blue` with `burnt_sienna`) right along the shadow contour of the white shape; if the inner edge needs to vanish into broad white, either pre-wet the pocket first or run a barely damp clean brush (`"pigments": {}, "water": 0.50`) along that inner edge before it dries.
- **Pre-wetted negative halo.** Wet a broad area *outside* the white contour with clean water first (`mop` or `oval_wash`), then lay a pale wash right along the outer edge of the white shape. The side against dry white stays crisp; the outer side bleeds into the wet halo and disappears without a hard border.
- **A loaded cut with water behind it (a white shape against a darker, soft background).** List the white shape's contour as points and move paths off it sideways (`scripts/passbuilder.py`, `offset_path`). In one wet pass: clear water over the open background with a mop, stopping a brush width short of the contour; a band of clear water from a size 14 round along a path about 22 pixels out, joining that water to where the cut will go; the background's colour dropped into the water from a brush at 0.6; then the cut, a loaded size 9 round at full water along a path about 8 pixels out. The cut's inner half lies on dry paper and dries crisp against the white. Its outer half lies on the band of water and bleeds away into the background. Two versions of this failed. A cut drawn in clear water left no contour, because its thin film had sunk in before the colour reached it and the colour stopped at the edge of the mop's water. A cut with no water beside it dried as a dark ribbon with paper on both sides, a drawing of the shape and not a background behind it.
- **Wet-in-wet ground contact.** Sweep a fast `hake` stroke (`"speed": 280` to `295`, lifting pressure to `0.15` and laying `angle` over to `80–85` at the tail so it breaks into dry-brush sparkle on the grain), and immediately touch a slightly stronger contact shadow right under the white feet, paws, or base *while that `hake` wash is still wet*.

## Stroke economy and its tradeoffs

Cutting stroke count is not a linear dial: down to a point it removes waste and makes every passage fresher; past that point it trades away real qualities in proportion to how far you compress.

| Range (single subject) | What happens | When to use it |
|---|---|---|
| **Above ~90–110 strokes** | **On a single open subject, check for overworking.** There it is usually a sign of brushes half the width of the shape, multi-row clear-water grids where one wide pale wash would do, patching tiny breathing highlights, and striping narrow darks over dry paint. | Expected, and no fault, where the subject has that much in it: landscapes with worked ground, foliage or bare trees (300 to 900 strokes), multi-figure scenes, intricate architecture, or detailed portrait busts that flood tight concave polygons (`references/faces-and-detail.md`). |
| **~55 to 75 strokes** | **The general sweet spot.** About 15 to 20 wide wet strokes establish 85% of the light and colour; 12 to 18 sweeping dry glazes turn the major shadow planes; 15 to 25 lifted strokes remain for broken surface texture (dappled fur, foliage, rough stone), crevice darks, and fine detail. | Most portraits, animals, still lifes, and landscapes. |
| **Below ~45 strokes (down to ~30)** | **Calligraphic / sumi-e economy.** Distinct parts must be chained into single unbroken paths — hopping at `pressure: 0.08–0.12` across gaps, J-looping down one limb and up its neighbour, rimming several contours in one `sword` journey — and mottled texture simplifies into one or two smooth ribbons. | Deliberately loose, airy, illustrative or minimalist studies. |

A close copy of a reference is outside this table. Painted by measurement (`references/copying-a-reference.md`) it took about ten thousand small strokes, each laying only what the sheet still lacked beneath it, and 250 strokes planned by hand came nowhere near it. The economy above is for painting from an idea.

Know the three proportional tradeoffs below ~45 strokes before choosing that register:

1. **Surface texture vs. sleek ribbons.** Dappled tortoiseshell fur, bark, or scrub needs varied, lifted marks; when each zone can afford only one or two sweeps, textured surfaces become smooth graphic colour planes.
2. **Chained-path bridges and shared mixes.** Hopping across features without lifting leaves faint connecting threads, rounds adjacent sub-forms together at turns (two crossed legs rounding into one mitt), and forces every stop on the chain to share one brush mix.
3. **Softer peak darks** if the third pass of crevice accents is omitted to save strokes.

## Deepening a broad wash once it has dried

A wash that dried too pale over a large area (a beach, a field, a sky) can take a second wash over it. From 0.11.0
the dried wash lies under the new rows as a layer of its own: their water still lifts a little from it, but its grains
no longer roll into the paper's hollows, so a full brush stirs it far less than it did. A wash of burnt sienna, yellow
ochre and cobalt blue (value 0.712, spread of values 0.022) laid again over itself in rows of a size 10 `flat_wash`, on
a 160 by 128 sheet:

| Second wash | 0.10.0 | 0.11.0 |
|---|---|---|
| Full water (0.95) | 0.544, spread 0.048: coarse speckle | 0.541, spread 0.027 |
| Full water over fixative | 0.541, spread 0.022 | 0.539, spread 0.023 |
| Drained to 0.55 | 0.599, spread 0.023 | 0.597, spread 0.024 |

- **On 0.11.0 use a full brush.** It darkens by half as much again as a drained one from the same load, and the
  speckle it leaves is slight. On 0.10.0 the full brush stirred the first wash into coarse speckle (the beach in
  `references/water.md`: spread 0.042 to 0.072), so there use a drained brush or fix first.
- **A drained brush lays less.** Drained to 0.55 it lays about a quarter of what the same load lays on bare paper,
  and the darkening grows as about the 1.45 power of the strength: gain 1 darkened the beach by 0.009, gain 4 by
  0.066. Rehearse two strengths on a small sheet that carries the same first wash, and read the strength off them.
- **Mix every segment from the reference less a dry look of the sheet**, both unblurred and restricted to the wash.
  A glaze mixed from a blur that took in a white passage next to it came out near-clear, and the edge of a
  near-clear stretch dries as a line across the finished wash. Where part of the wash already matches, its mix is
  near-clear too, so cover the whole wash from edge to edge and do not leave the glaze to end inside it.
- **Fixing first takes off the last of the speckle** (0.023 against 0.027 above) and stops the second wash lifting
  any of the first. Fix the whole wash, not a patch of it: on 0.10.0, laid at full water across a fixed band, the same
  kind of wash dried clean on the band (0.017) and speckled beside it (0.032), so the edge of the fixative showed.

## Diagnosing common faults

| What `look` shows | Cause | Fix on the next sheet (or next dry pass) |
|---|---|---|
| Flat, heavy, acrylic or gouache look | Washes loaded above `2.5` smothered paper reflectance | Drop Pass 1 to `0.25–0.65` and glazes to `0.75–1.25`; let overlaps build the darks |
| Stripey "caterpillar" bars or faceted ribbons inside one shadow | Several medium strokes laid onto dry paper, each leaving two dark capillary rims | Use one `size 35–55` wash or `size 24–32` `cats_tongue` so one outer rim sits on a real turn of form, or feed darks while shiny/moist |
| Fuzzy grey spray-paint halo outside the subject | Pre-wetted far beyond the silhouette | Stop the wet bed *on* the contour so pigment dries to a crisp organic wet-edge bead; pre-wet outside only where a deliberate bloom is wanted |
| Isolated grey worm on white fur or under feet | Narrow pale stroke laid onto dry paper | Soften one edge immediately with damp clean hair, or drop contact shadow into a still-wet `hake` ground stroke |
| A dark outline round a white shape, paper on both sides | The cut along its contour had no water beside it | Lay a band of clear water under the outer half of the cut first |
| The white shape has no shape | Bare paper inside and outside, nothing on its contour | A cut on every stretch of contour where the background should be darker than paper |
| A flat dark slab where the background should vary | A strong wash everywhere, strengthened again by charges and a second layer, judged by eye | Sample the reference or decide the values first; lay the middle value and keep the dark to where it belongs |
| Sandy speckle and blurred detail after a correction | A broad wet wash laid over finished small work re-wet it; a granulating earth in the wash gathered into specks | Correct with small glazes on dry paper, or `fix` the finished work before the broad wash (0.10.0); keep burnt umber out of deep washes (burnt sienna greys cobalt blue without the specks) |
| Coarse speckle all over a broad wash after it was deepened | On 0.10.0 or older: the second wash was laid with a full brush and stirred the dried first one | Upgrade to 0.11.0, where the first wash lies beneath the second; or drain the brush to 0.55 and raise the strength, or `fix` the first wash before the second (see "Deepening a broad wash once it has dried") |
| A thin line across a finished wash | The edge of a near-clear glaze, mixed from a blur that took in a light passage or ending inside the wash | Mix from unblurred targets inside the wash only; cover the wash from edge to edge |
| Unwanted vertical icicle drips | `tilt` above `0.18` on a flooded wash | Keep gentle gravity pooling to `0.05–0.08` for 15–20 seconds, then reset `tilt` to `0` |

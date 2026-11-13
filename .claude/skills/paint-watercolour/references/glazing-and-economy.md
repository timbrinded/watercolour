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
- **Wet-in-wet ground contact.** Sweep a fast `hake` stroke (`"speed": 280` to `295`, lifting pressure to `0.15` and laying `angle` over to `80–85` at the tail so it breaks into dry-brush sparkle on the grain), and immediately touch a slightly stronger contact shadow right under the white feet, paws, or base *while that `hake` wash is still wet*.

## Stroke economy and its tradeoffs

Cutting stroke count is not a linear dial: down to a point it removes waste and makes every passage fresher; past that point it trades away real qualities in proportion to how far you compress.

| Range (single subject) | What happens | When to use it |
|---|---|---|
| **Above ~90–110 strokes** | **Overworking.** Almost always a sign of brushes half the width of the shape, multi-row clear-water grids where one wide pale wash would do, patching tiny breathing highlights, and striping narrow darks over dry paint. Cutting by a third to a half here is pure gain with no loss of likeness. | Multi-figure scenes or intricate architecture only. |
| **~55 to 75 strokes** | **The general sweet spot.** About 15 to 20 wide wet strokes establish 85% of the light and colour; 12 to 18 sweeping dry glazes turn the major shadow planes; 15 to 25 lifted strokes remain for broken surface texture (dappled fur, foliage, rough stone), crevice darks, and fine detail. | Most portraits, animals, still lifes, and landscapes. |
| **Below ~45 strokes (down to ~30)** | **Calligraphic / sumi-e economy.** Distinct parts must be chained into single unbroken paths — hopping at `pressure: 0.08–0.12` across gaps, J-looping down one limb and up its neighbour, rimming several contours in one `sword` journey — and mottled texture simplifies into one or two smooth ribbons. | Deliberately loose, airy, illustrative or minimalist studies. |

Know the three proportional tradeoffs below ~45 strokes before choosing that register:

1. **Surface texture vs. sleek ribbons.** Dappled tortoiseshell fur, bark, or scrub needs varied, lifted marks; when each zone can afford only one or two sweeps, textured surfaces become smooth graphic colour planes.
2. **Chained-path bridges and shared mixes.** Hopping across features without lifting leaves faint connecting threads, rounds adjacent sub-forms together at turns (two crossed legs rounding into one mitt), and forces every stop on the chain to share one brush mix.
3. **Softer peak darks** if the third pass of crevice accents is omitted to save strokes.

## Diagnosing common faults

| What `look` shows | Cause | Fix on the next sheet (or next dry pass) |
|---|---|---|
| Flat, heavy, acrylic or gouache look | Washes loaded above `2.5` smothered paper reflectance | Drop Pass 1 to `0.25–0.65` and glazes to `0.75–1.25`; let overlaps build the darks |
| Stripey "caterpillar" bars or faceted ribbons inside one shadow | Several medium strokes laid onto dry paper, each leaving two dark capillary rims | Use one `size 35–55` wash or `size 24–32` `cats_tongue` so one outer rim sits on a real turn of form, or feed darks while shiny/moist |
| Fuzzy grey spray-paint halo outside the subject | Pre-wetted far beyond the silhouette | Stop the wet bed *on* the contour so pigment dries to a crisp organic wet-edge bead; pre-wet outside only where a deliberate bloom is wanted |
| Isolated grey worm on white fur or under feet | Narrow pale stroke laid onto dry paper | Soften one edge immediately with damp clean hair, or drop contact shadow into a still-wet `hake` ground stroke |
| Unwanted vertical icicle drips | `tilt` above `0.18` on a flooded wash | Keep gentle gravity pooling to `0.05–0.08` for 15–20 seconds, then reset `tilt` to `0` |

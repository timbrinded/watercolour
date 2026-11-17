# Faces, likeness and fine detail

Portraits and fine focal passages fail for opposite reasons from landscapes: a wash load that looks fresh on a hillside smothers skin into chalk, a wide mop that spans a rock face inflates a jaw or nose by its own radius, and a five-pixel drift in eye or mouth geometry changes who the person is and what they feel.

## The concentration trap and the portrait value ladder

In `load`, `pigments` sets **concentration per unit of water** directly. Raising `water` to `1.0` fills the brush reservoir with more paint at that concentration — it does **not** dilute the mix. On sunlit skin, a `0.30` to `1.00` wash is already heavy mid-dark; overlapping two of them kills the light of the paper.

Let **60 to 80% of a lit face remain untouched bare paper** (forehead, nose bridge and ball, lit cheekbone, lip highlight, chin boss, lit neck tendons) and step concentrations down into four clear registers:

1. **Linked gossamer skin wash (`0.05` to `0.15` total pigment, `"water": 0.80` to `0.86`).**
   Connect the shaded side in one continuous wash — temple turn into orbital socket, down the shaded wall of the nose, under the nose tip, and down the shaded cheek, jaw underside, and throat hollow (`burnt_sienna` with a touch of `quinacridone_rose` and `french_ultramarine` gives a lively translucent flesh shadow).
2. **Wet-in-wet socket and turning cores (`0.20` to `0.45` total pigment, `"water": 0.42` to `0.46`).**
   While the base wash is still shiny, step the brush water *down* so the new charge spreads softly inside the pool without flooding it, and touch deeper warm-cool mix into the inner brow overhang, under-jaw cast shadow, and neck cleft.
3. **Secondary darks (`0.45` to `0.85` total pigment).**
   Nostrils, oral fissure, ear concha recesses, and brow hair accents — always kept a clear step softer than the pupils so they do not steal focus.
4. **Pinpoint focal darks (`1.30` to `2.00` total pigment, two dried passes).**
   Reserved strictly for the pupils and upper lash blades right next to bare paper or a tiny final glint.

## Measuring likeness before the first wash

1. **Lock a single cranial axis.**
   Never mix coordinates from references with different head tilts without counter-rotating them onto one shared axis first. Hairline, brow line, interpupillary line, nostril base, mouth corners, and jaw angles must all sit perpendicular to the same head centreline; tilted eyes inside a level hairline and nose read as a deformed skull rather than a cocked head.
2. **Drop vertical plumb lines from the pupils.**
   High-contrast greyscale tonal maps are useful for spotting connected shadow shapes, *except* where adjacent shadows merge — most dangerously where lip corners bleed into nasolabial smile creases, tricking you into drawing a hinged Muppet mouth wider than the eyes. Drop plumb lines straight down from the pupils: even in a strained grin, the **lip corners stop at or inside the pupils** (`~0.85` to `1.0×` interpupillary distance), leaving `15` to `25` pixels of clean cheek muscle before any outer smile fold. Check neck length against jaw width too (`chin-to-collar notch ≈ 0.55` to `0.65×` jaw width on a bust) so shoulders do not drift low.
3. **Slim close-up lens perspective and contain bare-paper expansion.**
   Close-up photographs stretch horizontal facial width through wide-angle perspective, and in watercolour an uncontained bare-paper cheek lacks photographic shadow falloff so it visually merges into the white margin. Match long-lens cranial proportions (`~0.75` to `0.85×` horizontal compression on close-up references) and bound the lit side of the head either from within — a whisper-sheer `0.06` to `0.09` turning wash along the outer temple and cheekbone, immediately melted inward with damp clean hair — or from without, using an atmospheric counterchange wash that bleeds off the sheet or feathers away with clean water.
4. **Inset every contour path by the brush radius.**
   Tracing *on* a jawline or nose edge with a `size 22` round or mop deposits paint `22` pixels outside the line on every side (`+44` pixels of jowl or potato-nose bloat). Always offset the path inward by `size × pressure_width_factor`.

## Sculpting concave facial planes without ribbons

A face shadow has tight concave turns around the eye socket, nose bridge, alar wing, lips, and chin. A `size 30` mop cannot turn those corners without bloating them, square `flat` stamps leave boxy duct-tape facets, and separate `size 8` strokes on dry paper each dry with two dark capillary rims ("caterpillar stripes"). Use two clean constructions instead:

- **Flooded inset polygons (for connected base washes).** Trace the inset boundary of the shadow shape with a pointed squirrel `round` (`size 7` to `10`) for surgical `±2px` contour accuracy, and immediately sweep fast overlapping interior rows (`spacing ≈ 1.0` to `1.1 × size`, `"speed": 275` to `285`, reloading every 6 to 8 strokes so the reservoir never streaks) within the 90-second shiny window. All internal strokes merge into one seamless liquid pool with a single crisp outer boundary. Immediately melt form-turning edges with a damp clean squirrel brush (`"pigments": {}, "water": 0.28` to `0.32`) while leaving cast-shadow edges untouched.
- **One-sided dry glazes (for Pass-2 structure).** When glazing a sharper plane onto dry paper — a straight nose side-wall, an eyelid crease, a nasolabial fold, or the cast shadow under a jawbone — place one edge of a `dagger` or `round` stroke on the crisp anatomical line and immediately run a damp clean squirrel brush along the *other* edge before it dries. One side holds a crisp watercolour rim; the other vanishes without a ribbon outline.

## Feature mechanics and expression

### Eyes and psychological expression

Heavy dark washes across a face kill bare-paper luminosity without fixing a weak expression. Character lives in a dozen pixels of lid, iris, pupil, and brow geometry:

| Expression register | Geometry that produces it |
|---|---|
| **Open, gentle, naive, or surprised** | Tall parabolic `^` upper-lid arches; curved-up brows with a wide bright skin gap beneath them; large dilated pupils; bright pastel irises with no outer border; large pie-slice catchlight cutouts. |
| **Focused, severe, unhinged, or predatory** | Flat-topped or hooded upper-lid blades clipping the top of the iris; straight, upward-tightened lower lids (`AU7` squint) with fine corner crinkles; cooler, desaturated steel/earth irises ringed with a dark outer limbal border and upper-lid cast shadow across their top third; tight constricted pinprick pupils; a needle-prick `size 1.5` glint; low, straight dark brows pressing over a deep wet-in-wet inner socket pocket. |

- Fill the iris solidly rather than leaving a giant missing wedge, charge the darker limbal ring and upper-lid shadow across its top third while wet, and add the pinpoint glint last with `opaque_white` (`size 1.5`, `strength ~5.0`) on the pupil rim.
- Paint upper lash blades in two slow passes (`dagger` followed after `dry` by a fine `kolinsky_sable` `rigger` at `"speed": 80` to `90`) so paper grain leaves no crumbly white gaps along the lash line.

### The white of the eye (0.8.0 or later)

Painted round, the white of an eye is too small and too narrow at its corners to keep. Washes cut round it break up, and
measured washes tone it like the skin beside it, because in a photograph the white sits in the socket's shadow and is
darker than lit skin. Opaque white laid back over a wash dries pale grey (0.65 under a dark wash of 0.27). Mask it, as a
painter does:

1. **Before any paint, mask the whole opening of each eye, iris and all, as one tapered stroke.**
   - Read the upper and lower lid edges off a grid, corner to corner.
   - Run the stroke along the midline between them.
   - Set `radius` to the opening's largest half-height, less about 1.5 pixels so no white shows above the lash line.
   - At each point set the pressure to `(half-height / radius - 0.15) / 0.85`, clipped to 0 to 1. The width then
     follows the opening and tapers into both corners.

   A line of even width reads as a white bar, not an eye.
2. **Paint the face over it freely, `dry`, and `unmask`:** a clean almond of paper.
3. **Mask each catchlight with a dot** where the iris will be. Use a radius of 2.5 or more: a dot of 2.2 or less was
   lost.
4. **Shade the white.**
   - A lit eye: a cool grey (cobalt blue 0.3, burnt sienna 0.12) along its top under the upper lid, softened downward
     at once with a clean brush drained to 0.45.
   - An eye in shadow: its whole white at a middle value (cobalt blue 0.55, burnt sienna 0.3).
5. **Paint only the visible part of the iris** with a short level stroke at full pressure.
   - Use a round sized to the opening's half-height at the iris, at strength about 2. Its round ends cut the white as
     the iris does. A full disc of the iris's own radius spilt onto the lower lid as a brown crescent.
   - Then lay the upper lid's shadow across the iris's top third, thin dark arcs at its sides for the limbal ring, the
     pupil in two coats, and the lash line along the white's upper edge.
6. **`unmask` the catchlights.**

Measured on a trial at 768 by 576: the white dried at 0.95 and the catchlight at 0.88, against a lash line near 0.1.

### Noses, mouths, and chins

- **Noses:** Never draw lines down both sides of the bridge. Leave the bridge and ball bare paper; carve them with a straight shaded side-wall (crisp along the bridge, softened outward onto the cheek) wrapping into a warm capillary underside (`burnt_sienna + quinacridone_rose`). Tuck soft-edged nostrils (`0.45` to `0.70`) *inside* that underside shadow rather than floating dark commas on bare paper.
- **Mouths:** Avoid outlining both lips end to end. Anchor the oral fissure (`dagger` or `round`, sharpest at corners and centre; check curvature — a flat horizontal press reads tense and severe, whereas an upward U-curve past the pupils reads cartoonish), tint the shaded upper lip lightly, leave a bare-paper highlight strip on the lower lip, and place a small softened shadow cleft beneath the lower lip so the bare-paper chin boss projects forward.

### Hair masses and crisp costume trim

- **Hair without "helmet" or "buzzcut" silhouettes:** Rimming a skull in one uniform `oval_wash` horseshoe reads as a plastic helmet, while over-thinning sideburns disconnected from the crown reads as a flat-top buzzcut, and dry dark strokes down narrow pale strips leave ribbon outlines. Keep wave fullness widest at the upper-temple turn tapering smoothly down the sideburns, leave diagonal bare-paper shine ribbons in the crown, feather the outer crown edge with clean water, charge darker root and temple pigment *wet-in-wet*, and sweep a laid-over `comber` (`angle 72` to `80`) across the dried mass for multi-strand grain.
- **Crisp adjacent trim (collars, insignia, braid):** Always `dry` warm yellow or gold passages completely before laying cool `french_ultramarine` or `cobalt_blue` beside them, and keep the blue brush path offset outside the dried yellow seam by `radius + 2px`; transparent blue overlapping dried yellow turns vivid trim into dull olive mud.

## Find the register before choosing strengths

The value ladder at the top of this file is for pale skin in a high key. A brown face in strong sunlight against a dark background needed 2.4 to 2.6 for its shadow wash and 5 to 7 for the charges into it. From a reference, sample the values (`scripts/measure.py`) and read the strengths off a deposit chart (`copying-a-reference.md`). Without one, decide the value you want and do the same.

The same reference corrected two other habits:

- **The lit side is mostly paper, not empty paper.** A pale flesh at about 0.55 down the bridge of the nose, pale ochre on the lids, a cool grey touch at 0.45 on the upper lip and the side of the nose. Without them the lit half of the head has no surface. Measured against the reference, tints this pale were the largest part of what a nearly finished copy still lacked.
- **Wash straight over the far eye.** In shadow the white of an eye is not white. A hole left for it in the shadow wash dries as a hard-edged white box that no later mark brings back into the head.

## The drawing that goes on last

Forty or fifty crisp marks turn a soft, correct wash into a particular person. Draw them on washes that are completely dry, one stroke per mark, each loaded fresh and laid slowly. Measure every one first: enlarge the eyes and the mouth to seven times their size with a 10 pixel grid (`scripts/reference_grid.py --zoom 7 --step 10`), write each mark down as points, and check the pass over the reference (`scripts/preview_pass.py`). Marks this small must sit within two pixels.

The sizes below are for a face about 300 pixels across. "Dark" is burnt umber 3 to French ultramarine 1.2.

| Mark | Brush and load | Path |
|---|---|---|
| **Whites of the eyes** | `round` 1.8, `opaque_white` at 4.5 | One stroke 5 to 8 pixels long each side of each iris, laid before any dark and dried. They are too small to reserve; without them the eye is a dark almond with no eye in it. |
| **Upper lid** | `round` Kolinsky 3.5 to 4, dark at 6, fullness 0.8, `speed` 70 | Outer corner to inner, pressure 0.2, 0.8, 1.0, 0.9, 0.6, 0.3: a hairline that thickens over the iris and tapers into the corner. |
| **Iris** | `round` Kolinsky, `size` equal to the iris's radius, dark at 6 | A stroke 4 pixels long at pressure 1.0 and `speed` 20. Press fully: a touch at the default pressure leaves a spot only three quarters of `size` in radius, and at 0.5 little more than half, which gives a pinpoint pupil in a wide white eye. |
| **Lower lid** | `round` 1.3, warm dark (sienna, red, umber) at 2.2 to 2.4 | Four points, 0.3, 0.7, 0.7, 0.3. Much lighter than the upper lid. At 3.5 to 4 it closed the eye into an outlined almond and took the smile out of it. |
| **Brow** | `round` 3.5; cool grey at 3.4 on the lit side, warm brown at 4.5 on the shadow side | 0.3, 0.9, 1.0, 0.4. Grey, not black, where the light is on it. |
| **Nostril and the dark under the nose** | `round` 2.2, dark at 4.5; `round` 4.5, warm brown at 5 | Two short ticks pressed at their far ends; one wedge beneath, turning up into the far nostril. |
| **Mouth corners** | `round` 4 to 5, dark at 5.5 to 6 | A wedge from each corner inward, heaviest two thirds along. These carry the smile. |
| **Upper lip over teeth** | `round` Kolinsky 1.8, warm brown at 4.5 | One thin line along the top of the teeth. A pale grey band there dried as a smear across them. |
| **Teeth** | none | Paper. Keep every wash off their band, and hang the gaps from the upper lip as ticks of a size 1.4 round, 5 to 9 pixels long. Opaque white laid over a drawn mouth to recover them dried grey. |
| **Lower lip** | `round` 5, redder flesh at 3.5 | One stroke, 0.2, 0.9, 1.0, 0.8, 0.2, so that both ends come to points. |
| **Glints** | `round` 1.5, `opaque_white` at 4.5 | Dabs of 0.2 seconds, after a `dry`, last of all. |
| **Strand of hair** | `round` Kolinsky 2.4, the hair's dark at 3.2, `speed` 200 | Three or four points, 0.2, 0.8, 0.9, 0.2. A fresh load for each, and vary their lengths. |
| **An animal's eye and muzzle** | `round` Kolinsky 4.5, dark at 5.5, `speed` 60; `round` 5 to 10, warm dark at 2 to 3 | One almond, 0.2, 0.9, 1.0, 0.3, with a thin warm lid above it. Nose patch, mouth line and lower lip as shapes that touch; with paper between them they read as three stripes. |

Order: the long gestures and a `dry`; the whites of the eyes and a `dry`; every dark mark in one pass; `dry`; the glints.

**Gestures are the long strokes** that are one movement of the arm: hair swept from the parting to the fringe (80 to 130 pixels, a size 3 to 4 Kolinsky round at `speed` 190), the length of a hanging ear, a fold. Each is one stroke of three or four points with pressure 0.15, 0.8, 0.9, 0.15, so that it starts and ends on the point of the brush. Lay them pale, at about 1 to 1.7, and lighter than seems right: a gesture over finished washes adds to what is already there, and on a sheet otherwise within 0.04 of its reference the only passages too dark were hand strokes a third too wide and half as strong again as they should have been.

## Diagnosing portrait and detail faults

| What `look` shows | Cause | Fix on the next sheet (or next dry pass) |
|---|---|---|
| Face looks wide, bloated, or jowly | Close-up photo FOV, bare-paper cheek merging into white margin, or fat brush centred *on* jaw/nose contour | Slim close-up horizontal coordinates (`~0.75–0.85×`), bound the lit temple/cheek with a `0.06–0.09` inward-softened turn, and inset paths by brush radius |
| One eye droops or drifts off-level | Mixed landmarks from differently tilted references | Rotate reference onto one shared cranial axis; verify all paired landmarks on `--grid` |
| Wide "Muppet" or cartoon mouth | Tonal map merged lip corners into outer nasolabial folds, or fissure curved in a banana `◡` past the pupils | Drop pupil plumb lines: stop lip corners at/inside pupils with `15–25px` clean cheek space before smile creases, and keep strained mouths flat |
| Doe-eyed, naive, or surprised stare | Tall arched upper lids, high curved brows, dilated pupils, bright unringed irises, huge catchlight | Flatten/hood upper lid across top of iris, tighten lower lid straight, ring desaturated iris + shade top third, constrict pupil, drop brows low over socket shadow |
| Skin looks chalky, muddy, or over-painted | `0.30–1.0+` skin loads (`pigments` is concentration, not diluted by `water`) | Drop first skin washes to `0.05–0.15` and leave 60–80% of the lit face bare paper |
| Double-outlined stripes on cheeks, neck, or hair | Unsoftened medium strokes laid onto dry paper | Flood closed polygons while shiny + charge darks wet-in-wet, or immediately melt one edge of dry glazes with damp clean hair |
| A startled stare: small pupils in wide white eyes | Irises painted as light dabs, or a hole left in the shadow wash for the far eye | Iris at full pressure with `size` equal to its radius; wash over the far eye |
| The eye is an outlined almond and the smile has gone | Lower lid as dark as the upper | Lower lid at 2.2 to 2.4 with a size 1.3 round |
| Teeth cream, or grey | Washes laid over them, then opaque white over the drawn mouth | Keep their band free of every wash; draw only the gaps |
| Eyes and mouth in the right place, but no head | The lit side left as empty paper with nothing on its contour | Pale tints on the lit side, and a background or a thin warm line along the lit jaw |
| A face assembled from bars | Strokes planned as centre lines | Preview the pass for coverage; fewer, fatter, overlapping strokes |
| Lash line dries violet | Too much ultramarine in the dark | Burnt umber 3 to French ultramarine 1.2 |
| Hair edge, brow or a lock heavier than everything round it | Hand strokes laid over finished washes at full strength | Gestures at 1 to 1.7, lighter than seems right |
| Gold/yellow collar or trim turned olive-brown | Adjacent blue laid while yellow was wet, or glazed over dried yellow | `dry` yellow first and offset blue paths `radius + 2px` outside the gold seam |

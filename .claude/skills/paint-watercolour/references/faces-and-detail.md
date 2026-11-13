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

### Noses, mouths, and chins

- **Noses:** Never draw lines down both sides of the bridge. Leave the bridge and ball bare paper; carve them with a straight shaded side-wall (crisp along the bridge, softened outward onto the cheek) wrapping into a warm capillary underside (`burnt_sienna + quinacridone_rose`). Tuck soft-edged nostrils (`0.45` to `0.70`) *inside* that underside shadow rather than floating dark commas on bare paper.
- **Mouths:** Avoid outlining both lips end to end. Anchor the oral fissure (`dagger` or `round`, sharpest at corners and centre; check curvature — a flat horizontal press reads tense and severe, whereas an upward U-curve past the pupils reads cartoonish), tint the shaded upper lip lightly, leave a bare-paper highlight strip on the lower lip, and place a small softened shadow cleft beneath the lower lip so the bare-paper chin boss projects forward.

### Hair masses and crisp costume trim

- **Hair without "helmet" or "buzzcut" silhouettes:** Rimming a skull in one uniform `oval_wash` horseshoe reads as a plastic helmet, while over-thinning sideburns disconnected from the crown reads as a flat-top buzzcut, and dry dark strokes down narrow pale strips leave ribbon outlines. Keep wave fullness widest at the upper-temple turn tapering smoothly down the sideburns, leave diagonal bare-paper shine ribbons in the crown, feather the outer crown edge with clean water, charge darker root and temple pigment *wet-in-wet*, and sweep a laid-over `comber` (`angle 72` to `80`) across the dried mass for multi-strand grain.
- **Crisp adjacent trim (collars, insignia, braid):** Always `dry` warm yellow or gold passages completely before laying cool `french_ultramarine` or `cobalt_blue` beside them, and keep the blue brush path offset outside the dried yellow seam by `radius + 2px`; transparent blue overlapping dried yellow turns vivid trim into dull olive mud.

## Diagnosing portrait and detail faults

| What `look` shows | Cause | Fix on the next sheet (or next dry pass) |
|---|---|---|
| Face looks wide, bloated, or jowly | Close-up photo FOV, bare-paper cheek merging into white margin, or fat brush centred *on* jaw/nose contour | Slim close-up horizontal coordinates (`~0.75–0.85×`), bound the lit temple/cheek with a `0.06–0.09` inward-softened turn, and inset paths by brush radius |
| One eye droops or drifts off-level | Mixed landmarks from differently tilted references | Rotate reference onto one shared cranial axis; verify all paired landmarks on `--grid` |
| Wide "Muppet" or cartoon mouth | Tonal map merged lip corners into outer nasolabial folds, or fissure curved in a banana `◡` past the pupils | Drop pupil plumb lines: stop lip corners at/inside pupils with `15–25px` clean cheek space before smile creases, and keep strained mouths flat |
| Doe-eyed, naive, or surprised stare | Tall arched upper lids, high curved brows, dilated pupils, bright unringed irises, huge catchlight | Flatten/hood upper lid across top of iris, tighten lower lid straight, ring desaturated iris + shade top third, constrict pupil, drop brows low over socket shadow |
| Skin looks chalky, muddy, or over-painted | `0.30–1.0+` skin loads (`pigments` is concentration, not diluted by `water`) | Drop first skin washes to `0.05–0.15` and leave 60–80% of the lit face bare paper |
| Double-outlined stripes on cheeks, neck, or hair | Unsoftened medium strokes laid onto dry paper | Flood closed polygons while shiny + charge darks wet-in-wet, or immediately melt one edge of dry glazes with damp clean hair |
| Gold/yellow collar or trim turned olive-brown | Adjacent blue laid while yellow was wet, or glazed over dried yellow | `dry` yellow first and offset blue paths `radius + 2px` outside the gold seam |

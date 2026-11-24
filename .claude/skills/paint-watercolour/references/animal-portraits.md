# Animal portraits

A fur-bearing mammal differs from a human sitter in three ways. Its outline is hair, not a contour. Its form is carried by a coat whose direction and length change across it. Its likeness sits in a few small hard things (the eye, the nose leather, the whiskers) inside large soft masses. This file covers those three. Measure the likeness as `faces-and-detail.md` describes, and paint white fur as paper with the constructions in `glazing-and-economy.md` ("White and pale subjects on bare paper").

Every figure here was measured on cold press on 0.12.0. Pixel sizes are for hairs 25 to 50 pixels long on a sheet about 780 pixels wide; scale them with the animal.

Contents: planning the animal; the coat, in order; what a fur mark does at each wetness; which head draws a hair; the edge of the coat; eye, nose and whiskers; from a photograph, with the measured stages; diagnosing faults.

Two pictures go with the text. Open each when the passage it belongs to comes up:

- `figures/fur-marks-and-edges.png` — the trial sheets behind the wetness table and the edge table below.
- `figures/european-badger-portrait.png` — a European badger, 784 by 680, about 350 pixels from ear to nose. Take the head from it: the eye, the facial stripes laid as shapes, the nose. Do not take the flank, which shows the first fault in the last table.

## Plan the animal before the fur

- **Give it something to do, and join the head to the body.** The badger lifts its muzzle into open paper while the shoulder runs out of the lower left. The cheek overlaps the shoulder and the dark under the jaw runs into the chest. Check both overlaps in `look --view value` before any hair goes on; where they are missing the head floats.
- **Take the head turn and the light from one photograph.** Measure both eye openings, the ear bases and the nostrils in it (`scripts/reference_grid.py`). The turn narrows the far eye, and the two different eye shapes are what give the animal a direction of attention. Use other photographs only for what the first leaves out (the coat pattern, an ear fringe), never for positions.
- **Let the eye set the size of the sheet.** The badger's near eye is 37 pixels long, and that held a reserved glint, an iris, a pupil and two lids. A species with a small eye needs a larger head on the sheet than a human face needs.
- **Write the coat down as a map.** For each region note the direction the hair lies and how long it is, and mark where either changes: short and radiating round the eye and the whisker pads, swept back across the cheek, long and turning over the shoulder. Take it from the species and the individual; a badger's long guard hairs are pale with one dark band below a pale tip, so there each is a pale shaft and a pale tip laid separately.
- **Plan markings as shapes.** A stripe, a mask or a patch is part of the value plan, laid with the undercoat. Hairs drawn later do not make one.

## The coat, in order

1. **Reserve first.** Mask the glints, and any whisker or pale hair that must stay paper where a dark will cross it, on dry paper before any wash.
2. **Lay each mass as one connected wet wash**, with a brush as wide as the mass, leaving white fur as paper. Vary it while it is wet, not afterwards.
3. **Charge the markings, the large darks and the soft locks into it** while the film is 0.15 to 0.3, with a brush at fullness 0.6. Flick the fringe out of its edge at the same depth (see "The edge of the coat").
4. **`dry`, and look.** The masses, the markings and the light must read now. If they do not, hairs will not rescue the sheet; start another.
5. **Draw hairs on the dry coat**, tapered, in groups, following the map.
6. **`dry`, `unmask`, then the lights**: pale hairs and whiskers in `opaque_white`.

## What a fur mark does at each wetness

The undercoat in these trials was 0.6 of cobalt blue, burnt umber and ivory black, laid twice with a squirrel round; it dried at 0.64. Each mark was a tapered stroke 45 pixels long from a Kolinsky round, pressure 0.2, 0.9, 0.1. The film is the depth at the middle of the marks, caught with `wait`; towards the edge of the wash it was up to a third thinner.

| Mark | Film when it landed | What dried |
|---|---|---|
| Hair: size 2.4, strength 2, fullness 0.6, six at a pitch of 9 pixels | 0.5, 0.3, 0.15 or 0.06 | No hairs at any depth. The six ran together into one soft cloud, 0.41 to 0.47 at its darkest. |
| The same hair | none, undercoat dry | Six separate hairs, each 5 to 6 pixels wide at the middle, 0.33 to 0.38. |
| Hair: size 2.4, strength 6, fullness 0.45, at a pitch of 14 | 0.3 | A cloud again. |
| The same | 0.15 | Soft separate smudges: the finest mark that survives wet. |
| Lock: size 5, strength 4, fullness 0.6, at a pitch of 20 | 0.3 | Three soft-edged locks, 0.28 at their darkest. Use this for underfur, a soft marking or a dapple. |
| The same | 0.15 | The same locks with firmer edges, 0.32. |
| Hair: size 2.4, strength 3, fullness 0.35 | 0.02: the film gone, the paper damp (0.8) | Almost nothing. |

So a hair is a mark for dry paper. In a film, paint the lock, not the hair: about twice as wide as a hair, twice as strong, and at least 20 pixels from the next.

## Which head draws a hair

Each was one 60 pixel mark at strength 2 over the dried undercoat. Width is at the middle of the mark.

| Head | Width | Value | Use |
|---|---|---|---|
| `round` 2.4, Kolinsky, tapered | 4 | 0.28 | The ordinary guard hair. |
| `designer` 2, tapered | 3 | 0.23 | The darkest fine hair, and the longest taper. |
| `sword` 3, tapered | 5 | 0.27 | A coarse hair. |
| `round` 1.2, tapered | 2 to 3 | 0.35 | A fine hair. |
| `rigger` 1.0, tapered | 1 | 0.34 | A hairline: a whisker, an eyelash. |
| `comber` 3, 5 or 8, pressure 0.5, fullness 0.7 or more | about its `size` | 0.24 to 0.35 | One blunt band, not several hairs. Its ends do not taper. |
| `comber` 5, pressure 0.25 | 4 and 2 | 0.39 | Two lines. Flicked off the edge of a coat onto bare paper it gave clumps of two or three. |
| `comber` 5, laid over (`angle` 80) | two or three faint lines | 0.49 | Grain across a finished mass, not hairs. |

- **Lay hairs in groups.** On the badger's shoulder, groups of five to ten hairs that overlap and differ in length, with quiet undercoat between one group and the next, read as coat. Lower on the flank the same hairs spread evenly read as ticks.
- **A broken sweep for coarse coat** is the dry-brush of `SKILL.md`: a `round` 12 in `golden_synthetic`, strength 3, fullness 0.45, `angle` 50, pressure 0.75 left a broken streak on paper and over the undercoat. A `comber` 12 or a `fan` 16 left two ribbons, and a `hake` laid over at pressure 0.3 only specks.
- **Pale hairs over a dark** are one coat of `opaque_white` from a `round` or `rigger` of size 1 after a `dry`. Over a dark of 0.23 a load of 1.4 dried at 0.37 (a quiet strand), 2.6 at 0.42 and 3.7 at 0.53 (a tip that catches the light). Keep the strongest for the few hairs that turn into the light; `body-colour.md` has two coats and wider lines.

## The edge of the coat

Each coat was a wash of 1.0 that dried at 0.47, finished six ways along one side (the third row of the figure).

| Finish | What dried |
|---|---|
| Left alone | A hard scalloped edge with a dark rim: a cut-out. |
| Hairs flicked out of the wash at once, into a deep film | A fringe, with a dark bead at the root of each hair. |
| The same at a film of 0.2 | A fringe with soft roots and no beads. The one to use. |
| Tapered hairs over the dried edge (`round` 1.6, strength 1.5) | A crisp fringe with small dark overlaps at the roots. Acceptable where the wash could not be caught wet. |
| `comber` 4 flicked over the dried edge | Clumps of two or three parallel lines: a wet or spiky coat. |
| A clean `round` 8 at fullness 0.45 run along the wet edge | A soft band about 15 pixels wide with small blooms: down, or fur out of focus. |

A flick starts 9 pixels inside the wash and travels 16 beyond it, pressure 0.8 falling to 0.04, the last stretch fast (`t` 0, 0.12, 0.18). From a load at the coat's own strength the hairs dried at 0.70 to 0.81 beside the coat's 0.47, because a thin stroke lays less. That is right for a pale fringe against paper; load stronger for a dark one.

## Eye, nose and whiskers

The table in `faces-and-detail.md` gives an animal's eye as one almond with a warm lid, which is right for a small one. An eye 35 pixels long or more takes the layers below; sizes are the badger's.

1. **Glint.** `mask` on bare paper: a stroke 1.2 pixels long at `radius` 1.6 for the near eye, one dab at 1.05 for the far. Under a dark of 0.08 they dried at 0.98 and 0.96. The smaller, quieter glint belongs to the far eye.
2. **Wash over the eye** with the head's undercoat, and `dry`.
3. **One pass on the dry wash, in this order**, each stroke into the last while it is wet:
   - iris: three strokes of burnt sienna and cobalt blue at 2.6 to 3.1, `round` 6 to 7;
   - socket: a brown-black at 2.0, `round` 10, one stroke 35 pixels long;
   - pupil: mostly `ivory_black` at 2.5, `round` 6.6, pressed fully, `speed` 70;
   - upper lid: `designer` 2.2 at 2.0, one line 45 pixels long, `speed` 80;
   - lower rim: `rigger` 1 at 1.2.
4. **`dry`, `unmask`**, then the pale lower lid: a few strokes of `opaque_white` at 0.7 to 0.9 warmed with an earth.

Paint only as much white of the eye as the pose shows; most mammals show none.

**A large pale iris (a cat).** The layers above are for a dark iris. A cat's is pale, and in dim light its pupil is wide. On a tabby whose eye openings were 60 pixels long (0.13.0):

1. **Glints**: two dots of fluid at `radius` 2.6 in each eye.
2. **The whole opening as one pale wet shape** (`hand_marks.puddle`, cut 2.2, fill 4.5): hansa yellow 0.36, burnt umber 0.07, cobalt blue 0.05, which dried at (226, 210, 135). While it is wet, charge an olive (hansa yellow 1.5, burnt umber 0.75, cobalt blue 0.5, fullness 0.6) along the top, under the lid. `dry`.
3. **The pupil as a disc with a cut edge** (`puddle` on a disc, cut 1.8, fill 4), a neutral dark at 3.4 (cobalt blue 2.8, burnt umber 1.7, burnt sienna 0.8: burnt umber with ultramarine dries red-brown in a shape this size). `dry`, then a second coat 2 pixels smaller and 2 higher, which leaves the first as the light in the bottom of the pupil.
4. **The lids inside the opening**, not on its outside. The upper is 5 to 6 pixels thick in all: `round` 2.2 to 3.0 at 4.2 to 5 of the neutral dark. The lower is 3: `round` 1.5 to 1.8 at 3.0 to 4.2 of a dark brown.
5. **Once the head is painted**: the iris that is left glazed old gold on its shaded parts (hansa yellow 0.22, burnt sienna 0.2, burnt umber 0.06, `round` 2.4); the lid's shadow carried onto the iris beside the pupil (cobalt blue 0.5, burnt umber 0.6, `round` 3) and never over a glint; buff on the paper round the eye (hansa yellow 0.10, burnt sienna 0.16, cobalt blue 0.03 at 0.30, and 0.18 at the inner corner, which stays the lightest light of the face); one soft dark between the brows.

Measure the pupil as a share of the opening between the inner edges of the lids: on this cat 0.6. Read off an enlargement as a dark disc it came out at 14.6 pixels for 17, because the top of the iris lies in the lid's shadow and hides the pupil's edge. At 0.48 of the opening, with the lids drawn outside it, two reviewers each called the eyes staring. A ring round each pupil (`round` 1.9 at 4.5 along a circle of radius 15.4, left open where a glint sits on the pupil's edge) and lids grown 3 pixels inward made them heavy-lidded.

- **Nose leather** is one dark shape laid wet (0.9 to 1.0), then darks of 2.2 to 3.4 for the nostrils and the underside once it is dry. Keep its highlight short and broken so that it follows the pebbled skin.
- **Whiskers over paper**: `rigger` 0.65 to 0.75, strength 0.8 to 1.1, pressure 0.05 rising to 0.7, 50 to 65 pixels long, `speed` 150. Start each at the pad and vary the arcs. **Over dark fur** they are the fine white line of `SKILL.md` ("Lights you could not reserve"), or masked before the wash.
- **Masked whiskers** must be masked where they are: `scripts/fit_light_lines.py` moves guides read off a grid onto the whiskers themselves, and writes the fluid (`radius` 1.4 at the root, tapering) and a reference with those whiskers painted out, so that measured washes run across them. After `unmask` each is bare paper at one width from root to tip. Tint the outer third toward the fur with a `round` 1.5, halfway between the fur's colour and a pale buff, and a drooping one along its outer half in the fur's own colour, so that they thin away. A reviewer still found them all of one weight; a different radius for each was not tried.
- **Mask nothing else in the coat.** The pale hairs inside the ears and short guard hairs over the shoulder, masked, dried as white rungs and dashes. A tint stroke narrower than the masked line leaves a white fringe each side of it, so the tinting took three rounds and still showed. Those are the pale hairs of "Which head draws a hair": `opaque_white` at 1.4 to 3.7 after the last `dry`.

## From a photograph, with the measured stages

"The coat, in order" is for a portrait laid by hand. When the likeness must come from one photograph, the head can be laid by the measured stages of `copying-a-reference.md`. That was done once: a long-haired tabby in a loaf, from a dim phone photograph taken indoors, on a sheet 1024 by 768 with the head 400 pixels across (0.13.0, five paints, 12,191 strokes). Two reviewers who were shown only the photograph and the sheet each said it mostly met the brief. The second overlaid the two and found eyes, nose, ears, forehead stripes and muzzle in register. Both found the coat inside the outline wanting. The steps, and what each cost:

1. **Isolate the animal.** `scripts/isolate_subject.py` takes the photograph and a mask of the animal (from a segmentation model given a few points on the animal and on the room, or a polygon read off the grid). The animal's lightest fur becomes paper, which also takes off the colour of the lamp. The values are lifted (black 0.03, gamma 0.56 took the cat's median value from 0.20 to 0.44). The fur's colour is carried past the mask's edge before the edge is feathered, so the soft edge is fur and not the room. `--let-go` fades the rear and the underside into the paper. Denoise a phone photograph before this if it is grainy; the lift doubles the grain in the darks.
2. **Fit and mask the whiskers** (`scripts/fit_light_lines.py`), and nothing else in the coat.
3. **Paint the eyes first, on bare paper**, after rehearsing them on a sheet of their own at the full sheet's scale. Then `scripts/keep_passage.py` puts them into the reference as they stand, and every stage keeps off them in their own shape. Score the rehearsal against the reference side by side (`scripts/compare.py`) before the sheet, not after the first review.
4. **Lay the first wash and soften its outline** (`copying-a-reference.md`, "A soft outline for the first wash"): stage 1's rows with `--cut-in 8` and no `dry`, 318 strokes in 58 seconds of the sheet's clock, the film along the edge still 0.18 to 0.57; then `scripts/soften_outline.py` (ears kept crisp) and `dry`. This is the soft band of "The edge of the coat", laid round the whole animal as down for the hairs to stand on.
5. **Stages 2 to 13** (`copy_reference.py --first 2`): 2 to 7 from a copy of the reference smoothed with a bilateral filter, 8 to 13 from one sharpened with an unsharp mask (radius 1.3, amount 0.45). Both copies were made with OpenCV; no script here makes them. The value gap was 0.045 after stage 7 and 0.036 after 13, with an edge agreement of 0.60. The stages place the head: stripes, eye rings, nose and muzzle. They lay the coat as the first fault of the table below, because every row and shape stroke is a medium touch on a dried wash: the reviewers saw stitching on the flank and plush where long fur should be.
6. **Hairs on the dry sheet** (`scripts/coat_hairs.py`): 285 `long` hairs through the ruff, cheeks and body at 0.3 to 1.25 (most near 0.8), then `outline` tufts. A first pass of 290 hairs, most at 1.7, read as wire on its own. A second of 526 paler and broader ones under it (0.12 to 0.49, rounds of 1.5 to 2.6, spacing halved, lengths a third longer) made a fringe of the two. The script's defaults now lay the first pass at 0.4 to 1.7 with most near 0.9. Together the hairs made the ruff, the cheek and the line of the back read as long fur. They did not mend the flank.
7. **`dry`, `unmask`, tint the whisker tips, lift what must be lifted, then `fix`** before anything broad, and mask the whiskers again where a glaze will cross them. After the fix, a glaze over the fine work dries clean: the body was a third too light beside the face (0.25 against the head's 0.50), and two glazes took it to 0.17. Each was a pass of `measured_layers.py` (`mop` 14) given the sheet's own look darkened by a third where the reference's fur is dark, its row ends run over with a damp `mop` 9. Shadows between the locks of a white ruff went on the same way: tapered strokes of a grey-buff (cobalt blue, burnt sienna and hansa yellow as 0.36, 0.50, 0.14) at 0.17 to 0.42, `round` 4.5 to 7.5, 80 to 170 pixels long and fanned from under the chin, each with its outer edge melted at once by a damp `round` 5 run one brush width and 3 pixels to the side. Nothing lifts after a fix, paint laid later included, so try any new mark on the scrap first.

Not tried: the head by these stages and the body by hand in the order at the top of this file, which the flank asks for.

## Diagnosing animal portraits

| What `look` shows | Cause | Fix |
|---|---|---|
| The coat reads as scales or flagstones | Many medium strokes laid on a dried wash, each drying with its own rim. The badger's coat took a pass of 208 strokes of a squirrel `round` 6 to 15 on its dried underwash, in a portrait of 4,485 strokes. | One connected wet wash for the mass, varied and charged while wet; texture afterwards in a few grouped hairs. |
| The fur is a grey cloud with no hairs in it | Hairs laid into a film | Locks into the film; hairs after a `dry`. |
| Hairs read as ticks or a pattern | Even spacing, one length, one direction | Groups that overlap, varied in length, following the map. |
| The animal is a cut-out | The wash edge left alone, or outlined | Flick the fringe out of the wash at a film of 0.2. |
| The head floats | No overlap of cheek and shoulder; no dark joining jaw and chest | Plan both overlaps and check them in the value view before the hairs. |
| Blunt, even bars in the coat | A `comber` at pressure 0.5 or more | Tapered rounds, or the `comber` at pressure 0.25. |
| White hairs chalky and all alike | `opaque_white` at full strength on every hair | 1.4 for most, 3.7 for the few that catch the light. |
| The eye is a black bead | The glint painted afterwards in white, or left out | Mask it first, so that it is paper. |
| The eyes stare | The pupil measured too small, or the lids drawn on the outside of the opening, so too much iris shows | Pupil as a share of the opening; a ring to widen it; lids grown into the opening. |
| White rungs in an ear, white dashes on the coat | Pale hairs masked | Mask whiskers and glints only; pale hairs in `opaque_white`. |
| Hairs past the outline read as wire, or a spider on an ear tip | Their strength taken from the deposit rule, which gives 6 to 7.8 for a dark colour on a round under size 2 | 0.3 to 1.3 by hand (`coat_hairs.py`). A stiff damp brush twice and a `blot` took the spider back to a pale brown before the sheet was fixed. |
| A grey-blue streak beyond the coat | A hue solved from a sample of nearly bare paper, which comes out as cobalt | Solve a hair's hue from inside the coat. On a fixed sheet it took two coats of `opaque_white` and hairs drawn back across it. |
| The head does not come forward from a dark body | A dim photograph lifted evenly: the flank dried at 0.25 beside a head of 0.50 | After `fix`, glaze the body down (0.17 did it); the lift that suits the head is too much for the body. |

The order of work follows demonstrations by Jo Allsopp (reserve the light in the eye first) and Carrie McKenzie (fur as overlapping strokes of varied length over an underwash).

# Shapes and fills: choosing a mark and making a shape

Read this before making or filling a shape from an idea, before using a brush head or a kind of mark you have not yet seen alone on this painting, and whenever a sheet looks boxy, stepped, dotted or patterned.

## A mark has a shape before it has a texture

Every head leaves its own footprint, whatever else it does. `figures/brush-shapes.png`, beside this file, shows all nineteen: a pressed stroke, a single press, and a stroke from a nearly dry brush. Look at it before choosing a head.

- **Round-headed brushes** (`round`, `mop`, `oval_wash`, `filbert`, `cats_tongue`, and the pointed ones) end in a curve or a point. Pressed once they leave a disc; pressed and lifted along a path, a leaf.
- **Flat-headed brushes** (`flat`, `bright`, `flat_wash`, `hake`, `comber`, `fan`, `angular`) end square. Pressed once they leave a bar; dragged, a band with cut ends, however broken or streaked the band is.

So choose the head by the shape the subject has, and only then by its texture. Things that grow or flow (water, cloud, foliage, stone, flesh, fur) are made of curves: paint them with round heads on curved, smoothed paths. Things that are made or cut (walls, planks, hulls, windows) have corners: a flat lays one in a stroke.

This is easy to get wrong when a head is picked from a list of effects. A whole study of the sea was painted with a comber, a hake and a stiff flat because their entries promise streaks and broken marks. They gave the streaks, and every mark was a box: falling water read as a fringe, the wall of a wave as a fence, the level sea as bricks. The same broken mark comes from a round brush laid over on its side (in the table below), with ragged ends in place of cut ones. Rock is grown, not cut: its planes are laid with a round too.

## See a new mark alone before you use it

You do not see a stroke as you make it, so nothing tells you its shape unless you look. Looking is cheap: one stroke and `look --region x0,y0,x1,y1`, which shows that part of the sheet enlarged, take about five seconds.

- **Trying something** (a head, a load, a speed, or a state of the paper you have not used on this painting): one stroke, one look, on the scrap sheet or on a copy of the painting directory. Copying it takes a moment, and the copy is your undo. Ask of each look what shape the mark is and whether the subject has that shape, not only whether it has the texture you were after. It is easy to try a comber on the scrap sheet, see that its streaks are crisper than a fan's, and keep it, having looked at the texture and never at the shape. Change one thing and try again; it usually takes two or three goes.
- **Doing something practised:** lay the whole pass, dry it, look once.

A mark is practised only when you have seen that mark alone. A fill tried on one shape is not practised on another: a fill tried only on outlines drawn in many points left two bare islands in the first long shape drawn in few.

Two things follow. Paint on a sheet you can see: a sheet 400 wide is shown at twice its size, so a brush of size 3 is a few blurred pixels, while 640 and wider is shown at its own size. And when the same fault shows twice (steps, bricks, dots, a fringe), question the mark itself, its head, its size and its path, before tuning its spacing or its count.

## Marks that make one thing together

Strata in a rock, ripples on water, leaves on a branch and hairs in a coat are each several marks making one thing, and marks laid evenly read as a pattern before they read as the thing: bars, stripes, a fringe. Make them unequal in size, in length and in the gaps between them, break the symmetry between one side of the picture and the other, and when it still reads as a pattern use fewer and larger shapes. Round marks do not save it: like bars in rows and even stripes are a pattern whatever their ends are.

## Shapes one stroke makes

| Shape | Stroke |
|---|---|
| A disc | One press of a `round` or `mop` whose `size` is the disc's radius, at pressure 1. The mop's disc is wetter and softer. |
| A lumpy mass (cloud, foliage, foam) | Several presses of unequal sizes, overlapping while wet. The edge is scalloped. |
| A leaf, a pebble, any long shape | One stroke down its length with a round about as wide as half the shape, pressed in the middle and lifted at both ends, `smooth`. |
| A crescent | The same stroke on a curved path. |
| A reed, a tapering line | A small round, the pressure falling to nothing. |
| A broken, sparkling mark | A `round` laid over (`angle` about 75), strong paint (about 5 in all), fullness 0.6, firm pressure. It leaves flecks along the path with ragged ends. With little paint or light pressure it leaves almost nothing, and the first try usually does. |
| A plank, a wall, a band with corners | One straight stroke of a `flat`, `smooth` false. |

`scripts/organic_marks.py` writes the first four as actions (`press`, `swelling`).

## Filling a larger shape

The same blob, about 170 pixels across, filled six ways and measured dry:

| Way | Strokes | Of the blob covered | Edge off by | What it looks like |
|---|---|---|---|---|
| Level rows of a small round | 19 | 84% | 4.6 px | A stepped edge; the brush ran dry half-way down |
| One brush round the outline, then inward (`follow_inward`) | 4 to 6 | 96 to 99% | 0.7 to 2.1 px | A smooth edge, an even fill. The smaller brush took more turns and kept the closer edge |
| The edge cut with a small round set in by its own width, the inside flooded at once in rows that overlap the cut (`faces-and-detail.md`, flooded inset polygons) | 9 to 16 | 98 to 99.9% | 0.4 to 0.8 px | The closest edge and the most even tone, for several times the strokes. Flooded with one stroke of a big brush that did not reach the cut, it covered 68% |
| Clear water first, colour dropped in | 4 | 93% | 2.8 px | A soft-edged, even shape |
| One stroke of a brush as wide as the shape | 1 | 67% | 14 px | A clean pebble: right for a long shape, too small for a round one |
| A few presses of brushes that fit | 4 | 68% | 15 px | A lumpy mass with a scalloped edge |

- **Follow the outline inward.** One brush goes round just inside the edge, set in by what it paints on each side of its path (about its `size` when pressed), and keeps going round, each turn further in and overlapping the last by a third, until it reaches the middle. The first turn is the edge, so the edge is one smooth stroke. `follow_inward(outline, brush, size, mix)` in `organic_marks.py` does it for any outline wider than the brush paints, round or long: each turn is set in along the edge's own normal and stops at the shape's middle, and the brush is reloaded for every turn.
- **Rows make a poor edge and a good inside.** Level rows cut to a curved outline leave it stepped, and rows that stop inside the sheet to leave a light end in steps too. Behind an edge that a small round has already cut they are sound, and they give the most even tone: use that when a shape must match an outline exactly, and the inward fill when a few strokes matter more.
- **A shape no wider than the brush paints is one swelling stroke** down its length, not a fill.
- **For a soft shape, water first:** lay the shape in clear water the same way, then drop strong colour into its middle. It spreads to a soft edge inside the water's outline.
- **A light shape that washes must cross** is kept with masking fluid laid in fat round strokes: `mask` takes a radius up to 40 and `smooth`, so one stroke turned round inside a lump keeps the whole lump with a rounded edge, and every wash can sweep over it. A mask stroke ends round like any round mark, so a plank kept with one fat stroke comes out round-nosed. For a thing with corners, draw its edges and ends in a thin line of masking fluid (radius about 1.5, set in by that much) and fill the inside with fat strokes that overlap by a few pixels: strokes that only just met let a hairline of wash through.

Trials belong on the scrap sheet; on the painting, one mark to a shape. A passage that seems to need twenty strokes wants a larger brush.

## A fill is a shape, not yet a picture

Everything above makes an edge and covers what lies inside it, evenly. That is right for a flat thing and wrong for water, sky, flesh or anything with depth or light on it. Lay such a shape the same way and work in it while it is wet: stronger towards one side, a second colour charged in, a light left, the far part paler than the near (`wet-in-wet.md`, `water.md`). A shape filled in one even tone and ringed with bare paper is a diagram of the thing.

A closed outline is also only for a thing seen whole, with something else all round it: a leaf, a pebble, a cloud. Ground, water and sky are seldom that. They run to the edges of the sheet or behind whatever stands in front of them, and they are laid as washes across the sheet, with the whole things made in them or over them. Having a way to fill a closed shape makes it tempting to draw everything as one, and a ground or a stretch of water drawn as a closed shape in the middle of the paper is a plan of it, seen from nowhere. Decide where the eye is, and what runs off the sheet, before any outline.

# Body colour: covering paint laid over dried paint

Read this before laying any light over paint that is already there (a glint, a white line, a light decided late, white heightening on a toned ground), before drawing a dark over a light, and before naming `azurite`, `malachite` or `shell_white` in `--palette`. Everything here needs 0.11.0 or later and was measured on it, on cold press, paper seed 3, sheets of 128 pixels. Values are the value view, where bare paper reads 0.96.

## When paint forms a new layer

Paint laid on paint that has dried lies over it as a new layer. Paint laid into paint still wet from being laid mixes with it, as it always has.

- **Dried means it reached no film and paper no fuller than 0.6** where the brush lands, as `look --at` reads it. `dry` makes the whole sheet so. A light laid after a `wait`, onto paint that never got that dry, mixes with it and greys.
- **Water does not undo it.** Wet a dried dark with clear water and charge white into it: the white lies over the dark where it lands and wherever the water carries it, though the longer it stays wet the more of the dark it takes up (0.53 over a dark of 0.16, against 0.63 laid on the dried dark directly).
- **A new layer's water lifts from the layer beneath, clear or coloured,** as clear water lifts from paint on bare paper. What it lifts mixes into the new paint, so covering paint over a dark that lifts easily (umber, ultramarine) takes up some of it, and over a staining dark (phthalo green, quinacridone rose) almost none: a broad field of white dried at 0.68 over the first kind (a dark of 0.16) and 0.79 over the second, though that dark was deeper (0.07). To keep a light clean over a lifting dark, lay it in one quick stroke, not worked or laid twice while wet.
- **Paint two layers down under covering paint is fixed.** It keeps its colour, but nothing lifts it any more, so lift what must be lifted before a covering coat and one more layer go over it. Transparent glazes and the same paint laid again are merged instead, and stay liftable.
- **Pencil drawn before the paint lies under it.** Two coats of white over a pencil line left it 0.08 darker than the white beside it (0.19 on bare paper); a cobalt glaze left it 0.09 darker than the glaze, as on paper. Erase what must vanish under a transparent passage. Pencil drawn on dried paint, and coloured pencil and pastel, lie on the paint instead (0.12.0, `dry-media.md`).

## Covering a dark with white

`opaque_white` at 4.5, a round 6 in three rows, over a dried dark of 0.16:

| Coats, with `dry` between | 0.11.0 | 0.10.0, which mixed it in |
|---|---|---|
| 1 | 0.63 | 0.43 |
| 2 | 0.78 | 0.53 |
| 3 | 0.84 | |

Over a middle value of 0.67: 0.79 in one coat, 0.85 in two. A thin veil (strength 1.5, one coat) over the dark reads 0.46: translucent and cool, for mist, haze and the scumbled light on a far hill.

Masking fluid still makes the cleaner light: a masked shape under a dark stays at paper (0.96). Mask what you can plan; lay covering white for what you cannot: lights finer than the mask's floor, lights decided late, and lights over paint that is already there.

## Fine white lines and dots

`opaque_white` at 4.5 over the dark of 0.16, `dry` between coats. Value along the line's lightest pixels:

| Brush | Value |
|---|---|
| rigger 0.8, two coats | 0.55 |
| rigger 1.0, one coat | 0.47 |
| rigger 1.0, two coats | 0.59 |
| rigger 1.3, two coats | 0.63 |
| rigger 1.3, two coats, over a middle value of 0.67 | 0.79 |
| round 1.5, one dab of 0.3 seconds (a glint) | 0.54 |

A fine white line reads as a light, not as paper: two coats go about half to three fifths of the way from the dark to white. Where a fine line must be paper-white, mask it (`actions.md`: the finest fluid keeps a band one to two pixels wide at 0.94 to 0.97).

## Darks over body colour

A dark drawn over dried white stays dark: a one-pixel `carbon_ink` line at 1 over two dried coats of white reads 0.047, as on bare paper, and a rigger 1 at `ivory_black` 4 reads 0.43 (0.29 on bare paper). So restate drawing over lights, and dot pupils, lashes and seams over a white laid earlier. The pen is the surer of the two, because it lays its ink without water and lifts nothing from the white.

White laid over dark lines already drawn covers them: two coats over a band of dark ticks (teeth drawn in a mouth) took the band from 0.76 to 0.88.

## The covering paints

Named in `--palette` only. Each covers in proportion to its thickness. A round 6 at 4.0 in three rows over the dark of 0.16:

| Paint | Colour | Two coats' worth (2.6) on white paper | One coat | Two coats |
|---|---|---|---|---|
| `azurite` | deep mineral blue | 0.32 | 0.26 | 0.30 |
| `malachite` | mineral green | 0.51 | 0.37 | 0.44 |
| `shell_white` | chalky warm white, gofun | 0.96 | 0.49 | 0.64 (four coats 0.77) |

- Azurite and malachite reach their own colour over a dark in one or two coats, which no transparent blue or green can: the dark shows through those.
- `shell_white` hides less than `opaque_white` by design and builds over three or four coats.
- Thick fills of azurite and malachite sit on the plateau of their colour, so they dry flat, without a dark rim.
- A covering tint of any other colour is `opaque_white` with a little of the colour in the same load.
- `hansa_yellow` is transparent from 0.11.0. Over a dried colour it glazes it; for a covering yellow, mix it with `opaque_white`.

## On a toned ground

On a sheet printed with a tone (`supports-and-grounds.md`), transparent paint only darkens the tone, a mask keeps the tone (not white), and every light above the tone is covering paint. Two coats of `opaque_white` at 4.5 brought a tan ground of 0.66 to 0.84. Lay transparent darks first or last; lay lights in covering paint after a `dry`.

## Cost

Each coat needs a `dry` before the next, and is a stroke against the stroke budget where one was set. A light that needs two coats costs two strokes and two waits where a masked one costs the mask.

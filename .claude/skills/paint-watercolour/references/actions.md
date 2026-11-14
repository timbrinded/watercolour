# Actions, brushes and paints

## Starting a painting

```bash
watercolor new <directory> --prompt "<brief>" [--size 512] [--height 360] [--seed 0] \
    [--palette name,name,...] [--stroke-budget 150] [--no-scrap] [--no-pencil]
```

- `--size` is the width in pixels (128 to 1024); `--height` makes the sheet other than square.
- `--palette` limits the paint box for this painting; the default is every paint.
- `--stroke-budget` caps strokes and blots on the painting itself. A pass that would exceed it is refused whole.
- `--seed` fixes the paper and the small variation in each brush load, so a painting replays identically.

## A pass

A pass is a JSON file holding a list of actions, carried out in order.

| Action | Fields | Notes |
|---|---|---|
| `load` | `brush`, `hair`, `size`, `pigments`, `water`, `rinse` | `size` is the radius in pixels, 0.5 to 80. `pigments` maps paint names to amounts totalling at most 8. `water` is how full the brush is, 0 to 1. With `"rinse": false` the new mix is added to what the same brush already holds. |
| `drain` | `water` | Touch the brush to a cloth until it holds no more than this share (0 to 1) of what it can. It keeps its colour and strength and loses only fullness. Takes one second. A brush at about 0.6 gives colour to a wet wash without flooding it, at about 0.45 pulls out an edge, and at 0.2 or less lifts paint. Loading with a lower `water` does the same for a fresh load; `drain` is for a brush already holding paint. |
| `stroke` | `path`, `speed`, `smooth`, `dwell`, `sheet` | Each point of `path` is `[x, y]`, `[x, y, pressure]`, or a mapping with `x` and `y` and any of `pressure` (0 to 1, default 0.7), `angle` (0 upright to 90 laid flat, default 45), `twist` (-90 to 90 degrees, flat heads only, default 0) and `t` (seconds). Either every point gives `t` or none does; times must not run backward, and a stroke lasts at most 120 seconds. Without times the brush travels at `speed` pixels per second (default 120). `smooth` curves the path, and everything set along it, through its points. A single point is a dab held for `dwell` seconds (default 0.3, at most 10); a longer dwell releases more water. |
| `blot` | `path`, `radius`, `sheet` | Radius 1 to 80. Takes up most surface water and loose pigment. |
| `pencil` | `path`, `darkness`, `smooth`, `sheet` | Underdrawing. Allowed only until paint first touches the painting. |
| `erase` | `path`, `radius`, `sheet` | Removes pencil. Same restriction. |
| `wait` | `seconds`, `at`, `film`, `sheet` | Up to 3600. Paint keeps moving and drying. With `"at": [x, y]` and `"film": depth` the wait ends as soon as the film of water at that point is no deeper than that, or after `seconds` if it never is: `{"action": "wait", "seconds": 300, "at": [240, 180], "film": 0.12}` is how to catch a wash as it loses its shine. |
| `dry` | | Waits until every sheet is dry. |
| `tilt` | `x`, `y`, `sheet` | Each within 0.3. Positive `y` pulls paint down the sheet. Stays until changed. |

`"sheet": "scrap"` sends an action to the 256 by 256 scrap sheet, if the painting has one. Scrap strokes do not count against the budget.

Each load picks up slightly more or less pigment and water than asked for, as a real brush does.

## Brushes

A brush is the shape of its head, the hair it is made of, and its size. `hair` is optional; left out, the head is made of the hair usual for its shape. The full guide, with a chart of every mark, is `docs/brushes.md`.

| Shape | Head | Use |
|---|---|---|
| `round` | round, pointed; a fifth of its width at no pressure | Most strokes; swells and tapers strongly. |
| `designer` | round, long and slim | Drawing and long expressive lines; widest range of width. |
| `spotter` | round, short | Small precise touches; holds little. |
| `rigger` | round, very long and thin | Lines. Holds twice a round. |
| `extended_point` | fine point on a large reservoir | Long fine lines without reloading. |
| `mop` | round, soft (squirrel) | Large washes; holds two and a half times a round. |
| `stippler` | round, stiff, hairs apart (badger) | Broken texture. |
| `flat` | flat, square end | Planes and bands with square ends; keeps 90% of its width at no pressure. |
| `bright` | flat, short | Short controlled planes. |
| `flat_wash` | flat, wide, soft (squirrel) | Broad even washes. |
| `hake` | flat, wide, thin (goat) | Background washes. |
| `comber` | flat, hairs apart | Several fine lines in one stroke: grass, fur. |
| `fan` | flat, thin, spread | Sparse streaks. |
| `angular` | flat, end cut at an angle | Strokes that begin and end on a slant. |
| `dagger` | slanted, tapering (sable blend) | Fine line to broad stroke by pressure. |
| `sword` | long slanted point (Kolinsky) | Lining; the widest change of width. |
| `filbert` | flat, rounded end | Petal and leaf marks. |
| `cats_tongue` | rounded end drawn to a point | As a filbert, with a point. |
| `oval_wash` | rounded, large, soft (squirrel) | Washes with a soft rounded edge. |

| Hair | Holds | Character |
|---|---|---|
| `kolinsky_sable` | most of the sables | Finest point, strong spring. |
| `red_sable` | standard | The baseline. |
| `sable_blend` | a little less | Firmer; parts sooner. |
| `squirrel` | more than twice a sable | Very soft; lays a lot of water, soft edge. |
| `goat` | nearly twice a sable | Soft, no point; for washes. |
| `badger` | little | Stiff; breaks the mark up. |
| `golden_synthetic` | least | Springy; runs dry and streaks soonest. |
| `synthetic_sable` | slightly less than sable | Behaves as sable. |
| `synthetic_squirrel` | nearly twice a sable | Behaves as squirrel. |

A brush that is running dry, moving fast, or carrying thick paint parts into clumps and leaves streaks along the stroke; on paper that already has a film of water even a thick load goes on unbroken. A full brush presses paint along less than a damp one does. A damp brush also carries wet paint on its tip and gives it back further along the stroke, and the emptier it is the more of that paint it keeps: this is why a brush at about 0.6 blends and one at 0.2 lifts. The edge of a flat head is square to its direction of travel unless `twist` turns it.

## Paints

| Name | Colour | Behaviour |
|---|---|---|
| `french_ultramarine` | warm deep blue | granulates strongly |
| `cerulean_blue` | cool pale blue | granulates strongly, fairly opaque |
| `cobalt_blue` | middle blue | smooth; the usual sky blue |
| `phthalo_green` | cold strong green | stains; hard to lift |
| `hookers_green` | deep green | stains moderately |
| `hansa_yellow` | clean lemon yellow | stains |
| `yellow_ochre` | dull earth yellow | fairly opaque |
| `quinacridone_rose` | cool rose | stains strongly |
| `cadmium_red` | warm opaque red | |
| `burnt_sienna` | orange-brown earth | the usual partner for a blue in a grey |
| `burnt_umber` | dark brown earth | granulates |
| `ivory_black` | black | use sparingly, in mixes |
| `opaque_white` | covering white | for final lights only |

Granulating paints settle into the grain of the paper and look speckled in a wash; in a film of water deeper than about 0.6 (a wash laid twice, a deep sky) they gather into distinct dark specks. Staining paints sink in and will not lift.

## Looking

```bash
watercolor look <directory> [--view color|value|wetness] [--region x0,y0,x1,y1] [--grid] [--scrap] [--at x,y ...]
```

- `color` is the painting as it appears; wet paint looks a little darker than it will dry.
- `value` shows lightness only.
- `wetness` shows how wet the sheet is on two continuous scales, with the scale drawn beneath the picture. The film of water standing on the surface runs from pale blue (a trace) through mid blue (0.4) and deep blue (0.8) to violet (1.5) and magenta (2.5, flooded). Paper with no film on it turns from grey (dry) to green as it fills with water.
- `--region` enlarges part of the sheet; `--grid` draws labelled pixel coordinates over it.
- `--at x,y` (repeatable) reads the wetness at a point as numbers: `film`, the depth of water on the surface, and `paper`, how full the sheet is from 0 to 1. Use it before any stroke whose result depends on wetness.

`status` reports the clock, strokes used against the budget, what is in the brush and how full it is, and for each sheet its `wetness` (the film at its deepest, the film's usual depth where there is one, and how full the damp paper is) and the share of it that is shiny (film over 0.15), moist (a thinner film), damp (no film, paper more than 0.6 full) or dry. Those four names are only landmarks on the two scales; the numbers are what to act on.

When the last pass stopped before its end, because the command was killed or a fault ended it, every report also carries `interrupted_pass`: `actions_completed` out of `actions_given`, and `seconds_passed_in_next_action`, the part of a `wait` or `dry` that had already run when it stopped. Giving the same `paint` command again carries on from there, and its report then has `resumed_after_action` with the number of actions it did not repeat. A pass that differs in any way is a new pass and starts from its first action.

`watercolor --version` prints the version. `drain`, `wait` with `film`, `--at` and the wetness scale need 0.5.0 or later; carrying on after a command is cut short needs 0.5.2.

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
| `stroke` | `path`, `speed`, `smooth`, `dwell`, `sheet` | Each point of `path` is `[x, y]`, `[x, y, pressure]`, or a mapping with `x` and `y` and any of `pressure` (0 to 1, default 0.7), `angle` (0 upright to 90 laid flat, default 45), `twist` (-90 to 90 degrees, flat heads only, default 0) and `t` (seconds). Either every point gives `t` or none does; times must not run backward, and a stroke lasts at most 120 seconds. Without times the brush travels at `speed` pixels per second (default 120). `smooth` curves the path, and everything set along it, through its points. A single point is a dab held for `dwell` seconds (default 0.3, at most 10); a longer dwell releases more water. |
| `blot` | `path`, `radius`, `sheet` | Radius 1 to 80. Takes up most surface water and loose pigment. |
| `pencil` | `path`, `darkness`, `smooth`, `sheet` | Underdrawing. Allowed only until paint first touches the painting. |
| `erase` | `path`, `radius`, `sheet` | Removes pencil. Same restriction. |
| `wait` | `seconds` | Up to 3600. Paint keeps moving and drying. |
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

A brush that is running dry, moving fast, or carrying thick paint parts into clumps and leaves streaks along the stroke. A full brush presses paint along less than a damp one does. The edge of a flat head is square to its direction of travel unless `twist` turns it.

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

Granulating paints settle into the grain of the paper and look speckled in a wash. Staining paints sink in and will not lift.

## Looking

```bash
watercolor look <directory> [--view color|value|wetness] [--region x0,y0,x1,y1] [--grid] [--scrap]
```

- `color` is the painting as it appears; wet paint looks a little darker than it will dry.
- `value` shows lightness only.
- `wetness` shows standing water in strong blue, damp paper in pale blue and dry paper in grey.
- `--region` enlarges part of the sheet; `--grid` draws labelled pixel coordinates over it.

`status` reports the clock, strokes used against the budget, what is in the brush and how full it is, and the share of each sheet that is shiny, moist, damp or dry.

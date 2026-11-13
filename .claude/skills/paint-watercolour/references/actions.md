# Actions, brushes and paints

## Starting a painting

```bash
uv run watercolor new <directory> --prompt "<brief>" [--size 512] [--height 360] [--seed 0] \
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
| `load` | `brush`, `size`, `pigments`, `water`, `rinse` | `size` is the radius in pixels, 0.5 to 80. `pigments` maps paint names to amounts totalling at most 8. `water` is how full the brush is, 0 to 1. With `"rinse": false` the new mix is added to what the same brush already holds. |
| `stroke` | `path`, `speed`, `smooth`, `dwell`, `sheet` | `path` is a list of `[x, y]` or `[x, y, pressure]`; pressure defaults to 0.7. `speed` is pixels per second, default 120; above about 150 the brush starts to skip. `smooth` curves the path through its points. A single point is a dab held for `dwell` seconds (default 0.3, at most 10); a longer dwell releases more water. |
| `blot` | `path`, `radius`, `sheet` | Radius 1 to 80. Takes up most surface water and loose pigment. |
| `pencil` | `path`, `darkness`, `smooth`, `sheet` | Underdrawing. Allowed only until paint first touches the painting. |
| `erase` | `path`, `radius`, `sheet` | Removes pencil. Same restriction. |
| `wait` | `seconds` | Up to 3600. Paint keeps moving and drying. |
| `dry` | | Waits until every sheet is dry. |
| `tilt` | `x`, `y`, `sheet` | Each within 0.3. Positive `y` pulls paint down the sheet. Stays until changed. |

`"sheet": "scrap"` sends an action to the 256 by 256 scrap sheet, if the painting has one. Scrap strokes do not count against the budget.

Each load picks up slightly more or less pigment and water than asked for, as a real brush does.

## Brushes

| Brush | Edge | Width at no pressure | Holds | Use |
|---|---|---|---|---|
| `round` | fairly crisp | 20% of full | standard | Most strokes; swells and tapers strongly with pressure. |
| `flat` | crisp, chisel-ended | 90% of full | standard | Planes, bands and blocks with square ends; parts into streaks soonest when dry. |
| `mop` | soft | 70% of full | two and a half times a round | Large washes and wetting the paper. |
| `rigger` | soft, fine | 40% of full | twice a round | Lines and fine detail. |

A brush that is running dry, moving fast, or carrying thick paint parts into clumps and leaves streaks along the stroke. A full brush presses paint along less than a damp one does.

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
uv run watercolor look <directory> [--view color|value|wetness] [--region x0,y0,x1,y1] [--grid] [--scrap]
```

- `color` is the painting as it appears; wet paint looks a little darker than it will dry.
- `value` shows lightness only.
- `wetness` shows standing water in strong blue, damp paper in pale blue and dry paper in grey.
- `--region` enlarges part of the sheet; `--grid` draws labelled pixel coordinates over it.

`status` reports the clock, strokes used against the budget, what is in the brush and how full it is, and the share of each sheet that is shiny, moist, damp or dry.

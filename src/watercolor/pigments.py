"""Pigment definitions.

Absorption and scattering are Kubelka-Munk coefficients per RGB channel. They are
recalled from the pigment table in Curtis et al. (1997) and have not been checked
against the paper; those for cobalt blue, burnt sienna, yellow ochre, opaque white
and ivory black are estimated from the colour of each paint. Density, staining and granulation are estimates of how each
paint behaves and are expressed for this engine's per-second rates.

The paints after ivory black were fitted through the renderer's own Kubelka-Munk mixing, to published hue angles and
ratings (MacEvoy's Handprint guide) and to the most chroma the display can show at each hue. The phthalo, dioxazine and
fluorescent paints absorb strongly in some channels and almost nothing in the rest, an idealisation that makes them
cleaner than real paint. Their density, staining and granulation follow the existing paints that behave most like them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pigment:
    name: str
    absorption: tuple[float, float, float]
    scattering: tuple[float, float, float]
    density: float  # settling rate out of suspension, per second
    staining: float  # resistance to lifting once deposited
    granulation: float  # preference for settling into the valleys of the paper


PIGMENTS: dict[str, Pigment] = {
    pigment.name: pigment
    for pigment in (
        Pigment("french_ultramarine", (0.86, 0.86, 0.06), (0.005, 0.005, 0.09), 0.030, 1.0, 0.80),
        Pigment("cerulean_blue", (1.52, 0.32, 0.25), (0.06, 0.26, 0.40), 0.040, 0.8, 0.90),
        Pigment("phthalo_green", (1.55, 0.47, 0.63), (0.01, 0.05, 0.035), 0.012, 8.0, 0.05),
        Pigment("hookers_green", (1.62, 0.61, 1.64), (0.01, 0.012, 0.003), 0.020, 3.0, 0.20),
        Pigment("hansa_yellow", (0.06, 0.21, 1.78), (0.50, 0.88, 0.009), 0.015, 3.0, 0.10),
        Pigment("quinacridone_rose", (0.22, 1.47, 0.57), (0.05, 0.003, 0.03), 0.012, 6.0, 0.05),
        Pigment("cadmium_red", (0.14, 1.08, 1.68), (0.77, 0.015, 0.018), 0.030, 2.5, 0.30),
        Pigment("burnt_umber", (0.74, 1.54, 2.10), (0.09, 0.09, 0.004), 0.035, 1.5, 0.60),
        Pigment("cobalt_blue", (1.15, 0.64, 0.22), (0.01, 0.03, 0.10), 0.030, 1.2, 0.20),
        Pigment("burnt_sienna", (0.31, 0.78, 1.26), (0.06, 0.03, 0.005), 0.030, 1.5, 0.25),
        Pigment("yellow_ochre", (0.11, 0.27, 0.80), (0.30, 0.25, 0.05), 0.035, 1.2, 0.25),
        # Opaque white (gouache): it scatters strongly and absorbs almost nothing, so it covers what lies beneath.
        Pigment("opaque_white", (0.004, 0.004, 0.006), (3.0, 3.0, 3.0), 0.080, 1.0, 0.0),
        Pigment("ivory_black", (1.9, 1.9, 1.8), (0.01, 0.01, 0.01), 0.030, 2.0, 0.30),
        # Paints a painting has only when its --palette names them; DEFAULT_PALETTE below leaves them out.
        # Transparent, smooth and staining, with the rates of phthalo green and quinacridone rose.
        Pigment("phthalo_blue", (2.20, 0.70, 0.08), (0.006, 0.010, 0.030), 0.012, 8.0, 0.05),
        Pigment("phthalo_turquoise", (2.60, 0.05, 0.25), (0.004, 0.006, 0.010), 0.012, 8.0, 0.0),
        Pigment("dioxazine_violet", (0.60, 2.50, 0.15), (0.010, 0.006, 0.030), 0.012, 6.0, 0.0),
        # A clear cool green that, unlike phthalo green, lifts evenly once dry.
        Pigment("viridian", (1.5, 0.35, 0.45), (0.02, 0.06, 0.05), 0.030, 1.0, 0.30),
        # Fluorescent paints: absorption near zero in the channels of their colour, so their chroma reaches what the
        # display can show. They do not glow, and are never lighter than the paper.
        Pigment("fluorescent_pink", (0.01, 2.60, 0.45), (0.005, 0.005, 0.005), 0.012, 6.0, 0.0),
        Pigment("fluorescent_yellow", (0.02, 0.005, 2.60), (0.005, 0.005, 0.005), 0.012, 6.0, 0.0),
    )
}

# The paint box a painting has when --palette does not name one: the first thirteen paints above, in their order,
# so that a painting begun without --palette has the same paints, and replays the same, as before the others existed.
DEFAULT_PALETTE: tuple[str, ...] = (
    "french_ultramarine",
    "cerulean_blue",
    "phthalo_green",
    "hookers_green",
    "hansa_yellow",
    "quinacridone_rose",
    "cadmium_red",
    "burnt_umber",
    "cobalt_blue",
    "burnt_sienna",
    "yellow_ochre",
    "opaque_white",
    "ivory_black",
)

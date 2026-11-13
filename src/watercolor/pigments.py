"""Pigment definitions.

Absorption and scattering are Kubelka-Munk coefficients per RGB channel. They are
recalled from the pigment table in Curtis et al. (1997) and have not been checked
against the paper; those for cobalt blue, burnt sienna, yellow ochre, opaque white
and ivory black are estimated from the colour of each paint. Density, staining and granulation are estimates of how each
paint behaves and are expressed for this engine's per-second rates.
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
    )
}

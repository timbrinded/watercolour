"""Engine trials: each paints one watercolor behaviour so it can be compared with the real medium.

    uv run python trials/engine_trials.py [trial ...]

Pictures are written to trials/output/. These exercise the engine directly and
are not paintings, so the rules of a painting session do not apply.
"""

import sys
import time
from collections.abc import Callable
from pathlib import Path

import torch
from PIL import Image, ImageDraw

from watercolor.brushes import BRUSH_TYPES, HAIRS
from watercolor.paper import generate_paper
from watercolor.pigments import PIGMENTS
from watercolor.rendering import render, render_view, to_image
from watercolor.simulation import Sheet
from watercolor.studio import Studio
from watercolor.together import paint_together

SIZE = 384
OUTPUT = Path(__file__).parent / "output"
PALETTE = list(PIGMENTS)


def new_studio(size: int = SIZE) -> Studio:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pigments = [PIGMENTS[name] for name in PALETTE]
    sheet = Sheet(generate_paper(size, size, 7, device), pigments)
    return Studio({"painting": sheet}, PALETTE)


def wash(
    studio: Studio, kind: str, size: float, pigments: dict[str, float],
    x0: float, x1: float, y0: float, y1: float,
) -> None:  # fmt: skip
    """Lay horizontal strokes down a rectangle, reloading the brush every third stroke."""
    y = y0 + size * 0.6
    count = 0
    while y < y1:
        if count % 3 == 0:
            studio.load_brush(kind, size, pigments, 1.0)
        studio.stroke("painting", [[x0, y, 0.9], [x1, y, 0.9]], 140.0, smooth=False)
        y += size * 1.1
        count += 1


def flat_wash(studio: Studio) -> None:
    wash(studio, "round", 16, {"french_ultramarine": 0.7}, 70, 310, 70, 300)
    studio.dry()


def graded_wash(studio: Studio) -> None:
    for band, strength in enumerate((4.0, 2.0, 1.0, 0.5, 0.2, 0.0)):
        studio.load_brush("flat", 16, {"quinacridone_rose": strength}, 1.0)
        y = 70 + band * 38
        studio.stroke("painting", [[60, y, 0.9], [320, y, 0.9]], 140, smooth=False)
    studio.dry()


def wet_in_wet(studio: Studio) -> None:
    wash(studio, "mop", 30, {}, 50, 330, 50, 330)
    studio.wait(20)
    studio.load_brush("round", 10, {"quinacridone_rose": 4.0}, 0.8)
    studio.stroke("painting", [[110, 120], [160, 200], [120, 280]], 100, smooth=True)
    studio.load_brush("round", 10, {"hansa_yellow": 4.0}, 0.8)
    studio.stroke("painting", [[230, 110], [200, 200], [260, 290]], 100, smooth=True)
    studio.dry()


def wet_on_dry_beside_wet(studio: Studio) -> None:
    """The same stroke crossing from dry paper into a wet patch."""
    wash(studio, "mop", 30, {}, 192, 340, 60, 320)
    studio.wait(15)
    studio.load_brush("round", 9, {"burnt_umber": 4.0}, 0.9)
    for y in (110, 190, 270):
        studio.stroke("painting", [[40, y], [330, y]], 110, smooth=False)
    studio.dry()


def glaze(studio: Studio) -> None:
    wash(studio, "flat", 18, {"hansa_yellow": 1.2}, 60, 250, 60, 320)
    studio.dry()
    wash(studio, "flat", 18, {"french_ultramarine": 0.8}, 150, 330, 100, 280)
    studio.dry()


def backrun(studio: Studio) -> None:
    wash(studio, "round", 18, {"burnt_umber": 0.6}, 60, 320, 60, 320)
    studio.wait(110)
    print("   backrun: paper when water is dropped in:", studio.sheets["painting"].stage_fractions())
    studio.load_brush("round", 12, {}, 1.0)
    studio.stroke("painting", [[190, 190]], 100, smooth=False)
    studio.stroke("painting", [[120, 260]], 100, smooth=False)
    studio.dry()


def dry_brush(studio: Studio) -> None:
    for row, water in enumerate((1.0, 0.4, 0.25, 0.15, 0.08)):
        studio.load_brush("flat", 12, {"burnt_umber": 4.0}, water)
        y = 70 + row * 60
        studio.stroke("painting", [[50, y, 0.8], [330, y, 0.8]], 260, smooth=False)
    studio.dry()


def granulation(studio: Studio) -> None:
    for column, name in enumerate(("french_ultramarine", "cerulean_blue", "phthalo_green", "quinacridone_rose")):
        x = 30 + column * 85
        wash(studio, "flat", 14, {name: 1.0}, x, x + 70, 50, 340)
    studio.dry()


def lifting(studio: Studio) -> None:
    wash(studio, "flat", 16, {"french_ultramarine": 1.2}, 40, 180, 60, 320)
    wash(studio, "flat", 16, {"phthalo_green": 1.2}, 200, 340, 60, 320)
    studio.dry()
    studio.load_brush("flat", 10, {}, 0.8)
    for _ in range(3):
        studio.stroke("painting", [[30, 190], [350, 190]], 80, smooth=False)
    studio.wait(10)
    studio.blot("painting", [[30, 190], [350, 190]], 14)
    studio.dry()


def brush_marks(studio: Studio) -> None:
    rows = (("round", 12), ("round", 4), ("flat", 10), ("mop", 22), ("rigger", 2.5))
    for row, (kind, size) in enumerate(rows):
        studio.load_brush(kind, size, {"french_ultramarine": 3.0, "burnt_umber": 2.5}, 0.9)
        y = 50 + row * 68
        path = [[40, y, 0.1], [120, y - 14, 0.6], [200, y + 14, 1.0], [280, y - 10, 0.5], [345, y, 0.05]]
        studio.stroke("painting", path, 120, smooth=True)
    studio.dry()


def loose_pools(studio: Studio) -> None:
    """Pale washes laid loosely, colour dropped in, then stronger colour as the paper turns damp."""
    pale = {"cadmium_red": 0.25, "hansa_yellow": 0.2}
    for path in (
        [[80, 80], [150, 60], [250, 90], [300, 70]],
        [[60, 120], [160, 110], [260, 130], [330, 120]],
        [[70, 165], [170, 160], [270, 175], [320, 165]],
        [[90, 210], [180, 205], [260, 220], [300, 250]],
        [[120, 255], [200, 250], [250, 270]],
    ):
        studio.load_brush("mop", 30, pale, 1.0)
        studio.stroke("painting", path, 120, smooth=True)
    studio.load_brush("round", 14, {"cadmium_red": 2.0}, 1.0)
    for point in ([170, 110], [215, 160], [190, 215]):
        studio.stroke("painting", [point], 100, smooth=False, dwell=1.2)
    studio.load_brush("round", 14, {"hansa_yellow": 3.0, "cadmium_red": 0.4}, 1.0)
    for point in ([250, 190], [140, 160]):
        studio.stroke("painting", [point], 100, smooth=False, dwell=1.2)
    studio.wait(45)
    print("   loose_pools: paper before the second layer:", studio.sheets["painting"].stage_fractions())
    studio.load_brush("round", 9, {"cadmium_red": 5.0, "quinacridone_rose": 2.0}, 0.9)
    studio.stroke("painting", [[175, 95], [200, 150], [185, 225]], 90, smooth=True)
    studio.wait(50)
    print("   loose_pools: paper before the water drops:", studio.sheets["painting"].stage_fractions())
    studio.load_brush("round", 10, {}, 1.0)
    studio.stroke("painting", [[270, 110]], 100, smooth=False, dwell=1.0)
    studio.stroke("painting", [[110, 200]], 100, smooth=False, dwell=1.0)
    studio.dry()
    studio.load_brush("round", 5, {"burnt_umber": 4.0, "french_ultramarine": 3.0}, 0.8)
    studio.stroke("painting", [[60, 300, 0.3], [150, 290, 0.8], [260, 300, 0.6], [340, 285, 0.2]], 100, smooth=True)
    studio.dry()


def softened_edge(studio: Studio) -> None:
    """A band of paint whose lower edge is softened with a clean damp brush."""
    studio.load_brush("round", 16, {"cobalt_blue": 1.5, "burnt_sienna": 1.2}, 1.0)
    studio.stroke("painting", [[60, 120, 0.9], [320, 120, 0.9]], 130, smooth=False)
    studio.load_brush("round", 16, {}, 0.45)
    studio.stroke("painting", [[60, 146, 0.9], [320, 146, 0.9]], 130, smooth=False)
    studio.load_brush("round", 16, {"cobalt_blue": 1.5, "burnt_sienna": 1.2}, 1.0)
    studio.stroke("painting", [[60, 260, 0.9], [320, 260, 0.9]], 130, smooth=False)
    studio.dry()


def lighthouse_study(studio: Studio) -> None:
    """The main steps of a lighthouse painting: graded sky around a reserved tower, shading, band, sea, rocks."""
    sheet = "painting"

    def tower_left(y: float) -> float:
        return 302 - (y - 170) * 0.085

    def tower_right(y: float) -> float:
        return 338 + (y - 170) * 0.085

    for path in (
        [[tower_left(170), 170], [tower_left(430), 430]],
        [[tower_right(170), 170], [tower_right(430), 430]],
        [[308, 120], [308, 170]], [[332, 120], [332, 170]], [[308, 120], [320, 108], [332, 120]],
        [[0, 430], [640, 430]],
    ):  # fmt: skip
        studio.pencil(sheet, path, 0.5)

    # Sky: a wash that weakens and warms toward the horizon, cut in around the tower first.
    rows = list(range(22, 430, 26))
    for index, y in enumerate(rows):
        fade = index / (len(rows) - 1)
        mix = {"cobalt_blue": 0.55 * (1 - 0.75 * fade), "burnt_sienna": 0.08 * fade, "yellow_ochre": 0.12 * fade}
        top, bottom = y - 16, y + 16
        if bottom > 112:
            lantern = top < 170
            left = 302 if lantern else tower_left(y)
            right = 338 if lantern else tower_right(y)
            studio.load_brush("round", 7, mix, 1.0)
            studio.stroke(
                sheet, [[left - 8, max(top, 100), 0.9], [left - 8 - 0.085 * 32 * (not lantern), bottom, 0.9]], 90, False
            )
            studio.stroke(
                sheet,
                [[right + 8, max(top, 100), 0.9], [right + 8 + 0.085 * 32 * (not lantern), bottom, 0.9]],
                90,
                False,
            )
            studio.load_brush("mop", 20, mix, 1.0)
            studio.stroke(sheet, [[0, y, 0.9], [left - 24, y, 0.9]], 150, False)
            studio.load_brush("mop", 20, mix, 1.0)
            studio.stroke(sheet, [[right + 24, y, 0.9], [640, y, 0.9]], 150, False)
        else:
            studio.load_brush("mop", 20, mix, 1.0)
            studio.stroke(sheet, [[0, y, 0.9], [320, y, 0.9]], 150, False)
            studio.load_brush("mop", 20, mix, 1.0)
            studio.stroke(sheet, [[320, y, 0.9], [640, y, 0.9]], 150, False)
    studio.dry()

    # Shadow side of the tower, its inner edge softened with a clean damp brush.
    grey = {"cobalt_blue": 0.7, "burnt_sienna": 0.55}
    studio.load_brush("round", 9, grey, 1.0)
    for offset in (8, 20):
        studio.stroke(
            sheet, [[tower_right(175) - offset, 176, 0.9], [tower_right(425) - offset - 4, 426, 0.9]], 100, False
        )
    studio.load_brush("round", 9, {}, 0.4)
    studio.stroke(sheet, [[tower_right(175) - 32, 176, 0.9], [tower_right(425) - 38, 426, 0.9]], 100, False)
    studio.load_brush("round", 5, grey, 0.9)
    studio.stroke(sheet, [[326, 124, 0.9], [326, 168, 0.9]], 80, False)
    studio.dry()

    # Red band, stronger on the shadow side while it is still wet.
    studio.load_brush("flat", 9, {"cadmium_red": 3.0}, 1.0)
    for y in (305, 320, 335):
        studio.stroke(sheet, [[tower_left(y) + 9, y, 0.9], [tower_right(y) - 9, y, 0.9]], 90, False)
    studio.load_brush("round", 8, {"cadmium_red": 4.0, "quinacridone_rose": 2.0, "cobalt_blue": 1.0}, 0.9)
    studio.stroke(sheet, [[tower_right(300) - 14, 302, 0.9], [tower_right(340) - 15, 338, 0.9]], 80, False)

    # Sea: a strong band on either side of the headland.
    for x0, x1 in ((0, 170), (470, 640)):
        studio.load_brush("flat", 11, {"french_ultramarine": 2.2, "cobalt_blue": 1.0}, 1.0)
        for y in (443, 462):
            studio.stroke(sheet, [[x0, y, 0.9], [x1, y, 0.9]], 130, False)
    studio.dry()

    # Headland: a pale warm wash with darks dropped in while damp, then dry brush for the rock.
    for path in (
        [[150, 450], [250, 436], [400, 436], [490, 450]],
        [[90, 490], [250, 470], [420, 470], [560, 490]],
        [[0, 520], [200, 505], [440, 505], [640, 520]],
        [[0, 560], [320, 550], [640, 560]],
        [[0, 600], [320, 595], [640, 600]],
    ):
        studio.load_brush("mop", 22, {"yellow_ochre": 0.7, "burnt_sienna": 0.25}, 1.0)
        studio.stroke(sheet, path, 130, True)
    studio.wait(50)
    studio.load_brush("round", 9, {"hookers_green": 1.5, "burnt_sienna": 1.5}, 0.9)
    for point in ([210, 470], [260, 500], [420, 480], [120, 540], [500, 545]):
        studio.stroke(sheet, [point], 100, False, dwell=0.6)
    studio.dry()
    studio.load_brush("flat", 10, {"burnt_umber": 3.5, "french_ultramarine": 1.5}, 0.14)
    for path in ([[120, 520], [300, 505]], [[330, 540], [560, 525]], [[60, 585], [260, 575]], [[380, 590], [600, 580]]):
        studio.stroke(sheet, path, 260, True)

    # Lantern and windows: small dark marks.
    studio.load_brush("rigger", 2.5, {"burnt_umber": 5.0, "french_ultramarine": 4.0}, 0.9)
    for path in (
        [[306, 150], [334, 150]], [[312, 124], [312, 148]], [[320, 122], [320, 148]], [[328, 124], [328, 148]],
        [[312, 215], [312, 222]], [[318, 272], [318, 279]], [[310, 380], [310, 388]],
    ):  # fmt: skip
        studio.stroke(sheet, path, 60, False)
    studio.dry()


POOL_OUTLINE = (
    [[90, 95], [160, 80], [240, 95], [300, 85]],
    [[70, 140], [170, 130], [260, 145], [320, 135]],
    [[75, 185], [175, 180], [265, 190], [315, 185]],
    [[95, 230], [185, 225], [255, 235], [300, 245]],
    [[125, 270], [200, 268], [255, 275]],
)
DAB_POINTS = (("cadmium_red", [150, 130]), ("french_ultramarine", [235, 160]), ("hansa_yellow", [180, 215]))


def lay_pool(studio: Studio, pigments: dict[str, float]) -> None:
    """Wet an irregular area with clear water or a very dilute wash."""
    for path in POOL_OUTLINE:
        studio.load_brush("mop", 30, pigments, 1.0)
        studio.stroke("painting", path, 120, smooth=True)


def drop_dabs(studio: Studio, strength: float, water: float, dwell: float = 0.5) -> None:
    """Touch concentrated paint into the pool with a small brush."""
    for name, point in DAB_POINTS:
        studio.load_brush("round", 11, {name: strength}, water)
        studio.stroke("painting", [point], 100, smooth=False, dwell=dwell)


def report_paper(studio: Studio, label: str) -> None:
    stages = {stage: round(share, 2) for stage, share in studio.sheets["painting"].stage_fractions().items()}
    print(f"   {label}: {stages}")


def dabs_into_clear_water(studio: Studio) -> None:
    lay_pool(studio, {})
    drop_dabs(studio, strength=8.0, water=0.6)
    studio.dry()


def dabs_into_pale_wash(studio: Studio) -> None:
    lay_pool(studio, {"yellow_ochre": 0.04, "burnt_sienna": 0.02})
    drop_dabs(studio, strength=8.0, water=0.6)
    studio.dry()


def dabs_into_moist_wash(studio: Studio) -> None:
    """The same dabs, placed after the base has lost its shine."""
    lay_pool(studio, {"yellow_ochre": 0.04, "burnt_sienna": 0.02})
    studio.wait(75)
    report_paper(studio, "dabs_into_moist_wash, when the dabs go in")
    drop_dabs(studio, strength=8.0, water=0.6)
    studio.dry()


def thick_and_thin_dabs(studio: Studio) -> None:
    """Left: little water and much pigment. Right: much water and little pigment."""
    lay_pool(studio, {"yellow_ochre": 0.04})
    for x, strength, water in ((140, 8.0, 0.3), (250, 1.2, 1.0)):
        for y in (130, 215):
            studio.load_brush("round", 11, {"quinacridone_rose": strength}, water)
            studio.stroke("painting", [[x, y]], 100, smooth=False, dwell=0.5)
    studio.dry()


def layered_dabs(studio: Studio) -> None:
    """Dabs into a wet pale wash, then a second set of stronger dabs as it turns damp."""
    lay_pool(studio, {"cadmium_red": 0.03, "hansa_yellow": 0.03})
    for name, point in (("cadmium_red", [160, 120]), ("hansa_yellow", [230, 180]), ("cadmium_red", [170, 220])):
        studio.load_brush("round", 11, {name: 8.0}, 0.6)
        studio.stroke("painting", [point], 100, smooth=False, dwell=0.5)
    studio.wait(70)
    report_paper(studio, "layered_dabs, at the second layer")
    for point in ([185, 150], [200, 200]):
        studio.load_brush("round", 8, {"cadmium_red": 8.0, "quinacridone_rose": 4.0}, 0.5)
        studio.stroke("painting", [point], 100, smooth=False, dwell=0.5)
    studio.wait(45)
    report_paper(studio, "layered_dabs, when clear water is dropped")
    studio.load_brush("round", 8, {}, 1.0)
    studio.stroke("painting", [[265, 115]], 100, smooth=False, dwell=0.8)
    studio.dry()


def brush_direction(studio: Studio) -> None:
    """Blobs of strong colour in a pale wash losing its shine, each worked with a clean damp brush differently."""
    lay_pool(studio, {"yellow_ochre": 0.04})
    studio.wait(50)
    report_paper(studio, "brush_direction, when the blobs go in")
    blobs = (
        ("cadmium_red", [120, 110]),
        ("french_ultramarine", [250, 110]),
        ("cadmium_red", [120, 220]),
        ("french_ultramarine", [250, 220]),
    )
    for name, point in blobs:
        studio.load_brush("round", 7, {name: 8.0}, 0.5)
        studio.stroke("painting", [point], 100, smooth=False, dwell=0.4)
    studio.wait(2)
    # Top left: pulled straight out to the right with firm pressure.
    studio.load_brush("round", 9, {}, 0.35)
    studio.stroke("painting", [[112, 110, 1.0], [200, 104, 1.0]], 110, smooth=False)
    # Top right: the same pull with a light touch.
    studio.load_brush("round", 9, {}, 0.35)
    studio.stroke("painting", [[258, 110, 0.2], [330, 100, 0.2]], 110, smooth=False)
    # Bottom left: a swirl around and through the blob.
    studio.load_brush("round", 9, {}, 0.35)
    swirl = [
        [120, 220, 0.9],
        [140, 205, 0.9],
        [150, 228, 0.9],
        [122, 248, 0.9],
        [92, 226, 0.9],
        [112, 190, 0.9],
        [160, 196, 0.9],
    ]
    studio.stroke("painting", swirl, 110, smooth=True)
    # Bottom right: a flat brush dragged down through the blob.
    studio.load_brush("flat", 12, {}, 0.35)
    studio.stroke("painting", [[250, 205, 0.9], [254, 285, 0.9]], 110, smooth=False)
    studio.dry()


def stroke_through_colours(studio: Studio) -> None:
    """One firm stroke carried through three wet colours on dry paper, and the reverse direction below it."""
    for row, direction in ((120, 1), (250, -1)):
        for name, x in (("hansa_yellow", 110), ("cadmium_red", 190), ("french_ultramarine", 270)):
            studio.load_brush("round", 14, {name: 3.0}, 1.0)
            studio.stroke("painting", [[x, row]], 100, smooth=False, dwell=0.6)
        studio.load_brush("round", 9, {}, 0.4)
        ends = [[70, row, 0.9], [320, row, 0.9]]
        studio.stroke("painting", ends[::direction], 120, smooth=False)
    studio.dry()


def swirled_dots(studio: Studio) -> None:
    """A blob of clear water, a dot of red, a dot of blue a few seconds later, then one swirl through both."""
    for path in (
        [[120, 150], [200, 135], [270, 155]],
        [[115, 200], [195, 195], [275, 205]],
        [[135, 245], [200, 250], [255, 240]],
    ):
        studio.load_brush("mop", 28, {}, 1.0)
        studio.stroke("painting", path, 120, smooth=True)
    studio.load_brush("round", 9, {"cadmium_red": 8.0}, 0.6)
    studio.stroke("painting", [[165, 185]], 100, smooth=False, dwell=0.5)
    studio.wait(4)
    studio.load_brush("round", 9, {"french_ultramarine": 8.0}, 0.6)
    studio.stroke("painting", [[225, 205]], 100, smooth=False, dwell=0.5)
    studio.wait(3)
    studio.load_brush("round", 8, {}, 0.35)
    swirl = [
        [165, 185, 0.9], [200, 165, 0.9], [240, 185, 0.9], [240, 220, 0.9], [200, 235, 0.9],
        [165, 215, 0.9], [175, 185, 0.9], [205, 180, 0.9], [222, 200, 0.9], [200, 212, 0.7],
    ]  # fmt: skip
    studio.stroke("painting", swirl, 110, smooth=True)
    studio.dry()


def load_variation(studio: Studio) -> None:
    """The same mix loaded afresh for each of ten strokes: no two loads are quite alike."""
    for row in range(10):
        studio.load_brush("round", 9, {"cobalt_blue": 1.2}, 0.9)
        y = 50 + row * 31
        studio.stroke("painting", [[50, y, 0.8], [330, y, 0.8]], 130, smooth=False)
    studio.dry()


def paint_strength(studio: Studio) -> None:
    """One brush and one stroke at five strengths of paint, from a thin wash to paste."""
    for row, strength in enumerate((0.3, 1.0, 2.5, 5.0, 8.0)):
        studio.load_brush("round", 10, {"french_ultramarine": strength}, 1.0)
        y = 60 + row * 62
        studio.stroke("painting", [[40, y, 0.8], [200, y + 12, 0.8], [345, y, 0.8]], 130, smooth=True)
        studio.stroke("painting", [[345, y + 24, 0.8], [200, y + 36, 0.8], [40, y + 24, 0.8]], 130, smooth=True)
    studio.dry()


SIZES = {"lighthouse_study": 640, "brush_shapes": 640, "brush_hairs": 640, "stroke_gestures": 640}


def wet_edges(studio: Studio) -> None:
    """Outlines left by water moving on its own: a flooded blot on dry paper, and drops into a damp wash."""
    for _ in range(2):
        studio.load_brush("mop", 24, {"quinacridone_rose": 1.2}, 1.0)
        studio.stroke("painting", [[100, 95]], 100, smooth=False, dwell=4.0)
    wash(studio, "round", 18, {"burnt_umber": 0.6}, 30, 354, 200, 360)
    studio.wait(80)
    report_paper(studio, "wet_edges, when the water is dropped in")
    studio.load_brush("round", 10, {}, 1.0)
    studio.stroke("painting", [[110, 280]], 100, smooth=False, dwell=0.6)
    studio.stroke("painting", [[250, 275]], 100, smooth=False, dwell=1.5)
    studio.load_brush("round", 14, {"french_ultramarine": 2.0}, 1.0)
    studio.stroke("painting", [[285, 95]], 100, smooth=False, dwell=3.0)
    studio.dry()


def bristle_marks(studio: Studio) -> None:
    """Long strokes that run the brush dry, so the hairs part and the mark breaks into streaks."""
    rows = (("flat", 14, 1.0, 140), ("flat", 14, 0.45, 140), ("flat", 14, 0.25, 300), ("round", 12, 0.45, 140))
    for row, (kind, size, water, speed) in enumerate(rows):
        studio.load_brush(kind, size, {"french_ultramarine": 2.0, "burnt_sienna": 1.5}, water)
        y = 45 + row * 62
        studio.stroke("painting", [[30, y, 0.8], [354, y, 0.8]], speed, smooth=False)
        studio.stroke("painting", [[354, y + 26, 0.8], [30, y + 26, 0.8]], speed, smooth=False)
    studio.load_brush("flat", 12, {"hookers_green": 3.0}, 0.4)
    studio.stroke("painting", [[40, 330], [120, 290], [200, 345], [280, 300], [350, 340]], 160, smooth=True)
    studio.dry()


CHART_MIX = {"french_ultramarine": 1.2, "burnt_sienna": 1.0}
CHART_ROW = 32


def brush_shapes(studio: Studio) -> None:
    """Every shape of brush head in its usual hair: a pressed stroke, a dab, and a stroke from a nearly dry brush."""
    for row, kind in enumerate(BRUSH_TYPES):
        y = 22 + CHART_ROW * row
        studio.load_brush(kind, 9, CHART_MIX, 1.0)
        studio.stroke("painting", [[120, y, 0.15], [250, y - 5, 1.0], [390, y + 3, 0.25]], 120, smooth=True)
        studio.load_brush(kind, 9, CHART_MIX, 1.0)
        studio.stroke("painting", [[440, y]], 100, smooth=False, dwell=0.4)
        studio.load_brush(kind, 9, CHART_MIX, 0.3)
        studio.stroke("painting", [[490, y, 0.8], [625, y, 0.8]], 160, smooth=False)
    studio.dry()


def brush_hairs(studio: Studio) -> None:
    """One round brush in every hair, drawn out and back until it runs dry: how far each carries its paint."""
    for row, hair in enumerate(HAIRS):
        y = 30 + 66 * row
        studio.load_brush("round", 9, CHART_MIX, 1.0, hair=hair)
        for line in range(3):
            ends = (120, 625) if line % 2 == 0 else (625, 120)
            studio.stroke("painting", [[ends[0], y + 18 * line, 0.8], [ends[1], y + 18 * line, 0.8]], 140, smooth=False)
    studio.dry()


GESTURES = (
    "round: angle 0, 45, 90",
    "designer: angle 0, 45, 90",
    "rigger: angle 0, 45, 90",
    "filbert: angle 0, 45, 90",
    "flat: angle 0, 45, 90",
    "flat: twist 0, 30, 60, 90",
    "flat: twist turning",
    "sword: twist turning",
    "dagger: twist turning",
    "round: slow then fast",
    "round: pause midway",
    "rigger: flick",
)


def stroke_gestures(studio: Studio) -> None:
    """What the hand can do within one stroke: the angle of the brush, the twist of its head, and its timing."""

    def row(index: int) -> float:
        return 24.0 + 50.0 * index

    def level(kind: str, index: int, settings: list[dict[str, float]]) -> None:
        span = 480.0 / len(settings)
        for column, setting in enumerate(settings):
            x, y = 150.0 + span * column, row(index)
            studio.load_brush(kind, 9, CHART_MIX, 0.8)
            studio.stroke(
                "painting", [{"x": x, "y": y, **setting}, {"x": x + span - 22, "y": y, **setting}], 120, smooth=False
            )

    for index, kind in enumerate(("round", "designer", "rigger", "filbert", "flat")):
        level(kind, index, [{"angle": 0.0}, {"angle": 45.0}, {"angle": 90.0}])
    level("flat", 5, [{"twist": 0.0}, {"twist": 30.0}, {"twist": 60.0}, {"twist": 90.0}])
    for index, kind in ((6, "flat"), (7, "sword"), (8, "dagger")):
        studio.load_brush(kind, 9, CHART_MIX, 1.0)
        turning = [{"x": 150.0 + 60.0 * step, "y": row(index) + (6.0 if step % 2 else -6.0), "twist": twist, "pressure": 0.9}
                   for step, twist in enumerate((0.0, 0.0, 90.0, 90.0, 0.0, 0.0, -90.0, -90.0, 0.0))]  # fmt: skip
        studio.stroke("painting", turning, 110, smooth=True)
    studio.load_brush("round", 9, CHART_MIX, 0.8)
    studio.stroke("painting", [{"x": 150, "y": row(9), "t": 0.0}, {"x": 330, "y": row(9), "t": 5.0}, {"x": 620, "y": row(9), "t": 5.6}], 120, smooth=False)  # fmt: skip
    studio.load_brush("round", 9, CHART_MIX, 0.8)
    studio.stroke("painting", [{"x": 150, "y": row(10), "t": 0.0}, {"x": 380, "y": row(10), "t": 1.5}, {"x": 380, "y": row(10), "t": 5.5}, {"x": 620, "y": row(10), "t": 7.0}], 120, smooth=False)  # fmt: skip
    for start in (150.0, 320.0, 490.0):
        studio.load_brush("rigger", 4, CHART_MIX, 1.0)
        flick = [{"x": start, "y": row(11) + 10, "pressure": 1.0, "t": 0.0}, {"x": start + 40, "y": row(11), "pressure": 0.8, "t": 0.5}, {"x": start + 130, "y": row(11) - 14, "pressure": 0.05, "t": 0.75}]  # fmt: skip
        studio.stroke("painting", flick, 120, smooth=True)
    studio.dry()


# Trials that are charts: each row of the sheet is labelled with the name of what was used on it.
CHART_LABELS: dict[str, tuple[int, int, list[str]]] = {
    "brush_shapes": (22, CHART_ROW, list(BRUSH_TYPES)),
    "brush_hairs": (30, 66, list(HAIRS)),
    "stroke_gestures": (24, 50, list(GESTURES)),
}


TRIALS: dict[str, Callable[[Studio], None]] = {
    trial.__name__: trial
    for trial in (
        flat_wash, graded_wash, wet_in_wet, wet_on_dry_beside_wet, glaze,
        backrun, dry_brush, granulation, lifting, brush_marks, loose_pools, softened_edge, lighthouse_study,
        dabs_into_clear_water, dabs_into_pale_wash, dabs_into_moist_wash, thick_and_thin_dabs, layered_dabs,
        brush_direction, stroke_through_colours, swirled_dots, load_variation, paint_strength, wet_edges, bristle_marks, brush_shapes, brush_hairs, stroke_gestures,
    )
}  # fmt: skip


def main() -> None:
    """Run the named trials, or all of them. Trials on sheets of the same size are painted together."""
    names = sys.argv[1:] or list(TRIALS)
    OUTPUT.mkdir(exist_ok=True)
    pictures = {}
    for size in sorted({SIZES.get(name, SIZE) for name in names}):
        group = [name for name in names if SIZES.get(name, SIZE) == size]
        started = time.perf_counter()
        studios = paint_together([TRIALS[name] for name in group], size, PALETTE, seeds=[7] * len(group))
        elapsed = time.perf_counter() - started
        print(f"{len(group)} trials at {size} pixels painted together in {elapsed:.1f} s")
        for name, studio in zip(group, studios):
            sheet = studio.sheets["painting"]
            pictures[name] = to_image(render(sheet))
            if name in CHART_LABELS:
                first, spacing, labels = CHART_LABELS[name]
                for row, label in enumerate(labels):
                    ImageDraw.Draw(pictures[name]).text((6, first + spacing * row - 5), label, fill="black")
            pictures[name].save(OUTPUT / f"{name}.png")
            print(f"{name:24s} simulated {studio.clock:7.1f} s, pigment on paper {float(sheet.deposited.sum()):9.1f}")
            if name == "wet_in_wet":
                to_image(render_view(sheet, "value")).save(OUTPUT / f"{name}_value.png")
    columns = min(len(names), 4)
    rows = -(-len(names) // columns)
    contact = Image.new("RGB", (columns * SIZE, rows * (SIZE + 18)), "white")
    for index, name in enumerate(names):
        corner = ((index % columns) * SIZE, (index // columns) * (SIZE + 18))
        contact.paste(pictures[name].resize((SIZE, SIZE), Image.Resampling.LANCZOS), (corner[0], corner[1] + 18))
        ImageDraw.Draw(contact).text((corner[0] + 4, corner[1] + 3), name, fill="black")
    contact.save(OUTPUT / "contact_sheet.png")


if __name__ == "__main__":
    main()

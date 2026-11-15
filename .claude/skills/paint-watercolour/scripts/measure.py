"""Print the mean colour and value of a look image (or any image) at sheet coordinates.

Usage: measure.py <image> <sheet_width> x,y[,half] [x,y[,half] ...]
The image may be an enlargement of the sheet; coordinates are always sheet pixels.
"""

import sys

import numpy as np
from PIL import Image

if len(sys.argv) < 4:
    raise SystemExit(__doc__)
image = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(float)
scale = image.shape[1] / float(sys.argv[2])
for argument in sys.argv[3:]:
    parts = [float(value) for value in argument.split(",")]
    x, y = parts[0] * scale, parts[1] * scale
    half = (parts[2] if len(parts) > 2 else 4) * scale
    # a patch that overhangs the top or left edge is cut at the edge: a negative start would count from the far side
    top, left = max(0, int(y - half)), max(0, int(x - half))
    patch = image[top : int(y + half) + 1, left : int(x + half) + 1].reshape(-1, 3).mean(0)
    value = (0.2126 * patch[0] + 0.7152 * patch[1] + 0.0722 * patch[2]) / 255
    print(f"({parts[0]:.0f},{parts[1]:.0f}) rgb=({patch[0]:.0f},{patch[1]:.0f},{patch[2]:.0f}) value={value:.2f}")

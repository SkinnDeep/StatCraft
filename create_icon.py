"""Original StatCraft geometric application icon, generated without external assets.

Designed with a distinct deep-indigo hexagonal/slate badge, cyan Gaussian bell curve,
and amber precision spark — visually distinct from StatCraft's green bar chart icon.
"""
from math import exp
from pathlib import Path
from PIL import Image, ImageDraw

canvas = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)

# Deep slate-indigo rounded badge with subtle cyan rim
draw.rounded_rectangle((12, 12, 244, 244), radius=46, fill='#162b45', outline='#2e6da4', width=6)
draw.rounded_rectangle((22, 22, 234, 118), radius=36, fill='#1f3b5c')

# Subtle reference grid lines inside badge
for y in (92, 142, 192):
    draw.line((40, y, 216, y), fill='#294a70', width=3)

# Filled area under Gaussian normal distribution curve
bell_points = []
for i in range(65):
    x = 40 + i * (176.0 / 64.0)
    z = (i - 32) / 13.5
    y = 192 - 118.0 * exp(-0.5 * z * z)
    bell_points.append((x, y))

polygon_pts = [(40, 192)] + bell_points + [(216, 192)]
draw.polygon(polygon_pts, fill=(45, 178, 212, 115))

# Crisp cyan Gaussian bell curve stroke
for idx in range(len(bell_points) - 1):
    draw.line([bell_points[idx], bell_points[idx + 1]], fill='#45d1f5', width=9)

# Baseline axis
draw.line((36, 194, 220, 194), fill='#e2eef8', width=6)

# Amber precision diamond spark at the distribution peak
cx, cy, r = 128, 72, 18
draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill='#ffb72b', outline='#ffffff')
draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill='#ffffff')

canvas.save(
    Path(__file__).parent / 'StatCraft.ico',
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)],
)

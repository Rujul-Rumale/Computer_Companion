"""Generate dark 5x5 dot-matrix tray icon. Run: python scripts/generate_tray_icon.py"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "app_icon.png"

SIZE = 64
GRID = 5
BG = "#080a0d"
BORDER = "#1a1f28"
ON = "#6e7681"
OFF = "#12151b"


def main():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 4
    draw.rounded_rectangle(
        (margin, margin, SIZE - margin, SIZE - margin),
        radius=12,
        fill=BG,
        outline=BORDER,
        width=1,
    )

    inset = 11
    area = SIZE - 2 * inset
    pitch = area / (GRID - 1)
    dot_r = pitch * 0.32

    # Static idle-ish pattern: soft center diamond
    for r in range(GRID):
        for c in range(GRID):
            lit = abs(r - 2) + abs(c - 2) <= 2
            cx = inset + c * pitch
            cy = inset + r * pitch
            color = ON if lit else OFF
            draw.ellipse(
                (cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
                fill=color,
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

"""Generate free pet sprite PNGs for PetSurface. Run once: python scripts/generate_pet_assets.py"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "pet" / "default"
ICON_OUT = ROOT / "assets"

STATES = {
    "idle": ("#8b949e", "#c9d1d9"),
    "listening": ("#3fb950", "#7ee787"),
    "thinking": ("#58a6ff", "#a5d6ff"),
    "acting": ("#f0883e", "#ffb77a"),
    "speaking": ("#bc8cff", "#ddbfff"),
    "error": ("#f85149", "#ffaba8"),
    "muted": ("#6e7681", "#9ea7b3"),
}

SIZE = 128


def _draw_pet(draw: ImageDraw.ImageDraw, body: str, highlight: str, frame: int, state: str):
    cx, cy = SIZE // 2, SIZE // 2 + 4
    bob = int(3 * math.sin(frame * math.pi / 2))
    cy += bob

    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gr = 52 + (frame % 2)
    gdraw.ellipse((cx - gr, cy - gr, cx + gr, cy + gr), fill=_hex(body, 40))
    return glow

def _hex(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return r, g, b, alpha


def draw_frame(state: str, frame: int) -> Image.Image:
    body, hi = STATES[state]
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = SIZE // 2, SIZE // 2 + 4
    bob = int(3 * math.sin(frame * math.pi / 2))
    cy += bob

    gr = 52 + (frame % 2)
    draw.ellipse((cx - gr, cy - gr, cx + gr, cy + gr), fill=_hex(body, 35))

    body_r = 40
    draw.ellipse((cx - body_r, cy - body_r, cx + body_r, cy + body_r), fill=_hex(body, 230), outline=_hex(hi, 200), width=2)

    ear_y = cy - 28
    for ex in (cx - 22, cx + 22):
        draw.ellipse((ex - 12, ear_y - 14, ex + 12, ear_y + 10), fill=_hex(body, 220), outline=_hex(hi, 180), width=1)

    eye_y = cy - 6
    eye_open = 7 if state != "error" else 4
    for ex in (cx - 16, cx + 16):
        draw.ellipse((ex - 7, eye_y - eye_open, ex + 7, eye_y + eye_open), fill=(20, 24, 30, 255))
        draw.ellipse((ex - 2, eye_y - 3, ex + 2, eye_y + 1), fill=(255, 255, 255, 220))

    mouth_y = cy + 18
    if state == "speaking":
        open_h = 6 + (frame % 3) * 2
        draw.ellipse((cx - 10, mouth_y - open_h, cx + 10, mouth_y + open_h), fill=(30, 35, 42, 255))
    elif state == "muted":
        draw.line((cx - 12, mouth_y, cx + 12, mouth_y), fill=(30, 35, 42, 255), width=3)
        draw.line((cx - 8, mouth_y - 10, cx + 8, mouth_y + 10), fill=(248, 81, 73, 220), width=2)
    elif state == "listening":
        draw.arc((cx - 10, mouth_y - 6, cx + 10, mouth_y + 8), 200, 340, fill=(30, 35, 42, 255), width=2)
    elif state == "thinking":
        draw.ellipse((cx - 4, mouth_y - 2, cx + 4, mouth_y + 6), fill=(30, 35, 42, 255))
    elif state == "error":
        draw.line((cx - 8, mouth_y - 4, cx + 8, mouth_y + 4), fill=(248, 81, 73, 255), width=2)
        draw.line((cx - 8, mouth_y + 4, cx + 8, mouth_y - 4), fill=(248, 81, 73, 255), width=2)
    else:
        draw.arc((cx - 8, mouth_y - 4, cx + 8, mouth_y + 6), 200, 340, fill=(30, 35, 42, 255), width=2)

    if state == "acting":
        draw.polygon([(cx, cy - 46), (cx + 8, cy - 34), (cx, cy - 30), (cx - 8, cy - 34)], fill=_hex(hi, 200))

    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for state in STATES:
        frames = 4 if state in ("idle", "speaking", "listening") else 1
        for i in range(frames):
            img = draw_frame(state, i)
            suffix = f"_{i}" if frames > 1 else ""
            img.save(OUT / f"{state}{suffix}.png")

    icon = draw_frame("idle", 0).resize((64, 64), Image.Resampling.LANCZOS)
    icon.save(ICON_OUT / "app_icon.png")
    print(f"Wrote pet assets to {OUT}")


if __name__ == "__main__":
    main()

"""Generate the Canvas-AI app icon (windows/CanvasAI.ico + preview PNG).

Run:  python windows/make_icon.py
Renders large and downsamples for clean anti-aliasing, then writes a
multi-resolution .ico for Windows.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

S = 1024  # supersample canvas


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def gradient(size, top, bottom):
    g = Image.new("RGB", (size, size))
    px = g.load()
    for y in range(size):
        c = lerp(top, bottom, y / (size - 1))
        for x in range(size):
            px[x, y] = c
    return g


def make():
    top = (99, 102, 241)     # indigo-500
    bottom = (124, 58, 237)  # violet-600

    base = gradient(S, top, bottom)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(base, (0, 0), rounded_mask(S, int(S * 0.22)))

    d = ImageDraw.Draw(img)
    cx = S // 2
    capY = int(S * 0.40)
    half = int(S * 0.30)   # half width of mortarboard
    h = int(S * 0.135)     # vertical radius of the diamond

    white = (255, 255, 255, 255)
    shadow = (40, 20, 80, 90)

    # subtle drop shadow under the board
    d.polygon(
        [(cx, capY - h + 18), (cx + half + 12, capY + 18),
         (cx, capY + h + 18), (cx - half - 12, capY + 18)],
        fill=shadow,
    )
    # mortarboard (diamond)
    d.polygon(
        [(cx, capY - h), (cx + half, capY), (cx, capY + h), (cx - half, capY)],
        fill=white,
    )

    # head band / cap base (trapezoid) below the board
    bandTop = capY + int(h * 0.35)
    bw_top, bw_bot = int(S * 0.165), int(S * 0.135)
    bandBot = bandTop + int(S * 0.16)
    d.polygon(
        [(cx - bw_top, bandTop), (cx + bw_top, bandTop),
         (cx + bw_bot, bandBot), (cx - bw_bot, bandBot)],
        fill=white,
    )
    # notch of indigo so the band reads as a cap
    d.polygon(
        [(cx - bw_top + 26, bandTop), (cx + bw_top - 26, bandTop),
         (cx, bandTop + int(S * 0.052))],
        fill=(0, 0, 0, 0),
    )

    # tassel: from the board's right tip, down, ending in a knot
    tx = cx + half - 6
    d.line([(tx, capY), (tx + 30, capY + int(S * 0.16))], fill=white, width=14)
    knot = (tx + 30, capY + int(S * 0.16))
    r = int(S * 0.022)
    d.ellipse([knot[0] - r, knot[1] - r, knot[0] + r, knot[1] + r], fill=white)
    d.rectangle([knot[0] - 9, knot[1], knot[0] + 9, knot[1] + int(S * 0.06)], fill=white)

    # AI sparkle (four-point star) top-right
    sx, sy = int(S * 0.74), int(S * 0.26)
    a, b = int(S * 0.075), int(S * 0.024)
    d.polygon([(sx, sy - a), (sx + b, sy - b), (sx + a, sy),
               (sx + b, sy + b), (sx, sy + a), (sx - b, sy + b),
               (sx - a, sy), (sx - b, sy - b)], fill=white)
    # small companion sparkle
    sx2, sy2 = int(S * 0.84), int(S * 0.40)
    a2, b2 = int(S * 0.035), int(S * 0.011)
    d.polygon([(sx2, sy2 - a2), (sx2 + b2, sy2 - b2), (sx2 + a2, sy2),
               (sx2 + b2, sy2 + b2), (sx2, sy2 + a2), (sx2 - b2, sy2 + b2),
               (sx2 - a2, sy2), (sx2 - b2, sy2 - b2)], fill=(255, 255, 255, 220))

    out = img.resize((256, 256), Image.LANCZOS)
    here = os.path.dirname(__file__)
    out.save(os.path.join(here, "CanvasAI.png"))
    out.save(
        os.path.join(here, "CanvasAI.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("Wrote windows/CanvasAI.ico and windows/CanvasAI.png")


if __name__ == "__main__":
    make()

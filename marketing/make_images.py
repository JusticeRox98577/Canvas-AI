"""Generate store images + a high-res icon for the product listing.

Run:  python marketing/make_images.py
Outputs (in marketing/): icon-1024.png, promo-hero.png, promo-features.png,
promo-study.png — promos are 1600x1200 (4:3), LemonSqueezy's recommended size.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = (99, 102, 241)      # indigo
BOT = (124, 58, 237)      # violet
BG = (11, 13, 18)
PANEL = (22, 27, 37)
WHITE = (255, 255, 255)
MUTED = (165, 176, 196)


def font(size: int, bold: bool = True):
    names = (["DejaVuSans-Bold.ttf"] if bold else []) + ["DejaVuSans.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:  # noqa: BLE001
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vgrad(w, h, top, bot):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        c = _lerp(top, bot, y / max(1, h - 1))
        for x in range(w):
            px[x, y] = c
    return img


def draw_icon(size: int) -> Image.Image:
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    base = vgrad(S, S, TOP, BOT)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.paste(base, (0, 0), mask)
    d = ImageDraw.Draw(img)
    cx = S // 2
    capY = int(S * 0.40)
    half = int(S * 0.30)
    h = int(S * 0.135)
    d.polygon([(cx, capY - h), (cx + half, capY), (cx, capY + h), (cx - half, capY)], fill=WHITE)
    bt, bb = int(S * 0.165), int(S * 0.135)
    bandTop = capY + int(h * 0.35)
    bandBot = bandTop + int(S * 0.16)
    d.polygon([(cx - bt, bandTop), (cx + bt, bandTop), (cx + bb, bandBot), (cx - bb, bandBot)], fill=WHITE)
    d.polygon([(cx - bt + 26, bandTop), (cx + bt - 26, bandTop), (cx, bandTop + int(S * 0.052))], fill=(0, 0, 0, 0))
    sx, sy = int(S * 0.74), int(S * 0.26)
    a, b = int(S * 0.075), int(S * 0.024)
    d.polygon([(sx, sy - a), (sx + b, sy - b), (sx + a, sy), (sx + b, sy + b),
               (sx, sy + a), (sx - b, sy + b), (sx - a, sy), (sx - b, sy - b)], fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


def _canvas():
    W, H = 1600, 1200
    img = vgrad(W, H, (24, 22, 46), BG).convert("RGB")
    return img, ImageDraw.Draw(img), W, H


def hero():
    img, d, W, H = _canvas()
    ic = draw_icon(240)
    img.paste(ic, (W // 2 - 120, 150), ic)
    d.text((W // 2, 440), "Canvas-AI", font=font(120), fill=WHITE, anchor="ma")
    d.text((W // 2, 600), "Your AI study partner for Canvas", font=font(50, False), fill=MUTED, anchor="ma")
    chips = ["Quiz yourself", "Flashcards", "Explain anything", "Due-date tracker"]
    f = font(38)
    pad = 28
    widths = [d.textlength(c, font=f) + pad * 2 for c in chips]
    gap = 24
    total = sum(widths) + gap * (len(chips) - 1)
    x = (W - total) / 2
    y = 760
    for c, w in zip(chips, widths):
        d.rounded_rectangle([x, y, x + w, y + 76], radius=38, fill=PANEL, outline=(60, 70, 110), width=2)
        d.text((x + w / 2, y + 38), c, font=f, fill=WHITE, anchor="mm")
        x += w + gap
    d.text((W // 2, H - 110), "Runs on your own AI · Private by design", font=font(34, False), fill=(120, 130, 150), anchor="ma")
    return img


def features():
    img, d, W, H = _canvas()
    d.text((W // 2, 110), "Everything you need to study smarter", font=font(64), fill=WHITE, anchor="ma")
    rows = [
        ("Reads your real courses", "Modules, pages, and files pulled straight from Canvas."),
        ("Study mode", "Practice quizzes, flashcards, explanations, and summaries."),
        ("Due-date dashboard", "Everything due across all your classes, in one place."),
        ("Draft assistant", "First drafts you review and submit yourself."),
        ("Course chat", "Ask anything about a class in plain English."),
        ("Private by design", "Your coursework isn't routed through anyone else."),
    ]
    fx = font(40)
    fb = font(30, False)
    cardW, cardH = 700, 230
    gx, gy = 60, 40
    x0 = (W - (cardW * 2 + gx)) / 2
    y0 = 230
    for i, (title, body) in enumerate(rows):
        cx = x0 + (i % 2) * (cardW + gx)
        cy = y0 + (i // 2) * (cardH + gy)
        d.rounded_rectangle([cx, cy, cx + cardW, cy + cardH], radius=24, fill=PANEL, outline=(50, 60, 90), width=2)
        d.rounded_rectangle([cx + 36, cy + 40, cx + 36 + 14, cy + 40 + 60], radius=7, fill=BOT)
        d.text((cx + 72, cy + 44), title, font=fx, fill=WHITE)
        # wrap body
        words = body.split()
        line = ""
        ty = cy + 110
        for w in words:
            test = (line + " " + w).strip()
            if d.textlength(test, font=fb) > cardW - 110:
                d.text((cx + 72, ty), line, font=fb, fill=MUTED)
                ty += 42
                line = w
            else:
                line = test
        d.text((cx + 72, ty), line, font=fb, fill=MUTED)
    return img


def study():
    img, d, W, H = _canvas()
    ic = draw_icon(130)
    img.paste(ic, (90, 80), ic)
    d.text((250, 110), "Study mode", font=font(80), fill=WHITE)
    d.text((250, 210), "Turn any course into an interactive study session", font=font(38, False), fill=MUTED)
    items = [
        "“Quiz me” — practice questions with an answer key",
        "“Flashcards” — key terms and definitions",
        "“Explain concepts” — plain-English breakdowns",
        "“Summarize” — fast review notes before a test",
    ]
    f = font(46, False)
    y = 380
    for it in items:
        d.ellipse([110, y + 14, 110 + 26, y + 40], fill=BOT)
        d.text((170, y), it, font=f, fill=WHITE)
        y += 130
    d.text((110, H - 120), "All grounded in your real Canvas material.", font=font(34, False), fill=(120, 130, 150))
    return img


def main():
    draw_icon(1024).save(os.path.join(HERE, "icon-1024.png"))
    draw_icon(512).save(os.path.join(HERE, "icon-512.png"))
    hero().save(os.path.join(HERE, "promo-hero.png"))
    features().save(os.path.join(HERE, "promo-features.png"))
    study().save(os.path.join(HERE, "promo-study.png"))
    print("Wrote marketing/icon-1024.png, icon-512.png, promo-hero.png, promo-features.png, promo-study.png")


if __name__ == "__main__":
    main()

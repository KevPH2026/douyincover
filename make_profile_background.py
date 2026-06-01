from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageOps

from brand_marks import paste_cut_k


SRC = Path("/Users/k/.codex/generated_images/019e7edf-6862-77e2-8ebd-655fbfc48857/ig_0dfd3f2f9cd2ee83016a1c7befd738819abc4f20ddb9bbfdf9.png")
AVATAR = Path("douyin-avatar.webp")
OUT = Path("profile-background")
OUT.mkdir(exist_ok=True)

FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_REG = "/System/Library/Fonts/STHeiti Light.ttc"


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def fit_banner(path, size=(1920, 640)):
    img = Image.open(path).convert("RGB")
    target_w, target_h = size
    w, h = img.size
    target_ratio = target_w / target_h
    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    return img.resize(size, Image.LANCZOS)


def avatar_stamp(size=128):
    av = Image.open(AVATAR).convert("RGB").resize((size, size), Image.LANCZOS)
    av = ImageOps.grayscale(av).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size - 1, size - 1), fill=255)
    av.putalpha(mask)
    stamp = Image.new("RGBA", (size + 18, size + 18), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.ellipse((0, 0, size + 17, size + 17), fill=(6, 8, 10, 225), outline=(178, 255, 82, 255), width=4)
    stamp.alpha_composite(av, (9, 9))
    return stamp


def add_base_overlay(img):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(1920):
        alpha = int(max(0, 225 * (1 - x / 1260)))
        od.line((x, 0, x, 640), fill=(0, 0, 0, alpha))
    for y in range(0, 640):
        edge = max(0, (y - 360) / 280)
        od.line((0, y, 1920, y), fill=(0, 0, 0, int(70 * edge)))
    return Image.alpha_composite(img, overlay)


def make():
    shutil.copy(SRC, OUT / "profile-bg-source.png")
    img = add_base_overlay(fit_banner(SRC).convert("RGBA"))
    d = ImageDraw.Draw(img)

    d.text((92, 78), "MR.K 在路上", font=font(46), fill=(248, 248, 242, 240))
    d.text((92, 138), "KevPH2026 / Deep thoughts on AI, business and human nature", font=font(28, False), fill=(248, 248, 242, 178))

    d.text((92, 248), "少和人对话，多和AI对话", font=font(52), fill=(252, 252, 246, 255))
    d.rectangle((92, 326, 432, 337), fill=(178, 255, 82, 255))
    d.text((92, 380), "Cross-border AI practitioner · Solo Creator · Field notes on the AI second half", font=font(28, False), fill=(248, 248, 242, 204))

    paste_cut_k(img, (1376, 142), 390, (178, 255, 82), opacity=0.24)
    img.alpha_composite(avatar_stamp(), (1640, 68))

    img.convert("RGB").save(OUT / "mrk-profile-background-1920x640.png", "PNG", optimize=True)

    # A taller fallback crop is useful if Douyin asks for a mobile-safe upload.
    mobile = img.resize((1500, 500), Image.LANCZOS)
    mobile.convert("RGB").save(OUT / "mrk-profile-background-1500x500.png", "PNG", optimize=True)

    safe = add_base_overlay(fit_banner(SRC).convert("RGBA"))
    sd = ImageDraw.Draw(safe)
    # Douyin mobile overlays status/menu icons on the top band and profile info
    # on the left/middle. Keep the banner text-free and push identity low-right.
    paste_cut_k(safe, (1436, 246), 320, (178, 255, 82), opacity=0.22)
    sd.rectangle((1248, 468, 1538, 478), fill=(178, 255, 82, 210))
    safe.convert("RGB").save(OUT / "mrk-profile-background-safe-1920x640.png", "PNG", optimize=True)

    clean = add_base_overlay(fit_banner(SRC).convert("RGBA"))
    cd = ImageDraw.Draw(clean)
    paste_cut_k(clean, (1436, 246), 320, (178, 255, 82), opacity=0.22)
    cd.rectangle((1248, 468, 1538, 478), fill=(178, 255, 82, 210))
    clean.convert("RGB").save(OUT / "mrk-profile-background-clean-1920x640.png", "PNG", optimize=True)


make()

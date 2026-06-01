from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from brand_marks import paste_cut_k


SRC_DIR = Path("/Users/k/.codex/generated_images/019e7edf-6862-77e2-8ebd-655fbfc48857")
AVATAR = Path("douyin-avatar.webp")
OUT = Path("collection-covers-personal")
OUT.mkdir(exist_ok=True)

FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_REG = "/System/Library/Fonts/STHeiti Light.ttc"


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def fit_square(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    side = min(w, h)
    return img.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2)).resize((1080, 1080), Image.LANCZOS)


def make_avatar_stamp(size=116, accent=(178, 255, 82)):
    avatar = Image.open(AVATAR).convert("RGB").resize((size, size), Image.LANCZOS)
    avatar = ImageOps.grayscale(avatar).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size - 1, size - 1), fill=255)
    avatar.putalpha(mask)

    stamp = Image.new("RGBA", (size + 16, size + 16), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.ellipse((0, 0, size + 15, size + 15), fill=(6, 8, 10, 220), outline=accent + (255,), width=4)
    stamp.alpha_composite(avatar, (8, 8))
    return stamp


def add_readability(img):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for x in range(1080):
        alpha = int(max(0, 198 * (1 - x / 760)))
        d.line((x, 0, x, 1080), fill=(0, 0, 0, alpha))
    for y in range(620, 1080):
        alpha = int(70 * ((y - 620) / 460))
        d.line((0, y, 1080, y), fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def centered_text(draw, box, text, text_font, fill):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=text_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 2), text, font=text_font, fill=fill)


def cover(src_name, out_name, title, en_title, subtitle, accent):
    src = SRC_DIR / src_name
    shutil.copy(src, OUT / f"bg-{out_name}")

    img = fit_square(src).filter(ImageFilter.UnsharpMask(radius=1.2, percent=110))
    img = add_readability(img)
    d = ImageDraw.Draw(img)

    d.text((80, 72), "MR.K 在路上", font=font(42), fill=(248, 248, 242, 240))
    d.text((80, 132), "KevPH2026 / Deep thoughts on AI", font=font(26, bold=False), fill=(248, 248, 242, 176))

    paste_cut_k(img, (730, 664), 310, accent, opacity=0.24)

    stamp = make_avatar_stamp(116, accent)
    img.alpha_composite(stamp, (852, 74))

    series_pill = (80, 218, 80 + 172, 272)
    d.rounded_rectangle(series_pill, radius=27, fill=accent + (245,))
    centered_text(d, series_pill, "SERIES", font(28), (8, 10, 13, 255))

    title_font = font(136 if title != "强者恒强" else 124)
    lines = ["AI", "下半场"] if title == "AI下半场" else [title]
    y = 348
    for line in lines:
        d.text((80, y), line, font=title_font, fill=(252, 252, 246, 255))
        y += int(title_font.size * .98)

    d.text((80, y + 26), en_title.upper(), font=font(32), fill=(248, 248, 242, 186))
    y += 74
    d.rectangle((80, y + 24, 80 + 300, y + 35), fill=accent + (255,))
    d.text((80, y + 78), subtitle, font=font(38, bold=False), fill=(248, 248, 242, 210))
    d.text((80, 946), "少和人对话，多和AI对话", font=font(32, bold=False), fill=(248, 248, 242, 168))

    img.convert("RGB").save(OUT / out_name, "PNG", optimize=True)


cover(
    "ig_0dfd3f2f9cd2ee83016a1c71a63e18819ab43dec4a79b0de57.png",
    "ai-xiabanchang-personal.png",
    "AI下半场",
    "AI Second Half",
    "模型 / Agent / 商业重构",
    (178, 255, 82),
)
cover(
    "ig_0dfd3f2f9cd2ee83016a1c71ef07d0819a8defb5e8935f1da2.png",
    "qiangzhe-hengqiang-personal.png",
    "强者恒强",
    "The Strong Get Stronger",
    "判断力 / 筹码 / 个体系统",
    (80, 214, 255),
)
cover(
    "ig_0dfd3f2f9cd2ee83016a1c72349b60819ab2a1e74de846d4b1.png",
    "zai-lushang-personal.png",
    "在路上",
    "On The Road",
    "出差 / 客户 / 一线观察",
    (255, 96, 82),
)

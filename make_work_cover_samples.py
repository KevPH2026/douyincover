from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

from brand_marks import paste_cut_k


BG_DIR = Path("collection-covers-personal")
AVATAR = Path("douyin-avatar.webp")
OUT = Path("work-cover-samples")
OUT.mkdir(exist_ok=True)

FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_REG = "/System/Library/Fonts/STHeiti Light.ttc"


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def crop_916(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    target = 9 / 16
    if w / h > target:
        nw = int(h * target)
        left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    else:
        nh = int(w / target)
        top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    return img.resize((1080, 1920), Image.LANCZOS)


def avatar_stamp(accent):
    size = 116
    av = Image.open(AVATAR).convert("RGB").resize((size, size), Image.LANCZOS)
    av = ImageOps.grayscale(av).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size - 1, size - 1), fill=255)
    av.putalpha(mask)
    stamp = Image.new("RGBA", (size + 16, size + 16), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.ellipse((0, 0, size + 15, size + 15), fill=(6, 8, 10, 220), outline=accent + (255,), width=4)
    stamp.alpha_composite(av, (8, 8))
    return stamp


def wrap_lines(text, max_chars=6):
    parts = []
    text = text.strip()
    while text:
        parts.append(text[:max_chars])
        text = text[max_chars:]
    return parts


def cover(bg, out, tag, title, en_title, summary, code, accent):
    img = crop_916(BG_DIR / bg).filter(ImageFilter.UnsharpMask(radius=1.1, percent=110)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(1080):
        alpha = int(max(0, 220 * (1 - x / 820)))
        od.line((x, 0, x, 1920), fill=(0, 0, 0, alpha))
    for y in range(1060, 1920):
        alpha = int(115 * ((y - 1060) / 860))
        od.line((0, y, 1080, y), fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)
    d = ImageDraw.Draw(img)

    d.text((82, 72), "MR.K 在路上", font=font(42), fill=(248, 248, 242, 240))
    d.text((82, 132), "KevPH2026 / Deep thoughts on AI", font=font(26, False), fill=(248, 248, 242, 176))
    img.alpha_composite(avatar_stamp(accent), (852, 74))

    d.rounded_rectangle((82, 238, 82 + 190, 292), radius=27, fill=accent + (245,))
    d.text((112, 252), tag, font=font(30), fill=(8, 10, 13, 255))

    lines = title.split("\n") if "\n" in title else wrap_lines(title, 6)
    size = 150 if max(len(line) for line in lines) <= 4 else 136
    y = 390
    for line in lines[:3]:
        d.text((82, y), line, font=font(size), fill=(252, 252, 246, 255))
        y += int(size * .98)

    d.text((82, y + 30), en_title.upper(), font=font(38), fill=(248, 248, 242, 188))
    y += 90

    d.rectangle((82, y + 28, 82 + 300, y + 39), fill=accent + (255,))
    d.text((82, y + 90), summary, font=font(42, False), fill=(248, 248, 242, 226))
    d.text((82, 1744), "少和人对话，多和AI对话", font=font(32, False), fill=(248, 248, 242, 168))
    d.text((860, 1740), code, font=font(30), fill=accent + (240,))

    paste_cut_k(img, (666, 1220), 390, accent, opacity=0.23)
    img.convert("RGB").save(OUT / out, "PNG", optimize=True)


cover(
    "bg-ai-xiabanchang-personal.png",
    "work-ai-saas.png",
    "AI下半场",
    "SaaS\n正在消失",
    "SaaS Is Disappearing",
    "模型厂商开始绕过 API，直接吞掉应用层。",
    "AI-03",
    (178, 255, 82),
)
cover(
    "bg-qiangzhe-hengqiang-personal.png",
    "work-judgment.png",
    "强者恒强",
    "判断\n不能外包",
    "Judgment Is Not Outsourced",
    "AI越强，越考验人的方向感和取舍能力。",
    "K-12",
    (80, 214, 255),
)
cover(
    "bg-zai-lushang-personal.png",
    "work-road.png",
    "在路上",
    "5天\n4城",
    "5 Days / 4 Cities",
    "我在一线看到：AI创业正在变成线下战争。",
    "ROAD-01",
    (255, 96, 82),
)

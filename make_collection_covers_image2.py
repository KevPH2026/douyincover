from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageFilter


SRC_DIR = Path("/Users/k/.codex/generated_images/019e7edf-6862-77e2-8ebd-655fbfc48857")
OUT = Path("collection-covers-image2")
OUT.mkdir(exist_ok=True)

FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_REG = "/System/Library/Fonts/STHeiti Light.ttc"


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def fit_square(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side)).resize((1080, 1080), Image.LANCZOS)


def text_box(draw, xy, text, fnt):
    box = draw.textbbox(xy, text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def cover(src_name, out_name, title, subtitle, accent):
    bg_src = SRC_DIR / src_name
    shutil.copy(bg_src, OUT / f"bg-{out_name}")

    img = fit_square(bg_src).filter(ImageFilter.UnsharpMask(radius=1.2, percent=115))
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Left readability gradient.
    for x in range(1080):
        alpha = int(max(0, 190 * (1 - x / 720)))
        d.line((x, 0, x, 1080), fill=(0, 0, 0, alpha))
    # Bottom grounding gradient.
    for y in range(600, 1080):
        alpha = int(95 * ((y - 600) / 480))
        d.line((0, y, 1080, y), fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    d = ImageDraw.Draw(img)

    d.text((82, 88), "MR.K 在路上", font=font(34), fill=(245, 245, 238, 232))
    d.text((82, 142), "作品合集  /  KevPH2026", font=font(24, bold=False), fill=(245, 245, 238, 178))

    title_font = font(112 if title != "强者恒强" else 104)
    line_gap = 20
    if title == "AI下半场":
        lines = ["AI", "下半场"]
    elif title == "在路上":
        lines = ["在路上"]
    else:
        lines = [title]

    y = 332
    for line in lines:
        d.text((82, y), line, font=title_font, fill=(250, 250, 244, 255))
        y += text_box(d, (82, y), line, title_font)[1] + line_gap

    d.rectangle((82, y + 8, 318, y + 16), fill=accent + (255,))
    d.text((82, y + 58), subtitle, font=font(38, bold=False), fill=(245, 245, 238, 226))

    img.convert("RGB").save(OUT / out_name, "PNG", optimize=True)


cover(
    "ig_0dfd3f2f9cd2ee83016a1c71a63e18819ab43dec4a79b0de57.png",
    "ai-xiabanchang-image2.png",
    "AI下半场",
    "模型 / Agent / 商业重构",
    (178, 255, 82),
)
cover(
    "ig_0dfd3f2f9cd2ee83016a1c71ef07d0819a8defb5e8935f1da2.png",
    "qiangzhe-hengqiang-image2.png",
    "强者恒强",
    "判断力 / 筹码 / 个体系统",
    (80, 214, 255),
)
cover(
    "ig_0dfd3f2f9cd2ee83016a1c72349b60819ab2a1e74de846d4b1.png",
    "zai-lushang-image2.png",
    "在路上",
    "出差 / 客户 / 一线观察",
    (255, 96, 82),
)

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path("collection-covers")
OUT.mkdir(exist_ok=True)

FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_REG = "/System/Library/Fonts/STHeiti Light.ttc"


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def draw_cover(filename, title, kicker, accent, bg, fg=(245, 247, 250)):
    size = 1080
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)

    # Subtle grid for a consistent tech/editorial system.
    grid = tuple(max(0, min(255, c + 18)) for c in bg)
    for x in range(0, size, 90):
        d.line((x, 0, x, size), fill=grid, width=1)
    for y in range(0, size, 90):
        d.line((0, y, size, y), fill=grid, width=1)

    d.rectangle((70, 70, 1010, 1010), outline=accent, width=8)
    d.rectangle((70, 70, 1010, 185), fill=accent)
    d.text((105, 105), "MR.K 在路上", font=font(38), fill=(14, 17, 22))

    d.text((105, 360), title, font=font(130), fill=fg)
    d.line((105, 535, 745, 535), fill=accent, width=10)
    d.text((105, 585), kicker, font=font(46, bold=False), fill=fg)
    d.text((105, 855), "关注我，一起看懂下一段变量", font=font(40), fill=accent)

    img.save(OUT / filename, "PNG", optimize=True)


draw_cover(
    "ai-xiabanchang.png",
    "AI下半场",
    "模型 / Agent / 商业重构",
    accent=(177, 255, 80),
    bg=(13, 16, 22),
)
draw_cover(
    "qiangzhe-hengqiang.png",
    "强者恒强",
    "判断力 / 筹码 / 个体系统",
    accent=(67, 214, 255),
    bg=(18, 24, 31),
)
draw_cover(
    "zai-lushang.png",
    "在路上",
    "出差 / 客户 / 一线观察",
    accent=(255, 91, 87),
    bg=(20, 18, 16),
)

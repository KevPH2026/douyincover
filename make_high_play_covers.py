#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import math
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "generated-covers" / "high-play"
WORKS_JSON = OUT_DIR / "high-works-25.json"
AVATAR = ROOT / "douyin-avatar.webp"
AI_BG_DIR = OUT_DIR / "ai-backgrounds"
AI_PROMPT_DIR = OUT_DIR / "ai-background-prompts"


PALETTE = {
    "ai": {
        "label": "AI下半场",
        "en": "AI SECOND HALF",
        "accent": "#b2ff52",
        "sub": "模型 / Agent / 商业重构",
    },
    "strong": {
        "label": "强者恒强",
        "en": "THE STRONG GET STRONGER",
        "accent": "#50d6ff",
        "sub": "判断力 / 筹码 / 个体系统",
    },
    "road": {
        "label": "在路上",
        "en": "ON THE ROAD",
        "accent": "#ff6052",
        "sub": "出差 / 客户 / 一线观察",
    },
}


FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


def font(size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    for item in FONT_CANDIDATES:
        path = Path(item)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size, index=0)
            except Exception:
                continue
    return ImageFont.load_default()


def rgb(hex_color: str) -> tuple[int, int, int]:
    clean = hex_color.strip("#")
    return tuple(int(clean[i : i + 2], 16) for i in (0, 2, 4))


def rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    return (*rgb(hex_color), alpha)


def seed_for(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def clean_text(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text or "")
    text = re.sub(r"#\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(text: str) -> str:
    table = {
        "AI已具备人类水平": "ai-human-level",
        "错过AI就是错过时代": "miss-ai-miss-era",
        "AI入口": "ai-only-entry",
        "2850亿美元灰飞烟灭": "saas-killer",
        "独立思考重要": "independent-thinking",
        "传统影视即将消亡": "aigc-video-era",
        "乔布斯：多和聪明的人交往": "jobs-smart-people",
        "乔布斯多和聪明的人交往": "jobs-smart-people",
        "字节跳动真正的产品创新": "bytedance-product",
        "字节跳动产品创新": "bytedance-product",
        "技术不再是壁垒": "tech-is-not-moat",
        "AI不是泡沫": "ai-not-bubble",
        "先问为什么": "ask-why",
        "OpenAI开始掀桌子": "openai-table-flip",
        "SaaS杀手已经下场": "saas-killer-2",
        "多和AI聊天": "talk-to-ai",
        "软件工作谁还活着": "who-survives",
        "认知很多筹码太少": "cognition-vs-chips",
        "算法不拿人当人": "algorithm-sees-no-human",
        "百家争鸣用户受益": "let-users-win",
        "不要犹豫直接上路": "stop-hesitating",
        "AI驱动增量": "ai-drives-growth",
        "此心光明AI作证": "bright-heart-ai",
        "定义场景才能赚钱": "scene-defines-money",
        "你的AI才是人脉": "your-ai-network",
        "保持清醒唯快不破": "stay-awake-speed",
        "4000亿美元清算开始": "four-hundred-billion-reset",
        "没有壁垒只有飞轮": "flywheel-no-moat",
    }
    compact = re.sub(r"\s+", "", text)
    for key, value in table.items():
        if key in compact:
            return value
    raw = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return raw[:48] or "cover"


@dataclass
class CoverPlan:
    category: str
    title: str
    en_title: str
    summary: str
    code: str
    theme: str
    style: str


def plan_for(caption: str, idx: int) -> CoverPlan:
    compact = re.sub(r"\s+", "", caption)
    lower = caption.lower()

    rules: list[tuple[str, CoverPlan]] = [
        ("《Nature》", CoverPlan("ai", "Nature：\nAI已具备\n人类水平", "AI IS HUMAN-LEVEL", "真正的洗牌，不在未来，就在现在。", "AI-02", "Nature 论文、AI 人类水平、深夜代码屏幕、城市窗口", "terminal")),
        ("ClaudeCode", CoverPlan("ai", "错过AI\n就是错过\n时代", "API IS EATING THE WORLD", "AI成为唯一入口，软件正在退场。", "AI-03", "ClaudeCode、Clawbot、API eating the world、机场深夜", "terminal")),
        ("2850亿美元灰飞烟灭", CoverPlan("ai", "2850亿美元\n灰飞烟灭", "THE SAAS KILLER", "基础模型开始绕过 API，直接吞掉应用层。", "AI-01", "纳斯达克、市值蒸发、SaaS 杀手、金融图表", "market")),
        ("观点本身不重要", CoverPlan("strong", "观点不重要\n独立思考\n重要", "THINK FOR YOURSELF", "别急着站队，先保住自己的判断。", "K-02", "独立思考、书桌、教育、空白笔记、低调压迫感", "desk")),
        ("传统影视即将消亡", CoverPlan("ai", "传统影视\n即将消亡", "AIGC VIDEO ERA", "视频全民化时代，已经开始重写内容行业。", "AI-04", "Seedance 2.0、电影片场、生成式视频、监视器光", "cinema")),
        ("强者恒强", CoverPlan("strong", "乔布斯：\n多和聪明的人\n交往", "STAY WITH SMART PEOPLE", "强者不是独自聪明，而是长期站在聪明人中间。", "K-01", "乔布斯、聪明人、深夜办公室、白板讨论", "desk")),
        ("真正产品创新", CoverPlan("ai", "字节跳动\n真正的\n产品创新", "PRODUCT INNOVATION", "产品创新不是口号，是飞轮速度。", "AI-05", "字节跳动、产品创新、增长飞轮、产品会议室", "product")),
        ("技术不再是壁垒", CoverPlan("ai", "技术不再是\n壁垒", "TECH IS NOT THE MOAT", "一人公司爆发后，注意力才是稀缺资源。", "AI-06", "一人公司、AI coding、注意力倒挂、创业者深夜", "terminal")),
        ("最大经济驱动变量", CoverPlan("ai", "AI不是泡沫\n是经济变量", "AI IS THE DRIVER", "财报已经说明，AI正在驱动新增量。", "AI-07", "Google 财报、Gemini 增长、资本开支、数据大屏", "market")),
        ("当你要解决问题", CoverPlan("strong", "解决问题前\n先问为什么", "ASK WHY FIRST", "真正的问题，通常藏在问题背后。", "K-03", "问题拆解、白板、因果箭头、深夜思考", "desk")),
        ("OpenAI也开始掀桌子", CoverPlan("ai", "OpenAI\n开始掀桌子", "OPENAI TABLE FLIP", "模型厂商下场，应用层进入淘汰赛。", "AI-08", "OpenAI Frontier、企业 Agent、SaaS 淘汰赛", "terminal")),
        ("AI吞噬Saas", CoverPlan("ai", "SaaS杀手\n已经下场", "THE SAAS KILLER", "这不是回调，是软件行业的重新定价。", "AI-09", "SaaS 杀手、Anthropic、资本市场、黑色交易屏", "market")),
        ("拉黑老登", CoverPlan("ai", "多和AI聊天\n拉黑老登", "TALK TO AI MORE", "连接 AI 的密度，会重写人的圈层。", "AI-10", "AI 聊天、未来社交、黑色手机界面、城市夜色", "terminal")),
        ("SEO已死", CoverPlan("ai", "软件工作\n谁还活着", "WHO SURVIVES", "旧岗位被拆掉后，真正活下来的是新入口。", "AI-11", "旧软件岗位消失、终端代码、岗位墓碑隐喻但无文字", "terminal")),
        ("筹码", CoverPlan("strong", "认知很多\n筹码太少", "CHIPS BEAT TALK", "认知不是装点，筹码才决定容错率。", "K-04", "筹码、认知、深夜书桌、冷静现实感", "desk")),
        ("不拿人当人", CoverPlan("strong", "算法\n不拿人当人", "ALGORITHM SEES NO HUMAN", "当人性被量化，清醒就是第一层防线。", "K-05", "算法工程师、数据监控、注意力机器、冷色屏幕", "terminal")),
        ("百家争鸣", CoverPlan("ai", "百家争鸣\n用户受益", "LET USERS WIN", "竞争最后应该奖励用户，而不是吞掉用户。", "AI-12", "模型竞争、多个光源、用户受益、科技圆桌", "product")),
        ("不要犹豫", CoverPlan("road", "不要犹豫\n直接上路", "JUST GET MOVING", "想做成事，先把状态拉起来。", "ROAD-01", "上路、行动、城市夜路、心中有火眼里有光", "road")),
        ("AI在驱动增量", CoverPlan("ai", "AI驱动增量", "AI DRIVES GROWTH", "巨头还在加速，说明变量是真的。", "AI-13", "AI 增量、Google Cloud、增长曲线、数据中心", "market")),
        ("荣幸之至", CoverPlan("strong", "此心光明\nAI作证", "BRIGHT HEART", "真正的对话，是把自己问清楚。", "K-06", "王阳明、AI 对话、安静书房、光落在笔记本", "desk")),
        ("场景", CoverPlan("ai", "定义场景\n才能赚钱", "SCENE DEFINES MONEY", "未来的生意，先争夺场景定义权。", "AI-14", "场景商业、AI agent、客户现场、空间入口", "product")),
        ("Your AI is your net worth", CoverPlan("ai", "你的AI\n才是人脉", "YOUR AI IS NET WORTH", "人脉退场，AI连接质量上桌。", "AI-15", "AI 社交网络、连接节点、手机与电脑、未来入口", "terminal")),
        ("保持清醒", CoverPlan("strong", "保持清醒\n唯快不破", "STAY AWAKE MOVE FAST", "背叛过去最蠢，速度才是护城河。", "K-07", "保持清醒、速度、武功唯快不破、冷静书桌", "desk")),
        ("4000亿美元", CoverPlan("ai", "4000亿美元\n清算开始", "THE RESET BEGINS", "资本不等完美代码，只会先重估人力成本。", "AI-16", "4000 亿美元蒸发、Claude、SaaS 黑莓时刻、交易屏", "market")),
        ("没有壁垒", CoverPlan("strong", "没有壁垒\n只有飞轮", "NO MOAT ONLY FLYWHEEL", "产品壁垒很薄，飞轮速度才是真的。", "K-08", "互联网产品、飞轮、SaaS、创新低水平内卷", "product")),
    ]

    for key, plan in rules:
        if key in compact or key.lower() in lower:
            return plan

    if any(k in lower for k in ["ai", "saas", "openai", "google", "gemini", "api", "agent"]):
        return CoverPlan("ai", "AI\n下半场", "AI FIELD NOTE", "看懂模型之后，才看得懂生意。", f"AI-{idx:02d}", caption[:60], "terminal")
    return CoverPlan("strong", "强者\n恒强", "STRONG FIELD NOTE", "差距会在判断里继续拉开。", f"K-{idx:02d}", caption[:60], "desk")


def draw_gradient(draw: ImageDraw.ImageDraw, w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)


def add_noise(img: Image.Image, amount: int = 18) -> Image.Image:
    rnd = random.Random(seed_for(img.tobytes()[:512].hex()))
    noise = Image.new("L", img.size, 0)
    data = bytearray(noise.size[0] * noise.size[1])
    for i in range(len(data)):
        data[i] = max(0, min(255, 128 + rnd.randint(-amount, amount)))
    noise.putdata(data)
    overlay = Image.merge("RGBA", (noise, noise, noise, Image.new("L", img.size, 22)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def draw_background(plan: CoverPlan, caption: str) -> Image.Image:
    w = h = 1080
    rnd = random.Random(seed_for(plan.title + caption))
    accent = PALETTE[plan.category]["accent"]
    acc = rgb(accent)
    img = Image.new("RGBA", (w, h), (5, 7, 10, 255))
    d = ImageDraw.Draw(img, "RGBA")

    base_top = (4, 7, 9)
    base_bottom = (18 + acc[0] // 18, 23 + acc[1] // 20, 28 + acc[2] // 18)
    draw_gradient(d, w, h, base_top, base_bottom)

    for _ in range(34):
        x = rnd.randint(-160, w + 120)
        y = rnd.randint(-120, h + 120)
        r = rnd.randint(35, 170)
        alpha = rnd.randint(12, 38)
        color = (*acc, alpha) if rnd.random() > 0.42 else (255, 255, 255, rnd.randint(8, 22))
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    # Window/city bokeh on the right side.
    for _ in range(58):
        x = rnd.randint(520, 1120)
        y = rnd.randint(80, 760)
        r = rnd.randint(2, 9)
        color = rnd.choice([(255, 210, 138, 80), (*acc, 70), (160, 220, 255, 45)])
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    # Scene objects.
    if plan.style in {"terminal", "market"}:
        # Laptop.
        sx = rnd.randint(560, 650)
        sy = rnd.randint(390, 520)
        d.rounded_rectangle([sx, sy, sx + 430, sy + 265], radius=18, fill=(8, 14, 18, 220), outline=(*acc, 80), width=2)
        for i in range(16):
            y = sy + 28 + i * 13
            x = sx + 28 + rnd.randint(0, 24)
            d.line([x, y, x + rnd.randint(90, 310), y], fill=(*acc, rnd.randint(45, 100)), width=2)
        if plan.style == "market":
            pts = []
            for i in range(8):
                pts.append((sx + 40 + i * 48, sy + 190 - rnd.randint(-35, 90)))
            d.line(pts, fill=(*acc, 170), width=5)
            for x, y in pts:
                d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(*acc, 150))
        d.polygon([(sx - 40, sy + 285), (sx + 500, sy + 285), (sx + 570, sy + 355), (sx - 115, sy + 355)], fill=(20, 24, 27, 210))
    elif plan.style == "cinema":
        d.rounded_rectangle([590, 360, 1000, 600], radius=24, fill=(10, 12, 15, 230), outline=(*acc, 90), width=3)
        d.rectangle([620, 390, 970, 570], fill=(18, 26, 30, 210))
        for y in [420, 470, 520]:
            d.line([635, y, 950, y + rnd.randint(-22, 22)], fill=(*acc, 80), width=3)
        d.ellipse([725, 675, 1010, 960], outline=(*acc, 65), width=22)
    elif plan.style == "road":
        d.polygon([(560, 1080), (740, 520), (850, 520), (1030, 1080)], fill=(24, 25, 26, 190))
        d.line([795, 1080, 795, 530], fill=(*acc, 120), width=8)
        d.line([0, 675, 1080, 515], fill=(*acc, 40), width=3)
    else:
        # Desk/notebook/whiteboard.
        d.rounded_rectangle([590, 620, 1020, 870], radius=22, fill=(230, 224, 208, 34), outline=(255, 255, 255, 30), width=2)
        for i in range(9):
            y = 655 + i * 22
            d.line([630, y, 960, y + rnd.randint(-8, 8)], fill=(255, 255, 255, 34), width=2)
        d.rounded_rectangle([610, 300, 1005, 520], radius=16, fill=(240, 246, 248, 22), outline=(*acc, 68), width=2)
        for i in range(5):
            x = 650 + i * 64
            y = 410 + rnd.randint(-48, 40)
            d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(*acc, 110))
            if i:
                px = 650 + (i - 1) * 64
                py = 410 + rnd.randint(-48, 40)
                d.line([px, py, x, y], fill=(*acc, 80), width=3)

    # Diagonal system lines.
    for _ in range(7):
        y = rnd.randint(130, 520)
        d.line([560, y, 1060, y - rnd.randint(80, 170)], fill=(*acc, rnd.randint(28, 62)), width=1)

    # Left readability wash and vignette.
    wash = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wash, "RGBA")
    for x in range(w):
        t = max(0, 1 - x / 760)
        wd.line([(x, 0), (x, h)], fill=(0, 0, 0, int(196 * t)))
    img = Image.alpha_composite(img, wash)

    vig = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-260, -220, 1340, 1360], fill=255)
    vig = Image.eval(vig.filter(ImageFilter.GaussianBlur(90)), lambda p: 255 - p)
    vimg = Image.new("RGBA", (w, h), (0, 0, 0, 150))
    vimg.putalpha(vig.point(lambda p: int(p * 0.55)))
    img = Image.alpha_composite(img, vimg)
    img = add_noise(img, 12)
    return img.convert("RGB")


def cover_crop(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    img = img.convert("RGB")
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    new_size = (int(img.width * scale + 0.5), int(img.height * scale + 0.5))
    resized = img.resize(new_size, Image.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def ai_background_path(rank: int, plan: CoverPlan) -> Path:
    return AI_BG_DIR / f"{rank:02d}-{slugify(plan.title)}-bg.png"


def active_background(plan: CoverPlan, caption: str, rank: int) -> Image.Image:
    bg_path = ai_background_path(rank, plan)
    if bg_path.exists():
        img = cover_crop(Image.open(bg_path), (1080, 1080)).convert("RGBA")
        # The AI image is the scene; this wash keeps the fixed title area readable.
        wash = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wash, "RGBA")
        for x in range(1080):
            t = max(0, 1 - x / 760)
            wd.line([(x, 0), (x, 1080)], fill=(0, 0, 0, int(178 * t)))
        return Image.alpha_composite(img, wash).convert("RGB")
    return draw_background(plan, caption)


def ai_background_prompt(plan: CoverPlan, caption: str, rank: int) -> str:
    accent = PALETTE[plan.category]["accent"]
    clean = clean_text(caption)
    style_map = {
        "terminal": "late-night AI workspace, laptop code glow, realistic screen light, premium editorial photography",
        "market": "dark financial terminal room, market charts as abstract light lines, premium cinematic business photography",
        "cinema": "dark film production studio, monitor glow, AIGC video creation atmosphere, cinematic editorial photography",
        "desk": "quiet late-night desk, notebook, whiteboard, strategic thinking, calm pressure, premium editorial photography",
        "product": "AI product strategy room, laptop, whiteboard, growth flywheel mood, realistic business editorial photography",
        "road": "night city road, airport or client-visit field note atmosphere, documentary editorial photography",
    }
    safe_area = (
        "Keep the left half dark, simple, and uncluttered for large Chinese overlay typography. "
        "Put the main visual object or brightest detail on the right third or lower right."
    )
    return (
        f"Create a 1:1 square background image for a Douyin cover, no typography. "
        f"Use the content of this specific post as the scene direction: {clean[:620]}. "
        f"Final cover title will be: {plan.title.replace(chr(10), ' / ')}. "
        f"Interpretation theme: {plan.theme}. "
        f"Visual style: {style_map.get(plan.style, style_map['terminal'])}. "
        f"Brand mood: Mr.K, Chinese AI/business solo creator, calm judgment, cross-border AI, field notes. "
        f"Accent color hint: {accent}, use it only as subtle glow or environmental light. "
        f"{safe_area} "
        f"Use realistic depth, mature technology/business mood, dark cinematic base, tactile objects relevant to the post. "
        f"Photorealistic or cinematic editorial only; no abstract blobs, decorative circles, vector shapes, flat illustration, or generic AI poster look. "
        f"Do not include readable text, letters, logos, watermarks, UI labels, QR codes, captions, posters, or faces looking at camera. "
        f"The image will be used only as a background under fixed overlay typography."
    )


def prepare_ai_background_batch(works: list[dict]) -> None:
    AI_BG_DIR.mkdir(parents=True, exist_ok=True)
    AI_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = []
    prompt_index = []
    for rank, work in enumerate(works, 1):
        plan = plan_for(work["caption"], rank)
        prompt_path = AI_PROMPT_DIR / f"{rank:02d}-{slugify(plan.title)}.md"
        image_path = ai_background_path(rank, plan)
        prompt = ai_background_prompt(plan, work["caption"], rank)
        prompt_path.write_text(prompt, "utf-8")
        prompt_index.append(
            {
                "rank": rank,
                "title": plan.title,
                "date": work["date"],
                "play": work["play"],
                "promptFile": str(prompt_path),
                "image": str(image_path),
            }
        )
        tasks.append(
            {
                "id": f"bg-{rank:02d}",
                "promptFiles": [str(prompt_path.relative_to(OUT_DIR))],
                "image": str(image_path.relative_to(OUT_DIR)),
                "provider": "codex-cli",
                "ar": "1:1",
                "quality": "normal",
            }
        )
    (OUT_DIR / "ai-background-batch.json").write_text(json.dumps({"jobs": 1, "tasks": tasks}, ensure_ascii=False, indent=2), "utf-8")
    (OUT_DIR / "ai-background-prompts.json").write_text(json.dumps(prompt_index, ensure_ascii=False, indent=2), "utf-8")
    print(OUT_DIR / "ai-background-batch.json")
    print(OUT_DIR / "ai-background-prompts.json")


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt: ImageFont.ImageFont, fill, max_width: int | None = None) -> None:
    x, y = xy
    draw.text((x, y), text, font=fnt, fill=fill)


def draw_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fnt: ImageFont.ImageFont, fill) -> None:
    x1, y1, x2, y2 = box
    tw, th = text_size(draw, text, fnt)
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 2), text, font=fnt, fill=fill)


def wrap_lines(text: str, max_chars: int) -> list[str]:
    manual = [x.strip() for x in text.split("\n") if x.strip()]
    if len(manual) > 1:
        return manual[:3]
    src = manual[0] if manual else ""
    out = []
    while len(src) > max_chars:
        out.append(src[:max_chars])
        src = src[max_chars:]
    if src:
        out.append(src)
    return out[:3] or [text]


def draw_avatar(img: Image.Image, draw: ImageDraw.ImageDraw, accent: str) -> None:
    if not AVATAR.exists():
        return
    avatar = Image.open(AVATAR).convert("RGB").resize((108, 108), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (108, 108), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 107, 107], fill=255)
    avatar.putalpha(mask)
    x, y = 852, 76
    draw.ellipse([x - 11, y - 11, x + 119, y + 119], fill=(5, 7, 10, 230), outline=rgba(accent, 255), width=5)
    draw.ellipse([x - 3, y - 3, x + 111, y + 111], outline=(255, 255, 255, 230), width=6)
    img.paste(avatar, (x, y), avatar)


def draw_cut_k(draw: ImageDraw.ImageDraw, accent: str) -> None:
    x, y, size = 690, 710, 365
    s = size / 1000
    strokes = [
        ((240, 100), (240, 900)),
        ((300, 520), (785, 105)),
        ((305, 520), (820, 900)),
    ]
    for p1, p2 in strokes:
        draw.line(
            [(x + p1[0] * s, y + p1[1] * s), (x + p2[0] * s, y + p2[1] * s)],
            fill=rgba(accent, 68),
            width=int(128 * s),
        )
        draw.line(
            [(x + (p1[0] - 20) * s, y + (p1[1] + 8) * s), (x + (p2[0] - 20) * s, y + (p2[1] + 8) * s)],
            fill=(80, 214, 255, 48),
            width=int(92 * s),
        )


def fit_title_font(lines: list[str]) -> ImageFont.ImageFont:
    max_len = max(len(x) for x in lines)
    size = 96
    if max_len <= 4:
        size = 116
    elif max_len <= 6:
        size = 104
    elif max_len <= 8:
        size = 90
    return font(size, 800)


def render_cover(plan: CoverPlan, caption: str, play: str, rank: int) -> Image.Image:
    img = active_background(plan, caption, rank).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    accent = PALETTE[plan.category]["accent"]

    draw_cut_k(draw, accent)
    draw_text(draw, (80, 72), "MR.K 在路上", font(38, 800), (248, 248, 242, 246))
    draw_text(draw, (80, 126), "KevPH2026 / Deep thoughts on AI", font(25, 400), (248, 248, 242, 186))
    draw_avatar(img, draw, accent)

    draw.rounded_rectangle([80, 218, 252, 270], radius=26, fill=rgba(accent, 244))
    draw_center(draw, (80, 218, 252, 270), PALETTE[plan.category]["label"], font(26, 700), (8, 10, 13, 255))

    lines = wrap_lines(plan.title, 7)
    title_font = fit_title_font(lines)
    y = 330
    for line in lines:
        draw_text(draw, (80, y), line, title_font, (252, 252, 246, 255))
        y += int(title_font.size * 0.98)

    en_font = font(29, 700)
    draw_text(draw, (82, y + 20), plan.en_title.upper(), en_font, (248, 248, 242, 205))
    draw.rectangle([82, y + 76, 395, y + 86], fill=rgba(accent, 230))
    draw_text(draw, (82, y + 126), plan.summary, font(31, 400), (248, 248, 242, 226))

    draw.rounded_rectangle([80, 932, 360, 972], radius=20, fill=(5, 7, 10, 118), outline=rgba(accent, 190), width=1)
    tags = {
        "ai": "# AI下半场  # AI商业",
        "strong": "# 强者恒强  # 判断力",
        "road": "# 在路上  # 一线观察",
    }[plan.category]
    draw_center(draw, (80, 932, 360, 972), tags, font(22, 400), (248, 248, 242, 238))
    draw_text(draw, (82, 1000), f"播放 {play}", font(22, 400), (248, 248, 242, 202))
    draw_text(draw, (842, 995), plan.code, font(30, 700), rgba(accent, 244))
    draw_text(draw, (80, 1028), f"HIGH PLAY / {rank:02d}", font(15, 700), (248, 248, 242, 128))
    return img.convert("RGB")


def thumb_data_url(path: Path, max_w: int = 420, quality: int = 78) -> str:
    img = Image.open(path).convert("RGB")
    ratio = min(1, max_w / img.width)
    if ratio < 1:
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    import io

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    works = json.loads(WORKS_JSON.read_text("utf-8"))
    if "--prepare-ai-backgrounds" in sys.argv:
        prepare_ai_background_batch(works)
        return
    plans = []
    assets = []

    for rank, work in enumerate(works, 1):
        plan = plan_for(work["caption"], rank)
        title_slug = slugify(plan.title)
        play_slug = str(work["play"]).replace(".", "p").replace("万", "w").replace("-", "0")
        filename = f"{rank:02d}-{play_slug}-{title_slug}-1080x1080.png"
        out = OUT_DIR / filename
        cover = render_cover(plan, work["caption"], work["play"], rank)
        cover.save(out, "PNG", optimize=True)
        plans.append(
            {
                "rank": rank,
                "file": str(out),
                "caption": work["caption"],
                "date": work["date"],
                "play": work["play"],
                "playNum": work["playNum"],
                "category": plan.category,
                "title": plan.title,
                "enTitle": plan.en_title,
                "summary": plan.summary,
                "code": plan.code,
                "theme": plan.theme,
            }
        )
        assets.append(
            {
                "id": f"high-play-{rank:02d}",
                "title": plan.title.replace("\n", " "),
                "template": "work-square",
                "category": plan.category,
                "code": plan.code,
                "summary": plan.summary,
                "thumbnail": thumb_data_url(out, 260, 72),
                "render_url": f"generated-covers/high-play/{filename}",
                "editable": {
                    "template": "work-square",
                    "category": plan.category,
                    "title": plan.title,
                    "enTitle": plan.en_title,
                    "summary": plan.summary,
                    "code": plan.code,
                    "imageTheme": plan.theme,
                    "imageStyle": plan.style,
                },
                "source": {
                    "date": work["date"],
                    "play": work["play"],
                    "caption": work["caption"],
                },
                "created_at": 1780329600000 + rank,
            }
        )

    # Contact sheets.
    thumbs = []
    for item in plans:
        im = Image.open(item["file"]).convert("RGB").resize((216, 216), Image.LANCZOS)
        label = Image.new("RGB", (216, 48), "#f3f5f7")
        ld = ImageDraw.Draw(label)
        ld.text((8, 6), f"{item['rank']:02d}  {item['play']}", font=font(16, 700), fill="#11151a")
        ld.text((8, 27), item["title"].replace("\n", " ")[:18], font=font(13, 400), fill="#4b5563")
        cell = Image.new("RGB", (216, 264), "#f3f5f7")
        cell.paste(im, (0, 0))
        cell.paste(label, (0, 216))
        thumbs.append(cell)

    cols = 5
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 216, rows * 264), "#e8ebef")
    for idx, cell in enumerate(thumbs):
        sheet.paste(cell, ((idx % cols) * 216, (idx // cols) * 264))
    sheet.save(OUT_DIR / "all-high-play-contact-sheet.png", "PNG", optimize=True)

    (OUT_DIR / "high-play-cover-plans.json").write_text(json.dumps(plans, ensure_ascii=False, indent=2), "utf-8")
    (OUT_DIR / "mrk-materials.json").write_text(json.dumps({"assets": assets}, ensure_ascii=False, indent=2), "utf-8")

    print(f"generated={len(plans)}")
    print(OUT_DIR / "all-high-play-contact-sheet.png")
    print(OUT_DIR / "high-play-cover-plans.json")
    print(OUT_DIR / "mrk-materials.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from make_high_play_covers import (
    AVATAR,
    PALETTE,
    CoverPlan,
    draw_avatar,
    draw_center,
    draw_cut_k,
    font,
    rgba,
    rgb,
    slugify,
    text_size,
    thumb_data_url,
    wrap_lines,
)


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "generated-covers" / "low-play"
WORKS_JSON = OUT_DIR / "low-works-non-private.json"
AI_PROMPT_DIR = OUT_DIR / "ai-background-prompts"


TAG_RE = re.compile(r"#\S+")


@dataclass
class LowPlan:
    category: str
    title: str
    en_title: str
    summary: str
    code: str
    theme: str
    style: str


def compact_text(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text or "")
    text = re.sub(r"@\S+", " ", text)
    text = TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" 。！？,.，、")


def strip_private_prefix(text: str) -> str:
    return re.sub(r"^私密\s*", "", text or "").strip()


def first_sentence(text: str) -> str:
    text = compact_text(strip_private_prefix(text))
    if not text or text == "无作品描述":
        return "现场笔记"
    pieces = re.split(r"[。！？!?；;]\s*", text)
    for piece in pieces:
        piece = piece.strip(" ，、")
        if len(piece) >= 4:
            return piece[:28]
    return text[:28]


def code_for(category: str, idx: int) -> str:
    prefix = {"ai": "AI", "strong": "K", "road": "ROAD"}.get(category, "K")
    return f"{prefix}-{idx:02d}"


def category_for(caption: str) -> tuple[str, str]:
    lower = caption.lower()
    if any(key in lower for key in ["ai", "agent", "openai", "claude", "deepseek", "gemini", "manus", "notion", "llm", "vibecoding", "aigc", "agi", "token", "模型", "机器人", "智能体", "人工智能"]):
        return "ai", "terminal"
    if any(key in caption for key in ["出差", "路", "旅拍", "东京", "杭州", "上海", "保定", "北京", "远方", "风景", "城市", "机场"]):
        return "road", "road"
    return "strong", "desk"


def line_title(text: str, max_chars: int = 8) -> str:
    text = compact_text(text)
    text = text.replace("，", " ").replace(",", " ").replace("。", " ")
    words = [w for w in text.split() if w]
    if len(words) >= 2 and all(len(w) <= max_chars + 2 for w in words[:3]):
        return "\n".join(words[:3])
    if len(text) <= max_chars:
        return text
    if len(text) <= max_chars * 2:
        return text[:max_chars] + "\n" + text[max_chars:]
    return text[:max_chars] + "\n" + text[max_chars : max_chars * 2] + "\n" + text[max_chars * 2 : max_chars * 3]


def summary_from(caption: str, title: str) -> str:
    clean = compact_text(caption)
    if not clean or clean == "无作品描述":
        return "把现场、判断和行动，留成一条清醒的笔记。"
    clean = clean.replace(title.replace("\n", ""), "").strip(" ，。")
    if len(clean) < 10:
        clean = compact_text(caption)
    return clean[:34] + ("。" if not clean[:34].endswith(("。", "！", "？")) else "")


def rule_plan(caption: str, idx: int) -> LowPlan | None:
    c = compact_text(caption)
    rules = [
        ("小马过河", "strong", "烦恼是你\n人生的内容\n不是人生的问题", "LIFE IS CONTENT", "把问题放回生命里，路才会继续往前走。", "人生烦恼、小马过河、日落、低调自省", "desk"),
        ("做你想成为的自己", "strong", "做你想成为的\n自己", "BECOME YOURSELF", "别活在别人的注视里，把路走回自己手上。", "自我成长、靠自己、创业心力", "desk"),
        ("欲望一点都不可怕", "strong", "欲望不可怕\n它是动力", "DESIRE IS ENERGY", "真正危险的不是欲望，而是不敢承认自己想要。", "欲望、行动力、自由风速", "road"),
        ("token消耗", "ai", "截图看看\n你的Token消耗", "TOKEN SPEND CHECK", "新的生产力，也会留下新的消耗账本。", "token、AI挑战、词元消耗", "terminal"),
        ("5天换了4个城市", "road", "5天\n4个城市", "FOUR CITIES", "在路上，才能把判断从屏幕带回现实。", "出差、城市切换、视频日记", "road"),
        ("眼底有光", "road", "眼底有光\n心中晴朗", "LIGHT IN YOUR EYES", "把世界看进去，也把自己照亮一点。", "东京旅拍、夜色、情绪稳定", "road"),
        ("山高万仞", "strong", "山高万仞\n只登一步", "ONE STEP UP", "大问题不是一次解决的，是一步一步推进的。", "问题解决、团队、登山隐喻", "desk"),
        ("世界工厂走向世界智造", "ai", "从世界工厂\n到世界智造", "WORLD INTELLIGENCE", "中国制造正在被机器人和AI重新定义。", "中国机器人、世界智造、工厂未来", "product"),
        ("悖论中前行", "strong", "在悖论中\n前行", "MOVE THROUGH PARADOX", "能容纳矛盾，才有真正的判断。", "思辨、独立思考、悖论", "desk"),
        ("无作品描述", "road", "在路上\n也算答案", "FIELD NOTE", "没有文案，也可以是一条现场笔记。", "无作品描述、现场、路上", "road"),
        ("具身智能", "ai", "具身智能\n起步全球化", "EMBODIED AI", "硬件被AI加速，产品一上市就面对全球。", "具身智能、DeepSeek、全球化客户", "product"),
        ("正反馈", "strong", "远离没有\n正反馈的环境", "FIND POSITIVE SIGNAL", "人要待在能给自己回声的地方。", "正反馈、热爱、环境选择", "desk"),
        ("MiniMax", "ai", "MiniMax的\nDay 1", "AGENT DAY ONE", "伟大的智能体，也开始于一个小想法。", "MiniMax、Agent、Day1", "terminal"),
        ("OpenAI创始人加入Anthropic", "ai", "打不过\n就加入", "JOIN THE WINNER", "人才流向，是技术周期最诚实的信号。", "OpenAI、Anthropic、人才流动", "terminal"),
        ("HARNESS", "ai", "你觉得呢", "LLM FIELD NOTE", "一个问题，有时比答案更值钱。", "LLM、Harness、大模型", "terminal"),
        ("AI真正加速的是系统", "ai", "AI加速的\n是系统", "SYSTEMS ACCELERATE", "真正被AI放大的，是方向、记忆和工作流。", "操作系统、AI工作流、速度", "terminal"),
        ("中登", "strong", "原来我只是\n中登", "MID-GEN NOTE", "代际语言有点刺耳，但也很真实。", "00后、中登、咖啡、代际观察", "desk"),
        ("Agent冲榜全球Top2", "ai", "Agent冲榜\n全球Top 2", "AGENT TOP TWO", "小产品上榜，也是系统能力的回声。", "Botlearn、Agent榜单、打卡成绩", "terminal"),
        ("无穷的开始", "strong", "为什么要\n相信未来", "BELIEVE THE FUTURE", "知识的价值不是堆积，而是解释世界。", "无穷的开始、乐观、知识解释", "desk"),
        ("toB或许是AI时代下最好的生意", "ai", "ToB或许是\nAI最好的生意", "B2B AI OPPORTUNITY", "问题越多，机会越多。", "ToB、Agent交付、确定性", "product"),
        ("AI峰会", "ai", "有一起的吗", "WHO IS IN", "好的同行者，本身就是一种机会。", "AI峰会、Agent、同行者", "product"),
        ("没有任何护城河", "ai", "应用产品\n没有护城河", "NO APP MOAT", "建在模型之上的产品，必须重新理解边界。", "AI应用、护城河、模型厂商", "market"),
        ("黑客松", "ai", "认识有意思的\n一群人", "MEET BUILDERS", "优质连接，是AI时代的隐性资产。", "黑客松、AWS、投资、AI社群", "product"),
        ("一切皆媒体", "strong", "一切皆媒体", "EVERYTHING IS MEDIA", "注意力时代，表达本身就是生产资料。", "追觅、俞浩、媒体化", "product"),
        ("All in AI", "ai", "2026\nAll in AI", "ALL IN AI", "用任何方式靠近AI，就是靠近新生产力。", "All in AI、2026、AI公司", "terminal"),
        ("创业是事上练", "strong", "创业是\n事上练", "TRAIN IN REALITY", "真正的成长，只发生在具体事情里。", "创业、事上练、现实反馈", "desk"),
        ("一句话讲清楚", "strong", "一句话\n讲清楚", "MAKE IT CLEAR", "表达能不能变短，决定判断能不能变准。", "表达、沟通、清晰", "desk"),
        ("Avatar改变的", "ai", "Avatar改变\n内容生成", "AVATAR CHANGES CONTENT", "新的内容入口，往往先改变生产流程。", "Avatar、内容生成、AI视频", "cinema"),
        ("能量炸裂", "strong", "保持能量\n炸裂", "KEEP THE ENERGY", "状态不是玄学，是持续行动的基础设施。", "能量、状态、个人系统", "desk"),
        ("挑战vibecoding做50个产品", "ai", "50个产品\n挑战继续", "50 PRODUCT SPRINT", "用产品练手，比用观点证明自己更快。", "VibeCoding、产品挑战、Notion", "terminal"),
        ("实事求是", "strong", "实事求是\n解决一切问题", "SEEK TRUTH", "大道至简，先回到事实。", "教员、实事求是、超级个体", "desk"),
        ("Human 3.0", "ai", "Human 3.0\n重新认识自己", "HUMAN 3.0", "最正经的AI用途，是照见自己的漏洞。", "Dan Koe、Human 3.0、自我认知", "terminal"),
        ("无所不能", "strong", "电子外挂\n不是内核", "CORE BEFORE BOOST", "AI让你变强之前，先暴露你的底层。", "无知、智慧、AI外挂", "desk"),
        ("5场无声屠杀", "ai", "普通人的\n5场无声屠杀", "SILENT SHIFTS", "当AI重排世界，创造意义会变得更稀缺。", "AI屠杀、黑镜、意义创造", "terminal"),
        ("公司破产", "strong", "距离破产\n只剩几小时", "LAST HOURS", "传奇不是没有崩盘，而是能从崩盘里活过来。", "马斯克、火箭、创业危机", "market"),
        ("文科生的未来", "ai", "文科生的\n未来", "TASTE BECOMES RARE", "AI越强，审美和品味越稀缺。", "文科生、审美、品味、AI", "desk"),
        ("创业不是走得快", "strong", "创业不是走得快\n而是拐得对", "TURN RIGHT", "速度不稀缺，拐点判断才稀缺。", "创业、Manus、商业思维", "road"),
        ("第四次工业革命", "ai", "第四次\n工业革命", "FOURTH REVOLUTION", "技术越强，越要谨慎选择自己相信什么。", "赫拉利、技术地狱、工业革命", "terminal"),
        ("革命就意味着有人会牺牲", "ai", "革命会有人\n牺牲", "REVOLUTION HAS COST", "越是生产力跃迁，越考验战略取舍。", "AI革命、战略、生产力", "market"),
        ("Manus早期用户", "ai", "Manus早期用户\n的礼物", "EARLY AGENT SIGNAL", "有些产品会先出现在少数人的工作流里。", "Manus、Agent、早期用户", "product"),
        ("三分钟热度", "strong", "三分钟热度\n是顶级天赋", "RANGE IS TALENT", "兴趣跳跃不是缺陷，可能是探索系统。", "三分钟热度、天赋、翻译神文", "desk"),
    ]
    for key, category, title, en, summary, theme, style in rules:
        if key in c:
            return LowPlan(category, title, en, summary, code_for(category, idx), theme, style)
    return None


def plan_for_low(work: dict, idx: int) -> LowPlan:
    caption = work.get("caption", "")
    ruled = rule_plan(caption, idx)
    if ruled:
        return ruled
    category, style = category_for(caption)
    seed = first_sentence(caption)
    title = line_title(seed)
    en = {
        "ai": "AI FIELD NOTE",
        "road": "ON THE ROAD",
        "strong": "STRONG FIELD NOTE",
    }[category]
    return LowPlan(
        category=category,
        title=title,
        en_title=en,
        summary=summary_from(caption, title),
        code=code_for(category, idx),
        theme=compact_text(caption)[:80] or "现场笔记",
        style=style,
    )


def seed_for(text: str) -> int:
    return int(__import__("hashlib").sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def gradient_base(accent: str, style: str) -> Image.Image:
    w = h = 1080
    acc = rgb(accent)
    top = (4, 7, 9)
    bottom = (14 + acc[0] // 28, 19 + acc[1] // 28, 23 + acc[2] // 28)
    if style == "road":
        bottom = (22, 20, 18)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)
    return img


def add_film_grain(img: Image.Image, seed: int) -> Image.Image:
    rnd = random.Random(seed)
    w, h = img.size
    noise = Image.new("L", (w, h), 0)
    data = bytearray(w * h)
    for i in range(len(data)):
        data[i] = max(0, min(255, 128 + rnd.randint(-10, 10)))
    noise.putdata(data)
    overlay = Image.merge("RGBA", (noise, noise, noise, Image.new("L", (w, h), 18)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def draw_low_background(plan: LowPlan, caption: str) -> Image.Image:
    w = h = 1080
    accent = PALETTE[plan.category]["accent"]
    acc = rgb(accent)
    seed = seed_for(plan.title + caption + plan.style)
    rnd = random.Random(seed)
    img = gradient_base(accent, plan.style)
    d = ImageDraw.Draw(img, "RGBA")

    # Realistic right-side set: window frames and table plane, not decorative blobs.
    d.polygon([(560, 1080), (1080, 930), (1080, 1080)], fill=(255, 255, 255, 12))
    d.polygon([(500, 720), (1080, 610), (1080, 900), (540, 1030)], fill=(255, 255, 255, 18))
    for x in range(610, 1080, 94):
        d.line([(x, 80), (x + rnd.randint(-30, 20), 470)], fill=(255, 255, 255, 18), width=2)
    for y in range(120, 520, 92):
        d.line([(570, y), (1080, y - rnd.randint(10, 48))], fill=(*acc, 28), width=2)

    if plan.style in {"terminal", "market"}:
        mx, my = 575, 330
        d.rounded_rectangle([mx, my, mx + 430, my + 285], radius=18, fill=(7, 13, 17, 230), outline=(*acc, 105), width=2)
        d.rectangle([mx + 24, my + 30, mx + 406, my + 250], fill=(4, 9, 12, 235))
        if plan.style == "market":
            base = my + 205
            pts = []
            for i in range(9):
                pts.append((mx + 45 + i * 40, base - rnd.randint(5, 120)))
            d.line(pts, fill=(*acc, 175), width=5)
            for i in range(4):
                x = mx + 50 + i * 82
                d.rectangle([x, my + 60 + rnd.randint(0, 35), x + 44, my + 235], fill=(*acc, 34))
        else:
            for i in range(15):
                y = my + 54 + i * 13
                x = mx + 46 + rnd.randint(0, 26)
                d.line([x, y, x + rnd.randint(100, 298), y], fill=(*acc, rnd.randint(45, 105)), width=2)
        d.polygon([(mx - 80, my + 310), (mx + 500, my + 310), (mx + 575, my + 388), (mx - 170, my + 388)], fill=(20, 23, 25, 220))
        for i in range(10):
            x = mx - 22 + i * 48
            d.line([x, my + 338, x + 34, my + 338], fill=(255, 255, 255, 25), width=2)
    elif plan.style == "cinema":
        d.rounded_rectangle([585, 330, 1018, 610], radius=24, fill=(8, 10, 13, 230), outline=(*acc, 85), width=3)
        d.rectangle([620, 370, 982, 570], fill=(16, 21, 25, 225))
        d.polygon([(645, 530), (740, 405), (815, 518), (900, 440), (962, 555)], fill=(*acc, 42))
        d.rounded_rectangle([705, 650, 990, 760], radius=18, fill=(18, 18, 19, 190), outline=(255, 255, 255, 24), width=2)
        d.rectangle([790, 610, 870, 650], fill=(18, 20, 22, 220))
    elif plan.style == "road":
        d.polygon([(525, 1080), (720, 520), (870, 520), (1080, 1080)], fill=(24, 25, 26, 230))
        d.line([798, 1080, 798, 535], fill=(*acc, 130), width=8)
        for y in [590, 655, 735, 835, 960]:
            d.line([(620, y), (985, y + rnd.randint(-24, 24))], fill=(255, 255, 255, 24), width=2)
        for i in range(9):
            x = 640 + i * 48
            y = rnd.randint(160, 330)
            d.rectangle([x, y, x + 26, y + 18], fill=(255, 210, 138, 45))
    elif plan.style == "product":
        d.rounded_rectangle([590, 280, 1012, 555], radius=18, fill=(235, 246, 240, 24), outline=(*acc, 80), width=2)
        for i in range(7):
            x = 630 + i * 50
            y = 430 + rnd.randint(-60, 50)
            d.rounded_rectangle([x, y, x + 58, y + 36], radius=6, fill=(*acc, 42), outline=(*acc, 80), width=1)
            if i:
                d.line([x - 22, y + 18, x, y + 18], fill=(*acc, 75), width=2)
        d.rounded_rectangle([615, 665, 980, 850], radius=18, fill=(230, 224, 208, 34), outline=(255, 255, 255, 32), width=2)
        for i in range(8):
            y = 700 + i * 18
            d.line([650, y, 930, y + rnd.randint(-3, 3)], fill=(255, 255, 255, 34), width=2)
    else:
        d.rounded_rectangle([610, 300, 1005, 520], radius=16, fill=(240, 246, 248, 20), outline=(*acc, 70), width=2)
        for i in range(6):
            x = 650 + i * 54
            y = 420 + rnd.randint(-44, 36)
            d.rounded_rectangle([x - 10, y - 10, x + 10, y + 10], radius=5, fill=(*acc, 100))
            if i:
                px = 650 + (i - 1) * 54
                py = 420 + rnd.randint(-44, 36)
                d.line([px, py, x, y], fill=(*acc, 75), width=3)
        d.rounded_rectangle([590, 630, 1020, 870], radius=22, fill=(230, 224, 208, 35), outline=(255, 255, 255, 34), width=2)
        for i in range(9):
            y = 665 + i * 22
            d.line([630, y, 960, y + rnd.randint(-5, 5)], fill=(255, 255, 255, 36), width=2)

    # Left readability wash.
    wash = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wash, "RGBA")
    for x in range(w):
        t = max(0, 1 - x / 780)
        wd.line([(x, 0), (x, h)], fill=(0, 0, 0, int(205 * t)))
    img = Image.alpha_composite(img, wash)

    # Subtle vignette.
    edge = Image.new("L", (w, h), 0)
    ed = ImageDraw.Draw(edge)
    ed.rectangle([50, 50, w - 50, h - 50], fill=255)
    edge = Image.eval(edge.filter(ImageFilter.GaussianBlur(85)), lambda p: 255 - p)
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 130))
    vignette.putalpha(edge.point(lambda p: int(p * 0.48)))
    img = Image.alpha_composite(img, vignette)
    return add_film_grain(img, seed).convert("RGB")


def active_background(plan: LowPlan, caption: str, rank: int) -> Image.Image:
    return draw_low_background(plan, caption)


def fit_title_font(lines: list[str]) -> ImageFont.ImageFont:
    max_len = max(len(x) for x in lines)
    if max_len <= 4:
        size = 118
    elif max_len <= 6:
        size = 104
    elif max_len <= 8:
        size = 86
    else:
        size = 78
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    while size > 58:
        candidate = font(size, 800)
        if max(text_size(probe, line, candidate)[0] for line in lines) <= 560:
            return candidate
        size -= 4
    return font(size, 800)


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt: ImageFont.ImageFont, fill) -> None:
    draw.text(xy, text, font=fnt, fill=fill)


def render_cover(plan: LowPlan, caption: str, rank: int) -> Image.Image:
    img = active_background(plan, caption, rank).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    accent = PALETTE[plan.category]["accent"]

    draw_cut_k(draw, accent)
    draw_text(draw, (80, 72), "MR.K 在路上", font(38, 800), (248, 248, 242, 246))
    draw_text(draw, (80, 126), "KevPH2026 / Deep thoughts on AI", font(25, 400), (248, 248, 242, 186))
    draw_avatar(img, draw, accent)

    draw.rounded_rectangle([80, 218, 252, 270], radius=26, fill=rgba(accent, 244))
    draw_center(draw, (80, 218, 252, 270), PALETTE[plan.category]["label"], font(26, 700), (8, 10, 13, 255))

    lines = wrap_lines(plan.title, 8)
    title_font = fit_title_font(lines)
    y = 330
    for line in lines:
        draw_text(draw, (80, y), line, title_font, (252, 252, 246, 255))
        y += int(title_font.size * 0.98)

    draw_text(draw, (82, y + 20), plan.en_title.upper(), font(29, 700), (248, 248, 242, 205))
    draw.rectangle([82, y + 76, 395, y + 86], fill=rgba(accent, 230))
    draw_text(draw, (82, y + 126), plan.summary, font(31, 400), (248, 248, 242, 226))

    draw.rounded_rectangle([80, 942, 360, 982], radius=20, fill=(5, 7, 10, 118), outline=rgba(accent, 190), width=1)
    tags = {
        "ai": "# AI下半场  # AI商业",
        "strong": "# 强者恒强  # 判断力",
        "road": "# 在路上  # 一线观察",
    }[plan.category]
    draw_center(draw, (80, 942, 360, 982), tags, font(22, 400), (248, 248, 242, 238))
    draw_text(draw, (842, 995), plan.code, font(30, 700), rgba(accent, 244))
    draw_text(draw, (80, 1028), f"WORK NOTE / {rank:03d}", font(15, 700), (248, 248, 242, 128))
    return img.convert("RGB")


def cover_filename(rank: int, plan: LowPlan, work: dict) -> str:
    date_digits = re.sub(r"\D", "", work.get("date", ""))[:12] or f"{rank:03d}"
    slug = slugify(plan.title)
    if slug == "cover":
        slug = f"work-{rank:03d}"
    return f"{rank:03d}-{date_digits}-{slug}-1080x1080.png"


def prompt_for(plan: LowPlan, work: dict) -> str:
    accent = PALETTE[plan.category]["accent"]
    clean = compact_text(work.get("caption", ""))
    style_map = {
        "terminal": "late-night AI workspace, laptop glow, real screens, mature tech-business editorial photography",
        "market": "dark financial/business room, market pressure, abstract chart light, cinematic editorial photography",
        "cinema": "dark content production studio, monitor glow, AI video creation mood, cinematic editorial photography",
        "desk": "quiet late-night desk, notebook, whiteboard, calm pressure, strategic thinking editorial photography",
        "product": "AI product strategy room, laptop, whiteboard, prototype and growth flywheel atmosphere",
        "road": "night city road or travel field-note scene, documentary business creator mood",
    }
    return (
        "Create a 1:1 square background for a Douyin cover, no typography. "
        f"Post content: {clean[:620]}. "
        f"Cover title: {plan.title.replace(chr(10), ' / ')}. "
        f"Theme: {plan.theme}. "
        f"Style: {style_map.get(plan.style, style_map['desk'])}. "
        f"Accent color: {accent}, subtle environmental glow only. "
        "Keep the left half dark, clean, and uncluttered for large Chinese typography. "
        "Place the brightest object on the right third or lower right. "
        "Photorealistic/cinematic editorial only. No readable text, logo, watermark, UI labels, QR code, or face looking at camera."
    )


def save_contact_sheet(plans: list[dict]) -> None:
    thumbs = []
    for item in plans:
        im = Image.open(item["file"]).convert("RGB").resize((216, 216), Image.LANCZOS)
        label = Image.new("RGB", (216, 54), "#f3f5f7")
        ld = ImageDraw.Draw(label)
        ld.text((8, 6), f"{item['rank']:03d}  {item['date'][5:16]}", font=font(15, 700), fill="#11151a")
        ld.text((8, 29), item["title"].replace("\n", " ")[:18], font=font(13, 400), fill="#4b5563")
        cell = Image.new("RGB", (216, 270), "#f3f5f7")
        cell.paste(im, (0, 0))
        cell.paste(label, (0, 216))
        thumbs.append(cell)

    cols = 9
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 216, rows * 270), "#e8ebef")
    for idx, cell in enumerate(thumbs):
        sheet.paste(cell, ((idx % cols) * 216, (idx // cols) * 270))
    sheet.save(OUT_DIR / "all-low-play-contact-sheet.png", "PNG", optimize=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AI_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    works = json.loads(WORKS_JSON.read_text("utf-8"))
    works = [w for w in works if not w.get("isPrivate") and int(w.get("playNum") or 0) < 10000]

    plans: list[dict] = []
    assets: list[dict] = []
    prompt_index: list[dict] = []
    counters = {"ai": 0, "strong": 0, "road": 0}

    for rank, work in enumerate(works, 1):
        plan = plan_for_low(work, rank)
        counters[plan.category] += 1
        plan.code = code_for(plan.category, counters[plan.category])
        filename = cover_filename(rank, plan, work)
        out = OUT_DIR / filename
        cover = render_cover(plan, work.get("caption", ""), rank)
        cover.save(out, "PNG", optimize=True)

        prompt_file = AI_PROMPT_DIR / f"{rank:03d}-{filename.replace('-1080x1080.png', '')}.md"
        prompt_file.write_text(prompt_for(plan, work), "utf-8")
        item = {
            "rank": rank,
            "file": str(out),
            "caption": work.get("caption", ""),
            "date": work.get("date", ""),
            "play": work.get("play", ""),
            "playNum": work.get("playNum", 0),
            "media": work.get("media", ""),
            "category": plan.category,
            "title": plan.title,
            "enTitle": plan.en_title,
            "summary": plan.summary,
            "code": plan.code,
            "theme": plan.theme,
            "style": plan.style,
        }
        plans.append(item)
        prompt_index.append({**item, "promptFile": str(prompt_file)})
        assets.append(
            {
                "id": f"low-play-{rank:03d}",
                "title": plan.title.replace("\n", " "),
                "template": "work",
                "category": plan.category,
                "code": plan.code,
                "summary": plan.summary,
                "thumbnail": thumb_data_url(out, 260, 72),
                "render_data_url": thumb_data_url(out, 980, 84),
                "editable": {
                    "template": "work",
                    "category": plan.category,
                    "title": plan.title,
                    "enTitle": plan.en_title,
                    "summary": plan.summary,
                    "code": plan.code,
                    "imageTheme": plan.theme,
                    "imageStyle": plan.style,
                },
                "source": {
                    "date": work.get("date", ""),
                    "play": work.get("play", ""),
                    "caption": work.get("caption", ""),
                    "batch": "low-play-under-10000-no-private",
                },
                "created_at": 1780416000000 + rank,
            }
        )

    save_contact_sheet(plans)
    (OUT_DIR / "low-play-cover-plans.json").write_text(json.dumps(plans, ensure_ascii=False, indent=2), "utf-8")
    (OUT_DIR / "ai-background-prompts.json").write_text(json.dumps(prompt_index, ensure_ascii=False, indent=2), "utf-8")
    (OUT_DIR / "mrk-materials.json").write_text(json.dumps({"assets": assets}, ensure_ascii=False, indent=2), "utf-8")

    print(f"generated={len(plans)}")
    print(OUT_DIR / "all-low-play-contact-sheet.png")
    print(OUT_DIR / "low-play-cover-plans.json")
    print(OUT_DIR / "mrk-materials.json")


if __name__ == "__main__":
    main()

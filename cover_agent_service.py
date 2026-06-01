import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


ALLOWED_DOUYIN_HOSTS = (
    "douyin.com",
    "iesdouyin.com",
    "amemv.com",
    "snssdk.com",
)

CATEGORY_KEYS = {"ai", "strong", "road"}
TEMPLATE_KEYS = {"work", "collection", "profile"}
STYLE_KEYS = {"cinematic", "terminal", "field", "minimal"}
DENSITY_KEYS = {"low", "medium", "high"}


class ServiceError(Exception):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        super().__init__(payload.get("message", "service error"))


class PageMetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True
            return
        if tag.lower() != "meta":
            return
        values = {k.lower(): v for k, v in attrs if k and v}
        key = values.get("property") or values.get("name")
        content = values.get("content")
        if key and content:
            self.meta[key.lower()] = html.unescape(content).strip()

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    def data(self):
        title = " ".join("".join(self.title_parts).split())
        return {
            "title": title,
            "og_title": self.meta.get("og:title", ""),
            "description": self.meta.get("description", ""),
            "og_description": self.meta.get("og:description", ""),
            "cover_image_url": self.meta.get("og:image", "") or self.meta.get("twitter:image", ""),
        }


def trim(value, limit):
    text = str(value or "").strip()
    return text[:limit]


def safe_json_loads(text):
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
    raise ValueError("DeepSeek did not return valid JSON.")


def is_allowed_douyin_url(url):
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    return any(host == item or host.endswith("." + item) for item in ALLOWED_DOUYIN_HOSTS)


def fetch_douyin_metadata(url):
    url = str(url or "").strip()
    if not url:
        return {"status": "empty"}
    if not is_allowed_douyin_url(url):
        return {
            "status": "skipped",
            "url": url,
            "message": "Only Douyin share links are fetched by the server.",
        }

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read(1_000_000)
            charset = response.headers.get_content_charset() or "utf-8"
            final_url = response.geturl()
    except Exception as exc:
        return {"status": "failed", "url": url, "message": str(exc)}

    parser = PageMetaParser()
    try:
        parser.feed(body.decode(charset, errors="replace"))
    except Exception:
        parser.feed(body.decode("utf-8", errors="replace"))

    data = parser.data()
    data.update({"status": "ok", "url": url, "final_url": final_url})
    return data


def infer_category(text):
    source = str(text or "").lower()
    compact = re.sub(r"\s+", "", source)
    if "ai下半场" in compact or "模型" in source or "agent" in source or "saas" in source:
        return "ai"
    if "强者恒强" in compact:
        return "strong"
    if "在路上" in compact:
        return "road"
    if any(k in source for k in ["出差", "客户", "机场", "路上", "一线", "城市", "travel", "client"]):
        return "road"
    if any(k in source for k in ["强者", "判断", "认知", "筹码", "竞争", "增长", "strategy"]):
        return "strong"
    return "ai"


def fallback_title(text, current_title):
    source = str(text or "")
    compact = re.sub(r"\s+", "", source)
    if "估值" in compact and any(k in compact for k in ["回调", "下杀", "蒸发", "缩水"]):
        return "估值\n回调"
    if "saas" in source.lower() and "消失" in compact:
        return "SaaS\n正在消失"
    if "强者恒强" in compact:
        return "强者\n恒强"
    if "ai下半场" in compact:
        return "AI\n下半场"

    chinese = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", source))
    if chinese:
        short = chinese[:12]
        return short[:6] + ("\n" + short[6:] if len(short) > 6 else "")
    return trim(current_title or "这一轮\n要看懂", 18)


def fallback_plan(incoming, link_meta, reason="local_fallback"):
    current = incoming.get("current") or {}
    message = trim(incoming.get("message"), 240)
    source_text = " / ".join(
        [
            message,
            link_meta.get("og_title") or link_meta.get("title") or "",
            link_meta.get("og_description") or link_meta.get("description") or "",
        ]
    )
    category = infer_category(source_text)
    clean = re.sub(r"https?://\S+", "", source_text).strip(" /，。")
    title = trim(fallback_title(clean, current.get("title")), 18)

    category_defaults = {
        "ai": ("AI下半场", "AI SECOND HALF", "模型 / Agent / 商业重构", "AI-NEW"),
        "strong": ("强者恒强", "THE STRONG GET STRONGER", "判断力 / 筹码 / 个体系统", "K-NEW"),
        "road": ("在路上", "ON THE ROAD", "出差 / 客户 / 一线观察", "ROAD-NEW"),
    }[category]

    return {
        "reply": "我先按现有账号规则生成了一版封面方案；DeepSeek 未配置时会走本地判断。",
        "template": "work",
        "category": category,
        "fields": {
            "categoryTitle": category_defaults[0],
            "categoryEn": category_defaults[1],
            "categorySub": category_defaults[2],
            "title": title,
            "enTitle": trim(current.get("enTitle") or "Field Note", 36),
            "summary": trim(current.get("summary") or clean or "把这一轮变化讲清楚。", 34),
            "code": category_defaults[3],
        },
        "image": {
            "theme": trim(clean or current.get("imageTheme") or "深夜城市，AI商业判断，代码屏幕", 180),
            "style": "field" if category == "road" else "cinematic",
            "density": "medium",
            "promptHints": trim(clean, 220),
        },
        "reason": reason,
    }


SYSTEM_PROMPT = """
你是 Mr.K 在路上的抖音封面导演。你的任务是把自然语言、抖音作品链接信息、当前封面字段，整理成可以直接套用的封面方案。

账号固定规则：
- 账号：MR.K 在路上；ID：KevPH2026。
- 只使用三类栏目：ai=AI下半场，strong=强者恒强，road=在路上。
- 单条作品封面要服务点击：中文标题必须短、狠、好读，建议 2-8 个汉字一行，用 \\n 控制换行，最多 3 行。
- 摘要是点击理由，不要流水账，控制在 12-28 个中文字符。
- 图片只做背景，不要把标题文字写进生成图里；标题由前端固定版式叠加。
- 如果用户上传图片，你不能声称自己看到了图片细节；只把它作为生图参考图使用，并在 image.promptHints 中说明如何利用参考图的气质、颜色或场景。

只输出合法 JSON，不要 markdown，不要解释。JSON 结构：
{
  "reply": "给用户看的简短说明",
  "template": "work|collection|profile",
  "category": "ai|strong|road",
  "fields": {
    "categoryTitle": "...",
    "categoryEn": "...",
    "categorySub": "...",
    "title": "...",
    "enTitle": "...",
    "summary": "...",
    "code": "..."
  },
  "image": {
    "theme": "用于生图的中文主题",
    "style": "cinematic|terminal|field|minimal",
    "density": "low|medium|high",
    "promptHints": "给 image model 的构图补充"
  },
  "reason": "一句话说明判断逻辑"
}
"""


def normalize_plan(plan, incoming, link_meta):
    fallback = fallback_plan(incoming, link_meta, "normalized_fallback")
    plan = plan if isinstance(plan, dict) else {}
    fields = plan.get("fields") if isinstance(plan.get("fields"), dict) else {}
    image = plan.get("image") if isinstance(plan.get("image"), dict) else {}
    out = {
        "reply": trim(plan.get("reply") or fallback["reply"], 180),
        "template": plan.get("template") if plan.get("template") in TEMPLATE_KEYS else fallback["template"],
        "category": plan.get("category") if plan.get("category") in CATEGORY_KEYS else fallback["category"],
        "fields": {},
        "image": {},
        "reason": trim(plan.get("reason") or fallback["reason"], 180),
    }
    for key, limit in {
        "categoryTitle": 12,
        "categoryEn": 42,
        "categorySub": 32,
        "title": 24,
        "enTitle": 44,
        "summary": 42,
        "code": 18,
    }.items():
        out["fields"][key] = trim(fields.get(key) or fallback["fields"].get(key), limit)
    out["image"]["theme"] = trim(image.get("theme") or fallback["image"]["theme"], 240)
    out["image"]["style"] = image.get("style") if image.get("style") in STYLE_KEYS else fallback["image"]["style"]
    out["image"]["density"] = image.get("density") if image.get("density") in DENSITY_KEYS else fallback["image"]["density"]
    out["image"]["promptHints"] = trim(image.get("promptHints") or fallback["image"]["promptHints"], 320)
    return out


def create_cover_plan(incoming):
    link_meta = fetch_douyin_metadata(incoming.get("douyin_url"))
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        plan = fallback_plan(incoming, link_meta, "missing_deepseek_api_key")
        return {
            "plan": plan,
            "reply": plan["reply"],
            "model": "local-fallback",
            "source": link_meta,
            "fallback": True,
        }

    current = incoming.get("current") or {}
    history = incoming.get("history") or []
    history = history[-8:] if isinstance(history, list) else []
    user_payload = {
        "user_message": trim(incoming.get("message"), 1200),
        "douyin_url": trim(incoming.get("douyin_url"), 500),
        "douyin_meta": link_meta,
        "has_uploaded_reference_image": bool(incoming.get("has_reference_image")),
        "current": current,
        "history": history,
    }
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "max_tokens": 1400,
    }
    request = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]
        plan = normalize_plan(safe_json_loads(content), incoming, link_meta)
        return {
            "plan": plan,
            "reply": plan["reply"],
            "model": model,
            "source": link_meta,
            "fallback": False,
            "usage": result.get("usage"),
        }
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        plan = fallback_plan(incoming, link_meta, "deepseek_http_error")
        return {
            "plan": plan,
            "reply": plan["reply"],
            "model": "local-fallback",
            "source": link_meta,
            "fallback": True,
            "error": message,
        }
    except Exception as exc:
        plan = fallback_plan(incoming, link_meta, "deepseek_failed")
        return {
            "plan": plan,
            "reply": plan["reply"],
            "model": "local-fallback",
            "source": link_meta,
            "fallback": True,
            "error": str(exc),
        }

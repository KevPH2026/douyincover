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
TEMPLATE_KEYS = {"work", "collection", "profile", "intro"}
STYLE_KEYS = {"cinematic", "terminal", "field", "minimal"}
DENSITY_KEYS = {"low", "medium", "high"}
DEFAULT_CHAT_ENDPOINT = "https://api.deepseek.com/chat/completions"
DNA_MIN_SAMPLE_COUNT = 10


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


def unescape_json_text(value):
    text = str(value or "")
    try:
        text = json.loads(f'"{text}"')
    except Exception:
        text = text.replace("\\n", " ").replace("\\/", "/").replace('\\"', '"')
    return html.unescape(text)


def extract_page_content_samples(page_text):
    samples = []
    seen = set()
    patterns = [
        r'"desc"\s*:\s*"((?:\\.|[^"\\]){8,260})"',
        r'"description"\s*:\s*"((?:\\.|[^"\\]){8,260})"',
        r'"title"\s*:\s*"((?:\\.|[^"\\]){8,260})"',
        r'"text"\s*:\s*"((?:\\.|[^"\\]){8,260})"',
        r'"caption"\s*:\s*"((?:\\.|[^"\\]){8,260})"',
        r'"share_title"\s*:\s*"((?:\\.|[^"\\]){8,260})"',
    ]
    ignored = {
        "抖音",
        "douyin",
        "推荐",
        "首页",
        "登录",
        "分享",
        "关注",
        "用户",
        "音乐",
    }
    for pattern in patterns:
        for raw in re.findall(pattern, page_text, flags=re.I):
            clean = clean_sample_line(unescape_json_text(raw))
            compact = re.sub(r"\s+", "", clean.lower())
            if len(compact) < 8 or compact in seen:
                continue
            if any(token in compact for token in ignored):
                continue
            seen.add(compact)
            samples.append(clean)
            if len(samples) >= 30:
                return samples
    return samples


def trim(value, limit):
    text = str(value or "").strip()
    return text[:limit]


def model_config(incoming, kind):
    config = incoming.get("model_config") if isinstance(incoming, dict) else {}
    config = config if isinstance(config, dict) else {}
    section = config.get(kind) if isinstance(config.get(kind), dict) else {}
    return {
        "endpoint": trim(section.get("endpoint"), 600),
        "model": trim(section.get("model"), 120),
        "api_key": trim(section.get("apiKey") or section.get("api_key"), 2000),
    }


def normalize_chat_endpoint(endpoint):
    raw = trim(endpoint, 600).rstrip("/")
    if not raw:
        return DEFAULT_CHAT_ENDPOINT
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("LLM 接口地址必须是 http/https URL。")
    if raw.endswith("/chat/completions"):
        return raw
    if raw.endswith("/v1"):
        return f"{raw}/chat/completions"
    return f"{raw}/chat/completions"


def post_chat_completion(endpoint, payload, api_key, timeout=60):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


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
    raise ValueError("LLM did not return valid JSON.")


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
        decoded = body.decode(charset, errors="replace")
    except Exception:
        decoded = body.decode("utf-8", errors="replace")
    parser.feed(decoded)

    data = parser.data()
    data["content_samples"] = extract_page_content_samples(decoded)
    data.update({"status": "ok", "url": url, "final_url": final_url})
    return data


URL_PATTERN = re.compile(r"https?://[^\s，。！!？?；;、)）\]】\"'<>]+", re.I)
HASHTAG_PATTERN = re.compile(r"#\s*([^#\s，。！？；;、]+)")


def normalize_space(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def extract_first_url(text):
    for match in URL_PATTERN.findall(str(text or "")):
        candidate = match.strip().rstrip("，。！!？?；;、")
        if candidate:
            return candidate
    return ""


def extract_hashtags(text):
    seen = set()
    tags = []
    ignored = {"抖音精选", "热评文案收集"}
    for match in HASHTAG_PATTERN.finditer(str(text or "")):
        tag = match.group(1).strip(" #，。！？；;、")
        key = tag.lower()
        if tag and tag not in ignored and key not in seen:
            seen.add(key)
            tags.append(tag)
    return tags[:12]


def strip_hashtags(text):
    return normalize_space(HASHTAG_PATTERN.sub(" ", str(text or "")).replace("#", " "))


def clean_share_text(text):
    raw = html.unescape(str(text or ""))
    raw = raw.replace("Dou音", "抖音").replace("dou音", "抖音")
    raw = URL_PATTERN.sub(" ", raw)
    for phrase in [
        "复制此链接，打开抖音搜索，直接观看视频！",
        "复制此链接，打开抖音搜索，直接观看视频",
        "复制此链接，打开Dou音搜索，直接观看视频！",
        "复制此链接，打开Dou音搜索，直接观看视频",
        "打开抖音搜索，直接观看视频！",
        "打开抖音搜索，直接观看视频",
        "抖音精选",
    ]:
        raw = raw.replace(phrase, " ")
    raw = normalize_space(raw)

    # Douyin share text often starts with copy-code noise before the first real Chinese phrase.
    first_cjk = re.search(r"[\u4e00-\u9fff]", raw)
    if first_cjk and 0 < first_cjk.start() <= 90:
        prefix = raw[: first_cjk.start()]
        noisy_tokens = re.findall(r"[A-Za-z0-9@:/._%-]+", prefix)
        if len(noisy_tokens) >= 2 or re.search(r"\d{1,2}/\d{1,2}|@", prefix):
            raw = raw[first_cjk.start() :]

    raw = re.sub(r"\s*([，。！？；、])\s*", r"\1", raw)
    raw = re.sub(r"\s+#", " #", raw)
    return normalize_space(raw).strip("，。！？；;、 ")


def build_douyin_context(incoming):
    share_text = trim(incoming.get("douyin_share_text"), 2000)
    message = trim(incoming.get("message"), 1200)
    explicit_url = trim(incoming.get("douyin_url"), 500)
    url = explicit_url or extract_first_url("\n".join([share_text, message]))
    meta = fetch_douyin_metadata(url)
    raw_text = "\n".join([share_text, message])
    hashtags = extract_hashtags(raw_text)
    clean_text = clean_share_text(share_text or message)
    clean_without_tags = strip_hashtags(clean_text)
    meta_text = " / ".join(
        item
        for item in [
            meta.get("og_title") or meta.get("title") or "",
            meta.get("og_description") or meta.get("description") or "",
        ]
        if item
    )
    source_text = " / ".join(
        item
        for item in [
            clean_without_tags,
            " ".join(f"#{tag}" for tag in hashtags),
            meta_text,
        ]
        if item
    )
    return {
        "status": meta.get("status", "empty"),
        "url": url,
        "share_text": share_text,
        "clean_text": trim(clean_text, 800),
        "clean_without_tags": trim(clean_without_tags, 600),
        "hashtags": hashtags,
        "source_text": trim(source_text, 1600),
        "cover_image_url": meta.get("cover_image_url", ""),
        "meta": meta,
    }


def clean_sample_line(text):
    line = clean_share_text(text)
    line = URL_PATTERN.sub(" ", line)
    line = re.sub(r"^\d+[\).、\s]+", "", line)
    line = normalize_space(line).strip(" -_/｜|，。#")
    if not line:
        return ""
    if any(
        phrase in line
        for phrase in [
            "复制此链接",
            "打开抖音搜索",
            "直接观看视频",
            "http://",
            "https://",
        ]
    ):
        return ""
    return trim(line, 220)


def extract_content_samples(incoming, douyin_context=None):
    samples = []
    seen = set()

    def add(text, source="text"):
        clean = clean_sample_line(text)
        compact = re.sub(r"\s+", "", clean.lower())
        if len(compact) < 6 or compact in seen:
            return
        seen.add(compact)
        samples.append({"text": clean, "source": source})

    for item in incoming.get("content_samples") or incoming.get("samples") or []:
        if isinstance(item, dict):
            add(item.get("title") or item.get("text") or item.get("caption") or "", item.get("source") or "sample")
        else:
            add(item, "sample")

    source_blocks = [
        incoming.get("source_text", ""),
        incoming.get("message", ""),
        incoming.get("douyin_share_text", ""),
    ]
    if douyin_context:
        source_blocks.extend(
            [
                douyin_context.get("source_text", ""),
                douyin_context.get("clean_without_tags", ""),
                douyin_context.get("clean_text", ""),
            ]
        )

    for block in source_blocks:
        text = str(block or "")
        if not text:
            continue
        candidates = re.split(r"[\n\r]+|(?=\s*\d+[\).、])|(?=#)", text)
        for candidate in candidates:
            add(candidate, "pasted")

    if douyin_context:
        meta = douyin_context.get("meta") or {}
        for sample in meta.get("content_samples") or []:
            add(sample, "douyin_page")
        add(meta.get("og_title") or meta.get("title") or "", "douyin_meta")
        add(meta.get("og_description") or meta.get("description") or "", "douyin_meta")

    return samples[:40]


def keyword_hits(samples, keywords):
    text = "\n".join(item["text"] for item in samples).lower()
    compact = re.sub(r"\s+", "", text)
    return sum(1 for keyword in keywords if keyword.lower() in text or keyword in compact)


def local_client_dna(samples, douyin_context, reason="local_dna"):
    ai_score = keyword_hits(samples, ["ai", "模型", "agent", "openai", "deepseek", "saas", "api", "自动化"])
    business_score = keyword_hits(samples, ["商业", "创业", "公司", "估值", "增长", "产品", "客户", "市场"])
    cognition_score = keyword_hits(samples, ["认知", "判断", "强者", "乔布斯", "聪明", "选择", "底层逻辑"])
    field_score = keyword_hits(samples, ["出差", "路上", "客户现场", "一线", "机场", "城市", "跨境", "现场"])

    pillars = []
    if ai_score:
        pillars.append({"name": "AI 商业判断", "evidence": "样本里高频出现模型、Agent、API、SaaS 或自动化。"})
    if cognition_score:
        pillars.append({"name": "强者认知 / 判断力", "evidence": "样本里出现强者、判断、聪明人、选择等观点型表达。"})
    if field_score:
        pillars.append({"name": "一线观察 / 在路上", "evidence": "样本里有出差、客户、一线、现场等行动场景。"})
    if business_score and not any(item["name"] == "AI 商业判断" for item in pillars):
        pillars.append({"name": "商业增长 / 产品策略", "evidence": "样本里有公司、产品、客户、增长、估值等商业词。"})
    if not pillars:
        pillars.append({"name": "观点表达", "evidence": "样本更像观点集合，需要更多作品判断稳定栏目。"})

    tone = "冷静、判断型、有压迫感" if cognition_score >= field_score else "一线、真实、行动感"
    if ai_score >= max(cognition_score, field_score):
        tone = "深夜科技商业、克制但锋利"

    return {
        "status": "complete",
        "sample_count": len(samples),
        "min_required": DNA_MIN_SAMPLE_COUNT,
        "source_url": douyin_context.get("url", "") if douyin_context else "",
        "client_dna": {
            "positioning": "AI 时代的商业判断与个人系统内容账号",
            "audience": "关注 AI、商业变化、个人成长和判断力的创业者/知识工作者",
            "voice": tone,
            "content_pillars": pillars[:4],
            "signature_titles": [
                "这不是热点，这是重新定价",
                "判断不能外包",
                "在路上才有答案",
            ],
        },
        "style_signals": {
            "keywords": ["dark editorial", "AI business", "field notes", "strong judgment"],
            "avoid": ["通用 AI 壁纸", "花哨渐变", "营销海报感", "信息过满"],
            "visual_mood": tone,
        },
        "design_directions": [
            {
                "name": "Deep Work Command",
                "best_for": "AI、模型、公司、产品趋势类作品",
                "palette": "黑底 + 石墨灰 + 荧光绿",
                "background": "真实屏幕、终端、办公室、产品界面局部，不出现可读文字",
                "layout": "大标题左压，右侧场景，顶部固定品牌和头像印章",
            },
            {
                "name": "Strong Signal Editorial",
                "best_for": "强者恒强、乔布斯、判断力、认知内容",
                "palette": "黑白影像 + 冷青色高光",
                "background": "深夜书桌、白板、会议室、人物剪影，保持低调压迫感",
                "layout": "2-3 行中文判断句，英文副标题小字，编号 K-xx",
            },
            {
                "name": "Road Field Notes",
                "best_for": "出差、客户、一线观察、跨境场景",
                "palette": "夜色黑 + 暖白 + 红色小信号",
                "background": "机场、车窗、城市夜景、客户现场，保留大面积安全留白",
                "layout": "标题更像现场笔记，加入 ON THE ROAD 系列感",
            },
        ],
        "operating_rules": [
            "默认先收集至少 10 条公开作品样本，再定视觉 DNA。",
            "每个账号最多保留 3 个主栏目，避免主页变成分类货架。",
            "单条封面必须出现作品标题，播放量等历史数据不进封面。",
            "背景图只服务主题，不承担文字信息。",
        ],
        "next_questions": [
            "这个账号更想卖观点、卖服务，还是卖个人 IP？",
            "主页希望更像商业顾问、AI 产品人，还是一线创业者？",
            "是否有必须保留的头像、品牌色、口号或微信 ID？",
        ],
        "samples": samples[:12],
        "reason": reason,
    }


DNA_SYSTEM_PROMPT = """
你是一个短视频账号视觉 DNA 解码顾问。用户会提供抖音主页/作品链接、至少 10 条作品样本、截图转文字或分享文案。你的任务不是生成单张封面，而是为该账号提炼账号 DNA，并输出可执行的封面/主页/合集设计方向。

硬规则：
- 不得声称看到了没有提供的作品。
- 样本不足 10 条时不能做完整结论，只能要求补样本。
- 设计方向必须来自样本中的内容主题、表达方式、标题气质、视觉/场景线索。
- 输出要能直接指导封面系统：栏目、字体气质、配色、背景类型、版式、禁忌。

只输出合法 JSON，不要 markdown，不要解释。JSON 结构：
{
  "status": "complete",
  "client_dna": {
    "positioning": "...",
    "audience": "...",
    "voice": "...",
    "content_pillars": [{"name": "...", "evidence": "..."}],
    "signature_titles": ["..."]
  },
  "style_signals": {
    "keywords": ["..."],
    "avoid": ["..."],
    "visual_mood": "..."
  },
  "design_directions": [
    {
      "name": "...",
      "best_for": "...",
      "palette": "...",
      "background": "...",
      "layout": "..."
    }
  ],
  "operating_rules": ["..."],
  "next_questions": ["..."]
}
"""


def need_more_samples_response(samples, douyin_context):
    url = douyin_context.get("url", "") if douyin_context else ""
    return {
        "status": "need_samples",
        "sample_count": len(samples),
        "min_required": DNA_MIN_SAMPLE_COUNT,
        "missing_count": max(0, DNA_MIN_SAMPLE_COUNT - len(samples)),
        "source_url": url,
        "reply": f"目前只拿到 {len(samples)} 条可用内容样本。解码 DNA 至少需要 {DNA_MIN_SAMPLE_COUNT} 条公开作品样本，还差 {max(0, DNA_MIN_SAMPLE_COUNT - len(samples))} 条。",
        "collection_guide": [
            "粘贴抖音主页链接，并补充最近 10-20 条作品标题/文案。",
            "如果链接受登录或反爬限制，发主页作品列表截图或复制作品标题。",
            "每条样本最好包含：标题、口播核心句、封面文字、发布时间或播放表现。",
        ],
        "samples": samples,
    }


def analyze_client_dna(incoming):
    douyin_context = build_douyin_context(incoming)
    samples = extract_content_samples(incoming, douyin_context)
    if len(samples) < DNA_MIN_SAMPLE_COUNT:
        return need_more_samples_response(samples, douyin_context)

    llm_config = model_config(incoming, "llm")
    has_custom_llm = bool(llm_config["endpoint"] or llm_config["model"] or llm_config["api_key"])
    api_key = llm_config["api_key"] or os.environ.get("DEEPSEEK_API_KEY")
    endpoint = normalize_chat_endpoint(llm_config["endpoint"] or DEFAULT_CHAT_ENDPOINT)
    model = llm_config["model"] or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    if not api_key and not has_custom_llm:
        dna = local_client_dna(samples, douyin_context, "missing_llm_api_key")
        dna.update({"reply": "已基于样本生成本地 DNA 解码；配置 LLM 后可获得更细的设计方向。", "model": "local-fallback", "fallback": True})
        return dna

    user_payload = {
        "douyin_url": douyin_context.get("url", ""),
        "douyin_context": douyin_context,
        "sample_count": len(samples),
        "samples": samples[:30],
        "user_goal": trim(incoming.get("goal") or incoming.get("message"), 1200),
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": DNA_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "max_tokens": 2400,
    }
    try:
        try:
            result = post_chat_completion(endpoint, payload, api_key, timeout=80)
        except urllib.error.HTTPError as exc:
            if has_custom_llm and exc.code in {400, 422} and "response_format" in payload:
                relaxed_payload = dict(payload)
                relaxed_payload.pop("response_format", None)
                result = post_chat_completion(endpoint, relaxed_payload, api_key, timeout=80)
            else:
                raise
        parsed = safe_json_loads(result["choices"][0]["message"]["content"])
        dna = local_client_dna(samples, douyin_context, "llm_normalized")
        dna.update({k: v for k, v in parsed.items() if k in {"client_dna", "style_signals", "design_directions", "operating_rules", "next_questions"}})
        dna.update(
            {
                "status": "complete",
                "sample_count": len(samples),
                "min_required": DNA_MIN_SAMPLE_COUNT,
                "samples": samples[:12],
                "reply": f"已读取并整理 {len(samples)} 条内容样本，生成账号 DNA 和设计方向。",
                "model": model,
                "provider": "local-config" if has_custom_llm else "deepseek-env",
                "fallback": False,
                "usage": result.get("usage"),
            }
        )
        return dna
    except Exception as exc:
        dna = local_client_dna(samples, douyin_context, "llm_failed")
        dna.update({"reply": "LLM 暂不可用，已基于样本生成本地 DNA 解码。", "model": "local-fallback", "fallback": True, "error": str(exc)})
        return dna


def infer_category(text):
    source = str(text or "").lower()
    compact = re.sub(r"\s+", "", source)
    if any(k in compact for k in ["强势文化", "乔布斯", "强者恒强", "聪明的人"]):
        return "strong"
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
    if "乔布斯" in compact and any(k in compact for k in ["聪明", "交往", "多和", "强势文化", "强者恒强"]):
        return "乔布斯：\n多和聪明的人\n交往"
    if "乔布斯" in compact:
        return "乔布斯\n强者逻辑"
    if "强势文化" in compact:
        return "强势\n文化"
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


def fallback_summary(text, category, current_summary):
    source = str(text or "")
    compact = re.sub(r"\s+", "", source)
    if "乔布斯" in compact and any(k in compact for k in ["聪明", "交往", "多和", "强势文化", "强者恒强"]):
        return "强者会主动进入更高密度的人群。"
    if "强势文化" in compact:
        return "不是情绪强，是判断和行动更稳定。"
    if "强者恒强" in compact:
        return "差距会在每一次判断里继续拉开。"
    if category == "ai":
        return "看懂模型之后，才看得懂生意。"
    if category == "road":
        return "一线现场，比会议室更早给答案。"
    return trim(current_summary or "把这一轮变化讲清楚。", 34)


def fallback_en_title(text, category, current_en_title):
    source = str(text or "")
    compact = re.sub(r"\s+", "", source)
    if "乔布斯" in compact and any(k in compact for k in ["聪明", "强势文化", "强者恒强"]):
        return "Stay With Smart People"
    if "强势文化" in compact:
        return "Strong Culture"
    if "强者恒强" in compact:
        return "The Strong Get Stronger"
    if category == "ai":
        return "AI Field Note"
    if category == "road":
        return "Road Note"
    return trim(current_en_title or "Field Note", 36)


def fallback_image_theme(text, category, current_theme):
    source = trim(text, 180)
    compact = re.sub(r"\s+", "", source)
    if "乔布斯" in compact and any(k in compact for k in ["聪明", "强势文化", "强者恒强"]):
        return "硅谷深夜办公室，聪明人围绕白板讨论，黑白肖像气质，强势文化，低调电影感"
    if "强势文化" in compact:
        return "强势文化，深夜会议室，白板，筹码，判断力，安静的压迫感"
    if source:
        return source
    return current_theme or (
        "出差在路上，机场候机，客户现场，一线观察，雨夜城市"
        if category == "road"
        else "深夜城市，AI商业判断，代码屏幕"
    )


def fallback_plan(incoming, douyin_context, reason="local_fallback"):
    current = incoming.get("current") or {}
    message = "" if douyin_context.get("share_text") else trim(incoming.get("message"), 500)
    source_text = " / ".join(
        item
        for item in [
            douyin_context.get("source_text") or "",
            message if message and message not in (douyin_context.get("source_text") or "") else "",
        ]
        if item
    )
    category = infer_category(source_text)
    template_source = normalize_space(
        " ".join(
            [
                str(current.get("template") or ""),
                trim(incoming.get("message"), 500),
                trim(incoming.get("goal"), 500),
                source_text,
            ]
        )
    ).lower()
    wants_intro = current.get("template") == "intro" or any(
        token in template_source
        for token in ["片头", "动效", "视频开头", "前1秒", "前2秒", "1-2秒", "intro", "motion"]
    )
    template = "intro" if wants_intro else "work"
    clean = URL_PATTERN.sub(" ", source_text).strip(" /，。")
    readable_clean = strip_hashtags(clean).strip(" /，。#")
    title = trim(fallback_title(clean, current.get("title")), 24)
    summary = trim(fallback_summary(clean, category, current.get("summary")), 42)
    en_title = trim(fallback_en_title(clean, category, current.get("enTitle")), 44)

    category_defaults = {
        "ai": ("AI下半场", "AI SECOND HALF", "模型 / Agent / 商业重构", "AI-01"),
        "strong": ("强者恒强", "THE STRONG GET STRONGER", "判断力 / 筹码 / 个体系统", "K-01"),
        "road": ("在路上", "ON THE ROAD", "出差 / 客户 / 一线观察", "ROAD-01"),
    }[category]

    return {
        "reply": "我先按现有账号规则生成了一版封面方案；LLM 未配置或不可用时会走本地判断。",
        "template": template,
        "category": category,
        "fields": {
            "categoryTitle": category_defaults[0],
            "categoryEn": category_defaults[1],
            "categorySub": category_defaults[2],
            "title": title,
            "enTitle": en_title,
            "summary": summary,
            "code": "M-01" if template == "intro" else category_defaults[3],
        },
        "image": {
            "theme": trim(fallback_image_theme(clean, category, current.get("imageTheme")), 180),
            "style": "field" if category == "road" else "cinematic",
            "density": "medium",
            "promptHints": trim(readable_clean or clean, 220),
        },
        "reason": reason,
    }


SYSTEM_PROMPT = """
你是 Mr.K 在路上的抖音封面导演。你的任务是把自然语言、抖音作品链接信息、抖音分享文案、当前封面字段，整理成可以直接套用的封面方案。

账号固定规则：
- 账号：MR.K 在路上；ID：KevPH2026。
- 只使用三类栏目：ai=AI下半场，strong=强者恒强，road=在路上。
- 输出形态：work=单条静态封面，collection=合集封面，profile=主页背景，intro=覆盖视频前 1-2 秒的片头动效。
- 单条作品封面要服务点击：中文标题必须短、狠、好读，建议 2-8 个汉字一行，用 \\n 控制换行，最多 3 行。
- 片头动效也要服务点击：主干观点必须在 1-2 秒内大字出现，可以比静态封面更像开场 punchline。
- 摘要是点击理由，不要流水账，控制在 12-28 个中文字符。
- 图片只做背景，不要把标题文字写进生成图里；标题由前端固定版式叠加。
- 如果用户提到“片头、动效、视频开头、覆盖前 1-2 秒、intro、motion”，优先选择 template=intro。
- 如果用户只粘贴抖音分享文案或短链，优先使用 douyin_context.clean_without_tags、hashtags 和 douyin_meta 来判断主题；忽略复制口令、时间、随机码、"复制此链接" 这类噪声。
- 如果用户上传图片，你不能声称自己看到了图片细节；只把它作为生图参考图使用，并在 image.promptHints 中说明如何利用参考图的气质、颜色或场景。

只输出合法 JSON，不要 markdown，不要解释。JSON 结构：
{
  "reply": "给用户看的简短说明",
  "template": "work|collection|profile|intro",
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


def normalize_plan(plan, incoming, douyin_context):
    fallback = fallback_plan(incoming, douyin_context, "normalized_fallback")
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
    douyin_context = build_douyin_context(incoming)
    link_meta = douyin_context.get("meta") or {}
    llm_config = model_config(incoming, "llm")
    has_custom_llm = bool(llm_config["endpoint"] or llm_config["model"] or llm_config["api_key"])
    api_key = llm_config["api_key"] or os.environ.get("DEEPSEEK_API_KEY")
    endpoint = normalize_chat_endpoint(llm_config["endpoint"] or DEFAULT_CHAT_ENDPOINT)
    model = llm_config["model"] or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    if not api_key and not has_custom_llm:
        plan = fallback_plan(incoming, douyin_context, "missing_deepseek_api_key")
        return {
            "plan": plan,
            "reply": plan["reply"],
            "model": "local-fallback",
            "source": douyin_context,
            "fallback": True,
        }

    current = incoming.get("current") or {}
    history = incoming.get("history") or []
    history = history[-8:] if isinstance(history, list) else []
    user_payload = {
        "user_message": trim(incoming.get("message"), 1200),
        "douyin_share_text": trim(incoming.get("douyin_share_text"), 2000),
        "douyin_url": trim(incoming.get("douyin_url"), 500),
        "douyin_context": douyin_context,
        "douyin_meta": link_meta,
        "has_uploaded_reference_image": bool(incoming.get("has_reference_image")),
        "current": current,
        "history": history,
    }
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

    try:
        try:
            result = post_chat_completion(endpoint, payload, api_key)
        except urllib.error.HTTPError as exc:
            if has_custom_llm and exc.code in {400, 422} and "response_format" in payload:
                relaxed_payload = dict(payload)
                relaxed_payload.pop("response_format", None)
                result = post_chat_completion(endpoint, relaxed_payload, api_key)
            else:
                raise
        content = result["choices"][0]["message"]["content"]
        plan = normalize_plan(safe_json_loads(content), incoming, douyin_context)
        return {
            "plan": plan,
            "reply": plan["reply"],
            "model": model,
            "provider": "local-config" if has_custom_llm else "deepseek-env",
            "source": douyin_context,
            "fallback": False,
            "usage": result.get("usage"),
        }
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        plan = fallback_plan(incoming, douyin_context, "deepseek_http_error")
        return {
            "plan": plan,
            "reply": plan["reply"],
            "model": "local-fallback",
            "source": douyin_context,
            "fallback": True,
            "error": message,
        }
    except Exception as exc:
        plan = fallback_plan(incoming, douyin_context, "deepseek_failed")
        return {
            "plan": plan,
            "reply": plan["reply"],
            "model": "local-fallback",
            "source": douyin_context,
            "fallback": True,
            "error": str(exc),
        }

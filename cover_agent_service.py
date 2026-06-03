import html
import json
import os
import re
import shutil
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
TEMPLATE_KEYS = {"work", "collection", "profile", "intro", "outro"}
STYLE_KEYS = {"cinematic", "terminal", "field", "minimal"}
DENSITY_KEYS = {"low", "medium", "high"}
DEFAULT_CHAT_ENDPOINT = "https://api.deepseek.com/chat/completions"
DNA_MIN_SAMPLE_COUNT = 10
DOUYIN_FETCH_LIMIT = 1_500_000
DOUYIN_PROFILE_SAMPLE_LIMIT = 8


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


def extract_visible_content_samples(visible_text):
    samples = []
    seen = set()
    ignored_exact = {
        "开启读屏标签",
        "读屏标签已关闭",
        "精选",
        "推荐",
        "搜索",
        "关注",
        "朋友",
        "我的",
        "直播",
        "放映厅",
        "短剧",
        "通知",
        "投稿",
        "登录",
        "客户端",
        "壁纸",
        "打开声音",
        "相关推荐",
    }

    def add(line):
        clean = clean_sample_line(line)
        clean = re.sub(r"^第\s*\d+\s*集\s*[:：]\s*", "", clean)
        clean = re.sub(r"^发布时间\s*[:：].*$", "", clean)
        clean = normalize_space(clean).strip(" -_/｜|，。#")
        compact = re.sub(r"\s+", "", clean.lower())
        if len(compact) < 8 or compact in seen or clean in ignored_exact:
            return
        if re.fullmatch(r"[\d.,万wW]+", compact):
            return
        seen.add(compact)
        samples.append(clean)

    for raw in re.split(r"[\n\r]+", str(visible_text or "")):
        line = normalize_space(raw)
        if not line:
            continue
        if re.match(r"^第\s*\d+\s*集\s*[:：]", line) or "#" in line:
            add(line)
        elif 8 <= len(line) <= 180 and any(token in line.lower() for token in ["ai", "模型", "强者", "人生", "客户", "商业", "判断", "saas"]):
            add(line)
        if len(samples) >= 30:
            break
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


def read_url_text(url, timeout=8, limit=DOUYIN_FETCH_LIMIT):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.douyin.com/",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(limit)
        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
    try:
        decoded = body.decode(charset, errors="replace")
    except Exception:
        decoded = body.decode("utf-8", errors="replace")
    return final_url, decoded


def normalize_douyin_absolute_url(url, base_url="https://www.douyin.com"):
    raw = html.unescape(str(url or "")).replace("\\/", "/").strip()
    raw = raw.rstrip("\\")
    if raw.startswith("//"):
        raw = "https:" + raw
    if raw.startswith("/"):
        raw = urllib.parse.urljoin(base_url, raw)
    raw = raw.split("#")[0]
    if is_allowed_douyin_url(raw):
        return raw
    return ""


def normalize_sec_uid(value):
    text = unescape_json_text(value).replace("\\/", "/").strip()
    match = re.search(r"(MS4wLj[A-Za-z0-9_.-]{20,})", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_.-]{20,220}", text):
        return text
    return ""


def extract_douyin_aweme_id(url, page_text=""):
    for source in [str(url or ""), str(page_text or "")]:
        decoded = html.unescape(source).replace("\\/", "/")
        match = re.search(r"/(?:video|note)/(\d{10,30})", decoded)
        if match:
            return match.group(1)
        for pattern in [
            r'"aweme_id"\s*:\s*"(\d{10,30})"',
            r'"awemeId"\s*:\s*"(\d{10,30})"',
            r'"item_id"\s*:\s*"(\d{10,30})"',
            r'"note_id"\s*:\s*"(\d{10,30})"',
        ]:
            match = re.search(pattern, decoded, flags=re.I)
            if match:
                return match.group(1)
    return ""


def clean_identity_value(value, limit=120):
    text = unescape_json_text(value)
    text = normalize_space(text).strip(" ｜|_-，。:：")
    if not text or "http://" in text or "https://" in text:
        return ""
    if any(token in text.lower() for token in ["douyin.com", "iesdouyin.com", "undefined", "null"]):
        return ""
    if any(token in text.lower() for token in ["middleware", "perf_timing", "router_data", "render"]):
        return ""
    return trim(text, limit)


def invalid_nickname(value):
    text = str(value or "").strip()
    if not text:
        return True
    if len(text) > 36:
        return True
    return any(token in text for token in ["#", "发布在抖音", "来抖音", "第", "集：", "集 |"])


def first_json_field(page_text, keys, limit=120):
    sources = [str(page_text or ""), html.unescape(str(page_text or "")).replace("\\/", "/")]
    for source in sources:
        for key in keys:
            patterns = [
                rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\]){{1,{limit * 4}}})"',
                rf'\\"{re.escape(key)}\\"\s*:\s*\\"((?:\\.|[^"\\]){{1,{limit * 4}}})\\"',
            ]
            for pattern in patterns:
                match = re.search(pattern, source, flags=re.I)
                if match:
                    clean = clean_identity_value(match.group(1), limit)
                    if clean:
                        return clean
    return ""


def extract_avatar_url(page_text):
    decoded = html.unescape(str(page_text or "")).replace("\\/", "/")
    candidates = []
    for pattern in [
        r'"avatar[^"]*"\s*:\s*\{[^{}]{0,900}?"url_list"\s*:\s*\[\s*"([^"]+)"',
        r'"avatar[^"]*"\s*:\s*"([^"]+)"',
        r'(https?://[^"\'\s<>\\]+(?:avatar|aweme-avatar)[^"\'\s<>\\]+\.(?:webp|jpg|jpeg|png)[^"\'\s<>\\]*)',
    ]:
        candidates.extend(re.findall(pattern, decoded, flags=re.I))

    for candidate in candidates:
        url = html.unescape(str(candidate or "")).replace("\\/", "/").replace("\\u002F", "/").strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            continue
        if "avatar" in url.lower() and any(host in url for host in ["douyinpic.com", "douyinstatic.com", "byteimg.com", "pstatp.com", "toutiaoimg.com"]):
            return trim(url, 1000)
    return ""


def extract_douyin_identity(page_text, final_url="", meta=None):
    meta = meta or {}
    text = str(page_text or "")
    decoded = html.unescape(text).replace("\\/", "/")
    nickname = first_json_field(decoded, ["nickname", "nick_name", "author_name", "user_name"], 80)
    douyin_id = first_json_field(decoded, ["unique_id", "uniqueId", "douyin_id", "douyinId", "display_id"], 80)
    short_id = first_json_field(decoded, ["short_id", "shortId"], 80)
    sec_uid = normalize_sec_uid(first_json_field(decoded, ["sec_uid", "secUid"], 220))
    signature = first_json_field(decoded, ["signature", "desc", "description"], 220)
    avatar_url = extract_avatar_url(decoded)

    visible_name = ""
    for pattern in [
        r"(?:^|\n)\s*([^\n]{2,40}?)\s*\n+\s*粉丝\s*[\d.万wW]+",
        r"(?:^|\n)\s*([^\n]{2,40}?)\s*\n+\s*获赞\s*[\d.万wW]+",
        r"([A-Za-z0-9_.\-\u4e00-\u9fff]{2,40})的抖音主页",
    ]:
        match = re.search(pattern, decoded)
        if match:
            visible_name = clean_identity_value(match.group(1), 80)
            if visible_name and visible_name not in {"抖音", "精选", "推荐"}:
                break

    meta_title = clean_identity_value(meta.get("og_title") or meta.get("title") or "", 120)
    meta_desc = clean_identity_value(meta.get("og_description") or meta.get("description") or "", 220)
    profile_desc_name = ""
    if meta_desc:
        match = re.search(r"([A-Za-z0-9_.\-\u4e00-\u9fff]{2,40})的抖音主页", meta_desc)
        if match:
            profile_desc_name = clean_identity_value(match.group(1), 80)
    if not nickname and meta_title:
        for separator in ["的抖音", " - 抖音", " | 抖音", "抖音"]:
            if separator in meta_title:
                nickname = clean_identity_value(meta_title.split(separator)[0], 80)
                break
    if invalid_nickname(nickname) and visible_name:
        nickname = visible_name
    if invalid_nickname(nickname) and profile_desc_name:
        nickname = profile_desc_name
    if invalid_nickname(nickname) and signature:
        signature_head = clean_identity_value(re.split(r"[。,.，\s]", signature)[0], 80)
        if signature_head and signature_head not in {"抖音", "精选", "推荐"} and not invalid_nickname(signature_head):
            nickname = signature_head
    if invalid_nickname(nickname):
        nickname = ""
    if not signature and meta_desc:
        signature = meta_desc
    if not avatar_url and meta.get("cover_image_url"):
        avatar_url = meta.get("cover_image_url")

    parsed = urllib.parse.urlparse(str(final_url or ""))
    profile_url = extract_douyin_profile_url(decoded, final_url)
    if parsed.path.startswith("/user/") and not profile_url:
        profile_url = final_url

    if not sec_uid and profile_url:
        match = re.search(r"/user/([^/?#]+)", profile_url)
        if match:
            sec_uid = normalize_sec_uid(urllib.parse.unquote(match.group(1)))

    return {
        "nickname": nickname,
        "douyin_id": douyin_id,
        "short_id": short_id,
        "sec_uid": sec_uid,
        "signature": signature,
        "avatar_url": avatar_url,
        "profile_url": profile_url,
        "aweme_id": extract_douyin_aweme_id(final_url, decoded),
    }


def merge_identity(*identities):
    merged = {}
    for identity in identities:
        if not isinstance(identity, dict):
            continue
        for key in ["nickname", "douyin_id", "short_id", "sec_uid", "signature", "avatar_url", "profile_url", "aweme_id"]:
            value = identity.get(key)
            if value and not merged.get(key):
                merged[key] = value
    return merged


def extract_douyin_profile_url(page_text, final_url=""):
    candidates = []
    parsed_final = urllib.parse.urlparse(str(final_url or ""))
    if parsed_final.path.startswith("/user/"):
        candidates.append(final_url)

    text = str(page_text or "")
    decoded = html.unescape(text).replace("\\/", "/")
    patterns = [
        r'https?:\\/\\/(?:www\\.)?douyin\\.com\\/user\\/([^"\'\\\s<>?#]{8,220})',
        r'https?://(?:www\.)?douyin\.com/user/([^"\'\\\s<>?#]{8,220})',
        r'(?<![\w/])/(?:user)/([^"\'\\\s<>?#]{8,220})',
    ]
    for source in [text, decoded]:
        for pattern in patterns:
            for match in re.findall(pattern, source, flags=re.I):
                candidate = match[0] if isinstance(match, tuple) else match
                if candidate.startswith("http"):
                    candidates.append(candidate)
                else:
                    candidates.append(f"https://www.douyin.com/user/{candidate}")

        for pattern in [
            r'"sec_uid"\s*:\s*"((?:\\.|[^"\\]){10,220})"',
            r'"secUid"\s*:\s*"((?:\\.|[^"\\]){10,220})"',
            r'\\"sec_uid\\"\s*:\s*\\"((?:\\.|[^"\\]){10,220})\\"',
            r'\\"secUid\\"\s*:\s*\\"((?:\\.|[^"\\]){10,220})\\"',
        ]:
            for raw in re.findall(pattern, source):
                sec_uid = normalize_sec_uid(raw)
                if not sec_uid or "/" in sec_uid or "<" in sec_uid:
                    continue
                candidates.append(f"https://www.douyin.com/user/{urllib.parse.quote(sec_uid, safe='-_')}")

    seen = set()
    for candidate in candidates:
        clean = normalize_douyin_absolute_url(candidate)
        key = clean.split("?")[0]
        if clean and key not in seen:
            return clean
        seen.add(key)
    return ""


def extract_douyin_work_urls(page_text, base_url="https://www.douyin.com"):
    text = html.unescape(str(page_text or "")).replace("\\/", "/")
    candidates = []
    for pattern in [
        r'https?://(?:www\.)?douyin\.com/(?:video|note)/\d{10,30}',
        r'(?<![\w/])/(?:video|note)/\d{10,30}',
    ]:
        candidates.extend(re.findall(pattern, text, flags=re.I))

    seen = set()
    urls = []
    for candidate in candidates:
        clean = normalize_douyin_absolute_url(candidate, base_url)
        key = clean.split("?")[0]
        if not clean or key in seen:
            continue
        seen.add(key)
        urls.append(clean)
        if len(urls) >= 20:
            break
    return urls


def fetch_douyin_page(url, timeout=8, limit=DOUYIN_FETCH_LIMIT):
    try:
        final_url, decoded = read_url_text(url, timeout=timeout, limit=limit)
    except Exception as exc:
        return {"status": "failed", "url": url, "message": str(exc)}

    parser = PageMetaParser()
    parser.feed(decoded)
    data = parser.data()
    data["content_samples"] = extract_page_content_samples(decoded)
    data["profile_url"] = extract_douyin_profile_url(decoded, final_url)
    data["work_urls"] = extract_douyin_work_urls(decoded, final_url)
    data["aweme_id"] = extract_douyin_aweme_id(final_url, decoded)
    data["identity"] = extract_douyin_identity(decoded, final_url, data)
    data.update({"status": "ok", "url": url, "final_url": final_url})
    return data


def browser_executable_path():
    env_path = os.environ.get("MRK_BROWSER_EXECUTABLE", "").strip()
    if env_path and os.path.exists(env_path):
        return env_path
    for candidate in [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]:
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def fetch_douyin_rendered_page(url, timeout_ms=18000):
    if os.environ.get("MRK_DISABLE_DOUYIN_RENDER", "").lower() in {"1", "true", "yes"}:
        return {"status": "skipped", "url": url, "message": "Rendered Douyin fetch disabled."}
    executable = browser_executable_path()
    if not executable:
        return {"status": "skipped", "url": url, "message": "No local Chrome/Chromium executable available."}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "skipped", "url": url, "message": f"Playwright unavailable: {exc}"}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=executable)
            page = browser.new_page(
                locale="zh-CN",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36",
                viewport={"width": 1440, "height": 1100},
            )
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(3500)
            rendered = page.evaluate(
                """() => ({
                    url: location.href,
                    title: document.title || "",
                    bodyText: document.body ? document.body.innerText : "",
                    html: document.documentElement ? document.documentElement.innerHTML : "",
                    links: Array.from(document.querySelectorAll("a[href]")).map(a => a.href).filter(Boolean).slice(0, 120),
                    metas: Array.from(document.querySelectorAll("meta")).map(m => ({
                        name: m.getAttribute("name") || m.getAttribute("property") || "",
                        content: m.getAttribute("content") || ""
                    })).filter(item => item.name || item.content).slice(0, 80)
                })"""
            )
            browser.close()
    except Exception as exc:
        return {"status": "failed", "url": url, "message": str(exc)}

    final_url = rendered.get("url") or url
    body_text = rendered.get("bodyText") or ""
    html_text = rendered.get("html") or ""
    links_text = "\n".join(rendered.get("links") or [])
    combined = "\n".join([html_text[:DOUYIN_FETCH_LIMIT], body_text[:120_000], links_text])
    parser = PageMetaParser()
    parser.feed(html_text)
    data = parser.data()
    meta_from_dom = {str(item.get("name", "")).lower(): item.get("content", "") for item in rendered.get("metas") or []}
    for key, value in meta_from_dom.items():
        if value and key in {"og:title", "description", "og:description", "og:image", "twitter:image"}:
            if key == "og:image" or key == "twitter:image":
                data["cover_image_url"] = data.get("cover_image_url") or value
            else:
                data[key.replace(":", "_")] = data.get(key.replace(":", "_")) or value
    data["title"] = data.get("title") or rendered.get("title", "")
    data["content_samples"] = []
    seen = set()
    for sample in extract_visible_content_samples(body_text) + extract_page_content_samples(combined):
        compact = re.sub(r"\s+", "", sample.lower())
        if compact and compact not in seen:
            seen.add(compact)
            data["content_samples"].append(sample)
        if len(data["content_samples"]) >= 40:
            break
    data["profile_url"] = extract_douyin_profile_url(combined, final_url)
    data["work_urls"] = extract_douyin_work_urls(combined, final_url)
    data["aweme_id"] = extract_douyin_aweme_id(final_url, combined)
    data["identity"] = extract_douyin_identity(combined, final_url, data)
    data.update(
        {
            "status": "ok",
            "rendered": True,
            "url": url,
            "final_url": final_url,
            "visible_text": trim(body_text, 4000),
            "link_count": len(rendered.get("links") or []),
        }
    )
    return data


def merge_sample_lists(*lists, limit=40):
    samples = []
    seen = set()
    for items in lists:
        for item in items or []:
            clean = clean_sample_line(item)
            compact = re.sub(r"\s+", "", clean.lower())
            if len(compact) < 6 or compact in seen:
                continue
            seen.add(compact)
            samples.append(clean)
            if len(samples) >= limit:
                return samples
    return samples


def merge_url_lists(*lists, limit=20):
    urls = []
    seen = set()
    for items in lists:
        for item in items or []:
            clean = normalize_douyin_absolute_url(item)
            key = clean.split("?")[0]
            if not clean or key in seen:
                continue
            seen.add(key)
            urls.append(clean)
            if len(urls) >= limit:
                return urls
    return urls


def merge_page_metadata(static_data, rendered_data):
    if not rendered_data or rendered_data.get("status") != "ok":
        if rendered_data:
            static_data["rendered_status"] = rendered_data.get("status")
            static_data["rendered_message"] = rendered_data.get("message", "")
        return static_data
    merged = dict(static_data)
    merged["rendered_status"] = "ok"
    merged["rendered_final_url"] = rendered_data.get("final_url", "")
    for key in ["title", "og_title", "description", "og_description", "cover_image_url", "profile_url", "aweme_id", "visible_text"]:
        if rendered_data.get(key) and not merged.get(key):
            merged[key] = rendered_data[key]
    merged["content_samples"] = merge_sample_lists(
        merged.get("content_samples") or [],
        rendered_data.get("content_samples") or [],
        limit=40,
    )
    merged["work_urls"] = merge_url_lists(merged.get("work_urls") or [], rendered_data.get("work_urls") or [], limit=30)
    merged["identity"] = merge_identity(rendered_data.get("identity"), merged.get("identity"))
    return merged


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

    data = fetch_douyin_page(url)
    if data.get("status") != "ok":
        return data
    needs_rendered = not (
        data.get("profile_url")
        and (data.get("content_samples") or data.get("work_urls"))
        and any((data.get("identity") or {}).get(key) for key in ["nickname", "douyin_id", "avatar_url"])
    )
    if needs_rendered:
        data = merge_page_metadata(data, fetch_douyin_rendered_page(data.get("final_url") or url))

    main_final_url = data.get("final_url") or url
    profile_url = data.get("profile_url") or ""
    profile_samples = []
    related_samples = []
    related_pages = []
    profile_work_urls = []

    if profile_url:
        profile = fetch_douyin_page(profile_url, timeout=8, limit=DOUYIN_FETCH_LIMIT)
        if profile.get("status") == "ok" and not (profile.get("content_samples") or profile.get("work_urls")):
            profile = merge_page_metadata(profile, fetch_douyin_rendered_page(profile.get("final_url") or profile_url, timeout_ms=14000))
        data["profile_status"] = profile.get("status")
        data["profile_url"] = profile_url
        data["profile_final_url"] = profile.get("final_url", "")
        data["profile_message"] = profile.get("message", "")
        data["profile_identity"] = profile.get("identity") or {}
        profile_samples = profile.get("content_samples") or []
        profile_work_urls = profile.get("work_urls") or []

        main_key = main_final_url.split("?")[0]
        for work_url in profile_work_urls[:DOUYIN_PROFILE_SAMPLE_LIMIT]:
            if work_url.split("?")[0] == main_key:
                continue
            work = fetch_douyin_page(work_url, timeout=6, limit=900_000)
            page_samples = work.get("content_samples") or []
            related_pages.append(
                {
                    "url": work_url,
                    "status": work.get("status"),
                    "final_url": work.get("final_url", ""),
                    "identity": work.get("identity") or {},
                    "sample_count": len(page_samples),
                    "samples": page_samples[:5],
                    "message": work.get("message", ""),
                }
            )
            related_samples.extend(page_samples[:5])
            if len(related_samples) >= 24:
                break

    related_identities = [item.get("identity") for item in related_pages if item.get("identity")]
    account_identity = merge_identity(data.get("profile_identity"), data.get("identity"), *related_identities)
    if (data.get("identity") or {}).get("aweme_id"):
        account_identity["aweme_id"] = data["identity"]["aweme_id"]
    data["account_identity"] = account_identity
    data["profile_content_samples"] = profile_samples
    data["profile_work_urls"] = profile_work_urls[:20]
    data["related_work_pages"] = related_pages
    data["related_content_samples"] = related_samples[:30]
    data["discovery"] = {
        "input_url": url,
        "final_url": main_final_url,
        "profile_url": profile_url,
        "profile_status": data.get("profile_status", "not_found" if not profile_url else ""),
        "profile_sample_count": len(profile_samples),
        "profile_work_url_count": len(profile_work_urls),
        "related_page_count": len(related_pages),
        "related_sample_count": len(related_samples),
        "identity_fields": [key for key, value in (data.get("account_identity") or {}).items() if value],
    }
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
        "account_identity": meta.get("account_identity") or meta.get("identity") or {},
        "discovery": meta.get("discovery") or {},
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
        for sample in meta.get("profile_content_samples") or []:
            add(sample, "douyin_profile")
        for sample in meta.get("related_content_samples") or []:
            add(sample, "douyin_related_work")
        add(meta.get("og_title") or meta.get("title") or "", "douyin_meta")
        add(meta.get("og_description") or meta.get("description") or "", "douyin_meta")

    return samples[:40]


def keyword_hits(samples, keywords):
    text = "\n".join(item["text"] for item in samples).lower()
    compact = re.sub(r"\s+", "", text)
    return sum(1 for keyword in keywords if keyword.lower() in text or keyword in compact)


def custom_style_profile(tone):
    return {
        "name": "Custom Account Signal",
        "category": "custom",
        "categoryTitle": "自定义栏目",
        "categoryEn": "CUSTOM COLUMN",
        "categorySub": "主题 / 场景 / 业务线",
        "categoryColor": "#f5d76e",
        "imageStyle": "minimal",
        "imageDensity": "low",
        "imageTheme": "深色编辑感，真实工作场景，清晰留白，账号统一封面系统",
        "titleRule": "先找稳定标题句式，再固定栏目；样本不足时不要过早定死风格。",
        "backgroundRule": "背景只服务主题和气质，先保留留白，等样本增加后再提高识别度。",
        "coverRule": "先稳定标题层级、栏目色和安全区，再扩展更多背景变化。",
        "voiceRule": tone,
        "avoid": ["过早复杂化", "一条内容一个风格", "信息过满", "通用模板感"],
    }


def local_style_profile(ai_score, business_score, cognition_score, field_score, tone):
    if max(ai_score, business_score, cognition_score, field_score) == 0:
        return custom_style_profile(tone)
    if ai_score >= max(cognition_score, field_score, business_score):
        return {
            "name": "AI Command Editorial",
            "category": "ai",
            "categoryTitle": "AI下半场",
            "categoryEn": "AI SECOND HALF",
            "categorySub": "模型 / Agent / 商业重构",
            "categoryColor": "#b2ff52",
            "imageStyle": "terminal",
            "imageDensity": "medium",
            "imageTheme": "AI Agent，产品屏幕，代码终端，深夜办公室，商业判断，真实科技现场",
            "titleRule": "标题像判断句，不写泛泛趋势；优先使用“这不是X，是Y”“X正在重定价”。",
            "backgroundRule": "背景用真实屏幕、终端、产品界面局部或夜间工作台，不出现可读文字。",
            "coverRule": "左侧保留大标题安全区，右侧放屏幕光和场景深度，栏目色只做小信号。",
            "voiceRule": tone,
            "avoid": ["泛 AI 壁纸", "随机神经网络", "大面积科技渐变", "文字塞满背景"],
        }
    if field_score >= max(ai_score, cognition_score, business_score):
        return {
            "name": "Road Field Notes",
            "category": "road",
            "categoryTitle": "在路上",
            "categoryEn": "ON THE ROAD",
            "categorySub": "出差 / 客户 / 一线观察",
            "categoryColor": "#ff6052",
            "imageStyle": "field",
            "imageDensity": "medium",
            "imageTheme": "机场，车窗，城市夜景，客户现场，一线观察，真实出差现场，克制纪实感",
            "titleRule": "标题像现场笔记，优先写一线判断和反差，不写旅行流水账。",
            "backgroundRule": "背景选择路上、机场、酒店桌面、车窗、客户现场等真实场景，留出标题安全区。",
            "coverRule": "画面要有行动感，但文字区保持冷静干净，红色只做路线或信号点。",
            "voiceRule": tone,
            "avoid": ["旅行大片感", "游客视角", "过亮风景", "杂乱现场"],
        }
    if cognition_score >= max(ai_score, field_score, business_score):
        return {
            "name": "Strong Signal Editorial",
            "category": "strong",
            "categoryTitle": "强者恒强",
            "categoryEn": "THE STRONG GET STRONGER",
            "categorySub": "判断力 / 筹码 / 个体系统",
            "categoryColor": "#50d6ff",
            "imageStyle": "cinematic",
            "imageDensity": "low",
            "imageTheme": "强者恒强，深夜书桌，白板讨论，人物剪影，判断力，黑白编辑感，安静压迫感",
            "titleRule": "标题要像一句能被转述的判断，短、硬、有方向感。",
            "backgroundRule": "背景用深夜办公室、白板、桌面、谈判室或黑白人物剪影，避免励志海报感。",
            "coverRule": "大标题压住画面，英文副题克制，保留黑白编辑感和冷色高光。",
            "voiceRule": tone,
            "avoid": ["鸡汤海报", "夸张成功学符号", "金色财富感", "软口号"],
        }
    if business_score:
        return {
            "name": "Business Growth System",
            "category": "custom",
            "categoryTitle": "商业增长",
            "categoryEn": "BUSINESS GROWTH",
            "categorySub": "产品 / 客户 / 增长",
            "categoryColor": "#f5d76e",
            "imageStyle": "cinematic",
            "imageDensity": "medium",
            "imageTheme": "商业增长，产品会议，客户现场，市场图表，深夜办公室，真实商业决策",
            "titleRule": "标题围绕商业结果和决策代价，不写空泛方法论。",
            "backgroundRule": "背景用产品会议、客户讨论、市场看板、办公桌和真实业务现场。",
            "coverRule": "保持单一强标题，栏目名可自定义，颜色只做标识不做大面积铺色。",
            "voiceRule": tone,
            "avoid": ["企业宣传册感", "模板化商务握手", "PPT 图标堆叠", "过度金色"],
        }
    return custom_style_profile(tone)


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

    style_profile = local_style_profile(ai_score, business_score, cognition_score, field_score, tone)

    return {
        "status": "complete",
        "sample_count": len(samples),
        "min_required": DNA_MIN_SAMPLE_COUNT,
        "source_url": douyin_context.get("url", "") if douyin_context else "",
        "account_identity": douyin_context.get("account_identity", {}) if douyin_context else {},
        "discovery": douyin_context.get("discovery", {}) if douyin_context else {},
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
        "style_profile": style_profile,
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
- 必须额外输出一个可直接应用到页面控件的 style_profile；字段名必须稳定，不能只写自然语言建议。
- 如果 douyin_context.account_identity 里有昵称、抖音号、头像或主页链接，可以引用；没有抓到时不得编造。

只输出合法 JSON，不要 markdown，不要解释。JSON 结构：
{
  "status": "complete",
  "account_identity": {
    "nickname": "...",
    "douyin_id": "...",
    "short_id": "...",
    "avatar_url": "...",
    "profile_url": "..."
  },
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
  "style_profile": {
    "name": "...",
    "category": "ai|strong|road|custom",
    "categoryTitle": "...",
    "categoryEn": "...",
    "categorySub": "...",
    "categoryColor": "#b2ff52",
    "imageStyle": "cinematic|terminal|field|minimal",
    "imageDensity": "low|medium|high",
    "imageTheme": "...",
    "titleRule": "...",
    "backgroundRule": "...",
    "coverRule": "...",
    "voiceRule": "...",
    "avoid": ["..."]
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
    discovery = douyin_context.get("discovery", {}) if douyin_context else {}
    identity = douyin_context.get("account_identity", {}) if douyin_context else {}
    auto_note = ""
    if url:
        profile_url = discovery.get("profile_url") or identity.get("profile_url")
        related_count = discovery.get("related_sample_count", 0)
        profile_count = discovery.get("profile_sample_count", 0)
        if profile_url:
            auto_note = f"已自动尝试从作品链接追到作者主页，并抓取主页/相关作品样本：主页样本 {profile_count} 条，相关作品样本 {related_count} 条。"
        else:
            auto_note = "已自动尝试从作品链接解析作者主页、头像和抖音号，但当前页面没有暴露足够信息，可能被登录或反爬限制。"
    return {
        "status": "need_samples",
        "sample_count": len(samples),
        "min_required": DNA_MIN_SAMPLE_COUNT,
        "missing_count": max(0, DNA_MIN_SAMPLE_COUNT - len(samples)),
        "source_url": url,
        "reply": f"目前只拿到 {len(samples)} 条可用内容样本。{auto_note} 解码 DNA 至少需要 {DNA_MIN_SAMPLE_COUNT} 条公开作品样本，还差 {max(0, DNA_MIN_SAMPLE_COUNT - len(samples))} 条。",
        "account_identity": identity,
        "discovery": discovery,
        "collection_guide": [
            "只给 1 个作品链接时，系统会先自动找作者主页、头像、抖音号和其它公开作品。",
            "如果抖音页面受登录或反爬限制，发主页作品列表截图或复制作品标题。",
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
        "account_identity": douyin_context.get("account_identity", {}),
        "discovery": douyin_context.get("discovery", {}),
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
        dna.update({k: v for k, v in parsed.items() if k in {"account_identity", "client_dna", "style_signals", "style_profile", "design_directions", "operating_rules", "next_questions"}})
        dna["account_identity"] = merge_identity(douyin_context.get("account_identity", {}), parsed.get("account_identity", {}))
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
    wants_outro = current.get("template") == "outro" or any(
        token in template_source
        for token in ["片尾", "结尾", "视频结尾", "最后1秒", "最后2秒", "最后 1 秒", "最后 2 秒", "outro", "ending"]
    )
    wants_intro = current.get("template") == "intro" or any(
        token in template_source
        for token in ["片头", "动效", "视频开头", "前1秒", "前2秒", "1-2秒", "intro", "motion"]
    )
    template = "outro" if wants_outro else "intro" if wants_intro else "work"
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
        "reply": "我先按现有账号规则生成了一版封面/动效方案；LLM 未配置或不可用时会走本地判断。",
        "template": template,
        "category": category,
        "fields": {
            "categoryTitle": category_defaults[0],
            "categoryEn": category_defaults[1],
            "categorySub": category_defaults[2],
            "title": title,
            "enTitle": en_title,
            "summary": summary,
            "code": "END-01" if template == "outro" else "M-01" if template == "intro" else category_defaults[3],
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
- 输出形态：work=单条静态封面，collection=合集封面，profile=主页背景，intro=覆盖视频前 1-2 秒的片头动效，outro=视频最后 1-2 秒的片尾动效。
- 单条作品封面要服务点击：中文标题必须短、狠、好读，建议 2-8 个汉字一行，用 \\n 控制换行，最多 3 行。
- 片头动效也要服务点击：主干观点必须在 1-2 秒内大字出现，可以比静态封面更像开场 punchline。
- 片尾动效要服务关注和品牌记忆：用清晰 CTA 收束，如“关注我，看懂 AI 下半场 / KevPH2026”。
- 摘要是点击理由，不要流水账，控制在 12-28 个中文字符。
- 图片只做背景，不要把标题文字写进生成图里；标题由前端固定版式叠加。
- 如果用户提到“片头、动效、视频开头、覆盖前 1-2 秒、intro、motion”，优先选择 template=intro。
- 如果用户提到“片尾、结尾、视频结尾、最后 1-2 秒、outro、ending”，优先选择 template=outro。
- 如果用户只粘贴抖音分享文案或短链，优先使用 douyin_context.clean_without_tags、hashtags 和 douyin_meta 来判断主题；忽略复制口令、时间、随机码、"复制此链接" 这类噪声。
- 如果用户上传图片，你不能声称自己看到了图片细节；只把它作为生图参考图使用，并在 image.promptHints 中说明如何利用参考图的气质、颜色或场景。

只输出合法 JSON，不要 markdown，不要解释。JSON 结构：
{
  "reply": "给用户看的简短说明",
  "template": "work|collection|profile|intro|outro",
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

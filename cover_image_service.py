import json
import base64
import os
import urllib.error
import urllib.parse
import urllib.request


IMAGE_SIZES = {
    "work": "1024x1536",
    "collection": "1024x1024",
    "profile": "1536x1024",
}
DEFAULT_IMAGE_BASE = "https://api.openai.com/v1"


class ServiceError(Exception):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        super().__init__(payload.get("message", "service error"))


def trim(value, limit):
    return str(value or "").strip()[:limit]


def model_config(incoming, kind):
    config = incoming.get("model_config") if isinstance(incoming, dict) else {}
    config = config if isinstance(config, dict) else {}
    section = config.get(kind) if isinstance(config.get(kind), dict) else {}
    return {
        "endpoint": trim(section.get("endpoint"), 600),
        "model": trim(section.get("model"), 120),
        "api_key": trim(section.get("apiKey") or section.get("api_key"), 2000),
    }


def normalize_image_endpoint(endpoint, edit=False):
    raw = trim(endpoint, 600).rstrip("/")
    suffix = "edits" if edit else "generations"
    if not raw:
        return f"{DEFAULT_IMAGE_BASE}/images/{suffix}"
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ServiceError(400, {"error": "bad_model_endpoint", "message": "生图接口地址必须是 http/https URL。"})
    if raw.endswith("/images/generations") or raw.endswith("/images/edits"):
        if edit:
            return raw.replace("/images/generations", "/images/edits")
        return raw.replace("/images/edits", "/images/generations")
    if raw.endswith("/v1"):
        return f"{raw}/images/{suffix}"
    if raw.endswith("/images"):
        return f"{raw}/{suffix}"
    return raw


def post_json_url(url, payload, api_key, timeout=180):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise ServiceError(exc.code, {"error": "openai_error", "message": message})
    except Exception as exc:
        raise ServiceError(502, {"error": "generation_failed", "message": str(exc)})


def post_image_json(url, payload, api_key, timeout=180):
    try:
        return post_json_url(url, payload, api_key, timeout)
    except ServiceError as exc:
        if exc.status not in {400, 422}:
            raise
        slim = {
            key: value
            for key, value in payload.items()
            if key not in {"quality", "output_format", "input_fidelity"}
        }
        if slim == payload:
            raise
        return post_json_url(url, slim, api_key, timeout)


def is_image_data_url(value):
    text = str(value or "").strip()
    if len(text) > 7_500_000:
        return False
    return text.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,"))


def is_http_image_url(value):
    text = str(value or "").strip()
    parsed = urllib.parse.urlparse(text)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_references(incoming):
    images = []
    data_url = incoming.get("reference_image_data_url")
    image_url = incoming.get("reference_image_url")
    if is_image_data_url(data_url):
        images.append({"image_url": data_url})
    if is_http_image_url(image_url):
        images.append({"image_url": trim(image_url, 1200)})
    return images[:2]


def image_url_to_data_url(url):
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ServiceError(502, {"error": "bad_image_url", "message": "The image API returned an invalid image URL."})
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read(12_000_000)
            content_type = response.headers.get_content_type() or "image/png"
    except Exception as exc:
        raise ServiceError(502, {"error": "image_fetch_failed", "message": str(exc)})
    if not content_type.startswith("image/"):
        content_type = "image/png"
    return f"data:{content_type};base64,{base64.b64encode(body).decode('ascii')}"


def extract_image_data_url(result):
    try:
        item = result["data"][0]
    except Exception:
        raise ServiceError(502, {"error": "bad_openai_response", "message": "No image was returned."})
    if item.get("b64_json"):
        return f"data:image/png;base64,{item['b64_json']}"
    if item.get("url"):
        return image_url_to_data_url(item["url"])
    raise ServiceError(502, {"error": "bad_openai_response", "message": "No image data was returned."})


def generate_image(incoming):
    image_config = model_config(incoming, "image")
    has_custom_image = bool(image_config["endpoint"] or image_config["model"] or image_config["api_key"])
    api_key = image_config["api_key"] or os.environ.get("OPENAI_API_KEY")
    if not api_key and not has_custom_image:
        raise ServiceError(
            503,
            {
                "error": "missing_api_key",
                "message": "OPENAI_API_KEY is not set. The page can still use the local fallback generator.",
            },
        )

    prompt = trim(incoming.get("prompt"), 16000)
    template = trim(incoming.get("template") or "work", 24)
    if not prompt:
        raise ServiceError(400, {"error": "empty_prompt", "message": "Prompt is required."})

    model = image_config["model"] or os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
    size = IMAGE_SIZES.get(template, "1024x1536")
    quality = os.environ.get("OPENAI_IMAGE_QUALITY", "medium")
    references = build_references(incoming)
    common = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "output_format": "png",
    }

    endpoint = "images/generations"
    reference_used = False
    fallback_reason = ""
    generation_url = normalize_image_endpoint(image_config["endpoint"], edit=False)
    if references:
        edit_payload = dict(common)
        edit_payload["images"] = references
        edit_payload["input_fidelity"] = os.environ.get("OPENAI_IMAGE_INPUT_FIDELITY", "high")
        try:
            result = post_image_json(normalize_image_endpoint(image_config["endpoint"], edit=True), edit_payload, api_key)
            endpoint = "images/edits"
            reference_used = True
        except ServiceError as exc:
            if os.environ.get("OPENAI_IMAGE_FALLBACK_ON_EDIT_ERROR", "1") != "1":
                raise
            fallback_reason = exc.payload.get("message", str(exc))
            result = post_image_json(generation_url, common, api_key)
    else:
        result = post_image_json(generation_url, common, api_key)

    return {
        "image_data_url": extract_image_data_url(result),
        "prompt": prompt,
        "model": model,
        "size": size,
        "quality": quality,
        "endpoint": endpoint,
        "provider": "local-config" if has_custom_image else "openai-env",
        "reference_used": reference_used,
        "fallback_reason": fallback_reason,
        "usage": result.get("usage"),
    }

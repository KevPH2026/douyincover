import json
import os
import urllib.error
import urllib.parse
import urllib.request


IMAGE_SIZES = {
    "work": "1024x1536",
    "collection": "1024x1024",
    "profile": "1536x1024",
}


class ServiceError(Exception):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        super().__init__(payload.get("message", "service error"))


def trim(value, limit):
    return str(value or "").strip()[:limit]


def post_openai_json(path, payload, api_key, timeout=180):
    request = urllib.request.Request(
        f"https://api.openai.com/v1/{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
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


def extract_b64(result):
    try:
        return result["data"][0]["b64_json"]
    except Exception:
        raise ServiceError(502, {"error": "bad_openai_response", "message": "No image was returned."})


def generate_image(incoming):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
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

    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
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
    if references:
        edit_payload = dict(common)
        edit_payload["images"] = references
        edit_payload["input_fidelity"] = os.environ.get("OPENAI_IMAGE_INPUT_FIDELITY", "high")
        try:
            result = post_openai_json("images/edits", edit_payload, api_key)
            endpoint = "images/edits"
            reference_used = True
        except ServiceError as exc:
            if os.environ.get("OPENAI_IMAGE_FALLBACK_ON_EDIT_ERROR", "1") != "1":
                raise
            fallback_reason = exc.payload.get("message", str(exc))
            result = post_openai_json("images/generations", common, api_key)
    else:
        result = post_openai_json("images/generations", common, api_key)

    return {
        "image_data_url": f"data:image/png;base64,{extract_b64(result)}",
        "prompt": prompt,
        "model": model,
        "size": size,
        "quality": quality,
        "endpoint": endpoint,
        "reference_used": reference_used,
        "fallback_reason": fallback_reason,
        "usage": result.get("usage"),
    }

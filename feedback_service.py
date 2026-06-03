import json
import os
import secrets
import time
from pathlib import Path

from account_service import PREFIX
from account_service import ServiceError
from account_service import kv_get_json
from account_service import kv_set_json
from account_service import now_ms
from account_service import trim


MAX_FEEDBACK_ITEMS = 500
LOCAL_FEEDBACK_PATH = Path(os.environ.get("FEEDBACK_LOCAL_PATH") or ".codex-local/feedback.jsonl")


def feedback_index_key():
    return f"{PREFIX}:feedback:index"


def feedback_item_key(feedback_id):
    return f"{PREFIX}:feedback:{feedback_id}"


def clean_type(value):
    allowed = {"bug", "confusing", "idea", "output", "account", "other"}
    feedback_type = trim(value or "bug", 32)
    return feedback_type if feedback_type in allowed else "other"


def sanitize_context(context):
    source = context if isinstance(context, dict) else {}
    return {
        "page_url": trim(source.get("page_url"), 500),
        "template": trim(source.get("template"), 40),
        "category": trim(source.get("category"), 40),
        "title": trim(source.get("title"), 160),
        "en_title": trim(source.get("en_title"), 160),
        "summary": trim(source.get("summary"), 260),
        "code": trim(source.get("code"), 40),
        "image_style": trim(source.get("image_style"), 40),
        "image_density": trim(source.get("image_density"), 40),
        "viewport": trim(source.get("viewport"), 80),
        "storage_mode": trim(source.get("storage_mode"), 40),
        "user_email": trim(source.get("user_email"), 160),
    }


def sanitize_feedback(incoming, headers):
    message = trim(incoming.get("message"), 4000)
    if len(message) < 6:
        raise ServiceError(400, {"error": "missing_message", "message": "请至少写一句你遇到的问题。"})
    feedback_id = trim(incoming.get("id"), 80) or f"fb_{int(time.time())}_{secrets.token_hex(4)}"
    user_agent = trim(headers.get("user-agent") or headers.get("User-Agent") or incoming.get("user_agent"), 500)
    return {
        "id": feedback_id,
        "type": clean_type(incoming.get("type")),
        "message": message,
        "contact": trim(incoming.get("contact"), 180),
        "context": sanitize_context(incoming.get("context")),
        "user_agent": user_agent,
        "created_at": now_ms(),
        "source": "dna.superk.ai",
    }


def save_feedback_local(feedback):
    LOCAL_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCAL_FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(feedback, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {
        "ok": True,
        "feedback": feedback,
        "storage": "local",
        "path": str(LOCAL_FEEDBACK_PATH),
    }


def save_feedback_cloud(feedback):
    kv_set_json(feedback_item_key(feedback["id"]), feedback)
    index = kv_get_json(feedback_index_key(), []) or []
    index = [feedback["id"]] + [item for item in index if item != feedback["id"]]
    kv_set_json(feedback_index_key(), index[:MAX_FEEDBACK_ITEMS])
    return {"ok": True, "feedback": feedback, "storage": "cloud"}


def submit_feedback(incoming, headers):
    feedback = sanitize_feedback(incoming, headers)
    try:
        return save_feedback_cloud(feedback)
    except ServiceError as exc:
        if exc.payload.get("error") == "missing_storage" and not os.environ.get("VERCEL"):
            return save_feedback_local(feedback)
        raise


def handle_feedback(incoming, headers):
    action = trim(incoming.get("action") or "submit", 24)
    if action == "submit":
        return submit_feedback(incoming, headers)
    raise ServiceError(400, {"error": "bad_action", "message": "Unknown feedback action."})

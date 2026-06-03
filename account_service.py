import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request


PREFIX = os.environ.get("ACCOUNT_KV_PREFIX", "mrkcover")
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
MAX_ASSETS = 200


class ServiceError(Exception):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        super().__init__(payload.get("message", "service error"))


def trim(value, limit):
    return str(value or "").strip()[:limit]


def now_ms():
    return int(time.time() * 1000)


def kv_config():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        raise ServiceError(
            503,
            {
                "error": "missing_storage",
                "message": "KV_REST_API_URL and KV_REST_API_TOKEN are not set. The browser can use local storage fallback.",
            },
        )
    return url.rstrip("/"), token


def kv(command):
    url, token = kv_config()
    request = urllib.request.Request(
        url,
        data=json.dumps(command).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise ServiceError(exc.code, {"error": "kv_error", "message": message})
    except Exception as exc:
        raise ServiceError(502, {"error": "kv_failed", "message": str(exc)})
    if "error" in payload and payload["error"]:
        raise ServiceError(502, {"error": "kv_error", "message": str(payload["error"])})
    return payload.get("result")


def kv_get_json(key, default=None):
    result = kv(["GET", key])
    if result is None:
        return default
    if isinstance(result, (dict, list)):
        return result
    try:
        return json.loads(result)
    except Exception:
        return default


def kv_set_json(key, value, ttl=None):
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if ttl:
        return kv(["SET", key, encoded, "EX", int(ttl)])
    return kv(["SET", key, encoded])


def kv_delete(key):
    return kv(["DEL", key])


def normalize_email(email):
    return trim(email, 160).lower()


def public_user(user):
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name") or user["email"].split("@")[0],
        "created_at": user.get("created_at"),
    }


def password_digest(password, salt):
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return base64.b64encode(raw).decode("ascii")


def validate_credentials(email, password, registering=False):
    email = normalize_email(email)
    password = str(password or "")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ServiceError(400, {"error": "bad_email", "message": "请输入有效邮箱。"})
    if len(password) < 6:
        raise ServiceError(400, {"error": "weak_password", "message": "密码至少 6 位。"})
    if registering and len(password) > 128:
        raise ServiceError(400, {"error": "bad_password", "message": "密码过长。"})
    return email, password


def user_email_key(email):
    return f"{PREFIX}:user:email:{email}"


def user_id_key(user_id):
    return f"{PREFIX}:user:id:{user_id}"


def session_key(token):
    return f"{PREFIX}:session:{token}"


def asset_key(user_id, asset_id):
    return f"{PREFIX}:asset:{user_id}:{asset_id}"


def asset_index_key(user_id):
    return f"{PREFIX}:assets:{user_id}"


def create_session(user):
    token = secrets.token_urlsafe(32)
    kv_set_json(
        session_key(token),
        {
            "user_id": user["id"],
            "email": user["email"],
            "created_at": now_ms(),
        },
        SESSION_TTL_SECONDS,
    )
    return token


def auth_register(incoming):
    email, password = validate_credentials(incoming.get("email"), incoming.get("password"), True)
    if kv_get_json(user_email_key(email)):
        raise ServiceError(409, {"error": "email_exists", "message": "这个邮箱已经注册。"})

    user_id = secrets.token_hex(12)
    salt = secrets.token_hex(16)
    user = {
        "id": user_id,
        "email": email,
        "name": trim(incoming.get("name"), 48) or email.split("@")[0],
        "salt": salt,
        "password_hash": password_digest(password, salt),
        "created_at": now_ms(),
    }
    kv_set_json(user_email_key(email), user)
    kv_set_json(user_id_key(user_id), user)
    token = create_session(user)
    return {"token": token, "user": public_user(user), "storage": "cloud"}


def auth_login(incoming):
    email, password = validate_credentials(incoming.get("email"), incoming.get("password"))
    user = kv_get_json(user_email_key(email))
    if not user:
        raise ServiceError(401, {"error": "bad_login", "message": "邮箱或密码不正确。"})
    expected = password_digest(password, user["salt"])
    if not hmac.compare_digest(expected, user["password_hash"]):
        raise ServiceError(401, {"error": "bad_login", "message": "邮箱或密码不正确。"})
    token = create_session(user)
    return {"token": token, "user": public_user(user), "storage": "cloud"}


def token_from_headers(headers, incoming=None):
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    if incoming:
        return trim(incoming.get("token"), 512)
    return ""


def require_user(headers, incoming=None):
    token = token_from_headers(headers, incoming)
    if not token:
        raise ServiceError(401, {"error": "not_authenticated", "message": "请先登录。"})
    session = kv_get_json(session_key(token))
    if not session:
        raise ServiceError(401, {"error": "session_expired", "message": "登录已过期，请重新登录。"})
    user = kv_get_json(user_id_key(session["user_id"]))
    if not user:
        raise ServiceError(401, {"error": "user_missing", "message": "账号不存在。"})
    return user, token


def auth_me(headers, incoming):
    user, _ = require_user(headers, incoming)
    return {"user": public_user(user), "storage": "cloud"}


def auth_logout(headers, incoming):
    _, token = require_user(headers, incoming)
    kv_delete(session_key(token))
    return {"ok": True}


def handle_auth(incoming, headers):
    action = trim(incoming.get("action") or "me", 24)
    if action == "register":
        return auth_register(incoming)
    if action == "login":
        return auth_login(incoming)
    if action == "logout":
        return auth_logout(headers, incoming)
    if action == "me":
        return auth_me(headers, incoming)
    raise ServiceError(400, {"error": "bad_action", "message": "Unknown auth action."})


def sanitize_asset(asset):
    source = asset if isinstance(asset, dict) else {}
    created = source.get("created_at") or now_ms()
    asset_id = trim(source.get("id"), 80) or secrets.token_hex(10)
    title = trim(source.get("title") or source.get("name") or "未命名素材", 80)
    return {
        "id": asset_id,
        "title": title,
        "template": trim(source.get("template") or "work", 24),
        "category": trim(source.get("category") or "ai", 24),
        "code": trim(source.get("code"), 32),
        "summary": trim(source.get("summary"), 160),
        "thumbnail": trim(source.get("thumbnail"), 900_000),
        "render_data_url": trim(source.get("render_data_url"), 1_600_000),
        "editable": source.get("editable") if isinstance(source.get("editable"), dict) else {},
        "source": source.get("source") if isinstance(source.get("source"), dict) else {},
        "created_at": created,
        "updated_at": now_ms(),
    }


def list_assets(headers, incoming=None):
    user, _ = require_user(headers, incoming)
    index = kv_get_json(asset_index_key(user["id"]), []) or []
    assets = []
    for asset_id in index[:MAX_ASSETS]:
        item = kv_get_json(asset_key(user["id"], asset_id))
        if item:
            assets.append(item)
    return {"assets": assets, "storage": "cloud"}


def save_asset(headers, incoming):
    user, _ = require_user(headers, incoming)
    asset = sanitize_asset(incoming.get("asset"))
    kv_set_json(asset_key(user["id"], asset["id"]), asset)
    index = kv_get_json(asset_index_key(user["id"]), []) or []
    index = [asset["id"]] + [item for item in index if item != asset["id"]]
    index = index[:MAX_ASSETS]
    kv_set_json(asset_index_key(user["id"]), index)
    return {"asset": asset, "assets": list_assets(headers, incoming)["assets"], "storage": "cloud"}


def delete_asset(headers, incoming):
    user, _ = require_user(headers, incoming)
    asset_id = trim(incoming.get("id"), 80)
    if not asset_id:
        raise ServiceError(400, {"error": "missing_id", "message": "Missing asset id."})
    kv_delete(asset_key(user["id"], asset_id))
    index = kv_get_json(asset_index_key(user["id"]), []) or []
    index = [item for item in index if item != asset_id]
    kv_set_json(asset_index_key(user["id"]), index)
    return {"assets": list_assets(headers, incoming)["assets"], "storage": "cloud"}


def handle_assets(incoming, headers):
    action = trim(incoming.get("action") or "list", 24)
    if action == "list":
        return list_assets(headers, incoming)
    if action == "save":
        return save_asset(headers, incoming)
    if action == "delete":
        return delete_asset(headers, incoming)
    raise ServiceError(400, {"error": "bad_action", "message": "Unknown assets action."})

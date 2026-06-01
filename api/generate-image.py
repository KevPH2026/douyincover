import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler


IMAGE_SIZES = {
    "work": "1024x1536",
    "collection": "1024x1024",
    "profile": "1536x1024",
}


class handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self._json(
                503,
                {
                    "error": "missing_api_key",
                    "message": "OPENAI_API_KEY is not set. The page can still use the local fallback generator.",
                },
            )
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            incoming = json.loads(body.decode("utf-8"))
        except Exception:
            self._json(400, {"error": "bad_request", "message": "Invalid JSON request."})
            return

        prompt = str(incoming.get("prompt", "")).strip()
        template = str(incoming.get("template", "work")).strip()
        if not prompt:
            self._json(400, {"error": "empty_prompt", "message": "Prompt is required."})
            return

        payload = {
            "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1.5"),
            "prompt": prompt[:12000],
            "n": 1,
            "size": IMAGE_SIZES.get(template, "1024x1536"),
            "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
            "output_format": "png",
        }

        request = urllib.request.Request(
            "https://api.openai.com/v1/images/generations",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            self._json(exc.code, {"error": "openai_error", "message": message})
            return
        except Exception as exc:
            self._json(502, {"error": "generation_failed", "message": str(exc)})
            return

        try:
            b64 = result["data"][0]["b64_json"]
        except Exception:
            self._json(502, {"error": "bad_openai_response", "message": "No image was returned."})
            return

        self._json(
            200,
            {
                "image_data_url": f"data:image/png;base64,{b64}",
                "prompt": prompt,
                "model": payload["model"],
                "size": payload["size"],
                "quality": payload["quality"],
                "usage": result.get("usage"),
            },
        )

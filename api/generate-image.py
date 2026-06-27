import json
from http.server import BaseHTTPRequestHandler

from cover_image_service import ServiceError, generate_image


class handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            incoming = json.loads(body.decode("utf-8"))
        except Exception:
            self._json(400, {"error": "bad_request", "message": "Invalid JSON request."})
            return

        try:
            self._json(200, generate_image(incoming))
        except ServiceError as exc:
            if exc.payload.get("error") == "missing_api_key":
                self._json(200, {**exc.payload, "fallback": True})
                return
            self._json(exc.status, exc.payload)

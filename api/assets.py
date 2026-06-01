import json
from http.server import BaseHTTPRequestHandler

from account_service import ServiceError, handle_assets, list_assets


class handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8"))

    def do_GET(self):
        try:
            self._json(200, list_assets(self.headers))
        except ServiceError as exc:
            self._json(exc.status, exc.payload)

    def do_POST(self):
        try:
            incoming = self._read_json()
        except Exception:
            self._json(400, {"error": "bad_request", "message": "Invalid JSON request."})
            return

        try:
            self._json(200, handle_assets(incoming, self.headers))
        except ServiceError as exc:
            self._json(exc.status, exc.payload)

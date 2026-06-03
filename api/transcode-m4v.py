import json
from http.server import BaseHTTPRequestHandler

from motion_export_service import MotionExportError
from motion_export_service import transcode_m4v


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
            self._json(200, transcode_m4v(incoming))
        except MotionExportError as exc:
            self._json(exc.status, exc.payload)

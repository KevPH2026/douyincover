#!/usr/bin/env python3
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from cover_agent_service import create_cover_plan
from cover_image_service import ServiceError as ImageServiceError
from cover_image_service import generate_image


class CoverStudioHandler(SimpleHTTPRequestHandler):
    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            return json.loads(body.decode("utf-8"))
        except Exception:
            raise ValueError("Invalid JSON request.")

    def do_POST(self):
        if self.path == "/api/generate-image":
            try:
                self._json(200, generate_image(self._read_json()))
            except ValueError as exc:
                self._json(400, {"error": "bad_request", "message": str(exc)})
            except ImageServiceError as exc:
                self._json(exc.status, exc.payload)
            return

        if self.path == "/api/cover-agent":
            try:
                self._json(200, create_cover_plan(self._read_json()))
            except ValueError as exc:
                self._json(400, {"error": "bad_request", "message": str(exc)})
            except Exception as exc:
                self._json(502, {"error": "agent_failed", "message": str(exc)})
            return

        self._json(404, {"error": "not_found", "message": "Unknown API endpoint."})


def main():
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), CoverStudioHandler)
    print(f"Mr.K Cover Studio running at http://127.0.0.1:{port}/mrk-cover-studio.html", flush=True)
    print("Set DEEPSEEK_API_KEY and OPENAI_API_KEY to enable the full agent workflow.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)


if __name__ == "__main__":
    main()

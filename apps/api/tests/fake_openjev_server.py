"""HTTP fake of the OpenJev server for the E2E stack: `python -m tests.fake_openjev_server PORT`.

Scenario: strong fit, a stated mandatory language the candidate does not meet (blocker) and a
stated years-of-experience requirement that is met.
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.fake_openjev import FakeOpenJev

FAKE = FakeOpenJev(
    scores={"dim_skills": 3.6, "dim_experience": 3.2, "dim_role": 4.0, "dim_domain": 2.0},
    yes={
        "req_language_stated": 0.96,
        "req_language_met": 0.02,
        "req_years_experience_stated": 0.9,
        "req_years_experience_met": 0.88,
    },
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def _send(self, status: int, payload: object) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/v1/version":
            self._send(200, FAKE.version)
        else:
            self._send(404, {"error": {"code": 404, "message": "GET /v1/version"}})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        time.sleep(1.5)  # long enough for the UI to show the running state
        self._send(200, FAKE.answer(body))


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()

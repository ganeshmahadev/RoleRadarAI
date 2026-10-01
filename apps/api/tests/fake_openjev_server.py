"""HTTP fake of the OpenJev server for the E2E stack: `python -m tests.fake_openjev_server PORT`.

Default scenario: strong fit, a stated mandatory language the candidate does not meet (blocker)
and a stated years-of-experience requirement that is met.

Marker scenario (for ranking tests): a vacancy containing `FAKE_LEVEL=<0..4>` gets that level on
every dimension and no stated requirements, plus a failed mandatory language if it also contains
`FAKE_BLOCK`.
"""

import json
import re
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


LEVEL = re.compile(r"FAKE_LEVEL=([0-4](?:\.\d+)?)")


def answer(body: dict[str, object]) -> dict[str, object]:
    state = str(body.get("state", ""))
    marker = LEVEL.search(state)
    if marker is None:
        return FAKE.answer(body)
    blocked = "FAKE_BLOCK" in state
    fake = FakeOpenJev(
        default_score=float(marker.group(1)),
        default_yes=0.05,
        yes={"req_language_stated": 0.95, "req_language_met": 0.03} if blocked else {},
    )
    return fake.answer(body)


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
        self._send(200, answer(body))


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()

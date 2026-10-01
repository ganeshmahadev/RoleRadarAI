"""Deterministic stand-in for the OpenJev server (same wire format as shim.py@81a22f1b)."""

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

VERSION = {
    "model_dir": "openjev-MLX-4bit",
    "T": 0.85,
    "noul_t": 1.829074,
    "noul_bias": 0.0,
    "flags": {"perms": 1, "targeted": True},
    "shim_file": "shim.py",
    "shim_sha256": "81a22f1b1b8912a465059207ef9f60b7c6c16b4de6372305d867efbe38a1987a",
}


@dataclass
class FakeOpenJev:
    """`scores` / `yes` map question ids to answers; anything else gets the defaults."""

    scores: dict[str, float] = field(default_factory=dict)
    yes: dict[str, float] = field(default_factory=dict)
    default_score: float = 3.0
    default_yes: float = 0.1
    version: dict[str, Any] = field(default_factory=lambda: dict(VERSION))
    fail_with: int | None = None
    requests: list[dict[str, Any]] = field(default_factory=list)

    def answer(self, body: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(body)
        answers: dict[str, Any] = {}
        for qid, q in body["questions"].items():
            if q["type"] == "score":
                levels = q["criteria"]
                value = self.scores.get(qid, self.default_score)
                answers[qid] = {
                    "type": "score",
                    "score": value,
                    "legend": {str(i): lvl for i, lvl in enumerate(levels)},
                    "probabilities": {
                        str(i): 1.0 if i == round(value) else 0.0 for i in range(len(levels))
                    },
                    "confidence": 0.8,
                }
            else:
                answers[qid] = {"type": "noul", "noul": self.yes.get(qid, self.default_yes)}
        return {
            "id": "shim-test",
            "model": "openjev-MLX-4bit T=0.85 shim=shim.py@81a22f1b1b89",
            "answers": answers,
            "usage": {"input_tokens": 1234, "output_tokens": 0},
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail_with:
            return httpx.Response(self.fail_with, json={"error": {"code": self.fail_with}})
        if request.method == "GET" and request.url.path == "/v1/version":
            return httpx.Response(200, json=self.version)
        if request.method == "POST" and request.url.path == "/v1/systemone":
            return httpx.Response(200, json=self.answer(json.loads(request.content)))
        return httpx.Response(404, json={"error": {"code": 404, "message": "GET /v1/version"}})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

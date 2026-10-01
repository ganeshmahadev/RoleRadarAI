"""Offline EURES API built from the sanitized fixtures (shapes confirmed by the user, OD-7).

- search for a term, or for "Example Vision ApS": the fixture result list (3 hits, 2 of them the
  same vacancy in two languages);
- search for "Blocked*": HTTP 429; any other company: no results;
- detail: the fixture detail; its employer (legalID 12345678) is swapped for the search hit's
  employer, without a legalID, when the id belongs to another employer.
"""

import json
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "eures"
EMPTY = {"numberRecords": 0, "jvs": []}


def handler(requests: list[httpx.Request] | None = None) -> httpx.MockTransport:
    search = json.loads((FIXTURES / "search.json").read_text())
    detail = json.loads((FIXTURES / "detail.json").read_text())
    employers = {jv["id"]: jv["employer"]["name"] for jv in search["jvs"]}

    def handle(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        if request.url.path.endswith("/jv-search/search"):
            keyword = json.loads(request.content)["keywords"][0]["keyword"]
            if keyword.startswith("Blocked"):
                return httpx.Response(429, text="Too Many Requests")
            known = keyword == "Example Vision ApS" or "Engineer" in keyword
            return httpx.Response(200, json=search if known else EMPTY)
        if "/jv/id/" in request.url.path:
            job_id = request.url.path.rsplit("/", 1)[-1]
            employer = employers.get(job_id, "Example Vision ApS")
            body = json.loads(json.dumps(detail))
            profile = next(iter(body["jvProfiles"].values()))
            if employer != profile["employer"]["name"]:
                profile["employer"].update(name=employer, legalID=None)
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    return httpx.MockTransport(handle)

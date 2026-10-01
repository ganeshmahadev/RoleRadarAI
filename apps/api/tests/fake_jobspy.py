"""Deterministic stand-in for JobSpy (same row shape as `scrape_jobs(...).to_dict("records")`).

Per search term T it returns, for the requested site:
- "Senior T" at 3Shape A/S (a SIRI company in the seed) — on Indeed and LinkedIn with different
  text, to exercise cross-board dedup;
- "Lead T" on Google (FAKE_LEVEL marker for the fake OpenJev);
- "Office Manager" on Indeed (filtered out as not relevant);
- one row without a description (skipped).
"""

from datetime import date
from typing import Any


class FakeJobSpyClient:
    def __init__(
        self, fail_site: str | None = None, error: str = "HTTP 429 Too Many Requests"
    ) -> None:
        self.fail_site = fail_site
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def scrape(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.calls.append(params)
        site = params["site_name"][0]
        term = params["search_term"]
        if site == self.fail_site:
            raise RuntimeError(self.error)
        slug = term.lower().replace(" ", "-")
        body = (
            f"<p>We are hiring a {term} to build production ML systems with Python and PyTorch.</p>"
            "<ul><li>3+ years of experience</li><li>English required</li></ul>"
        )
        rows: list[dict[str, Any]] = []
        if site in ("indeed", "linkedin"):
            rows.append(
                {
                    "id": f"{site}-{slug}-1",
                    "site": site,
                    "job_url": f"https://{site}.example.test/jobs/{slug}-1",
                    "job_url_direct": "https://careers.3shape.example.test/jobs/1",
                    "title": f"Senior {term}",
                    "company": "3Shape A/S",
                    "location": "Copenhagen, Capital Region, DK",
                    "date_posted": date(2026, 10, 1),
                    "job_type": "fulltime",
                    "is_remote": False,
                    "description": body + f"<p>Posted on {site}. FAKE_LEVEL=3.6</p>",
                }
            )
        if site == "indeed":
            rows.append(
                {
                    "id": "indeed-office-1",
                    "site": site,
                    "job_url": "https://indeed.example.test/jobs/office-manager-1",
                    "title": "Office Manager",
                    "company": "Example Office ApS",
                    "location": "Aarhus, DK",
                    "description": (
                        "<p>Run our office, coordinate facilities and suppliers for 40 staff."
                        " FAKE_LEVEL=4.0</p>"
                    ),
                }
            )
            rows.append(
                {
                    "id": "indeed-empty",
                    "site": site,
                    "job_url": "https://indeed.example.test/x",
                    "title": "No text",
                    "description": None,
                }
            )
        if site == "google":
            rows.append(
                {
                    "id": f"google-{slug}-1",
                    "site": site,
                    "job_url": f"https://google.example.test/jobs/{slug}-lead",
                    "title": f"Lead {term}",
                    "company": "Unknown Startup ApS",
                    "location": "Odense, DK",
                    "date_posted": "2026-09-30",
                    "description": body + "<p>Leadership role. FAKE_LEVEL=2.8</p>",
                }
            )
        return rows

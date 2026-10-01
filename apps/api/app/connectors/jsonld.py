"""schema.org JobPosting extraction from JSON-LD (PRD §26 priority 2)."""

import json
import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from app.connectors.parse import first_str, parse_datetime
from app.connectors.text import clean_text, html_to_text

_COMMENT = re.compile(r"^\s*(<!--|<!\[CDATA\[)|(-->|\]\]>)\s*$")


def _types(node: dict[str, Any]) -> list[str]:
    value = node.get("@type")
    values = value if isinstance(value, list) else [value]
    return [v.rsplit("/", 1)[-1] for v in values if isinstance(v, str)]


def _walk(node: object) -> list[dict[str, Any]]:
    if isinstance(node, list):
        return [found for item in node for found in _walk(item)]
    if not isinstance(node, dict):
        return []
    found = [node] if "JobPosting" in _types(node) else []
    graph = node.get("@graph")
    if graph is not None:
        found.extend(_walk(graph))
    return found


def find_job_postings(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    postings: list[dict[str, Any]] = []
    for script in soup.find_all("script"):
        kind = str(script.get("type") or "").strip().lower()
        if kind != "application/ld+json":
            continue
        raw = _COMMENT.sub("", script.string or script.get_text() or "")
        try:
            data = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            continue
        postings.extend(_walk(data))
    return postings


@dataclass(frozen=True)
class JsonLdFields:
    title: str | None
    description: str
    employer_name: str | None
    location: str | None
    country: str | None
    city: str | None
    employment_type: str | None
    workplace_type: str | None
    apply_url: str | None
    external_id: str | None
    published_at: Any
    expires_at: Any


def _name(value: object) -> str | None:
    if isinstance(value, dict):
        return clean_text(value.get("name"))
    return clean_text(value)


def _places(posting: dict[str, Any]) -> list[tuple[str | None, str | None, str | None]]:
    locations = posting.get("jobLocation")
    items = locations if isinstance(locations, list) else [locations]
    places: list[tuple[str | None, str | None, str | None]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        address = item.get("address")
        if isinstance(address, str):
            places.append((clean_text(address), None, None))
            continue
        if not isinstance(address, dict):
            continue
        city = clean_text(address.get("addressLocality"))
        region = clean_text(address.get("addressRegion"))
        country = _name(address.get("addressCountry"))
        places.append((city, region, country))
    return places


def extract_fields(posting: dict[str, Any]) -> JsonLdFields:
    places = _places(posting)
    labels = []
    for city, region, country in places:
        label = ", ".join(part for part in (city, region, country) if part)
        if label and label not in labels:
            labels.append(label)
    city = places[0][0] if places else None
    country = places[0][2] if places else None

    employment = posting.get("employmentType")
    if isinstance(employment, list):
        employment = ", ".join(e for e in employment if isinstance(e, str))
    location_type = str(posting.get("jobLocationType") or "").upper()

    identifier = posting.get("identifier")
    external_id = (
        first_str(identifier.get("value"))
        if isinstance(identifier, dict)
        else first_str(identifier)
        if isinstance(identifier, str)
        else None
    )
    description = posting.get("description")
    return JsonLdFields(
        title=clean_text(posting.get("title")),
        description=html_to_text(description, unescape_first="&lt;" in description)
        if isinstance(description, str)
        else "",
        employer_name=_name(posting.get("hiringOrganization")),
        location=" / ".join(labels) or None,
        country=country,
        city=city,
        employment_type=clean_text(employment),
        workplace_type="remote" if location_type == "TELECOMMUTE" else None,
        apply_url=first_str(posting.get("url")),
        external_id=external_id,
        published_at=parse_datetime(posting.get("datePosted")),
        expires_at=parse_datetime(posting.get("validThrough")),
    )

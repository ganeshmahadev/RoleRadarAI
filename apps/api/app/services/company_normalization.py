"""Deterministic company-name normalization and EURES search-URL generation.

Both reproduce the seed workbook exactly (verified for all 982 rows in tests).
"""

import re
import unicodedata
from urllib.parse import quote_plus

# Danish/Nordic legal-form suffixes stripped from the end of the official name.
_LEGAL_SUFFIX = re.compile(
    r"[\s.,]*\b(a/s|aps|p/s|i/s|k/s|s/i|amba|a\.m\.b\.a\.|smba)\.?\s*$", re.IGNORECASE
)
_NON_NAME_CHARS = re.compile(r"[^\w&+]+")
_WHITESPACE = re.compile(r"\s+")

EURES_SEARCH_URL_TEMPLATE = (
    "https://europa.eu/eures/portal/jv-se/search?page=1&resultsPerPage=50&orderBy=BEST_MATCH"
    "&locationCodes=dk&keywordsEverywhere={query}&publicationPeriod=LAST_MONTH"
    "&previousPageType=findJob&lang=en"
)


def normalize_company_name(name: str) -> str:
    """Lowercase, legal suffix removed, accents folded (å→a; ø/æ kept), punctuation → space."""
    stripped = _LEGAL_SUFFIX.sub("", name).strip()
    decomposed = unicodedata.normalize("NFKD", stripped)
    folded = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()
    return _WHITESPACE.sub(" ", _NON_NAME_CHARS.sub(" ", folded)).strip()


def build_eures_search_url(company_name: str) -> str:
    """Company-specific EURES Denmark search (PRD §8). Navigation URL only; never fetched."""
    return EURES_SEARCH_URL_TEMPLATE.format(query=quote_plus(company_name))

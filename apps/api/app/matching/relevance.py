"""Cheap relevance filter (PRD §28 step 1): only relevant titles are sent to OpenJev.

A job is relevant when every word of at least one of the profile's target roles appears in the
job title (normalized: lowercase, accents folded, punctuation removed). Users control recall by
listing title variants as target roles (e.g. "ML Engineer" and "Machine Learning Engineer").
No synonyms are invented.
"""

from app.services.company_normalization import normalize_text

# Joining words that carry no meaning in a title (English and Danish).
_STOPWORDS = frozenset(
    {"a", "an", "and", "the", "of", "for", "in", "to", "with", "&", "og", "i", "af", "til"}
)


def title_tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in normalize_text(text).split() if t not in _STOPWORDS)


def matching_role(title: str, target_roles: list[str]) -> str | None:
    """The first target role whose words all appear in the title, or None."""
    words = title_tokens(title)
    for role in target_roles:
        needed = title_tokens(role)
        if needed and needed <= words:
            return role
    return None

import pytest

from app.matching.relevance import matching_role

ROLES = ["Machine Learning Engineer", "ML Engineer", "Data Scientist"]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Machine Learning Engineer", "Machine Learning Engineer"),
        ("Machine-Learning Engineer (Copenhagen)", "Machine Learning Engineer"),
        ("Engineer, Machine Learning", "Machine Learning Engineer"),  # word order is free
        ("Lead ML Engineer", "ML Engineer"),
        ("Data Scientist & Analyst", "Data Scientist"),
        ("Data Scíentist", "Data Scientist"),  # accents folded
        ("Data Engineer", None),
        ("Machine Operator", None),
        ("Office Manager", None),
        ("", None),
    ],
)
def test_matching_role(title: str, expected: str | None) -> None:
    assert matching_role(title, ROLES) == expected


def test_stopwords_and_empty_roles_are_ignored() -> None:
    assert matching_role("Head of Data Science", ["Head of Data Science"]) == "Head of Data Science"
    assert matching_role("Head Data Science", ["Head of Data Science"]) == "Head of Data Science"
    assert matching_role("Anything", ["", "  ", "of the"]) is None
    assert matching_role("Udvikler og arkitekt", ["Udvikler"]) == "Udvikler"

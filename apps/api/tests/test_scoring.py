import math

import pytest

from app.matching.rubric import RUBRIC_V1 as R
from app.matching.scoring import (
    BLOCKED,
    Classification,
    RequirementStatus,
    band,
    dimension_score,
    evaluate,
    label_requirement,
    met_id,
    phase_one_questions,
    phase_two_questions,
    stated_id,
)
from app.providers.decision import ScoreQuestion

ALL_DIMS = {d.key: 4.0 for d in R.dimensions}
NONE_STATED = {r.key: 0.1 for r in R.hard_requirements}


def test_rubric_weights_sum_to_one_and_keys_are_unique() -> None:
    assert math.isclose(R.total_weight(), 1.0)
    keys = [d.key for d in R.dimensions] + [r.key for r in R.hard_requirements]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize(("level", "expected"), [(0, 0), (2, 50), (3.7, 92.5), (4, 100), (5, 100)])
def test_dimension_score_is_level_over_four(level: float, expected: float) -> None:
    assert dimension_score(R, level) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("p", "status"),
    [
        (0.76, RequirementStatus.MET),
        (0.75, RequirementStatus.PARTIAL),  # boundaries are PARTIAL (decision 2026-10-02)
        (0.60, RequirementStatus.PARTIAL),
        (0.50, RequirementStatus.PARTIAL),
        (0.4999, RequirementStatus.NOT_MET),
        (0.012, RequirementStatus.NOT_MET),
    ],
)
def test_requirement_thresholds(p: float, status: RequirementStatus) -> None:
    assert label_requirement(R, p) is status


@pytest.mark.parametrize(
    ("score", "category"),
    [
        (100, "STRONG"),
        (84.6, "STRONG"),
        (84.4, "GOOD"),
        (70, "GOOD"),
        (69.4, "STRETCH"),
        (55, "STRETCH"),
        (54.4, "LOW"),
        (0, "LOW"),
    ],
)
def test_bands_use_the_rounded_score(score: float, category: str) -> None:
    assert band(R, score) == category


def test_no_stated_requirements_rescales_weights() -> None:
    levels = {**ALL_DIMS, "skills": 2.0}  # skills 50, the rest 100
    outcome = evaluate(R, dimension_levels=levels, stated=NONE_STATED, met={})
    assert outcome.must_have is None
    # (0.25*50 + 0.45*100) / 0.70
    assert outcome.overall_score == pytest.approx(round((0.25 * 50 + 0.45 * 100) / 0.70, 1))
    assert all(r.status is RequirementStatus.UNKNOWN for r in outcome.requirements)
    assert all(r.classification is Classification.INFORMATIONAL for r in outcome.requirements)
    assert outcome.category == "GOOD"  # 82.1


def test_must_have_is_average_of_stated_met_probabilities() -> None:
    stated = {**NONE_STATED, "language": 0.9, "years_experience": 0.8}
    met = {"language": 0.9, "years_experience": 0.7}
    outcome = evaluate(R, dimension_levels=ALL_DIMS, stated=stated, met=met)
    assert outcome.must_have == pytest.approx(80.0)
    assert outcome.overall_score == pytest.approx(round(0.30 * 80 + 0.70 * 100, 1))
    assert outcome.matched == ["Mandatory language"]
    assert outcome.partial == ["Minimum years of experience"]
    assert outcome.missing == []
    assert outcome.hard_blocker is False
    assert outcome.category == "STRONG"  # 94


def test_not_met_requirement_blocks_but_keeps_the_score() -> None:
    stated = {**NONE_STATED, "language": 0.97}
    outcome = evaluate(R, dimension_levels=ALL_DIMS, stated=stated, met={"language": 0.012})
    language = next(r for r in outcome.requirements if r.key == "language")
    assert language.status is RequirementStatus.NOT_MET
    assert language.classification is Classification.BLOCKER
    assert outcome.hard_blocker is True
    assert outcome.category == BLOCKED
    assert outcome.missing == ["Mandatory language"]
    assert outcome.overall_score == pytest.approx(
        round(0.30 * 1.2 + 0.70 * 100, 1)
    )  # unchanged formula


def test_question_sets() -> None:
    one = phase_one_questions(R)
    assert set(one) == {f"dim_{d.key}" for d in R.dimensions} | {
        stated_id(r.key) for r in R.hard_requirements
    }
    assert one["dim_skills"].type == "score"
    skills = one["dim_skills"]
    assert isinstance(skills, ScoreQuestion) and skills.criteria == list(R.levels)
    assert one[stated_id("language")].type == "noul"
    two = phase_two_questions(R, ["language", "licence"])
    assert set(two) == {met_id("language"), met_id("licence")}
    assert phase_two_questions(R, []) == {}

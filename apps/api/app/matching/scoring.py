"""Deterministic scoring for rubric_v1 (PRD §18, §19, §21). No I/O, no model calls."""

from dataclasses import dataclass, field
from enum import StrEnum

from app.matching.rubric import Rubric
from app.providers.decision import Question, ScoreQuestion, YesNoQuestion


class RequirementStatus(StrEnum):
    MET = "MET"
    PARTIAL = "PARTIAL"
    NOT_MET = "NOT_MET"
    UNKNOWN = "UNKNOWN"  # not stated by the vacancy: not scored


class Classification(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"
    INFORMATIONAL = "informational"
    NONE = "none"


BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class RequirementResult:
    key: str
    label: str
    stated_probability: float
    met_probability: float | None
    status: RequirementStatus
    classification: Classification


@dataclass(frozen=True)
class MatchOutcome:
    dimensions: dict[str, float]  # key → 0..100
    must_have: float | None  # 0..100, None when the vacancy states no hard requirement
    requirements: list[RequirementResult]
    overall_score: float  # 0..100, one decimal
    category: str
    hard_blocker: bool
    matched: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def dim_id(key: str) -> str:
    return f"dim_{key}"


def stated_id(key: str) -> str:
    return f"req_{key}_stated"


def met_id(key: str) -> str:
    return f"req_{key}_met"


def phase_one_questions(rubric: Rubric) -> dict[str, Question]:
    """Every dimension score plus "is this hard requirement stated?" for each type."""
    questions: dict[str, Question] = {
        dim_id(d.key): ScoreQuestion(instructions=d.instructions, criteria=list(rubric.levels))
        for d in rubric.dimensions
    }
    for req in rubric.hard_requirements:
        questions[stated_id(req.key)] = YesNoQuestion(instructions=req.stated_question)
    return questions


def phase_two_questions(rubric: Rubric, stated_keys: list[str]) -> dict[str, Question]:
    """ "Does the candidate meet it?" only for requirements the vacancy states."""
    return {
        met_id(r.key): YesNoQuestion(instructions=r.met_question)
        for r in rubric.hard_requirements
        if r.key in stated_keys
    }


def is_stated(rubric: Rubric, probability: float) -> bool:
    return probability > rubric.stated_threshold


def dimension_score(rubric: Rubric, expected_level: float) -> float:
    top = len(rubric.levels) - 1
    return max(0.0, min(100.0, expected_level / top * 100))


def label_requirement(rubric: Rubric, met_probability: float) -> RequirementStatus:
    if met_probability > rubric.met_threshold:
        return RequirementStatus.MET
    if met_probability >= rubric.partial_threshold:
        return RequirementStatus.PARTIAL
    return RequirementStatus.NOT_MET


_CLASSIFICATION = {
    RequirementStatus.MET: Classification.NONE,
    RequirementStatus.PARTIAL: Classification.WARNING,
    RequirementStatus.NOT_MET: Classification.BLOCKER,
    RequirementStatus.UNKNOWN: Classification.INFORMATIONAL,
}


def band(rubric: Rubric, score: float) -> str:
    rounded = round(score)
    return next(name for minimum, name in rubric.bands if rounded >= minimum)


def evaluate(
    rubric: Rubric,
    *,
    dimension_levels: dict[str, float],
    stated: dict[str, float],
    met: dict[str, float],
) -> MatchOutcome:
    dimensions = {
        d.key: dimension_score(rubric, dimension_levels[d.key]) for d in rubric.dimensions
    }

    requirements: list[RequirementResult] = []
    for req in rubric.hard_requirements:
        p_stated = stated[req.key]
        if is_stated(rubric, p_stated):
            p_met = met[req.key]
            status = label_requirement(rubric, p_met)
        else:
            p_met, status = None, RequirementStatus.UNKNOWN
        requirements.append(
            RequirementResult(req.key, req.label, p_stated, p_met, status, _CLASSIFICATION[status])
        )

    scored = [r.met_probability for r in requirements if r.met_probability is not None]
    must_have = sum(scored) / len(scored) * 100 if scored else None

    weighted = sum(d.weight * dimensions[d.key] for d in rubric.dimensions)
    total = sum(d.weight for d in rubric.dimensions)
    if must_have is not None:  # otherwise the must-have weight is dropped and the rest rescaled
        weighted += rubric.must_have_weight * must_have
        total += rubric.must_have_weight
    overall = round(weighted / total, 1)

    hard_blocker = any(r.classification is Classification.BLOCKER for r in requirements)
    by_status = {s: [r.label for r in requirements if r.status is s] for s in RequirementStatus}
    return MatchOutcome(
        dimensions={k: round(v, 1) for k, v in dimensions.items()},
        must_have=round(must_have, 1) if must_have is not None else None,
        requirements=requirements,
        overall_score=overall,
        category=BLOCKED if hard_blocker else band(rubric, overall),
        hard_blocker=hard_blocker,
        matched=by_status[RequirementStatus.MET],
        partial=by_status[RequirementStatus.PARTIAL],
        missing=by_status[RequirementStatus.NOT_MET],
    )

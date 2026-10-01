"""rubric_v1: the versioned matching configuration (PRD §17–§21, decisions 2026-10-02).

Weights, thresholds and bands live here (configuration), never inside prompts. Changing anything
that affects scores requires a new `version`, which invalidates cached matches.
"""

from dataclasses import dataclass

LEVELS = ("clear mismatch", "weak", "partial", "strong", "excellent")  # PRD §17, 0..4


@dataclass(frozen=True)
class Dimension:
    key: str
    label: str
    weight: float
    instructions: str


@dataclass(frozen=True)
class HardRequirement:
    """A PRD §19 hard-requirement type, checked with two yes/no questions (OD-6)."""

    key: str
    label: str
    stated_question: str
    met_question: str


@dataclass(frozen=True)
class Rubric:
    version: str
    levels: tuple[str, ...]
    must_have_weight: float
    dimensions: tuple[Dimension, ...]
    hard_requirements: tuple[HardRequirement, ...]
    stated_threshold: float  # P(stated as mandatory) above this = stated
    met_threshold: float  # p > this = MET
    partial_threshold: float  # partial_threshold <= p <= met_threshold = PARTIAL
    bands: tuple[tuple[int, str], ...]  # (minimum rounded score, category), highest first
    max_resume_chars: int
    max_description_chars: int

    def total_weight(self) -> float:
        return self.must_have_weight + sum(d.weight for d in self.dimensions)


_ONLY = " Judge only from the CANDIDATE and VACANCY text above; do not assume anything not stated."

RUBRIC_V1 = Rubric(
    version="rubric_v1",
    levels=LEVELS,
    must_have_weight=0.30,
    dimensions=(
        Dimension(
            "skills",
            "Skills",
            0.25,
            "How well do the candidate's technical skills match the skills the vacancy asks for?"
            + _ONLY,
        ),
        Dimension(
            "experience",
            "Experience",
            0.20,
            "How well does the candidate's relevant work experience match what the vacancy "
            "requires?" + _ONLY,
        ),
        Dimension(
            "role",
            "Role alignment",
            0.10,
            "How closely do the candidate's target roles and career direction align with this "
            "role?" + _ONLY,
        ),
        Dimension(
            "seniority",
            "Seniority",
            0.05,
            "How well does the candidate's seniority level fit the seniority of this role?" + _ONLY,
        ),
        Dimension(
            "domain",
            "Domain",
            0.05,
            "How well does the candidate's industry and domain background fit the vacancy's "
            "domain?" + _ONLY,
        ),
        Dimension(
            "education",
            "Education & certification",
            0.05,
            "How well do the candidate's education and certifications fit what the vacancy "
            "asks for?" + _ONLY,
        ),
    ),
    hard_requirements=(
        HardRequirement(
            "language",
            "Mandatory language",
            "Does the vacancy state that proficiency in a specific language is mandatory "
            "(required, not merely an advantage)?" + _ONLY,
            "Does the candidate meet the vacancy's mandatory language requirement, at the level "
            "required, based on the candidate's stated languages and resume?" + _ONLY,
        ),
        HardRequirement(
            "security_clearance",
            "Security clearance",
            "Does the vacancy require a security clearance?" + _ONLY,
            "Does the candidate hold the security clearance the vacancy requires?" + _ONLY,
        ),
        HardRequirement(
            "licence",
            "Required licence",
            "Does the vacancy require a specific licence (for example a driving or professional "
            "licence) as mandatory?" + _ONLY,
            "Does the candidate hold the licence the vacancy requires?" + _ONLY,
        ),
        HardRequirement(
            "qualification",
            "Professional qualification",
            "Does the vacancy require a specific degree or professional qualification as "
            "mandatory (not merely preferred)?" + _ONLY,
            "Does the candidate have the degree or professional qualification the vacancy "
            "requires?" + _ONLY,
        ),
        HardRequirement(
            "years_experience",
            "Minimum years of experience",
            "Does the vacancy state a minimum number of years of experience as a requirement?"
            + _ONLY,
            "Does the candidate meet the vacancy's minimum years-of-experience requirement?"
            + _ONLY,
        ),
        HardRequirement(
            "work_location",
            "Work location",
            "Does the vacancy restrict where the employee must be based or work (for example a "
            "specific country, city or mandatory on-site presence)?" + _ONLY,
            "Can the candidate meet the vacancy's location requirement, given the candidate's "
            "preferred locations, remote preference and work authorization?" + _ONLY,
        ),
    ),
    stated_threshold=0.5,
    met_threshold=0.75,
    partial_threshold=0.5,
    bands=((85, "STRONG"), (70, "GOOD"), (55, "STRETCH"), (0, "LOW")),
    max_resume_chars=16_000,
    max_description_chars=16_000,
)

RUBRICS = {RUBRIC_V1.version: RUBRIC_V1}
CURRENT_RUBRIC = RUBRIC_V1

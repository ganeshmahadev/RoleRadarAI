"""DecisionProvider boundary (PRD §11.1, §73): typed questions in, calibrated answers out.

Generic on purpose: the matching service builds the questions; a provider only answers them.
"""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import AppError


class DecisionUnavailable(AppError):
    """Transport failure, timeout or 5xx: safe to retry later."""

    code = "DECISION_PROVIDER_UNAVAILABLE"
    retryable = True
    http_status = 503


class DecisionRequestRejected(AppError):
    """The provider rejected the request (a bug in the questions): do not retry."""

    code = "DECISION_REQUEST_REJECTED"
    http_status = 502


class DecisionInvalidResponse(AppError):
    code = "DECISION_INVALID_RESPONSE"
    http_status = 502


class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: str
    criteria: Annotated[list[str], Field(min_length=2)]  # ordered levels, lowest first


class YesNoQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: str


Question = ScoreQuestion | YesNoQuestion


class ScoreAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["score"]
    score: Annotated[float, Field(ge=0)]  # expected level index
    probabilities: dict[str, Annotated[float, Field(ge=0, le=1)]]
    confidence: Annotated[float, Field(ge=0, le=1)]


class YesNoAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["noul"]
    noul: Annotated[float, Field(ge=0, le=1)]  # calibrated probability of "yes"


Answer = Annotated[ScoreAnswer | YesNoAnswer, Field(discriminator="type")]


class ModelInfo(BaseModel):
    provider: str
    name: str
    revision: str  # changes whenever weights, calibration or helper change


class DecisionResult(BaseModel):
    model: str
    answers: dict[str, Answer]
    input_tokens: int


class DecisionProvider(Protocol):
    async def model_info(self) -> ModelInfo: ...

    async def decide(self, state: str, questions: dict[str, Question]) -> DecisionResult: ...

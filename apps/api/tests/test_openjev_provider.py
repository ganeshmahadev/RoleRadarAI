import httpx
import pytest
from httpx import AsyncClient

from app.main import create_app
from app.providers.decision import (
    DecisionInvalidResponse,
    DecisionRequestRejected,
    DecisionUnavailable,
    Question,
    ScoreQuestion,
    YesNoQuestion,
)
from app.providers.factory import get_decision_provider
from app.providers.openjev import OpenJevProvider, revision_from_version
from tests.fake_openjev import VERSION, FakeOpenJev

QUESTIONS: dict[str, Question] = {
    "skills": ScoreQuestion(instructions="Skills fit?", criteria=["weak", "ok", "strong"]),
    "danish": YesNoQuestion(instructions="Is Danish mandatory?"),
}


def provider(fake: FakeOpenJev | httpx.MockTransport) -> OpenJevProvider:
    transport = fake.transport() if isinstance(fake, FakeOpenJev) else fake
    return OpenJevProvider(
        "http://openjev.test", timeout_seconds=5, transport=transport, backoff_seconds=0
    )


async def test_model_info_revision() -> None:
    info = await provider(FakeOpenJev()).model_info()
    assert (info.provider, info.name) == ("openjev", "openjev-MLX-4bit")
    assert info.revision.startswith("openjev-MLX-4bit;T=0.85;noul=1.829074,0.0;helper=81a22f1b1b89")


def test_revision_changes_with_calibration_or_helper() -> None:
    base = revision_from_version(VERSION).revision
    assert revision_from_version({**VERSION, "T": 0.9}).revision != base
    assert revision_from_version({**VERSION, "shim_sha256": "ff" * 32}).revision != base
    assert revision_from_version({**VERSION, "flags": {"perms": 4}}).revision != base


async def test_decide_sends_contract_and_parses_answers() -> None:
    fake = FakeOpenJev(scores={"skills": 1.6}, yes={"danish": 0.93})
    result = await provider(fake).decide("CANDIDATE ...", QUESTIONS)
    sent = fake.requests[0]
    assert sent["state"] == "CANDIDATE ..."
    assert sent["questions"]["skills"] == {
        "type": "score",
        "instructions": "Skills fit?",
        "criteria": ["weak", "ok", "strong"],
    }
    assert sent["questions"]["danish"] == {"type": "noul", "instructions": "Is Danish mandatory?"}
    assert result.answers["skills"].score == 1.6  # type: ignore[union-attr]
    assert result.answers["danish"].noul == 0.93  # type: ignore[union-attr]
    assert result.input_tokens == 1234
    assert "openjev-MLX-4bit" in result.model


async def test_transport_errors_are_retried_then_unavailable() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(DecisionUnavailable, match="start-openjev.sh") as info:
        await provider(httpx.MockTransport(handler)).model_info()
    assert calls == 3
    assert info.value.retryable is True


async def test_transport_error_then_success() -> None:
    fake = FakeOpenJev()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return fake.handler(request)

    assert (await provider(httpx.MockTransport(handler)).model_info()).name == "openjev-MLX-4bit"
    assert calls == 2


async def test_http_errors_are_classified_without_retry() -> None:
    with pytest.raises(DecisionUnavailable):
        await provider(FakeOpenJev(fail_with=503)).decide("s", QUESTIONS)
    with pytest.raises(DecisionRequestRejected) as info:
        await provider(FakeOpenJev(fail_with=422)).decide("s", QUESTIONS)
    assert info.value.retryable is False


@pytest.mark.parametrize(
    "payload",
    [
        {"answers": {}},  # no model field
        {
            "model": "m",
            "answers": {
                "skills": {"type": "score", "score": 1, "probabilities": {}, "confidence": 0.5}
            },
        },
        {
            "model": "m",
            "answers": {
                "skills": {"type": "noul", "noul": 0.5},
                "danish": {"type": "noul", "noul": 0.5},
            },
        },
        {
            "model": "m",
            "answers": {
                "skills": {"type": "score", "score": 1, "probabilities": {}, "confidence": 0.5},
                "danish": {"type": "noul", "noul": 1.7},
            },
        },
    ],
)
async def test_invalid_responses_are_rejected(payload: dict[str, object]) -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(DecisionInvalidResponse):
        await provider(transport).decide("s", QUESTIONS)


async def test_health_openjev_endpoint() -> None:
    for fake, expected in ((FakeOpenJev(), 200), (FakeOpenJev(fail_with=503), 503)):
        app = create_app()
        app.dependency_overrides[get_decision_provider] = lambda f=fake: provider(f)
        async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            response = await c.get("/api/v1/health/openjev")
        assert response.status_code == expected
        if expected == 200:
            assert response.json()["detail"].startswith("openjev-MLX-4bit;")

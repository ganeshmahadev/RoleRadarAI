"""Structured, retry-classified errors for job-source retrieval (PRD §57, §65)."""


class SourceError(Exception):
    """Base error. `code` is stable and shown to the API client; `retryable` drives P7 retries."""

    code = "SOURCE_ERROR"
    retryable = False
    http_status = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidUrl(SourceError):
    code = "INVALID_URL"


class BlockedUrl(SourceError):
    """SSRF protection: private/loopback/metadata targets, bad schemes or ports."""

    code = "BLOCKED_URL"


class EuresNotAllowed(SourceError):
    """EURES vacancy content must never be fetched (PRD §8)."""

    code = "EURES_NOT_ALLOWED"


class RobotsDisallowed(SourceError):
    """robots.txt disallows the path: use manual JD paste (PRD §26)."""

    code = "ROBOTS_DISALLOWED"


class FetchFailed(SourceError):
    code = "FETCH_FAILED"
    http_status = 502

    def __init__(self, message: str, *, retryable: bool, status: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status = status


class ResponseTooLarge(SourceError):
    code = "RESPONSE_TOO_LARGE"


class UnsupportedSource(SourceError):
    code = "UNSUPPORTED_SOURCE"


class ExtractionFailed(SourceError):
    """The page was fetched but no usable vacancy could be extracted: paste the JD manually."""

    code = "EXTRACTION_FAILED"


class UnsupportedOperation(SourceError):
    """A connector does not implement this capability (PRD §9)."""

    code = "UNSUPPORTED_OPERATION"

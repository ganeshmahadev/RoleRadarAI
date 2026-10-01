"""Structured application errors returned as {"detail": {code, message, retryable}} (PRD §65)."""


class AppError(Exception):
    """`code` is stable and shown to the API client; `retryable` drives retry policy (P7)."""

    code = "APP_ERROR"
    retryable = False
    http_status = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

"""Domain errors (docs/04-architecture/02-backend-modules.md, Error model). Routers map them to the API format."""

from __future__ import annotations

from typing import Any


class KeeperError(Exception):
    code = "error"
    http_status = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None, *, code: str | None = None,
                 http_status: int | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if code:
            self.code = code
        if http_status:
            self.http_status = http_status


class NotFound(KeeperError):
    code, http_status = "not_found", 404


class ValidationFailed(KeeperError):
    code, http_status = "validation_failed", 400


class Forbidden(KeeperError):
    code, http_status = "forbidden", 403


class ConsentRequired(KeeperError):
    code, http_status = "consent_required", 403


class Conflict(KeeperError):
    code, http_status = "conflict", 409


class RulerMismatch(KeeperError):
    code, http_status = "ruler_mismatch", 409


class JobInProgress(KeeperError):
    code, http_status = "job_in_progress", 409


class ConfirmationRequired(KeeperError):
    code, http_status = "confirmation_required", 402


class SpendCapReached(KeeperError):
    code, http_status = "spend_cap_reached", 402


class ModelOutputInvalid(KeeperError):
    code, http_status = "model_output_invalid", 422


class RateLimited(KeeperError):
    code, http_status = "rate_limited", 429


class ModelUnavailable(KeeperError):
    code, http_status = "model_unavailable", 503


class SandboxUnavailable(KeeperError):
    code, http_status = "sandbox_unavailable", 503


class NoApiKey(KeeperError):
    code, http_status = "no_api_key", 503


class AuthRequired(KeeperError):
    code, http_status = "auth_required", 401

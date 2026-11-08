"""Built-in error categories and extensible typed failures. Messages/causes are not metric labels."""
from .ModelUsage import ModelUsageStats

ERROR_KINDS = frozenset({
    "none", "invalid_arguments", "unknown_tool", "authentication",
    "permission_denied", "rate_limit", "quota_exceeded", "timeout",
    "connection", "provider_unavailable", "invalid_response", "unsupported",
    "not_found", "audio_device", "execution_error", "internal", "unknown",
})


def error_kind(error: Exception, fallback: str = "internal") -> str:
    if isinstance(error, OperationError):
        return error.kind
    # SDKs often wrap network errors. Inspect structured causes, never prose.
    cause = getattr(error, "original_error", None) or error.__cause__
    if isinstance(cause, Exception) and cause is not error:
        return error_kind(cause, fallback)
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    body = getattr(error, "body", None)
    detail = body.get("error", body) if isinstance(body, dict) else {}
    code = detail.get("code") if isinstance(detail, dict) else None
    if code in ("insufficient_quota", "quota_exceeded"):
        return "quota_exceeded"
    if status in (400, 422):
        return "invalid_arguments"
    if status == 401:
        return "authentication"
    if status == 403:
        return "permission_denied"
    if status == 404:
        return "not_found"
    if status in (408, 504):
        return "timeout"
    if status == 429:
        return "rate_limit"
    if isinstance(status, int) and status >= 500:
        return "provider_unavailable"
    # isinstance keeps plugin-provided class names out of the label contract.
    import httpx
    import requests
    import json
    import binascii
    from openai import APITimeoutError, APIConnectionError
    if isinstance(error, (TimeoutError, httpx.TimeoutException, requests.Timeout, APITimeoutError)):
        return "timeout"
    if isinstance(error, (ConnectionError, httpx.NetworkError, requests.ConnectionError, APIConnectionError)):
        return "connection"
    if isinstance(error, (json.JSONDecodeError, binascii.Error)):
        return "invalid_response"
    return fallback


class OperationError(Exception):
    def __init__(self, message: str, original_error: Exception | None = None, *, kind: str | None = None):
        super().__init__(message)
        self.original_error = original_error
        self.kind = (kind if isinstance(kind, str) and kind.strip() and kind != "none" else "unknown") if kind is not None else (
            error_kind(original_error) if original_error is not None else "unknown"
        )


class ToolError(OperationError):
    pass


class AudioPipelineError(OperationError):
    def __init__(self, message: str, original_error: Exception, *, stage: str):
        super().__init__(message, original_error)
        self.stage = stage if isinstance(stage, str) and stage.strip() else "unknown"


class LLMError(OperationError):
    """Legacy public error name/constructor; also catches new model errors."""
    def __init__(self, message: str, original_error: Exception | None = None, *,
                 kind: str | None = None, usage: ModelUsageStats | None = None):
        super().__init__(message, original_error, kind=kind)
        self.usage = usage


class ModelError(LLMError):
    """Typed provider failure, compatible with existing except LLMError blocks."""

"""Public, request-scoped model usage API for provider plugins.

Providers populate identity and any known usage before returning/streaming.
Legacy numeric defaults remain zero for compatibility. Use unknown() or explicit
None for unreported measurements. Handlers, not providers, emit terminal events.
"""
from dataclasses import dataclass
from collections.abc import Iterable


@dataclass
class ModelUsageStats:
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    total_tokens: int | None = 0
    cached_tokens: int | None = 0
    reasoning_tokens: int | None = None
    provider: str | None = None
    model_name: str | None = None
    response_ms: float | None = None
    time_to_first_token_ms: float | None = None
    output_chars: int | None = None
    retry_attempts: int | None = 0
    voice_name: str | None = None
    input_language: str | None = None
    output_language: str | None = None
    time_to_first_byte_ms: float | None = None
    reasoning_tokens_in_output: bool | None = None
    is_provider_operation: bool = True
    # Filled by the playback consumer; absent when playback was not observed.
    num_underruns: int | None = None

    @classmethod
    def unknown(cls, **metadata) -> "ModelUsageStats":
        """Usage was not reported; do not turn unknown amounts into zero usage."""
        return cls(**{ "input_tokens": None, "output_tokens": None, "total_tokens": None,
                       "cached_tokens": None, "retry_attempts": None, **metadata })


@dataclass
class TranscriptionResult:
    text: str
    usage: ModelUsageStats


@dataclass
class SynthesisResult:
    audio_stream: Iterable[bytes]
    usage: ModelUsageStats

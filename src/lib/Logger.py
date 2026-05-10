import sys
import traceback
from typing import Any, Literal, cast
import io
import datetime
import logging
import atexit
from functools import wraps
from dataclasses import dataclass
from pythonjsonlogger.json import JsonFormatter
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import (
    Resource,
    SERVICE_NAME,
    SERVICE_INSTANCE_ID,
    SERVICE_NAMESPACE,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

from .UI import emit_message, send_message


def configure_stdio() -> None:
    if sys.stdout and not sys.stdout.closed:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", write_through=True
        )
    if sys.stderr and not sys.stderr.closed:
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", write_through=True
        )


logger = logging.getLogger()

logHandler = logging.StreamHandler(stream=sys.stdout)
formatter = JsonFormatter(
    static_fields={"type": "log"},
    reserved_attrs=[],
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    rename_fields={"levelname": "prefix", "asctime": "timestamp"},
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

tracer = trace.get_tracer(__name__)


def enable_remote_tracing(username: str, attributes: dict[str, str]):
    """
    Enable remote OpenTelemetry tracing and logging to the monitoring endpoint.

    Args:
        username: The username for identification in traces and logs
        attributes: Additional attributes to attach to telemetry data
    """

    # Setup shared resource for both tracing and logging
    resource = Resource.create(
        {"service.name": "com.covaslabs.chat", "user.name": username, **attributes}
    )

    log("debug", f"Enabling remote tracing and logging", attributes)

    # Setup OpenTelemetry tracing
    otel_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(otel_provider)

    # Add OTLP exporter for remote tracing
    trace_endpoint_url = "https://monitoring.covaslabs.com/v1/traces"
    otlp_trace_exporter = OTLPSpanExporter(
        endpoint=trace_endpoint_url,
        headers={
            "x-user-name": username,
        },
        timeout=10,
        compression=None,
    )

    log(
        "debug",
        f"Creating BatchSpanProcessor with OTLP exporter to {trace_endpoint_url}",
    )

    trace_processor = BatchSpanProcessor(
        otlp_trace_exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
        export_timeout_millis=30000,
    )
    otel_provider.add_span_processor(trace_processor)

    # Setup OpenTelemetry logging
    log_provider = LoggerProvider(resource=resource)
    set_logger_provider(log_provider)

    # Add OTLP exporter for remote logging
    log_endpoint_url = "https://monitoring.covaslabs.com/v1/logs"
    otlp_log_exporter = OTLPLogExporter(
        endpoint=log_endpoint_url,
        headers={
            "x-user-name": username,
        },
        timeout=10,
        compression=None,
    )

    log(
        "debug",
        f"Creating BatchLogRecordProcessor with OTLP exporter to {log_endpoint_url}",
    )

    log_processor = BatchLogRecordProcessor(
        otlp_log_exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
        export_timeout_millis=30000,
    )
    log_provider.add_log_record_processor(log_processor)

    # Attach OTLP logging handler to the root logger
    otel_log_handler = LoggingHandler(
        level=logging.NOTSET, logger_provider=log_provider
    )

    # Add a filter to prevent urllib3 and opentelemetry logs from going to remote
    # while still allowing them to be logged locally
    class NoTelemetryLibsFilter(logging.Filter):
        def filter(self, record):
            # Prevent logs from telemetry libraries from being sent remotely
            return not (
                (record.threadName or "").startswith("OtelBatchLogRecordProcessor")
                or "monitoring.covaslabs.com" in record.message
                or record.name.startswith("opentelemetry")
            )

    otel_log_handler.addFilter(NoTelemetryLibsFilter())
    logging.getLogger().addHandler(otel_log_handler)

    # Instrument OpenAI for automatic tracing
    log("debug", "Instrumenting OpenAI API calls")
    OpenAIInstrumentor().instrument()

    # Register shutdown handler to ensure spans and logs are flushed on exit
    def shutdown_telemetry():
        try:
            log("debug", "Flushing remaining spans and logs...")
            otel_provider.force_flush(timeout_millis=5000)
            log_provider.force_flush(timeout_millis=5000)
            otel_provider.shutdown()
            log_provider.shutdown()
            log("debug", "Telemetry shutdown complete")
        except Exception as e:
            log("warn", f"Error during telemetry shutdown: {e}")

    atexit.register(shutdown_telemetry)

    log("info", f"Remote tracing and logging enabled", attributes)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Call default handler for keyboard interrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    if not sys.stderr.closed and not sys.stdout.closed:
        contents = traceback.format_exception(exc_type, exc_value, exc_traceback)
        emit_message(
            "log",
            stream=sys.stderr,
            prefix="error",
            message="Uncaught exception: " + str(contents),
        )
        emit_message(
            "chat",
            role="error",
            message="Uncaught exception, please check the logs for more details.",
        )


sys.excepthook = handle_exception


def show_chat_message(role: str, *args: Any, **payload: Any):
    output = io.StringIO()
    print(*args, file=output)
    contents = output.getvalue().strip()
    output.close()
    role = role.lower()

    # logger.info(contents)

    emit_message("chat", role=role, message=contents, **payload)


def log(prefix: Literal["info", "debug", "warn", "error"], message: Any, *args: Any):
    output = io.StringIO()
    print(message, *args, file=output)
    contents = output.getvalue().strip()
    output.close()
    prefix = cast(Literal["info", "debug", "warn", "error"], prefix.lower())

    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    if prefix == "debug":
        logging.debug(contents, extra={"timestamp": timestamp})
    elif prefix == "info":
        logging.info(contents, extra={"timestamp": timestamp})
    elif prefix == "warn":
        logging.warning(contents, extra={"timestamp": timestamp})
    elif prefix == "error":
        logging.error(contents, extra={"timestamp": timestamp})
    else:
        logging.info(contents, extra={"timestamp": timestamp})
    if sys.stdout and not sys.stdout.closed:
        sys.stdout.flush()
    if sys.stderr and not sys.stderr.closed:
        sys.stderr.flush()


def observe():
    """Observe decorator for tracing function calls with arguments and return values using OpenTelemetry."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(func.__name__) as span:
                result = None
                duration = None
                try:
                    start = datetime.datetime.now()
                    result = func(*args, **kwargs)
                    end = datetime.datetime.now()
                    duration = (end - start).total_seconds()
                    span.set_attribute("duration", duration)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
                finally:
                    logger.debug(
                        f"Trace for function {func.__name__} completed",
                        extra={
                            "func_name": func.__name__,
                            "span_id": format(span.get_span_context().span_id, "016x"),
                            "trace_id": format(
                                span.get_span_context().trace_id, "032x"
                            ),
                            "arguments": {
                                **{f"arg{i}": repr(arg) for i, arg in enumerate(args)},
                                **{k: repr(v) for k, v in kwargs.items()},
                            },
                            "return": repr(result)
                            if "result" in locals()
                            else "exception",
                            "duration": duration,
                        },
                    )

        return wrapper

    return decorator


@dataclass
class PromptUsageStats:
    """Approximate prompt size accounting by use-case (chars)."""

    system_chars: int = 0
    memory_chars: int = 0
    status_chars: int = 0
    conversation_chars: int = 0
    web_search_chars: int = 0
    genui_chars: int = 0
    reuse_chars: int = 0

    def compute_total(self) -> int:
        return (
            self.system_chars
            + self.memory_chars
            + self.status_chars
            + self.conversation_chars
            + self.web_search_chars
            + self.genui_chars
        )


@dataclass
class LatencyUsageStats:
    response_ms: float | None = None
    time_to_first_token_ms: float | None = None
    time_to_first_byte_ms: float | None = None


@dataclass
class AudioUsageStats:
    input_audio_duration_ms: float | None = None
    output_audio_duration_ms: float | None = None


@dataclass
class TextUsageStats:
    input_chars: int | None = None
    output_chars: int | None = None


@dataclass
class CacheUsageStats:
    llm_calls_saved: int = 0
    llm_calls_added: int = 0


@dataclass
class ModelUsageStats:
    """Token-level API usage as reported by the model provider."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int | None = None
    provider: str | None = None
    model_name: str | None = None
    response_ms: float | None = None
    time_to_first_token_ms: float | None = None
    output_chars: int | None = None


def _to_usage_payload_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None

    data = vars(value).copy()
    return {key: item for key, item in data.items() if item is not None}


def _normalize_optional_string(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized if normalized else None
    return None


def _persist_and_send_usage(
    *,
    usage_kind: str,
    message: dict[str, Any],
) -> None:
    try:
        from .Database import ModelUsageStore

        ModelUsageStore().insert(
            timestamp=message["timestamp"],
            usage_kind=usage_kind,
            payload=message,
        )
    except Exception as exc:
        log("error", "Failed to persist model usage:", exc)

    send_message(message)


def _build_usage_message(
    *,
    message_type: str,
    timestamp: str,
    context: str,
    provider: str | None,
    model_name: str | None,
    model_usage: dict[str, Any] | None = None,
    prompt_usage: dict[str, Any] | None = None,
    latency_usage: dict[str, Any] | None = None,
    audio_usage: dict[str, Any] | None = None,
    text_usage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
    message: dict[str, Any] = {
        "type": message_type,
        "schema_version": 2,
        "timestamp": timestamp,
        "context": context,
        "provider": _normalize_optional_string(provider),
        "model_name": _normalize_optional_string(model_name),
    }

    if model_usage is not None:
        message["model_usage"] = model_usage
    if prompt_usage is not None:
        message["prompt_usage"] = prompt_usage
    if latency_usage is not None:
        message["latency_usage"] = latency_usage
    if audio_usage is not None:
        message["audio_usage"] = audio_usage
    if text_usage is not None:
        message["text_usage"] = text_usage

    return message


def log_llm_usage(
    context: str,
    model_usage: ModelUsageStats,
    prompt_usage: PromptUsageStats,
    llm_model: Any | None = None,
    response_text: str | None = None,
) -> None:
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    provider = _normalize_optional_string(getattr(llm_model, "provider_name", None))
    if provider is None:
        provider = _normalize_optional_string(model_usage.provider)
    model_name = _normalize_optional_string(getattr(llm_model, "model_name", None))
    if model_name is None:
        model_name = _normalize_optional_string(model_usage.model_name)
    model_usage_data = {
        "input_tokens": model_usage.input_tokens,
        "output_tokens": model_usage.output_tokens,
        "total_tokens": model_usage.total_tokens,
        "cached_tokens": model_usage.cached_tokens,
        "reasoning_tokens": model_usage.reasoning_tokens,
    }
    if provider is not None:
        model_usage_data["provider"] = provider
    if model_name is not None:
        model_usage_data["model_name"] = model_name
    prompt_usage_data = vars(prompt_usage).copy()
    prompt_usage_data["total_prompt_chars"] = prompt_usage.compute_total()
    latency_usage = _to_usage_payload_dict(
        LatencyUsageStats(
            response_ms=model_usage.response_ms,
            time_to_first_token_ms=model_usage.time_to_first_token_ms,
        ),
    )
    text_usage = _to_usage_payload_dict(
        TextUsageStats(
            output_chars=(
                len(response_text)
                if response_text is not None
                else model_usage.output_chars
            ),
        ),
    )

    message = _build_usage_message(
        message_type="llm_usage",
        timestamp=timestamp,
        context=context,
        provider=provider,
        model_name=model_name,
        model_usage=model_usage_data,
        prompt_usage=prompt_usage_data,
        latency_usage=latency_usage,
        text_usage=text_usage,
    )

    _persist_and_send_usage(usage_kind="llm", message=message)


def log_stt_usage(
    context: str,
    *,
    provider: str | None,
    model_name: str | None,
    latency_usage: LatencyUsageStats | None = None,
    audio_usage: AudioUsageStats | None = None,
    text_usage: TextUsageStats | None = None,
) -> None:
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    message = _build_usage_message(
        message_type="stt_usage",
        timestamp=timestamp,
        context=context,
        provider=provider,
        model_name=model_name,
        latency_usage=_to_usage_payload_dict(latency_usage),
        audio_usage=_to_usage_payload_dict(audio_usage),
        text_usage=_to_usage_payload_dict(text_usage),
    )

    _persist_and_send_usage(usage_kind="stt", message=message)


def log_tts_usage(
    context: str,
    *,
    provider: str | None,
    model_name: str | None,
    latency_usage: LatencyUsageStats | None = None,
    audio_usage: AudioUsageStats | None = None,
    text_usage: TextUsageStats | None = None,
) -> None:
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    message = _build_usage_message(
        message_type="tts_usage",
        timestamp=timestamp,
        context=context,
        provider=provider,
        model_name=model_name,
        latency_usage=_to_usage_payload_dict(latency_usage),
        audio_usage=_to_usage_payload_dict(audio_usage),
        text_usage=_to_usage_payload_dict(text_usage),
    )

    _persist_and_send_usage(usage_kind="tts", message=message)


def log_action_cache_usage(
    context: str,
    *,
    provider: str | None,
    model_name: str | None,
    cache_usage: CacheUsageStats,
) -> None:
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    message = _build_usage_message(
        message_type="action_cache_usage",
        timestamp=timestamp,
        context=context,
        provider=provider,
        model_name=model_name,
    )
    message["cache_usage"] = _to_usage_payload_dict(cache_usage) or {}

    _persist_and_send_usage(usage_kind="llm", message=message)

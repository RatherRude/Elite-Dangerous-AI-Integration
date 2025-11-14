import sys
from typing import Any, Literal
import io
import datetime
import logging
import json
import atexit
from functools import wraps 
from pythonjsonlogger.json import JsonFormatter
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_INSTANCE_ID, SERVICE_NAMESPACE
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)

logger = logging.getLogger()

logHandler = logging.StreamHandler(stream=sys.stdout)
formatter = JsonFormatter(
    static_fields={"type": "log"},
    reserved_attrs=[], 
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    rename_fields={'levelname': 'prefix', 'asctime': 'timestamp'}
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

tracer = trace.get_tracer(__name__)

def enable_remote_tracing(username: str, attributes: dict[str, str]):
    """
    Enable remote OpenTelemetry tracing and logging to the monitoring endpoint.
    
    Args:
        username: The username for identification in traces and logs
        attributes: Additional attributes to attach to telemetry data
    """
    
    # Setup shared resource for both tracing and logging
    resource = Resource.create({
        "service.name": "com.covaslabs.chat",
        "user.name": username,
        **attributes
    })
    
    log('debug', f'Enabling remote tracing and logging', attributes)
    
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
    
    log('debug', f'Creating BatchSpanProcessor with OTLP exporter to {trace_endpoint_url}')
    
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
    
    log('debug', f'Creating BatchLogRecordProcessor with OTLP exporter to {log_endpoint_url}')
    
    log_processor = BatchLogRecordProcessor(
        otlp_log_exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
        export_timeout_millis=30000,
    )
    log_provider.add_log_record_processor(log_processor)
    
    # Attach OTLP logging handler to the root logger
    otel_log_handler = LoggingHandler(level=logging.NOTSET, logger_provider=log_provider)
    
    # Add a filter to prevent urllib3 and opentelemetry logs from going to remote
    # while still allowing them to be logged locally
    class NoTelemetryLibsFilter(logging.Filter):
        def filter(self, record):
            # Prevent logs from telemetry libraries from being sent remotely
            return not ((record.threadName or '').startswith('OtelBatchLogRecordProcessor') or 'monitoring.covaslabs.com' in record.message or record.name.startswith('opentelemetry'))
    
    otel_log_handler.addFilter(NoTelemetryLibsFilter())
    logging.getLogger().addHandler(otel_log_handler)
    
    # Instrument OpenAI for automatic tracing
    log('debug', 'Instrumenting OpenAI API calls')
    OpenAIInstrumentor().instrument()
    
    # Register shutdown handler to ensure spans and logs are flushed on exit
    def shutdown_telemetry():
        try:
            log('debug', 'Flushing remaining spans and logs...')
            otel_provider.force_flush(timeout_millis=5000)
            log_provider.force_flush(timeout_millis=5000)
            otel_provider.shutdown()
            log_provider.shutdown()
            log('debug', 'Telemetry shutdown complete')
        except Exception as e:
            log('warn', f'Error during telemetry shutdown: {e}')
    
    atexit.register(shutdown_telemetry)
    
    log('info', f'Remote tracing and logging enabled', attributes)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Call default handler for keyboard interrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    if not sys.stderr.closed and not sys.stdout.closed:
        output = io.StringIO()
        print("Uncaught exception", exc_type, exc_value, exc_traceback, file=output)
        contents = output.getvalue().strip()
        output.close()
        print(json.dumps({
            "type": "log",
            "timestamp": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "prefix": "error",
            "message": contents
        }), file=sys.stderr)
        print(json.dumps({
            "type": "chat",
            "timestamp": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "role": "error",
            "message": "Uncaught exception, please check the logs for more details."
        }), file=sys.stdout)

sys.excepthook = handle_exception

def show_chat_message(role: str, *args: Any):
    output = io.StringIO()
    print(*args, file=output)
    contents = output.getvalue().strip()
    output.close()
    role = role.lower()
    
    message: dict[str, str] = {
        'type': 'chat',
        'timestamp': datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        'role': role,
        'message': contents,
    }
    
    #logger.info(contents)
    
    print(json.dumps(message), flush=True)

def log(prefix: Literal['info', 'debug', 'warn', 'error'], message: Any, *args: Any):
    output = io.StringIO()
    print(message, *args, file=output)
    contents = output.getvalue().strip()
    output.close()
    prefix = prefix.lower()
    
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    if prefix == 'debug':
        logging.debug(contents, extra={"timestamp": timestamp})
    elif prefix == 'info':
        logging.info(contents, extra={"timestamp": timestamp})
    elif prefix == 'warn':
        logging.warning(contents, extra={"timestamp": timestamp})
    elif prefix == 'error':
        logging.error(contents, extra={"timestamp": timestamp})
    else:
        logging.info(contents, extra={"timestamp": timestamp})
    if sys.stdout:
        sys.stdout.flush()
    if sys.stderr:
        sys.stderr.flush()
        
def observe():
    """Observe decorator for tracing function calls with arguments and return values using OpenTelemetry."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(func.__name__) as span:
                result = None
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
                    logger.debug(f"Trace for function {func.__name__} completed", extra={
                        "func_name": func.__name__,
                        "span_id": format(span.get_span_context().span_id, '016x'), 
                        "trace_id": format(span.get_span_context().trace_id, '032x'),
                        "arguments": {**{f"arg{i}": repr(arg) for i, arg in enumerate(args)}, **{k: repr(v) for k, v in kwargs.items()}},
                        "return": repr(result) if 'result' in locals() else 'exception',
                    })
        return wrapper
    return decorator
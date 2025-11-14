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
    Enable remote OpenTelemetry tracing to the monitoring endpoint.
    
    Args:
        username: The username for identification in traces
        instance_id: The unique instance identifier
    """
    
    # Setup OpenTelemetry tracing - disabled by default
    resource = Resource.create({
        "service.name": "com.covaslabs.chat",
        "user.name": username,
        **attributes
    })
    otel_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(otel_provider)
    
    log('debug', f'Enabling tracing', attributes)
    
    # Add OTLP exporter for remote tracing with all required configuration
    endpoint_url = "https://monitoring.covaslabs.com/v1/traces"
    otlp_exporter = OTLPSpanExporter(
        endpoint=endpoint_url,
        # Headers for authentication/identification (if needed)
        headers={
            "x-user-name": username,
        },
        # Timeout in seconds for the export request
        timeout=10,
        # Compression method (gzip is commonly supported)
        compression=None,
        # Use HTTP/1.1 or HTTP/2
        # The default is usually fine, but we can be explicit
    )
    
    log('debug', f'Creating BatchSpanProcessor with OTLP exporter to {endpoint_url}')
    
    processor = BatchSpanProcessor(
        otlp_exporter,
        # Max queue size before dropping spans
        max_queue_size=2048,
        # Max batch size per export
        max_export_batch_size=512,
        # Delay between exports in milliseconds
        schedule_delay_millis=5000,
        # Timeout for export in milliseconds
        export_timeout_millis=30000,
    )
    otel_provider.add_span_processor(processor)
    
    # Register shutdown handler to ensure spans are flushed on exit
    def shutdown_tracing():
        try:
            log('debug', 'Flushing remaining spans...')
            otel_provider.force_flush(timeout_millis=5000)
            otel_provider.shutdown()
            log('debug', 'Tracing shutdown complete')
        except Exception as e:
            log('warn', f'Error during tracing shutdown: {e}')
    
    atexit.register(shutdown_tracing)
    
    log('info', f'Remote tracing enabled', attributes)


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
                # Add function arguments as span attributes
                for i, arg in enumerate(args):
                    span.set_attribute(f"arg{i}", repr(arg))
                for k, v in kwargs.items():
                    span.set_attribute(k, repr(v))
                
                try:
                    start = datetime.datetime.now()
                    result = func(*args, **kwargs)
                    end = datetime.datetime.now()
                    duration = (end - start).total_seconds()
                    span.set_attribute("duration", duration)
                    span.set_attribute("return", repr(result))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
                finally:
                    print({
                        "type": "trace",
                        "timestamp": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "span": span.get_span_context().span_id,
                        "trace": span.get_span_context().trace_id,
                        "name": func.__name__,
                    })
        return wrapper
    return decorator
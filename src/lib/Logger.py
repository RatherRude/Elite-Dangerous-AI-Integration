import sys
from typing import Any, Literal
import io
import datetime
import logging
import json
from pythonjsonlogger.json import JsonFormatter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger()

logHandler = logging.StreamHandler(stream=sys.stdout)
formatter = JsonFormatter(
    static_fields={"type": "log", "timestamp": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}, 
    reserved_attrs=[], 
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    rename_fields={'levelname': 'prefix', 'asctime': 'timestamp'}
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Call default handler for keyboard interrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    if not sys.stderr.closed:
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
    
    logger.info(contents)
    
    print(json.dumps(message))
    
    if sys.stdout:
        sys.stdout.flush()

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
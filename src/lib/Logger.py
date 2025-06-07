import sys
from typing import Any, Literal
import io
import datetime
import logging
import json
from pythonjsonlogger.json import JsonFormatter

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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Call default handler for keyboard interrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

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
    
    message = {
        'type': 'log',
        'timestamp': datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        'prefix': prefix,
        'message': contents,
    }

    if prefix == 'debug':
        logging.debug(contents)
    elif prefix == 'info':
        logging.info(contents)
    elif prefix == 'warn':
        logging.warning(contents)
    elif prefix == 'error':
        logging.error(contents)
    else:
        logging.info(contents)
    if sys.stdout:
        sys.stdout.flush()
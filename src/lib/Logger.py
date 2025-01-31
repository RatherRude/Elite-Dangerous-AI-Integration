import sys
from typing import Any
import io
import json
import datetime

def log(prefix: str, message: Any, *args: Any):
    output = io.StringIO()
    print(message, *args, file=output)
    contents = output.getvalue()
    output.close()
    print(json.dumps({
        'type': 'log',
        'timestamp': datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'prefix': prefix.lower(),
        'message': contents,
    }))
    if sys.stdout:
        sys.stdout.flush()

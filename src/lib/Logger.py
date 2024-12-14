import sys
from typing import Any


def log(prefix: str, message: Any, *arg: Any):
    print(prefix.lower() + ':', message, *arg)
    if sys.stdout:
        sys.stdout.flush()

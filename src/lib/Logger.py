import sys


def log(prefix: str, message, *arg):
    print(prefix.lower() + ':', message, *arg)
    if sys.stdout:
        sys.stdout.flush()

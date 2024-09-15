import sys


def log(prefix: str, message, *arg):
    print(prefix.lower() + ':', message, *arg)
    sys.stdout.flush()

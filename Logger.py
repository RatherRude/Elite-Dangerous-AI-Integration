import sys


def log(prefix: str, message, *arg):
    print(prefix+':', message, *arg)
    sys.stdout.flush()
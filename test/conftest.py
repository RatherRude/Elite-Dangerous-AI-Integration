import io
import sys


def pytest_configure() -> None:
    sys.stdout = io.TextIOWrapper(sys.__stdout__.buffer, encoding="utf-8", write_through=True)
    sys.stderr = io.TextIOWrapper(sys.__stderr__.buffer, encoding="utf-8", write_through=True)

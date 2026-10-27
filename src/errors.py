import sys


def compilation_error(line: int, col: int, message: str):
    sys.stderr.write(f"compilation error: line {line}:{col}: {message}\n")
    sys.exit(1)

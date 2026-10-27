import sys

try:
    from errors import compilation_error
    from lexer import lex
    from parser import Parser
except ImportError:
    from src.errors import compilation_error
    from src.lexer import lex
    from src.parser import Parser


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "--ast":
        sys.stderr.write("Usage: python3 src/compiler.py --ast <input.txt>\n")
        sys.exit(1)

    source_path = sys.argv[2]
    try:
        with open(source_path, "rb") as f:
            data = f.read()
    except Exception as e:
        sys.stderr.write(f"compilation error: line 1:1: cannot read file '{source_path}': {e}\n")
        sys.exit(1)

    tokens = lex(data)
    p = Parser(tokens)
    ast_root = p.parse_program()
    ast_root.dump()


if __name__ == "__main__":
    main()

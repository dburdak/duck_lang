import sys

try:
    from errors import compilation_error
    from lexer import lex
    from parser import Parser
    from semantic import SemanticAnalyzer
except ImportError:
    from src.errors import compilation_error
    from src.lexer import lex
    from src.parser import Parser
    from src.semantic import SemanticAnalyzer


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("--ast", "--ir"):
        sys.stderr.write("Usage: python3 src/compiler.py (--ast|--ir) <input.txt>\n")
        sys.exit(1)

    mode = sys.argv[1]
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
    if mode == "--ast":
        ast_root.dump()
        return

    analyzer = SemanticAnalyzer(ast_root)
    analyzer.analyze()
    try:
        if __package__:
            from src.codegen import CodeGenerator
        else:
            from codegen import CodeGenerator
    except ModuleNotFoundError as import_error:
        if import_error.name == "llvmlite":
            compilation_error(1, 1, "LLVM generation requires llvmlite; install dependencies from requirements.txt")
        raise
    ir_text = CodeGenerator(ast_root, analyzer).generate()
    sys.stdout.write(ir_text)


if __name__ == "__main__":
    main()

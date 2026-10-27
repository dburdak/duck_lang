import os
import sys
import tempfile

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


def compile_file(source_path, mode):
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
        if any(getattr(item, "methods", None) for item in ast_root.items):
            SemanticAnalyzer(ast_root).analyze()
        ast_root.dump()
        return None

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
    return CodeGenerator(ast_root, analyzer).generate()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    usage = "Usage: python3 compiler.py [--ast <input.txt> | <input.txt> <output.ll>]\n"
    if len(args) == 2 and args[0] in ("--ast", "--ir"):
        mode, source_path = args
        output_path = None
    elif len(args) == 2:
        mode, source_path, output_path = "--output", args[0], args[1]
    else:
        sys.stderr.write(usage)
        return 1

    temporary_path = None
    try:
        if output_path is not None:
            if os.path.abspath(source_path) == os.path.abspath(output_path):
                compilation_error(1, 1, "input and output paths must be different")
            try:
                os.remove(output_path)
            except FileNotFoundError:
                pass

        ir_text = compile_file(source_path, mode)
        if mode == "--ir":
            sys.stdout.write(ir_text)
        elif output_path is not None:
            directory = os.path.dirname(os.path.abspath(output_path))
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=directory, delete=False
            ) as output_file:
                temporary_path = output_file.name
                output_file.write(ir_text)
            os.replace(temporary_path, output_path)
            temporary_path = None
        return 0
    except RecursionError:
        sys.stderr.write("compilation error: line 1:1: nesting is too deep\n")
    except SystemExit as error:
        if error.code not in (None, 0) and output_path is not None:
            try:
                os.remove(output_path)
            except FileNotFoundError:
                pass
        return error.code if isinstance(error.code, int) else 1
    except Exception:
        sys.stderr.write("compilation error: line 1:1: unexpected compiler error\n")
    finally:
        if temporary_path is not None:
            try:
                os.remove(temporary_path)
            except FileNotFoundError:
                pass
    if output_path is not None:
        try:
            os.remove(output_path)
        except FileNotFoundError:
            pass
    return 1


if __name__ == "__main__":
    sys.exit(main())

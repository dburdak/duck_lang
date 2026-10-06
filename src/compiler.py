import argparse
import sys

# Error reporting
def raise_err(error, err_line, column, ue_part=""):
    ERRORS = {
        1: "redeclared variable",
        2: "undeclared variable",
        3: "invalid variable name",
        4: "unparsable statement",
        5: "missing finish statement",
        6: "finish must be the last statement",
        7: "unparsable finish statement",
        8: "unsupported operator",
        9: "'🪶' is not closed before the end of the line",
        10: "unexpected byte",
        11: "unknown type",
        12: "cannot assign to immutable variable",
        13: "expected '<-'",
    }

    if isinstance(error, int):
        code = error
        msg = ERRORS.get(code, "unknown compilation error")
        if ue_part:
            msg += f" {ue_part}"
    else:
        code = 13
        msg = str(error)

    sys.stderr.write(f"compilation error: line {err_line}:{column}: {msg}\n")
    sys.exit(code)


# Table of Emoji to UTF-8 Byte Sequences & Unicode Code Points
EMOJI_UTF8_TABLE = {
    "🐥": {"codepoint": "U+1F425", "utf8_bytes": b"\xF0\x9F\x90\xA5", "utf8_hex": "0xF0 0x9F 0x90 0xA5", "desc": "Integer (32-bit)"},
    "🦆": {"codepoint": "U+1F986", "utf8_bytes": b"\xF0\x9F\xA6\x86", "utf8_hex": "0xF0 0x9F 0xA6 0x86", "desc": "Integer (64-bit)"},
    "🥚": {"codepoint": "U+1F95A", "utf8_bytes": b"\xF0\x9F\xA5\x9A", "utf8_hex": "0xF0 0x9F 0xA5 0x9A", "desc": "Boolean type"},
    "🪺": {"codepoint": "U+1FABA", "utf8_bytes": b"\xF0\x9F\xAA\xBA", "utf8_hex": "0xF0 0x9F 0xAA 0xBA", "desc": "Boolean true"},
    "🪹": {"codepoint": "U+1FAB9", "utf8_bytes": b"\xF0\x9F\xAA\xB9", "utf8_hex": "0xF0 0x9F 0xAA 0xB9", "desc": "Boolean false"},
    "🍃": {"codepoint": "U+1F343", "utf8_bytes": b"\xF0\x9F\x8D\x83", "utf8_hex": "0xF0 0x9F 0x8D 0x83", "desc": "Mutable variable"},
    "🪨": {"codepoint": "U+1FAA8", "utf8_bytes": b"\xF0\x9F\xAA\xA8", "utf8_hex": "0xF0 0x9F 0xAA 0xA8", "desc": "Constant variable"},
    "🐤": {"codepoint": "U+1F424", "utf8_bytes": b"\xF0\x9F\x90\xA4", "utf8_hex": "0xF0 0x9F 0x90 0xA4", "desc": "If keyword"},
    "🦢": {"codepoint": "U+1F9A2", "utf8_bytes": b"\xF0\x9F\xA6\xA2", "utf8_hex": "0xF0 0x9F 0xA6 0xA2", "desc": "Else keyword"},
    "🪶": {"codepoint": "U+1FAB6", "utf8_bytes": b"\xF0\x9F\xAA\xB6", "utf8_hex": "0xF0 0x9F 0xAA 0xB6", "desc": "Block open"},
    "🪽": {"codepoint": "U+1FABD", "utf8_bytes": b"\xF0\x9F\xAA\xBD", "utf8_hex": "0xF0 0x9F 0xAA 0xBD", "desc": "Block close"},
    "≡": {"codepoint": "U+2261", "utf8_bytes": b"\xE2\x89\xA1", "utf8_hex": "0xE2 0x89 0xA1", "desc": "Equal comparison"},
    "≢": {"codepoint": "U+2262", "utf8_bytes": b"\xE2\x89\xA2", "utf8_hex": "0xE2 0x89 0xA2", "desc": "Not equal comparison"},
}

# Lexer Keywords dictionary for Duck Lang
KEYWORDS = {
    # Types
    "🐥": "typename",
    "🦆": "typename",
    "🥚": "typename",
    # Specifiers
    "🍃": "specifier",
    "🪨": "specifier",
    # Boolean Literals
    "🪺": "bool_literal",
    "🪹": "bool_literal",
    # Control Flow
    "🐤": "keyword",
    "🦢": "keyword",
    "waddle": "keyword",
    "finish": "statement",
}


class Token:
    def __init__(self, kind, text, line, col):
        self.kind = kind
        self.text = text
        self.line = line
        self.col = col

    def to_str(self):
        return f"({self.kind}, {self.text}, {self.line}, {self.col})"


def is_alpha(b):
    if (ord("A") <= b <= ord("Z")) or (ord("a") <= b <= ord("z")) or b == ord("_"):
        return True
    return False


def is_digit(b):
    if ord("0") <= b <= ord("9"):
        return True
    return False


def is_operator(b):
    if b in (ord("*"), ord("/"), ord("+"), ord("-")):
        return True
    return False


def lex(data: bytes):
    lexer_lines, tokens = [], []
    line, col = 1, 1
    i = 0
    while i < len(data):
        b = data[i]

        # Whitespace
        if b in (32, 9, 13):  # space, tab, \r
            i += 1
            col += 1
        # Newline
        elif b == 10:  # \n
            lexer_lines.append(tokens)
            tokens = []
            line += 1
            col = 1
            i += 1
        # Identifiers and text keywords
        elif is_alpha(b):
            start = i
            start_col = col
            while i < len(data) and (is_alpha(data[i]) or is_digit(data[i])):
                i += 1
                col += 1
            word = data[start:i].decode()
            tokens.append(Token(KEYWORDS.get(word, "ident"), word, line, start_col))
        # Numbers
        elif is_digit(b):
            start = i
            start_col = col
            while i < len(data) and is_digit(data[i]):
                i += 1
                col += 1
            if i < len(data) and is_alpha(data[i]):
                raise_err(10, line, col, ue_part=chr(data[i]))
            num = data[start:i].decode()
            tokens.append(Token("constant", num, line, start_col))
        # Parentheses
        elif b == ord("("):
            tokens.append(Token("lparen", "(", line, col))
            i += 1
            col += 1
        elif b == ord(")"):
            tokens.append(Token("rparen", ")", line, col))
            i += 1
            col += 1
        # Punctuation
        elif b == ord(":"):
            tokens.append(Token("colon", ":", line, col))
            i += 1
            col += 1
        elif b == ord(";"):
            tokens.append(Token("semicolon", ";", line, col))
            i += 1
            col += 1
        # Assignment operator <-
        elif b == ord("<"):
            if i + 1 < len(data) and data[i + 1] == ord("-"):
                tokens.append(Token("assignment", "<-", line, col))
                i += 2
                col += 2
            else:
                raise_err(10, line, col, ue_part="<")
        # Single-byte arithmetic operators (+, -, *, /)
        elif is_operator(b):
            tokens.append(Token("operator", chr(b), line, col))
            i += 1
            col += 1
        # Multibyte UTF-8 sequence (emojis, unicode symbols ≡, ≢, 🪶, 🪽, etc.)
        elif b >= 128:
            start_col = col
            if (b & 0xE0) == 0xC0:
                length = 2
            elif (b & 0xF0) == 0xE0:
                length = 3
            elif (b & 0xF8) == 0xF0:
                length = 4
            else:
                length = 1

            if i + length > len(data):
                raise_err(10, line, col, ue_part="invalid UTF-8 sequence")

            try:
                char_str = data[i : i + length].decode("utf-8")
            except UnicodeDecodeError:
                raise_err(10, line, col, ue_part="invalid UTF-8 bytes")

            if char_str in KEYWORDS:
                tokens.append(Token(KEYWORDS[char_str], char_str, line, start_col))
            elif char_str == "🪶":
                tokens.append(Token("lbrace", "🪶", line, start_col))
            elif char_str == "🪽":
                tokens.append(Token("rbrace", "🪽", line, start_col))
            elif char_str in ("≡", "≢"):
                tokens.append(Token("comparison", char_str, line, start_col))
            else:
                raise_err(10, line, start_col, ue_part=char_str)

            i += length
            col += 1
        else:
            raise_err(10, line, col, ue_part=chr(b))

    if tokens:
        lexer_lines.append(tokens)
    return lexer_lines


# ── AST Node Hierarchy ────────────────────────────────────────────────
class Node:
    def __init__(self, line, col):
        self.line, self.col = line, col


class ProgramNode(Node):
    def __init__(self, line, col, stmts, exit_node):
        super().__init__(line, col)
        self.stmts = stmts
        self.exit = exit_node

    def dump(self, indent=0):
        print(" " * indent + "Program")
        for stmt in self.stmts:
            stmt.dump(indent + 2)
        if self.exit:
            self.exit.dump(indent + 2)


class StmtNode(Node):
    pass


class ExprNode(Node):
    pass


class DeclNode(StmtNode):
    def __init__(self, line, col, type_name: str, name: str, mutable: bool, init):
        super().__init__(line, col)
        self.type_name = type_name
        self.name = name
        self.mutable = mutable
        self.init = init

    def dump(self, indent=0):
        kind = "mut" if self.mutable else "const"
        print(" " * indent + f"Decl {self.name} {self.type_name} {kind}")
        self.init.dump(indent + 2)


class AssignNode(StmtNode):
    def __init__(self, line, col, name, value):
        super().__init__(line, col)
        self.name = name
        self.value = value

    def dump(self, indent=0):
        print(" " * indent + f"Assign {self.name}")
        self.value.dump(indent + 2)


class BinOpNode(ExprNode):
    def __init__(self, line, col, op, left, right):
        super().__init__(line, col)
        self.op = op
        self.left = left
        self.right = right

    def dump(self, indent=0):
        print(" " * indent + f"BinOp {self.op}")
        self.left.dump(indent + 2)
        self.right.dump(indent + 2)


class VarNode(ExprNode):
    def __init__(self, line, col, name):
        super().__init__(line, col)
        self.name = name

    def dump(self, indent=0):
        print(" " * indent + f"Var {self.name}")


class ConstNode(ExprNode):
    def __init__(self, line, col, val):
        super().__init__(line, col)
        self.val = val

    def dump(self, indent=0):
        print(" " * indent + f"Const {self.val}")


class BoolNode(ExprNode):
    def __init__(self, line, col, val: bool):
        super().__init__(line, col)
        self.val = val

    def dump(self, indent=0):
        print(" " * indent + f"Bool {'true' if self.val else 'false'}")


class BlockNode(Node):
    def __init__(self, line, col, stmts, exit_node=None):
        super().__init__(line, col)
        self.stmts = stmts
        self.exit = exit_node

    def dump(self, indent=0):
        print(" " * indent + "Block")
        for s in self.stmts:
            s.dump(indent + 2)
        if self.exit:
            self.exit.dump(indent + 2)


class IfNode(StmtNode):
    def __init__(self, line, col, condition, then_block, else_block=None):
        super().__init__(line, col)
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block

    def dump(self, indent=0):
        print(" " * indent + "If")
        self.condition.dump(indent + 2)
        self.then_block.dump(indent + 2)
        if self.else_block:
            print(" " * indent + "Else")
            self.else_block.dump(indent + 2)


class WhileNode(StmtNode):
    def __init__(self, line, col, condition, body_block):
        super().__init__(line, col)
        self.condition = condition
        self.body_block = body_block

    def dump(self, indent=0):
        print(" " * indent + "While")
        self.condition.dump(indent + 2)
        self.body_block.dump(indent + 2)


class ExitNode(Node):
    def __init__(self, line, col, val):
        super().__init__(line, col)
        self.val = val

    def dump(self, indent=0):
        print(" " * indent + "Exit")
        self.val.dump(indent + 2)


def guarantees_exit(node):
    if node is None:
        return False
    if isinstance(node, ExitNode):
        return True
    if isinstance(node, IfNode):
        return guarantees_exit(node.then_block) and guarantees_exit(node.else_block)
    if isinstance(node, BlockNode):
        if node.exit is not None:
            return True
        return any(guarantees_exit(s) for s in node.stmts)
    return False


# ── Parser ────────────────────────────────────────────────────────────
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def eat(self):
        tok = self.peek()
        if tok:
            self.pos += 1
        return tok

    def expect(self, kind, expected_desc):
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            raise_err(f"expected {expected_desc}, found end of file", line, col)
        if tok.kind != kind:
            raise_err(f"expected {expected_desc}, got '{tok.text}'", tok.line, tok.col)
        return self.eat()

    def get_pos_info(self):
        if self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            return tok.line, tok.col
        if self.tokens:
            last = self.tokens[-1]
            return last.line, last.col + len(last.text)
        return 1, 1

    def parse_program(self):
        stmts = []
        exit_node = None
        has_exit = False

        while self.peek() is not None:
            if has_exit:
                tok = self.peek()
                raise_err(6, tok.line, tok.col)

            tok = self.peek()
            if tok.kind == "statement" and tok.text == "finish":
                exit_node = self.parse_exit()
                has_exit = True
            else:
                stmt_node = self.parse_statement()
                stmts.append(stmt_node)
                if guarantees_exit(stmt_node):
                    has_exit = True

        if not has_exit:
            line, col = self.get_pos_info()
            raise_err(5, line, col)

        first_line = stmts[0].line if stmts else (exit_node.line if exit_node else 1)
        first_col = stmts[0].col if stmts else (exit_node.col if exit_node else 1)
        return ProgramNode(first_line, first_col, stmts, exit_node)

    def parse_statement(self):
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            raise_err("expected statement, found end of file", line, col)

        if tok.kind == "specifier":
            return self.parse_decl()
        elif tok.kind == "ident":
            return self.parse_assignment()
        elif tok.kind == "keyword" and tok.text == "🐤":
            return self.parse_if()
        elif tok.kind == "keyword" and tok.text == "waddle":
            return self.parse_while()
        else:
            raise_err(f"cannot start a statement with '{tok.text}'", tok.line, tok.col)

    def parse_decl(self):
        spec_tok = self.eat()  # '🍃' | '🪨'
        mutable = (spec_tok.text == "🍃")

        name_tok = self.expect("ident", "variable name")
        self.expect("colon", "':'")

        type_tok = self.expect("typename", "type name")
        type_name = type_tok.text

        self.expect("assignment", "'<-'")
        init = self.parse_expr()
        self.expect("semicolon", "';'")

        return DeclNode(spec_tok.line, spec_tok.col, type_name, name_tok.text, mutable, init)

    def parse_assignment(self):
        var_tok = self.eat()  # ident
        self.expect("assignment", "'<-'")
        value = self.parse_expr()
        self.expect("semicolon", "';'")
        return AssignNode(var_tok.line, var_tok.col, var_tok.text, value)

    def parse_exit(self):
        exit_tok = self.eat()  # 'finish'
        val = self.parse_operand(is_exit=True)
        self.expect("semicolon", "';'")
        return ExitNode(exit_tok.line, exit_tok.col, val)


    def parse_arith(self):
        node = self.parse_term()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text in "+-":
            op_tok = self.eat()
            node = BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, self.parse_term())
        return node

    def parse_term(self):
        node = self.parse_operand()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text in "*/":
            op_tok = self.eat()
            node = BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, self.parse_operand())
        return node

    def parse_expr(self):
        node = self.parse_arith()
        if (tok := self.peek()) is not None and tok.kind == "comparison":
            op_tok = self.eat()
            right = self.parse_arith()
            if (tok2 := self.peek()) is not None and tok2.kind == "comparison":
                raise_err("multiple comparisons in one expression are not allowed", tok2.line, tok2.col)
            return BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, right)
        return node

    def parse_operand(self, is_exit=False):
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            if is_exit:
                raise_err(7, line, col)
            else:
                raise_err("expected constant or variable, found end of file", line, col)

        if tok.kind == "ident":
            self.eat()
            return VarNode(tok.line, tok.col, tok.text)
        elif tok.kind == "constant":
            self.eat()
            return ConstNode(tok.line, tok.col, tok.text)
        elif tok.kind == "bool_literal":
            self.eat()
            is_true = (tok.text in ("🪺", "true", "full"))
            return BoolNode(tok.line, tok.col, is_true)
        elif tok.kind == "lparen":
            self.eat()
            expr = self.parse_expr()
            self.expect("rparen", "')'")
            return expr
        else:
            if is_exit:
                raise_err(7, tok.line, tok.col)
            else:
                raise_err(f"expected constant or variable, got '{tok.text}'", tok.line, tok.col)

    def parse_if(self):
        if_tok = self.eat()  # '🐤'
        condition = self.parse_expr()
        then_block = self.parse_block()

        else_block = None
        tok = self.peek()
        if tok is not None and tok.kind == "keyword" and tok.text == "🦢":
            self.eat()
            else_block = self.parse_block()

        return IfNode(if_tok.line, if_tok.col, condition, then_block, else_block)

    def parse_while(self):
        while_tok = self.eat()  # 'waddle'
        condition = self.parse_expr()
        body_block = self.parse_block()
        return WhileNode(while_tok.line, while_tok.col, condition, body_block)

    def parse_block(self):
        lbrace_tok = self.expect("lbrace", "'🪶'")
        stmts = []
        exit_node = None
        has_exit = False

        while True:
            tok = self.peek()
            if tok is None:
                raise_err("block opened here is never closed", lbrace_tok.line, lbrace_tok.col)
            if tok.kind == "rbrace":
                break

            if tok.kind == "statement" and tok.text == "finish":
                if has_exit:
                    raise_err(6, tok.line, tok.col)
                exit_node = self.parse_exit()
                has_exit = True
            else:
                if has_exit:
                    raise_err(6, tok.line, tok.col)
                stmt = self.parse_statement()
                stmts.append(stmt)
                if guarantees_exit(stmt):
                    has_exit = True

        self.expect("rbrace", "'🪽'")

        if not stmts and exit_node is None:
            raise_err("block must not be empty", lbrace_tok.line, lbrace_tok.col)

        return BlockNode(lbrace_tok.line, lbrace_tok.col, stmts, exit_node)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", help="path to the .txt file with your code")
    parser.add_argument("output_path", nargs="?", default=None, help="path to the .ll file")
    parser.add_argument("--tokens", action="store_true", help="print the token stream to stdout")
    parser.add_argument("--ast", action="store_true", help="print the AST tree and exit")
    args = parser.parse_args()

    with open(args.source_path, "rb") as f:
        data = f.read()

    lexer_lines = lex(data)
    all_tokens = [tok for line in lexer_lines for tok in line]

    if args.tokens:
        for tok in all_tokens:
            print(tok.to_str())
    elif args.ast:
        p = Parser(all_tokens)
        ast_root = p.parse_program()
        ast_root.dump()


if __name__ == "__main__":
    main()

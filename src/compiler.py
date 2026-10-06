import argparse
import sys
from typing import List


# ── Error Reporting ───────────────────────────────────────────────────
def compilation_error(line: int, col: int, message: str):
    sys.stderr.write(f"compilation error: line {line}:{col}: {message}\n")
    sys.exit(1)


# ── Emoji & Symbol UTF-8 Table ─────────────────────────────────────────
class EmojiEntry:
    def __init__(self, seq: bytes, kind: str, text: str, codepoint: str, desc: str):
        self.seq = seq
        self.kind = kind
        self.text = text
        self.codepoint = codepoint
        self.desc = desc

    @property
    def utf8_hex(self) -> str:
        return " ".join(f"0x{b:02X}" for b in self.seq)


# Single source of truth for non-ASCII symbols in Duck Lang
EMOJI_UTF8_TABLE: List[EmojiEntry] = [
    EmojiEntry(b"\xF0\x9F\x90\xA5", "typename", "🐥", "U+1F425", "Integer (32-bit)"),
    EmojiEntry(b"\xF0\x9F\xA6\x86", "typename", "🦆", "U+1F986", "Integer (64-bit)"),
    EmojiEntry(b"\xF0\x9F\xA5\x9A", "typename", "🥚", "U+1F95A", "Boolean type"),
    EmojiEntry(b"\xF0\x9F\x8D\x83", "specifier", "🍃", "U+1F343", "Mutable variable"),
    EmojiEntry(b"\xF0\x9F\xAA\xA8", "specifier", "🪨", "U+1FAA8", "Constant variable"),
    EmojiEntry(b"\xF0\x9F\xAA\xBA", "bool_literal", "🪺", "U+1FABA", "Boolean true"),
    EmojiEntry(b"\xF0\x9F\xAA\xB9", "bool_literal", "🪹", "U+1FAB9", "Boolean false"),
    EmojiEntry(b"\xF0\x9F\x90\xA4", "keyword", "🐤", "U+1F424", "If keyword"),
    EmojiEntry(b"\xF0\x9F\xA6\xA2", "keyword", "🦢", "U+1F9A2", "Else keyword"),
    EmojiEntry(b"\xF0\x9F\xAA\xB6", "lbrace", "🪶", "U+1FAB6", "Block open"),
    EmojiEntry(b"\xF0\x9F\xAA\xBD", "rbrace", "🪽", "U+1FABD", "Block close"),
    EmojiEntry(b"\xE2\x89\xA1", "comparison", "≡", "U+2261", "Equal comparison"),
    EmojiEntry(b"\xE2\x89\xA2", "comparison", "≢", "U+2262", "Not equal comparison"),
]

# Sort table entries by sequence length descending
EMOJI_UTF8_TABLE.sort(key=lambda e: len(e.seq), reverse=True)

# Reserved text keywords
KEYWORD_BYTES = {
    b"waddle": "keyword",
    b"finish": "statement",
}


class Token:
    def __init__(self, kind: str, text: str, line: int, col: int):
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
    n = len(data)

    I64_MAX = 9223372036854775807

    while i < n:
        b = data[i]

        # Whitespace
        if b in (32, 9, 13):  # space, tab, \r
            i += 1
            col += 1
        elif b == 10:  # \n
            line += 1
            col = 1
            i += 1
        # Identifiers and text keywords
        elif is_alpha(b):
            start = i
            start_col = col
            while i < n and (is_alpha(data[i]) or is_digit(data[i])):
                i += 1
                col += 1
            word_bytes = data[start:i]
            kind = KEYWORD_BYTES.get(word_bytes, "ident")
            text = word_bytes.decode("ascii")
            tokens.append(Token(kind, text, line, start_col))
        # Number Literals
        elif is_digit(b):
            start = i
            start_col = col
            while i < n and is_digit(data[i]):
                i += 1
                col += 1
            if i < n and is_alpha(data[i]):
                bad_b = data[i]
                char_disp = chr(bad_b) if 32 <= bad_b <= 126 else f"0x{bad_b:02X}"
                compilation_error(line, col, f"unexpected byte '{char_disp}'")
            num_bytes = data[start:i]
            num_str = num_bytes.decode("ascii")
            stripped = num_str.lstrip("0")
            if len(stripped) > 19 or (len(stripped) > 0 and int(num_str) > I64_MAX):
                compilation_error(
                    line,
                    start_col,
                    f"integer literal {num_str} is out of range (exceeds i64 max {I64_MAX})",
                )
            tokens.append(Token("constant", num_str, line, start_col))
        # Single-byte ASCII punctuation and operators
        elif b == ord("("):
            tokens.append(Token("lparen", "(", line, col))
            i += 1
            col += 1
        elif b == ord(")"):
            tokens.append(Token("rparen", ")", line, col))
            i += 1
            col += 1
        elif b == ord(":"):
            tokens.append(Token("colon", ":", line, col))
            i += 1
            col += 1
        elif b == ord(";"):
            tokens.append(Token("semicolon", ";", line, col))
            i += 1
            col += 1
        elif b == ord("<"):
            if i + 1 < n and data[i + 1] == ord("-"):
                tokens.append(Token("assignment", "<-", line, col))
                i += 2
                col += 2
            else:
                compilation_error(line, col, "unexpected byte '<'")
        elif is_operator(b):
            tokens.append(Token("operator", chr(b), line, col))
            i += 1
            col += 1
        # Multibyte UTF-8 matching via EMOJI_UTF8_TABLE
        elif b >= 128:
            start_col = col
            matched = False
            for entry in EMOJI_UTF8_TABLE:
                if data.startswith(entry.seq, i):
                    tokens.append(Token(entry.kind, entry.text, line, start_col))
                    i += len(entry.seq)
                    col += 1
                    matched = True
                    break

            if not matched:
                # UTF-8 byte sequence error handling
                if 0x80 <= b <= 0xBF:
                    compilation_error(line, col, f"invalid UTF-8 byte 0x{b:02X}")
                elif b == 0xFF or b < 0xC0 or b > 0xF7:
                    compilation_error(line, col, f"invalid UTF-8 byte 0x{b:02X}")

                if 0xC0 <= b <= 0xDF:
                    expected_len = 2
                elif 0xE0 <= b <= 0xEF:
                    expected_len = 3
                elif 0xF0 <= b <= 0xF7:
                    expected_len = 4
                else:
                    expected_len = 1

                if i + expected_len > n:
                    compilation_error(line, col, "truncated UTF-8 sequence at end of file")

                seq_bytes = data[i : i + expected_len]
                for cb in seq_bytes[1:]:
                    if cb < 0x80 or cb > 0xBF:
                        compilation_error(line, col, f"invalid UTF-8 byte 0x{cb:02X}")

                hex_str = " ".join(f"0x{cb:02X}" for cb in seq_bytes)
                compilation_error(line, col, f"unexpected byte sequence {hex_str}")
        else:
            char_disp = chr(b) if 32 <= b <= 126 else f"0x{b:02X}"
            compilation_error(line, col, f"unexpected byte '{char_disp}'")

    return tokens


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
    def __init__(self, line: int, col: int, type_name: str, name: str, mutable: bool, init: ExprNode):
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
    def __init__(self, line: int, col: int, name: str, value: ExprNode):
        super().__init__(line, col)
        self.name = name
        self.value = value

    def dump(self, indent=0):
        print(" " * indent + f"Assign {self.name}")
        self.value.dump(indent + 2)


class BinOpNode(ExprNode):
    def __init__(self, line: int, col: int, op: str, left: ExprNode, right: ExprNode):
        super().__init__(line, col)
        self.op = op
        self.left = left
        self.right = right

    def dump(self, indent=0):
        print(" " * indent + f"BinOp {self.op}")
        self.left.dump(indent + 2)
        self.right.dump(indent + 2)


class VarNode(ExprNode):
    def __init__(self, line: int, col: int, name: str):
        super().__init__(line, col)
        self.name = name

    def dump(self, indent=0):
        print(" " * indent + f"Var {self.name}")


class ConstNode(ExprNode):
    def __init__(self, line: int, col: int, val: str):
        super().__init__(line, col)
        self.val = val

    def dump(self, indent=0):
        print(" " * indent + f"Const {self.val}")


class BoolNode(ExprNode):
    def __init__(self, line: int, col: int, val: bool):
        super().__init__(line, col)
        self.val = val

    def dump(self, indent=0):
        print(" " * indent + f"Bool {'true' if self.val else 'false'}")


class BlockNode(Node):
    def __init__(self, line: int, col: int, stmts: list):
        super().__init__(line, col)
        self.stmts = stmts

    def dump(self, indent=0):
        print(" " * indent + "Block")
        for s in self.stmts:
            s.dump(indent + 2)


class IfNode(StmtNode):
    def __init__(self, line: int, col: int, condition: ExprNode, then_block: BlockNode, else_block: BlockNode = None):
        super().__init__(line, col)
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block

    def dump(self, indent=0):
        print(" " * indent + "If")
        self.condition.dump(indent + 2)
        self.then_block.dump(indent + 2)
        if self.else_block:
            self.else_block.dump(indent + 2)


class WhileNode(StmtNode):
    def __init__(self, line: int, col: int, condition: ExprNode, body_block: BlockNode):
        super().__init__(line, col)
        self.condition = condition
        self.body_block = body_block

    def dump(self, indent=0):
        print(" " * indent + "While")
        self.condition.dump(indent + 2)
        self.body_block.dump(indent + 2)


class ExitNode(StmtNode):
    def __init__(self, line: int, col: int, val: ExprNode):
        super().__init__(line, col)
        self.val = val

    def dump(self, indent=0):
        print(" " * indent + "Exit")
        self.val.dump(indent + 2)


# ── Parser ────────────────────────────────────────────────────────────
# Grammar Rule -> Parser Function Mapping:
# program    ::= { statement } finish                       -> parse_program()
# statement  ::= var_decl | assignment | if | while         -> parse_statement()
# var_decl   ::= ( "🍃" | "🪨" ) ident ":" type "<-" expr ";"  -> parse_decl()
# assignment ::= ident "<-" expr ";"                        -> parse_assignment()
# if         ::= "🐤" expr block [ "🦢" block ]             -> parse_if()
# while      ::= "waddle" expr block                        -> parse_while()
# block      ::= "🪶" block_item { block_item } "🪽"         -> parse_block()
# finish     ::= "finish" operand ";"                       -> parse_exit()
# expr       ::= arith [ ( "≡" | "≢" ) arith ]              -> parse_expr()
# arith      ::= term { ( "+" | "-" ) term }                -> parse_arith()
# term       ::= operand { ( "*" | "/" ) operand }          -> parse_term()
# operand    ::= ident | number | "🪺" | "🪹" | "(" expr ")" -> parse_operand()
class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def eat(self) -> Token:
        tok = self.peek()
        if tok:
            self.pos += 1
        return tok

    def expect(self, kind: str, expected_desc: str) -> Token:
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, f"expected {expected_desc}, found end of file")
        if tok.kind != kind:
            compilation_error(tok.line, tok.col, f"expected {expected_desc}, got '{tok.text}'")
        return self.eat()

    def get_pos_info(self):
        if self.tokens:
            last = self.tokens[-1]
            return last.line, last.col + len(last.text)
        return 1, 1

    def parse_program(self) -> ProgramNode:
        stmts = []
        while self.peek() is not None and self.peek().text != "finish":
            stmts.append(self.parse_statement())

        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "missing finish statement")

        exit_node = self.parse_exit()
        stmts.append(exit_node)

        if self.peek() is not None:
            trailing = self.peek()
            compilation_error(trailing.line, trailing.col, "finish must be the last statement")

        first_line = stmts[0].line if stmts else 1
        first_col = stmts[0].col if stmts else 1
        return ProgramNode(first_line, first_col, stmts)

    def parse_statement(self) -> StmtNode:
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "expected statement, found end of file")

        if tok.kind == "specifier":
            return self.parse_decl()
        elif tok.kind == "ident":
            return self.parse_assignment()
        elif tok.kind == "keyword" and tok.text == "🐤":
            return self.parse_if()
        elif tok.kind == "keyword" and tok.text == "waddle":
            return self.parse_while()
        else:
            compilation_error(tok.line, tok.col, f"cannot start a statement with '{tok.text}'")

    def parse_decl(self) -> DeclNode:
        spec_tok = self.eat()  # '🍃' | '🪨'
        mutable = (spec_tok.text == "🍃")

        name_tok = self.expect("ident", "variable name")
        self.expect("colon", "':'")

        type_tok = self.expect("typename", "type name")
        type_name = type_tok.text

        self.expect("assignment", "'<-'")
        init = self.parse_expr()
        self.expect("semicolon", "';'")

        # Integer literal range check for 🐥 (i32)
        if type_name == "🐥":
            if isinstance(init, ConstNode):
                val_int = int(init.val)
                I32_MAX = 2147483647
                if val_int > I32_MAX:
                    compilation_error(
                        init.line,
                        init.col,
                        f"integer literal {init.val} is out of range for 🐥 (i32 max 2147483647)",
                    )

        return DeclNode(spec_tok.line, spec_tok.col, type_name, name_tok.text, mutable, init)

    def parse_assignment(self) -> AssignNode:
        var_tok = self.eat()  # ident
        self.expect("assignment", "'<-'")
        value = self.parse_expr()
        self.expect("semicolon", "';'")
        return AssignNode(var_tok.line, var_tok.col, var_tok.text, value)

    def parse_exit(self) -> ExitNode:
        exit_tok = self.expect("statement", "'finish'")
        val = self.parse_operand()
        self.expect("semicolon", "';'")
        return ExitNode(exit_tok.line, exit_tok.col, val)

    def parse_arith(self) -> ExprNode:
        node = self.parse_term()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text in "+-":
            op_tok = self.eat()
            node = BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, self.parse_term())
        return node

    def parse_term(self) -> ExprNode:
        node = self.parse_operand()
        while (tok := self.peek()) is not None and tok.kind == "operator" and tok.text in "*/":
            op_tok = self.eat()
            node = BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, self.parse_operand())
        return node

    def parse_expr(self) -> ExprNode:
        node = self.parse_arith()
        if (tok := self.peek()) is not None and tok.kind == "comparison":
            op_tok = self.eat()
            right = self.parse_arith()
            if (tok2 := self.peek()) is not None and tok2.kind == "comparison":
                compilation_error(tok2.line, tok2.col, "multiple comparisons in one expression are not allowed")
            return BinOpNode(op_tok.line, op_tok.col, op_tok.text, node, right)
        return node

    def parse_operand(self) -> ExprNode:
        tok = self.peek()
        if tok is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "expected constant or variable, found end of file")

        if tok.kind == "ident":
            self.eat()
            return VarNode(tok.line, tok.col, tok.text)
        elif tok.kind == "constant":
            self.eat()
            return ConstNode(tok.line, tok.col, tok.text)
        elif tok.kind == "bool_literal":
            self.eat()
            is_true = (tok.text == "🪺")
            return BoolNode(tok.line, tok.col, is_true)
        elif tok.kind == "lparen":
            self.eat()
            expr = self.parse_expr()
            self.expect("rparen", "')'")
            return expr
        else:
            compilation_error(tok.line, tok.col, f"expected constant or variable, got '{tok.text}'")

    def parse_if(self) -> IfNode:
        if_tok = self.eat()  # '🐤'
        condition = self.parse_expr()
        then_block = self.parse_block()

        else_block = None
        tok = self.peek()
        if tok is not None and tok.kind == "keyword" and tok.text == "🦢":
            self.eat()
            else_block = self.parse_block()

        return IfNode(if_tok.line, if_tok.col, condition, then_block, else_block)

    def parse_while(self) -> WhileNode:
        while_tok = self.eat()  # 'waddle'
        condition = self.parse_expr()
        body_block = self.parse_block()
        return WhileNode(while_tok.line, while_tok.col, condition, body_block)

    def parse_block(self) -> BlockNode:
        lbrace_tok = self.expect("lbrace", "'🪶'")
        stmts = []

        while True:
            tok = self.peek()
            if tok is None:
                compilation_error(lbrace_tok.line, lbrace_tok.col, "'🪶' opened here is never closed")
            if tok.kind == "rbrace":
                break

            if tok.text == "finish":
                stmts.append(self.parse_exit())
            else:
                stmts.append(self.parse_statement())

        self.expect("rbrace", "'🪽'")

        if not stmts:
            compilation_error(lbrace_tok.line, lbrace_tok.col, "block must not be empty")

        return BlockNode(lbrace_tok.line, lbrace_tok.col, stmts)


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

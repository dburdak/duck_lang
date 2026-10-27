from typing import List

try:
    from errors import compilation_error
    from lexer import Token
    from ast_nodes import (
        ASTNode,
        ProgramNode,
        StmtNode,
        ExprNode,
        DeclNode,
        AssignNode,
        BinOpNode,
        VarNode,
        ConstNode,
        BoolNode,
        BlockNode,
        IfNode,
        WhileNode,
        ExitNode,
    )
except ImportError:
    from src.errors import compilation_error
    from src.lexer import Token
    from src.ast_nodes import (
        ASTNode,
        ProgramNode,
        StmtNode,
        ExprNode,
        DeclNode,
        AssignNode,
        BinOpNode,
        VarNode,
        ConstNode,
        BoolNode,
        BlockNode,
        IfNode,
        WhileNode,
        ExitNode,
    )

# ── Type Limits Table ─────────────────────────────────────────────────
I32_MAX = 2147483647
I64_MAX = 9223372036854775807

TYPE_LIMITS = {
    "🐥": ("i32", I32_MAX),
    "🦆": ("i64", I64_MAX),
}


def literal_exceeds(text: str, max_val: int) -> bool:
    digits = text.lstrip("0") or "0"
    max_str = str(max_val)
    if len(digits) != len(max_str):
        return len(digits) > len(max_str)
    return digits > max_str


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

        # Integer literal range check for 🐥 (i32) and 🦆 (i64)
        if type_name in TYPE_LIMITS:
            type_label, limit_val = TYPE_LIMITS[type_name]
            if isinstance(init, ConstNode):
                if literal_exceeds(init.val, limit_val):
                    compilation_error(
                        init.line,
                        init.col,
                        f"integer literal {init.val} is out of range for {type_name} ({type_label} max {limit_val})",
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

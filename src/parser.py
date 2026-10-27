from typing import List
from contextlib import contextmanager

try:
    from errors import compilation_error
    from lexer import Token
    from ast_nodes import (
        ProgramNode,
        ParamNode,
        FunctionNode,
        FieldNode,
        StructNode,
        StmtNode,
        ExprNode,
        DeclNode,
        AssignNode,
        BinOpNode,
        VarNode,
        ConstNode,
        BoolNode,
        StringNode,
        FieldAccessNode,
        CallNode,
        ObjectCreateNode,
        ReadNode,
        BlockNode,
        IfNode,
        WhileNode,
        ReturnNode,
        ExitNode,
        SwapStmtNode,
        PrintStmtNode,
    )
except ImportError:
    from src.errors import compilation_error
    from src.lexer import Token
    from src.ast_nodes import (
        ProgramNode,
        ParamNode,
        FunctionNode,
        FieldNode,
        StructNode,
        StmtNode,
        ExprNode,
        DeclNode,
        AssignNode,
        BinOpNode,
        VarNode,
        ConstNode,
        BoolNode,
        StringNode,
        FieldAccessNode,
        CallNode,
        ObjectCreateNode,
        ReadNode,
        BlockNode,
        IfNode,
        WhileNode,
        ReturnNode,
        ExitNode,
        SwapStmtNode,
        PrintStmtNode,
    )


I32_MAX = 2147483647
I64_MAX = 9223372036854775807
TYPE_LIMITS = {"🐥": ("i32", I32_MAX), "🦆": ("i64", I64_MAX)}


def literal_exceeds(text: str, max_val: int) -> bool:
    digits = text.lstrip("0") or "0"
    maximum = str(max_val)
    if len(digits) != len(maximum):
        return len(digits) > len(maximum)
    return digits > maximum


class Parser:
    MAX_NESTING = 100

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.nesting_depth = 0

    @contextmanager
    def nested(self, token):
        self.nesting_depth += 1
        if self.nesting_depth > self.MAX_NESTING:
            self.nesting_depth -= 1
            compilation_error(token.line, token.col, "nesting is too deep")
        try:
            yield
        finally:
            self.nesting_depth -= 1

    def peek(self, offset=0):
        index = self.pos + offset
        return self.tokens[index] if index < len(self.tokens) else None

    def eat(self):
        token = self.peek()
        if token is not None:
            self.pos += 1
        return token

    def get_pos_info(self):
        if self.tokens:
            last = self.tokens[-1]
            return last.line, last.col + len(last.text)
        return 1, 1

    def expect(self, kind, expected_desc):
        token = self.peek()
        if token is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, f"expected {expected_desc}, found end of file")
        if token.kind != kind:
            compilation_error(token.line, token.col, f"expected {expected_desc}, got '{token.text}'")
        return self.eat()

    def parse_program(self):
        items = []
        while self.peek() is not None and self.peek().kind != "statement":
            token = self.peek()
            if token.kind == "flock":
                items.append(self.parse_struct_decl())
            elif token.kind == "hatch" and self.peek(1) is not None and self.peek(1).kind == "ident" and self.peek(2) is not None and self.peek(2).kind == "lparen":
                items.append(self.parse_func_decl())
            else:
                items.append(self.parse_statement())

        if self.peek() is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "missing finish statement")

        items.append(self.parse_exit())
        if self.peek() is not None:
            token = self.peek()
            compilation_error(token.line, token.col, "finish must be the last statement")

        first = items[0] if items else None
        return ProgramNode(first.line if first else 1, first.col if first else 1, items)

    def parse_type(self):
        token = self.peek()
        if token is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "expected type name, found end of file")
        if token.kind not in ("typename", "ident"):
            compilation_error(token.line, token.col, f"expected type name, got '{token.text}'")
        return self.eat().text

    def parse_params(self):
        params = []
        if self.peek() is not None and self.peek().kind != "rparen":
            params.append(self.parse_param())
            while self.peek() is not None and self.peek().kind == "comma":
                self.eat()
                params.append(self.parse_param())
        return params

    def parse_param(self):
        name = self.expect("ident", "parameter name")
        self.expect("colon", "':'")
        type_name = self.parse_type()
        return ParamNode(name.line, name.col, name.text, type_name)

    def parse_func_decl(self):
        token = self.expect("hatch", "'hatch'")
        name = self.expect("ident", "function name")
        params = self.parse_signature_params()
        self.expect("arrow", "'->'")
        result_type = self.parse_type()
        body = self.parse_block()
        return FunctionNode(token.line, token.col, name.text, params, result_type, body)

    def parse_signature_params(self):
        self.expect("lparen", "'('")
        params = self.parse_params()
        self.expect("rparen", "')'")
        return params

    def parse_struct_decl(self):
        token = self.expect("flock", "'flock'")
        name = self.expect("ident", "structure name")
        self.expect("lbrace", "'🪶'")
        members = []
        while self.peek() is not None and self.peek().kind != "rbrace":
            members.append(self.parse_member())
        self.expect("rbrace", "'🪽'")
        structure = StructNode(token.line, token.col, name.text, members)
        for index, field in enumerate(structure.fields):
            field.index = index
        for method in structure.methods:
            method.struct_name = name.text
        return structure

    def parse_member(self):
        specifier = self.peek()
        if specifier is None or specifier.kind not in ("specifier", "hatch"):
            if specifier is None:
                line, col = self.get_pos_info()
                compilation_error(line, col, "expected a structure member, found end of file")
            compilation_error(specifier.line, specifier.col, f"cannot start a structure member with '{specifier.text}'")
        self.eat()
        mutable = specifier.text in ("🍃", "hatch", "leaf")
        if self.peek() is not None and self.peek().kind == "hatch":
            hatch = self.eat()
            name = self.expect("ident", "member function name")
            params = self.parse_signature_params()
            self.expect("arrow", "'->'")
            result_type = self.parse_type()
            body = self.parse_block()
            return FunctionNode(hatch.line, hatch.col, name.text, params, result_type, body, mutable, None)

        name = self.expect("ident", "field name")
        self.expect("colon", "':'")
        type_name = self.parse_type()
        self.expect("semicolon", "';'")
        return FieldNode(specifier.line, specifier.col, name.text, type_name, mutable)

    def parse_statement(self) -> StmtNode:
        token = self.peek()
        if token is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "expected statement, found end of file")
        if token.kind in ("specifier", "hatch"):
            if token.kind == "hatch" and self.peek(1) is not None and self.peek(1).kind == "ident" and self.peek(2) is not None and self.peek(2).kind == "lparen":
                compilation_error(token.line, token.col, "function declarations are only allowed at the top level")
            return self.parse_decl()
        if token.kind == "ident":
            return self.parse_simple_stmt()
        if token.kind == "keyword" and token.text == "🐤":
            return self.parse_if()
        if token.kind == "keyword" and token.text in ("waddle", "🔁"):
            return self.parse_while()
        if token.kind == "print":
            return self.parse_print()
        if token.kind == "lay":
            return self.parse_return_stmt()
        compilation_error(token.line, token.col, f"cannot start a statement with '{token.text}'")

    def parse_decl(self):
        specifier = self.eat()
        mutable = specifier.text in ("🍃", "hatch", "leaf")
        name = self.expect("ident", "variable name")
        self.expect("colon", "':'")
        type_name = self.parse_type()
        self.expect("assignment", "'<-'")
        init = self.parse_expr()
        self.expect("semicolon", "';'")

        if type_name in TYPE_LIMITS and isinstance(init, ConstNode):
            type_label, maximum = TYPE_LIMITS[type_name]
            if literal_exceeds(init.val, maximum):
                compilation_error(
                    init.line,
                    init.col,
                    f"integer literal {init.val} is out of range for {type_name} ({type_label} max {maximum})",
                )
        return DeclNode(specifier.line, specifier.col, type_name, name.text, mutable, init)

    def parse_simple_stmt(self):
        first = self.parse_postfix()
        if self.peek() is not None and self.peek().kind == "assignment":
            operator = self.eat()
            value = self.parse_expr()
            self.expect("semicolon", "';'")
            return AssignNode(operator.line, operator.col, first, value)
        if self.peek() is not None and self.peek().kind == "swap":
            targets = [first]
            while self.peek() is not None and self.peek().kind == "swap":
                self.eat()
                targets.append(self.parse_swap_target())
            self.expect("semicolon", "';'")
            return SwapStmtNode(first.line, first.col, targets)
        if isinstance(first, CallNode):
            self.expect("semicolon", "';'")
            return first
        next_token = self.peek()
        if next_token is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "expected '<-', found end of file")
        compilation_error(next_token.line, next_token.col, f"expected '<-', got '{next_token.text}'")

    def parse_swap_target(self):
        token = self.peek()
        if token is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "expected variable name, found end of file")
        if token.kind != "ident":
            compilation_error(token.line, token.col, f"expected variable name, got '{token.text}'")
        return self.parse_postfix()

    def parse_print(self):
        token = self.eat()
        if self.peek() is not None and self.peek().kind == "string":
            value = self.eat()
            expr = StringNode(value.line, value.col, value.value, value.text[1:-1])
        else:
            expr = self.parse_expr()
        self.expect("semicolon", "';'")
        return PrintStmtNode(token.line, token.col, expr)

    def parse_return_stmt(self):
        token = self.eat()
        value = self.parse_expr()
        self.expect("semicolon", "';'")
        return ReturnNode(token.line, token.col, value)

    def parse_exit(self):
        token = self.expect("statement", "'finish'")
        value = self.parse_expr()
        self.expect("semicolon", "';'")
        return ExitNode(token.line, token.col, value)

    def parse_if(self):
        token = self.eat()
        condition = self.parse_expr()
        then_block = self.parse_block()
        else_block = None
        if self.peek() is not None and self.peek().kind == "keyword" and self.peek().text == "🦢":
            self.eat()
            else_block = self.parse_block()
        return IfNode(token.line, token.col, condition, then_block, else_block)

    def parse_while(self):
        token = self.eat()
        condition = self.parse_expr()
        body = self.parse_block()
        return WhileNode(token.line, token.col, condition, body)

    def parse_block(self):
        opening = self.expect("lbrace", "'🪶'")
        with self.nested(opening):
            stmts = []
            while True:
                token = self.peek()
                if token is None:
                    compilation_error(opening.line, opening.col, "'🪶' opened here is never closed")
                if token.kind == "rbrace":
                    break
                if token.kind == "statement":
                    stmts.append(self.parse_exit())
                else:
                    stmts.append(self.parse_statement())
            self.expect("rbrace", "'🪽'")
            if not stmts:
                compilation_error(opening.line, opening.col, "block must not be empty")
            return BlockNode(opening.line, opening.col, stmts)

    def parse_expr(self):
        node = self.parse_arith()
        if self.peek() is not None and self.peek().kind == "comparison":
            operator = self.eat()
            right = self.parse_arith()
            if self.peek() is not None and self.peek().kind == "comparison":
                token = self.peek()
                compilation_error(token.line, token.col, "multiple comparisons in one expression are not allowed")
            return BinOpNode(operator.line, operator.col, operator.text, node, right)
        return node

    def parse_arith(self):
        node = self.parse_term()
        while self.peek() is not None and self.peek().kind == "operator" and self.peek().text in "+-":
            operator = self.eat()
            node = BinOpNode(operator.line, operator.col, operator.text, node, self.parse_term())
        return node

    def parse_term(self):
        node = self.parse_postfix()
        while self.peek() is not None and self.peek().kind == "operator" and self.peek().text in "*/":
            operator = self.eat()
            node = BinOpNode(operator.line, operator.col, operator.text, node, self.parse_postfix())
        return node

    def parse_postfix(self):
        node = self.parse_primary()
        while self.peek() is not None:
            if self.peek().kind == "dot":
                self.eat()
                name = self.expect("ident", "member name")
                node = FieldAccessNode(name.line, name.col, node, name.text)
            elif self.peek().kind == "lparen":
                args = self.parse_call_args()
                member_call = isinstance(node, FieldAccessNode)
                node = CallNode(node.line, node.col, node, args, member_call)
            else:
                break
        return node

    def parse_call_args(self):
        opening = self.expect("lparen", "'('")
        with self.nested(opening):
            args = []
            if self.peek() is not None and self.peek().kind != "rparen":
                args.append(self.parse_expr())
                while self.peek() is not None and self.peek().kind == "comma":
                    self.eat()
                    args.append(self.parse_expr())
            self.expect("rparen", "')'")
            return args

    def parse_primary(self):
        token = self.peek()
        if token is None:
            line, col = self.get_pos_info()
            compilation_error(line, col, "expected constant or variable, found end of file")
        if token.kind == "ident":
            self.eat()
            if self.peek() is not None and self.peek().kind == "object_lbrace":
                return self.parse_object_creation(token)
            return VarNode(token.line, token.col, token.text)
        if token.kind == "constant":
            self.eat()
            return ConstNode(token.line, token.col, token.text)
        if token.kind == "bool_literal":
            self.eat()
            return BoolNode(token.line, token.col, token.text in ("🪺", "nest_full"))
        if token.kind == "string":
            self.eat()
            return StringNode(token.line, token.col, token.value, token.text[1:-1])
        if token.kind == "read":
            self.eat()
            type_name = self.parse_type()
            return ReadNode(token.line, token.col, type_name)
        if token.kind == "lparen":
            with self.nested(token):
                self.eat()
                expr = self.parse_expr()
                self.expect("rparen", "')'")
                return expr
        compilation_error(token.line, token.col, f"expected constant or variable, got '{token.text}'")

    def parse_object_creation(self, name):
        opening = self.expect("object_lbrace", "'{'")
        with self.nested(opening):
            fields = [self.parse_object_field()]
            while self.peek() is not None and self.peek().kind == "comma":
                self.eat()
                fields.append(self.parse_object_field())
            self.expect("object_rbrace", "'}'")
            return ObjectCreateNode(name.line, name.col, name.text, fields)

    def parse_object_field(self):
        name = self.expect("ident", "field name")
        self.expect("colon", "':'")
        value = self.parse_expr()
        return name.text, value

class ASTNode:
    def __init__(self, line: int, col: int):
        self.line = line
        self.col = col


class ProgramNode(ASTNode):
    def __init__(self, line: int, col: int, stmts: list):
        super().__init__(line, col)
        self.stmts = stmts

    def dump(self, indent=0):
        print(" " * indent + "Program")
        for stmt in self.stmts:
            stmt.dump(indent + 2)


class StmtNode(ASTNode):
    pass


class ExprNode(ASTNode):
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


class BlockNode(ASTNode):
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


class SwapStmtNode(StmtNode):
    def __init__(self, line: int, col: int, targets: list):
        super().__init__(line, col)
        self.targets = targets

    def dump(self, indent=0):
        print(" " * indent + f"Swap {' '.join(self.targets)}")


class PrintStmtNode(StmtNode):
    def __init__(self, line: int, col: int, expr: ExprNode):
        super().__init__(line, col)
        self.expr = expr

    def dump(self, indent=0):
        print(" " * indent + "Print")
        self.expr.dump(indent + 2)


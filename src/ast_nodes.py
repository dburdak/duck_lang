class ASTNode:
    def __init__(self, line: int, col: int):
        self.line = line
        self.col = col


class ProgramNode(ASTNode):
    def __init__(self, line: int, col: int, items: list):
        super().__init__(line, col)
        self.items = items
        self.stmts = items

    def dump(self, indent=0):
        print(" " * indent + "Program")
        for item in self.items:
            item.dump(indent + 2)


class StmtNode(ASTNode):
    pass


class ExprNode(ASTNode):
    def __init__(self, line: int, col: int):
        super().__init__(line, col)
        self.inferred_type = None


class ParamNode(ASTNode):
    def __init__(self, line: int, col: int, name: str, type_name: str):
        super().__init__(line, col)
        self.name = name
        self.type_name = type_name

    def dump(self, indent=0):
        print(" " * indent + f"Parameter {self.name} {self.type_name}")


class FunctionNode(ASTNode):
    def __init__(self, line, col, name, params, result_type, body, mutable=None, struct_name=None):
        super().__init__(line, col)
        self.name = name
        self.params = params
        self.result_type = result_type
        self.body = body
        self.mutable = mutable
        self.struct_name = struct_name
        self.assigns_field = False

    def dump(self, indent=0):
        prefix = "MemberFunction" if self.struct_name else "Function"
        flag = "mut" if self.mutable else "const" if self.mutable is not None else ""
        suffix = f" {flag}" if flag else ""
        if self.struct_name:
            suffix += f" assigns_field={self.assigns_field}"
        print(" " * indent + f"{prefix} {self.name} -> {self.result_type}{suffix}")
        for param in self.params:
            param.dump(indent + 2)
        self.body.dump(indent + 2)


class FieldNode(ASTNode):
    def __init__(self, line, col, name, type_name, mutable):
        super().__init__(line, col)
        self.name = name
        self.type_name = type_name
        self.mutable = mutable
        self.index = -1
        self.kind = "field"
        self.address = None

    def dump(self, indent=0):
        flag = "mut" if self.mutable else "const"
        print(" " * indent + f"Field {self.name} {self.type_name} {flag} index={self.index}")


class StructNode(ASTNode):
    def __init__(self, line, col, name, members):
        super().__init__(line, col)
        self.name = name
        self.members = members
        self.fields = [member for member in members if isinstance(member, FieldNode)]
        self.methods = [member for member in members if isinstance(member, FunctionNode)]

    def dump(self, indent=0):
        print(" " * indent + f"Struct {self.name}")
        for member in self.members:
            member.dump(indent + 2)


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
    def __init__(self, line: int, col: int, target: ExprNode, value: ExprNode):
        super().__init__(line, col)
        self.target = target
        self.name = target.name if isinstance(target, VarNode) else None
        self.value = value

    def dump(self, indent=0):
        target_name = self.name if self.name is not None else "Field"
        print(" " * indent + f"Assign {target_name}")
        if self.name is None:
            self.target.dump(indent + 2)
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
        self.symbol = None

    def dump(self, indent=0):
        print(" " * indent + f"Var {self.name}")


class ConstNode(ExprNode):
    def __init__(self, line: int, col: int, val: str):
        super().__init__(line, col)
        self.val = val

    def dump(self, indent=0):
        print(" " * indent + f"Const {self.val}")


class FieldAccessNode(ExprNode):
    def __init__(self, line, col, base, name):
        super().__init__(line, col)
        self.base = base
        self.name = name
        self.field = None

    def dump(self, indent=0):
        print(" " * indent + f"FieldAccess {self.name}")
        self.base.dump(indent + 2)


class CallNode(ExprNode):
    def __init__(self, line, col, callee, args, member_call=False):
        super().__init__(line, col)
        self.callee = callee
        self.args = args
        self.member_call = member_call
        self.chain_ends_in_member_call = member_call
        self.function = None

    def dump(self, indent=0):
        kind = "MemberCall" if self.member_call else "Call"
        print(
            " " * indent
            + f"{kind} arguments={len(self.args)} chain_ends_in_member_call={self.chain_ends_in_member_call}"
        )
        self.callee.dump(indent + 2)
        for arg in self.args:
            arg.dump(indent + 2)


class ObjectCreateNode(ExprNode):
    def __init__(self, line, col, type_name, fields):
        super().__init__(line, col)
        self.type_name = type_name
        self.fields = fields

    def dump(self, indent=0):
        print(" " * indent + f"ObjectCreate {self.type_name}")
        for name, value in self.fields:
            print(" " * (indent + 2) + f"Initializer {name}")
            value.dump(indent + 4)


class ReadNode(ExprNode):
    def __init__(self, line, col, type_name):
        super().__init__(line, col)
        self.type_name = type_name

    def dump(self, indent=0):
        print(" " * indent + f"Read {self.type_name}")


class StringNode(ExprNode):
    def __init__(self, line, col, value: bytes, source_text=None):
        super().__init__(line, col)
        self.value = value
        self.source_text = source_text

    def dump(self, indent=0):
        shown = self.source_text if self.source_text is not None else "".join(chr(byte) for byte in self.value)
        print(" " * indent + f'String "{shown}"')


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
        for stmt in self.stmts:
            stmt.dump(indent + 2)


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


class ReturnNode(StmtNode):
    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value

    def dump(self, indent=0):
        print(" " * indent + "Return")
        self.value.dump(indent + 2)


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
        def display(target):
            if isinstance(target, VarNode):
                return target.name
            if isinstance(target, FieldAccessNode):
                return display(target.base) + "." + target.name
            return "<temporary>"
        print(" " * indent + f"Swap {' '.join(display(target) for target in self.targets)}")


class PrintStmtNode(StmtNode):
    def __init__(self, line: int, col: int, expr: ExprNode):
        super().__init__(line, col)
        self.expr = expr

    def dump(self, indent=0):
        print(" " * indent + "Print")
        self.expr.dump(indent + 2)

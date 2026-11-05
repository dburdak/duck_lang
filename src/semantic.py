try:
    from errors import compilation_error
    from ast_nodes import (
        ProgramNode,
        StmtNode,
        FunctionNode,
        StructNode,
        FieldNode,
        ParamNode,
        DeclNode,
        ExprStmtNode,
        InlineExprNode,
        AssignNode,
        BinOpNode,
        VarNode,
        ConstNode,
        BoolNode,
        StringNode,
        FieldAccessNode,
        CallNode,
        ObjectCreateNode,
        RaftLiteralNode,
        RaftType,
        IndexNode,
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
    from src.ast_nodes import (
        ProgramNode,
        StmtNode,
        FunctionNode,
        StructNode,
        FieldNode,
        ParamNode,
        DeclNode,
        ExprStmtNode,
        InlineExprNode,
        AssignNode,
        BinOpNode,
        VarNode,
        ConstNode,
        BoolNode,
        StringNode,
        FieldAccessNode,
        CallNode,
        ObjectCreateNode,
        RaftLiteralNode,
        RaftType,
        IndexNode,
        ReadNode,
        BlockNode,
        IfNode,
        WhileNode,
        ReturnNode,
        ExitNode,
        SwapStmtNode,
        PrintStmtNode,
    )


I32 = "🐥"
I64 = "🦆"
BOOL = "🥚"
INTEGER_TYPES = (I32, I64)
BUILTIN_TYPES = (I32, I64, BOOL)
I32_MAX = 2147483647
I64_MAX = 9223372036854775807
MAX_RAFT_BYTES = 1024 * 1024
BUILTIN_TYPE_BYTES = {I32: 4, I64: 8, BOOL: 1}


class VariableSymbol:
    def __init__(self, name, type_name, mutable, node, kind):
        self.name = name
        self.type_name = type_name
        self.mutable = mutable
        self.node = node
        self.kind = kind
        self.address = None
        self.constant_value = None


class FunctionSymbol:
    def __init__(self, node, owner=None):
        self.node = node
        self.name = node.name
        self.param_types = [param.type_name for param in node.params]
        self.result_type = node.result_type
        self.owner = owner


class StructureSymbol:
    def __init__(self, node):
        self.node = node
        self.name = node.name
        self.fields = {}
        self.methods = {}


class SemanticAnalyzer:
    def __init__(self, program: ProgramNode):
        self.program = program
        self.structs = {}
        self.functions = {}
        self.globals = {}
        self.scopes = []
        self.current_function = None
        self.current_struct = None
        self.return_type = None
        self.in_global_scope = False
        self.global_positions = {}
        self.current_item_position = None

    def error(self, node, message):
        compilation_error(node.line, node.col, message)

    def analyze(self):
        self.collect_declarations()
        self.analyze_globals()
        for index, item in enumerate(self.program.items):
            if isinstance(item, FunctionNode):
                self.analyze_function(item, item_position=index)
            elif isinstance(item, StructNode):
                for method in item.methods:
                    self.analyze_function(method, item.name, index)
        return self.program

    def collect_declarations(self):
        for item in self.program.items:
            if isinstance(item, StructNode):
                if item.name in self.structs:
                    self.error(item, f"structure '{item.name}' is already declared")
                self.structs[item.name] = StructureSymbol(item)
                item.symbol = self.structs[item.name]

        for name, structure in self.structs.items():
            for index, field in enumerate(structure.node.fields):
                self.validate_type(field.type_name, field)
                if isinstance(field.type_name, RaftType):
                    self.error(field, "raft fields are not supported")
                if field.name in structure.fields:
                    self.error(field, f"field '{field.name}' is already declared in structure '{name}'")
                field.index = index
                structure.fields[field.name] = field
            for method in structure.node.methods:
                self.validate_function_signature(method)
                if method.name in structure.methods:
                    self.error(method, f"member function '{method.name}' is already declared in structure '{name}'")
                method.struct_name = name
                symbol = FunctionSymbol(method, structure)
                method.symbol = symbol
                structure.methods[method.name] = symbol
        self.validate_struct_cycles()

        for item in self.program.items:
            if isinstance(item, FunctionNode) and item.struct_name is None:
                self.validate_function_signature(item)
                if item.name in self.functions:
                    self.error(item, f"function '{item.name}' is already declared")
                symbol = FunctionSymbol(item)
                item.symbol = symbol
                self.functions[item.name] = symbol

    def validate_type(self, type_name, node):
        if isinstance(type_name, RaftType):
            if type_name.element_type not in BUILTIN_TYPES:
                self.error(node, f"invalid raft type '{type_name}'")
            return
        if type_name not in BUILTIN_TYPES and type_name not in self.structs:
            self.error(node, f"unknown type '{type_name}'")

    def validate_function_signature(self, function):
        for param in function.params:
            self.validate_type(param.type_name, param)
            if isinstance(param.type_name, RaftType) and param.type_name.size_expr is not None:
                self.error(param, "raft function parameters must omit the size")
        self.validate_type(function.result_type, function)
        if isinstance(function.result_type, RaftType):
            self.error(function, "functions cannot return raft values")
        seen = set()
        for param in function.params:
            if param.name in seen:
                self.error(param, f"parameter '{param.name}' is already declared")
            seen.add(param.name)

    def validate_struct_cycles(self):
        visiting = set()
        visited = set()

        def visit(structure, path):
            if structure.name in visiting:
                field = path[-1]
                self.error(field, f"structure '{structure.name}' contains a recursive by-value field")
            if structure.name in visited:
                return
            visiting.add(structure.name)
            for field in structure.node.fields:
                child = self.structs.get(field.type_name)
                if child is not None:
                    visit(child, path + [field])
            visiting.remove(structure.name)
            visited.add(structure.name)

        for structure in self.structs.values():
            visit(structure, [])

    def analyze_globals(self):
        self.scopes = []
        self.current_function = None
        self.current_struct = None
        self.in_global_scope = True
        items = self.program.items
        for index, item in enumerate(items):
            if isinstance(item, DeclNode):
                self.analyze_decl(item, self.globals)
                self.global_positions[item.name] = index
            elif isinstance(item, (StmtNode, CallNode)):
                if isinstance(item, ExitNode):
                    self.check_exit(item)
                else:
                    self.analyze_statement(item)
        self.in_global_scope = False

    def analyze_function(self, function, struct_name=None, item_position=None):
        self.current_function = function
        self.current_struct = self.structs[struct_name] if struct_name else None
        self.return_type = function.result_type
        self.current_item_position = item_position
        self.scopes = [{}]
        for param in function.params:
            symbol = VariableSymbol(param.name, param.type_name, False, param, "parameter")
            param.symbol = symbol
            self.scopes[0][param.name] = symbol
        self.analyze_block(function.body, create_scope=False)
        if not self.block_returns(function.body):
            self.error(function, f"function '{function.name}' can leave without a value")
        self.current_function = None
        self.current_struct = None
        self.return_type = None
        self.current_item_position = None

    def block_returns(self, block):
        for stmt in block.stmts:
            if isinstance(stmt, (ReturnNode, ExitNode)):
                return True
            if isinstance(stmt, IfNode) and stmt.else_block is not None:
                if self.block_returns(stmt.then_block) and self.block_returns(stmt.else_block):
                    return True
            if isinstance(stmt, BlockNode) and self.block_returns(stmt):
                return True
        return False

    def analyze_block(self, block, create_scope=True):
        if create_scope:
            self.scopes.append({})
        for stmt in block.stmts:
            self.analyze_statement(stmt)
        if create_scope:
            self.scopes.pop()

    def analyze_statement(self, stmt):
        if isinstance(stmt, DeclNode):
            self.analyze_decl(stmt, self.scopes[-1] if self.scopes else self.globals)
        elif isinstance(stmt, ExprStmtNode):
            self.check_expr(stmt.expr)
        elif isinstance(stmt, AssignNode):
            target_type, mutable = self.analyze_lvalue(stmt.target)
            targets_field = self.current_function is not None and self.current_struct is not None and self.target_reaches_field(stmt.target)
            if targets_field and self.current_function.mutable is False:
                self.error(stmt, "constant member function cannot assign fields")
            if not mutable:
                self.error(stmt.target, "cannot assign to an immutable variable or field")
            value_type = self.check_expr(stmt.value, target_type)
            if value_type != target_type:
                self.error(stmt.value, f"cannot assign value of type '{value_type}' to '{target_type}'")
            self.check_raft_size_compatibility(target_type, value_type, stmt.value)
            if targets_field:
                self.current_function.assigns_field = True
        elif isinstance(stmt, SwapStmtNode):
            target_types = []
            for target in stmt.targets:
                type_name, mutable = self.analyze_lvalue(target)
                if not mutable:
                    self.error(target, "cannot swap an immutable variable or field")
                target_types.append(type_name)
            if any(type_name != target_types[0] for type_name in target_types[1:]):
                self.error(stmt, "swap targets must have the same type")
            for type_name in target_types[1:]:
                self.check_raft_size_compatibility(target_types[0], type_name, stmt)
        elif isinstance(stmt, CallNode):
            self.check_expr(stmt)
        elif isinstance(stmt, PrintStmtNode):
            type_name = self.check_expr(stmt.expr)
            if type_name not in BUILTIN_TYPES and type_name not in self.structs and type_name != "string":
                self.error(stmt.expr, f"cannot print value of type '{type_name}'")
        elif isinstance(stmt, IfNode):
            if self.check_expr(stmt.condition) != BOOL:
                self.error(stmt.condition, "if condition must have type '🥚'")
            self.analyze_block(stmt.then_block)
            if stmt.else_block:
                self.analyze_block(stmt.else_block)
        elif isinstance(stmt, WhileNode):
            if self.check_expr(stmt.condition) != BOOL:
                self.error(stmt.condition, "while condition must have type '🥚'")
            self.analyze_block(stmt.body_block)
        elif isinstance(stmt, ReturnNode):
            if self.current_function is None:
                self.error(stmt, "lay is only allowed inside a function")
            message = (
                f"function '{self.function_label(self.current_function)}' returns "
                f"{self.return_type}, but 'lay' value has type {{type_name}}"
            )
            result_type = self.check_expr(stmt.value, self.return_type, message)
            if result_type != self.return_type:
                self.error(stmt.value, f"returned value has type '{result_type}', expected '{self.return_type}'")
        elif isinstance(stmt, ExitNode):
            self.check_exit(stmt)

    def analyze_decl(self, decl, scope):
        self.validate_type(decl.type_name, decl)
        if isinstance(decl.type_name, RaftType):
            if decl.type_name.size_expr is None:
                self.error(decl, "raft variable declarations must specify a size")
            size_type = self.check_expr(decl.type_name.size_expr)
            if size_type not in INTEGER_TYPES:
                self.error(decl.type_name.size_expr, "raft size must have an integer type")
            known_size = self.known_integer_value(decl.type_name.size_expr)
            element_bytes = BUILTIN_TYPE_BYTES[decl.type_name.element_type]
            max_elements = MAX_RAFT_BYTES // element_bytes
            if known_size is not None:
                if known_size <= 0:
                    self.error(decl.type_name.size_expr, "raft size must be greater than zero")
                if known_size > max_elements:
                    self.error(
                        decl.type_name.size_expr,
                        f"raft size exceeds the {MAX_RAFT_BYTES}-byte limit",
                    )
                decl.type_name.static_size = known_size
        if decl.name in scope:
            self.error(decl, f"variable '{decl.name}' is already declared in this scope")
        init_type = self.check_expr(decl.init, decl.type_name)
        if init_type != decl.type_name:
            self.error(decl.init, f"initializer has type '{init_type}', expected '{decl.type_name}'")
        self.check_raft_size_compatibility(decl.type_name, init_type, decl.init)
        symbol = VariableSymbol(decl.name, decl.type_name, decl.mutable, decl, "global" if scope is self.globals else "local")
        if not decl.mutable:
            symbol.constant_value = self.known_integer_value(decl.init)
        decl.symbol = symbol
        scope[decl.name] = symbol
        if scope is self.globals:
            self.globals[decl.name] = symbol

    def lookup_variable(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        if self.current_struct and name in self.current_struct.fields:
            return self.current_struct.fields[name]
        symbol = self.globals.get(name)
        if (
            symbol is not None
            and self.current_function is not None
            and self.global_positions.get(name, -1) >= self.current_item_position
        ):
            return None
        return symbol

    def check_expr(self, expr, expected=None, mismatch_message=None):
        if isinstance(expr, InlineExprNode):
            self.scopes.append({})
            for statement in expr.statements:
                self.analyze_statement(statement)
            type_name = self.check_expr(expr.value, expr.return_type)
            self.scopes.pop()
        elif isinstance(expr, ConstNode):
            if expected in INTEGER_TYPES:
                type_name = expected
            elif self.literal_fits(expr.val, I32_MAX):
                type_name = I32
            elif self.literal_fits(expr.val, I64_MAX):
                type_name = I64
            else:
                self.error(expr, f"integer literal {expr.val} is out of range for 🦆 (i64 max {I64_MAX})")
            maximum = I32_MAX if type_name == I32 else I64_MAX
            digits = expr.val.lstrip("0") or "0"
            if len(digits) > len(str(maximum)) or (len(digits) == len(str(maximum)) and digits > str(maximum)):
                self.error(expr, f"integer literal {expr.val} is out of range for {type_name}")
        elif isinstance(expr, BoolNode):
            type_name = BOOL
        elif isinstance(expr, StringNode):
            type_name = "string"
        elif isinstance(expr, ReadNode):
            self.validate_type(expr.type_name, expr)
            if expr.type_name not in INTEGER_TYPES:
                self.error(expr, "read requires an integer type")
            type_name = expr.type_name
        elif isinstance(expr, VarNode):
            symbol = self.lookup_variable(expr.name)
            if symbol is None:
                self.error(expr, f"undeclared name '{expr.name}'")
            expr.symbol = symbol
            type_name = symbol.type_name
        elif isinstance(expr, FieldAccessNode):
            base_type = self.check_expr(expr.base)
            structure = self.structs.get(base_type)
            if structure is None:
                self.error(expr, f"type '{base_type}' has no fields")
            field = structure.fields.get(expr.name)
            if field is None:
                self.error(expr, f"structure '{base_type}' has no field '{expr.name}'")
            expr.field = field
            type_name = field.type_name
        elif isinstance(expr, RaftLiteralNode):
            if not isinstance(expected, RaftType):
                self.error(expr, "raft literal needs an expected raft type")
            if not expr.elements and expected.size_expr is None:
                self.error(expr, "an empty raft literal needs an expected size")
            max_elements = MAX_RAFT_BYTES // BUILTIN_TYPE_BYTES[expected.element_type]
            if len(expr.elements) > max_elements:
                self.error(expr, f"raft literal exceeds the {MAX_RAFT_BYTES}-byte limit")
            if expr.elements and expected.static_size is not None and len(expr.elements) != expected.static_size:
                self.error(expr, f"raft literal has {len(expr.elements)} elements, expected {expected.static_size}")
            for index, element in enumerate(expr.elements, 1):
                element_type = self.check_expr(element, expected.element_type)
                if element_type != expected.element_type:
                    self.error(
                        element,
                        f"raft element {index} expects '{expected.element_type}', got '{element_type}'",
                    )
            type_name = expected
        elif isinstance(expr, IndexNode):
            base_type = self.check_expr(expr.base)
            if not isinstance(base_type, RaftType):
                self.error(expr, f"value of type '{base_type}' cannot be indexed")
            index_type = self.check_expr(expr.index)
            if index_type not in INTEGER_TYPES:
                self.error(expr.index, "raft index must have an integer type")
            known_index = self.known_integer_value(expr.index)
            if known_index is not None:
                if base_type.static_size is not None and (known_index < 0 or known_index >= base_type.static_size):
                    self.error(
                        expr.index,
                        f"constant raft index {known_index} is out of bounds for size {base_type.static_size}",
                    )
                if base_type.static_size is not None:
                    expr.known_index = known_index
            type_name = base_type.element_type
        elif isinstance(expr, ObjectCreateNode):
            structure = self.structs.get(expr.type_name)
            if structure is None:
                self.error(expr, f"unknown structure '{expr.type_name}'")
            initialized = set()
            for name, value in expr.fields:
                field = structure.fields.get(name)
                if field is None:
                    self.error(expr, f"structure '{expr.type_name}' has no field '{name}'")
                if name in initialized:
                    self.error(expr, f"field '{name}' is initialized more than once")
                initialized.add(name)
                value_type = self.check_expr(value, field.type_name)
                if value_type != field.type_name:
                    self.error(value, f"field '{name}' expects '{field.type_name}', got '{value_type}'")
            missing = [field.name for field in structure.node.fields if field.name not in initialized]
            if missing:
                self.error(expr, f"missing initializer for field '{missing[0]}'")
            type_name = expr.type_name
        elif isinstance(expr, CallNode):
            type_name = self.check_call(expr)
        elif isinstance(expr, BinOpNode):
            type_name = self.check_binary(expr, expected)
        else:
            self.error(expr, "unsupported expression")
        expr.inferred_type = type_name
        if expected is not None and type_name != expected:
            message = mismatch_message.format(type_name=type_name) if mismatch_message else f"expected value of type '{expected}', got '{type_name}'"
            self.error(expr, message)
        return type_name

    def literal_fits(self, text, maximum):
        digits = text.lstrip("0") or "0"
        limit = str(maximum)
        return len(digits) < len(limit) or (len(digits) == len(limit) and digits <= limit)

    def check_raft_size_compatibility(self, expected, actual, node):
        if (
            isinstance(expected, RaftType)
            and isinstance(actual, RaftType)
            and expected.static_size is not None
            and actual.static_size is not None
            and expected.static_size != actual.static_size
        ):
            self.error(node, "raft sizes do not match")

    def known_integer_value(self, expr):
        if isinstance(expr, ConstNode):
            return int(expr.val)
        if isinstance(expr, VarNode) and expr.symbol is not None:
            return getattr(expr.symbol, "constant_value", None)
        if not isinstance(expr, BinOpNode) or expr.op not in ("+", "-", "*", "/"):
            return None
        left = self.known_integer_value(expr.left)
        right = self.known_integer_value(expr.right)
        if left is None or right is None:
            return None
        if expr.op == "+":
            value = left + right
        elif expr.op == "-":
            value = left - right
        elif expr.op == "*":
            value = left * right
        else:
            if right == 0:
                return None
            value = (abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1)
        if expr.inferred_type in INTEGER_TYPES:
            bits = 32 if expr.inferred_type == I32 else 64
            if value < -(1 << (bits - 1)) or value >= (1 << (bits - 1)):
                return None
        return value

    def check_binary(self, expr, expected):
        if expr.op in ("+", "-", "*", "/"):
            if isinstance(expr.left, ConstNode) and isinstance(expr.right, ConstNode):
                left_type = self.check_expr(expr.left, expected)
                right_type = self.check_expr(expr.right, left_type)
            elif isinstance(expr.left, ConstNode):
                right_type = self.check_expr(expr.right)
                left_type = self.check_expr(expr.left, right_type)
            else:
                left_type = self.check_expr(expr.left)
                right_type = self.check_expr(expr.right, left_type if isinstance(expr.right, ConstNode) else None)
            if left_type not in INTEGER_TYPES or right_type != left_type:
                self.error(expr, "arithmetic operands must have the same integer type")
            return left_type
        if isinstance(expr.left, ConstNode) and isinstance(expr.right, ConstNode):
            right_type = self.check_expr(expr.right, expected)
            left_type = self.check_expr(expr.left, right_type)
        elif isinstance(expr.left, ConstNode):
            right_type = self.check_expr(expr.right)
            left_type = self.check_expr(expr.left, right_type)
        else:
            left_type = self.check_expr(expr.left)
            right_type = self.check_expr(expr.right, left_type if isinstance(expr.right, ConstNode) else None)
        if left_type != right_type:
            self.error(expr, "comparison operands must have the same type")
        if expr.op in ("≡", "≢") and left_type in BUILTIN_TYPES:
            return BOOL
        self.error(expr, "comparison is not defined for these operands")

    def check_call(self, call):
        if isinstance(call.callee, FieldAccessNode):
            receiver = call.callee.base
            receiver_type = self.check_expr(receiver)
            structure = self.structs.get(receiver_type)
            method = structure.methods.get(call.callee.name) if structure else None
            if method is None:
                self.error(call.callee, f"structure '{receiver_type}' has no method '{call.callee.name}'")
            call.function = method
            if method.node.mutable:
                if not self.is_mutable_receiver(receiver):
                    self.error(call, f"mutating method '{method.name}' requires a mutable object")
                if self.current_function and self.current_struct and self.current_function.mutable is False:
                    self.error(call, "constant member function cannot call a mutating method")
        elif isinstance(call.callee, VarNode):
            method = None
            if self.current_struct:
                method = self.current_struct.methods.get(call.callee.name)
            function = self.functions.get(call.callee.name)
            if method is not None and function is None:
                call.function = method
                call.member_call = True
                call.chain_ends_in_member_call = True
                call.callee.symbol = method
                if method.node.mutable and self.current_function and self.current_function.mutable is False:
                    self.error(call, "constant member function cannot call a mutating method")
            elif function is not None:
                call.function = function
            else:
                self.error(call.callee, f"unknown function '{call.callee.name}'")
        else:
            self.error(call.callee, "call target must be a function or member function")

        signature = call.function
        function_name = self.function_label(signature)
        if len(call.args) != len(signature.param_types):
            self.error(call, f"function '{function_name}' expects {len(signature.param_types)} arguments, got {len(call.args)}")
        for index, (arg, param_type) in enumerate(zip(call.args, signature.param_types), 1):
            message = f"argument {index} of '{function_name}' expects {param_type}, got {{type_name}}"
            arg_type = self.check_expr(arg, param_type, message)
            if arg_type != param_type:
                self.error(arg, message.format(type_name=arg_type))
        return signature.result_type

    def function_label(self, function):
        owner = getattr(function, "owner", None)
        if owner is not None:
            return f"{owner.name}.{function.name}"
        if getattr(function, "struct_name", None) is not None:
            return f"{function.struct_name}.{function.name}"
        return function.name

    def analyze_lvalue(self, target):
        if isinstance(target, VarNode):
            self.check_expr(target)
            if target.symbol.kind == "field":
                mutable = target.symbol.mutable and self.current_function is not None and self.current_function.mutable is True
            else:
                mutable = target.symbol.mutable
            return target.symbol.type_name, mutable
        if isinstance(target, FieldAccessNode):
            type_name = self.check_expr(target)
            return type_name, self.is_mutable_receiver(target)
        if isinstance(target, IndexNode):
            type_name = self.check_expr(target)
            return type_name, self.is_mutable_receiver(target.base)
        self.error(target, "assignment and swap targets must be variables or fields")

    def is_mutable_receiver(self, target):
        if isinstance(target, VarNode):
            self.check_expr(target)
            if target.symbol.kind == "field":
                return target.symbol.mutable and self.current_function is not None and self.current_function.mutable is True
            return target.symbol.mutable
        if isinstance(target, FieldAccessNode):
            self.check_expr(target)
            return target.field.mutable and self.is_mutable_receiver(target.base)
        if isinstance(target, IndexNode):
            self.check_expr(target)
            return self.is_mutable_receiver(target.base)
        return False

    def target_reaches_field(self, target):
        if isinstance(target, VarNode):
            return target.symbol.kind == "field"
        if isinstance(target, FieldAccessNode):
            return self.target_reaches_field(target.base)
        if isinstance(target, IndexNode):
            return self.target_reaches_field(target.base)
        return False

    def check_exit(self, exit_node):
        type_name = self.check_expr(exit_node.val)
        if type_name not in INTEGER_TYPES:
            self.error(exit_node.val, "finish value must have an integer type")

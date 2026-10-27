from llvmlite import binding, ir

try:
    from ast_nodes import (
        FunctionNode,
        StructNode,
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
    from src.ast_nodes import (
        FunctionNode,
        StructNode,
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


class CodeGenerator:
    def __init__(self, program, analyzer):
        self.program = program
        self.analyzer = analyzer
        self.module = ir.Module(name="duck_lang")
        self.module.triple = binding.get_default_triple()
        self.llvm_types = {
            "🐥": ir.IntType(32),
            "🦆": ir.IntType(64),
            "🥚": ir.IntType(1),
        }
        self.struct_types = {}
        self.function_values = {}
        self.global_values = {}
        self.builder = None
        self.alloca_builder = None
        self.entry_block = None
        self.current_function = None
        self.current_self = None
        self.current_self_struct = None
        self.printf = None
        self.scanf = None
        self.abort = None
        self.exit_function = None
        self.string_number = 0
        self.declare_runtime()
        self.create_struct_types()
        self.create_globals()
        self.declare_functions()

    def type_of(self, type_name):
        if type_name in self.llvm_types:
            return self.llvm_types[type_name]
        return self.struct_types[type_name]

    def declare_runtime(self):
        i8p = ir.IntType(8).as_pointer()
        printf_type = ir.FunctionType(ir.IntType(32), [i8p], var_arg=True)
        self.printf = ir.Function(self.module, printf_type, name="printf")
        self.scanf = ir.Function(self.module, printf_type, name="scanf")
        abort_type = ir.FunctionType(ir.VoidType(), [])
        self.abort = ir.Function(self.module, abort_type, name="abort")
        exit_type = ir.FunctionType(ir.VoidType(), [ir.IntType(32)])
        self.exit_function = ir.Function(self.module, exit_type, name="exit")

    def create_struct_types(self):
        for name in self.analyzer.structs:
            self.struct_types[name] = self.module.context.get_identified_type("duck.struct." + name)
        for name, structure in self.analyzer.structs.items():
            fields = [self.type_of(field.type_name) for field in structure.node.fields]
            self.struct_types[name].set_body(*fields)

    def create_globals(self):
        for name, symbol in self.analyzer.globals.items():
            value = ir.GlobalVariable(self.module, self.type_of(symbol.type_name), name="duck_global_" + name)
            value.initializer = ir.Constant(self.type_of(symbol.type_name), None)
            symbol.address = value
            self.global_values[symbol] = value

    def declare_functions(self):
        for item in self.program.items:
            if isinstance(item, FunctionNode):
                self.declare_function(item)
            elif isinstance(item, StructNode):
                for method in item.methods:
                    self.declare_function(method)

    def declare_function(self, function_node):
        function_symbol = function_node.symbol
        arg_types = []
        if function_symbol.owner is not None:
            arg_types.append(self.type_of(function_symbol.owner.name).as_pointer())
        arg_types.extend(self.type_of(type_name) for type_name in function_symbol.param_types)
        signature = ir.FunctionType(self.type_of(function_symbol.result_type), arg_types)
        if function_symbol.owner is None:
            name = "duck_fn_" + function_symbol.name
        else:
            name = "duck_method_" + function_symbol.owner.name + "_" + function_symbol.name
        value = ir.Function(self.module, signature, name=name)
        index = 0
        if function_symbol.owner is not None:
            value.args[0].name = "self"
            index = 1
        for param, argument in zip(function_node.params, value.args[index:]):
            argument.name = param.name
        self.function_values[function_symbol] = value

    def add_string(self, contents):
        payload = contents + b"\0"
        array_type = ir.ArrayType(ir.IntType(8), len(payload))
        global_value = ir.GlobalVariable(self.module, array_type, name=f".duck.str.{self.string_number}")
        self.string_number += 1
        global_value.linkage = "internal"
        global_value.global_constant = True
        global_value.initializer = ir.Constant(array_type, bytearray(payload))
        zero = ir.Constant(ir.IntType(32), 0)
        return self.builder.gep(global_value, [zero, zero], inbounds=True)

    def emit_printf(self, format_text, arguments=()):
        format_pointer = self.add_string(format_text)
        return self.builder.call(self.printf, [format_pointer, *arguments])

    def emit_function(self, function_node):
        function_value = self.function_values[function_node.symbol]
        entry = function_value.append_basic_block("entry")
        body = function_value.append_basic_block("body")
        self.entry_block = entry
        self.builder = ir.IRBuilder(entry)
        self.alloca_builder = ir.IRBuilder(entry)
        self.builder.branch(body)
        self.builder.position_at_end(body)
        self.current_function = function_node
        self.current_self = None
        self.current_self_struct = None
        argument_index = 0
        if function_node.symbol.owner is not None:
            self.current_self = function_value.args[0]
            self.current_self_struct = function_node.symbol.owner
            argument_index = 1
        for param, argument in zip(function_node.params, function_value.args[argument_index:]):
            address = self.alloca(param.type_name, param.name)
            param.symbol.address = address
            self.builder.store(argument, address)
        self.emit_block(function_node.body)
        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(self.type_of(function_node.result_type), None))

    def emit_main(self):
        main_type = ir.FunctionType(ir.IntType(32), [])
        main = ir.Function(self.module, main_type, name="main")
        entry = main.append_basic_block("entry")
        body = main.append_basic_block("body")
        self.entry_block = entry
        self.builder = ir.IRBuilder(entry)
        self.alloca_builder = ir.IRBuilder(entry)
        self.builder.branch(body)
        self.builder.position_at_end(body)
        self.current_function = None
        self.current_self = None
        self.current_self_struct = None
        for item in self.program.items:
            if self.builder.block.is_terminated:
                break
            if isinstance(item, (FunctionNode, StructNode)):
                continue
            self.emit_statement(item)
        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(ir.IntType(32), 0))

    def alloca(self, type_name, name):
        self.alloca_builder.position_at_start(self.entry_block)
        return self.alloca_builder.alloca(self.type_of(type_name), name=name)

    def emit_block(self, block):
        for statement in block.stmts:
            if self.builder.block.is_terminated:
                break
            self.emit_statement(statement)

    def emit_statement(self, stmt):
        if isinstance(stmt, DeclNode):
            symbol = stmt.symbol
            if symbol.kind == "global":
                address = symbol.address
            else:
                address = self.alloca(symbol.type_name, symbol.name)
                symbol.address = address
            self.builder.store(self.emit_expr(stmt.init), address)
        elif isinstance(stmt, AssignNode):
            self.builder.store(self.emit_expr(stmt.value), self.emit_lvalue(stmt.target))
        elif isinstance(stmt, SwapStmtNode):
            pointers = [self.emit_lvalue(target) for target in stmt.targets]
            values = [self.builder.load(pointer) for pointer in pointers]
            for index, pointer in enumerate(pointers):
                self.builder.store(values[(index + 1) % len(values)], pointer)
        elif isinstance(stmt, CallNode):
            self.emit_expr(stmt)
        elif isinstance(stmt, PrintStmtNode):
            self.emit_print(stmt.expr)
        elif isinstance(stmt, IfNode):
            self.emit_if(stmt)
        elif isinstance(stmt, WhileNode):
            self.emit_while(stmt)
        elif isinstance(stmt, ReturnNode):
            self.builder.ret(self.emit_expr(stmt.value))
        elif isinstance(stmt, ExitNode):
            value = self.emit_expr(stmt.val)
            if value.type.width == 64:
                value = self.builder.trunc(value, ir.IntType(32))
            if self.current_function is None:
                self.builder.ret(value)
            else:
                self.builder.call(self.exit_function, [value])
                self.builder.unreachable()

    def emit_if(self, stmt):
        function = self.builder.function
        then_block = function.append_basic_block("if.then")
        else_block = function.append_basic_block("if.else") if stmt.else_block else None
        merge_block = function.append_basic_block("if.end")
        false_target = else_block if else_block is not None else merge_block
        self.builder.cbranch(self.emit_expr(stmt.condition), then_block, false_target)
        has_merge_predecessor = else_block is None
        self.builder.position_at_end(then_block)
        self.emit_block(stmt.then_block)
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_block)
            has_merge_predecessor = True
        if else_block is not None:
            self.builder.position_at_end(else_block)
            self.emit_block(stmt.else_block)
            if not self.builder.block.is_terminated:
                self.builder.branch(merge_block)
                has_merge_predecessor = True
        self.builder.position_at_end(merge_block)
        if not has_merge_predecessor:
            self.builder.unreachable()

    def emit_while(self, stmt):
        function = self.builder.function
        condition_block = function.append_basic_block("while.cond")
        body_block = function.append_basic_block("while.body")
        end_block = function.append_basic_block("while.end")
        self.builder.branch(condition_block)
        self.builder.position_at_end(condition_block)
        self.builder.cbranch(self.emit_expr(stmt.condition), body_block, end_block)
        self.builder.position_at_end(body_block)
        self.emit_block(stmt.body_block)
        if not self.builder.block.is_terminated:
            self.builder.branch(condition_block)
        self.builder.position_at_end(end_block)

    def emit_expr(self, expr):
        if isinstance(expr, ConstNode):
            return ir.Constant(self.type_of(expr.inferred_type), int(expr.val))
        if isinstance(expr, BoolNode):
            return ir.Constant(ir.IntType(1), int(expr.val))
        if isinstance(expr, StringNode):
            return self.add_string(self.decode_string(expr.value))
        if isinstance(expr, VarNode):
            return self.builder.load(self.emit_lvalue(expr), name=expr.name + ".value")
        if isinstance(expr, FieldAccessNode):
            return self.builder.load(self.emit_lvalue(expr), name=expr.name + ".value")
        if isinstance(expr, ObjectCreateNode):
            value = ir.Constant(self.type_of(expr.type_name), None)
            fields = self.analyzer.structs[expr.type_name].fields
            for name, initializer in expr.fields:
                value = self.builder.insert_value(value, self.emit_expr(initializer), fields[name].index)
            return value
        if isinstance(expr, ReadNode):
            slot = self.alloca(expr.type_name, "read.value")
            self.builder.store(ir.Constant(self.type_of(expr.type_name), 0), slot)
            format_text = b"%d" if expr.type_name == "🐥" else b"%lld"
            self.builder.call(self.scanf, [self.add_string(format_text), slot])
            return self.builder.load(slot, name="read.result")
        if isinstance(expr, CallNode):
            return self.emit_call(expr)
        if isinstance(expr, BinOpNode):
            return self.emit_binary(expr)
        raise RuntimeError(f"unsupported expression node: {type(expr).__name__}")

    def emit_binary(self, expr):
        left = self.emit_expr(expr.left)
        right = self.emit_expr(expr.right)
        if expr.op in ("≡", "≢"):
            if left.type == ir.IntType(1):
                predicate = "==" if expr.op == "≡" else "!="
                return self.builder.icmp_unsigned(predicate, left, right)
            predicate = "==" if expr.op == "≡" else "!="
            return self.builder.icmp_signed(predicate, left, right)
        if expr.op in ("+", "-", "*"):
            return self.emit_checked_arithmetic(expr.op, left, right)
        if expr.op == "/":
            self.check_division(left, right)
            return self.builder.sdiv(left, right, name="div")
        raise RuntimeError(f"unsupported operator: {expr.op}")

    def emit_checked_arithmetic(self, operator, left, right):
        bits = left.type.width
        intrinsic_name = {"+": "sadd", "-": "ssub", "*": "smul"}[operator]
        result_type = ir.LiteralStructType([left.type, ir.IntType(1)])
        name = f"llvm.{intrinsic_name}.with.overflow.i{bits}"
        intrinsic = self.module.globals.get(name)
        if intrinsic is None:
            intrinsic = ir.Function(self.module, ir.FunctionType(result_type, [left.type, left.type]), name=name)
        pair = self.builder.call(intrinsic, [left, right], name="checked")
        overflow = self.builder.extract_value(pair, 1)
        result = self.builder.extract_value(pair, 0)
        self.branch_on_error(overflow, "arithmetic.overflow")
        return result

    def check_division(self, left, right):
        zero = ir.Constant(right.type, 0)
        is_zero = self.builder.icmp_signed("==", right, zero)
        bits = left.type.width
        minimum = ir.Constant(left.type, -(1 << (bits - 1)))
        minus_one = ir.Constant(right.type, -1)
        is_minimum = self.builder.icmp_signed("==", left, minimum)
        is_minus_one = self.builder.icmp_signed("==", right, minus_one)
        overflow = self.builder.and_(is_minimum, is_minus_one)
        invalid = self.builder.or_(is_zero, overflow)
        self.branch_on_error(invalid, "division.error")

    def branch_on_error(self, condition, name):
        function = self.builder.function
        error_block = function.append_basic_block(name)
        continue_block = function.append_basic_block("checked.cont")
        self.builder.cbranch(condition, error_block, continue_block)
        self.builder.position_at_end(error_block)
        self.builder.call(self.abort, [])
        self.builder.unreachable()
        self.builder.position_at_end(continue_block)

    def emit_lvalue(self, expr):
        if isinstance(expr, VarNode):
            symbol = expr.symbol
            if symbol.kind == "field":
                if self.current_self is None:
                    raise RuntimeError("field name used without a member receiver")
                return self.field_pointer(self.current_self, symbol)
            if symbol.address is None:
                raise RuntimeError(f"variable '{symbol.name}' has no storage")
            return symbol.address
        if isinstance(expr, FieldAccessNode):
            base_pointer = self.emit_struct_pointer(expr.base)
            return self.field_pointer(base_pointer, expr.field)
        raise RuntimeError("expression is not an lvalue")

    def emit_struct_pointer(self, expr):
        if isinstance(expr, (VarNode, FieldAccessNode)):
            return self.emit_lvalue(expr)
        value = self.emit_expr(expr)
        type_name = expr.inferred_type
        pointer = self.alloca(type_name, "temporary.object")
        self.builder.store(value, pointer)
        return pointer

    def field_pointer(self, base_pointer, field):
        zero = ir.Constant(ir.IntType(32), 0)
        index = ir.Constant(ir.IntType(32), field.index)
        return self.builder.gep(base_pointer, [zero, index], inbounds=True, name=field.name + ".ptr")

    def emit_call(self, call):
        function_symbol = call.function
        function_value = self.function_values[function_symbol]
        args = []
        if function_symbol.owner is not None:
            if isinstance(call.callee, FieldAccessNode):
                args.append(self.emit_struct_pointer(call.callee.base))
            else:
                args.append(self.current_self)
        args.extend(self.emit_expr(argument) for argument in call.args)
        return self.builder.call(function_value, args, name=function_symbol.name + ".result")

    def emit_print(self, expr):
        type_name = expr.inferred_type
        if type_name == "string":
            self.emit_printf(b"%s\n", [self.emit_expr(expr)])
        elif type_name == "🐥":
            self.emit_printf(b"%d\n", [self.emit_expr(expr)])
        elif type_name == "🦆":
            self.emit_printf(b"%lld\n", [self.emit_expr(expr)])
        elif type_name == "🥚":
            truth = self.builder.select(
                self.emit_expr(expr),
                self.add_string(b"true"),
                self.add_string(b"false"),
            )
            self.emit_printf(b"%s\n", [truth])
        elif type_name in self.analyzer.structs:
            self.emit_print_object(expr, type_name)

    def emit_print_object(self, expr, type_name):
        structure = self.analyzer.structs[type_name]
        pointer = self.emit_struct_pointer(expr)
        self.emit_printf(b"%s {", [self.add_string(self.ascii_bytes(type_name))])
        for index, field in enumerate(structure.node.fields):
            if index == 0:
                self.emit_printf(b" ")
            else:
                self.emit_printf(b", ")
            self.emit_printf(b"%s: ", [self.add_string(self.ascii_bytes(field.name))])
            value = self.builder.load(self.field_pointer(pointer, field))
            self.emit_print_value(value, field.type_name)
        self.emit_printf(b" }\n" if structure.node.fields else b"}\n")

    def emit_print_value(self, value, type_name):
        if type_name == "🐥":
            self.emit_printf(b"%d", [value])
        elif type_name == "🦆":
            self.emit_printf(b"%lld", [value])
        elif type_name == "🥚":
            pointer = self.builder.select(value, self.add_string(b"true"), self.add_string(b"false"))
            self.emit_printf(b"%s", [pointer])
        else:
            structure = self.analyzer.structs[type_name]
            temp = self.alloca(type_name, "nested.print")
            self.builder.store(value, temp)
            self.emit_printf(b"%s {", [self.add_string(self.ascii_bytes(type_name))])
            for index, field in enumerate(structure.node.fields):
                if index == 0:
                    self.emit_printf(b" ")
                else:
                    self.emit_printf(b", ")
                self.emit_printf(b"%s: ", [self.add_string(self.ascii_bytes(field.name))])
                member_value = self.builder.load(self.field_pointer(temp, field))
                self.emit_print_value(member_value, field.type_name)
            self.emit_printf(b" }" if structure.node.fields else b"}")

    def decode_string(self, value):
        output = bytearray()
        index = 0
        escapes = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("\\"): 92, ord('"'): 34}
        while index < len(value):
            if value[index] == ord("\\") and index + 1 < len(value):
                index += 1
                output.append(escapes.get(value[index], value[index]))
            else:
                output.append(value[index])
            index += 1
        return bytes(output)

    def ascii_bytes(self, text):
        return bytes(ord(character) for character in text)

    def generate(self):
        for item in self.program.items:
            if isinstance(item, FunctionNode):
                self.emit_function(item)
            elif isinstance(item, StructNode):
                for method in item.methods:
                    self.emit_function(method)
        self.emit_main()
        module_text = str(self.module)
        parsed_module = binding.parse_assembly(module_text)
        parsed_module.verify()
        return module_text

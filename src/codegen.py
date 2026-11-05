from llvmlite import binding, ir

try:
    from ast_nodes import (
        FunctionNode,
        StructNode,
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
    from src.ast_nodes import (
        FunctionNode,
        StructNode,
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


class CodeGenerator:
    MAX_RAFT_ELEMENTS = {"🐥": 262144, "🦆": 131072, "🥚": 1048576}

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
        self.write = None
        self.scanf = None
        self.abort = None
        self.exit_function = None
        self.stack_saves = []
        self.string_number = 0
        self.declare_runtime()
        self.create_struct_types()
        self.create_globals()
        self.declare_functions()

    def type_of(self, type_name):
        if isinstance(type_name, RaftType):
            return ir.LiteralStructType(
                [
                    ir.IntType(64),
                    self.type_of(type_name.element_type).as_pointer(),
                ]
            )
        if type_name in self.llvm_types:
            return self.llvm_types[type_name]
        return self.struct_types[type_name]

    def declare_runtime(self):
        i8p = ir.IntType(8).as_pointer()
        printf_type = ir.FunctionType(ir.IntType(32), [i8p], var_arg=True)
        self.printf = ir.Function(self.module, printf_type, name="printf")
        write_type = ir.FunctionType(
            ir.IntType(64),
            [ir.IntType(32), i8p, ir.IntType(64)],
        )
        self.write = ir.Function(self.module, write_type, name="write")
        self.scanf = ir.Function(self.module, printf_type, name="scanf")
        abort_type = ir.FunctionType(ir.VoidType(), [])
        self.abort = ir.Function(self.module, abort_type, name="abort")
        exit_type = ir.FunctionType(ir.VoidType(), [ir.IntType(32)])
        self.exit_function = ir.Function(self.module, exit_type, name="exit")
        stack_save_type = ir.FunctionType(i8p, [])
        self.stack_save = ir.Function(self.module, stack_save_type, name="llvm.stacksave")
        stack_restore_type = ir.FunctionType(ir.VoidType(), [i8p])
        self.stack_restore = ir.Function(self.module, stack_restore_type, name="llvm.stackrestore")

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
        self.stack_saves = []
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
        stack_save = self.builder.call(self.stack_save, [], name="raft.scope.save")
        self.stack_saves.append(stack_save)
        for statement in block.stmts:
            if self.builder.block.is_terminated:
                break
            self.emit_statement(statement)
        if not self.builder.block.is_terminated:
            self.builder.call(self.stack_restore, [stack_save])
        self.stack_saves.pop()

    def emit_statement(self, stmt):
        if isinstance(stmt, DeclNode):
            symbol = stmt.symbol
            if symbol.kind == "global":
                address = symbol.address
            else:
                address = self.alloca(symbol.type_name, symbol.name)
                symbol.address = address
            if isinstance(symbol.type_name, RaftType):
                self.emit_raft_declaration(stmt, address)
            else:
                self.builder.store(self.emit_expr(stmt.init), address)
        elif isinstance(stmt, ExprStmtNode):
            self.emit_expr(stmt.expr)
        elif isinstance(stmt, AssignNode):
            if isinstance(stmt.target.inferred_type, RaftType):
                target_address = self.emit_lvalue(stmt.target)
                target = self.builder.load(target_address, name="raft.assignment.target")
                source = self.emit_expr(stmt.value)
                target_size = self.builder.extract_value(target, 0, name="raft.target.size")
                source_size = self.builder.extract_value(source, 0, name="raft.source.size")
                same_size = self.builder.icmp_unsigned(
                    "==", target_size, source_size, name="raft.assignment.sizes.match"
                )
                self.branch_on_raft_error(
                    same_size,
                    b"runtime error: raft assignment length does not match",
                    "raft.assignment.length.error",
                )
                destination_data = self.builder.extract_value(target, 1, name="raft.target.data")
                source_data = self.builder.extract_value(source, 1, name="raft.source.data")
                self.emit_raft_copy(destination_data, source_data, target_size)
            else:
                self.builder.store(self.emit_expr(stmt.value), self.emit_lvalue(stmt.target))
        elif isinstance(stmt, SwapStmtNode):
            pointers = [self.emit_lvalue(target) for target in stmt.targets]
            values = [self.builder.load(pointer) for pointer in pointers]
            if isinstance(stmt.targets[0].inferred_type, RaftType):
                first_size = self.builder.extract_value(values[0], 0, name="raft.swap.first.size")
                for value in values[1:]:
                    other_size = self.builder.extract_value(value, 0, name="raft.swap.other.size")
                    same_size = self.builder.icmp_unsigned(
                        "==", first_size, other_size, name="raft.swap.sizes.match"
                    )
                    self.branch_on_raft_error(
                        same_size,
                        b"runtime error: raft swap lengths do not match",
                        "raft.swap.length.error",
                    )
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
            value = self.emit_expr(stmt.value)
            for stack_save in reversed(self.stack_saves):
                self.builder.call(self.stack_restore, [stack_save])
            self.builder.ret(value)
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
        if isinstance(expr, InlineExprNode):
            for statement in expr.statements:
                self.emit_statement(statement)
                if self.builder.block.is_terminated:
                    break
            return self.emit_expr(expr.value)
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
        if isinstance(expr, RaftLiteralNode):
            return self.emit_raft_literal(expr)
        if isinstance(expr, IndexNode):
            return self.builder.load(self.emit_lvalue(expr), name="raft.element")
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
        if isinstance(expr, IndexNode):
            descriptor_pointer = self.emit_lvalue(expr.base)
            descriptor = self.builder.load(descriptor_pointer, name="raft.descriptor")
            data_pointer = self.builder.extract_value(descriptor, 1, name="raft.data")
            index = self.emit_raft_index(expr, descriptor)
            return self.builder.gep(data_pointer, [index], inbounds=True, name="raft.element.ptr")
        raise RuntimeError("expression is not an lvalue")

    def emit_raft_size(self, raft_type):
        size = self.emit_expr(raft_type.size_expr)
        if size.type.width == 32:
            size = self.builder.sext(size, ir.IntType(64), name="raft.size")
        return size

    def branch_on_raft_error(self, condition, message, name):
        function = self.builder.function
        error_block = function.append_basic_block(name)
        continue_block = function.append_basic_block(name + ".cont")
        self.builder.cbranch(condition, continue_block, error_block)
        self.builder.position_at_end(error_block)
        encoded = message + b"\n"
        self.builder.call(
            self.write,
            [
                ir.Constant(ir.IntType(32), 2),
                self.add_string(encoded),
                ir.Constant(ir.IntType(64), len(encoded)),
            ],
        )
        self.builder.call(self.exit_function, [ir.Constant(ir.IntType(32), 1)])
        self.builder.unreachable()
        self.builder.position_at_end(continue_block)

    def emit_raft_declaration(self, decl, address):
        raft_type = decl.type_name
        size = self.emit_raft_size(raft_type)
        zero = ir.Constant(ir.IntType(64), 0)
        max_elements = self.MAX_RAFT_ELEMENTS[raft_type.element_type]
        positive = self.builder.icmp_signed(">", size, zero, name="raft.size.positive")
        within_limit = self.builder.icmp_signed(
            "<=",
            size,
            ir.Constant(ir.IntType(64), max_elements),
            name="raft.size.within_limit",
        )
        valid_size = self.builder.and_(positive, within_limit, name="raft.size.valid")
        self.branch_on_raft_error(
            valid_size,
            {
                "🐥": b"runtime error: raft size must be between 1 and 262144",
                "🦆": b"runtime error: raft size must be between 1 and 131072",
                "🥚": b"runtime error: raft size must be between 1 and 1048576",
            }[raft_type.element_type],
            "raft.size.error",
        )
        element_type = self.type_of(raft_type.element_type)
        data_pointer = self.builder.alloca(element_type, size=size, name="raft.data")
        if isinstance(decl.init, RaftLiteralNode):
            if decl.init.elements:
                matches_length = self.builder.icmp_unsigned(
                    "==",
                    size,
                    ir.Constant(ir.IntType(64), len(decl.init.elements)),
                    name="raft.initializer.length.matches",
                )
                self.branch_on_raft_error(
                    matches_length,
                    b"runtime error: raft initializer length does not match its size",
                    "raft.initializer.length.error",
                )
                for index, element in enumerate(decl.init.elements):
                    pointer = self.builder.gep(
                        data_pointer,
                        [ir.Constant(ir.IntType(64), index)],
                        inbounds=True,
                    )
                    self.builder.store(self.emit_expr(element), pointer)
            else:
                self.emit_raft_zero_fill(data_pointer, size, element_type)
        else:
            source = self.emit_expr(decl.init)
            source_size = self.builder.extract_value(source, 0, name="raft.source.size")
            source_data = self.builder.extract_value(source, 1, name="raft.source.data")
            matches_length = self.builder.icmp_unsigned(
                "==", size, source_size, name="raft.copy.length.matches"
            )
            self.branch_on_raft_error(
                matches_length,
                b"runtime error: raft copy length does not match its size",
                "raft.copy.length.error",
            )
            self.emit_raft_copy(data_pointer, source_data, size)
        descriptor = ir.Constant(self.type_of(raft_type), None)
        descriptor = self.builder.insert_value(descriptor, size, 0, name="raft.value")
        descriptor = self.builder.insert_value(descriptor, data_pointer, 1, name="raft.value")
        self.builder.store(descriptor, address)

    def emit_raft_literal(self, expr):
        element_type = self.type_of(expr.inferred_type.element_type)
        size = ir.Constant(ir.IntType(64), len(expr.elements))
        data_pointer = self.builder.alloca(element_type, size=size, name="raft.literal.data")
        for index, element in enumerate(expr.elements):
            pointer = self.builder.gep(
                data_pointer,
                [ir.Constant(ir.IntType(64), index)],
                inbounds=True,
            )
            self.builder.store(self.emit_expr(element), pointer)
        descriptor = ir.Constant(self.type_of(expr.inferred_type), None)
        descriptor = self.builder.insert_value(descriptor, size, 0, name="raft.literal")
        descriptor = self.builder.insert_value(descriptor, data_pointer, 1, name="raft.literal")
        return descriptor

    def emit_raft_zero_fill(self, data_pointer, size, element_type):
        function = self.builder.function
        condition_block = function.append_basic_block("raft.zero.cond")
        body_block = function.append_basic_block("raft.zero.body")
        end_block = function.append_basic_block("raft.zero.end")
        preheader = self.builder.block
        self.builder.branch(condition_block)
        self.builder.position_at_end(condition_block)
        index = self.builder.phi(ir.IntType(64), name="raft.zero.index")
        index.add_incoming(ir.Constant(ir.IntType(64), 0), preheader)
        more = self.builder.icmp_unsigned("<", index, size, name="raft.zero.more")
        self.builder.cbranch(more, body_block, end_block)
        self.builder.position_at_end(body_block)
        pointer = self.builder.gep(data_pointer, [index], inbounds=True)
        self.builder.store(ir.Constant(element_type, 0), pointer)
        next_index = self.builder.add(index, ir.Constant(ir.IntType(64), 1), name="raft.zero.next")
        self.builder.branch(condition_block)
        index.add_incoming(next_index, body_block)
        self.builder.position_at_end(end_block)

    def emit_raft_copy(self, destination, source, size):
        function = self.builder.function
        condition_block = function.append_basic_block("raft.copy.cond")
        body_block = function.append_basic_block("raft.copy.body")
        end_block = function.append_basic_block("raft.copy.end")
        preheader = self.builder.block
        self.builder.branch(condition_block)
        self.builder.position_at_end(condition_block)
        index = self.builder.phi(ir.IntType(64), name="raft.copy.index")
        index.add_incoming(ir.Constant(ir.IntType(64), 0), preheader)
        more = self.builder.icmp_unsigned("<", index, size, name="raft.copy.more")
        self.builder.cbranch(more, body_block, end_block)
        self.builder.position_at_end(body_block)
        source_pointer = self.builder.gep(source, [index], inbounds=True)
        destination_pointer = self.builder.gep(destination, [index], inbounds=True)
        value = self.builder.load(source_pointer, name="raft.copy.value")
        self.builder.store(value, destination_pointer)
        next_index = self.builder.add(index, ir.Constant(ir.IntType(64), 1), name="raft.copy.next")
        self.builder.branch(condition_block)
        index.add_incoming(next_index, body_block)
        self.builder.position_at_end(end_block)

    def emit_raft_index(self, expr, descriptor):
        if expr.known_index is not None:
            return ir.Constant(ir.IntType(64), expr.known_index)
        index = self.emit_expr(expr.index)
        if index.type.width == 32:
            index = self.builder.sext(index, ir.IntType(64), name="raft.index")
        zero = ir.Constant(ir.IntType(64), 0)
        size = self.builder.extract_value(descriptor, 0, name="raft.length")
        nonnegative = self.builder.icmp_signed(">=", index, zero, name="raft.index.nonnegative")
        below_size = self.builder.icmp_signed("<", index, size, name="raft.index.inrange")
        in_bounds = self.builder.and_(nonnegative, below_size, name="raft.index.valid")
        self.branch_on_raft_error(
            in_bounds,
            b"runtime error: raft index out of bounds",
            "raft.bounds.error",
        )
        return index

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
        for argument, parameter_type in zip(call.args, function_symbol.param_types):
            value = self.emit_expr(argument)
            if isinstance(parameter_type, RaftType):
                value = self.emit_raft_value_copy(value, parameter_type)
            args.append(value)
        return self.builder.call(function_value, args, name=function_symbol.name + ".result")

    def emit_raft_value_copy(self, value, raft_type):
        size = self.builder.extract_value(value, 0, name="raft.argument.size")
        source = self.builder.extract_value(value, 1, name="raft.argument.data")
        destination = self.builder.alloca(
            self.type_of(raft_type.element_type),
            size=size,
            name="raft.argument.copy",
        )
        self.emit_raft_copy(destination, source, size)
        copied_value = ir.Constant(self.type_of(raft_type), None)
        copied_value = self.builder.insert_value(copied_value, size, 0, name="raft.argument")
        copied_value = self.builder.insert_value(copied_value, destination, 1, name="raft.argument")
        return copied_value

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

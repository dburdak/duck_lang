import copy

try:
    from ast_nodes import (
        ASTNode,
        AssignNode,
        BlockNode,
        CallNode,
        DeclNode,
        ExprStmtNode,
        FieldAccessNode,
        FunctionNode,
        IfNode,
        InlineExprNode,
        IndexNode,
        PrintStmtNode,
        ProgramNode,
        RaftLiteralNode,
        RaftType,
        ReadNode,
        ReturnNode,
        StructNode,
        SwapStmtNode,
        VarNode,
        WhileNode,
    )
    from semantic import SemanticAnalyzer
except ImportError:
    from src.ast_nodes import (
        ASTNode,
        AssignNode,
        BlockNode,
        CallNode,
        DeclNode,
        ExprStmtNode,
        FieldAccessNode,
        FunctionNode,
        IfNode,
        InlineExprNode,
        IndexNode,
        PrintStmtNode,
        ProgramNode,
        RaftLiteralNode,
        RaftType,
        ReadNode,
        ReturnNode,
        StructNode,
        SwapStmtNode,
        VarNode,
        WhileNode,
    )
    from src.semantic import SemanticAnalyzer


class Optimizer:
    def __init__(self, program):
        self.program = program
        self.fresh_names = self._all_names(program)
        self.inline_counter = 0

    def optimize(self):
        changed = True
        while changed:
            SemanticAnalyzer(self.program).analyze()
            removed_variables = self.remove_unused_variables()
            SemanticAnalyzer(self.program).analyze()
            removed_functions = self.remove_unused_functions()
            SemanticAnalyzer(self.program).analyze()
            inlined_functions = self.inline_single_use_functions()
            changed = removed_variables or removed_functions or inlined_functions
        SemanticAnalyzer(self.program).analyze()
        return self.program

    def remove_unused_variables(self):
        reads = {}
        declarations = []
        for node in self.walk(self.program):
            if isinstance(node, DeclNode) and getattr(node, "symbol", None) is not None:
                declarations.append(node)
        self.visit_reads(self.program, reads)
        unused = {
            declaration.symbol
            for declaration in declarations
            if reads.get(declaration.symbol, 0) == 0
        }
        if not unused:
            return False
        before = {
            id(node)
            for node in self.walk(self.program)
            if (
                isinstance(node, DeclNode) and getattr(node, "symbol", None) in unused
            )
            or (
                isinstance(node, AssignNode)
                and isinstance(node.target, VarNode)
                and node.target.symbol in unused
            )
        }
        self.rewrite_statement_lists(self.program, unused)
        after = {
            id(node)
            for node in self.walk(self.program)
            if (
                isinstance(node, DeclNode) and getattr(node, "symbol", None) in unused
            )
            or (
                isinstance(node, AssignNode)
                and isinstance(node.target, VarNode)
                and node.target.symbol in unused
            )
        }
        return before != after

    def visit_reads(self, node, reads):
        if isinstance(node, (list, tuple)):
            for item in node:
                self.visit_reads(item, reads)
            return
        if not isinstance(node, ASTNode):
            return
        if isinstance(node, VarNode):
            if node.symbol is not None:
                reads[node.symbol] = reads.get(node.symbol, 0) + 1
            return
        if isinstance(node, AssignNode):
            self.visit_lvalue_reads(node.target, reads)
            self.visit_reads(node.value, reads)
            return
        if isinstance(node, SwapStmtNode):
            for target in node.targets:
                self.visit_reads(target, reads)
            return
        for child in self.children(node):
            self.visit_reads(child, reads)

    def visit_lvalue_reads(self, node, reads):
        if isinstance(node, VarNode):
            return
        if isinstance(node, FieldAccessNode):
            self.visit_reads(node.base, reads)
        elif isinstance(node, IndexNode):
            self.visit_reads(node.base, reads)
            self.visit_reads(node.index, reads)
        else:
            self.visit_reads(node, reads)

    def rewrite_statement_lists(self, node, unused):
        if isinstance(node, (list, tuple)):
            for item in node:
                self.rewrite_statement_lists(item, unused)
            return
        if not isinstance(node, ASTNode):
            return
        if isinstance(node, ProgramNode):
            node.items = self.rewrite_statements(node.items, unused)
            node.stmts = node.items
            return
        if isinstance(node, InlineExprNode):
            node.statements = self.rewrite_statements(node.statements, unused)
            self.rewrite_statement_lists(node.value, unused)
            return
        if isinstance(node, FunctionNode):
            node.body.stmts = self.rewrite_statements(node.body.stmts, unused)
            return
        if isinstance(node, StructNode):
            for method in node.methods:
                self.rewrite_statement_lists(method, unused)
            return
        if isinstance(node, BlockNode):
            node.stmts = self.rewrite_statements(node.stmts, unused)
            return
        if isinstance(node, IfNode):
            self.rewrite_statement_lists(node.condition, unused)
            self.rewrite_statement_lists(node.then_block, unused)
            if node.else_block is not None:
                self.rewrite_statement_lists(node.else_block, unused)
            return
        if isinstance(node, WhileNode):
            self.rewrite_statement_lists(node.condition, unused)
            self.rewrite_statement_lists(node.body_block, unused)
            return
        for child in self.children(node):
            self.rewrite_statement_lists(child, unused)

    def rewrite_statements(self, statements, unused):
        rewritten = []
        for statement in statements:
            self.rewrite_statement_lists(statement, unused)
            if isinstance(statement, DeclNode) and getattr(statement, "symbol", None) in unused:
                if self.raft_declaration_has_runtime_effect(statement):
                    rewritten.append(statement)
                    continue
                if self.has_side_effect(statement.init):
                    rewritten.append(ExprStmtNode(statement.line, statement.col, statement.init))
                continue
            if (
                isinstance(statement, AssignNode)
                and isinstance(statement.target, VarNode)
                and statement.target.symbol in unused
            ):
                if self.has_side_effect(statement.value):
                    rewritten.append(ExprStmtNode(statement.line, statement.col, statement.value))
                continue
            rewritten.append(statement)
        return rewritten

    def raft_declaration_has_runtime_effect(self, declaration):
        type_name = declaration.type_name
        if not isinstance(type_name, RaftType):
            return False
        if type_name.static_size is None:
            return True
        if isinstance(declaration.init, RaftLiteralNode):
            return False
        actual_type = getattr(declaration.init, "inferred_type", None)
        return not (
            isinstance(actual_type, RaftType)
            and actual_type.static_size == type_name.static_size
        )

    def has_side_effect(self, node):
        return any(
            isinstance(item, (CallNode, ReadNode, PrintStmtNode, ExprStmtNode))
            for item in self.walk(node)
        )

    def remove_unused_functions(self):
        functions = self.callable_functions()
        if not functions:
            return False
        by_symbol = {function.symbol: function for function in functions}
        reachable = set()
        pending = []
        for item in self.program.items:
            if isinstance(item, (FunctionNode, StructNode)):
                continue
            pending.extend(self.called_functions(item))
        while pending:
            symbol = pending.pop()
            if symbol in reachable or symbol not in by_symbol:
                continue
            reachable.add(symbol)
            pending.extend(self.called_functions(by_symbol[symbol].body))
        removed = False
        retained_items = []
        for item in self.program.items:
            if isinstance(item, FunctionNode):
                if item.symbol not in reachable:
                    removed = True
                    continue
            elif isinstance(item, StructNode):
                members = []
                for member in item.members:
                    if isinstance(member, FunctionNode) and member.symbol not in reachable:
                        removed = True
                    else:
                        members.append(member)
                item.members = members
                item.fields = [member for member in members if not isinstance(member, FunctionNode)]
                item.methods = [member for member in members if isinstance(member, FunctionNode)]
            retained_items.append(item)
        self.program.items = retained_items
        self.program.stmts = retained_items
        return removed

    def inline_single_use_functions(self):
        all_functions = self.callable_functions()
        functions = [
            function for function in all_functions if function.struct_name is None
        ]
        if not functions:
            return False
        call_counts = {function.symbol: 0 for function in functions}
        call_graph = {function.symbol: set() for function in all_functions}
        for function in all_functions:
            for called_function in self.called_functions(function.body):
                if called_function in call_counts:
                    call_counts[called_function] += 1
                call_graph[function.symbol].add(called_function)
        for item in self.program.items:
            if isinstance(item, (FunctionNode, StructNode)):
                continue
            for call in self.global_function_calls(item):
                if call.function in call_counts:
                    call_counts[call.function] += 1
        recursive = {
            symbol
            for symbol in call_graph
            if self.reaches_self(symbol, symbol, call_graph, set())
        }
        candidates = {
            function.name: function
            for function in functions
            if call_counts[function.symbol] == 1
            and function.symbol not in recursive
            and self.is_inlineable(function)
        }
        if not candidates:
            return False
        self.program = self.transform_calls(self.program, candidates)
        return True

    def is_inlineable(self, function):
        statements = function.body.stmts
        if not statements or not isinstance(statements[-1], ReturnNode):
            return False
        if any(not isinstance(statement, (DeclNode, AssignNode, CallNode, PrintStmtNode)) for statement in statements[:-1]):
            return False
        if isinstance(function.result_type, RaftType):
            return False
        if any(isinstance(param.type_name, RaftType) for param in function.params):
            return False
        if any(isinstance(node, DeclNode) and isinstance(node.type_name, RaftType) for node in self.walk(function.body)):
            return False
        return True

    def reaches_self(self, start, current, graph, visited):
        if current in visited:
            return False
        visited.add(current)
        for target in graph.get(current, ()):
            if target == start or self.reaches_self(start, target, graph, visited):
                return True
        return False

    def transform_calls(self, node, candidates):
        if isinstance(node, list):
            return [self.transform_calls(item, candidates) for item in node]
        if isinstance(node, tuple):
            return tuple(self.transform_calls(item, candidates) for item in node)
        if not isinstance(node, ASTNode):
            return node
        for name, value in list(vars(node).items()):
            if isinstance(node, ProgramNode) and name == "stmts":
                continue
            if isinstance(value, ASTNode):
                setattr(node, name, self.transform_calls(value, candidates))
            elif isinstance(value, list):
                if name in ("items", "stmts"):
                    setattr(node, name, self.transform_statement_list(value, candidates))
                else:
                    setattr(node, name, self.transform_calls(value, candidates))
            elif isinstance(value, tuple):
                setattr(node, name, self.transform_calls(value, candidates))
            elif isinstance(value, RaftType) and value.size_expr is not None:
                value.size_expr = self.transform_calls(value.size_expr, candidates)
        if isinstance(node, ProgramNode):
            node.stmts = node.items
        if not isinstance(node, CallNode) or node.function is None:
            return node
        function = candidates.get(node.function.name) if node.function.owner is None else None
        if function is None:
            return node
        return self.make_inline_expr(node, function)

    def transform_statement_list(self, statements, candidates):
        transformed = []
        for statement in statements:
            result = self.transform_calls(statement, candidates)
            if isinstance(statement, CallNode) and isinstance(result, InlineExprNode):
                result = ExprStmtNode(statement.line, statement.col, result)
            transformed.append(result)
        return transformed

    def make_inline_expr(self, call, function):
        params, body = copy.deepcopy((function.params, function.body))
        declarations = []
        local_symbols = {}
        for parameter in params:
            if parameter.symbol is not None:
                local_symbols[parameter.symbol] = self.fresh_name(function.name, parameter.name)
        for node in self.walk(body):
            symbol = getattr(node, "symbol", None)
            if isinstance(node, DeclNode) and symbol is not None:
                local_symbols[symbol] = self.fresh_name(function.name, node.name)
        for node in self.walk((params, body)):
            symbol = getattr(node, "symbol", None)
            if isinstance(node, DeclNode) and symbol in local_symbols:
                node.name = local_symbols[symbol]
            elif isinstance(node, VarNode) and symbol in local_symbols:
                node.name = local_symbols[symbol]
        for parameter, argument in zip(params, call.args):
            declarations.append(
                DeclNode(
                    call.line,
                    call.col,
                    parameter.type_name,
                    local_symbols[parameter.symbol],
                    False,
                    argument,
                )
            )
        return_statement = body.stmts[-1]
        statements = declarations + body.stmts[:-1]
        result = copy.deepcopy(return_statement.value)
        inline = InlineExprNode(call.line, call.col, statements, result, function.result_type)
        inline.inferred_type = call.inferred_type
        return inline

    def fresh_name(self, function_name, original):
        while True:
            self.inline_counter += 1
            candidate = f"__inline_{function_name}_{self.inline_counter}_{original}"
            if candidate not in self.fresh_names:
                self.fresh_names.add(candidate)
                return candidate

    def callable_functions(self):
        functions = []
        for item in self.program.items:
            if isinstance(item, FunctionNode):
                functions.append(item)
            elif isinstance(item, StructNode):
                functions.extend(item.methods)
        return functions

    def called_functions(self, node):
        return [
            call.function
            for call in self.walk(node)
            if isinstance(call, CallNode) and call.function is not None
        ]

    def global_function_calls(self, node):
        return [
            call
            for call in self.walk(node)
            if isinstance(call, CallNode)
            and call.function is not None
            and call.function.owner is None
        ]

    def walk(self, value):
        if isinstance(value, ASTNode):
            yield value
            for child in self.children(value):
                yield from self.walk(child)
        elif isinstance(value, RaftType):
            if value.size_expr is not None:
                yield from self.walk(value.size_expr)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from self.walk(item)

    def children(self, node):
        for name, value in vars(node).items():
            if name in ("symbol", "function", "field", "inferred_type", "address"):
                continue
            if isinstance(node, ProgramNode) and name == "stmts":
                continue
            if isinstance(value, ASTNode):
                yield value
            elif isinstance(value, (list, tuple)):
                yield value
            elif isinstance(value, RaftType) and value.size_expr is not None:
                yield value.size_expr

    def _all_names(self, program):
        return {
            node.name
            for node in self.walk(program)
            if isinstance(node, (VarNode, DeclNode, FunctionNode))
        } | {
            parameter.name
            for node in self.walk(program)
            if isinstance(node, FunctionNode)
            for parameter in node.params
        }

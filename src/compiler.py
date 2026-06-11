from typing import Optional, List
from lexer_core import Lexer
from parser_core import LL1Parser
from ir_generator import IRGenerator
from codegen import CodeGenerator
from symbol_table import SymbolTable
from constants import TYPES
from ast_core import ASTBuilder, ASTIRGenerator, ASTRenderer, ASTSemanticAnalyzer


class CompilerResult:
    """编译结果"""
    def __init__(self):
        self.success = False
        self.tokens = []
        self.parse_records = []
        self.symbol_table = None
        self.quadruples = []
        self.assembly_code = ""
        self.ast = None
        self.annotated_syntax_tree = ""
        self.backpatch_report = ""
        self.errors = []
        self.warnings = []
    
    def __str__(self):
        lines = ["=" * 80]
        lines.append("编译结果".center(80))
        lines.append("=" * 80)
        
        if self.success:
            lines.append("✓ 编译成功".center(80))
        else:
            lines.append("✗ 编译失败".center(80))
        
        if self.errors:
            lines.append("\n错误:")
            for err in self.errors:
                lines.append(f"  {err}")
        
        if self.warnings:
            lines.append("\n警告:")
            for warn in self.warnings:
                lines.append(f"  {warn}")
        
        lines.append("=" * 80)
        return "\n".join(lines)


class Compiler:
    """C语言编译器（简化版）"""
    
    def __init__(self):
        self.lexer: Optional[Lexer] = None
        self.parser: Optional[LL1Parser] = None
        self.semantic_analyzer: Optional[ASTSemanticAnalyzer] = None
        self.ir_generator: Optional[IRGenerator] = None
        self.code_generator: Optional[CodeGenerator] = None
        self.ast_builder: Optional[ASTBuilder] = None
        self.ast = None
        self.source_code = ""
        self.result = CompilerResult()
    
    def compile(self, source_code: str, verbose: bool = True) -> CompilerResult:
        """
        编译源代码
        
        Args:
            source_code: C源代码
            verbose: 是否输出详细信息
        
        Returns:
            CompilerResult: 编译结果
        """
        # 每次编译都重新创建结果对象，避免上一次编译残留 token/四元式/错误。
        self.result = CompilerResult()
        # 先规范化中文全角标点，保证后续词法分析只面对标准 C 风格符号。
        source_code = self._normalize_source(source_code)
        # 保存规范化后的源码，后面生成带注释语法树时还要读取源码行。
        self.source_code = source_code
        
        try:
            # 1. 词法分析
            if verbose:
                print("\n" + "=" * 80)
                print("第一阶段：词法分析".center(80))
                print("=" * 80)
            
            # 词法分析把字符流转换成 token 流，语法分析和 ASTBuilder 会消费这批 tokens。
            success, tokens = self.lexical_analysis(source_code, verbose)
            if not success:
                return self.result
            
            # 2. 语法分析
            if verbose:
                print("\n" + "=" * 80)
                print("第二阶段：语法分析".center(80))
                print("=" * 80)
            
            # LL(1) 语法分析检查 token 排列是否符合文法，并记录推导步骤。
            success, parse_records = self.syntax_analysis(tokens, verbose)
            if not success:
                return self.result
            
            # 3. AST构建
            if verbose:
                print("\n" + "=" * 80)
                print("第三阶段：AST构建".center(80))
                print("=" * 80)
            
            success, ast = self.ast_construction(tokens, verbose)
            if not success:
                return self.result
            
            # 4. 语义分析
            if verbose:
                print("\n" + "=" * 80)
                print("第四阶段：语义分析".center(80))
                print("=" * 80)
            
            success, symbol_table = self.semantic_analysis(ast, verbose)
            if not success:
                return self.result
            
            # 5. 中间代码生成
            if verbose:
                print("\n" + "=" * 80)
                print("第五阶段：中间代码生成".center(80))
                print("=" * 80)
            
            success, ir_gen = self.intermediate_code_generation(symbol_table, ast, tokens, verbose)
            if not success:
                return self.result
            # 提交/答辩用语法树使用富注释渲染：包含 TYPE_SPEC、INIT_FIELD、
            # symbol/offset/lvalue 以及 while/if 回填目标，比内部 AST 调试树更适合展示。
            self.result.annotated_syntax_tree = self._generate_annotated_syntax_tree()
            self.result.backpatch_report = self._generate_backpatch_report()
            
            # 6. 目标代码生成
            if verbose:
                print("\n" + "=" * 80)
                print("第六阶段：目标代码生成".center(80))
                print("=" * 80)
            
            # 目标代码生成阶段遍历四元式，生成 8086 汇编文本。
            success, asm_code = self.target_code_generation(ir_gen, symbol_table, verbose)
            if not success:
                return self.result
            
            # 所有阶段都成功后，才把最终结果标记为成功。
            self.result.success = True
            
            if verbose:
                print("\n" + "=" * 80)
                print("编译完成！".center(80))
                print("=" * 80)
            
        except Exception as e:
            self.result.errors.append(f"编译器内部错误: {str(e)}")
            self.result.success = False
            if verbose:
                import traceback
                traceback.print_exc()
        
        return self.result

    def _normalize_source(self, source_code: str) -> str:
        """Normalize common full-width punctuation copied from Chinese documents."""
        return source_code.translate(str.maketrans({
            "；": ";",
            "，": ",",
            "（": "(",
            "）": ")",
            "｛": "{",
            "｝": "}",
            "［": "[",
            "］": "]",
        }))
    
    def lexical_analysis(self, source_code: str, verbose: bool = True) -> tuple[bool, List]:
        """词法分析"""
        self.lexer = Lexer(source_code)
        tokens = self.lexer.tokenize()
        
        self.result.tokens = tokens
        
        if self.lexer.errors:
            self.result.errors.extend(self.lexer.errors)
            if verbose:
                print("✗ 词法分析失败")
                for err in self.lexer.errors:
                    print(f"  {err}")
            return False, []
        
        if verbose:
            print(f"✓ 词法分析成功，识别 {len(tokens)} 个token")
            print(f"\n{self.lexer.table}")
        
        return True, tokens
    
    def syntax_analysis(self, tokens: List, verbose: bool = True) -> tuple[bool, List]:
        """语法分析"""
        self.parser = LL1Parser()
        records, success, message = self.parser.analyze(tokens)
        
        self.result.parse_records = records
        
        if not success:
            self.result.errors.append(f"语法分析错误: {message}")
            if verbose:
                print(f"✗ {message}")
            return False, []
        
        if verbose:
            print(f"✓ {message}")
            print(f"  分析步骤数: {len(records)}")
        
        return True, records

    def ast_construction(self, tokens: List, verbose: bool = True):
        """AST构建"""
        try:
            self.ast_builder = ASTBuilder(tokens)
            self.ast = self.ast_builder.build()
            self.result.ast = self.ast
        except Exception as exc:
            self.result.errors.append(f"AST构建错误: {exc}")
            if verbose:
                print(f"✗ AST构建失败: {exc}")
            return False, None

        if verbose:
            print("✓ AST构建成功")
            print(ASTRenderer().render(self.ast))

        return True, self.ast
    
    def semantic_analysis(self, ast, verbose: bool = True) -> tuple[bool, SymbolTable]:
        """语义分析"""
        # 语义分析只遍历 AST，不再重新扫描 token。
        self.semantic_analyzer = ASTSemanticAnalyzer()
        symbol_table = self.semantic_analyzer.analyze(ast)
        
        self.result.symbol_table = symbol_table
        
        if self.semantic_analyzer.errors or symbol_table.errors:
            self.result.errors.extend(self.semantic_analyzer.errors + symbol_table.errors)
            if verbose:
                print("✗ 语义分析失败")
                for err in self.semantic_analyzer.errors + symbol_table.errors:
                    print(f"  {err}")
            return False, symbol_table
        
        if verbose:
            print("✓ 语义分析成功")
            print(symbol_table)
        
        return True, symbol_table

    def intermediate_code_generation(self, symbol_table: SymbolTable, ast, tokens: List,
                                     verbose: bool = True) -> tuple[bool, IRGenerator]:
        """中间代码生成"""
        # IRGenerator 保存四元式列表、临时变量计数器，并提供 emit/new_temp 等接口。
        self.ir_generator = IRGenerator(symbol_table)

        # 中间代码生成只遍历 AST，不再复用 token 流扫描语句。
        struct_defs = self.ast_builder.struct_defs if self.ast_builder else {}
        macros = self._collect_object_macros(tokens)
        ASTIRGenerator(self.ir_generator, struct_defs, macros).generate(ast)
        
        self.result.quadruples = self.ir_generator.quadruples
        
        if verbose:
            print("✓ 中间代码生成成功")
            print(self.ir_generator.to_readable_string())
        
        return True, self.ir_generator
    
    def target_code_generation(self, ir_gen: IRGenerator, symbol_table: SymbolTable,
                               verbose: bool = True) -> tuple[bool, str]:
        """目标代码生成"""
        # CodeGenerator 会扫描四元式、分配汇编标签，并生成数据段/代码段/栈段。
        self.code_generator = CodeGenerator(ir_gen, symbol_table)
        asm_code = self.code_generator.generate()
        
        self.result.assembly_code = asm_code
        
        if verbose:
            print("✓ 目标代码生成成功")
            print("\n汇编代码预览（前30行）:")
            lines = asm_code.split('\n')
            for i, line in enumerate(lines[:30]):
                print(f"  {line}")
            if len(lines) > 30:
                print(f"  ... (共 {len(lines)} 行)")
        
        return True, asm_code
    

    def _generate_annotated_syntax_tree(self) -> str:
        """Build an annotated AST text from the current token stream."""
        from constants import TYPES

        class Node:
            def __init__(self, label, children=None):
                self.label = label
                self.children = children or []

        tokens = [
            t for t in self.result.tokens
            if TYPES.get(t.type, "") not in {"PREPROCESSOR", "EOF"} and t.attribute != "const"
        ]
        n = len(tokens)
        comments_by_line = {}
        for line_no, line in enumerate(self.source_code.splitlines(), 1):
            if "//" in line:
                comments_by_line[line_no] = line.split("//", 1)[1].strip()

        struct_defs = {}
        env_stack = [{}]
        next_offset = [-2]
        quads = self.ir_generator.quadruples if self.ir_generator else []
        while_false_targets = []
        if_false_targets = []
        loop_back_targets = []
        for qidx, quad in enumerate(quads):
            if quad.op == "j" and quad.result.isdigit() and int(quad.result) <= qidx:
                loop_back_targets.append((qidx, int(quad.result)))
            elif quad.op.startswith("j") and quad.op != "j" and quad.result.isdigit():
                has_loop_back = any(q.op == "j" and q.result == str(qidx) for q in quads)
                if has_loop_back:
                    while_false_targets.append((qidx, int(quad.result)))
                else:
                    if_false_targets.append((qidx, int(quad.result)))

        def ttype(idx):
            if 0 <= idx < n:
                return TYPES.get(tokens[idx].type, "")
            return ""

        def attr(idx):
            if 0 <= idx < n:
                return tokens[idx].attribute
            return ""

        def line(idx):
            if 0 <= idx < n:
                return tokens[idx].line
            return 0

        def split_top_level(token_list, delimiter=","):
            parts, cur, depth = [], [], 0
            for tk in token_list:
                a = tk.attribute
                if a in {"(", "[", "{"}:
                    depth += 1
                    cur.append(tk)
                elif a in {")", "]", "}"}:
                    depth -= 1
                    cur.append(tk)
                elif a == delimiter and depth == 0:
                    parts.append(cur)
                    cur = []
                else:
                    cur.append(tk)
            parts.append(cur)
            return parts

        def strip_outer_braces(token_list):
            if len(token_list) >= 2 and token_list[0].attribute == "{" and token_list[-1].attribute == "}":
                return token_list[1:-1]
            return token_list

        def tokens_text(token_list):
            return " ".join(t.attribute for t in token_list).replace(" . ", ".").replace(" [ ", "[").replace(" ]", "]")

        def parse_type_at(idx):
            if attr(idx) == "struct" and ttype(idx + 1) == "IDENTIFIER":
                return f"struct {attr(idx + 1)}", idx + 2

            if ttype(idx) == "KEYWORD" and attr(idx) in {
                "int", "float", "double", "char", "void", "long", "short", "signed", "unsigned"
            }:
                base = attr(idx)
                idx += 1
                pointer = 0
                while attr(idx) == "*":
                    pointer += 1
                    idx += 1
                return base + ("*" * pointer), idx

            if ttype(idx) == "IDENTIFIER" and attr(idx) in struct_defs:
                return f"struct {attr(idx)}", idx + 1

            return None, idx

        def array_type(base_type, dims):
            out = base_type
            for dim in dims:
                out += f"[{dim}]"
            return out

        def add_symbol(name, type_name):
            env_stack[-1][name] = {"type": type_name, "offset": next_offset[0]}
            next_offset[0] -= 2

        def lookup_symbol(name):
            for env in reversed(env_stack):
                if name in env:
                    return env[name]
            return None

        def parse_declarator(idx):
            pointer = 0
            while attr(idx) == "*":
                pointer += 1
                idx += 1
            if ttype(idx) != "IDENTIFIER":
                return None, idx
            name = attr(idx)
            decl_line = line(idx)
            idx += 1
            dims = []
            while attr(idx) == "[":
                idx += 1
                dim = attr(idx) if ttype(idx) in {"CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"} else ""
                if dim:
                    dims.append(int(dim, 0))
                while idx < n and attr(idx) != "]":
                    idx += 1
                if attr(idx) == "]":
                    idx += 1
            return {"name": name, "line": decl_line, "pointer": pointer, "dims": dims}, idx

        def expr_type(node_label):
            marker = "[type: "
            if marker not in node_label:
                return "int"
            return node_label.split(marker, 1)[1].split("]", 1)[0]

        def identifier_node(name, at_line, lvalue=True, include_offset=True):
            sym = lookup_symbol(name)
            if sym:
                parts = [f'IDENTIFIER  "{name}"  @{at_line}', f"[type: {sym['type']}]", f"[symbol: {name}]"]
                if include_offset:
                    parts.append(f"[offset: {sym['offset']}]")
                if lvalue:
                    parts.append("[lvalue]")
                return Node("  ".join(parts))
            return Node(f'IDENTIFIER  "{name}"  @{at_line}')

        def literal_node(tk):
            tk_type = TYPES.get(tk.type, "")
            if tk_type in {"CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"}:
                return Node(f'LITERAL_INT  "{tk.attribute}"  @{tk.line}  [type: int]')
            if tk_type == "CONST_FLOAT":
                return Node(f'LITERAL_FLOAT  "{tk.attribute}"  @{tk.line}  [type: float]')
            if tk_type == "CONST_CHAR":
                return Node(f'LITERAL_CHAR  "{tk.attribute}"  @{tk.line}  [type: char]')
            if tk_type == "STRING_LITERAL":
                return Node(f'LITERAL_STRING  "{tk.attribute}"  @{tk.line}  [type: char*]')
            return Node(f'UNKNOWN_LITERAL  "{tk.attribute}"  @{tk.line}')

        def parse_postfix(token_list):
            if not token_list:
                return Node("EMPTY_EXPR")
            if len(token_list) == 1:
                tk = token_list[0]
                if TYPES.get(tk.type, "") == "IDENTIFIER":
                    return identifier_node(tk.attribute, tk.line)
                return literal_node(tk)

            if TYPES.get(token_list[0].type, "") == "IDENTIFIER":
                base = identifier_node(token_list[0].attribute, token_list[0].line)
                base_type = expr_type(base.label)
                idx = 1
                cur = base
                cur_type = base_type
                while idx < len(token_list):
                    a = token_list[idx].attribute
                    if a == "." and idx + 1 < len(token_list):
                        member = token_list[idx + 1].attribute
                        member_type = "int"
                        if cur_type.startswith("struct "):
                            sname = cur_type.split(" ", 1)[1]
                            for field in struct_defs.get(sname, []):
                                if field["name"] == member:
                                    member_type = array_type(field["type"], field["dims"])
                                    break
                        cur = Node(f'MEMBER_EXPR  ".{member}"  @{token_list[idx].line}  [type: {member_type}]', [cur])
                        cur_type = member_type
                        idx += 2
                        continue

                    if a == "[":
                        depth = 1
                        start = idx + 1
                        idx += 1
                        while idx < len(token_list) and depth > 0:
                            if token_list[idx].attribute == "[":
                                depth += 1
                            elif token_list[idx].attribute == "]":
                                depth -= 1
                            idx += 1
                        index_tokens = token_list[start:idx - 1]
                        elem_type = cur_type.rsplit("[", 1)[0] if "[" in cur_type else cur_type
                        cur = Node(f"ARRAY_SUBSCRIPT  @{token_list[start - 1].line}  [type: {elem_type}]  [lvalue]", [
                            cur,
                            parse_expr(index_tokens),
                        ])
                        cur_type = elem_type
                        continue

                    if a == "(":
                        args = []
                        inside = token_list[idx + 1:-1]
                        for part in split_top_level(inside):
                            if part:
                                args.append(parse_expr(part))
                        ret_type = "int" if token_list[0].attribute == "printf" else "void"
                        cur = Node(f'FUNC_CALL  "{token_list[0].attribute}"  @{token_list[0].line}  [type: {ret_type}]', args)
                        return cur

                    break
                return cur

            return Node(" ".join(t.attribute for t in token_list))

        def parse_expr(token_list):
            if not token_list:
                return Node("EMPTY_EXPR")

            depth = 0
            for ops in ({"=", "+=", "-="}, {"||"}, {"&&"}, {"==", "!="}, {"<", ">", "<=", ">="}, {"+", "-"}, {"*", "/", "%"}):
                scan = range(len(token_list) - 1, -1, -1) if ops not in ({"=", "+=", "-="},) else range(len(token_list))
                for idx in scan:
                    a = token_list[idx].attribute
                    if a in {")", "]", "}"}:
                        depth += 1
                    elif a in {"(", "[", "{"}:
                        depth -= 1
                    elif depth == 0 and a in ops:
                        left = parse_expr(token_list[:idx])
                        right = parse_expr(token_list[idx + 1:])
                        if a in {"=", "+=", "-="}:
                            return Node(f"ASSIGN_EXPR  op={a}  @{token_list[idx].line}  [type: {expr_type(right.label)}]", [left, right])
                        return Node(f"BINARY_EXPR  op={a}  @{token_list[idx].line}  [type: int]", [left, right])

            if len(token_list) == 2 and token_list[1].attribute in {"++", "--"}:
                return Node(f"UNARY_EXPR  op={token_list[1].attribute}  @{token_list[1].line}  [type: int]", [
                    parse_expr([token_list[0]])
                ])
            return parse_postfix(token_list)

        def find_matching(idx, left="{", right="}"):
            depth = 0
            while idx < n:
                if attr(idx) == left:
                    depth += 1
                elif attr(idx) == right:
                    depth -= 1
                    if depth == 0:
                        return idx
                idx += 1
            return n - 1

        def parse_parenthesized(idx):
            if attr(idx) != "(":
                return [], idx
            end = find_matching(idx, "(", ")")
            return tokens[idx + 1:end], end + 1

        def collect_until(idx, stops):
            start, depth = idx, 0
            while idx < n:
                a = attr(idx)
                if a in {"(", "[", "{"}:
                    depth += 1
                elif a in {")", "]", "}"}:
                    depth -= 1
                elif depth == 0 and a in stops:
                    break
                idx += 1
            return tokens[start:idx], idx

        def parse_initializer(base_type, dims, init_tokens, at_line, field_names=None):
            init_tokens = strip_outer_braces(init_tokens)
            if field_names:
                children = []
                parts = split_top_level(init_tokens)
                for field, part in zip(field_names, parts):
                    field_type = array_type(field["type"], field["dims"])
                    children.append(Node(f'INIT_FIELD  "{field["name"]}"  @{at_line}  [type: {field_type}]',
                                         parse_initializer(field["type"], field["dims"], part, at_line).children or [parse_expr(strip_outer_braces(part))]))
                return Node("INIT_LIST", children)

            if dims:
                children = [parse_expr(strip_outer_braces(part)) for part in split_top_level(init_tokens) if part]
                return Node("INIT_LIST", children)
            return parse_expr(init_tokens)

        def parse_declaration(idx):
            type_name, after_type = parse_type_at(idx)
            if type_name is None:
                return None, idx + 1
            children = []
            idx = after_type
            while idx < n and attr(idx) != ";":
                decl, idx = parse_declarator(idx)
                if not decl:
                    idx += 1
                    continue
                full_type = array_type(type_name + ("*" * decl["pointer"]), decl["dims"])
                add_symbol(decl["name"], full_type)
                node_children = [Node(f'TYPE_SPEC  "{full_type}"  @{decl["line"]}')]
                if attr(idx) == "=":
                    init_tokens, idx = collect_until(idx + 1, {",", ";"})
                    field_names = None
                    if type_name.startswith("struct "):
                        field_names = struct_defs.get(type_name.split(" ", 1)[1], [])
                    init_node = parse_initializer(type_name, decl["dims"], init_tokens, decl["line"], field_names)
                    if init_node.label == "INIT_LIST":
                        node_children.extend(init_node.children)
                    else:
                        node_children.append(init_node)
                children.append(Node(f'VAR_DECL  "{decl["name"]}"  @{decl["line"]}  [type: {full_type}]', node_children))
                if attr(idx) == ",":
                    idx += 1
                    continue
                break
            if attr(idx) == ";":
                idx += 1
            return children, idx

        def parse_statement(idx):
            if idx >= n:
                return None, idx
            a = attr(idx)
            if a == "{":
                return parse_block(idx)
            if a == "while":
                cond, after_cond = parse_parenthesized(idx + 1)
                body, next_idx = parse_statement(after_cond)
                false_info = while_false_targets.pop(0) if while_false_targets else None
                loop_info = loop_back_targets.pop(0) if loop_back_targets else None
                label = f"WHILE_STMT  @{line(idx)}  [control: while({tokens_text(cond)})]"
                if false_info:
                    label += f"  [false -> quad {false_info[1]}: exit loop]"
                if body and body.label.startswith("COMPOUND_STMT"):
                    body.label += "  [loop_body: execute nested statements, then jump back to while condition]"
                    if loop_info:
                        body.label += f"  [loop_back -> quad {loop_info[1]}]"
                return Node(label, [parse_expr(cond), body]), next_idx
            if a == "if":
                cond, after_cond = parse_parenthesized(idx + 1)
                body, next_idx = parse_statement(after_cond)
                children = [parse_expr(cond), body]
                if attr(next_idx) == "else":
                    else_body, next_idx = parse_statement(next_idx + 1)
                    children.append(else_body)
                false_info = if_false_targets.pop(0) if if_false_targets else None
                label = f"IF_STMT  @{line(idx)}  [control: if({tokens_text(cond)})]"
                if false_info:
                    label += f"  [false -> quad {false_info[1]}: skip then]"
                return Node(label, children), next_idx
            if a == "return":
                expr_tokens, next_idx = collect_until(idx + 1, {";"})
                children = [parse_expr(expr_tokens)] if expr_tokens else []
                if attr(next_idx) == ";":
                    next_idx += 1
                return Node(f"RETURN_STMT  @{line(idx)}", children), next_idx
            type_name, _ = parse_type_at(idx)
            if type_name is not None and not (ttype(idx + 1) == "IDENTIFIER" and attr(idx + 2) == "("):
                decl_nodes, next_idx = parse_declaration(idx)
                if len(decl_nodes) == 1:
                    return decl_nodes[0], next_idx
                return Node("DECL_STMT", decl_nodes), next_idx
            expr_tokens, next_idx = collect_until(idx, {";"})
            if attr(next_idx) == ";":
                next_idx += 1
            return Node(f"EXPR_STMT  @{line(idx)}", [parse_expr(expr_tokens)]), next_idx

        def parse_block(idx):
            block_line = line(idx)
            idx += 1
            children = []
            while idx < n and attr(idx) != "}":
                node, idx = parse_statement(idx)
                if node:
                    children.append(node)
            if attr(idx) == "}":
                idx += 1
            return Node(f"COMPOUND_STMT  @{block_line}", children), idx

        def parse_struct_decl(idx):
            name = attr(idx + 1)
            decl_line = line(idx)
            idx += 3
            fields = []
            child_nodes = []
            while idx < n and attr(idx) != "}":
                field_type, after_type = parse_type_at(idx)
                if field_type is None:
                    idx += 1
                    continue
                decl, idx2 = parse_declarator(after_type)
                if decl:
                    full_type = array_type(field_type + ("*" * decl["pointer"]), decl["dims"])
                    comment = comments_by_line.get(decl["line"], "")
                    label = f'FIELD_DECL  "{decl["name"]}"  @{decl["line"]}  [type: {full_type}]'
                    if comment:
                        label += f"  [comment: {comment}]"
                    child_nodes.append(Node(label))
                    fields.append({"name": decl["name"], "type": field_type + ("*" * decl["pointer"]), "dims": decl["dims"]})
                idx = idx2
                while idx < n and attr(idx) != ";":
                    idx += 1
                if attr(idx) == ";":
                    idx += 1
            struct_defs[name] = fields
            while idx < n and attr(idx) != ";":
                idx += 1
            return Node(f'STRUCT_DECL  "{name}"  @{decl_line}', child_nodes), idx + 1

        def parse_function(idx):
            ret_type, after_type = parse_type_at(idx)
            if ret_type is None or ttype(after_type) != "IDENTIFIER" or attr(after_type + 1) != "(":
                return None, idx
            name = attr(after_type)
            fn_line = line(after_type)
            _, after_params = parse_parenthesized(after_type + 1)
            env_stack.append({})
            next_offset[0] = -2
            body = None
            if attr(after_params) == "{":
                body, next_idx = parse_block(after_params)
            else:
                next_idx = after_params
            env_stack.pop()
            return Node(f'FUNC_DEF  "{name}"  @{fn_line}', [
                Node(f'TYPE_SPEC  "{ret_type}"  @{line(idx)}'),
                body or Node("COMPOUND_STMT"),
            ]), next_idx

        root = Node("PROGRAM  @1", [])
        i = 0
        while i < n:
            if attr(i) == "struct" and ttype(i + 1) == "IDENTIFIER" and attr(i + 2) == "{":
                node, i = parse_struct_decl(i)
                root.children.append(node)
                continue
            fn_node, next_i = parse_function(i)
            if fn_node:
                root.children.append(fn_node)
                i = next_i
                continue
            i += 1

        def render(node):
            lines = [node.label]

            def walk(children, prefix):
                for idx, child in enumerate(children):
                    last = idx == len(children) - 1
                    connector = "`-- " if last else "|-- "
                    lines.append(prefix + connector + child.label)
                    walk(child.children, prefix + ("    " if last else "|   "))

            walk(node.children, "")
            return "\n".join(lines)

        return render(root)

    def _generate_backpatch_report(self) -> str:
        """生成控制流回填检查说明。"""
        from constants import TYPES

        quads = self.ir_generator.quadruples if self.ir_generator else []
        controls = []
        for token in self.result.tokens:
            if TYPES.get(token.type, "") == "KEYWORD" and token.attribute in {"while", "if", "for"}:
                controls.append(token.attribute)
        control_summary = " -> ".join(dict.fromkeys(controls)) if controls else "none"
        lines = [
            "BACKPATCH_CHECK",
            "GROUP: 第4组 while(){ if(){} }",
            f"CONTROL_FLOW: {control_summary}",
            "",
            "QUADRUPLES",
        ]
        for idx, quad in enumerate(quads):
            note = ""
            if quad.op.startswith("j") and quad.op != "j":
                has_loop_back = any(q.op == "j" and q.result == str(idx) for q in quads)
                if has_loop_back:
                    note = "    ; while 假出口，回填到循环结束"
                elif quad.result.isdigit() and int(quad.result) > idx:
                    note = "    ; if 假出口，回填到 then 后"
                else:
                    note = "    ; 条件跳转"
            elif quad.op == "j":
                note = "    ; while 体结束，跳回条件入口"
            elif quad.op == "=[]":
                note = "    ; 数组取值"
            lines.append(f"{idx:4d}: {quad.to_readable()}{note}")

        while_false = []
        if_false = []
        loop_back = []
        for idx, quad in enumerate(quads):
            if quad.op == "j" and quad.result.isdigit() and int(quad.result) <= idx:
                loop_back.append((idx, int(quad.result)))
            elif quad.op.startswith("j") and quad.op != "j" and quad.result.isdigit():
                has_loop_back = any(q.op == "j" and q.result == str(idx) for q in quads)
                if has_loop_back:
                    while_false.append((idx, int(quad.result)))
                else:
                    if_false.append((idx, int(quad.result)))

        lines.extend(["", "BACKPATCH_LISTS"])
        for idx, target in while_false:
            lines.append(f"while.false_list = {{{idx}}} -> 回填到 quad {target}")
        for idx, target in if_false:
            lines.append(f"if.false_list    = {{{idx}}} -> 回填到 quad {target}")
        for idx, target in loop_back:
            lines.append(f"while.loop_back  = quad {idx} -> 跳回 quad {target}")
        return "\n".join(lines)

    def _collect_object_macros(self, tokens: List) -> dict:
        """Collect simple object-like #define constants, such as '#define MAX 5'."""
        from constants import TYPES

        macros = {}
        for token in tokens:
            if TYPES.get(token.type, "") != "PREPROCESSOR":
                continue
            parts = token.attribute.strip().split()
            if len(parts) >= 3 and parts[0] == "#define":
                name = parts[1]
                value = parts[2]
                if name.isidentifier():
                    macros[name] = value
        return macros
     
    def save_assembly(self, filename: str) -> str:
        """保存汇编代码到文件"""
        if self.code_generator and self.result.assembly_code:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.result.assembly_code)
            return filename
        return ""
    
    def save_ir(self, filename: str) -> str:
        """保存中间代码到文件"""
        if self.ir_generator:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.ir_generator.to_readable_string())
            return filename
        return ""


def main():
    # 读取示例C代码
    with open('c-code.c', 'r', encoding='utf-8') as f:
        source_code = f.read()
    
    print("C语言编译器".center(80, "="))
    print(f"\n源代码:\n{source_code}\n")
    
    # 创建编译器并编译
    compiler = Compiler()
    result = compiler.compile(source_code, verbose=True)
    
    # 输出结果
    print("\n" + str(result))
    
    # 保存输出文件
    if result.success:
        compiler.save_ir("output.ir")
        compiler.save_assembly("output.asm")
        print("\n生成的文件:")
        print("  - output.ir   (中间代码)")
        print("  - output.asm  (汇编代码)")


if __name__ == "__main__":
    main()

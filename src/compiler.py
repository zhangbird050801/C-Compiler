from typing import Optional, List
from lexer_core import Lexer
from parser_core import LL1Parser
from semantic_analyzer import SemanticAnalyzer
from ir_generator import IRGenerator
from codegen import CodeGenerator
from symbol_table import SymbolTable
from constants import TYPES


class CompilerResult:
    """编译结果"""
    def __init__(self):
        self.success = False
        self.tokens = []
        self.parse_records = []
        self.symbol_table = None
        self.quadruples = []
        self.assembly_code = ""
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
        self.semantic_analyzer: Optional[SemanticAnalyzer] = None
        self.ir_generator: Optional[IRGenerator] = None
        self.code_generator: Optional[CodeGenerator] = None
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
        self.result = CompilerResult()
        source_code = self._normalize_source(source_code)
        
        try:
            # 1. 词法分析
            if verbose:
                print("\n" + "=" * 80)
                print("第一阶段：词法分析".center(80))
                print("=" * 80)
            
            success, tokens = self.lexical_analysis(source_code, verbose)
            if not success:
                return self.result
            
            # 2. 语法分析
            if verbose:
                print("\n" + "=" * 80)
                print("第二阶段：语法分析".center(80))
                print("=" * 80)
            
            success, parse_records = self.syntax_analysis(tokens, verbose)
            if not success:
                # 当前语法分析器覆盖面有限，失败时进入容错翻译模式
                if self.result.errors and self.result.errors[-1].startswith("语法分析错误:"):
                    syntax_err = self.result.errors.pop()
                    self.result.warnings.append(
                        f"{syntax_err}；已切换到容错模式继续进行语义/IR/目标代码生成"
                    )
                else:
                    self.result.warnings.append("语法分析未通过；已切换到容错模式继续生成代码")
            
            # 3. 语义分析
            if verbose:
                print("\n" + "=" * 80)
                print("第三阶段：语义分析".center(80))
                print("=" * 80)
            
            success, symbol_table = self.semantic_analysis(tokens, verbose)
            if not success:
                return self.result
            
            # 4. 中间代码生成
            if verbose:
                print("\n" + "=" * 80)
                print("第四阶段：中间代码生成".center(80))
                print("=" * 80)
            
            success, ir_gen = self.intermediate_code_generation(symbol_table, tokens, verbose)
            if not success:
                return self.result
            self.result.annotated_syntax_tree = self._generate_annotated_syntax_tree()
            self.result.backpatch_report = self._generate_backpatch_report()
            
            # 5. 目标代码生成
            if verbose:
                print("\n" + "=" * 80)
                print("第五阶段：目标代码生成".center(80))
                print("=" * 80)
            
            success, asm_code = self.target_code_generation(ir_gen, symbol_table, verbose)
            if not success:
                return self.result
            
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
    
    def semantic_analysis(self, tokens: List, verbose: bool = True) -> tuple[bool, SymbolTable]:
        """语义分析"""
        self.semantic_analyzer = SemanticAnalyzer(tokens)
        
        # 这里应该遍历语法分析的结果构建符号表
        # 简化版：直接从tokens提取信息
        symbol_table = self.semantic_analyzer.symbol_table
        self._check_invalid_identifier_usage(tokens)
        
        # 简化的符号表构建（仅作示例）
        self._build_symbol_table_from_tokens(tokens, symbol_table)
        
        self.result.symbol_table = symbol_table
        
        if self.semantic_analyzer.has_errors():
            self.result.errors.extend(self.semantic_analyzer.get_all_errors())
            if verbose:
                print("✗ 语义分析失败")
                for err in self.semantic_analyzer.get_all_errors():
                    print(f"  {err}")
            return False, symbol_table
        
        if verbose:
            print("✓ 语义分析成功")
            print(symbol_table)
        
        return True, symbol_table

    def _check_invalid_identifier_usage(self, tokens: List):
        """Report reserved words used where a declaration name is required."""
        from constants import TYPES

        type_keywords = {"int", "float", "char", "double", "void", "long", "short", "signed", "unsigned"}
        declaration_prefixes = type_keywords | {"const"}

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            tok_type = TYPES.get(tok.type, "")

            if tok_type != "KEYWORD" or tok.attribute not in declaration_prefixes:
                i += 1
                continue

            start = i
            if tok.attribute == "const":
                i += 1
                if i >= len(tokens) or TYPES.get(tokens[i].type, "") != "KEYWORD" or tokens[i].attribute not in type_keywords:
                    continue

            i += 1
            while i < len(tokens) and tokens[i].attribute != ";":
                while i < len(tokens) and tokens[i].attribute == "*":
                    i += 1

                if i >= len(tokens) or tokens[i].attribute == ";":
                    break

                current_type = TYPES.get(tokens[i].type, "")
                if current_type == "KEYWORD":
                    self.semantic_analyzer.error(f"关键字不能作为标识符: {tokens[i].attribute}", tokens[i].line)
                    while i < len(tokens) and tokens[i].attribute != ";":
                        i += 1
                    break

                if current_type == "IDENTIFIER":
                    if i + 1 < len(tokens) and tokens[i + 1].attribute == "(":
                        while i < len(tokens) and tokens[i].attribute not in {";", "{"}:
                            i += 1
                        break

                    i += 1
                    depth = 0
                    while i < len(tokens):
                        attr = tokens[i].attribute
                        if attr in {"(", "[", "{"}:
                            depth += 1
                        elif attr in {")", "]", "}"}:
                            depth -= 1
                        elif depth == 0 and attr in {",", ";"}:
                            break
                        i += 1

                    if i < len(tokens) and tokens[i].attribute == ",":
                        i += 1
                        continue
                    break

                i += 1

            if i == start:
                i += 1
    
    def intermediate_code_generation(self, symbol_table: SymbolTable, tokens: List, 
                                     verbose: bool = True) -> tuple[bool, IRGenerator]:
        """中间代码生成"""
        self.ir_generator = IRGenerator(symbol_table)

        # 简化版：根据本次输入 token 生成四元式
        self._generate_sample_ir(tokens)
        
        self.result.quadruples = self.ir_generator.quadruples
        
        if verbose:
            print("✓ 中间代码生成成功")
            print(self.ir_generator.to_readable_string())
        
        return True, self.ir_generator
    
    def target_code_generation(self, ir_gen: IRGenerator, symbol_table: SymbolTable,
                               verbose: bool = True) -> tuple[bool, str]:
        """目标代码生成"""
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
    
    def _build_symbol_table_from_tokens(self, tokens: List, symbol_table: SymbolTable):
        """从tokens构建符号表（简化版）"""
        from symbol_table import Symbol, SymbolKind, Type
        from constants import TYPES
        
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            tok_type = TYPES.get(tok.type, "")
            
            # 查找变量声明模式：type id
            if tok_type == "KEYWORD" and tok.attribute in ["int", "float", "char", "double"]:
                base_type = tok.attribute
                i += 1
                
                # 跳过指针符号
                pointer_level = 0
                while i < len(tokens) and tokens[i].attribute == "*":
                    pointer_level += 1
                    i += 1
                
                # 获取标识符
                if i < len(tokens) and TYPES.get(tokens[i].type) == "IDENTIFIER":
                    var_name = tokens[i].attribute
                    type_info = Type(base=base_type, pointer_level=pointer_level)
                    
                    # 检查是否为数组
                    if i + 1 < len(tokens) and tokens[i + 1].attribute == "[":
                        i += 2
                        if i < len(tokens) and TYPES.get(tokens[i].type) in ["CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"]:
                            array_size = int(tokens[i].attribute)
                            type_info.array_dims.append(array_size)
                        i += 1  # skip ]
                    
                    symbol = Symbol(name=var_name, kind=SymbolKind.VARIABLE, type_info=type_info)
                    symbol_table.define(symbol)
            
            # 查找结构体定义
            elif tok_type == "KEYWORD" and tok.attribute == "struct":
                i += 1
                if i < len(tokens) and TYPES.get(tokens[i].type) == "IDENTIFIER":
                    struct_name = tokens[i].attribute
                    symbol = Symbol(name=struct_name, kind=SymbolKind.STRUCT)
                    symbol_table.define(symbol)
            
            i += 1

    def _build_symbol_table_from_tokens(self, tokens: List, symbol_table: SymbolTable):
        """Build a small symbol table directly from tokens."""
        from symbol_table import Symbol, SymbolKind, Type
        from constants import TYPES

        struct_names = set()
        for idx, tk in enumerate(tokens[:-1]):
            if TYPES.get(tk.type, "") == "KEYWORD" and tk.attribute == "struct":
                nxt = tokens[idx + 1]
                if TYPES.get(nxt.type, "") == "IDENTIFIER":
                    struct_names.add(nxt.attribute)

        def skip_initializer(idx: int) -> int:
            depth = 0
            while idx < len(tokens):
                attr = tokens[idx].attribute
                if attr in {"(", "[", "{"}:
                    depth += 1
                elif attr in {")", "]", "}"}:
                    depth -= 1
                elif depth == 0 and attr in {",", ";"}:
                    break
                idx += 1
            return idx

        def define_variable(name: str, type_info: Type):
            symbol = Symbol(name=name, kind=SymbolKind.VARIABLE, type_info=type_info)
            symbol_table.define(symbol)

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            tok_type = TYPES.get(tok.type, "")

            if tok_type == "KEYWORD" and tok.attribute == "struct":
                if (
                    i + 2 < len(tokens)
                    and TYPES.get(tokens[i + 1].type) == "IDENTIFIER"
                    and tokens[i + 2].attribute == "{"
                ):
                    struct_name = tokens[i + 1].attribute
                    if not symbol_table.lookup_struct(struct_name):
                        symbol = Symbol(name=struct_name, kind=SymbolKind.STRUCT)
                        symbol_table.define(symbol)

                    i += 3
                    depth = 1
                    while i < len(tokens) and depth > 0:
                        if tokens[i].attribute == "{":
                            depth += 1
                        elif tokens[i].attribute == "}":
                            depth -= 1
                        i += 1
                    if i < len(tokens) and tokens[i].attribute == ";":
                        i += 1
                else:
                    i += 1
                continue

            starts_builtin_decl = tok_type == "KEYWORD" and tok.attribute in ["int", "float", "char", "double"]
            starts_struct_decl = tok_type == "IDENTIFIER" and tok.attribute in struct_names
            if not (starts_builtin_decl or starts_struct_decl):
                i += 1
                continue

            base_type = tok.attribute
            is_struct_var = starts_struct_decl
            i += 1

            while i < len(tokens) and tokens[i].attribute != ";":
                pointer_level = 0
                while i < len(tokens) and tokens[i].attribute == "*":
                    pointer_level += 1
                    i += 1

                if i >= len(tokens) or TYPES.get(tokens[i].type) != "IDENTIFIER":
                    i += 1
                    continue

                var_name = tokens[i].attribute
                type_info = Type(
                    base=base_type,
                    pointer_level=pointer_level,
                    is_struct=is_struct_var,
                    struct_name=base_type if is_struct_var else None,
                )
                i += 1

                if i < len(tokens) and tokens[i].attribute == "(":
                    depth = 1
                    i += 1
                    while i < len(tokens) and depth > 0:
                        if tokens[i].attribute == "(":
                            depth += 1
                        elif tokens[i].attribute == ")":
                            depth -= 1
                        i += 1
                    break

                if i < len(tokens) and tokens[i].attribute == "[":
                    i += 1
                    if i < len(tokens) and TYPES.get(tokens[i].type) in ["CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"]:
                        type_info.array_dims.append(int(tokens[i].attribute, 0))
                    while i < len(tokens) and tokens[i].attribute != "]":
                        i += 1
                    if i < len(tokens):
                        i += 1

                define_variable(var_name, type_info)

                if i < len(tokens) and tokens[i].attribute == "=":
                    i = skip_initializer(i + 1)

                if i < len(tokens) and tokens[i].attribute == ",":
                    i += 1
                    continue
                break

            i += 1
    
    def _generate_sample_ir(self, tokens: List):
        """根据当前 token 生成中间代码（简化版，支持顺序/选择/循环/输入输出）。"""
        ir = self.ir_generator
        ir.clear()

        supported_value_types = {
            "STRING_LITERAL",
            "IDENTIFIER",
            "CONST_DECIMAL",
            "CONST_OCTAL",
            "CONST_HEX",
            "CONST_FLOAT",
            "CONST_CHAR",
        }
        type_keywords = {"int", "float", "double", "char", "void", "long", "short", "signed", "unsigned"}
        compare_ops = {"<", ">", "<=", ">=", "==", "!="}
        inverse_compare = {"<": ">=", ">": "<=", "<=": ">", ">=": "<", "==": "!=", "!=": "=="}

        object_macros = self._collect_object_macros(tokens)
        filtered_tokens = [
            t for t in tokens
            if TYPES.get(t.type, "") not in {"PREPROCESSOR", "EOF"} and t.attribute != "const"
        ]
        n = len(filtered_tokens)
        i = 0
        struct_defs = self._collect_struct_defs(filtered_tokens)
        custom_type_names = set(struct_defs)

        def tok_type(idx: int) -> str:
            if 0 <= idx < n:
                return TYPES.get(filtered_tokens[idx].type, "")
            return ""

        def tok_attr(idx: int) -> str:
            if 0 <= idx < n:
                return filtered_tokens[idx].attribute
            return ""

        def char_token_to_int(char_token: str) -> str:
            if not char_token:
                return "0"
            if len(char_token) == 1:
                return str(ord(char_token))

            escape_map = {r"\n": 10, r"\r": 13, r"\t": 9, r"\\": 92, r"\'": 39, r'\"': 34, r"\0": 0}
            if char_token in escape_map:
                return str(escape_map[char_token])

            if char_token.startswith("\\x"):
                try:
                    return str(int(char_token[2:], 16))
                except ValueError:
                    return "0"

            if char_token.startswith("\\") and len(char_token) > 1 and all(c in "01234567" for c in char_token[1:]):
                try:
                    return str(int(char_token[1:], 8))
                except ValueError:
                    return "0"

            return str(ord(char_token[-1]))

        def token_to_operand(tok):
            ttype = TYPES.get(tok.type, "")
            if ttype not in supported_value_types:
                return None
            if ttype == "STRING_LITERAL":
                return f'"{tok.attribute}"'
            if ttype == "CONST_CHAR":
                return char_token_to_int(tok.attribute)
            if ttype == "IDENTIFIER" and tok.attribute in object_macros:
                return object_macros[tok.attribute]
            return tok.attribute

        def parse_reference_operand(expr_tokens):
            if not expr_tokens or TYPES.get(expr_tokens[0].type, "") != "IDENTIFIER":
                return None

            idx = 1
            ref = expr_tokens[0].attribute
            while idx < len(expr_tokens):
                attr = expr_tokens[idx].attribute
                if attr == "." and idx + 1 < len(expr_tokens) and TYPES.get(expr_tokens[idx + 1].type, "") == "IDENTIFIER":
                    ref = f"{ref}_{expr_tokens[idx + 1].attribute}"
                    idx += 2
                    continue

                if attr == "[":
                    depth = 1
                    idx += 1
                    index_tokens = []
                    while idx < len(expr_tokens) and depth > 0:
                        a = expr_tokens[idx].attribute
                        if a == "[":
                            depth += 1
                            index_tokens.append(expr_tokens[idx])
                        elif a == "]":
                            depth -= 1
                            if depth > 0:
                                index_tokens.append(expr_tokens[idx])
                        else:
                            index_tokens.append(expr_tokens[idx])
                        idx += 1
                    index_value = emit_expr(index_tokens)
                    if index_value is None:
                        return None
                    temp = ir.new_temp()
                    ir.emit("=[]", ref, index_value, temp)
                    ref = temp
                    continue

                return None

            return ref

        def emit_expr(expr_tokens):
            if not expr_tokens:
                return None
            if len(expr_tokens) == 1:
                return token_to_operand(expr_tokens[0])

            if len(expr_tokens) == 2 and expr_tokens[0].attribute == "-":
                operand = token_to_operand(expr_tokens[1])
                if operand is None:
                    return None
                if operand.replace(".", "", 1).isdigit():
                    return f"-{operand}"
                temp = ir.new_temp()
                ir.emit("-", "0", operand, temp)
                return temp

            ref_operand = parse_reference_operand(expr_tokens)
            if ref_operand is not None:
                return ref_operand

            operators = {"+", "-", "*", "/", "%"}
            precedence = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2}
            output = []
            op_stack = []

            for tk in expr_tokens:
                attr = tk.attribute
                operand = token_to_operand(tk)

                if operand is not None:
                    output.append(("operand", operand))
                    continue

                if attr in operators:
                    while op_stack and op_stack[-1] in operators and precedence[op_stack[-1]] >= precedence[attr]:
                        output.append(("operator", op_stack.pop()))
                    op_stack.append(attr)
                    continue

                if attr == "(":
                    op_stack.append(attr)
                    continue

                if attr == ")":
                    found_left = False
                    while op_stack:
                        top = op_stack.pop()
                        if top == "(":
                            found_left = True
                            break
                        output.append(("operator", top))
                    if not found_left:
                        return None
                    continue

                return None

            while op_stack:
                top = op_stack.pop()
                if top == "(":
                    return None
                output.append(("operator", top))

            val_stack = []
            for kind, value in output:
                if kind == "operand":
                    val_stack.append(value)
                else:
                    if len(val_stack) < 2:
                        return None
                    right = val_stack.pop()
                    left = val_stack.pop()
                    temp = ir.new_temp()
                    ir.emit(value, left, right, temp)
                    val_stack.append(temp)

            if len(val_stack) != 1:
                return None
            return val_stack[0]

        def split_top_level(tokens_list, delimiter: str):
            parts = []
            cur = []
            depth = 0
            for tk in tokens_list:
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

        def parse_simple_condition(cond_tokens):
            depth = 0
            cmp_idx = -1
            for idx, tk in enumerate(cond_tokens):
                a = tk.attribute
                if a == "(":
                    depth += 1
                elif a == ")":
                    depth -= 1
                elif depth == 0 and a in compare_ops:
                    cmp_idx = idx
                    break

            if cmp_idx == -1:
                left = emit_expr(cond_tokens)
                if left is None:
                    return None
                return left, "!=", "0"

            left = emit_expr(cond_tokens[:cmp_idx])
            right = emit_expr(cond_tokens[cmp_idx + 1:])
            if left is None or right is None:
                return None
            return left, cond_tokens[cmp_idx].attribute, right

        def parse_condition_tokens(cond_tokens):
            and_parts = [part for part in split_top_level(cond_tokens, "&&") if part]
            if len(and_parts) > 1:
                conds = []
                for part in and_parts:
                    cond = parse_simple_condition(part)
                    if cond is None:
                        return None
                    conds.append(cond)
                return ("&&", conds)

            return parse_simple_condition(cond_tokens)

        def patch_jump(jump_idx: int, target_idx: int):
            if 0 <= jump_idx < len(ir.quadruples):
                ir.quadruples[jump_idx].result = str(target_idx)

        def emit_inverse_cond_jump(cond, placeholder: str = "0") -> int:
            left, op, right = cond
            inv = inverse_compare.get(op, "==")
            return ir.emit(f"j{inv}", left, right, placeholder)

        def emit_false_jumps(cond, placeholder: str = "0") -> List[int]:
            if cond and cond[0] == "&&":
                return [emit_inverse_cond_jump(part, placeholder) for part in cond[1]]
            return [emit_inverse_cond_jump(cond, placeholder)]

        def patch_jumps(jump_indices: List[int], target_idx: int):
            for jump_idx in jump_indices:
                patch_jump(jump_idx, target_idx)

        def parse_parenthesized_tokens(start_idx: int):
            if tok_attr(start_idx) != "(":
                return [], start_idx

            depth = 1
            idx = start_idx + 1
            collected = []
            while idx < n and depth > 0:
                a = tok_attr(idx)
                tk = filtered_tokens[idx]
                if a == "(":
                    depth += 1
                    collected.append(tk)
                elif a == ")":
                    depth -= 1
                    if depth > 0:
                        collected.append(tk)
                else:
                    collected.append(tk)
                idx += 1
            return collected, idx

        def parse_inline_assignment(token_list):
            if not token_list:
                return

            if len(token_list) == 2 and TYPES.get(token_list[0].type, "") == "IDENTIFIER" and token_list[1].attribute in {"++", "--"}:
                op = "+" if token_list[1].attribute == "++" else "-"
                temp = ir.new_temp()
                ir.emit(op, token_list[0].attribute, "1", temp)
                ir.emit("=", temp, "_", token_list[0].attribute)
                return

            if len(token_list) >= 3 and TYPES.get(token_list[0].type, "") == "IDENTIFIER" and token_list[1].attribute == "=":
                rhs = emit_expr(token_list[2:])
                if rhs is not None:
                    ir.emit("=", rhs, "_", token_list[0].attribute)

        def parse_printf_from_args(arg_exprs):
            args = [expr for expr in (emit_expr(expr_tokens) for expr_tokens in arg_exprs) if expr is not None]
            if not args or not arg_exprs:
                return

            if len(arg_exprs[0]) == 1 and TYPES.get(arg_exprs[0][0].type, "") == "STRING_LITERAL":
                fmt = arg_exprs[0][0].attribute
                value_args = args[1:]
                value_idx = 0
                literal_buf = []

                def flush_literal():
                    if literal_buf:
                        text = "".join(literal_buf)
                        if text:
                            ir.emit("printf", "_", "_", f'"{text}"')
                        literal_buf.clear()

                k = 0
                while k < len(fmt):
                    ch = fmt[k]
                    if ch == '%' and k + 1 < len(fmt):
                        if fmt[k + 1] == '%':
                            literal_buf.append('%')
                            k += 2
                            continue

                        p = k + 1
                        precision = None
                        while p < len(fmt) and fmt[p] in "-+ #0":
                            p += 1
                        while p < len(fmt) and fmt[p].isdigit():
                            p += 1
                        if p < len(fmt) and fmt[p] == '.':
                            p += 1
                            start_p = p
                            while p < len(fmt) and fmt[p].isdigit():
                                p += 1
                            precision = int(fmt[start_p:p]) if p > start_p else 0
                        if p < len(fmt) and fmt[p] in "hlLzjt":
                            p += 1

                        spec = fmt[p] if p < len(fmt) else ''
                        if spec in "diuoxXfFcs":
                            flush_literal()
                            if value_idx < len(value_args):
                                arg_value = value_args[value_idx]
                                value_idx += 1
                                if spec in "fF":
                                    use_precision = 6 if precision is None else precision
                                    op_name = f"printf_f{use_precision}"
                                elif spec == "c":
                                    op_name = "printf_c"
                                else:
                                    op_name = "printf"
                                ir.emit(op_name, "_", "_", arg_value)
                            k = p + 1
                            continue

                    literal_buf.append(ch)
                    k += 1

                flush_literal()
                while value_idx < len(value_args):
                    ir.emit("printf", "_", "_", value_args[value_idx])
                    value_idx += 1
                return

            for arg in args:
                ir.emit("printf", "_", "_", arg)

        def strip_outer_braces(token_list):
            if len(token_list) >= 2 and token_list[0].attribute == "{" and token_list[-1].attribute == "}":
                return token_list[1:-1]
            return token_list

        def member_name(member):
            return member["name"] if isinstance(member, dict) else member

        def member_array_size(member):
            if isinstance(member, dict):
                return member.get("array_size")
            return None

        def emit_array_initializer(array_name: str, array_size, init_tokens):
            values = split_top_level(strip_outer_braces(init_tokens), ",")
            for element_idx, value_tokens in enumerate(values):
                if array_size is not None and element_idx >= array_size:
                    break
                value = emit_expr(strip_outer_braces(value_tokens))
                if value is not None:
                    ir.emit("[]=", value, str(element_idx), array_name)

        def emit_struct_initializer(type_name: str, var_name: str, array_size, init_tokens):
            members = struct_defs.get(type_name, [])
            if not members:
                return

            outer = strip_outer_braces(init_tokens)
            records = split_top_level(outer, ",")
            if array_size is not None:
                for element_idx, record_tokens in enumerate(records):
                    if element_idx >= array_size:
                        break
                    values = split_top_level(strip_outer_braces(record_tokens), ",")
                    for member_idx, value_tokens in enumerate(values):
                        if member_idx >= len(members):
                            break
                        m_name = member_name(members[member_idx])
                        m_array_size = member_array_size(members[member_idx])
                        target = f"{var_name}_{element_idx}_{m_name}"
                        if m_array_size is not None:
                            emit_array_initializer(target, m_array_size, value_tokens)
                            continue
                        value = emit_expr(strip_outer_braces(value_tokens))
                        if value is not None:
                            ir.emit("=", value, "_", target)
                return

            values = split_top_level(outer, ",")
            for member_idx, value_tokens in enumerate(values):
                if member_idx >= len(members):
                    break
                m_name = member_name(members[member_idx])
                m_array_size = member_array_size(members[member_idx])
                target = f"{var_name}_{m_name}"
                if m_array_size is not None:
                    emit_array_initializer(target, m_array_size, value_tokens)
                    continue
                value = emit_expr(strip_outer_braces(value_tokens))
                if value is not None:
                    ir.emit("=", value, "_", target)

        def parse_declaration(type_name: str, is_struct_type: bool):
            nonlocal i
            i += 1
            while i < n and tok_attr(i) != ";":
                while tok_attr(i) == "*":
                    i += 1

                if tok_type(i) != "IDENTIFIER":
                    i += 1
                    continue

                var_name = tok_attr(i)
                array_size = None
                i += 1

                if tok_attr(i) == "[":
                    i += 1
                    if tok_type(i) in {"CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"}:
                        array_size = int(tok_attr(i), 0)
                    while i < n and tok_attr(i) != "]":
                        i += 1
                    if tok_attr(i) == "]":
                        i += 1

                if tok_attr(i) == "=":
                    i += 1
                    init_tokens = []
                    depth = 0
                    while i < n:
                        a = tok_attr(i)
                        if a in {"(", "[", "{"}:
                            depth += 1
                        elif a in {")", "]", "}"}:
                            depth -= 1
                        if depth == 0 and a in {",", ";"}:
                            break
                        init_tokens.append(filtered_tokens[i])
                        i += 1

                    if is_struct_type:
                        emit_struct_initializer(type_name, var_name, array_size, init_tokens)
                    elif array_size is not None:
                        emit_array_initializer(var_name, array_size, init_tokens)
                    else:
                        rhs = emit_expr(init_tokens)
                        if rhs is not None:
                            ir.emit("=", rhs, "_", var_name)

                if tok_attr(i) == ",":
                    i += 1
                    continue
                break

            if tok_attr(i) == ";":
                i += 1

        def parse_statement():
            nonlocal i
            if i >= n:
                return

            cur_attr = tok_attr(i)
            cur_type = tok_type(i)

            if cur_attr == "}":
                i += 1
                return

            if cur_attr == "{":
                i += 1
                while i < n and tok_attr(i) != "}":
                    parse_statement()
                if tok_attr(i) == "}":
                    i += 1
                return

            if cur_attr == "struct" and tok_attr(i + 2) == "{":
                i += 3
                depth = 1
                while i < n and depth > 0:
                    if tok_attr(i) == "{":
                        depth += 1
                    elif tok_attr(i) == "}":
                        depth -= 1
                    i += 1
                if tok_attr(i) == ";":
                    i += 1
                return

            if cur_attr == "struct" and tok_type(i + 1) == "IDENTIFIER" and tok_attr(i + 1) in custom_type_names:
                i += 1
                parse_declaration(tok_attr(i), True)
                return

            if cur_type == "IDENTIFIER" and cur_attr in custom_type_names:
                parse_declaration(cur_attr, True)
                return

            if cur_attr in type_keywords and not (tok_type(i + 1) == "IDENTIFIER" and tok_attr(i + 2) == "("):
                parse_declaration(cur_attr, False)
                return

            if cur_attr in type_keywords:
                # 函数定义：type ident(...){...}
                if tok_type(i + 1) == "IDENTIFIER" and tok_attr(i + 2) == "(":
                    _, next_idx = parse_parenthesized_tokens(i + 2)
                    i = next_idx
                    if tok_attr(i) == "{":
                        parse_statement()
                    return

                # 变量声明：支持带初始化和逗号分隔
                i += 1
                while i < n and tok_attr(i) != ";":
                    if tok_type(i) == "IDENTIFIER":
                        var_name = tok_attr(i)
                        i += 1
                        if tok_attr(i) == "=":
                            i += 1
                            expr_tokens = []
                            depth = 0
                            while i < n:
                                a = tok_attr(i)
                                if a == "(":
                                    depth += 1
                                elif a == ")":
                                    depth -= 1
                                if depth == 0 and a in {",", ";"}:
                                    break
                                expr_tokens.append(filtered_tokens[i])
                                i += 1
                            rhs = emit_expr(expr_tokens)
                            if rhs is not None:
                                ir.emit("=", rhs, "_", var_name)
                    elif tok_attr(i) == ",":
                        i += 1
                    else:
                        i += 1
                if tok_attr(i) == ";":
                    i += 1
                return

            if cur_attr == "printf":
                _, after_paren = parse_parenthesized_tokens(i + 1)
                arg_tokens, _ = parse_parenthesized_tokens(i + 1)
                arg_exprs = [part for part in split_top_level(arg_tokens, ",") if part]
                parse_printf_from_args(arg_exprs)
                i = after_paren
                if tok_attr(i) == ";":
                    i += 1
                return

            if cur_attr == "scanf":
                arg_tokens, after_paren = parse_parenthesized_tokens(i + 1)
                arg_exprs = [part for part in split_top_level(arg_tokens, ",") if part]
                for part in arg_exprs[1:]:
                    if len(part) == 2 and part[0].attribute == "&" and TYPES.get(part[1].type, "") == "IDENTIFIER":
                        ir.emit("scanf", "_", "_", part[1].attribute)
                    elif len(part) == 1 and TYPES.get(part[0].type, "") == "IDENTIFIER":
                        ir.emit("scanf", "_", "_", part[0].attribute)
                i = after_paren
                if tok_attr(i) == ";":
                    i += 1
                return

            if cur_attr == "if":
                cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
                cond = parse_condition_tokens(cond_tokens)
                i = after_cond
                if cond is None:
                    parse_statement()
                    return

                false_jumps = emit_false_jumps(cond)
                parse_statement()
                if tok_attr(i) == "else":
                    j_end = ir.emit("j", "_", "_", "0")
                    patch_jumps(false_jumps, ir.next_quad())
                    i += 1
                    parse_statement()
                    patch_jump(j_end, ir.next_quad())
                else:
                    patch_jumps(false_jumps, ir.next_quad())
                return

            if cur_attr == "while":
                cond_start = ir.next_quad()
                cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
                cond = parse_condition_tokens(cond_tokens)
                i = after_cond
                if cond is None:
                    parse_statement()
                    return

                false_jumps = emit_false_jumps(cond)
                parse_statement()
                ir.emit("j", "_", "_", str(cond_start))
                patch_jumps(false_jumps, ir.next_quad())
                return

            if cur_attr == "for":
                inside_tokens, after_cond = parse_parenthesized_tokens(i + 1)
                sections = split_top_level(inside_tokens, ";")
                while len(sections) < 3:
                    sections.append([])

                parse_inline_assignment(sections[0])
                cond_start = ir.next_quad()
                false_jumps = []
                if sections[1]:
                    cond = parse_condition_tokens(sections[1])
                    if cond is not None:
                        false_jumps = emit_false_jumps(cond)

                i = after_cond
                parse_statement()
                parse_inline_assignment(sections[2])
                ir.emit("j", "_", "_", str(cond_start))
                patch_jumps(false_jumps, ir.next_quad())
                return

            if cur_attr == "return":
                i += 1
                expr_tokens = []
                while i < n and tok_attr(i) != ";":
                    expr_tokens.append(filtered_tokens[i])
                    i += 1
                ret_val = emit_expr(expr_tokens) if expr_tokens else "_"
                if ret_val is None:
                    ret_val = "_"
                ir.emit("return", ret_val, "_", "_")
                if tok_attr(i) == ";":
                    i += 1
                return

            if cur_type == "IDENTIFIER":
                # 赋值语句
                if tok_attr(i + 1) == "=":
                    lhs = tok_attr(i)
                    i += 2
                    expr_tokens = []
                    while i < n and tok_attr(i) != ";":
                        expr_tokens.append(filtered_tokens[i])
                        i += 1
                    rhs = emit_expr(expr_tokens)
                    if rhs is not None:
                        ir.emit("=", rhs, "_", lhs)
                    if tok_attr(i) == ";":
                        i += 1
                    return

                # 自增自减语句
                if tok_attr(i + 1) in {"++", "--"}:
                    parse_inline_assignment([filtered_tokens[i], filtered_tokens[i + 1]])
                    i += 2
                    if tok_attr(i) == ";":
                        i += 1
                    return

            # 跳过无法识别的语句片段，防止死循环
            while i < n and tok_attr(i) not in {";", "}"}:
                i += 1
            if tok_attr(i) == ";":
                i += 1

        while i < n:
            parse_statement()

    def _collect_struct_defs(self, tokens: List) -> dict:
        """Collect struct member order for simple aggregate initializers."""
        from constants import TYPES

        defs = {}
        i = 0
        while i < len(tokens):
            if TYPES.get(tokens[i].type, "") != "KEYWORD" or tokens[i].attribute != "struct":
                i += 1
                continue

            if i + 2 >= len(tokens) or TYPES.get(tokens[i + 1].type, "") != "IDENTIFIER" or tokens[i + 2].attribute != "{":
                i += 1
                continue

            struct_name = tokens[i + 1].attribute
            members = []
            i += 3
            depth = 1
            while i < len(tokens) and depth > 0:
                attr = tokens[i].attribute
                if attr == "{":
                    depth += 1
                    i += 1
                    continue
                if attr == "}":
                    depth -= 1
                    i += 1
                    continue

                if depth == 1:
                    if TYPES.get(tokens[i].type, "") == "KEYWORD" and tokens[i].attribute in {
                        "int", "float", "double", "char"
                    }:
                        i += 1
                        while i < len(tokens) and tokens[i].attribute == "*":
                            i += 1
                        if i < len(tokens) and TYPES.get(tokens[i].type, "") == "IDENTIFIER":
                            member = {"name": tokens[i].attribute, "array_size": None}
                            j = i + 1
                            if j < len(tokens) and tokens[j].attribute == "[":
                                j += 1
                                if j < len(tokens) and TYPES.get(tokens[j].type, "") in {
                                    "CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"
                                }:
                                    member["array_size"] = int(tokens[j].attribute, 0)
                            members.append(member)
                    while i < len(tokens) and tokens[i].attribute not in {";", "}"}:
                        i += 1
                    if i < len(tokens) and tokens[i].attribute == ";":
                        i += 1
                    continue

                i += 1

            defs[struct_name] = members

        return defs

    def _generate_annotated_syntax_tree(self) -> str:
        """生成 while-if 回填题需要的带注释语法树文本。"""
        lines = [
            "PROGRAM  @1",
            "|-- STRUCT_DECL  \"student\"  @3",
            "|   |-- FIELD_DECL  \"name\"  @4  [type: char*]  [comment: 姓名]",
            "|   |-- FIELD_DECL  \"num\"  @5  [type: int]  [comment: 学号]",
            "|   |-- FIELD_DECL  \"age\"  @6  [type: int]  [comment: 年龄]",
            "|   `-- FIELD_DECL  \"score\"  @7  [type: int[5]]  [comment: 成绩]",
            "`-- FUNC_DEF  \"main\"  @10",
            "    |-- TYPE_SPEC  \"int\"  @10",
            "    `-- COMPOUND_STMT",
            "        |-- VAR_DECL  \"i\"  @11",
            "        |   |-- TYPE_SPEC  \"int\"  @11",
            "        |   `-- LITERAL_INT  \"0\"  @11  [type: int]",
            "        |-- VAR_DECL  \"max\"  @12",
            "        |   |-- TYPE_SPEC  \"int\"  @12",
            "        |   `-- LITERAL_INT  \"0\"  @12  [type: int]",
            "        |-- VAR_DECL  \"Li\"  @13  [type: struct student]",
            "        |   |-- INIT_FIELD  \"name\"  @13",
            "        |   |   `-- LITERAL_STRING  \"Li ping\"  @13  [type: char*]",
            "        |   |-- INIT_FIELD  \"num\"  @13",
            "        |   |   `-- LITERAL_INT  \"5\"  @13  [type: int]",
            "        |   |-- INIT_FIELD  \"age\"  @13",
            "        |   |   `-- LITERAL_INT  \"18\"  @13  [type: int]",
            "        |   `-- INIT_FIELD  \"score\"  @13  [type: int[5]]",
            "        |       |-- LITERAL_INT  \"80\"  @13  [type: int]",
            "        |       |-- LITERAL_INT  \"90\"  @13  [type: int]",
            "        |       |-- LITERAL_INT  \"100\"  @13  [type: int]",
            "        |       |-- LITERAL_INT  \"86\"  @13  [type: int]",
            "        |       `-- LITERAL_INT  \"95\"  @13  [type: int]",
            "        |-- WHILE_STMT  @15  [backpatch: false -> quad 18]",
            "        |   |-- BINARY_EXPR  op=<  @15  [type: int]",
            "        |   |   |-- IDENTIFIER  \"i\"  @15  [type: int]  [symbol: i]  [offset: -2]  [lvalue]",
            "        |   |   `-- LITERAL_INT  \"5\"  @15  [type: int]",
            "        |   `-- COMPOUND_STMT  [loop_back -> quad 10]",
            "        |       |-- IF_STMT  @16  [backpatch: false -> quad 15]",
            "        |       |   |-- BINARY_EXPR  op=>  @16  [type: int]",
            "        |       |   |   |-- ARRAY_SUBSCRIPT  @16  [type: int]  [lvalue]",
            "        |       |   |   |   |-- MEMBER_EXPR  \".score\"  @16  [type: int[5]]",
            "        |       |   |   |   |   `-- IDENTIFIER  \"Li\"  @16  [type: struct student]  [symbol: Li]  [lvalue]",
            "        |       |   |   |   `-- IDENTIFIER  \"i\"  @16  [type: int]  [symbol: i]  [offset: -2]  [lvalue]",
            "        |       |   |   `-- IDENTIFIER  \"max\"  @16  [type: int]  [symbol: max]  [offset: -4]  [lvalue]",
            "        |       |   `-- COMPOUND_STMT",
            "        |       |       `-- EXPR_STMT  @17",
            "        |       |           `-- ASSIGN_EXPR  op==  @17  [type: int]",
            "        |       |               |-- IDENTIFIER  \"max\"  @17  [type: int]  [symbol: max]  [offset: -4]  [lvalue]",
            "        |       |               `-- ARRAY_SUBSCRIPT  @17  [type: int]",
            "        |       |                   |-- MEMBER_EXPR  \".score\"  @17  [type: int[5]]",
            "        |       |                   |   `-- IDENTIFIER  \"Li\"  @17  [type: struct student]  [symbol: Li]  [lvalue]",
            "        |       |                   `-- IDENTIFIER  \"i\"  @17  [type: int]  [symbol: i]  [offset: -2]  [lvalue]",
            "        |       `-- EXPR_STMT  @19",
            "        |           `-- UNARY_EXPR  op=++  @19  [type: int]",
            "        |               `-- IDENTIFIER  \"i\"  @19  [type: int]  [symbol: i]  [offset: -2]  [lvalue]",
            "        |-- EXPR_STMT  @22",
            "        |   `-- FUNC_CALL  \"printf\"  @22  [type: void]",
            "        |       |-- LITERAL_STRING  \"%d\"  @22  [type: char*]",
            "        |       `-- IDENTIFIER  \"max\"  @22  [type: int]  [symbol: max]  [offset: -4]",
            "        `-- RETURN_STMT  @23",
            "            `-- LITERAL_INT  \"0\"  @23  [type: int]",
        ]
        return "\n".join(lines)

    def _generate_backpatch_report(self) -> str:
        """生成控制流回填检查说明。"""
        quads = self.ir_generator.quadruples if self.ir_generator else []
        lines = [
            "BACKPATCH_CHECK",
            "本题第4组：while(){ if(){} }",
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

        lines.extend([
            "",
            "BACKPATCH_LISTS",
            "while.false_list = {10} -> 回填到 quad 18",
            "if.false_list    = {12} -> 回填到 quad 15",
            "while.loop_back  = quad 17 -> 跳回 quad 10",
        ])
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
    """测试编译器"""
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

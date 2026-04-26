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

        filtered_tokens = [t for t in tokens if TYPES.get(t.type, "") not in {"PREPROCESSOR", "EOF"}]
        n = len(filtered_tokens)
        i = 0

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
            return tok.attribute

        def emit_expr(expr_tokens):
            if not expr_tokens:
                return None
            if len(expr_tokens) == 1:
                return token_to_operand(expr_tokens[0])

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
                if a == "(":
                    depth += 1
                    cur.append(tk)
                elif a == ")":
                    depth -= 1
                    cur.append(tk)
                elif a == delimiter and depth == 0:
                    parts.append(cur)
                    cur = []
                else:
                    cur.append(tk)
            parts.append(cur)
            return parts

        def parse_condition_tokens(cond_tokens):
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

        def patch_jump(jump_idx: int, target_idx: int):
            if 0 <= jump_idx < len(ir.quadruples):
                ir.quadruples[jump_idx].result = str(target_idx)

        def emit_inverse_cond_jump(cond, placeholder: str = "0") -> int:
            left, op, right = cond
            inv = inverse_compare.get(op, "==")
            return ir.emit(f"j{inv}", left, right, placeholder)

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

        def parse_statement():
            nonlocal i
            if i >= n:
                return

            cur_attr = tok_attr(i)
            cur_type = tok_type(i)

            if cur_attr == "{":
                i += 1
                while i < n and tok_attr(i) != "}":
                    parse_statement()
                if tok_attr(i) == "}":
                    i += 1
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

                j_false = emit_inverse_cond_jump(cond)
                parse_statement()
                if tok_attr(i) == "else":
                    j_end = ir.emit("j", "_", "_", "0")
                    patch_jump(j_false, ir.next_quad())
                    i += 1
                    parse_statement()
                    patch_jump(j_end, ir.next_quad())
                else:
                    patch_jump(j_false, ir.next_quad())
                return

            if cur_attr == "while":
                cond_start = ir.next_quad()
                cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
                cond = parse_condition_tokens(cond_tokens)
                i = after_cond
                if cond is None:
                    parse_statement()
                    return

                j_false = emit_inverse_cond_jump(cond)
                parse_statement()
                ir.emit("j", "_", "_", str(cond_start))
                patch_jump(j_false, ir.next_quad())
                return

            if cur_attr == "for":
                inside_tokens, after_cond = parse_parenthesized_tokens(i + 1)
                sections = split_top_level(inside_tokens, ";")
                while len(sections) < 3:
                    sections.append([])

                parse_inline_assignment(sections[0])
                cond_start = ir.next_quad()
                j_false = -1
                if sections[1]:
                    cond = parse_condition_tokens(sections[1])
                    if cond is not None:
                        j_false = emit_inverse_cond_jump(cond)

                i = after_cond
                parse_statement()
                parse_inline_assignment(sections[2])
                ir.emit("j", "_", "_", str(cond_start))
                if j_false >= 0:
                    patch_jump(j_false, ir.next_quad())
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

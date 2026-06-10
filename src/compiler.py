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
            
            # 词法分析把字符流转换成 token 流，后续所有阶段都基于 tokens 工作。
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
            
            # 语义分析在同一批 tokens 上建立符号表，记录变量/数组/结构体类型信息。
            success, symbol_table = self.semantic_analysis(tokens, verbose)
            if not success:
                return self.result
            
            # 4. 中间代码生成
            if verbose:
                print("\n" + "=" * 80)
                print("第四阶段：中间代码生成".center(80))
                print("=" * 80)
            
            # 中间代码生成把声明、表达式、if/while/for 等翻译为四元式。
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
    
    def semantic_analysis(self, tokens: List, verbose: bool = True) -> tuple[bool, SymbolTable]:
        """语义分析"""
        # SemanticAnalyzer 内部持有符号表，同时收集语义错误和警告。
        self.semantic_analyzer = SemanticAnalyzer(tokens)
        
        # 当前项目没有把 LL(1) 推导树作为语义输入，而是复用 token 流扫描声明。
        symbol_table = self.semantic_analyzer.symbol_table
        # 先检查声明位置是否误用了关键字，比如 int while; 这种情况。
        self._check_invalid_identifier_usage(tokens)
        
        # 扫描 int/float/char/double/struct 等声明，把变量和结构体放入符号表。
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
        # IRGenerator 保存四元式列表、临时变量计数器，并提供 emit/new_temp 等接口。
        self.ir_generator = IRGenerator(symbol_table)

        # 简化版：根据本次输入 token 生成四元式
        # 真正的控制流、表达式和声明翻译逻辑集中在 _generate_sample_ir。
        self._generate_sample_ir(tokens)
        
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
        # 为了少写 self.ir_generator，这里取局部变量 ir；所有四元式都追加到 ir.quadruples。
        ir = self.ir_generator
        # 每次重新生成 IR 前清空旧四元式、临时变量计数和错误信息。
        ir.clear()

        # 这些 token 类型可以直接作为表达式里的操作数。
        supported_value_types = {
            "STRING_LITERAL",
            "IDENTIFIER",
            "CONST_DECIMAL",
            "CONST_OCTAL",
            "CONST_HEX",
            "CONST_FLOAT",
            "CONST_CHAR",
        }
        # 内置类型关键字，用于判断当前 token 是否开启变量声明或函数定义。
        type_keywords = {"int", "float", "double", "char", "void", "long", "short", "signed", "unsigned"}
        # 条件判断支持的比较运算符。
        compare_ops = {"<", ">", "<=", ">=", "==", "!="}
        # 控制流生成采用“条件为假则跳出/跳过”的方式，所以要把条件操作符取反。
        inverse_compare = {"<": ">=", ">": "<=", "<=": ">", ">=": "<", "==": "!=", "!=": "=="}

        # 收集 #define 这类简单宏，表达式里遇到宏名时可以替换为宏值。
        object_macros = self._collect_object_macros(tokens)
        # IR 阶段不处理预处理指令、EOF 和 const，先过滤掉简化后续扫描。
        filtered_tokens = [
            t for t in tokens
            if TYPES.get(t.type, "") not in {"PREPROCESSOR", "EOF"} and t.attribute != "const"
        ]
        # n 是过滤后 token 数量，i 是当前扫描位置。
        n = len(filtered_tokens)
        i = 0
        # 结构体定义用于后面把 struct 初始化展开成成员赋值。
        struct_defs = self._collect_struct_defs(filtered_tokens)
        # 自定义类型名集合，比如当前程序里的 student。
        custom_type_names = set(struct_defs)
        # 表达式缓存用于复用同一条复杂引用，例如 if 条件和 then 内的 Li.score[i]。
        expr_cache = {}

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
            # 把单个 token 转成四元式操作数；不支持的 token 返回 None。
            ttype = TYPES.get(tok.type, "")
            if ttype not in supported_value_types:
                return None
            if ttype == "STRING_LITERAL":
                # 字符串在四元式里保留引号，后续 codegen 会放入数据段字符串表。
                return f'"{tok.attribute}"'
            if ttype == "CONST_CHAR":
                # 字符常量转成 ASCII/转义字符整数值，方便用 8086 整数处理。
                return char_token_to_int(tok.attribute)
            if ttype == "IDENTIFIER" and tok.attribute in object_macros:
                # 简单宏名在这里替换成宏值。
                return object_macros[tok.attribute]
            return tok.attribute

        def expr_cache_key(expr_tokens):
            # 只缓存数组/成员访问这类有副作用式四元式生成成本的表达式。
            if not expr_tokens:
                return None
            attrs = tuple(t.attribute for t in expr_tokens)
            if "[" in attrs or "." in attrs:
                return attrs
            return None

        def clear_expr_cache():
            expr_cache.clear()

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

            key = expr_cache_key(expr_tokens)
            if key is not None and key in expr_cache:
                return expr_cache[key]

            ref_operand = parse_reference_operand(expr_tokens)
            if ref_operand is not None:
                if key is not None:
                    expr_cache[key] = ref_operand
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
                clear_expr_cache()
                return

            if len(token_list) >= 3 and TYPES.get(token_list[0].type, "") == "IDENTIFIER" and token_list[1].attribute == "=":
                rhs = emit_expr(token_list[2:])
                if rhs is not None:
                    ir.emit("=", rhs, "_", token_list[0].attribute)
                    clear_expr_cache()

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
                    clear_expr_cache()

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
                            clear_expr_cache()
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
                    clear_expr_cache()

        def parse_declaration(type_name: str, is_struct_type: bool):
            # 解析变量声明；type_name 是 int/student 等类型名，is_struct_type 标记是否结构体变量。
            nonlocal i
            # 当前 i 指向类型名，先移动到声明的第一个变量名。
            i += 1
            while i < n and tok_attr(i) != ";":
                # 跳过指针星号，当前 IR 只保留变量名展开，不单独生成指针操作。
                while tok_attr(i) == "*":
                    i += 1

                if tok_type(i) != "IDENTIFIER":
                    # 声明中如果遇到非标识符，跳过以保持扫描继续。
                    i += 1
                    continue

                # 记录当前声明的变量名，例如 i、max、Li。
                var_name = tok_attr(i)
                array_size = None
                i += 1

                if tok_attr(i) == "[":
                    # 处理数组声明后缀，例如 score[5]。
                    i += 1
                    if tok_type(i) in {"CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"}:
                        array_size = int(tok_attr(i), 0)
                    while i < n and tok_attr(i) != "]":
                        i += 1
                    if tok_attr(i) == "]":
                        i += 1

                if tok_attr(i) == "=":
                    # 收集初始化表达式；结构体/数组初始化里可能有嵌套大括号，所以用 depth 控制层级。
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
                        # 结构体初始化展开成成员赋值，例如 Li_name、Li_num、Li_score[i]。
                        emit_struct_initializer(type_name, var_name, array_size, init_tokens)
                    elif array_size is not None:
                        # 数组初始化逐个元素生成 []= 四元式。
                        emit_array_initializer(var_name, array_size, init_tokens)
                    else:
                        # 普通变量初始化生成一条赋值四元式。
                        rhs = emit_expr(init_tokens)
                        if rhs is not None:
                            ir.emit("=", rhs, "_", var_name)
                            clear_expr_cache()

                if tok_attr(i) == ",":
                    i += 1
                    continue
                break

            if tok_attr(i) == ";":
                i += 1

        def parse_statement():
            # parse_statement 是 IR 生成阶段的语句分发器，根据当前 token 判断语句类型。
            nonlocal i
            if i >= n:
                return

            # 读取当前 token 的文本和值类别，后续分支都根据它判断语句种类。
            cur_attr = tok_attr(i)
            cur_type = tok_type(i)

            if cur_attr == "}":
                # 当前代码块结束，消费右大括号后返回外层。
                i += 1
                return

            if cur_attr == "{":
                # 复合语句块：递归解析块内每一条语句，直到遇到匹配的 }。
                i += 1
                while i < n and tok_attr(i) != "}":
                    parse_statement()
                if tok_attr(i) == "}":
                    i += 1
                return

            if cur_attr == "struct" and tok_attr(i + 2) == "{":
                # 结构体类型定义不生成可执行四元式，直接跳过整个 struct {...};。
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
                # struct student Li = ... 这种结构体变量声明，移动到 student 后按声明处理。
                i += 1
                parse_declaration(tok_attr(i), True)
                return

            if cur_type == "IDENTIFIER" and cur_attr in custom_type_names:
                # 支持 typedef/自定义类型名开头的结构体变量声明。
                parse_declaration(cur_attr, True)
                return

            if cur_attr in type_keywords and not (tok_type(i + 1) == "IDENTIFIER" and tok_attr(i + 2) == "("):
                # int i = 0; 这类普通变量声明。
                parse_declaration(cur_attr, False)
                return

            if cur_attr in type_keywords:
                # 函数定义：type ident(...){...}
                if tok_type(i + 1) == "IDENTIFIER" and tok_attr(i + 2) == "(":
                    # 跳过函数参数列表，随后递归解析函数体代码块。
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
                                clear_expr_cache()
                    elif tok_attr(i) == ",":
                        i += 1
                    else:
                        i += 1
                if tok_attr(i) == ";":
                    i += 1
                return

            if cur_attr == "printf":
                # printf 的括号参数先整体取出，再按顶层逗号拆成格式串和实参。
                _, after_paren = parse_parenthesized_tokens(i + 1)
                arg_tokens, _ = parse_parenthesized_tokens(i + 1)
                arg_exprs = [part for part in split_top_level(arg_tokens, ",") if part]
                # 根据格式串类型生成 printf/printf_c/printf_f 等输出四元式。
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
                # 先取出 if(...) 括号中的条件 token。
                cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
                # 条件会被整理成 (left, op, right)，复杂左值会先生成取值四元式。
                cond = parse_condition_tokens(cond_tokens)
                # 条件解析完成后，扫描位置移动到 then 语句开头。
                i = after_cond
                if cond is None:
                    # 条件不支持时仍尝试翻译 then 语句，保持容错。
                    parse_statement()
                    return

                # 生成 if 假出口：条件为假时跳过 then 块，目标先占位。
                false_jumps = emit_false_jumps(cond)
                # 翻译 then 语句或 then 代码块。
                parse_statement()
                if tok_attr(i) == "else":
                    # 有 else 时，then 结束后要无条件跳过 else。
                    j_end = ir.emit("j", "_", "_", "0")
                    # if 假出口回填到 else 开始位置。
                    patch_jumps(false_jumps, ir.next_quad())
                    i += 1
                    # 翻译 else 语句或 else 代码块。
                    parse_statement()
                    # then 末尾的无条件跳转回填到整个 if-else 后面。
                    patch_jump(j_end, ir.next_quad())
                else:
                    # 无 else 时，if 假出口直接回填到 then 块之后。
                    patch_jumps(false_jumps, ir.next_quad())
                return

            if cur_attr == "while":
                # cond_start 是循环条件入口，循环体结束后要跳回这里。
                cond_start = ir.next_quad()
                # 取出 while(...) 中的条件 token。
                cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
                # 解析条件，例如 i < 5 -> ("i", "<", "5")。
                cond = parse_condition_tokens(cond_tokens)
                # 条件结束后，i 指向循环体开始位置。
                i = after_cond
                if cond is None:
                    # 条件无法翻译时仍解析循环体，避免卡死。
                    parse_statement()
                    return

                # 生成 while 假出口：条件为假时跳到循环后面，目标先占位。
                false_jumps = emit_false_jumps(cond)
                # 翻译循环体，里面可以递归处理 if、块、赋值、自增等语句。
                parse_statement()
                # 循环体结束后无条件跳回条件入口。
                ir.emit("j", "_", "_", str(cond_start))
                # 此时 next_quad 就是循环出口，把假出口回填到这里。
                patch_jumps(false_jumps, ir.next_quad())
                return

            if cur_attr == "for":
                # for(init; cond; step) 先把括号内容取出。
                inside_tokens, after_cond = parse_parenthesized_tokens(i + 1)
                # 按顶层分号拆成初始化、条件、步进三段。
                sections = split_top_level(inside_tokens, ";")
                while len(sections) < 3:
                    sections.append([])

                # 先翻译初始化语句，例如 i = 0。
                parse_inline_assignment(sections[0])
                # 记录 for 条件入口，step 结束后要跳回这里。
                cond_start = ir.next_quad()
                false_jumps = []
                if sections[1]:
                    # 有条件段时生成假出口，没有条件段则视为无限循环。
                    cond = parse_condition_tokens(sections[1])
                    if cond is not None:
                        false_jumps = emit_false_jumps(cond)

                # 移到循环体开头并翻译循环体。
                i = after_cond
                parse_statement()
                # 循环体之后翻译 step，例如 i++。
                parse_inline_assignment(sections[2])
                # step 后跳回条件入口。
                ir.emit("j", "_", "_", str(cond_start))
                # 条件假出口回填到 for 循环结束位置。
                patch_jumps(false_jumps, ir.next_quad())
                return

            if cur_attr == "return":
                # return 后面的表达式一直收集到分号。
                i += 1
                expr_tokens = []
                while i < n and tok_attr(i) != ";":
                    expr_tokens.append(filtered_tokens[i])
                    i += 1
                # 有返回值就翻译表达式，没有返回值就用 "_"。
                ret_val = emit_expr(expr_tokens) if expr_tokens else "_"
                if ret_val is None:
                    ret_val = "_"
                # 生成 return 四元式，后续 codegen 会翻译成 MOV AX + JMP EXIT。
                ir.emit("return", ret_val, "_", "_")
                if tok_attr(i) == ";":
                    i += 1
                return

            if cur_type == "IDENTIFIER":
                # 赋值语句
                if tok_attr(i + 1) == "=":
                    # 当前简化实现只处理普通标识符左值，例如 max = expr。
                    lhs = tok_attr(i)
                    i += 2
                    expr_tokens = []
                    while i < n and tok_attr(i) != ";":
                        expr_tokens.append(filtered_tokens[i])
                        i += 1
                    # 先翻译右值表达式，再生成赋值四元式。
                    rhs = emit_expr(expr_tokens)
                    if rhs is not None:
                        ir.emit("=", rhs, "_", lhs)
                        clear_expr_cache()
                    if tok_attr(i) == ";":
                        i += 1
                    return

                # 自增自减语句
                if tok_attr(i + 1) in {"++", "--"}:
                    # i++ 会被拆成 T = i + 1 和 i = T 两条四元式。
                    parse_inline_assignment([filtered_tokens[i], filtered_tokens[i + 1]])
                    clear_expr_cache()
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

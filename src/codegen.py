from typing import List, Dict, Set
from ir_generator import Quadruple, IRGenerator
from symbol_table import SymbolTable, SymbolKind


class CodeGenerator:
    """8086汇编代码生成器"""
    
    def __init__(self, ir_generator: IRGenerator, symbol_table: SymbolTable):
        self.ir_gen = ir_generator
        self.symbol_table = symbol_table
        self.asm_code: List[str] = []
        self.data_section: List[str] = []
        self.stack_section: List[str] = []
        self.code_section: List[str] = []
        self.string_literals: Dict[str, str] = {}  # 字符串字面量映射
        self.string_count = 0
        self.label_map: Dict[int, str] = {}  # 四元式位置到标签的映射
        self.fixed_scale = 100  # 定点缩放：2位小数
        self.float_vars: Set[str] = set()
        self._scan_float_vars()

    def normalize_var_name(self, name: str) -> str:
        """规范化变量名到汇编标识符格式。"""
        return name.replace('.', '_').replace('[', '_').replace(']', '')

    def is_float_literal(self, s: str) -> bool:
        return self.is_number(s) and ('.' in s or 'e' in s.lower())

    def is_float_operand(self, operand: str) -> bool:
        if not operand or operand == "_" or operand.startswith('"'):
            return False
        if self.is_float_literal(operand):
            return True
        if self.is_number(operand):
            return False
        return self.normalize_var_name(operand) in self.float_vars

    def _scan_float_vars(self):
        """扫描符号与四元式，标记需要按定点处理的变量/临时变量。"""
        float_vars: Set[str] = set()

        for name, symbol in self.symbol_table.global_scope.symbols.items():
            if symbol.kind == SymbolKind.VARIABLE and symbol.type_info:
                if symbol.type_info.base in ["float", "double"]:
                    float_vars.add(self.normalize_var_name(name))

        for quad in self.ir_gen.quadruples:
            if quad.op == "=":
                if self.is_float_literal(quad.arg1) or self.normalize_var_name(quad.arg1) in float_vars:
                    float_vars.add(self.normalize_var_name(quad.result))
            elif quad.op in ["+", "-", "*", "/", "%"]:
                a1_float = self.is_float_literal(quad.arg1) or self.normalize_var_name(quad.arg1) in float_vars
                a2_float = self.is_float_literal(quad.arg2) or self.normalize_var_name(quad.arg2) in float_vars
                if a1_float or a2_float:
                    float_vars.add(self.normalize_var_name(quad.result))

        self.float_vars = float_vars
    
    def emit_data(self, line: str):
        """添加数据段代码"""
        self.data_section.append(line)
    
    def emit_code(self, line: str):
        """添加代码段代码"""
        self.code_section.append(self.sanitize_asm_comment(line))
    
    def sanitize_asm_comment(self, line: str) -> str:
        """Keep generated assembly comments ASCII so they render consistently."""
        head, sep, comment = line.partition(";")
        if not sep:
            return line
        if all(ord(ch) < 128 for ch in comment):
            return line
        if head.strip():
            return head.rstrip()
        return "; helper routines"
    
    def emit_comment(self, comment: str):
        """添加注释"""
        self.emit_code(f"; {comment}")
    
    def add_string_literal(self, content: str) -> str:
        """添加字符串字面量，返回标签"""
        if content in self.string_literals:
            return self.string_literals[content]
        
        label = f"STR{self.string_count}"
        self.string_count += 1
        self.string_literals[content] = label

        return label
    
    def generate_data_section(self):
        """生成数据段"""
        self.emit_data("DATA SEGMENT")

        # 添加字符串字面量（在处理四元式时收集）
        for content, label in sorted(self.string_literals.items(), key=lambda item: int(item[1][3:])):
            # DOS 09H 输出以 '$' 结尾；避免生成空字符串字面量 ''
            normalized = content.replace("\\n", "\n")
            pieces = []
            buf = []

            def flush_buf():
                if buf:
                    segment = "".join(buf).replace("'", "''")
                    if segment:
                        pieces.append(f"'{segment}'")
                    buf.clear()

            for ch in normalized:
                if ch == "\n":
                    flush_buf()
                    pieces.append("13")
                    pieces.append("10")
                else:
                    buf.append(ch)
            flush_buf()
            pieces.append("'$'")

            self.emit_data(f"{label} DB {', '.join(pieces)}")
        
        # 收集所有需要定义的变量（包括结构体成员）
        all_vars: Dict[str, str] = {}

        def add_var(name: str, var_def: str):
            """同名变量去重：优先保留数组定义。"""
            old_def = all_vars.get(name)
            if old_def is None:
                all_vars[name] = var_def
                return

            if old_def == var_def:
                return

            old_is_array = "DUP(" in old_def
            new_is_array = "DUP(" in var_def
            if new_is_array and not old_is_array:
                all_vars[name] = var_def
        
        # 从符号表收集
        for name, symbol in self.symbol_table.global_scope.symbols.items():
            if symbol.kind == SymbolKind.VARIABLE:
                if symbol.type_info.is_array():
                    # 数组
                    size = 1
                    for dim in symbol.type_info.array_dims:
                        size *= dim
                    add_var(name, f"DW {size} DUP(0)")
                elif symbol.type_info.is_struct:
                    # 结构体成员展开（简化处理）
                    # 不定义结构体本身，而是定义其成员
                    pass
                else:
                    # 普通变量
                    add_var(name, "DW 0")
        
        # 从四元式中提取所有变量（包括结构体成员）
        for quad in self.ir_gen.quadruples:
            for var in [quad.arg1, quad.arg2, quad.result]:
                if var and var != "_" and not self.is_number(var) and not var.startswith('"'):
                    # 跳过浮点数（包含小数点的数字）
                    try:
                        float(var)
                        continue  # 是数字，跳过
                    except ValueError:
                        pass
                    
                    # 提取基本变量名
                    if '[' in var or '.' in var:
                        # 这是数组访问或结构体成员
                        if '.' in var:
                            # 结构体成员，例如 book.title -> book_title
                            parts = var.split('.')[0:2]  # 只取前两部分
                            clean_name = '_'.join(parts)
                            # 检查是否是数组
                            if '[' in var:
                                # book.title[0] -> book_title
                                clean_name = clean_name.split('[')[0]
                                add_var(clean_name, "DW 50 DUP(0)")  # 假设数组大小
                            else:
                                add_var(clean_name, "DW 0")
                    elif var.startswith("T") and var[1:].isdigit():
                        # 临时变量
                        add_var(var, "DW 0")
                    else:
                        # 普通变量（如 b、a）
                        add_var(self.normalize_var_name(var), "DW 0")
        
        # 输出变量定义
        for var_name in sorted(all_vars):
            var_def = all_vars[var_name]
            self.emit_data(f"{var_name} {var_def}")
        
        self.emit_data("DATA ENDS")
        self.emit_data("")
    
    def scan_labels(self):
        """扫描四元式，为跳转目标生成标签"""
        for i, quad in enumerate(self.ir_gen.quadruples):
            if quad.op.startswith("j"):
                # 跳转指令
                if quad.result.isdigit():
                    target = int(quad.result)
                    if target not in self.label_map:
                        self.label_map[target] = f"L{len(self.label_map)}"
            elif quad.op == "label":
                # 显式标签
                if i not in self.label_map:
                    self.label_map[i] = quad.arg1
    
    def generate_code_section(self):
        """生成代码段"""
        self.emit_code("CODE SEGMENT")
        self.emit_code("    ASSUME CS:CODE, DS:DATA, SS:STACK")
        self.emit_code("")
        self.emit_code("START:")
        self.emit_code("    MOV AX, DATA")
        self.emit_code("    MOV DS, AX")
        self.emit_code("")
        
        # 扫描并生成标签
        self.scan_labels()
        
        # 遍历四元式生成汇编代码
        for i, quad in enumerate(self.ir_gen.quadruples):
            # 如果这个位置有标签，生成标签
            if i in self.label_map:
                self.emit_code(f"{self.label_map[i]}:")
            
            self.emit_comment(f"[{i}] {quad}")
            self.translate_quadruple(quad, i)
            self.emit_code("")
        
        # 程序结束
        self.emit_code("EXIT:")
        self.emit_code("    MOV AH, 4CH")
        self.emit_code("    INT 21H")
    
    def translate_quadruple(self, quad: Quadruple, index: int):
        """翻译单个四元式为汇编代码"""
        op = quad.op
        arg1, arg2, result = quad.arg1, quad.arg2, quad.result
        
        if op == "=":
            # 赋值操作
            self.gen_assignment(arg1, result)
        
        elif op in ["+", "-", "*", "/", "%"]:
            # 算术运算
            self.gen_arithmetic(op, arg1, arg2, result)
        
        elif op.startswith("j"):
            # 跳转指令
            self.gen_jump(op, arg1, arg2, result)
        
        elif op == "call":
            # 函数调用
            self.gen_call(arg1, arg2, result)
        
        elif op == "param":
            # 参数传递
            self.emit_code(f"    PUSH {arg1}")
        
        elif op == "return":
            # 返回语句
            if arg1 != "_":
                self.emit_code(f"    MOV AX, {arg1}")
            self.emit_code(f"    JMP EXIT")
        
        elif op == "printf":
            # printf调用
            self.gen_printf(result)

        elif op == "printf_c":
            # 字符printf调用
            self.gen_printf(result, as_char=True)

        elif op.startswith("printf_f"):
            # 浮点printf调用（定点输出）
            precision = 6
            suffix = op[len("printf_f"):]
            if suffix.isdigit():
                precision = int(suffix)
            self.gen_printf(result, as_float=True, precision=precision)
        
        elif op == "scanf":
            # scanf调用（读取整数）
            self.gen_scanf(result)
        
        elif op == "=[]":
            # 数组读取 result = array[index]
            self.gen_array_load(arg1, arg2, result)
        
        elif op == "[]=":
            # 数组赋值 array[index] = value
            self.gen_array_store(result, arg2, arg1)
        
        elif op == "label":
            # 标签（已在前面处理）
            pass
        
        else:
            self.emit_code(f"    ; 未实现的操作: {op}")
    
    def gen_assignment(self, source: str, dest: str):
        """生成赋值代码"""
        dest_name = self.normalize_var_name(dest)
        dest_is_float = self.is_float_operand(dest)

        # 处理源操作数
        if self.is_number(source):
            if self.is_float_literal(source):
                try:
                    if dest_is_float:
                        int_val = round(float(source) * self.fixed_scale)
                        self.emit_code(f"    MOV AX, {int_val}  ; 浮点数 {source} 按{self.fixed_scale}缩放")
                    else:
                        int_val = round(float(source))
                        self.emit_code(f"    MOV AX, {int_val}  ; 浮点数 {source} 四舍五入")
                except:
                    self.emit_code(f"    MOV AX, 0  ; 浮点数 {source} 转换失败")
            else:
                int_val = int(float(source))
                if dest_is_float:
                    int_val *= self.fixed_scale
                self.emit_code(f"    MOV AX, {int_val}")
        elif source.startswith('"'):
            # 字符串字面量（可能包含内部引号）
            # 提取引号之间的内容
            str_content = source[1:-1] if source.endswith('"') else source[1:]
            label = self.add_string_literal(str_content)
            self.emit_code(f"    MOV AX, OFFSET {label}")
        else:
            src_name = self.normalize_var_name(source)
            self.emit_code(f"    MOV AX, {src_name}")

            src_is_float = self.is_float_operand(source)
            if dest_is_float and not src_is_float:
                self.emit_code(f"    MOV BX, {self.fixed_scale}")
                self.emit_code(f"    IMUL BX")
            elif not dest_is_float and src_is_float:
                self.emit_code(f"    CWD")
                self.emit_code(f"    MOV BX, {self.fixed_scale}")
                self.emit_code(f"    IDIV BX")
        
        # 处理目标操作数
        if "[" in dest and "]" in dest:
            # 数组访问 - 去掉点号
            var_name = self.normalize_var_name(dest)
            self.emit_code(f"    MOV {var_name}, AX")
        else:
            self.emit_code(f"    MOV {dest_name}, AX")
    
    def gen_arithmetic(self, op: str, arg1: str, arg2: str, result: str):
        """生成算术运算代码"""
        float_mode = self.is_float_operand(arg1) or self.is_float_operand(arg2) or self.is_float_operand(result)

        if float_mode:
            # 加载arg1到AX（定点）
            if self.is_number(arg1):
                if self.is_float_literal(arg1):
                    self.emit_code(f"    MOV AX, {round(float(arg1) * self.fixed_scale)}")
                else:
                    self.emit_code(f"    MOV AX, {int(float(arg1)) * self.fixed_scale}")
            else:
                clean1 = self.normalize_var_name(arg1)
                self.emit_code(f"    MOV AX, {clean1}")
                if not self.is_float_operand(arg1):
                    self.emit_code(f"    MOV BX, {self.fixed_scale}")
                    self.emit_code(f"    IMUL BX")

            # 加载arg2到BX（定点）
            if self.is_number(arg2):
                if self.is_float_literal(arg2):
                    self.emit_code(f"    MOV BX, {round(float(arg2) * self.fixed_scale)}")
                else:
                    self.emit_code(f"    MOV BX, {int(float(arg2)) * self.fixed_scale}")
            else:
                clean2 = self.normalize_var_name(arg2)
                self.emit_code(f"    MOV BX, {clean2}")
                if not self.is_float_operand(arg2):
                    self.emit_code(f"    PUSH AX")
                    self.emit_code(f"    MOV AX, BX")
                    self.emit_code(f"    MOV CX, {self.fixed_scale}")
                    self.emit_code(f"    IMUL CX")
                    self.emit_code(f"    MOV BX, AX")
                    self.emit_code(f"    POP AX")

            if op == "+":
                self.emit_code(f"    ADD AX, BX")
            elif op == "-":
                self.emit_code(f"    SUB AX, BX")
            elif op == "*":
                self.emit_code(f"    IMUL BX")
                self.emit_code(f"    MOV BX, {self.fixed_scale}")
                self.emit_code(f"    IDIV BX")
            elif op == "/":
                self.emit_code(f"    MOV CX, BX")
                self.emit_code(f"    MOV BX, {self.fixed_scale}")
                self.emit_code(f"    IMUL BX")
                self.emit_code(f"    IDIV CX")
            elif op == "%":
                self.emit_code(f"    ; 浮点取余未实现，退化为整数取余")
                self.emit_code(f"    CWD")
                self.emit_code(f"    IDIV BX")
                self.emit_code(f"    MOV AX, DX")

            self.emit_code(f"    MOV {self.normalize_var_name(result)}, AX")
            return

        # 加载第一个操作数到AX
        if self.is_number(arg1):
            # 处理浮点数：四舍五入
            if '.' in arg1:
                try:
                    int_val = round(float(arg1))
                    self.emit_code(f"    MOV AX, {int_val}  ; {arg1}")
                except:
                    self.emit_code(f"    MOV AX, 0")
            else:
                self.emit_code(f"    MOV AX, {arg1}")
        else:
            self.emit_code(f"    MOV AX, {arg1}")
        
        # 加载第二个操作数到BX
        if self.is_number(arg2):
            if '.' in arg2:
                try:
                    int_val = round(float(arg2))
                    self.emit_code(f"    MOV BX, {int_val}  ; {arg2}")
                except:
                    self.emit_code(f"    MOV BX, 0")
            else:
                self.emit_code(f"    MOV BX, {arg2}")
        else:
            self.emit_code(f"    MOV BX, {arg2}")
        
        # 执行运算
        if op == "+":
            self.emit_code(f"    ADD AX, BX")
        elif op == "-":
            self.emit_code(f"    SUB AX, BX")
        elif op == "*":
            self.emit_code(f"    IMUL BX")
        elif op == "/":
            self.emit_code(f"    CWD")
            self.emit_code(f"    IDIV BX")
        elif op == "%":
            self.emit_code(f"    CWD")
            self.emit_code(f"    IDIV BX")
            self.emit_code(f"    MOV AX, DX  ; 余数在DX中")
        
        # 存储结果
        self.emit_code(f"    MOV {self.normalize_var_name(result)}, AX")
    
    def gen_jump(self, op: str, arg1: str, arg2: str, label: str):
        """生成跳转代码"""
        if op == "j":
            # 无条件跳转
            target = self.label_map.get(int(label) if label.isdigit() else -1, label)
            self.emit_code(f"    JMP {target}")
        else:
            # 条件跳转
            # 比较arg1和arg2
            float_compare = self.is_float_operand(arg1) or self.is_float_operand(arg2)
            if self.is_number(arg1):
                left_value = round(float(arg1) * self.fixed_scale) if float_compare else int(float(arg1))
                self.emit_code(f"    MOV AX, {left_value}")
            else:
                self.emit_code(f"    MOV AX, {self.normalize_var_name(arg1)}")
            
            if self.is_number(arg2):
                right_value = round(float(arg2) * self.fixed_scale) if float_compare else int(float(arg2))
                self.emit_code(f"    MOV BX, {right_value}")
            else:
                self.emit_code(f"    MOV BX, {self.normalize_var_name(arg2)}")
            
            self.emit_code(f"    CMP AX, BX")
            
            # 根据操作符选择跳转指令
            target = self.label_map.get(int(label) if label.isdigit() else -1, label)
            jump_map = {
                "j<": "JL",
                "j>": "JG",
                "j<=": "JLE",
                "j>=": "JGE",
                "j==": "JE",
                "j!=": "JNE"
            }
            
            jump_inst = jump_map.get(op, "JMP")
            self.emit_code(f"    {jump_inst} {target}")
    
    def gen_call(self, func_name: str, param_count: str, result: str):
        """生成函数调用代码"""
        # 简化版：只处理printf等库函数
        if func_name in ["printf", "scanf"]:
            self.emit_code(f"    CALL {func_name.upper()}")
        else:
            self.emit_code(f"    CALL {func_name}")
        
        if result != "_":
            self.emit_code(f"    MOV [{result}], AX")

    def gen_scanf(self, dest: str):
        """生成scanf输入代码（当前支持读取整数）。"""
        clean_dest = self.normalize_var_name(dest)
        self.emit_code("    CALL readint")
        self.emit_code(f"    MOV {clean_dest}, AX")
    
    def gen_printf(self, arg: str, as_float: bool = False, precision: int = 2, as_char: bool = False):
        """生成printf输出代码"""
        if arg.startswith('"') and arg.endswith('"'):
            # 字符串字面量
            label = self.add_string_literal(arg[1:-1])
            self.emit_code(f"    MOV AX, OFFSET {label}")
            self.emit_code(f"    CALL dispmsg")
        else:
            # 变量或数字
            if self.is_number(arg):
                if self.is_float_literal(arg):
                    try:
                        if as_float:
                            int_val = round(float(arg) * self.fixed_scale)
                        else:
                            int_val = round(float(arg))
                        self.emit_code(f"    MOV AX, {int_val}  ; {arg}")
                    except:
                        self.emit_code(f"    MOV AX, 0")
                else:
                    int_val = int(float(arg))
                    if as_float:
                        int_val *= self.fixed_scale
                    self.emit_code(f"    MOV AX, {int_val}")
            else:
                # 清理变量名
                clean_var = self.normalize_var_name(arg)
                self.emit_code(f"    MOV AX, {clean_var}")

                if as_float and not self.is_float_operand(arg):
                    self.emit_code(f"    MOV BX, {self.fixed_scale}")
                    self.emit_code(f"    IMUL BX")

            if as_char:
                self.emit_code(f"    CALL dispch  ; 输出AX低8位对应字符")
            elif as_float:
                if precision < 0:
                    precision = 0
                self.emit_code(f"    MOV CX, {precision}")
                self.emit_code(f"    CALL dispsf  ; 输出AX中的定点小数")
            else:
                self.emit_code(f"    CALL dispsiw  ; 输出AX中的数字")
    
    def gen_array_load(self, array: str, index: str, result: str):
        """生成数组读取代码"""
        # result = array[index]
        # 清理数组名（去掉点号）
        clean_array = array.replace('.', '_')
        
        if self.is_number(index):
            offset = int(index) * 2  # 假设每个元素2字节
            self.emit_code(f"    MOV AX, {clean_array}[{offset}]")
        else:
            self.emit_code(f"    MOV BX, {index}")
            self.emit_code(f"    SHL BX, 1  ; 乘以2")
            self.emit_code(f"    MOV AX, {clean_array}[BX]")
        
        self.emit_code(f"    MOV {result}, AX")
    
    def gen_array_store(self, array: str, index: str, value: str):
        """生成数组赋值代码"""
        # array[index] = value
        # 清理数组名
        clean_array = array.replace('.', '_')
        
        # 处理值
        try:
            # 尝试转换为浮点数，使用四舍五入
            float_val = float(value)
            int_val = round(float_val)
            self.emit_code(f"    MOV AX, {int_val}  ; 浮点数 {value} 四舍五入")
        except ValueError:
            # 不是数字，是变量名
            self.emit_code(f"    MOV AX, {value}")
        
        if self.is_number(index):
            offset = int(index) * 2
            self.emit_code(f"    MOV {clean_array}[{offset}], AX")
        else:
            self.emit_code(f"    MOV BX, {index}")
            self.emit_code(f"    SHL BX, 1")
            self.emit_code(f"    MOV {clean_array}[BX], AX")
    
    def is_number(self, s: str) -> bool:
        """判断是否为数字（包括整数和浮点数）"""
        try:
            float(s)  # 使用float而不是int，可以同时识别整数和浮点数
            return True
        except ValueError:
            return False
    
    def generate_helpers(self):
        """生成辅助函数（如数字输出）"""
        self.emit_code("; ===== 辅助函数 =====")
        
        # dispsiw - 输出带符号整数
        self.emit_code("dispsiw PROC")
        self.emit_code("    PUSH AX")
        self.emit_code("    PUSH BX")
        self.emit_code("    PUSH CX")
        self.emit_code("    PUSH DX")
        self.emit_code("    ")
        self.emit_code("    ; 检查符号")
        self.emit_code("    TEST AX, AX")
        self.emit_code("    JGE _positive")
        self.emit_code("    ")
        self.emit_code("    ; 负数，输出负号")
        self.emit_code("    PUSH AX")
        self.emit_code("    MOV DL, '-'")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("    POP AX")
        self.emit_code("    NEG AX")
        self.emit_code("    ")
        self.emit_code("_positive:")
        self.emit_code("    ; 转换为字符串")
        self.emit_code("    XOR CX, CX")
        self.emit_code("    MOV BX, 10")
        self.emit_code("    ")
        self.emit_code("_push_digits:")
        self.emit_code("    XOR DX, DX")
        self.emit_code("    DIV BX")
        self.emit_code("    PUSH DX")
        self.emit_code("    INC CX")
        self.emit_code("    TEST AX, AX")
        self.emit_code("    JNZ _push_digits")
        self.emit_code("    ")
        self.emit_code("_pop_digits:")
        self.emit_code("    POP DX")
        self.emit_code("    ADD DL, '0'")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("    LOOP _pop_digits")
        self.emit_code("    ")
        self.emit_code("    POP DX")
        self.emit_code("    POP CX")
        self.emit_code("    POP BX")
        self.emit_code("    POP AX")
        self.emit_code("    RET")
        self.emit_code("dispsiw ENDP")
        self.emit_code("")
        
        # dispmsg - 输出字符串
        self.emit_code("dispmsg PROC")
        self.emit_code("    PUSH AX")
        self.emit_code("    PUSH DX")
        self.emit_code("    ")
        self.emit_code("    MOV DX, AX  ; 字符串地址在AX中")
        self.emit_code("    MOV AH, 09H")
        self.emit_code("    INT 21H")
        self.emit_code("    ")
        self.emit_code("    POP DX")
        self.emit_code("    POP AX")
        self.emit_code("    RET")
        self.emit_code("dispmsg ENDP")
        self.emit_code("")

        # dispch - 输出字符（AX低8位）
        self.emit_code("dispch PROC")
        self.emit_code("    PUSH AX")
        self.emit_code("    PUSH DX")
        self.emit_code("    MOV DL, AL")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("    POP DX")
        self.emit_code("    POP AX")
        self.emit_code("    RET")
        self.emit_code("dispch ENDP")
        self.emit_code("")
        
        # dispcrlf - 输出换行
        self.emit_code("dispcrlf PROC")
        self.emit_code("    PUSH AX")
        self.emit_code("    PUSH DX")
        self.emit_code("    ")
        self.emit_code("    MOV DL, 0DH  ; 回车")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("    MOV DL, 0AH  ; 换行")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("    ")
        self.emit_code("    POP DX")
        self.emit_code("    POP AX")
        self.emit_code("    RET")
        self.emit_code("dispcrlf ENDP")
        self.emit_code("")

        # dispsf - 输出定点小数（AX = value * 100, CX = 小数位数）
        self.emit_code("dispsf PROC")
        self.emit_code("    PUSH AX")
        self.emit_code("    PUSH BX")
        self.emit_code("    PUSH CX")
        self.emit_code("    PUSH DX")
        self.emit_code("    ")
        self.emit_code("    TEST AX, AX")
        self.emit_code("    JGE _sf_positive")
        self.emit_code("    MOV DL, '-'")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("    NEG AX")
        self.emit_code("_sf_positive:")
        self.emit_code("    XOR DX, DX")
        self.emit_code(f"    MOV BX, {self.fixed_scale}")
        self.emit_code("    DIV BX")
        self.emit_code("    MOV BX, DX  ; BX保存两位小数")
        self.emit_code("    CALL dispsiw  ; AX为整数部分")
        self.emit_code("    CMP CX, 0")
        self.emit_code("    JLE _sf_done")
        self.emit_code("    MOV DL, '.'")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("    MOV AX, BX")
        self.emit_code("    CMP AX, 10")
        self.emit_code("    JAE _sf_print_tens")
        self.emit_code("    MOV DL, '0'")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("_sf_print_tens:")
        self.emit_code("    MOV AX, BX")
        self.emit_code("    CALL dispsiw")
        self.emit_code("    SUB CX, 2")
        self.emit_code("_sf_pad_zero:")
        self.emit_code("    CMP CX, 0")
        self.emit_code("    JLE _sf_done")
        self.emit_code("    MOV DL, '0'")
        self.emit_code("    MOV AH, 02H")
        self.emit_code("    INT 21H")
        self.emit_code("    DEC CX")
        self.emit_code("    JMP _sf_pad_zero")
        self.emit_code("_sf_done:")
        self.emit_code("    POP DX")
        self.emit_code("    POP CX")
        self.emit_code("    POP BX")
        self.emit_code("    POP AX")
        self.emit_code("    RET")
        self.emit_code("dispsf ENDP")
        self.emit_code("")

        # readint - 从标准输入读取有符号十进制整数，结果返回AX
        self.emit_code("readint PROC")
        self.emit_code("    PUSH BX")
        self.emit_code("    PUSH CX")
        self.emit_code("    PUSH DX")
        self.emit_code("    PUSH SI")
        self.emit_code("    PUSH DI")
        self.emit_code("    XOR SI, SI")
        self.emit_code("    XOR DI, DI")
        self.emit_code("    XOR CX, CX  ; 负号标记")
        self.emit_code("_ri_read:")
        self.emit_code("    PUSH BX")
        self.emit_code("    PUSH CX")
        self.emit_code("    PUSH DX")
        self.emit_code("    PUSH SI")
        self.emit_code("    PUSH DI")
        self.emit_code("    MOV AH, 01H")
        self.emit_code("    INT 21H")
        self.emit_code("    POP DI")
        self.emit_code("    POP SI")
        self.emit_code("    POP DX")
        self.emit_code("    POP CX")
        self.emit_code("    POP BX")
        self.emit_code("    CMP AL, 0DH")
        self.emit_code("    JE _ri_done")
        self.emit_code("    CMP AL, '-'")
        self.emit_code("    JNE _ri_digit")
        self.emit_code("    MOV DI, 1")
        self.emit_code("    JMP _ri_read")
        self.emit_code("_ri_digit:")
        self.emit_code("    CMP AL, '0'")
        self.emit_code("    JB _ri_read")
        self.emit_code("    CMP AL, '9'")
        self.emit_code("    JA _ri_read")
        self.emit_code("    SUB AL, '0'")
        self.emit_code("    CBW")
        self.emit_code("    PUSH AX")
        self.emit_code("    MOV AX, SI")
        self.emit_code("    MOV BX, 10")
        self.emit_code("    IMUL BX")
        self.emit_code("    MOV SI, AX")
        self.emit_code("    POP AX")
        self.emit_code("    ADD SI, AX")
        self.emit_code("    JMP _ri_read")
        self.emit_code("_ri_done:")
        self.emit_code("    MOV AX, SI")
        self.emit_code("    CMP DI, 0")
        self.emit_code("    JE _ri_exit")
        self.emit_code("    NEG AX")
        self.emit_code("_ri_exit:")
        self.emit_code("    POP DI")
        self.emit_code("    POP SI")
        self.emit_code("    POP DX")
        self.emit_code("    POP CX")
        self.emit_code("    POP BX")
        self.emit_code("    RET")
        self.emit_code("readint ENDP")
        self.emit_code("")
    
    def generate(self) -> str:
        """生成完整的汇编代码"""
        self.asm_code.clear()
        self.data_section.clear()
        self.stack_section.clear()
        self.code_section.clear()
        self.string_literals.clear()
        self.string_count = 0
        self.label_map.clear()
        
        # 生成代码段（会收集字符串字面量）
        self.generate_code_section()
        
        # 生成辅助函数
        self.generate_helpers()

        # 关闭代码段（辅助函数也在代码段内）
        self.emit_code("CODE ENDS")
        self.emit_code("")
        
        # 生成数据段
        self.generate_data_section()
        self.stack_section.extend([
            "STACK SEGMENT PARA STACK 'STACK'",
            "    DW 100H DUP(?)",
            "STACK ENDS",
            "",
        ])
        
        # 组合
        self.asm_code.extend(self.data_section)
        self.asm_code.extend(self.stack_section)
        self.asm_code.extend(self.code_section)
        self.asm_code.append("END START")
        
        return "\n".join(self.asm_code)
    
    def save_to_file(self, filename: str):
        """保存汇编代码到文件"""
        code = self.generate()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(code)
        return filename

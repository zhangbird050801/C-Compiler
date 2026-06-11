from typing import List, Dict, Set
from ir_generator import Quadruple, IRGenerator
from symbol_table import SymbolTable, SymbolKind


class CodeGenerator:
    """8086汇编代码生成器"""
    
    def __init__(self, ir_generator: IRGenerator, symbol_table: SymbolTable):
        # ir_gen 提供四元式列表，codegen 的任务就是逐条翻译这些四元式。
        self.ir_gen = ir_generator
        # symbol_table 用来确定变量、数组、结构体成员的数据段定义。
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

        # 先从符号表找出声明为 float/double 的变量。
        for name, symbol in self.symbol_table.global_scope.symbols.items():
            if symbol.kind == SymbolKind.VARIABLE and symbol.type_info:
                if symbol.type_info.base in ["float", "double"]:
                    float_vars.add(self.normalize_var_name(name))

        # 再从四元式传播浮点属性：浮点赋值或浮点运算结果也要按定点处理。
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
        # 数据段先输出段头，再收集字符串、变量、临时变量和数组定义。
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
        # key 是汇编符号名，value 是 DW/DB 定义；统一收集后再排序输出，避免重复定义。
        all_vars: Dict[str, str] = {}

        def array_def_size(var_def: str):
            marker = "DUP("
            if marker not in var_def:
                return None
            prefix = var_def.split(marker, 1)[0].strip().split()
            if not prefix:
                return None
            try:
                return int(prefix[-1])
            except ValueError:
                return None

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
            elif new_is_array and old_is_array:
                old_size = array_def_size(old_def) or 0
                new_size = array_def_size(var_def) or 0
                if new_size > old_size:
                    all_vars[name] = var_def
        
        # 从符号表收集源程序里声明过的变量和数组。
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
        
        # 从四元式中补充收集临时变量、结构体展开变量和数组访问变量。
        # 例如 T1/T2 不在源码符号表中，但四元式使用了它们，汇编数据段必须补定义。
        for quad in self.ir_gen.quadruples:
            if quad.op == "[]=":
                size = 50
                if self.is_number(quad.arg2):
                    size = int(float(quad.arg2)) + 1
                add_var(self.normalize_var_name(quad.result), f"DW {size} DUP(0)")
            elif quad.op == "=[]":
                array_name = self.normalize_var_name(quad.arg1)
                if array_name not in all_vars:
                    add_var(array_name, "DW 50 DUP(0)")

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
        # 四元式的跳转目标是数字编号；汇编需要把这些编号转换成 L0/L1 这样的标签。
        # 先扫描再生成代码，是为了在遇到第一条跳转前就知道所有目标标签。
        for i, quad in enumerate(self.ir_gen.quadruples):
            if quad.op.startswith("j"):
                # 跳转指令
                if quad.result.isdigit():
                    # result 是目标四元式编号，例如 goto 17。
                    target = int(quad.result)
                    if target not in self.label_map:
                        # 第一次遇到该目标时分配一个稳定的汇编标签。
                        self.label_map[target] = f"L{len(self.label_map)}"
            elif quad.op == "label":
                # 显式标签
                if i not in self.label_map:
                    self.label_map[i] = quad.arg1
    
    def generate_code_section(self):
        """生成代码段"""
        # 输出代码段头和段寄存器初始化。
        self.emit_code("CODE SEGMENT")
        self.emit_code("    ASSUME CS:CODE, DS:DATA, SS:STACK")
        self.emit_code("")
        self.emit_code("START:")
        self.emit_code("    MOV AX, DATA")
        self.emit_code("    MOV DS, AX")
        self.emit_code("")
        
        # 扫描并生成标签
        # 必须先扫描所有四元式，才能知道哪些位置需要输出标签。
        self.scan_labels()
        
        # 遍历四元式生成汇编代码
        for i, quad in enumerate(self.ir_gen.quadruples):
            # 如果这个位置有标签，生成标签
            if i in self.label_map:
                # 例如 quad 10 是循环入口，会在其前面输出 L2:。
                self.emit_code(f"{self.label_map[i]}:")
            
            # 每条四元式前输出注释，方便从 output.asm 反查四元式来源。
            self.emit_comment(f"[{i}] {quad}")
            # 真正翻译单条四元式。
            self.translate_quadruple(quad, i)
            self.emit_code("")
        
        # 程序结束
        self.emit_code("EXIT:")
        self.emit_code("    MOV AH, 4CH")
        self.emit_code("    INT 21H")
    
    def translate_quadruple(self, quad: Quadruple, index: int):
        """翻译单个四元式为汇编代码"""
        # 四元式格式固定为 (op, arg1, arg2, result)，这里先拆出来分发。
        op = quad.op
        arg1, arg2, result = quad.arg1, quad.arg2, quad.result
        
        if op == "=":
            # 赋值操作
            # 形如 (=, rhs, _, lhs)，翻译成 MOV AX,rhs; MOV lhs,AX。
            self.gen_assignment(arg1, result)
        
        elif op in ["+", "-", "*", "/", "%"]:
            # 算术运算
            # 形如 (+, a, b, t)，翻译成寄存器运算并把结果写入 t。
            self.gen_arithmetic(op, arg1, arg2, result)
        
        elif op.startswith("j"):
            # 跳转指令
            # j 是无条件跳转，j< / j>= 等是条件跳转。
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
            # result 保存要输出的字符串、变量或常量。
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
            # 形如 (=[], arr, idx, t)，翻译成按 idx 计算偏移后读取 arr[idx]。
            self.gen_array_load(arg1, arg2, result)
        
        elif op == "[]=":
            # 数组赋值 array[index] = value
            # 形如 ([]=, value, idx, arr)，翻译成按 idx 计算偏移后写 arr[idx]。
            self.gen_array_store(result, arg2, arg1)
        
        elif op == "label":
            # 标签（已在前面处理）
            pass
        
        else:
            self.emit_code(f"    ; 未实现的操作: {op}")
    
    def gen_assignment(self, source: str, dest: str):
        """生成赋值代码"""
        # dest_name 是适合汇编使用的目标变量名，例如 Li.score 会规范化成 Li_score。
        dest_name = self.normalize_var_name(dest)
        dest_is_float = self.is_float_operand(dest)

        # 处理源操作数
        if self.is_number(source):
            # 数字源操作数直接装入 AX；浮点数按定点规则缩放或四舍五入。
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
            # 字符串放入数据段，AX 中保存字符串偏移地址。
            label = self.add_string_literal(str_content)
            self.emit_code(f"    MOV AX, OFFSET {label}")
        else:
            # 变量或临时变量源操作数：从内存读到 AX。
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
            # 当前简化实现把复杂数组目标规范化成普通符号写回。
            var_name = self.normalize_var_name(dest)
            self.emit_code(f"    MOV {var_name}, AX")
        else:
            # 普通赋值：把 AX 写入目标变量。
            self.emit_code(f"    MOV {dest_name}, AX")
    
    def gen_arithmetic(self, op: str, arg1: str, arg2: str, result: str):
        """生成算术运算代码"""
        # 只要任一操作数或结果是浮点，就用定点缩放模式处理。
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

        # 整数模式：加载第一个操作数到 AX。
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
        
        # 加载第二个操作数到 BX。
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
        
        # 根据 op 选择 8086 算术指令。
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
        
        # 运算结果统一保存在 AX，最后写入 result。
        self.emit_code(f"    MOV {self.normalize_var_name(result)}, AX")
    
    def gen_jump(self, op: str, arg1: str, arg2: str, label: str):
        """生成跳转代码"""
        # op == "j" 表示无条件跳转，对应四元式 (j, _, _, target)。
        if op == "j":
            # 无条件跳转
            # label 如果是四元式编号，先查 label_map 转成 L0/L1 这样的汇编标签。
            target = self.label_map.get(int(label) if label.isdigit() else -1, label)
            # 输出 JMP 目标标签，例如 JMP L2。
            self.emit_code(f"    JMP {target}")
        else:
            # 条件跳转
            # 条件跳转先把左右操作数分别装入 AX/BX，再 CMP。
            # CMP 之后再根据四元式 op 选择 JL/JG/JLE/JGE/JE/JNE。
            # 如果任一操作数是浮点变量/常量，比较前要按定点缩放处理。
            float_compare = self.is_float_operand(arg1) or self.is_float_operand(arg2)
            # 左操作数是常量时直接装入 AX。
            if self.is_number(arg1):
                # 浮点比较使用 fixed_scale 缩放后的整数。
                left_value = round(float(arg1) * self.fixed_scale) if float_compare else int(float(arg1))
                self.emit_code(f"    MOV AX, {left_value}")
            else:
                # 左操作数是变量/临时变量时，从内存装入 AX。
                self.emit_code(f"    MOV AX, {self.normalize_var_name(arg1)}")
            
            # 右操作数是常量时直接装入 BX。
            if self.is_number(arg2):
                # 同样根据是否浮点比较决定是否缩放。
                right_value = round(float(arg2) * self.fixed_scale) if float_compare else int(float(arg2))
                self.emit_code(f"    MOV BX, {right_value}")
            else:
                # 右操作数是变量/临时变量时，从内存装入 BX。
                self.emit_code(f"    MOV BX, {self.normalize_var_name(arg2)}")
            
            # CMP 设置标志位，后面的条件跳转根据标志位决定是否跳转。
            self.emit_code(f"    CMP AX, BX")
            
            # 根据操作符选择跳转指令
            # 四元式 j>= 对应汇编 JGE，j<= 对应 JLE。
            # label 是四元式编号时，需要先转换成 scan_labels 分配的汇编标签。
            target = self.label_map.get(int(label) if label.isdigit() else -1, label)
            # 四元式条件跳转操作符到 8086 条件跳转指令的映射。
            jump_map = {
                "j<": "JL",
                "j>": "JG",
                "j<=": "JLE",
                "j>=": "JGE",
                "j==": "JE",
                "j!=": "JNE"
            }
            
            # 默认兜底为 JMP，正常情况下 op 都会在 jump_map 中。
            jump_inst = jump_map.get(op, "JMP")
            # 输出最终条件跳转，例如 JGE L0 或 JLE L1。
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
            # 字符串输出时把字符串放入数据段，AX 保存 OFFSET，再调用 dispmsg。
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
                # 变量输出时把变量值装入 AX，再根据类型调用整数/字符/浮点输出过程。
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
                # 当前 c-code.c 的 printf("%d", max) 最终走这里，调用整数输出。
                self.emit_code(f"    CALL dispsiw  ; 输出AX中的数字")
    
    def gen_array_load(self, array: str, index: str, result: str):
        """生成数组读取代码"""
        # result = array[index]
        # 清理数组名（去掉点号）
        # 结构体成员数组 Li.score 在 IR 中已经展开为 Li_score。
        # 这里再做一次替换，保证出现点号时也能成为合法汇编符号。
        clean_array = array.replace('.', '_')
        
        # 下标是常量时，可以在编译期算出固定字节偏移。
        if self.is_number(index):
            # 常量下标可以编译期直接换算成字节偏移；DW 元素占 2 字节。
            offset = int(index) * 2  # 假设每个元素2字节
            # 直接读取 array[offset] 到 AX。
            self.emit_code(f"    MOV AX, {clean_array}[{offset}]")
        else:
            # 变量下标运行时计算偏移：BX = index * 2。
            # 8086 的 word 数组按字节寻址，所以 i 要左移一位后才能作为偏移。
            # 先把变量下标 i 装入 BX。
            self.emit_code(f"    MOV BX, {index}")
            # 左移 1 位等价于乘以 2，得到 word 数组的字节偏移。
            self.emit_code(f"    SHL BX, 1  ; 乘以2")
            # 用 BX 作为偏移读取数组元素。
            self.emit_code(f"    MOV AX, {clean_array}[BX]")
        
        # 数组元素读入 AX 后，写入四元式指定的临时变量 result。
        # 例如把 Li_score[i] 的值写入 T1。
        self.emit_code(f"    MOV {result}, AX")
    
    def gen_array_store(self, array: str, index: str, value: str):
        """生成数组赋值代码"""
        # array[index] = value
        # 清理数组名
        # 写数组时同样先把数组名规范化，避免结构体点号影响汇编符号。
        # 例如 Li.score 会变成 Li_score。
        clean_array = array.replace('.', '_')
        
        # 处理值
        try:
            # 常量值先转成整数装入 AX。
            # 尝试转换为浮点数，使用四舍五入
            float_val = float(value)
            int_val = round(float_val)
            # 数组初始化里的 80、90、100 等常量会走这里。
            self.emit_code(f"    MOV AX, {int_val}  ; 浮点数 {value} 四舍五入")
        except ValueError:
            # 不是数字，是变量名
            # 变量值从内存装入 AX。
            # 如果 value 是 T1 或普通变量，就先把它装入 AX。
            self.emit_code(f"    MOV AX, {value}")
        
        # 常量下标可以直接写固定偏移。
        if self.is_number(index):
            # 常量下标直接写固定偏移。
            offset = int(index) * 2
            # 把 AX 写入 array[offset]。
            self.emit_code(f"    MOV {clean_array}[{offset}], AX")
        else:
            # 变量下标运行时换算成字节偏移后写入。
            # 与数组读取相同，word 数组需要使用 index * 2 作为字节偏移。
            # 先把变量下标装入 BX。
            self.emit_code(f"    MOV BX, {index}")
            # 再把下标换算成字节偏移。
            self.emit_code(f"    SHL BX, 1")
            # 最后把 AX 写入 array[BX]。
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
        # 每次生成前清空上一次的段内容、字符串表和标签映射。
        self.asm_code.clear()
        self.data_section.clear()
        self.stack_section.clear()
        self.code_section.clear()
        self.string_literals.clear()
        self.string_count = 0
        self.label_map.clear()
        
        # 生成代码段（翻译 printf 时会顺便收集字符串字面量）。
        self.generate_code_section()
        
        # 生成辅助函数，例如整数输出、字符串输出和输入整数。
        self.generate_helpers()

        # 关闭代码段（辅助函数也在代码段内）
        self.emit_code("CODE ENDS")
        self.emit_code("")
        
        # 生成数据段；此时字符串表和四元式临时变量都已经收集完。
        self.generate_data_section()
        self.stack_section.extend([
            "STACK SEGMENT PARA STACK 'STACK'",
            "    DW 100H DUP(?)",
            "STACK ENDS",
            "",
        ])
        
        # 按 MASM 风格组合数据段、栈段、代码段和 END START。
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

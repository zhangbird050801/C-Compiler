from typing import List, Dict, Set, Optional
from ir_generator import Quadruple, IRGenerator
from symbol_table import SymbolTable, Symbol, SymbolKind, Type


class CodeGenerator:
    """8086汇编代码生成器"""
    
    def __init__(self, ir_generator: IRGenerator, symbol_table: SymbolTable):
        self.ir_gen = ir_generator
        self.symbol_table = symbol_table
        self.asm_code: List[str] = []
        self.data_section: List[str] = []
        self.code_section: List[str] = []
        self.string_literals: Dict[str, str] = {}  # 字符串字面量映射
        self.string_count = 0
        self.label_map: Dict[int, str] = {}  # 四元式位置到标签的映射
        
        # 寄存器分配（简化版）
        self.registers = ["AX", "BX", "CX", "DX"]
        self.reg_pool = set(self.registers)
        self.var_reg_map: Dict[str, str] = {}
    
    def allocate_reg(self) -> Optional[str]:
        """分配寄存器"""
        if self.reg_pool:
            return self.reg_pool.pop()
        return None
    
    def free_reg(self, reg: str):
        """释放寄存器"""
        if reg in self.registers:
            self.reg_pool.add(reg)
            # 清除变量到寄存器的映射
            to_remove = [var for var, r in self.var_reg_map.items() if r == reg]
            for var in to_remove:
                del self.var_reg_map[var]
    
    def get_var_location(self, var: str) -> str:
        """获取变量的位置（寄存器或内存）"""
        if var in self.var_reg_map:
            return self.var_reg_map[var]
        return f"[{var}]"
    
    def emit_data(self, line: str):
        """添加数据段代码"""
        self.data_section.append(line)
    
    def emit_code(self, line: str):
        """添加代码段代码"""
        self.code_section.append(line)
    
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
        
        # 转义处理
        escaped = content.replace("\\n", "', 13, 10, '")
        self.emit_data(f"{label} DB '{escaped}', 0")
        
        return label
    
    def generate_data_section(self):
        """生成数据段"""
        self.emit_data("DATA SEGMENT")
        
        # 添加字符串字面量（在处理四元式时收集）
        
        # 收集所有需要定义的变量（包括结构体成员）
        all_vars = set()
        
        # 从符号表收集
        for name, symbol in self.symbol_table.global_scope.symbols.items():
            if symbol.kind == SymbolKind.VARIABLE:
                if symbol.type_info.is_array():
                    # 数组
                    size = 1
                    for dim in symbol.type_info.array_dims:
                        size *= dim
                    all_vars.add((name, f"DW {size} DUP(0)"))
                elif symbol.type_info.is_struct:
                    # 结构体成员展开（简化处理）
                    # 不定义结构体本身，而是定义其成员
                    pass
                else:
                    # 普通变量
                    all_vars.add((name, "DW 0"))
        
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
                    
                    # 清理变量名（点号转下划线）
                    clean_var = var.replace('.', '_').replace('[', '_').replace(']', '_')
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
                                all_vars.add((clean_name, "DW 50 DUP(0)"))  # 假设数组大小
                            else:
                                all_vars.add((clean_name, "DW 0"))
                    elif var.startswith("T") and var[1:].isdigit():
                        # 临时变量
                        all_vars.add((var, "DW 0"))
        
        # 输出变量定义
        for var_name, var_def in sorted(all_vars):
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
        self.emit_code("    ASSUME CS:CODE, DS:DATA")
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
        self.emit_code("CODE ENDS")
        self.emit_code("")
    
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
        
        elif op == "scanf":
            # scanf调用（简化）
            self.emit_code(f"    ; scanf {result}")
        
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
        # 处理源操作数
        if self.is_number(source):
            # 处理浮点数：四舍五入转换为整数
            if '.' in source:
                try:
                    float_val = float(source)
                    int_val = round(float_val)  # 四舍五入
                    self.emit_code(f"    MOV AX, {int_val}  ; 浮点数 {source} 四舍五入")
                except:
                    self.emit_code(f"    MOV AX, 0  ; 浮点数 {source} 转换失败")
            else:
                self.emit_code(f"    MOV AX, {source}")
        elif source.startswith('"'):
            # 字符串字面量（可能包含内部引号）
            # 提取引号之间的内容
            str_content = source[1:-1] if source.endswith('"') else source[1:]
            label = self.add_string_literal(str_content)
            self.emit_code(f"    MOV AX, OFFSET {label}")
        elif "." in source:
            # 结构体成员访问 - 转换为下划线
            var_name = source.replace('.', '_')
            self.emit_code(f"    MOV AX, {var_name}")
        else:
            self.emit_code(f"    MOV AX, {source}")
        
        # 处理目标操作数
        if "." in dest:
            # 结构体成员 - 转换为下划线
            var_name = dest.replace('.', '_')
            self.emit_code(f"    MOV {var_name}, AX")
        elif "[" in dest and "]" in dest:
            # 数组访问 - 去掉点号
            var_name = dest.replace('.', '_')
            self.emit_code(f"    MOV {var_name}, AX")
        else:
            self.emit_code(f"    MOV {dest}, AX")
    
    def gen_arithmetic(self, op: str, arg1: str, arg2: str, result: str):
        """生成算术运算代码"""
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
        self.emit_code(f"    MOV {result}, AX")
    
    def gen_jump(self, op: str, arg1: str, arg2: str, label: str):
        """生成跳转代码"""
        if op == "j":
            # 无条件跳转
            target = self.label_map.get(int(label) if label.isdigit() else -1, label)
            self.emit_code(f"    JMP {target}")
        else:
            # 条件跳转
            # 比较arg1和arg2
            if self.is_number(arg1):
                self.emit_code(f"    MOV AX, {arg1}")
            else:
                self.emit_code(f"    MOV AX, [{arg1}]")
            
            if self.is_number(arg2):
                self.emit_code(f"    MOV BX, {arg2}")
            else:
                self.emit_code(f"    MOV BX, [{arg2}]")
            
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
    
    def gen_printf(self, arg: str):
        """生成printf输出代码"""
        if arg.startswith('"') and arg.endswith('"'):
            # 字符串字面量
            label = self.add_string_literal(arg[1:-1])
            self.emit_code(f"    MOV AX, OFFSET {label}")
            self.emit_code(f"    CALL dispmsg")
        else:
            # 变量或数字
            if self.is_number(arg):
                if '.' in arg:
                    try:
                        int_val = round(float(arg))
                        self.emit_code(f"    MOV AX, {int_val}  ; {arg}")
                    except:
                        self.emit_code(f"    MOV AX, 0")
                else:
                    self.emit_code(f"    MOV AX, {arg}")
            else:
                # 清理变量名
                clean_var = arg.replace('.', '_')
                self.emit_code(f"    MOV AX, {clean_var}")
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
    
    def generate(self) -> str:
        """生成完整的汇编代码"""
        self.asm_code.clear()
        self.data_section.clear()
        self.code_section.clear()
        self.string_literals.clear()
        self.string_count = 0
        self.label_map.clear()
        
        # 生成代码段（会收集字符串字面量）
        self.generate_code_section()
        
        # 生成辅助函数
        self.generate_helpers()
        
        # 生成数据段
        self.generate_data_section()
        
        # 组合
        self.asm_code.extend(self.data_section)
        self.asm_code.extend(self.code_section)
        self.asm_code.append("END START")
        
        return "\n".join(self.asm_code)
    
    def save_to_file(self, filename: str):
        """保存汇编代码到文件"""
        code = self.generate()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(code)
        return filename

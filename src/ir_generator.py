from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from symbol_table import SymbolTable, Symbol, Type, SymbolKind
from constants import TYPES, EOF


@dataclass
class Quadruple:
    """四元式 (操作符, 参数1, 参数2, 结果)"""
    op: str
    arg1: str
    arg2: str
    result: str
    line: int = 0
    
    def __str__(self):
        return f"({self.op}, {self.arg1}, {self.arg2}, {self.result})"
    
    def to_readable(self) -> str:
        """生成可读形式"""
        if self.op == "=":
            return f"{self.result} = {self.arg1}"
        elif self.op in ["+", "-", "*", "/", "%"]:
            return f"{self.result} = {self.arg1} {self.op} {self.arg2}"
        elif self.op.startswith("j"):
            # 条件跳转或无条件跳转
            if self.op == "j":
                return f"goto {self.result}"
            else:
                return f"if {self.arg1} {self.op[1:]} {self.arg2} goto {self.result}"
        elif self.op == "call":
            if self.arg2 == "_":
                return f"{self.result} = call {self.arg1}"
            else:
                return f"{self.result} = call {self.arg1}, {self.arg2}"
        elif self.op == "param":
            return f"param {self.arg1}"
        elif self.op == "return":
            return f"return {self.arg1}"
        elif self.op == "printf":
            return f"printf {self.result}"
        elif self.op == "scanf":
            return f"scanf {self.result}"
        elif self.op == "label":
            return f"{self.arg1}:"
        elif self.op == "=[]":
            return f"{self.result} = {self.arg1}[{self.arg2}]"
        elif self.op == "[]=":
            return f"{self.result}[{self.arg2}] = {self.arg1}"
        else:
            return str(self)


class IRGenerator:
    """中间代码生成器"""
    
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table
        self.quadruples: List[Quadruple] = []
        self.temp_count = 0
        self.label_count = 0
        self.errors: List[str] = []
        
        # 用于回填的标签栈
        self.break_stack: List[int] = []
        self.continue_stack: List[int] = []
    
    def new_temp(self) -> str:
        """生成新的临时变量"""
        self.temp_count += 1
        return f"T{self.temp_count}"
    
    def new_label(self) -> str:
        """生成新的标签"""
        self.label_count += 1
        return f"L{self.label_count}"
    
    def emit(self, op: str, arg1: str = "_", arg2: str = "_", result: str = "_", line: int = 0):
        """生成一条四元式"""
        quad = Quadruple(op, arg1, arg2, result, line)
        self.quadruples.append(quad)
        return len(self.quadruples) - 1
    
    def backpatch(self, quad_list: List[int], label: str):
        """回填"""
        for idx in quad_list:
            if idx < len(self.quadruples):
                self.quadruples[idx].result = label
    
    def next_quad(self) -> int:
        """返回下一条四元式的位置"""
        return len(self.quadruples)
    
    def gen_assignment(self, lhs: str, rhs: str, line: int = 0):
        """生成赋值语句"""
        self.emit("=", rhs, "_", lhs, line)
    
    def gen_binary_op(self, op: str, arg1: str, arg2: str, result: str, line: int = 0):
        """生成二元运算"""
        self.emit(op, arg1, arg2, result, line)
    
    def gen_unary_op(self, op: str, arg: str, result: str, line: int = 0):
        """生成一元运算"""
        if op == "-":
            self.emit("-", "0", arg, result, line)
        elif op == "!":
            self.emit("!", arg, "_", result, line)
        else:
            self.emit(op, arg, "_", result, line)
    
    def gen_goto(self, label: str, line: int = 0) -> int:
        """生成无条件跳转"""
        return self.emit("j", "_", "_", label, line)
    
    def gen_if_goto(self, condition: str, op: str, arg2: str, label: str, line: int = 0) -> int:
        """生成条件跳转"""
        # op可以是: <, >, <=, >=, ==, !=
        return self.emit(f"j{op}", condition, arg2, label, line)
    
    def gen_label(self, label: str):
        """生成标签"""
        self.emit("label", label, "_", "_")
    
    def gen_param(self, param: str, line: int = 0):
        """生成参数传递"""
        self.emit("param", param, "_", "_", line)
    
    def gen_call(self, func_name: str, param_count: int, result: str, line: int = 0):
        """生成函数调用"""
        self.emit("call", func_name, str(param_count), result, line)
    
    def gen_return(self, value: str = "_", line: int = 0):
        """生成返回语句"""
        self.emit("return", value, "_", "_", line)
    
    def gen_array_access(self, array_name: str, index: str, result: str, line: int = 0):
        """生成数组访问"""
        # array[index] -> result = array[index]
        self.emit("=[]", array_name, index, result, line)
    
    def gen_array_store(self, array_name: str, index: str, value: str, line: int = 0):
        """生成数组赋值"""
        # array[index] = value
        self.emit("[]=", value, index, array_name, line)
    
    def gen_struct_access(self, struct_var: str, member: str, result: str, line: int = 0):
        """生成结构体成员访问"""
        # struct.member -> result = struct.member
        member_ref = f"{struct_var}.{member}"
        self.emit("=", member_ref, "_", result, line)
    
    def gen_struct_store(self, struct_var: str, member: str, value: str, line: int = 0):
        """生成结构体成员赋值"""
        # struct.member = value
        member_ref = f"{struct_var}.{member}"
        self.emit("=", value, "_", member_ref, line)
    
    def gen_printf(self, format_str: str, args: List[str], line: int = 0):
        """生成printf调用"""
        # 简化版：每个参数生成一条printf四元式
        if format_str:
            self.emit("printf", "_", "_", format_str, line)
        for arg in args:
            self.emit("printf", "_", "_", arg, line)
    
    def gen_scanf(self, var: str, line: int = 0):
        """生成scanf调用"""
        self.emit("scanf", "_", "_", var, line)
    
    def gen_if_statement(self, condition_code: Tuple[str, List[int], List[int]], 
                        true_quad: int, false_quad: int = None) -> Tuple[List[int], List[int]]:
        """
        生成if语句
        返回: (next_list, 需要回填的跳转列表)
        """
        cond_result, true_list, false_list = condition_code
        
        # 回填真出口
        true_label = self.new_label()
        self.backpatch(true_list, str(true_quad))
        
        # 处理假出口
        if false_quad is not None:
            self.backpatch(false_list, str(false_quad))
        
        return true_list, false_list
    
    def gen_while_statement(self, begin: int, condition_code: Tuple[str, List[int], List[int]], 
                           body_quad: int) -> List[int]:
        """生成while循环"""
        cond_result, true_list, false_list = condition_code
        
        # 回填真出口到循环体
        self.backpatch(true_list, str(body_quad))
        
        # 循环体结束后跳回条件判断
        self.gen_goto(str(begin))
        
        return false_list
    
    def gen_for_statement(self, init_quad: int, cond_quad: int, 
                         condition_code: Tuple[str, List[int], List[int]],
                         step_quad: int, body_quad: int) -> List[int]:
        """生成for循环"""
        cond_result, true_list, false_list = condition_code
        
        # 回填真出口到循环体
        self.backpatch(true_list, str(body_quad))
        
        # 循环体结束后跳到步进语句
        # 步进语句结束后跳回条件判断
        
        return false_list
    
    def optimize(self):
        """简单优化：删除无用的跳转和临时变量"""
        # 这里可以实现一些简单的优化
        # 例如：删除跳转到下一条指令的跳转
        optimized = []
        for i, quad in enumerate(self.quadruples):
            if quad.op == "j" and quad.result.isdigit():
                target = int(quad.result)
                if target == i + 1:
                    continue  # 跳过跳转到下一条的指令
            optimized.append(quad)
        
        self.quadruples = optimized
    
    def to_string(self) -> str:
        """转换为字符串表示"""
        lines = ["=" * 60, "中间代码（四元式）", "=" * 60]
        for i, quad in enumerate(self.quadruples):
            lines.append(f"{i:4d}  {quad}")
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def to_readable_string(self) -> str:
        """转换为可读的形式"""
        lines = ["=" * 60, "中间代码（可读形式）", "=" * 60]
        for i, quad in enumerate(self.quadruples):
            lines.append(f"{i:4d}  {quad.to_readable()}")
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def get_quadruples(self) -> List[Quadruple]:
        """获取四元式列表"""
        return self.quadruples
    
    def clear(self):
        """清空生成器状态"""
        self.quadruples.clear()
        self.temp_count = 0
        self.label_count = 0
        self.errors.clear()

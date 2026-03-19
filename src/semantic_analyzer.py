from typing import List, Optional, Tuple
from dataclasses import dataclass
from symbol_table import SymbolTable, Symbol, SymbolKind, Type, Scope
from constants import TYPES, EOF


@dataclass
class ASTNode:
    """抽象语法树节点"""
    node_type: str
    value: any = None
    children: List['ASTNode'] = None
    attributes: dict = None
    line: int = 0
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.attributes is None:
            self.attributes = {}


class SemanticAnalyzer:
    """语义分析器"""
    
    def __init__(self, tokens: List):
        self.tokens = tokens
        self.pos = 0
        self.current_token = None
        self.symbol_table = SymbolTable()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.ast = None
        
        # 过滤预处理指令
        self.tokens = [t for t in tokens if TYPES.get(t.type) != "PREPROCESSOR"]
        if self.tokens:
            self.current_token = self.tokens[0]
    
    def error(self, msg: str, line: int = None):
        """记录错误"""
        l = line if line is not None else (self.current_token.line if self.current_token else 0)
        self.errors.append(f"语义错误 (行 {l}): {msg}")
    
    def warning(self, msg: str, line: int = None):
        """记录警告"""
        l = line if line is not None else (self.current_token.line if self.current_token else 0)
        self.warnings.append(f"警义 (行 {l}): {msg}")
    
    def advance(self):
        """前进到下一个token"""
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = None
    
    def peek(self, offset: int = 1) -> Optional:
        """向前查看token"""
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return None
    
    def expect(self, expected_type_or_value) -> bool:
        """检查当前token是否符合预期"""
        if self.current_token is None:
            return False
        
        if isinstance(expected_type_or_value, int):
            return self.current_token.type == expected_type_or_value
        else:
            return self.current_token.attribute == expected_type_or_value
    
    def parse_type(self) -> Optional[Type]:
        """解析类型"""
        if not self.current_token:
            return None
        
        base_type = None
        pointer_level = 0
        
        # 解析基础类型
        if self.expect("typedef"):
            self.advance()
            # typedef 定义
            return self.parse_typedef()
        
        if self.expect("struct"):
            self.advance()
            if self.expect(TYPES.get(82, "IDENTIFIER")):  # struct name
                struct_name = self.current_token.attribute
                self.advance()
                return Type(base="struct", is_struct=True, struct_name=struct_name)
        
        # 基本类型
        type_keywords = ["int", "float", "char", "double", "void", "long", "short", "signed", "unsigned"]
        if self.current_token.attribute in type_keywords:
            base_type = self.current_token.attribute
            self.advance()
        else:
            return None
        
        # 解析指针
        while self.current_token and self.current_token.attribute == "*":
            pointer_level += 1
            self.advance()
        
        return Type(base=base_type, pointer_level=pointer_level)
    
    def parse_typedef(self) -> Optional[Type]:
        """解析typedef"""
        # 简化版：跳过typedef处理
        # 完整实现需要处理复杂的typedef语法
        return None
    
    def check_type_compatibility(self, type1: Type, type2: Type) -> bool:
        """检查类型兼容性"""
        if type1 is None or type2 is None:
            return False
        
        # 简化版类型检查
        if type1.base != type2.base:
            # 允许int和float之间的隐式转换
            if {type1.base, type2.base}.issubset({"int", "float", "double"}):
                return True
            return False
        
        if type1.pointer_level != type2.pointer_level:
            return False
        
        return True
    
    def check_array_index(self, array_type: Type, index_node: ASTNode) -> bool:
        """检查数组索引"""
        if not array_type.is_array():
            self.error("对非数组类型使用下标")
            return False
        
        # 检查索引是否为整数类型
        # 简化版：假设索引合法
        return True
    
    def check_function_call(self, func_name: str, args: List[ASTNode]) -> Optional[Type]:
        """检查函数调用"""
        func_symbol = self.symbol_table.lookup(func_name)
        
        if not func_symbol:
            self.error(f"未定义的函数: {func_name}")
            return None
        
        if func_symbol.kind != SymbolKind.FUNCTION:
            self.error(f"{func_name} 不是函数")
            return None
        
        # 检查参数数量
        if len(args) != len(func_symbol.params):
            self.error(f"函数 {func_name} 参数数量不匹配：期望 {len(func_symbol.params)}，实际 {len(args)}")
        
        # 检查参数类型（简化版）
        # 完整实现需要递归检查每个参数的类型
        
        return func_symbol.type_info
    
    def check_assignment(self, lhs_type: Type, rhs_type: Type, line: int):
        """检查赋值语句的类型兼容性"""
        if not self.check_type_compatibility(lhs_type, rhs_type):
            self.error(f"类型不兼容的赋值: {lhs_type} = {rhs_type}", line)
    
    def check_binary_op(self, op: str, left_type: Type, right_type: Type) -> Optional[Type]:
        """检查二元运算"""
        # 算术运算符
        if op in ["+", "-", "*", "/", "%"]:
            if left_type.base in ["int", "float", "double"] and right_type.base in ["int", "float", "double"]:
                # 提升到更宽的类型
                if "double" in [left_type.base, right_type.base]:
                    return Type(base="double")
                elif "float" in [left_type.base, right_type.base]:
                    return Type(base="float")
                else:
                    return Type(base="int")
            else:
                self.error(f"算术运算符 {op} 的操作数类型错误")
                return None
        
        # 比较运算符
        elif op in ["<", ">", "<=", ">=", "==", "!="]:
            return Type(base="int")  # 返回bool/int
        
        # 逻辑运算符
        elif op in ["&&", "||"]:
            return Type(base="int")
        
        return None
    
    def analyze_declaration(self, type_info: Type, name: str, line: int) -> bool:
        """分析变量声明"""
        # 检查是否重复定义
        if self.symbol_table.current_scope.lookup(name):
            self.error(f"变量重定义: {name}", line)
            return False
        
        # 创建符号并加入符号表
        symbol = Symbol(
            name=name,
            kind=SymbolKind.VARIABLE,
            type_info=type_info
        )
        
        return self.symbol_table.define(symbol)
    
    def analyze_struct_declaration(self, struct_name: str, members: List[Tuple[Type, str]], line: int):
        """分析结构体声明"""
        if self.symbol_table.lookup_struct(struct_name):
            self.error(f"结构体重定义: {struct_name}", line)
            return False
        
        member_symbols = {}
        for member_type, member_name in members:
            member_symbols[member_name] = Symbol(
                name=member_name,
                kind=SymbolKind.VARIABLE,
                type_info=member_type
            )
        
        struct_symbol = Symbol(
            name=struct_name,
            kind=SymbolKind.STRUCT,
            members=member_symbols
        )
        
        return self.symbol_table.define(struct_symbol)
    
    def analyze_function_declaration(self, return_type: Type, func_name: str, 
                                     params: List[Tuple[Type, str]], line: int):
        """分析函数声明"""
        if self.symbol_table.lookup(func_name):
            self.error(f"函数重定义: {func_name}", line)
            return False
        
        param_symbols = []
        for param_type, param_name in params:
            param_symbols.append(Symbol(
                name=param_name,
                kind=SymbolKind.PARAMETER,
                type_info=param_type
            ))
        
        func_symbol = Symbol(
            name=func_name,
            kind=SymbolKind.FUNCTION,
            type_info=return_type,
            params=param_symbols
        )
        
        return self.symbol_table.define(func_symbol)
    
    def get_symbol_info(self, name: str) -> Optional[Symbol]:
        """获取符号信息"""
        return self.symbol_table.lookup(name)
    
    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0 or len(self.symbol_table.errors) > 0
    
    def get_all_errors(self) -> List[str]:
        """获取所有错误"""
        return self.errors + self.symbol_table.errors
    
    def print_symbol_table(self):
        """打印符号表"""
        print(self.symbol_table)
    
    def print_errors(self):
        """打印错误信息"""
        if self.has_errors():
            print("\n语义错误:")
            for err in self.get_all_errors():
                print(f"  {err}")
        else:
            print("\n语义分析通过，无错误！")
        
        if self.warnings:
            print("\n警告:")
            for warn in self.warnings:
                print(f"  {warn}")

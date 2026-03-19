from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class SymbolKind(Enum):
    VARIABLE = "variable"
    FUNCTION = "function"
    STRUCT = "struct"
    TYPEDEF = "typedef"
    PARAMETER = "parameter"


@dataclass
class Type:
    """类型信息"""
    base: str  # int, float, char, void, struct_name等
    pointer_level: int = 0  # 指针层数
    array_dims: List[int] = field(default_factory=list)  # 数组维度
    is_struct: bool = False
    struct_name: Optional[str] = None
    
    def __str__(self):
        s = self.base
        if self.pointer_level > 0:
            s += "*" * self.pointer_level
        for dim in self.array_dims:
            s += f"[{dim}]"
        return s
    
    def is_array(self) -> bool:
        return len(self.array_dims) > 0


@dataclass
class Symbol:
    """符号表项"""
    name: str
    kind: SymbolKind
    type_info: Optional[Type] = None
    scope_level: int = 0
    offset: int = 0  # 相对于栈基址的偏移
    value: Any = None  # 初始值（常量）
    params: List['Symbol'] = field(default_factory=list)  # 函数参数
    members: Dict[str, 'Symbol'] = field(default_factory=dict)  # 结构体成员
    
    def __str__(self):
        if self.kind == SymbolKind.FUNCTION:
            param_str = ", ".join(str(p.type_info) for p in self.params)
            return f"{self.type_info} {self.name}({param_str})"
        elif self.kind == SymbolKind.STRUCT:
            return f"struct {self.name}"
        else:
            return f"{self.type_info} {self.name}"


class Scope:
    """作用域"""
    def __init__(self, level: int, parent: Optional['Scope'] = None):
        self.level = level
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.offset = 0  # 当前作用域的栈偏移
    
    def define(self, symbol: Symbol) -> bool:
        """在当前作用域定义符号"""
        if symbol.name in self.symbols:
            return False
        symbol.scope_level = self.level
        symbol.offset = self.offset
        self.symbols[symbol.name] = symbol
        # 计算下一个符号的偏移
        self.offset += self._get_size(symbol.type_info)
        return True
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """在当前作用域查找符号"""
        return self.symbols.get(name)
    
    def _get_size(self, type_info: Optional[Type]) -> int:
        """计算类型大小（简化版本，以字为单位）"""
        if type_info is None:
            return 2
        base_size = 2  # 默认为2字节
        if type_info.base == "char":
            base_size = 1
        elif type_info.base == "float" or type_info.base == "double":
            base_size = 4
        
        # 数组
        total_size = base_size
        for dim in type_info.array_dims:
            total_size *= dim
        
        return total_size


class SymbolTable:
    """符号表管理器"""
    def __init__(self):
        self.global_scope = Scope(0)
        self.current_scope = self.global_scope
        self.scope_level = 0
        self.struct_types: Dict[str, Symbol] = {}  # 结构体定义
        self.typedef_names: Dict[str, Type] = {}  # typedef别名
        self.errors: List[str] = []
    
    def enter_scope(self):
        """进入新作用域"""
        self.scope_level += 1
        new_scope = Scope(self.scope_level, self.current_scope)
        self.current_scope = new_scope
    
    def exit_scope(self):
        """退出当前作用域"""
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent
            self.scope_level -= 1
    
    def define(self, symbol: Symbol) -> bool:
        """定义符号"""
        if not self.current_scope.define(symbol):
            self.errors.append(f"符号重定义: {symbol.name}")
            return False
        
        # 如果是结构体定义，加入结构体类型表
        if symbol.kind == SymbolKind.STRUCT:
            self.struct_types[symbol.name] = symbol
        
        return True
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """查找符号（支持作用域链查找）"""
        scope = self.current_scope
        while scope:
            symbol = scope.lookup(name)
            if symbol:
                return symbol
            scope = scope.parent
        return None
    
    def lookup_struct(self, name: str) -> Optional[Symbol]:
        """查找结构体类型"""
        return self.struct_types.get(name)
    
    def add_typedef(self, alias: str, type_info: Type):
        """添加typedef别名"""
        self.typedef_names[alias] = type_info
    
    def get_typedef(self, alias: str) -> Optional[Type]:
        """获取typedef定义的类型"""
        return self.typedef_names.get(alias)
    
    def is_defined(self, name: str) -> bool:
        """检查符号是否已定义"""
        return self.lookup(name) is not None
    
    def __str__(self):
        lines = ["=" * 60, "符号表", "=" * 60]
        lines.append(f"{'名称':<20} {'类型':<20} {'作用域':<10} {'偏移':<10}")
        lines.append("-" * 60)
        
        def collect_symbols(scope: Scope, symbols_list: List):
            for sym in scope.symbols.values():
                symbols_list.append(sym)
        
        all_symbols = []
        collect_symbols(self.global_scope, all_symbols)
        
        for sym in all_symbols:
            lines.append(f"{sym.name:<20} {str(sym.type_info):<20} {sym.scope_level:<10} {sym.offset:<10}")
        
        lines.append("=" * 60)
        return "\n".join(lines)

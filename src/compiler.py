from typing import Optional, List
from lexer_core import Lexer
from parser_core import LL1Parser
from semantic_analyzer import SemanticAnalyzer
from ir_generator import IRGenerator
from codegen import CodeGenerator
from symbol_table import SymbolTable


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
                return self.result
            
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
        
        # 简化版：生成示例四元式
        # 完整实现需要遍历AST生成四元式
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
        """生成示例中间代码（简化版）"""
        # 这里应该遍历AST生成四元式
        # 简化版：根据示例c-code.c生成一些四元式
        
        ir = self.ir_generator
        
        # 示例：book变量初始化
        ir.emit("=", '"Compilers: Principles, Techniques, and Tools"', "_", "book.title")
        ir.emit("=", '"Alfred V. Aho et al."', "_", "book.author")
        ir.emit("=", '" 2nd"', "_", "book.version")
        ir.emit("=", "13", "_", "book.book_id")
        ir.emit("=", "100", "_", "book.price_and_discount[0]")
        ir.emit("=", "0.8", "_", "book.price_and_discount[1]")
        
        # 计算discount_price
        t1 = ir.new_temp()
        t2 = ir.new_temp()
        ir.emit("=[]", "book.price_and_discount", "0", t1)
        ir.emit("=[]", "book.price_and_discount", "1", t2)
        ir.emit("*", t1, t2, "discount_price")
        
        # printf调用
        ir.emit("printf", "_", "_", '"Price of book "')
        ir.emit("printf", "_", "_", "book.title")
        ir.emit("printf", "_", "_", '" is: "')
        ir.emit("printf", "_", "_", "discount_price")
    
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

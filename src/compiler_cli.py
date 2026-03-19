#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
C语言编译器 - 命令行接口
支持词法分析、语法分析、语义分析、中间代码生成、目标代码生成
"""

import argparse
import sys
from pathlib import Path
from compiler import Compiler


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔════════════════════════════════════════════════════════════════╗
║                     C 语言编译器 v1.0                          ║
║              Lexer → Parser → Semantic → IR → ASM              ║
╚════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def compile_file(source_file: str, output_dir: str = None, verbose: bool = True,
                 save_tokens: bool = False, save_parse: bool = False):
    """编译C源文件"""
    
    # 读取源文件
    source_path = Path(source_file)
    if not source_path.exists():
        print(f"✗ 错误：源文件不存在: {source_file}")
        return False
    
    with open(source_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
    
    # 确定输出目录
    if output_dir is None:
        output_dir = source_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # 输出文件名（基于源文件名）
    base_name = source_path.stem
    
    if verbose:
        print_banner()
        print(f"📄 源文件: {source_path}")
        print(f"📂 输出目录: {output_dir}")
        print("=" * 70)
    
    # 创建编译器并编译
    compiler = Compiler()
    result = compiler.compile(source_code, verbose=verbose)
    
    # 保存输出文件
    if result.success:
        # 保存中间代码
        ir_file = output_dir / f"{base_name}.ir"
        compiler.save_ir(str(ir_file))
        
        # 保存汇编代码
        asm_file = output_dir / f"{base_name}.asm"
        compiler.save_assembly(str(asm_file))
        
        if verbose:
            print("\n✓ 编译成功！生成的文件：")
            print(f"  📝 {ir_file.name} - 中间代码（四元式）")
            print(f"  📝 {asm_file.name} - 目标代码（8086汇编）")
        
        # 可选：保存token列表
        if save_tokens and result.tokens:
            tokens_file = output_dir / f"{base_name}.tokens"
            with open(tokens_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("Token 列表\n")
                f.write("=" * 60 + "\n")
                for i, tok in enumerate(result.tokens):
                    from constants import TYPES
                    tok_type = TYPES.get(tok.type, "UNKNOWN")
                    f.write(f"{i:4d}  {tok_type:20s}  {tok.attribute:20s}  行{tok.line}\n")
            if verbose:
                print(f"  📝 {tokens_file.name} - Token列表")
        
        # 可选：保存语法分析过程
        if save_parse and result.parse_records:
            parse_file = output_dir / f"{base_name}.parse"
            with open(parse_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("语法分析过程\n")
                f.write("=" * 80 + "\n")
                for step, stack, input_str, prod, action in result.parse_records:
                    f.write(f"步骤 {step}:\n")
                    f.write(f"  栈: {stack}\n")
                    f.write(f"  输入: {input_str}\n")
                    if prod:
                        f.write(f"  产生式: {prod}\n")
                    f.write(f"  动作: {action}\n")
                    f.write("-" * 80 + "\n")
            if verbose:
                print(f"  📝 {parse_file.name} - 语法分析过程")
        
        return True
    else:
        if verbose:
            print("\n✗ 编译失败")
            print("\n错误列表：")
            for err in result.errors:
                print(f"  ❌ {err}")
        return False


def interactive_mode():
    """交互式模式"""
    print_banner()
    print("进入交互模式（输入 'exit' 或 'quit' 退出）\n")
    
    while True:
        try:
            print("请输入C代码（以空行结束）：")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            
            if not lines:
                continue
            
            source_code = "\n".join(lines)
            
            # 编译
            compiler = Compiler()
            result = compiler.compile(source_code, verbose=True)
            
            if result.success:
                print("\n中间代码：")
                print(compiler.ir_generator.to_readable_string())
            
            print("\n" + "=" * 70 + "\n")
            
        except (EOFError, KeyboardInterrupt):
            print("\n\n再见！")
            break
        except Exception as e:
            print(f"\n错误: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="C语言编译器 - 将C代码编译为8086汇编",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s source.c                    # 编译source.c
  %(prog)s source.c -o output/         # 指定输出目录
  %(prog)s source.c -v                 # 详细输出
  %(prog)s source.c --save-all         # 保存所有中间结果
  %(prog)s -i                          # 交互模式
        """
    )
    
    parser.add_argument('source', nargs='?', help='C源代码文件')
    parser.add_argument('-o', '--output', help='输出目录', default=None)
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='详细输出', default=True)
    parser.add_argument('-q', '--quiet', action='store_true', 
                       help='安静模式（最小输出）')
    parser.add_argument('--save-tokens', action='store_true',
                       help='保存token列表')
    parser.add_argument('--save-parse', action='store_true',
                       help='保存语法分析过程')
    parser.add_argument('--save-all', action='store_true',
                       help='保存所有中间结果')
    parser.add_argument('-i', '--interactive', action='store_true',
                       help='交互模式')
    
    args = parser.parse_args()
    
    # 交互模式
    if args.interactive:
        interactive_mode()
        return 0
    
    # 需要源文件
    if not args.source:
        parser.print_help()
        return 1
    
    # 编译文件
    verbose = args.verbose and not args.quiet
    save_tokens = args.save_tokens or args.save_all
    save_parse = args.save_parse or args.save_all
    
    success = compile_file(
        args.source,
        args.output,
        verbose=verbose,
        save_tokens=save_tokens,
        save_parse=save_parse
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

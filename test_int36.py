#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.Lexer import Lexer, TYPES, KEYWORDS

def print_token(token):
    type_name = TYPES.get(token.type, 'UNKNOWN')
    if token.type in KEYWORDS.values():
        # 找到对应的关键字
        for k, v in KEYWORDS.items():
            if v == token.type:
                type_name = f"KEYWORD({k})"
                break

    error_mark = " [ERROR]" if token.is_error else ""
    print(f"Line {token.line}: {type_name:<20} = '{token.attribute}'{error_mark}")

def test_file(filename):
    print(f"读取测试文件: {filename}")
    print("=" * 80)

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code = f.read()

        lexer = Lexer(code)
        tokens = lexer.tokenize()

        print(f"共生成 {len(tokens)} 个token:")
        print("-" * 80)

        for token in tokens:
            print_token(token)

        if lexer.errors:
            print(f"\n发现 {len(lexer.errors)} 个错误:")
            for error in lexer.errors:
                print(f"  {error}")

        print("\n" + "=" * 80)

    except FileNotFoundError:
        print(f"错误: 找不到文件 {filename}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    # 测试 src/test_sample.c 文件
    test_file("test_sample.c")
import sys
from collections import namedtuple

file = 'c-code.txt'

KEYWORDS = {
    'auto': 1, 'break': 2, 'case': 3, 'char': 4, 'const': 5, 'continue': 6, 'default': 7, 'do': 8,
    'double': 9, 'else': 10, 'enum': 11, 'extern': 12, 'float': 13, 'for': 14, 'goto': 15, 'if': 16,
    'int': 17, 'long': 18, 'register': 19, 'return': 20, 'short': 21, 'signed': 22, 'sizeof': 23, 'static': 24,
    'struct': 25, 'switch': 26, 'typedef': 27, 'union': 28, 'unsigned': 29, 'void': 30, 'volatile': 31, 'while': 32
}

OP = {
    '=': 33, '+=': 34, '-=': 35, '*=': 36, '/=': 37, '%=': 38, '&=': 39, '|=': 40, '^=': 41, '<<=': 42, '>>=': 43,
    '++': 44, '--': 45, '+': 46, '-': 47, '*': 48, '/': 49, '%': 50, '~': 51, '&': 52, '|': 53, '^': 54, '<<': 55,
    '>>': 56, '!': 57, '&&': 58, '||': 59, '==': 60, '!=': 61, '<': 62, '>': 63, '<=': 64, '>=': 65, '->': 66,
    '.': 67, '?':68, ':': 69
}

DL = {
    '(': 70, ')': 71, '[': 72, ']': 73, '{': 74, '}': 75, ',': 76, ';': 77,
}

PR = {
    '"': 78, '/*': 79, '*/': 80, '//': 81
}

ID, CONST_TEN, CONST_E, CONST_S, CONST_FLOAT, CONST_CHAR, STRING_ = 82, 83, 84, 85, 86, 87, 88
EOF = -1

TOKEN = namedtuple('Token', ['type', 'attribute'])

class SymbolTable:
    def __init__(self):
        self.symbols = {}

    def add(self, name):
        if name not in self.symbols:
            self.symbols[name] = {'name': name, 'type': None}
        return self.symbols[name]

    def __str__(self):
        return str(self.symbols)


def process(text):
    code_ = []
    char_, string_ = False, False

    i = 0
    l = len(text)
    while i < l:
        c = text[i]

        # string
        # 排除 printf("Birdy：\"Hello！\""); 里面包含转义的情况
        if c == '"' and not char_ and (i == 0 or text[i - 1] != '\\'):
            string_ = not string_
        # char
        elif c == "'" and not string_ and (i == 0 or text[i - 1] != '\\'):
            char_ = not char_

        if string_ or char_:
            code_.append(c)
            i += 1
            continue

        # //
        if c == '/' and i + 1 < l and text[i + 1] == '/':
            i += 2
            while i < l and text[i] != '\n':
                i += 1
            code_.append('\n')
            continue
        # /* */
        elif c == '/' and i + 1 < l and text[i + 1] == '*':
            i += 2
            while i < l and not (i + 1 < l and text[i:i+2] == '*/'):
                i += 1
            i += 2
            code_.append(' ')
            continue

        code_.append(c)
        i += 1

    return "".join(code_)


class Lexer:
    def __init__(self, text):
        self.text = text


if __name__ == '__main__':
    try:
        with open(file, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        print(e)
        sys.exit(1)

    code_ = process(code)
    print(code_)

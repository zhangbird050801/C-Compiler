import sys

file = 'c-code.txt'

KEYWORDS = {
    'auto': 1, 'break': 2, 'case': 3, 'char': 4, 'const': 5, 'continue': 6, 'default': 7, 'do': 8,
    'double': 9, 'else': 10, 'enum': 11, 'extern': 12, 'float': 13, 'for': 14, 'goto': 15, 'if': 16,
    'int': 17, 'long': 18, 'register': 19, 'return': 20, 'short': 21, 'signed': 22, 'sizeof': 23, 'static': 24,
    'struct': 25, 'switch': 26, 'typedef': 27, 'union': 28, 'unsigned': 29, 'void': 30, 'volatile': 31, 'while': 32
}

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


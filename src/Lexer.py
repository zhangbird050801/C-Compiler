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

ID, CONST_DECIMAL, CONST_OCTAL, CONST_HEX, CONST_FLOAT, CONST_CHAR, STRING_ = 82, 83, 84, 85, 86, 87, 88
EOF = -1
HEX_CHAR = '0123456789abcdefABCDEF'
OCTAL_CHAR = '01234567'

ERRORS = {
    'INVALID_HEX': "无效的十六进制数",
    'INVALID_OCTAL_DIGIT': "无效的八进制数",
    'UNEXPECTED_CHAR': "无效的字符常量",    
    'UNTERMINATED_STRING': "未结束的字符串常量 '{}' ",
    'INVALID_FLOAT_EXPONENT': "无效的浮点数",
    'INVALID_IDENTIFIER': '无效的标识符',
}

TOKEN = namedtuple('Token', ['type', 'attribute'])

TYPES = {}
for _ in KEYWORDS.values():
    TYPES[_] = 'KEYWORD'
for _ in OP.values():
    TYPES[_] = 'OPERATOR'
for _ in DL.values():
    TYPES[_] = 'DELIMITER'
TYPES[ID], TYPES[CONST_DECIMAL], TYPES[CONST_OCTAL], TYPES[CONST_HEX], TYPES[CONST_FLOAT], TYPES[CONST_CHAR], TYPES[STRING_], TYPES[EOF] \
    = 'IDENTIFIER', 'CONST_DECIMAL', 'CONST_OCTAL', 'CONST_HEX', 'CONST_FLOAT', 'CONST_CHAR', 'STRING_LITERAL', 'EOF'

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
        self.pos = 0
        self.line = 1
        self.col = 1
        self.table = SymbolTable()
        self.char = self.text[self.pos] if self.text else None

        # 按符号长度进行降序
        # 使得长的优先匹配
        t_ = {**OP, **DL}
        self.symbols = sorted(t_.items(), key=lambda x: len(x[0]), reverse=True)

    def error(self, error, *args):
        m = ERRORS.get(error, "未知错误").format(*args)
        raise Exception(f'{m} at line {self.line}')

    def next(self):
        if self.char == '\n':
            self.line += 1
            self.col = 0
        self.pos += 1
        self.col += 1
        self.char = self.text[self.pos] if self.pos < len(self.text) else None

    def skip(self):
        while self.char is not None and self.char.isspace():
            self.next()

    # KEYWORDS or ID
    def _id(self):
        # 实际用不到这两行
        if not (self.char and (self.char.isalpha() or self.char == '_')):
            self.error('INVALID_IDENTIFIER')

        tmp = ''
        while self.char is not None and (self.char.isalnum() or self.char == '_'):
            tmp += self.char; self.next()

        type_ = KEYWORDS.get(tmp, ID)

        if type_ == ID:
            self.table.add(tmp)

        return TOKEN(type_, tmp)

    def _num(self):
        tmp = ''
        flag = False

        if self.char == '0':
            tmp += self.char
            self.next()

            # 16
            if self.char in 'xX':
                tmp += self.char; self.next()

                _ = self.pos
                while self.char is not None and self.char in HEX_CHAR:
                    tmp += self.char; self.next()
                if _ == self.pos or (self.char is not None and self.char.isalpha()):
                    self.error('INVALID_HEX')
                return TOKEN(CONST_HEX, tmp)

            # 8
            if self.char is not None and self.char.isdigit():
                while self.char is not None and self.char in OCTAL_CHAR:
                    tmp += self.char; self.next()

                if self.char is not None and self.char.isdigit() or self.char.isalpha():
                    self.error('INVALID_OCTAL_DIGIT')

                return TOKEN(CONST_OCTAL, tmp)

            # float
            if self.char == '.':
                tmp += self.char; self.next()
                while self.char is not None and self.char.isdigit():
                    tmp += self.char; self.next()
                if self.char in 'eE':
                    tmp += self.char; self.next()
                    if self.char in '+-':
                        tmp += self.char; self.next()
                    if not (self.char and self.char.isdigit()):
                        self.error('INVALID_FLOAT_EXPONENT')
                    while self.char is not None and self.char.isdigit():
                        tmp += self.char; self.next()
                return TOKEN(CONST_FLOAT, tmp)

            return TOKEN(CONST_DECIMAL, tmp)

        else:
            flag = False
            while self.char is not None and self.char.isdigit():
                tmp += self.char; self.next()
            if self.char == '.':
                flag = True
                tmp += self.char; self.next()
                while self.char is not None and self.char.isdigit():
                    tmp += self.char; self.next()
            if self.char in 'eE':
                flag = True
                tmp += self.char; self.next()
                if self.char in '+-':
                    tmp += self.char; self.next()
                if not (self.char and self.char.isdigit()):
                    self.error('INVALID_FLOAT_EXPONENT')
                while self.char is not None and self.char.isdigit():
                    tmp += self.char; self.next()
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                self.error('INVALID_IDENTIFIER')
            if flag:
                return TOKEN(CONST_FLOAT, tmp)
            else:
                return TOKEN(CONST_DECIMAL, tmp)

        # if self.char == '0':
        #     _ = self.text[self.pos + 1] if self.pos + 1 < len(self.text) else None
        #
        #     if _ in 'xX':
        #         tmp += self.char; self.next()
        #         tmp += self.char; self.next()
        #
        #         s = self.pos
        #         while self.char is not None and self.char in HEX_CHAR:
        #             tmp += self.char; self.next()
        #         if self.pos == s:
        #             self.error('INVALID_HEX')
        #         return TOKEN(CONST_HEX, tmp)
        #     elif _ is not None and _ in OCTAL_CHAR:
        #         tmp += self.char; self.next()
        #         while self.char is not None and self.char in OCTAL_CHAR:
        #             tmp += self.char; self.next()
        #         if self.char is not None and self.char.isdigit():
        #             self.error('INVALID_OCTAL_DIGIT', self.char)
        #         return TOKEN(CONST_OCTAL, tmp)
        #
        # while self.char is not None and self.char.isdigit():
        #     tmp += self.char; self.next()
        #
        # if self.char == '.':
        #     flag = True
        #     tmp += self.char; self.next()
        #     while self.char is not None and self.char.isdigit():
        #         tmp += self.char; self.next()
        #
        # if self.char in 'eE':
        #     flag = True
        #     tmp += self.char; self.next()
        #     if self.char in '-+':
        #         tmp += self.char; self.next()
        #     if not (self.char and self.char.isdigit()):
        #         self.error('INVALID_FLOAT_EXPONENT')
        #     while self.char is not None and self.char.isdigit():
        #         tmp += self.char; self.next()
        #
        # if self.char is not None and (self.char.isalpha() or self.char == '_'):
        #     self.error('INVALID_IDENTIFIER')
        #
        # if flag:
        #     return TOKEN(CONST_FLOAT, tmp)
        # else:
        #     return TOKEN(CONST_DECIMAL, tmp)


    def _str(self):
        tmp = ''
        self.next()
        while self.char is not None and self.char != '"':
            if self.char == '\\':
                tmp += self.char; self.next()

                if self.char is None:
                    self.error('UNTERMINATED_STRING', self.char)
                
                tmp += self.char; self.next()
            else:
                tmp += self.char; self.next()

        self.next()
        return TOKEN(STRING_, tmp)

    def _char(self):
        tmp = ''
        self.next()

        if self.char is None:
            self.error('UNTERMINATED_CHAR', self.char)
        
        if self.char == '\\':
            tmp += self.char; self.next()

            if self.char is None:
                self.error('UNTERMINATED_CHAR', self.char)
            
            tmp += self.char; self.next()
        else:
            tmp += self.char; self.next()

        if self.char != "'":
            self.error('UNEXPECTED_CHAR')

        self.next()
        return TOKEN(CONST_CHAR, tmp)

    def next_token(self):
        while self.char is not None:
            self.skip()
            _ = self.char
            if _ is None:
                continue
            if _.isalpha() or _ == '_':
                return self._id()
            if _.isdigit():
                return self._num()
            if _ == '"':
                return self._str()
            if _ == "'":
                return self._char()

            for s, t in self.symbols:
                if self.text.startswith(s, self.pos):
                    for _ in range(len(s)): self.next()
                    return TOKEN(t, s)
            self.error('UNEXPECTED_CHAR')
        return TOKEN(EOF, 'EOF')

    def tokenize(self):
        ans = []
        _ = self.next_token()
        while _.type != EOF:
            ans.append(_)
            _ = self.next_token()
        ans.append(_)
        return ans


if __name__ == '__main__':
    try:
        with open(file, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        print(e)
        sys.exit(1)

    code_ = process(code)
    # print(code_)

    lexer = Lexer(code_)
    tokens = lexer.tokenize()
    for token in tokens:
        _ = TYPES.get(token.type, 'UNKNOWN')

        if token.type == STRING_:
            attr_ = f'"{token.attribute}"'
        elif token.type == CONST_CHAR:
            attr_ = f"'{token.attribute}'"
        else:
            attr_ = token.attribute

        print(f"( {_:<16} <{token.type}>: {attr_} )")

    print(lexer.table)

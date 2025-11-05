from collections import namedtuple

TOKEN = namedtuple('Token', ['type', 'attribute', 'line', 'is_error'])

def make_token(type_, attr, line, is_error=False):
    return TOKEN(type_, attr, line, is_error)

# 关键字映射表
KEYWORDS = {
    'auto': 1, 'break': 2, 'case': 3, 'char': 4, 'const': 5, 'continue': 6, 'default': 7, 'do': 8,
    'double': 9, 'else': 10, 'enum': 11, 'extern': 12, 'float': 13, 'for': 14, 'goto': 15, 'if': 16,
    'int': 17, 'long': 18, 'register': 19, 'return': 20, 'short': 21, 'signed': 22, 'sizeof': 23, 'static': 24,
    'struct': 25, 'switch': 26, 'typedef': 27, 'union': 28, 'unsigned': 29, 'void': 30, 'volatile': 31, 'while': 32,
    'int36': 90
}

# 操作符映射表
OP = {
    '=': 33, '+=': 34, '-=': 35, '*=': 36, '/=': 37, '%=': 38, '&=': 39, '|=': 40, '^=': 41, '<<=': 42, '>>=': 43,
    '++': 44, '--': 45, '+': 46, '-': 47, '*': 48, '/': 49, '%': 50, '~': 51, '&': 52, '|': 53, '^': 54, '<<': 55,
    '>>': 56, '!': 57, '&&': 58, '||': 59, '==': 60, '!=': 61, '<': 62, '>': 63, '<=': 64, '>=': 65, '->': 66,
    '.': 67, '?': 68, ':': 69
}

# 界符映射表
DL = {
    '(': 70, ')': 71, '[': 72, ']': 73, '{': 74, '}': 75, ',': 76, ';': 77,
}

# 其他 Token 类型
ID, CONST_DECIMAL, CONST_OCTAL, CONST_HEX, CONST_FLOAT, CONST_CHAR, STRING_, PREPROCESSOR = 82, 83, 84, 85, 86, 87, 88, 89

EOF = -1

# 字符集定义
HEX_CHAR = '0123456789abcdefABCDEF'
OCTAL_CHAR = '01234567'
BASE36_CHAR = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

# 错误信息映射表
ERRORS = {
    'INVALID_HEX': "无效的十六进制数",
    'INVALID_OCTAL_DIGIT': "无效的八进制数",
    'UNEXPECTED_CHAR': "无效的字符常量",
    'UNTERMINATED_STRING': "未结束的字符串常量",
    'INVALID_FLOAT_EXPONENT': "无效的浮点数",
    'INVALID_IDENTIFIER': '无效的标识符',
    'UNTERMINATED_CHAR': "未结束的字符常量",
    'EMPTY_CHAR': "空字符常量",
    'MULTI_CHAR': "字符常量包含多个字符",
    'INVALID_ESCAPE': "无效的转义序列",
    'STRING_NEWLINE': "字符串中包含未转义的换行符",
    'UNTERMINATED_COMMENT': "未闭合的块注释",
    'IDENTIFIER_TOO_LONG': "标识符长度超过限制",
    'UNKNOWN_CHAR': "未知字符",
}

# Token 类型名称映射表
TYPES = {}
for _ in KEYWORDS.values():
    TYPES[_] = 'KEYWORD'
for _ in OP.values():
    TYPES[_] = 'OPERATOR'
for _ in DL.values():
    TYPES[_] = 'DELIMITER'
TYPES[ID], TYPES[CONST_DECIMAL], TYPES[CONST_OCTAL], TYPES[CONST_HEX], TYPES[CONST_FLOAT], TYPES[CONST_CHAR], TYPES[
    STRING_], TYPES[PREPROCESSOR], TYPES[EOF] \
    = 'IDENTIFIER', 'CONST_DECIMAL', 'CONST_OCTAL', 'CONST_HEX', 'CONST_FLOAT', 'CONST_CHAR', 'STRING_LITERAL', 'PREPROCESSOR', 'EOF'

# 3. 符号表类
class SymbolTable:
    def __init__(self):
        self.symbols = {}

    def add(self, name):
        if name not in self.symbols:
            self.symbols[name] = {'name': name}
        return self.symbols[name]

    def __str__(self):
        if not self.symbols:
            return "符号表为空"

        result = ["\n" + "=" * 50, "标识符", "=" * 50, f"{'序号':<6} {'标识符':<20}", "-" * 50]

        for idx, (name, info) in enumerate(self.symbols.items(), 1):
            result.append(f"{idx:<6} {name:<20}")

        return "\n".join(result)


class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1
        self.table = SymbolTable()
        self.char = self.text[self.pos] if self.text else None
        self.errors = []

        # 合并操作符和界符，按长度降序排列（优先匹配长符号）
        t_ = {**OP, **DL}
        self.symbols = sorted(t_.items(), key=lambda x: len(x[0]), reverse=True)

    def error(self, error, content='', line=None, *args):
        num = line if line is not None else self.line
        m = ERRORS.get(error, "未知错误").format(*args)
        if content:
            _ = f'错误: {m}, 内容: "{content}" at line {num}'
        else:
            _ = f'错误: {m} at line {num}'
        self.errors.append(_)
        return _

    def next(self):
        """移动到下一个字符"""
        if self.char == '\n':
            self.line += 1
            self.col = 0
        self.pos += 1
        self.col += 1
        self.char = self.text[self.pos] if self.pos < len(self.text) else None

    def skip(self):
        while self.char is not None:
            if self.char.isspace():
                self.next()
                continue

            # 处理 // 单行注释
            if self.char == '/' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '/':
                while self.char is not None and self.char != '\n':
                    self.next()
                continue

            # 处理 /* */ 多行注释
            if self.char == '/' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '*':
                l = self.line
                self.next()  # skip /
                self.next()  # skip *

                while self.char is not None and not (
                        self.char == '*' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '/'):
                    self.next()

                if self.char is None:
                    self.error('UNTERMINATED_COMMENT', '', line=l)
                    break
                else:
                    self.next()  # skip *
                    self.next()  # skip /
                continue

            break

    def _id(self):
        """识别关键字或标识符"""
        l = self.line
        if not (self.char and (self.char.isalpha() or self.char == '_')):
            self.error('INVALID_IDENTIFIER', '', line=l)
        tmp = ''
        while self.char is not None and (self.char.isalnum() or self.char == '_'):
            tmp += self.char
            self.next()
        type_ = KEYWORDS.get(tmp, ID)
        if type_ == ID:
            self.table.add(tmp)
        return make_token(type_, tmp, line=l)

    def _float(self, tmp):
        """处理浮点数的小数部分和指数部分"""
        flag = False
        error_flag = False
        
        # 处理小数点
        if self.char == '.':
            flag = True
            tmp += self.char
            self.next()
            while self.char is not None and self.char.isdigit():
                tmp += self.char
                self.next()

        # 处理指数部分
        if self.char in 'eE':
            flag = True
            tmp += self.char
            self.next()
            if self.char in '+-':
                tmp += self.char
                self.next()
            if not (self.char and self.char.isdigit()):
                self.error('INVALID_FLOAT_EXPONENT', tmp)
                error_flag = True
                return tmp, flag, error_flag
            while self.char is not None and self.char.isdigit():
                tmp += self.char
                self.next()

        return tmp, flag, error_flag

    def _num(self):
        """识别数字常量（十进制、八进制、十六进制、浮点数）"""
        tmp = ''
        is_error = False
        l = self.line

        # 处理以 . 开头的浮点数
        if self.char == '.':
            tmp += self.char
            self.next()
            while self.char is not None and self.char.isdigit():
                tmp += self.char
                self.next()
            if self.char is not None and self.char in 'eE':
                tmp += self.char
                self.next()
                if self.char in '+-':
                    tmp += self.char
                    self.next()
                if not (self.char and self.char.isdigit()):
                    self.error('INVALID_FLOAT_EXPONENT', tmp, line=l)
                    is_error = True
                while self.char is not None and self.char.isdigit():
                    tmp += self.char
                    self.next()
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char
                    self.next()
                self.error('INVALID_IDENTIFIER', tmp, line=l)
                is_error = True
            return make_token(CONST_FLOAT, tmp, line=l, is_error=is_error)

        # 处理以 0 开头的数字（可能是八进制或十六进制）
        flag_octal = False
        if self.char == '0':
            flag_octal = True
            tmp += self.char
            self.next()
            
            # 十六进制
            if self.char in 'xX':
                tmp += self.char
                self.next()
                _ = self.pos
                while self.char is not None and self.char in HEX_CHAR:
                    tmp += self.char
                    self.next()
                if _ == self.pos or (self.char is not None and (self.char.isalnum() or self.char == '_')):
                    while self.char is not None and (self.char.isalnum() or self.char == '_'):
                        tmp += self.char
                        self.next()
                    self.error('INVALID_HEX', tmp, line=l)
                    is_error = True
                return make_token(CONST_HEX, tmp, line=l, is_error=is_error)

        # 继续读取数字
        while self.char is not None and self.char.isdigit():
            tmp += self.char
            self.next()

        # 检查是否是浮点数
        if self.char == '.' or self.char in 'eE':
            flag_octal = False
            tmp, flag, is_error_float = self._float(tmp)
            is_error = is_error or is_error_float
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char
                    self.next()
                self.error('INVALID_IDENTIFIER', tmp, line=l)
                is_error = True
            return make_token(CONST_FLOAT, tmp, line=l, is_error=is_error)

        # 检查是否有非法字符跟随
        if self.char is not None and (self.char.isalpha() or self.char == '_'):
            while self.char is not None and (self.char.isalnum() or self.char == '_'):
                tmp += self.char
                self.next()
            self.error('INVALID_IDENTIFIER', tmp, line=l)
            is_error = True

        # 检查八进制数的合法性
        has_invalid_octal_digit = False
        if flag_octal:
            for char in tmp[1:]:
                if char not in OCTAL_CHAR:
                    has_invalid_octal_digit = True
                    break

        if has_invalid_octal_digit:
            self.error('INVALID_OCTAL_DIGIT', tmp, line=l)
            is_error = True
            return make_token(CONST_OCTAL, tmp, line=l, is_error=is_error)

        if flag_octal and len(tmp) > 0:
            return make_token(CONST_OCTAL, tmp, line=l, is_error=is_error)

        return make_token(CONST_DECIMAL, tmp, line=l, is_error=is_error)

    def _str(self):
        """识别字符串常量"""
        tmp = ''
        is_error = False
        l = self.line
        self.next()  # skip opening "
        
        while self.char is not None and self.char != '"' and self.char != '\n':
            if self.char == '\\':
                tmp += self.char
                self.next()
                if self.char is None:
                    self.error('UNTERMINATED_STRING', tmp, line=l)
                    is_error = True
                    break
                tmp += self.char
                self.next()
            else:
                tmp += self.char
                self.next()
                
        if self.char == '\n':
            self.error('STRING_NEWLINE', tmp, line=l)
            is_error = True
        elif self.char == '"':
            self.next()
        else:
            self.error('UNTERMINATED_STRING', tmp, line=l)
            is_error = True
        return make_token(STRING_, tmp, line=l, is_error=is_error)

    def _char(self):
        """识别字符常量"""
        tmp = ''
        is_error = False
        l = self.line
        self.next()  # skip opening '

        # 空字符常量
        if self.char == "'":
            self.error('EMPTY_CHAR', '', line=l)
            self.next()
            return make_token(CONST_CHAR, tmp, line=l, is_error=True)

        if self.char is None:
            self.error('UNTERMINATED_CHAR', tmp, line=l)
            return make_token(CONST_CHAR, tmp, line=l, is_error=True)

        # 处理转义字符
        if self.char == '\\':
            tmp += self.char
            self.next()
            if self.char is None:
                self.error('UNTERMINATED_CHAR', tmp, line=l)
                return make_token(CONST_CHAR, tmp, line=l, is_error=True)
            tmp += self.char
            self.next()
        else:
            tmp += self.char
            self.next()

        # 检查多字符常量
        if self.char != "'" and self.char is not None and self.char != '\n':
            extra_chars = ''
            while self.char is not None and self.char != "'" and self.char != '\n':
                extra_chars += self.char
                self.next()
            self.error('MULTI_CHAR', tmp + extra_chars, line=l)
            is_error = True
            tmp = tmp + extra_chars

        if self.char != "'":
            self.error('UNTERMINATED_CHAR', tmp, line=l)
            is_error = True
        else:
            self.next()

        return make_token(CONST_CHAR, tmp, line=l, is_error=is_error)

    def _preprocessor(self):
        """识别预处理指令"""
        l = self.line
        tmp = ''
        while self.char is not None:
            # 处理续行符
            if self.char == '\\':
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '\n':
                    self.next()  # skip \
                    self.next()  # skip \n
                    tmp += ' '
                    continue

            if self.char == '\n':
                break

            tmp += self.char
            self.next()
        return make_token(PREPROCESSOR, tmp.strip(), line=l)

    def next_token(self):
        while self.char is not None:
            self.skip()

            _ = self.char
            if _ is None:
                continue

            l = self.line

            if _ == '#':
                return self._preprocessor()
            if _.isalpha() or _ == '_':
                return self._id()
            if _.isdigit():
                return self._num()
            if _ == '.' and self.pos + 1 < len(self.text) and self.text[self.pos + 1].isdigit():
                return self._num()
            if _ == '"':
                return self._str()
            if _ == "'":
                return self._char()

            # 匹配操作符和界符
            for s, t in self.symbols:
                if self.text.startswith(s, self.pos):
                    for _ in range(len(s)):
                        self.next()
                    return make_token(t, s, line=l)

            # 未知字符
            unknown_char = self.char
            self.error('UNKNOWN_CHAR', unknown_char, line=l)
            self.next()

        return make_token(EOF, 'EOF', line=self.line)

    def tokenize(self):
        ans = []
        _ = self.next_token()
        while _.type != EOF:
            ans.append(_)
            _ = self.next_token()
        ans.append(_)
        return ans

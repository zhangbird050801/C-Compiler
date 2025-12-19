from collections import namedtuple
from constants import (KEYWORDS, OP, DL, ID, CONST_DECIMAL, CONST_OCTAL, CONST_HEX, CONST_FLOAT, CONST_CHAR, STRING_, PREPROCESSOR,  EOF, HEX_CHAR, OCTAL_CHAR, ERRORS, TYPES)

TOKEN = namedtuple('Token', ['type', 'attribute', 'line', 'error'])

def make_token(type_, attr, line, err=False):
    return TOKEN(type_, attr, line, err)

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

        result = ["\n" + "=" * 50, "标识符表", "=" * 50, f"{'序号':<8} {'标识符':<20}", "-" * 50]

        for idx, (name, info) in enumerate(self.symbols.items(), 1):
            result.append(f"{idx:<8} {name:<20}")

        result.append("=" * 50)
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

    def get_next(self):
        pos = self.pos + 1
        return self.text[pos] if pos < len(self.text) else None

    def read_exp(self, tmp): 
        tmp += self.char; self.next()
        if self.char is not None and self.char in '+-':
            tmp += self.char; self.next()
        # +- 后非数字或空
        if not (self.char and self.char.isdigit()):
            return tmp, True
        while self.char is not None and self.char.isdigit(): # 读取指数
            tmp += self.char; self.next()
        return tmp, False

    def skip(self): # 跳过注释
        while self.char is not None:
            if self.char.isspace():
                self.next()
                continue

            # 处理 // 单行注释
            if self.char == '/' and self.get_next() == '/':
                while self.char is not None and self.char != '\n':
                    self.next()
                continue

            # 处理 /* */ 多行注释
            if self.char == '/' and self.get_next() == '*':
                l = self.line
                self.next()  # skip /
                self.next()  # skip *

                while self.char is not None and not (self.char == '*' and self.get_next() == '/'): # */
                    self.next()

                if self.char is None: 
                    self.error('UNTERMINATED_COMMENT', '', line=l) # 未闭合
                    break
                else:
                    self.next()  # skip *
                    self.next()  # skip /
                continue
            break

    def _id(self): # 识别关键词、标识符或36进制数
        l = self.line
        if not (self.char and (self.char.isalpha() or self.char == '_')): # 不以字母或下划线开头
            self.error('INVALID_IDENTIFIER', '', line=l)
        _ = ''
        while self.char is not None and (self.char.isalnum() or self.char == '_'):
            _ += self.char; self.next()
        
        # 是否是关键字
        type_ = KEYWORDS.get(_, None)
        if type_ is not None:
            return make_token(type_, _, line=l)

        # 否则是标识符
        self.table.add(_)
        return make_token(ID, _, line=l)

    def _float(self, tmp): # 处理浮点数的小数部分和指数部分
        flag = False
        err = False
        
        if self.char == '.':
            flag = True
            tmp += self.char; self.next()
            while self.char is not None and self.char.isdigit():
                tmp += self.char; self.next()

        if self.char is not None and self.char in 'eE':
            flag = True
            tmp, err = self.read_exp(tmp) # 获取指数部分
            if err:
                self.error('INVALID_FLOAT_EXPONENT', tmp)

        return tmp, flag, err

    def _num(self): # 数字常量
        tmp = ''
        err = False
        l = self.line

        # 处理以 . 开头的浮点数
        if self.char == '.':
            tmp += self.char; self.next()
            while self.char is not None and self.char.isdigit():
                tmp += self.char; self.next()
            if self.char is not None and self.char in 'eE': # 遇到 eE -> 指数
                tmp, err = self.read_exp(tmp)
                if err:
                    self.error('INVALID_FLOAT_EXPONENT', tmp, line=l)
            if self.char is not None and self.char in 'fFlL':
                tmp += self.char; self.next()
            if self.char is not None and (self.char.isalnum() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char; self.next()
                self.error('INVALID_IDENTIFIER', tmp, line=l); err = True
            return make_token(CONST_FLOAT, tmp, line=l, err=err)


        # 处理以 0 开头的数字（八进制/十六进制/0）
        if self.char == '0':
            tmp += self.char; self.next()
            # 检查是否是 0.xxx 形式的浮点数
            if self.char == '.':
                tmp, flag, err_float = self._float(tmp)
                err = err or err_float
                if self.char is not None and self.char in 'fFlL':
                    tmp += self.char; self.next()
                if self.char is not None and (self.char.isalnum() or self.char == '_'):
                    while self.char is not None and (self.char.isalnum() or self.char == '_'):
                        tmp += self.char; self.next()
                    self.error('INVALID_IDENTIFIER', tmp, line=l); err = True
                return make_token(CONST_FLOAT, tmp, line=l, err=err)
            # 十六进制
            if self.char is not None and self.char in 'xX':
                tmp += self.char; self.next()
                _ = self.pos
                while self.char is not None and self.char in HEX_CHAR:
                    tmp += self.char; self.next()
                # 跟随非法字符
                if self.char is not None and (self.char.isalnum() or self.char == '_'):
                    while self.char is not None and (self.char.isalnum() or self.char == '_'):
                        tmp += self.char; self.next()
                    self.error('INVALID_HEX', tmp, line=l); err = True
                elif _ == self.pos:
                    # 0x 后面没有任何十六进制数字
                    self.error('INVALID_HEX', tmp, line=l); err = True
                return make_token(CONST_HEX, tmp, line=l, err=err)
            # 八进制
            _ = False
            while self.char is not None and self.char.isdigit():
                if self.char not in OCTAL_CHAR:
                    _ = True
                tmp += self.char; self.next()
            if self.char is not None and (self.char.isalnum() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char; self.next()
                self.error('INVALID_OCTAL_DIGIT', tmp, line=l); err = True
            elif _:
                self.error('INVALID_OCTAL_DIGIT', tmp, line=l); err = True
            return make_token(CONST_OCTAL, tmp, line=l, err=err)

        # 十进制
        while self.char is not None and self.char.isdigit():
            tmp += self.char; self.next()

        # 浮点数 12.xx | 12e+3
        if self.char is not None and (self.char == '.' or self.char in 'eE'):
            tmp, flag, err_float = self._float(tmp)
            err = err or err_float
            if self.char is not None and self.char in 'fFlL':
                tmp += self.char; self.next()
            if self.char is not None and (self.char.isalnum() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char; self.next()
                self.error('INVALID_IDENTIFIER', tmp, line=l); err = True
            return make_token(CONST_FLOAT, tmp, line=l, err=err)

        # 检查十进制数后是否跟着字母或下划线
        if self.char is not None and (self.char.isalpha() or self.char == '_'):
            while self.char is not None and (self.char.isalnum() or self.char == '_'):
                tmp += self.char; self.next()
            self.error('INVALID_IDENTIFIER', tmp, line=l); err = True

        return make_token(CONST_DECIMAL, tmp, line=l, err=err)

    def _str(self):
        """识别字符串常量"""
        tmp = ''
        err = False
        l = self.line
        self.next()  # skip opening "
        
        while self.char is not None and self.char != '"' and self.char != '\n':
            if self.char == '\\':
                tmp += self.char; self.next()
                if self.char is None:
                    self.error('UNTERMINATED_STRING', tmp, line=l); err = True
                    break
                if self.char == '\n':
                    self.next()
                    continue
                tmp += self.char; self.next()
            else:
                tmp += self.char; self.next()
                
        if self.char == '\n':
            # 遇到换行符意味着字符串未闭合
            self.error('UNTERMINATED_STRING', tmp, line=l); err = True
        elif self.char == '"':
            self.next()
        else:
            self.error('UNTERMINATED_STRING', tmp, line=l); err = True
        return make_token(STRING_, tmp, line=l, err=err)

    def _char(self):
        """识别字符常量"""
        tmp = ''
        err = False
        l = self.line
        self.next()  # skip opening '

        # 空字符常量
        if self.char == "'":
            self.error('EMPTY_CHAR', '', line=l)
            self.next()
            return make_token(CONST_CHAR, tmp, line=l, err=True)

        if self.char is None:
            self.error('UNTERMINATED_CHAR', tmp, line=l)
            return make_token(CONST_CHAR, tmp, line=l, err=True)

        # 处理转义字符
        if self.char == '\\':
            tmp += self.char; self.next()
            if self.char is None:
                self.error('UNTERMINATED_CHAR', tmp, line=l)
                return make_token(CONST_CHAR, tmp, line=l, err=True)
            tmp += self.char; self.next()
        else:
            tmp += self.char; self.next()

        # 检查多字符常量
        if self.char != "'" and self.char is not None and self.char != '\n':
            extra_chars = ''
            while self.char is not None and self.char != "'" and self.char != '\n':
                extra_chars += self.char
                self.next()
            self.error('MULTI_CHAR', tmp + extra_chars, line=l); err = True
            tmp = tmp + extra_chars

        if self.char != "'":
            self.error('UNTERMINATED_CHAR', tmp, line=l); err = True
        else:
            self.next()

        return make_token(CONST_CHAR, tmp, line=l, err=err)

    def _preprocessor(self): 
        l = self.line
        tmp = ''
        while self.char is not None:
            if self.char == '\\' and self.get_next() == '\n':
                self.next()  # skip \
                self.next()  # skip \n
                tmp += ' '
                continue

            if self.char == '\n':
                break

            tmp += self.char; self.next()
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
            if _ == '.' and self.get_next() and self.get_next().isdigit():
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

            _ = self.char
            self.error('UNKNOWN_CHAR', _, line=l)
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

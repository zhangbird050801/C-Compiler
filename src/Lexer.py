from collections import namedtuple

TOKEN = namedtuple('Token', ['type', 'attribute', 'line', 'is_error'])

def make_token(type_, attr, line, is_error=False):
    """创建一个 Token"""
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

CONST_BASE36 = 91
EOF = -1

# 字符集定义
HEX_CHAR = '0123456789abcdefABCDEF'
OCTAL_CHAR = '01234567'
BASE36_CHAR = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

# 错误信息映射表
ERRORS = {
    'INVALID_HEX': "无效的十六进制数",
    'INVALID_OCTAL_DIGIT': "无效的八进制数",
    'INVALID_BASE36': "无效的36进制数",
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

TYPES[CONST_BASE36] = 'CONST_BASE36'

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

        result = ["\n" + "=" * 50]
        result.append("标识符")
        result.append("=" * 50)
        result.append(f"{'序号':<6} {'标识符':<20}")
        result.append("-" * 50)

        for idx, (name, info) in enumerate(self.symbols.items(), 1):
            result.append(f"{idx:<6} {name:<20}")

        result.append("=" * 50)
        result.append(f"总计: {len(self.symbols)} 个标识符")
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

        # 添加状态跟踪变量
        self.last_token = None
        self.expected_number_base = 10  # 默认十进制
        self.expect_base36_number = False  # 是否期望36进制常量

    def error(self, error, content='', line=None, *args):
        """记录错误信息"""
        report_line = line if line is not None else self.line
        m = ERRORS.get(error, "未知错误").format(*args)
        if content:
            error_msg = f'错误: {m}, 内容: "{content}" at line {report_line}'
        else:
            error_msg = f'错误: {m} at line {report_line}'
        self.errors.append(error_msg)
        return error_msg

    def next(self):
        """移动到下一个字符"""
        if self.char == '\n':
            self.line += 1
            self.col = 0
        self.pos += 1
        self.col += 1
        self.char = self.text[self.pos] if self.pos < len(self.text) else None

    def skip_whitespace_and_comments(self):
        """跳过所有空白字符、单行注释和多行注释"""
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
                start_line = self.line
                self.next()  # skip /
                self.next()  # skip *

                while self.char is not None and not (
                        self.char == '*' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '/'):
                    self.next()

                if self.char is None:
                    self.error('UNTERMINATED_COMMENT', '', line=start_line)
                    break
                else:
                    self.next()  # skip *
                    self.next()  # skip /
                continue

            # 既不是空白也不是注释，停止
            break

    def _id(self):
        """识别关键字或标识符"""
        start_line = self.line
        if not (self.char and (self.char.isalpha() or self.char == '_')):
            self.error('INVALID_IDENTIFIER', '', line=start_line)
        tmp = ''
        while self.char is not None and (self.char.isalnum() or self.char == '_'):
            tmp += self.char
            self.next()

        # 检查是否为关键字
        type_ = KEYWORDS.get(tmp, ID)

        # 如果不是关键字，且明确期望36进制常量，检查是否为36进制常量
        if (type_ == ID and hasattr(self, 'expect_base36_number') and
            self.expect_base36_number and self._is_valid_base36(tmp)):
            return make_token(CONST_BASE36, tmp, line=start_line)

        # 普通标识符处理
        if type_ == ID:
            self.table.add(tmp)
        return make_token(type_, tmp, line=start_line)

    def _is_valid_base36(self, s):
        """检查字符串是否是有效的36进制数"""
        if not s:  # 空字符串
            return False
        # 检查所有字符是否都在BASE36_CHAR中
        for char in s:
            if char not in BASE36_CHAR:
                return False
        return True

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
        """识别数字常量（十进制、八进制、十六进制、浮点数、36进制）"""
        tmp = ''
        is_error = False
        start_line = self.line

        # 检查是否应该解析为36进制
        if (hasattr(self, 'expected_number_base') and self.expected_number_base == 36 and
            self.char is not None and self.char in BASE36_CHAR):
            tmp = ''
            while self.char is not None and self.char in BASE36_CHAR:
                tmp += self.char
                self.next()

            # 检查是否有非法字符跟随
            if self.char is not None and (self.char.isalnum() or self.char == '_'):
                # 消耗掉非法字符
                invalid_chars = ''
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    invalid_chars += self.char
                    self.next()
                self.error('INVALID_BASE36', tmp + invalid_chars, line=start_line)
                is_error = True

            return make_token(CONST_BASE36, tmp, line=start_line, is_error=is_error)

        # 处理以 . 开头的浮点数
        if self.char == '.':
            tmp += self.char
            self.next()
            while self.char is not None and self.char.isdigit():
                tmp += self.char
                self.next()
            if self.char in 'eE':
                tmp += self.char
                self.next()
                if self.char in '+-':
                    tmp += self.char
                    self.next()
                if not (self.char and self.char.isdigit()):
                    self.error('INVALID_FLOAT_EXPONENT', tmp, line=start_line)
                    is_error = True
                while self.char is not None and self.char.isdigit():
                    tmp += self.char
                    self.next()
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char
                    self.next()
                self.error('INVALID_IDENTIFIER', tmp, line=start_line)
                is_error = True
            return make_token(CONST_FLOAT, tmp, line=start_line, is_error=is_error)

        # 处理以 0 开头的数字（可能是八进制或十六进制）
        is_octal_candidate = False
        if self.char == '0':
            is_octal_candidate = True
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
                    self.error('INVALID_HEX', tmp, line=start_line)
                    is_error = True
                return make_token(CONST_HEX, tmp, line=start_line, is_error=is_error)

        # 继续读取数字
        while self.char is not None and self.char.isdigit():
            tmp += self.char
            self.next()

        # 检查是否是浮点数
        if self.char == '.' or self.char in 'eE':
            is_octal_candidate = False
            tmp, flag, is_error_float = self._float(tmp)
            is_error = is_error or is_error_float
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char
                    self.next()
                self.error('INVALID_IDENTIFIER', tmp, line=start_line)
                is_error = True
            return make_token(CONST_FLOAT, tmp, line=start_line, is_error=is_error)

        # 检查是否有非法字符跟随
        if self.char is not None and (self.char.isalpha() or self.char == '_'):
            while self.char is not None and (self.char.isalnum() or self.char == '_'):
                tmp += self.char
                self.next()
            self.error('INVALID_IDENTIFIER', tmp, line=start_line)
            is_error = True

        # 检查八进制数的合法性
        has_invalid_octal_digit = False
        if is_octal_candidate:
            for char in tmp[1:]:
                if char not in OCTAL_CHAR:
                    has_invalid_octal_digit = True
                    break

        if has_invalid_octal_digit:
            self.error('INVALID_OCTAL_DIGIT', tmp, line=start_line)
            is_error = True
            return make_token(CONST_OCTAL, tmp, line=start_line, is_error=is_error)

        if is_octal_candidate and len(tmp) > 0:
            return make_token(CONST_OCTAL, tmp, line=start_line, is_error=is_error)

        return make_token(CONST_DECIMAL, tmp, line=start_line, is_error=is_error)

    def _str(self):
        """识别字符串常量"""
        tmp = ''
        is_error = False
        start_line = self.line
        self.next()  # skip opening "
        
        while self.char is not None and self.char != '"' and self.char != '\n':
            if self.char == '\\':
                tmp += self.char
                self.next()
                if self.char is None:
                    self.error('UNTERMINATED_STRING', tmp, line=start_line)
                    is_error = True
                    break
                tmp += self.char
                self.next()
            else:
                tmp += self.char
                self.next()
                
        if self.char == '\n':
            self.error('STRING_NEWLINE', tmp, line=start_line)
            is_error = True
        elif self.char == '"':
            self.next()
        else:
            self.error('UNTERMINATED_STRING', tmp, line=start_line)
            is_error = True
        return make_token(STRING_, tmp, line=start_line, is_error=is_error)

    def _char(self):
        """识别字符常量"""
        tmp = ''
        is_error = False
        start_line = self.line
        self.next()  # skip opening '

        # 空字符常量
        if self.char == "'":
            self.error('EMPTY_CHAR', '', line=start_line)
            self.next()
            return make_token(CONST_CHAR, tmp, line=start_line, is_error=True)

        if self.char is None:
            self.error('UNTERMINATED_CHAR', tmp, line=start_line)
            return make_token(CONST_CHAR, tmp, line=start_line, is_error=True)

        # 处理转义字符
        if self.char == '\\':
            tmp += self.char
            self.next()
            if self.char is None:
                self.error('UNTERMINATED_CHAR', tmp, line=start_line)
                return make_token(CONST_CHAR, tmp, line=start_line, is_error=True)
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
            self.error('MULTI_CHAR', tmp + extra_chars, line=start_line)
            is_error = True
            tmp = tmp + extra_chars

        if self.char != "'":
            self.error('UNTERMINATED_CHAR', tmp, line=start_line)
            is_error = True
        else:
            self.next()

        return make_token(CONST_CHAR, tmp, line=start_line, is_error=is_error)

    def _preprocessor(self):
        """识别预处理指令"""
        start_line = self.line
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
        return make_token(PREPROCESSOR, tmp.strip(), line=start_line)

    def next_token(self):
        while self.char is not None:
            self.skip_whitespace_and_comments()

            _ = self.char
            if _ is None:
                continue

            start_line = self.line

            token = None
            if _ == '#':
                token = self._preprocessor()
            elif _.isalpha() or _ == '_':
                token = self._id()
            elif _.isdigit():
                token = self._num()
            elif _ == '.' and self.pos + 1 < len(self.text) and self.text[self.pos + 1].isdigit():
                token = self._num()
            elif _ == '"':
                token = self._str()
            elif _ == "'":
                token = self._char()
            else:
                # 匹配操作符和界符
                for s, t in self.symbols:
                    if self.text.startswith(s, self.pos):
                        for _ in range(len(s)):
                            self.next()
                        token = make_token(t, s, line=start_line)
                        break
                else:
                    # 未知字符
                    unknown_char = self.char
                    self.error('UNKNOWN_CHAR', unknown_char, line=start_line)
                    self.next()
                    continue

            # 更新状态和last_token
            if token:
                self._update_lexer_state(token)
                self.last_token = token
                return token

        return make_token(EOF, 'EOF', line=self.line)

    def _update_lexer_state(self, token):
        """根据当前token更新词法分析器状态"""
        # 遇到int36关键字，设置期望的数字进制为36
        if token.type == KEYWORDS.get('int36'):
            self.expected_number_base = 36
            self.expect_base36_number = False
        # 遇到其他基本类型关键字，重置为十进制
        elif token.type in [KEYWORDS.get(k) for k in ['int', 'char', 'float', 'double', 'long', 'short', 'signed', 'unsigned']]:
            self.expected_number_base = 10
            self.expect_base36_number = False
        # 遇到分号，重置为十进制（声明语句结束）
        elif token.type == DL.get(';'):
            self.expected_number_base = 10
            self.expect_base36_number = False
        # 遇到等号，如果当前是36进制上下文，设置期望36进制常量
        elif token.type == OP.get('='):
            if self.expected_number_base == 36:
                self.expect_base36_number = True
            else:
                self.expect_base36_number = False
        # 遇到逗号，在36进制上下文中继续期望36进制常量（用于声明多个变量时的初始化）
        elif token.type == DL.get(','):
            if self.expected_number_base == 36:
                self.expect_base36_number = False  # 逗号后面是变量名，不是常量
        # 处理完一个token后，如果是数字常量，重置期望标志
        elif token.type in [CONST_BASE36, CONST_DECIMAL, CONST_OCTAL, CONST_HEX, CONST_FLOAT]:
            self.expect_base36_number = False
        # 其他情况保持当前进制但不期望36进制常量
        elif token.type == ID:
            # 标识符（变量名）后不期望36进制常量
            self.expect_base36_number = False

    def tokenize(self):
        ans = []
        _ = self.next_token()
        while _.type != EOF:
            ans.append(_)
            _ = self.next_token()
        ans.append(_)
        return ans

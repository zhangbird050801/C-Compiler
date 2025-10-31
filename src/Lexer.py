import sys
from collections import namedtuple

file = 'c-code.c'

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

ID, CONST_DECIMAL, CONST_OCTAL, CONST_HEX, CONST_FLOAT, CONST_CHAR, STRING_, PREPROCESSOR = 82, 83, 84, 85, 86, 87, 88, 89
EOF = -1
HEX_CHAR = '0123456789abcdefABCDEF'
OCTAL_CHAR = '01234567'
MAX_IDENTIFIER_LENGTH = 63  # C99 标准建议至少 63 个字符
VALID_ESCAPE_CHARS = 'abfnrtvxo\\\'"?0123456789'  # 合法的转义字符

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

TOKEN = namedtuple('Token', ['type', 'attribute', 'is_error'])

# 创建token的辅助函数
def make_token(type_, attr, is_error=False):
    return TOKEN(type_, attr, is_error)

TYPES = {}
for _ in KEYWORDS.values():
    TYPES[_] = 'KEYWORD'
for _ in OP.values():
    TYPES[_] = 'OPERATOR'
for _ in DL.values():
    TYPES[_] = 'DELIMITER'
TYPES[ID], TYPES[CONST_DECIMAL], TYPES[CONST_OCTAL], TYPES[CONST_HEX], TYPES[CONST_FLOAT], TYPES[CONST_CHAR], TYPES[STRING_], TYPES[PREPROCESSOR], TYPES[EOF] \
    = 'IDENTIFIER', 'CONST_DECIMAL', 'CONST_OCTAL', 'CONST_HEX', 'CONST_FLOAT', 'CONST_CHAR', 'STRING_LITERAL', 'PREPROCESSOR', 'EOF'

class SymbolTable:
    def __init__(self):
        self.symbols = {}

    def add(self, name):
        if name not in self.symbols:
            self.symbols[name] = {'name': name, 'type': None}
        return self.symbols[name]

    def __str__(self):
        if not self.symbols:
            return "符号表为空"
        
        result = ["\n" + "="*50]
        result.append("符号表 (Symbol Table)")
        result.append("="*50)
        result.append(f"{'序号':<6} {'标识符':<20} {'类型':<15}")
        result.append("-"*50)
        
        for idx, (name, info) in enumerate(self.symbols.items(), 1):
            type_str = info['type'] if info['type'] else '未定义'
            result.append(f"{idx:<6} {name:<20} {type_str:<15}")
        
        result.append("="*50)
        result.append(f"总计: {len(self.symbols)} 个标识符")
        result.append("="*50)
        
        return "\n".join(result)


def process(text):
    code_ = []
    char_, string_ = False, False

    i = 0
    l = len(text)
    line_num = 1  # 从1开始，匹配源文件行号
    
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
            if c == '\n':
                line_num += 1
            i += 1
            continue

        # //
        if c == '/' and i + 1 < l and text[i + 1] == '/':
            code_.append(' ')  # 用空格替换 //
            i += 2
            while i < l and text[i] != '\n':
                code_.append(' ')  # 用空格替换注释内容
                i += 1
            if i < l:
                code_.append('\n')  # 保留换行符
                line_num += 1
                i += 1
            continue
        # /* */
        elif c == '/' and i + 1 < l and text[i + 1] == '*':
            comment_start_line = line_num
            code_.append(' ')  # 用空格替换 /
            i += 1
            code_.append(' ')  # 用空格替换 *
            i += 1
            while i < l and not (i + 1 < l and text[i:i+2] == '*/'):
                if text[i] == '\n':
                    code_.append('\n')  # 保留换行符
                    line_num += 1
                else:
                    code_.append(' ')  # 用空格替换注释内容
                i += 1
            if i + 1 < l:
                code_.append(' ')  # 用空格替换 *
                i += 1
                code_.append(' ')  # 用空格替换 /
                i += 1
            else:
                # 未闭合的块注释
                print(f">>> 错误: 未闭合的块注释 at line {comment_start_line}")
            continue

        code_.append(c)
        if c == '\n':
            line_num += 1
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
        self.errors = []  # 存储错误信息

        # 按符号长度进行降序
        # 使得长的优先匹配
        t_ = {**OP, **DL}
        self.symbols = sorted(t_.items(), key=lambda x: len(x[0]), reverse=True)

    def error(self, error, content='', *args):
        m = ERRORS.get(error, "未知错误").format(*args)
        if content:
            error_msg = f'错误: {m}, 内容: "{content}" at line {self.line}'
        else:
            error_msg = f'错误: {m} at line {self.line}'
        self.errors.append(error_msg)
        return error_msg

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
            self.error('INVALID_IDENTIFIER', '')

        tmp = ''
        while self.char is not None and (self.char.isalnum() or self.char == '_'):
            tmp += self.char; self.next()

        # 检查标识符长度（已禁用）
        # if len(tmp) > MAX_IDENTIFIER_LENGTH:
        #     self.error('IDENTIFIER_TOO_LONG', tmp)

        type_ = KEYWORDS.get(tmp, ID)

        if type_ == ID:
            self.table.add(tmp)

        return make_token(type_, tmp)

    def _float(self, tmp):
        flag = False
        error_flag = False
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
                self.error('INVALID_FLOAT_EXPONENT', tmp)
                error_flag = True
                return tmp, flag, error_flag
            while self.char is not None and self.char.isdigit():
                tmp += self.char; self.next()

        return tmp, flag, error_flag

    def _num(self):
        tmp = ''
        is_error = False

        # --- [BUG 1 修复] ---
        # 专门处理以 '.' 开头的浮点数 (如 .123)
        if self.char == '.':
            tmp += self.char
            self.next()  # 消耗 '.'

            # 消耗小数点后的所有数字
            while self.char is not None and self.char.isdigit():
                tmp += self.char
                self.next()

            # 检查 'e' 或 'E' 的指数部分
            if self.char in 'eE':
                tmp += self.char;
                self.next()
                if self.char in '+-':
                    tmp += self.char;
                    self.next()
                if not (self.char and self.char.isdigit()):
                    self.error('INVALID_FLOAT_EXPONENT', tmp)
                    is_error = True
                while self.char is not None and self.char.isdigit():
                    tmp += self.char;
                    self.next()

            # 检查是否有非法的后缀 (如 .123abc)
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char;
                    self.next()
                self.error('INVALID_IDENTIFIER', tmp)
                is_error = True

            return make_token(CONST_FLOAT, tmp, is_error)
        # --- [BUG 1 修复结束] ---

        # --- [BUG 2 修复：统一的数字处理逻辑] ---

        # 1. 检查是否可能为八进制 (以 0 开头)
        is_octal_candidate = False
        if self.char == '0':
            is_octal_candidate = True
            tmp += self.char
            self.next()

            # 2. 检查是否为十六进制 (如果是，则特殊处理并立即返回)
            if self.char in 'xX':
                tmp += self.char;
                self.next()
                _ = self.pos
                while self.char is not None and self.char in HEX_CHAR:
                    tmp += self.char;
                    self.next()

                # 检查 0x 后面是否跟了非法字符
                if _ == self.pos or (self.char is not None and (self.char.isalnum() or self.char == '_')):
                    while self.char is not None and (self.char.isalnum() or self.char == '_'):
                        tmp += self.char;
                        self.next()
                    self.error('INVALID_HEX', tmp)
                    is_error = True
                return make_token(CONST_HEX, tmp, is_error)

        # 3. 消耗所有剩余的连续数字 (十进制或八进制)
        while self.char is not None and self.char.isdigit():
            tmp += self.char
            self.next()

        # 4. 检查是否为浮点数 (e.g., "01" -> "01.23", "123" -> "123e4")
        if self.char == '.' or self.char in 'eE':
            is_octal_candidate = False  # 肯定是浮点数了
            # _float 会处理 . 和 eE 后面的所有部分
            tmp, flag, is_error_float = self._float(tmp)
            is_error = is_error or is_error_float

            # 检查浮点数后面是否有非法后缀
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char;
                    self.next()
                self.error('INVALID_IDENTIFIER', tmp)
                is_error = True

            return make_token(CONST_FLOAT, tmp, is_error)

        # 5. 检查是否跟了非法标识符 (e.g., "123abc")
        if self.char is not None and (self.char.isalpha() or self.char == '_'):
            while self.char is not None and (self.char.isalnum() or self.char == '_'):
                tmp += self.char;
                self.next()
            self.error('INVALID_IDENTIFIER', tmp)
            is_error = True
            # 注意：即使是 "01abc" (非法标识符)，它首先是个非法的八进制数
            # 但报告为 INVALID_IDENTIFIER 更合适

        # 6. 如果不是浮点数，现在判断是十进制还是八进制
        has_invalid_octal_digit = False
        if is_octal_candidate:
            # 检查是否包含 8 或 9 (e.g., "08", "019")
            for char in tmp[1:]:  # 检查 '0' 后面的所有数字
                if char not in OCTAL_CHAR:
                    has_invalid_octal_digit = True
                    break

        if has_invalid_octal_digit:
            self.error('INVALID_OCTAL_DIGIT', tmp)
            is_error = True
            return make_token(CONST_OCTAL, tmp, is_error)  # 报告为无效八进制

        if is_octal_candidate and len(tmp) > 0:
            # 它是 '0' 或者 '0123' 这种合法的八进制
            return make_token(CONST_OCTAL, tmp, is_error)

        # 剩下的都是合法的十进制数
        return make_token(CONST_DECIMAL, tmp, is_error)

    def _str(self):
        tmp = ''
        is_error = False
        self.next()
        while self.char is not None and self.char != '"' and self.char != '\n':
            if self.char == '\\':
                tmp += self.char; self.next()

                if self.char is None:
                    self.error('UNTERMINATED_STRING', tmp)
                    is_error = True
                    break
                
                # 检查转义字符是否合法（可选，比较宽松的检查）
                # if self.char not in VALID_ESCAPE_CHARS:
                #     self.error('INVALID_ESCAPE', f"\\{self.char}")
                
                tmp += self.char; self.next()
            else:
                tmp += self.char; self.next()

        # 遇到换行符（字符串跨行）
        if self.char == '\n':
            self.error('STRING_NEWLINE', tmp)
            is_error = True
        # 正常结束
        elif self.char == '"':
            self.next()
        # 文件结束但字符串未闭合
        else:
            self.error('UNTERMINATED_STRING', tmp)
            is_error = True
            
        return make_token(STRING_, tmp, is_error)

    def _char(self):
        tmp = ''
        is_error = False
        start_line = self.line
        self.next()

        # 空字符常量 ''
        if self.char == "'":
            self.error('EMPTY_CHAR', '')
            self.next()
            return make_token(CONST_CHAR, tmp, True)

        if self.char is None:
            self.error('UNTERMINATED_CHAR', tmp)
            return make_token(CONST_CHAR, tmp, True)
        
        if self.char == '\\':
            tmp += self.char; self.next()

            if self.char is None:
                self.error('UNTERMINATED_CHAR', tmp)
                return make_token(CONST_CHAR, tmp, True)
            
            # 检查转义字符（可选）
            # if self.char not in VALID_ESCAPE_CHARS:
            #     self.error('INVALID_ESCAPE', f"\\{self.char}")
            #     is_error = True
            
            tmp += self.char; self.next()
        else:
            tmp += self.char; self.next()

        # 检查是否是多字符常量（如 'abc'）
        if self.char != "'" and self.char is not None and self.char != '\n':
            # 收集所有额外字符
            extra_chars = ''
            while self.char is not None and self.char != "'" and self.char != '\n':
                extra_chars += self.char
                self.next()
            self.error('MULTI_CHAR', tmp + extra_chars)
            is_error = True

        if self.char != "'":
            self.error('UNTERMINATED_CHAR', tmp)
            is_error = True
        else:
            self.next()
            
        return make_token(CONST_CHAR, tmp, is_error)

    def _preprocessor(self):
        """处理预处理指令 如 #include, #define 等"""
        tmp = ''
        while self.char is not None and self.char != '\n':
            tmp += self.char
            self.next()
        return make_token(PREPROCESSOR, tmp.strip())

    def next_token(self):
        while self.char is not None:
            self.skip()
            _ = self.char
            if _ is None:
                continue
            
            # 处理预处理指令
            if _ == '#':
                return self._preprocessor()
            
            if _.isalpha() or _ == '_':
                return self._id()
            if _.isdigit():
                return self._num()

            # --- [BUG 1 修复] ---
            # 新增判断：如果是点，并且点后面是数字，
            # 也交给 _num() 处理
            if _ == '.' and self.pos + 1 < len(self.text) and self.text[self.pos + 1].isdigit():
                return self._num()
            # --- [修复结束] ---

            if _ == '"':
                return self._str()
            if _ == "'":
                return self._char()

            for s, t in self.symbols:
                if self.text.startswith(s, self.pos):
                    for _ in range(len(s)): self.next()
                    return make_token(t, s)
            
            # 遇到无法识别的字符，记录错误但继续
            unknown_char = self.char
            self.error('UNKNOWN_CHAR', unknown_char)
            self.next()  # 跳过这个字符继续解析
        return make_token(EOF, 'EOF')

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
    
    # 输出所有token，遇到错误立即显示
    for token in tokens:
        if token.is_error:
            # 立即输出错误信息
            for error in lexer.errors:
                if token.attribute in error:  # 找到对应的错误信息
                    print(f">>> {error}")
                    break
            continue  # 跳过有错误的token，不输出到正常列表
            
        _ = TYPES.get(token.type, 'UNKNOWN')

        if token.type == STRING_:
            attr_ = f'"{token.attribute}"'
        elif token.type == CONST_CHAR:
            attr_ = f"'{token.attribute}'"
        else:
            attr_ = token.attribute

        print(f"( {_:<16} <{token.type}>: {attr_} )")

    print(lexer.table)
    
    # 输出所有错误汇总
    if lexer.errors:
        print("\n" + "="*50)
        print("词法分析过程中发现以下错误:")
        print("="*50)
        for error in lexer.errors:
            print(error)

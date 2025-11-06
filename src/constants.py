# 关键字映射表
KEYWORDS = {
    'auto': 1, 'break': 2, 'case': 3, 'char': 4, 'const': 5, 'continue': 6, 'default': 7, 'do': 8,
    'double': 9, 'else': 10, 'enum': 11, 'extern': 12, 'float': 13, 'for': 14, 'goto': 15, 'if': 16,
    'int': 17, 'long': 18, 'register': 19, 'return': 20, 'short': 21, 'signed': 22, 'sizeof': 23, 'static': 24,
    'struct': 25, 'switch': 26, 'typedef': 27, 'union': 28, 'unsigned': 29, 'void': 30, 'volatile': 31, 'while': 32
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
# BASE36_CHAR = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

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

import sys
from collections import namedtuple
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk

# ==============================================================================
# 1. 核心词法分析逻辑 (已重构)
# ==============================================================================

# --- [修改点 1]：Token 增加了 'line' 属性 ---
TOKEN = namedtuple('Token', ['type', 'attribute', 'line', 'is_error'])


# --- [修改点 2]：make_token 增加了 'line' 参数 ---
def make_token(type_, attr, line, is_error=False):
    return TOKEN(type_, attr, line, is_error)


# --- 常量定义 (不变) ---
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
    '.': 67, '?': 68, ':': 69
}
DL = {
    '(': 70, ')': 71, '[': 72, ']': 73, '{': 74, '}': 75, ',': 76, ';': 77,
}
ID, CONST_DECIMAL, CONST_OCTAL, CONST_HEX, CONST_FLOAT, CONST_CHAR, STRING_, PREPROCESSOR = 82, 83, 84, 85, 86, 87, 88, 89
EOF = -1
HEX_CHAR = '0123456789abcdefABCDEF'
OCTAL_CHAR = '01234567'

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
    'UNTERMINATED_COMMENT': "未闭合的块注释",  # <-- [修改点 3]：新错误类型
    'IDENTIFIER_TOO_LONG': "标识符长度超过限制",
    'UNKNOWN_CHAR': "未知字符",
}

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


# --- 符号表类 (不变) ---
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

        result = ["\n" + "=" * 50]
        result.append("符号表 (Symbol Table)")
        result.append("=" * 50)
        result.append(f"{'序号':<6} {'标识符':<20} {'类型':<15}")
        result.append("-" * 50)

        for idx, (name, info) in enumerate(self.symbols.items(), 1):
            type_str = info['type'] if info['type'] else '未定义'
            result.append(f"{idx:<6} {name:<20} {type_str:<15}")

        result.append("=" * 50)
        result.append(f"总计: {len(self.symbols)} 个标识符")
        result.append("=" * 50)

        return "\n".join(result)


# --- [修改点 4]：process 函数被彻底移除 ---
# (已删除)


# --- 词法分析器类 (已重构) ---
class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1
        self.table = SymbolTable()
        self.char = self.text[self.pos] if self.text else None
        self.errors = []

        t_ = {**OP, **DL}
        self.symbols = sorted(t_.items(), key=lambda x: len(x[0]), reverse=True)

    def error(self, error, content='', line=None, *args):
        # 错误现在可以指定行号
        report_line = line if line is not None else self.line

        m = ERRORS.get(error, "未知错误").format(*args)
        if content:
            error_msg = f'错误: {m}, 内容: "{content}" at line {report_line}'
        else:
            error_msg = f'错误: {m} at line {report_line}'
        self.errors.append(error_msg)
        return error_msg

    def next(self):
        if self.char == '\n':
            self.line += 1
            self.col = 0
        self.pos += 1
        self.col += 1
        self.char = self.text[self.pos] if self.pos < len(self.text) else None

    # --- [修改点 5]：全新的函数，用于处理空白和注释 ---
    def skip_whitespace_and_comments(self):
        """ 跳过所有空白字符、单行注释和多行注释 """
        while self.char is not None:
            if self.char.isspace():
                self.next()
                continue

            # 处理 // 注释
            if self.char == '/' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '/':
                while self.char is not None and self.char != '\n':
                    self.next()
                continue  # 继续循环，可能会有更多空白或注释

            # 处理 /* */ 注释
            if self.char == '/' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '*':
                start_line = self.line  # 记录起始行，用于报错
                self.next()  # skip /
                self.next()  # skip *

                while self.char is not None and not (
                        self.char == '*' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '/'):
                    self.next()

                if self.char is None:
                    # 未闭合的注释，使用 Lexer 的错误处理机制！
                    self.error('UNTERMINATED_COMMENT', '', line=start_line)
                    break  # 结束循环
                else:
                    self.next()  # skip *
                    self.next()  # skip /
                continue  # 继续循环

            # 如果既不是空白也不是注释，则停止
            break

    # KEYWORDS or ID
    def _id(self):
        start_line = self.line
        if not (self.char and (self.char.isalpha() or self.char == '_')):
            self.error('INVALID_IDENTIFIER', '', line=start_line)
        tmp = ''
        while self.char is not None and (self.char.isalnum() or self.char == '_'):
            tmp += self.char;
            self.next()
        type_ = KEYWORDS.get(tmp, ID)
        if type_ == ID:
            self.table.add(tmp)
        # --- [修改点 6]：所有 make_token 调用都增加了 line=start_line ---
        return make_token(type_, tmp, line=start_line)

    def _float(self, tmp):
        # (这个辅助函数不变)
        flag = False
        error_flag = False
        if self.char == '.':
            flag = True
            tmp += self.char;
            self.next()
            while self.char is not None and self.char.isdigit():
                tmp += self.char;
                self.next()

        if self.char in 'eE':
            flag = True
            tmp += self.char;
            self.next()
            if self.char in '+-':
                tmp += self.char;
                self.next()
            if not (self.char and self.char.isdigit()):
                self.error('INVALID_FLOAT_EXPONENT', tmp)
                error_flag = True
                return tmp, flag, error_flag
            while self.char is not None and self.char.isdigit():
                tmp += self.char;
                self.next()

        return tmp, flag, error_flag

    def _num(self):
        tmp = ''
        is_error = False
        start_line = self.line  # 记录Token的起始行号

        if self.char == '.':
            tmp += self.char
            self.next()
            while self.char is not None and self.char.isdigit():
                tmp += self.char
                self.next()
            if self.char in 'eE':
                tmp += self.char;
                self.next()
                if self.char in '+-':
                    tmp += self.char;
                    self.next()
                if not (self.char and self.char.isdigit()):
                    self.error('INVALID_FLOAT_EXPONENT', tmp, line=start_line)
                    is_error = True
                while self.char is not None and self.char.isdigit():
                    tmp += self.char;
                    self.next()
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char;
                    self.next()
                self.error('INVALID_IDENTIFIER', tmp, line=start_line)
                is_error = True
            return make_token(CONST_FLOAT, tmp, line=start_line, is_error=is_error)

        is_octal_candidate = False
        if self.char == '0':
            is_octal_candidate = True
            tmp += self.char
            self.next()
            if self.char in 'xX':
                tmp += self.char;
                self.next()
                _ = self.pos
                while self.char is not None and self.char in HEX_CHAR:
                    tmp += self.char;
                    self.next()
                if _ == self.pos or (self.char is not None and (self.char.isalnum() or self.char == '_')):
                    while self.char is not None and (self.char.isalnum() or self.char == '_'):
                        tmp += self.char;
                        self.next()
                    self.error('INVALID_HEX', tmp, line=start_line)
                    is_error = True
                return make_token(CONST_HEX, tmp, line=start_line, is_error=is_error)

        while self.char is not None and self.char.isdigit():
            tmp += self.char
            self.next()

        if self.char == '.' or self.char in 'eE':
            is_octal_candidate = False
            tmp, flag, is_error_float = self._float(tmp)
            is_error = is_error or is_error_float
            if self.char is not None and (self.char.isalpha() or self.char == '_'):
                while self.char is not None and (self.char.isalnum() or self.char == '_'):
                    tmp += self.char;
                    self.next()
                self.error('INVALID_IDENTIFIER', tmp, line=start_line)
                is_error = True
            return make_token(CONST_FLOAT, tmp, line=start_line, is_error=is_error)

        if self.char is not None and (self.char.isalpha() or self.char == '_'):
            while self.char is not None and (self.char.isalnum() or self.char == '_'):
                tmp += self.char;
                self.next()
            self.error('INVALID_IDENTIFIER', tmp, line=start_line)
            is_error = True

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
        tmp = ''
        is_error = False
        start_line = self.line
        self.next()
        while self.char is not None and self.char != '"' and self.char != '\n':
            if self.char == '\\':
                tmp += self.char;
                self.next()
                if self.char is None:
                    self.error('UNTERMINATED_STRING', tmp, line=start_line)
                    is_error = True
                    break
                tmp += self.char;
                self.next()
            else:
                tmp += self.char;
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
        tmp = ''
        is_error = False
        start_line = self.line
        self.next()

        if self.char == "'":
            self.error('EMPTY_CHAR', '', line=start_line)
            self.next()
            return make_token(CONST_CHAR, tmp, line=start_line, is_error=True)

        if self.char is None:
            self.error('UNTERMINATED_CHAR', tmp, line=start_line)
            return make_token(CONST_CHAR, tmp, line=start_line, is_error=True)

        if self.char == '\\':
            tmp += self.char;
            self.next()
            if self.char is None:
                self.error('UNTERMINATED_CHAR', tmp, line=start_line)
                return make_token(CONST_CHAR, tmp, line=start_line, is_error=True)
            tmp += self.char;
            self.next()
        else:
            tmp += self.char;
            self.next()

        # 检查是否是多字符常量（如 'abc'）
        if self.char != "'" and self.char is not None and self.char != '\n':
            extra_chars = ''
            while self.char is not None and self.char != "'" and self.char != '\n':
                extra_chars += self.char
                self.next()

            # --- [BUG 修复在这里] ---
            # 1. 报告完整的错误
            self.error('MULTI_CHAR', tmp + extra_chars, line=start_line)
            is_error = True
            # 2. 更新 tmp，让 Token 也包含完整内容
            tmp = tmp + extra_chars
            # --- [修复结束] ---

        if self.char != "'":
            self.error('UNTERMINATED_CHAR', tmp, line=start_line)
            is_error = True
        else:
            self.next()

        return make_token(CONST_CHAR, tmp, line=start_line, is_error=is_error)

    def _preprocessor(self):
        start_line = self.line
        tmp = ''
        while self.char is not None:
            # (Bug 3: 续行符 \n 暂未修复，保持原样)
            if self.char == '\\':
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '\n':
                    self.next()  # skip \
                    self.next()  # skip \n
                    tmp += ' '  # 续行符替换为空格
                    continue

            if self.char == '\n':
                break

            tmp += self.char
            self.next()
        return make_token(PREPROCESSOR, tmp.strip(), line=start_line)

    def next_token(self):
        while self.char is not None:
            # --- [修改点 7]：调用新函数来跳过空白和注释 ---
            self.skip_whitespace_and_comments()

            _ = self.char
            if _ is None:
                continue

            start_line = self.line  # 记录所有Token的起始行号

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

            for s, t in self.symbols:
                if self.text.startswith(s, self.pos):
                    for _ in range(len(s)): self.next()
                    return make_token(t, s, line=start_line)

            unknown_char = self.char
            self.error('UNKNOWN_CHAR', unknown_char, line=start_line)
            self.next()

        # 循环结束，返回 EOF
        return make_token(EOF, 'EOF', line=self.line)

    def tokenize(self):
        ans = []
        _ = self.next_token()
        while _.type != EOF:
            ans.append(_)
            _ = self.next_token()
        ans.append(_)
        return ans


# ==============================================================================
# 2. GUI 应用层 (已更新)
# ==============================================================================

class LexerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("C 语言词法分析器 (GUI版 v2)")
        self.geometry("1000x700")

        style = ttk.Style(self)
        style.theme_use('clam')

        self.create_widgets()

    def create_widgets(self):
        # (GUI 布局不变)
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill='x')
        self.load_button = ttk.Button(top_frame, text="1. 加载 C 文件", command=self.load_file)
        self.load_button.pack(side='left', padx=5)
        self.run_button = ttk.Button(top_frame, text="2. 运行词法分析", command=self.run_analysis)
        self.run_button.pack(side='left', padx=5)
        self.clear_button = ttk.Button(top_frame, text="清除全部", command=self.clear_all)
        self.clear_button.pack(side='right', padx=5)
        main_frame = ttk.Frame(self, padding="0 10 10 10")
        main_frame.pack(fill='both', expand=True)
        paned_window = ttk.PanedWindow(main_frame, orient='horizontal')
        paned_window.pack(fill='both', expand=True)
        input_frame = ttk.Frame(paned_window, padding=5)
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(1, weight=1)
        ttk.Label(input_frame, text="C 源代码输入:").grid(row=0, column=0, sticky='w', pady=5)
        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=10, width=60)
        self.input_text.grid(row=1, column=0, sticky='nsew')
        paned_window.add(input_frame, weight=1)
        output_frame = ttk.Frame(paned_window, padding=5)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)
        ttk.Label(output_frame, text="分析结果:").grid(row=0, column=0, sticky='w', pady=5)
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=10, width=60, state='disabled')
        self.output_text.grid(row=1, column=0, sticky='nsew')
        paned_window.add(output_frame, weight=1)

    def load_file(self):
        # (不变)
        filepath = filedialog.askopenfilename(
            title="选择一个 C 源文件",
            filetypes=[("C Files", "*.c"), ("Header Files", "*.h"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert("1.0", code)
            self.output_text.config(state='normal')
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", f"成功加载文件: {filepath}\n")
            self.output_text.config(state='disabled')
        except Exception as e:
            messagebox.showerror("加载失败", f"无法读取文件: {e}")

    # --- [修改点 8]：run_analysis 已重构 ---
    def run_analysis(self):
        code = self.input_text.get("1.0", tk.END)
        if not code.strip():
            messagebox.showwarning("输入为空", "请输入或加载 C 代码后再试。")
            return

        self.output_text.config(state='normal')
        self.output_text.delete("1.0", tk.END)

        output_buffer = []

        try:
            # 1. 运行词法分析
            lexer = Lexer(code)
            tokens = lexer.tokenize()

            output_buffer.append("=" * 50 + "\n")
            output_buffer.append("词法单元流 (Token Stream)\n")
            output_buffer.append("=" * 50 + "\n")

            # 2. [最终融合方案]
            # 打印带行号的Token流，并内联显示错误

            printed_error_messages = set()

            for token in tokens:
                if token.is_error:
                    # [内联错误显示]
                    # 尝试使用 token.line 和 token.attribute 进行精确匹配
                    found_error = False
                    for error in lexer.errors:
                        if error in printed_error_messages:
                            continue

                        # 关键: 使用行号和内容双重匹配
                        if f"at line {token.line}" in error and token.attribute in error:
                            output_buffer.append(f">>> {error}\n")
                            printed_error_messages.add(error)
                            found_error = True
                            break

                    # 兜底：处理空字符串 '' 错误
                    if not found_error and token.attribute == '':
                        for error in lexer.errors:
                            if error in printed_error_messages:
                                continue
                            if f"at line {token.line}" in error and "空字符" in error:
                                output_buffer.append(f">>> {error}\n")
                                printed_error_messages.add(error)
                                break
                    continue  # 跳过打印这个错误的Token

                # --- [保留行号显示] ---
                # (处理正常Token的逻辑)

                _ = TYPES.get(token.type, 'UNKNOWN')

                if token.type == STRING_:
                    attr_ = f'"{token.attribute}"'
                elif token.type == CONST_CHAR:
                    attr_ = f"'{token.attribute}'"
                else:
                    attr_ = token.attribute

                # 构建带行号的输出
                line_prefix = f"[L{token.line:<3}]"  # L表示Line, <3 表示左对齐占3位
                token_body = f"( {_:<16} <{token.type}>: {attr_} )"

                output_buffer.append(f"    {line_prefix} {token_body}\n")

            # 6. 打印符号表 (不变)
            output_buffer.append(str(lexer.table) + "\n")

            # 7. 打印错误汇总 (不变)
            if lexer.errors:
                output_buffer.append("\n" + "=" * 50 + "\n")
                output_buffer.append("词法分析过程中发现以下错误:\n")
                output_buffer.append("=" * 50 + "\n")
                for error in lexer.errors:
                    output_buffer.append(f">>> {error}\n")
            else:
                output_buffer.append("\n" + "=" * 50 + "\n")
                output_buffer.append("词法分析完成，未发现错误。\n")
                output_buffer.append("=" * 50 + "\n")

        except Exception as e:
            output_buffer.append("\n" + "!" * 50 + "\n")
            output_buffer.append(f"程序执行时发生致命错误: {e}\n")
            output_buffer.append("!" * 50 + "\n")

        # 8. 写入GUI
        self.output_text.insert("1.0", "".join(output_buffer))
        self.output_text.config(state='disabled')

    def clear_all(self):
        # (不变)
        self.input_text.delete("1.0", tk.END)
        self.output_text.config(state='normal')
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state='disabled')


# ==============================================================================
# 3. 启动器 (不变)
# ==============================================================================

if __name__ == '__main__':
    app = LexerApp()
    app.mainloop()
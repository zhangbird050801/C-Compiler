"""
C 语言词法分析器 GUI 界面
"""
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk, font
from lexer_core import (
    Lexer, TYPES, STRING_, CONST_CHAR, EOF
)


class LexerApp(tk.Tk):
    """词法分析器图形界面应用"""
    
    def __init__(self):
        super().__init__()
        self.title("C 语言词法分析器 (GUI版 v3)")
        self.geometry("1400x700")

        # 设置字体
        self.default_font = font.nametofont("TkDefaultFont")
        self.text_font = font.Font(family="Consolas", size=14)  # 修改这里的size值来调整字体大小
        self.button_font = font.Font(family="Consolas", size=14)

        style = ttk.Style(self)
        style.theme_use('clam')

        # 设置按钮字体
        style.configure('TButton', font=self.button_font)
        style.configure('TLabel', font=self.button_font)

        self.create_widgets()

    def create_widgets(self):
        """创建界面组件"""
        # 顶部工具栏
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill='x')
        
        self.load_button = ttk.Button(top_frame, text="1. 加载 C 文件", command=self.load_file)
        self.load_button.pack(side='left', padx=5)
        
        self.run_button = ttk.Button(top_frame, text="2. 运行词法分析", command=self.run_analysis)
        self.run_button.pack(side='left', padx=5)
        
        self.clear_button = ttk.Button(top_frame, text="清除全部", command=self.clear_all)
        self.clear_button.pack(side='right', padx=5)
        
        # 主内容区域
        main_frame = ttk.Frame(self, padding="0 10 10 10")
        main_frame.pack(fill='both', expand=True)
        
        paned_window = ttk.PanedWindow(main_frame, orient='horizontal')
        paned_window.pack(fill='both', expand=True)
        
        # 左侧：输入区域（带行号）
        input_frame = ttk.Frame(paned_window, padding=5)
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="C 源代码输入:").grid(row=0, column=0, sticky='w', pady=5)
        
        # 使用标准文本编辑器
        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=10, width=60, font=self.text_font)
        self.input_text.grid(row=1, column=0, sticky='nsew')
        
        paned_window.add(input_frame, weight=1)
        
        # 右侧：输出区域
        output_frame = ttk.Frame(paned_window, padding=5)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)
        
        ttk.Label(output_frame, text="分析结果:").grid(row=0, column=0, sticky='w', pady=5)
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame, wrap=tk.WORD, height=10, width=60, state='disabled', font=self.text_font
        )
        self.output_text.grid(row=1, column=0, sticky='nsew')
        
        paned_window.add(output_frame, weight=1)

    def load_file(self):
        """加载 C 源文件"""
        filepath = filedialog.askopenfilename(
            title="选择一个 C 源文件",
            filetypes=[
                ("C Files", "*.c"), 
                ("Header Files", "*.h"), 
                ("Text Files", "*.txt"), 
                ("All Files", "*.*")
            ]
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

    def run_analysis(self):
        """运行词法分析"""
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
            output_buffer.append("词法分析\n")
            output_buffer.append("=" * 50 + "\n")

            # 2. 打印带行号的 Token 流，并内联显示错误
            printed_error_messages = set()

            for token in tokens:
                if token.error:
                    # 内联错误显示
                    found_error = False
                    for error in lexer.errors:
                        if error in printed_error_messages:
                            continue

                        # 使用行号和内容双重匹配
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
                    continue  # 跳过打印这个错误的 Token

                # 处理正常 Token
                _ = TYPES.get(token.type, 'UNKNOWN')

                if token.type == STRING_:
                    attr_ = f'"{token.attribute}"'
                elif token.type == CONST_CHAR:
                    attr_ = f"'{token.attribute}'"
                else:
                    attr_ = token.attribute

                # 构建带行号的输出
                line_prefix = f"[Line{token.line:<3}]"  # L 表示 Line, <3 表示左对齐占3位
                token_body = f"( {_:<16} <{token.type}>: {attr_} )"

                output_buffer.append(f"    {line_prefix} {token_body}\n")

            # 3. 打印符号表
            output_buffer.append(str(lexer.table) + "\n")

            # 4. 打印错误汇总
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

        # 5. 写入 GUI
        self.output_text.insert("1.0", "".join(output_buffer))
        self.output_text.config(state='disabled')

    def clear_all(self):
        """清除所有内容"""
        self.input_text.delete("1.0", tk.END)
        self.output_text.config(state='normal')
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state='disabled')

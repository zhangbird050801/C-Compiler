"""
C 语言编译器实验 - 语法分析 (实验报告专用版)
"""
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk, font
from lexer_core import Lexer, TYPES, STRING_, CONST_CHAR, EOF
try:
    from parser_core import LL1Parser
except ImportError:
    LL1Parser = None

class LexerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("C 语言编译器实验 - 语法分析表生成")
        self.geometry("1400x850")
        self.text_font = font.Font(family="Consolas", size=10) # 字体稍微调小以便显示长串
        self.header_font = font.Font(family="Microsoft YaHei", size=11, weight="bold")
        self.create_widgets()

    def create_widgets(self):
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill='x')

        ttk.Button(top_frame, text="1. 加载 C 文件", command=self.load_file).pack(side='left', padx=5)
        ttk.Button(top_frame, text="2. 运行词法分析", command=self.run_analysis).pack(side='left', padx=5)
        ttk.Button(top_frame, text="3. 生成语法分析表", command=self.run_parser).pack(side='left', padx=5)
        ttk.Button(top_frame, text="清除全部", command=self.clear_all).pack(side='right', padx=5)

        self.paned_window = ttk.PanedWindow(self, orient='horizontal')
        self.paned_window.pack(fill='both', expand=True, padx=10, pady=10)

        # 左侧
        input_frame = ttk.Frame(self.paned_window, padding=5)
        ttk.Label(input_frame, text="C 源代码输入:", font=self.header_font).pack(anchor='w')
        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.NONE, font=self.text_font)
        self.input_text.pack(fill='both', expand=True)
        self.paned_window.add(input_frame, weight=1)

        # 右侧 (Notebook)
        output_frame = ttk.Frame(self.paned_window, padding=5)
        self.notebook = ttk.Notebook(output_frame)
        self.notebook.pack(fill='both', expand=True)

        self.lexer_tab = scrolledtext.ScrolledText(self.notebook, wrap=tk.NONE, font=self.text_font, state='disabled')
        self.notebook.add(self.lexer_tab, text=" 词法 Token 流 ")

        self.parser_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.parser_tab, text=" 语法分析过程表 ")

        # --- 关键修改：定义5列数据 ---
        columns = ("step", "stack", "input", "production", "action")
        self.tree = ttk.Treeview(self.parser_tab, columns=columns, show='headings')

        # 设置表头文字
        self.tree.heading("step", text="步骤")
        self.tree.heading("stack", text="分析栈 (Stack)")
        self.tree.heading("input", text="符号串 (Input)")
        self.tree.heading("production", text="所用产生式")
        self.tree.heading("action", text="下一步动作")

        # 设置列宽 (根据内容调整)
        self.tree.column("step", width=50, anchor='center')
        self.tree.column("stack", width=300, anchor='w')
        self.tree.column("input", width=250, anchor='e') # 符号串通常右对齐好看
        self.tree.column("production", width=200, anchor='w')
        self.tree.column("action", width=250, anchor='w')

        vsb = ttk.Scrollbar(self.parser_tab, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.parser_tab, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        self.parser_tab.grid_columnconfigure(0, weight=1)
        self.parser_tab.grid_rowconfigure(0, weight=1)

        self.paned_window.add(output_frame, weight=3) # 让右侧宽一点

    def load_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("C Files", "*.c"), ("All Files", "*.*")])
        if filepath:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.input_text.delete("1.0", tk.END)
                self.input_text.insert("1.0", f.read())

    def run_analysis(self):
        code = self.input_text.get("1.0", tk.END)
        lexer = Lexer(code); tokens = lexer.tokenize()
        self.notebook.select(0)
        self.lexer_tab.config(state='normal'); self.lexer_tab.delete("1.0", tk.END)
        for t in tokens: self.lexer_tab.insert(tk.END, f"[L{t.line:<2}] ({TYPES.get(t.type, 'UNK'):<15} : {t.attribute})\n")
        self.lexer_tab.config(state='disabled')

    def run_parser(self):
        if LL1Parser is None: return
        code = self.input_text.get("1.0", tk.END)
        lexer = Lexer(code); tokens = lexer.tokenize()
        parser = LL1Parser()

        # 获取返回的 5元组 records
        records, success, message = parser.analyze(tokens)

        self.notebook.select(1)
        for item in self.tree.get_children(): self.tree.delete(item)

        # 插入数据
        for step, stack, inp, prod, action in records:
            self.tree.insert("", tk.END, values=(step, stack, inp, prod, action))

        if success: messagebox.showinfo("成功", message)
        else: messagebox.showerror("错误", message)

    def clear_all(self):
        self.input_text.delete("1.0", tk.END)
        self.lexer_tab.config(state='normal'); self.lexer_tab.delete("1.0", tk.END); self.lexer_tab.config(state='disabled')
        for item in self.tree.get_children(): self.tree.delete(item)

if __name__ == '__main__':
    app = LexerApp()
    app.mainloop()
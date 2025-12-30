"""
C 语言编译器实验 - 语法分析 (含 First/Follow/Select 集展示)
"""
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk, font
from lexer_core import Lexer, TYPES, EOF

# 尝试导入 parser
try:
    from parser_core import LL1Parser
except ImportError:
    LL1Parser = None

class LexerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("C 语言编译器实验 - 语法分析与文法集合")
        self.geometry("1400x900")
        self.text_font = font.Font(family="Consolas", size=10)
        self.header_font = font.Font(family="Microsoft YaHei", size=11, weight="bold")
        self.create_widgets()

    def create_widgets(self):
        # 顶部按钮区
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill='x')

        ttk.Button(top_frame, text="1. 加载 C 文件", command=self.load_file).pack(side='left', padx=5)
        ttk.Button(top_frame, text="2. 运行词法分析", command=self.run_analysis).pack(side='left', padx=5)
        ttk.Button(top_frame, text="3. 生成分析表 & 集合", command=self.run_parser).pack(side='left', padx=5)
        ttk.Button(top_frame, text="清除全部", command=self.clear_all).pack(side='right', padx=5)

        self.paned_window = ttk.PanedWindow(self, orient='horizontal')
        self.paned_window.pack(fill='both', expand=True, padx=10, pady=10)

        # --- 左侧：代码输入 ---
        input_frame = ttk.Frame(self.paned_window, padding=5)
        ttk.Label(input_frame, text="C 源代码输入:", font=self.header_font).pack(anchor='w')
        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.NONE, font=self.text_font)
        self.input_text.pack(fill='both', expand=True)
        self.paned_window.add(input_frame, weight=1)

        # --- 右侧：结果展示 (Notebook) ---
        output_frame = ttk.Frame(self.paned_window, padding=5)
        self.notebook = ttk.Notebook(output_frame)
        self.notebook.pack(fill='both', expand=True)

        # Tab 1: 词法 Token
        self.lexer_tab = scrolledtext.ScrolledText(self.notebook, wrap=tk.NONE, font=self.text_font, state='disabled')
        self.notebook.add(self.lexer_tab, text=" 词法 Token 流 ")

        # Tab 2: 语法分析过程 (表格)
        self.parser_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.parser_tab, text=" 语法分析过程表 ")

        columns = ("step", "stack", "input", "production", "action")
        self.tree = ttk.Treeview(self.parser_tab, columns=columns, show='headings')

        self.tree.heading("step", text="步骤")
        self.tree.heading("stack", text="分析栈 (Stack)")
        self.tree.heading("input", text="符号串 (Input)")
        self.tree.heading("production", text="所用产生式")
        self.tree.heading("action", text="下一步动作")

        self.tree.column("step", width=50, anchor='center')
        self.tree.column("stack", width=300, anchor='w')
        self.tree.column("input", width=250, anchor='e')
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

        # Tab 3: 文法集合 (First/Follow/Select) -- 新增 --
        self.sets_tab = scrolledtext.ScrolledText(self.notebook, wrap=tk.NONE, font=self.text_font, state='disabled')
        self.notebook.add(self.sets_tab, text=" 文法集合 (Sets) ")

        self.paned_window.add(output_frame, weight=3)

    def load_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("C Files", "*.c"), ("All Files", "*.*")])
        if filepath:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.input_text.delete("1.0", tk.END)
                self.input_text.insert("1.0", f.read())

    def run_analysis(self):
        code = self.input_text.get("1.0", tk.END)
        lexer = Lexer(code)
        tokens = lexer.tokenize()

        self.notebook.select(0) # 切换到 Token 页
        self.lexer_tab.config(state='normal')
        self.lexer_tab.delete("1.0", tk.END)
        for t in tokens:
            t_type = TYPES.get(t.type, 'UNK')
            self.lexer_tab.insert(tk.END, f"[L{t.line:<2}] ({t_type:<15} : {t.attribute})\n")
        self.lexer_tab.config(state='disabled')

    def run_parser(self):
        if LL1Parser is None:
            messagebox.showerror("错误", "未找到 parser_core.py 或导入失败")
            return

        code = self.input_text.get("1.0", tk.END)
        lexer = Lexer(code)
        tokens = lexer.tokenize()

        # 初始化 Parser
        try:
            parser = LL1Parser() # 这里会触发 First/Follow/Select 的计算
        except Exception as e:
            messagebox.showerror("文法构建错误", f"构建预测分析表时出错:\n{e}")
            return

        # 1. 展示 First/Follow/Select 集 (如果 parser 支持)
        if hasattr(parser, 'calc_sets'):
            sets_data = parser.calc_sets()
            self.display_sets(sets_data)
            # 自动切换到集合页查看结果 (或者保留在分析表页，看您的需求)
            # self.notebook.select(2)

        # 2. 执行语法分析
        records, success, message = parser.analyze(tokens)

        # 3. 展示分析过程
        self.notebook.select(1) # 切换到分析过程表
        for item in self.tree.get_children():
            self.tree.delete(item)

        for step, stack, inp, prod, action in records:
            self.tree.insert("", tk.END, values=(step, stack, inp, prod, action))

        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("语法错误", message)

    def display_sets(self, sets_data):
        """格式化并展示 First, Follow, Select 集"""
        self.sets_tab.config(state='normal')
        self.sets_tab.delete("1.0", tk.END)

        def fmt_set(s):
            # 将集合元素排序并转为字符串 {a, b, c}
            elements = sorted(list(s))
            return "{" + ", ".join(elements) + "}"

        # --- FIRST 集 ---
        self.sets_tab.insert(tk.END, "====== FIRST 集合 (First Sets) ======\n")
        first = sets_data.get('first', {})
        for nt in sorted(first.keys()):
            self.sets_tab.insert(tk.END, f"First({nt:<15}) = {fmt_set(first[nt])}\n")
        self.sets_tab.insert(tk.END, "\n")

        # --- FOLLOW 集 ---
        self.sets_tab.insert(tk.END, "====== FOLLOW 集合 (Follow Sets) ======\n")
        follow = sets_data.get('follow', {})
        for nt in sorted(follow.keys()):
            self.sets_tab.insert(tk.END, f"Follow({nt:<15}) = {fmt_set(follow[nt])}\n")
        self.sets_tab.insert(tk.END, "\n")

        # --- SELECT 集 ---
        self.sets_tab.insert(tk.END, "====== SELECT 集合 (Select Sets) ======\n")
        select = sets_data.get('select', {})
        # 按非终结符排序展示
        sorted_select = sorted(select.items(), key=lambda x: x[0][0])

        for (lhs, rhs_tuple), terms in sorted_select:
            # 格式化产生式右部
            rhs_str = " ".join(rhs_tuple)
            if not rhs_str or rhs_str == "epsilon": # 处理空推导显示
                rhs_str = "ε"

            prod_str = f"{lhs} -> {rhs_str}"
            self.sets_tab.insert(tk.END, f"Select({prod_str:<30}) = {fmt_set(terms)}\n")

        self.sets_tab.config(state='disabled')

    def clear_all(self):
        self.input_text.delete("1.0", tk.END)

        self.lexer_tab.config(state='normal')
        self.lexer_tab.delete("1.0", tk.END)
        self.lexer_tab.config(state='disabled')

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.sets_tab.config(state='normal')
        self.sets_tab.delete("1.0", tk.END)
        self.sets_tab.config(state='disabled')

if __name__ == '__main__':
    app = LexerApp()
    app.mainloop()
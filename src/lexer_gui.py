"""
C 语言编译器实验 - 语法分析 (完美表头优化版)
"""
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk, font
from lexer_core import Lexer, TYPES, EOF

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

        # --- 样式配置 ---
        style = ttk.Style()
        # 设置 Treeview 行高，避免太拥挤
        style.configure("Sets.Treeview", font=("Consolas", 10), rowheight=25)
        style.configure("Sets.Treeview.Heading", font=("Microsoft YaHei", 10, "bold"))

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

        # 左侧：代码输入
        input_frame = ttk.Frame(self.paned_window, padding=5)
        ttk.Label(input_frame, text="C 源代码输入:", font=self.header_font).pack(anchor='w')
        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.NONE, font=self.text_font)
        self.input_text.pack(fill='both', expand=True)
        self.paned_window.add(input_frame, weight=1)

        # 右侧：Notebook
        output_frame = ttk.Frame(self.paned_window, padding=5)
        self.notebook = ttk.Notebook(output_frame)
        self.notebook.pack(fill='both', expand=True)

        # Tab 1: Token
        self.lexer_tab = scrolledtext.ScrolledText(self.notebook, wrap=tk.NONE, font=self.text_font, state='disabled')
        self.notebook.add(self.lexer_tab, text=" 词法 Token 流 ")

        # Tab 2: 分析表
        self.parser_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.parser_tab, text=" 语法分析过程表 ")

        parser_cols = ("step", "stack", "input", "production", "action")
        self.tree = ttk.Treeview(self.parser_tab, columns=parser_cols, show='headings')

        self.tree.heading("step", text="步骤"); self.tree.column("step", width=50, anchor='center')
        self.tree.heading("stack", text="分析栈"); self.tree.column("stack", width=300, anchor='w')
        self.tree.heading("input", text="符号串"); self.tree.column("input", width=250, anchor='e')
        self.tree.heading("production", text="产生式"); self.tree.column("production", width=200, anchor='w')
        self.tree.heading("action", text="动作"); self.tree.column("action", width=250, anchor='w')

        vsb = ttk.Scrollbar(self.parser_tab, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.parser_tab, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        self.parser_tab.grid_columnconfigure(0, weight=1)
        self.parser_tab.grid_rowconfigure(0, weight=1)

        # Tab 3: 文法集合 (Treeview)
        self.sets_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sets_frame, text=" 文法集合 (Sets) ")

        # 定义三列：左部(右对齐), 符号(居中), 右部(左对齐)
        sets_cols = ("left", "op", "right")
        self.sets_tree = ttk.Treeview(self.sets_frame, columns=sets_cols, show='headings', style="Sets.Treeview")

        # 配置列
        self.sets_tree.heading("left", text="文法/集合 左部")
        self.sets_tree.column("left", width=350, anchor='e')  # 右对齐 -> 往中间靠

        self.sets_tree.heading("op", text="符号")
        self.sets_tree.column("op", width=50, anchor='center') # 居中

        self.sets_tree.heading("right", text="文法右部 / 集合内容")
        self.sets_tree.column("right", width=500, anchor='w')  # 左对齐 -> 往中间靠

        # --- 关键：配置表头行的 Tag 样式 ---
        # background: 浅灰色背景，显眼
        # font: 加粗，大一号
        self.sets_tree.tag_configure("header", background="#e1e1e1", foreground="#000000", font=("Microsoft YaHei", 10, "bold"))

        vsb_sets = ttk.Scrollbar(self.sets_frame, orient="vertical", command=self.sets_tree.yview)
        hsb_sets = ttk.Scrollbar(self.sets_frame, orient="horizontal", command=self.sets_tree.xview)
        self.sets_tree.configure(yscrollcommand=vsb_sets.set, xscrollcommand=hsb_sets.set)

        self.sets_tree.grid(row=0, column=0, sticky='nsew')
        vsb_sets.grid(row=0, column=1, sticky='ns')
        hsb_sets.grid(row=1, column=0, sticky='ew')
        self.sets_frame.grid_columnconfigure(0, weight=1)
        self.sets_frame.grid_rowconfigure(0, weight=1)

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

        self.notebook.select(0)
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

        try:
            parser = LL1Parser()
        except Exception as e:
            messagebox.showerror("文法构建错误", f"构建预测分析表时出错:\n{e}")
            return

        if hasattr(parser, 'calc_sets'):
            sets_data = parser.calc_sets()
            self.display_sets(parser, sets_data)

        records, success, message = parser.analyze(tokens)

        self.notebook.select(1)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for step, stack, inp, prod, action in records:
            self.tree.insert("", tk.END, values=(step, stack, inp, prod, action))

        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("语法错误", message)

    def display_sets(self, parser, sets_data):
        # 清空
        for item in self.sets_tree.get_children():
            self.sets_tree.delete(item)

        def fmt_set(s):
            elements = sorted(list(s))
            return "{" + ", ".join(elements) + "}"

        # --- 核心辅助函数：插入显眼的表头 ---
        def add_section_header(title_left, title_right):
            # 插入一个空行（白色背景）
            self.sets_tree.insert("", tk.END, values=("", "", ""))

            # 构造左右填充的文本
            # 左边：====== TitlePart1
            # 右边：TitlePart2 ======
            # 中间：留空

            fill_char = "=" * 30 # 大量的等号
            val_left = f"{fill_char} {title_left}"
            val_right = f"{title_right} {fill_char}"

            # 插入带 tag 的行
            self.sets_tree.insert("", tk.END, values=(val_left, "", val_right), tags=("header",))

        def add_row(left, op, right):
            self.sets_tree.insert("", tk.END, values=(left, op, right))

        # ====== 1. 文法定义 ======
        # 将标题拆分为 "文法定义" 和 "G[S]"，分别放在左右两列
        add_section_header("文法定义", "G[S]")
        for lhs, rhss in parser.grammar.prods.items():
            lhs_disp = parser.display(lhs)
            rhs_texts = []
            for rhs in rhss:
                if rhs == ['epsilon']:
                    rhs_texts.append("ε")
                else:
                    rhs_texts.append(" ".join(parser.display(s) for s in rhs))
            add_row(lhs_disp, "->", ' | '.join(rhs_texts))

        # ====== 2. FIRST 集 ======
        add_section_header("FIRST", "集合")
        first = sets_data.get('first', {})
        for nt in sorted(first.keys()):
            name = parser.display(nt)
            add_row(f"First({name})", "=", fmt_set(first[nt]))

        # ====== 3. FOLLOW 集 ======
        add_section_header("FOLLOW", "集合")
        follow = sets_data.get('follow', {})
        for nt in sorted(follow.keys()):
            name = parser.display(nt)
            add_row(f"Follow({name})", "=", fmt_set(follow[nt]))

        # ====== 4. SELECT 集 ======
        add_section_header("SELECT", "集合")
        select = sets_data.get('select', {})
        sorted_select = sorted(select.items(), key=lambda x: x[0][0])

        for (lhs, rhs_tuple), terms in sorted_select:
            lhs_disp = parser.display(lhs)
            rhs_list = list(rhs_tuple)
            if not rhs_list or rhs_list == ["epsilon"]:
                rhs_str = "ε"
            else:
                rhs_str = " ".join(parser.display(s) for s in rhs_list)

            prod_str = f"{lhs_disp} -> {rhs_str}"
            add_row(f"Select({prod_str})", "=", fmt_set(terms))

    def clear_all(self):
        self.input_text.delete("1.0", tk.END)
        self.lexer_tab.config(state='normal')
        self.lexer_tab.delete("1.0", tk.END)
        self.lexer_tab.config(state='disabled')
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.sets_tree.get_children():
            self.sets_tree.delete(item)

if __name__ == '__main__':
    app = LexerApp()
    app.mainloop()
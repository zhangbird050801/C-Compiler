"""
C 语言编译器实验 - 完整编译流程可视化
"""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, messagebox, ttk, font
from lexer_core import Lexer, TYPES, EOF

try:
    from parser_core import LL1Parser
except ImportError:
    LL1Parser = None

try:
    from compiler import Compiler
    COMPILER_AVAILABLE = True
except ImportError:
    COMPILER_AVAILABLE = False
    Compiler = None

try:
    from ast_core import ASTRenderer
except ImportError:
    ASTRenderer = None

try:
    from semantic_analyzer import SemanticAnalyzer
except ImportError:
    SemanticAnalyzer = None

try:
    from ir_generator import IRGenerator
except ImportError:
    IRGenerator = None

try:
    from codegen import CodeGen
except ImportError:
    CodeGen = None

class LexerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("C 语言编译器实验 - 完整编译流程")
        self.geometry("1400x900")
        self.cn_font_family = self.choose_font_family([
            "Microsoft YaHei UI", "Microsoft YaHei", "SimSun", "NSimSun", "Arial"
        ])
        self.text_font_family = self.choose_font_family([
            "NSimSun", "SimSun", "Microsoft YaHei UI", "Microsoft YaHei", "Consolas"
        ])
        self.text_font = font.Font(family=self.text_font_family, size=11)
        self.ui_font = font.Font(family=self.cn_font_family, size=10)
        self.header_font = font.Font(family=self.cn_font_family, size=11, weight="bold")

        # --- 样式配置 ---
        style = ttk.Style()
        # 设置 Treeview 行高，避免太拥挤
        style.configure("Treeview", font=(self.cn_font_family, 10), rowheight=28)
        style.configure("Treeview.Heading", font=(self.cn_font_family, 10, "bold"))
        style.configure("Sets.Treeview", font=(self.cn_font_family, 10), rowheight=28)
        style.configure("Sets.Treeview.Heading", font=(self.cn_font_family, 10, "bold"))

        self.create_widgets()

    def choose_font_family(self, candidates):
        available = set(font.families(self))
        for family in candidates:
            if family in available:
                return family
        return "TkDefaultFont"

    def create_widgets(self):
        # 顶部按钮区
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill='x')

        ttk.Button(top_frame, text="1. 加载 C 文件", command=self.load_file).pack(side='left', padx=5)
        ttk.Button(top_frame, text="2. 运行词法分析", command=self.run_analysis).pack(side='left', padx=5)
        ttk.Button(top_frame, text="3. 生成分析表 & 集合", command=self.run_parser).pack(side='left', padx=5)
        ttk.Button(top_frame, text="4. 完整编译", command=self.run_full_compile).pack(side='left', padx=5)
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
        self.sets_tree.tag_configure("header", background="#e1e1e1", foreground="#000000", font=(self.cn_font_family, 10, "bold"))
        self.sets_tree.column("left", width=520, anchor='w')
        self.sets_tree.column("right", width=650, anchor='w')
        self.sets_tree.tag_configure("header", background="#e1e1e1", foreground="#000000", font=(self.cn_font_family, 10, "bold"))

        vsb_sets = ttk.Scrollbar(self.sets_frame, orient="vertical", command=self.sets_tree.yview)
        hsb_sets = ttk.Scrollbar(self.sets_frame, orient="horizontal", command=self.sets_tree.xview)
        self.sets_tree.configure(yscrollcommand=vsb_sets.set, xscrollcommand=hsb_sets.set)

        self.sets_tree.grid(row=0, column=0, sticky='nsew')
        vsb_sets.grid(row=0, column=1, sticky='ns')
        hsb_sets.grid(row=1, column=0, sticky='ew')
        self.sets_frame.grid_columnconfigure(0, weight=1)
        self.sets_frame.grid_rowconfigure(0, weight=1)

        # Tab 4: 语义分析与符号表
        self.semantic_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.semantic_tab, text=" 语义分析 & 符号表 ")
        
        semantic_cols = ("name", "type", "kind", "scope", "offset")
        self.semantic_tree = ttk.Treeview(self.semantic_tab, columns=semantic_cols, show='headings')
        
        self.semantic_tree.heading("name", text="名称"); self.semantic_tree.column("name", width=150, anchor='w')
        self.semantic_tree.heading("type", text="类型"); self.semantic_tree.column("type", width=200, anchor='w')
        self.semantic_tree.heading("kind", text="种类"); self.semantic_tree.column("kind", width=100, anchor='center')
        self.semantic_tree.heading("scope", text="作用域"); self.semantic_tree.column("scope", width=80, anchor='center')
        self.semantic_tree.heading("offset", text="偏移"); self.semantic_tree.column("offset", width=80, anchor='center')
        
        vsb_sem = ttk.Scrollbar(self.semantic_tab, orient="vertical", command=self.semantic_tree.yview)
        hsb_sem = ttk.Scrollbar(self.semantic_tab, orient="horizontal", command=self.semantic_tree.xview)
        self.semantic_tree.configure(yscrollcommand=vsb_sem.set, xscrollcommand=hsb_sem.set)
        self.semantic_tree.grid(row=0, column=0, sticky='nsew')
        vsb_sem.grid(row=0, column=1, sticky='ns')
        hsb_sem.grid(row=1, column=0, sticky='ew')
        self.semantic_tab.grid_columnconfigure(0, weight=1)
        self.semantic_tab.grid_rowconfigure(0, weight=1)

        # Tab 5: 中间代码（四元式）
        self.ir_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.ir_tab, text=" 中间代码（四元式） ")
        
        ir_cols = ("index", "op", "arg1", "arg2", "result", "readable")
        self.ir_tree = ttk.Treeview(self.ir_tab, columns=ir_cols, show='headings')
        
        self.ir_tree.heading("index", text="序号"); self.ir_tree.column("index", width=50, anchor='center')
        self.ir_tree.heading("op", text="操作符"); self.ir_tree.column("op", width=80, anchor='center')
        self.ir_tree.heading("arg1", text="参数1"); self.ir_tree.column("arg1", width=120, anchor='w')
        self.ir_tree.heading("arg2", text="参数2"); self.ir_tree.column("arg2", width=120, anchor='w')
        self.ir_tree.heading("result", text="结果"); self.ir_tree.column("result", width=120, anchor='w')
        self.ir_tree.heading("readable", text="可读形式"); self.ir_tree.column("readable", width=300, anchor='w')
        
        vsb_ir = ttk.Scrollbar(self.ir_tab, orient="vertical", command=self.ir_tree.yview)
        hsb_ir = ttk.Scrollbar(self.ir_tab, orient="horizontal", command=self.ir_tree.xview)
        self.ir_tree.configure(yscrollcommand=vsb_ir.set, xscrollcommand=hsb_ir.set)
        self.ir_tree.grid(row=0, column=0, sticky='nsew')
        vsb_ir.grid(row=0, column=1, sticky='ns')
        hsb_ir.grid(row=1, column=0, sticky='ew')
        self.ir_tab.grid_columnconfigure(0, weight=1)
        self.ir_tab.grid_rowconfigure(0, weight=1)

        # Tab 6: 目标代码（汇编）
        self.asm_tab = scrolledtext.ScrolledText(self.notebook, wrap=tk.NONE, font=self.text_font, state='disabled')
        self.notebook.add(self.asm_tab, text=" 目标代码（汇编） ")

        # Tab 7: 基础 AST
        self.basic_ast_tab = scrolledtext.ScrolledText(self.notebook, wrap=tk.NONE, font=self.text_font, state='disabled')
        self.notebook.add(self.basic_ast_tab, text=" 基础AST ")

        # Tab 8: 题目2 注释语法树
        self.annotated_tree_tab = scrolledtext.ScrolledText(self.notebook, wrap=tk.NONE, font=self.text_font, state='disabled')
        self.annotated_tree_tab.tag_configure("control_flow", foreground="#c00000")
        self.notebook.add(self.annotated_tree_tab, text=" 注释AST/回填树 ")

        # Tab 9: 回填检查
        self.backpatch_tab = scrolledtext.ScrolledText(self.notebook, wrap=tk.NONE, font=self.text_font, state='disabled')
        self.notebook.add(self.backpatch_tab, text=" 回填检查 ")

        self.paned_window.add(output_frame, weight=3)

        self.load_default_source()

    def load_default_source(self):
        default_file = Path(__file__).resolve().parent / "c-code.c"
        if default_file.exists() and not self.input_text.get("1.0", tk.END).strip():
            self.input_text.insert("1.0", default_file.read_text(encoding="utf-8"))

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

    def run_full_compile(self):
        """运行完整编译流程"""
        if not COMPILER_AVAILABLE:
            messagebox.showerror("错误", "编译器模块未找到，请确保 compiler.py 存在")
            return
        
        code = self.input_text.get("1.0", tk.END).strip()
        if not code:
            messagebox.showwarning("警告", "请输入或加载C源代码")
            return
        
        try:
            compiler = Compiler()
            result = compiler.compile(code, verbose=False)
            
            if result.success:
                self.lexer_tab.config(state='normal')
                self.lexer_tab.delete("1.0", tk.END)
                for token in result.tokens:
                    t_type = TYPES.get(token.type, 'UNK')
                    self.lexer_tab.insert(tk.END, f"[L{token.line:<2}] ({t_type:<15} : {token.attribute})\n")
                self.lexer_tab.config(state='disabled')

                for item in self.tree.get_children():
                    self.tree.delete(item)
                for step, stack, inp, prod, action in result.parse_records:
                    self.tree.insert("", tk.END, values=(step, stack, inp, prod, action))

                if LL1Parser is not None:
                    parser = LL1Parser()
                    if hasattr(parser, 'calc_sets'):
                        self.display_sets(parser, parser.calc_sets())

                # 显示语义分析结果（符号表）
                for item in self.semantic_tree.get_children():
                    self.semantic_tree.delete(item)
                
                if result.symbol_table:
                    for name, symbol in result.symbol_table.global_scope.symbols.items():
                        kind_str = symbol.kind.value if symbol.kind else ""
                        type_str = str(symbol.type_info) if symbol.type_info else ""
                        self.semantic_tree.insert("", tk.END, 
                            values=(name, type_str, kind_str, symbol.scope_level, symbol.offset))
                
                # 显示中间代码（四元式）
                for item in self.ir_tree.get_children():
                    self.ir_tree.delete(item)
                
                for i, quad in enumerate(result.quadruples):
                    self.ir_tree.insert("", tk.END,
                        values=(i, quad.op, quad.arg1, quad.arg2, quad.result, quad.to_readable()))
                
                # 显示目标代码（汇编）
                self.asm_tab.config(state='normal')
                self.asm_tab.delete("1.0", tk.END)
                self.asm_tab.insert("1.0", result.assembly_code)
                self.asm_tab.config(state='disabled')

                basic_ast_text = ""
                if result.ast is not None and ASTRenderer is not None:
                    basic_ast_text = ASTRenderer().render(result.ast)
                elif result.ast is not None:
                    basic_ast_text = str(result.ast)

                self.basic_ast_tab.config(state='normal')
                self.basic_ast_tab.delete("1.0", tk.END)
                self.basic_ast_tab.insert("1.0", basic_ast_text)
                self.basic_ast_tab.config(state='disabled')

                self.annotated_tree_tab.config(state='normal')
                self.annotated_tree_tab.delete("1.0", tk.END)
                self.annotated_tree_tab.insert("1.0", result.annotated_syntax_tree)
                self.apply_ast_highlights()
                self.annotated_tree_tab.config(state='disabled')

                self.backpatch_tab.config(state='normal')
                self.backpatch_tab.delete("1.0", tk.END)
                self.backpatch_tab.insert("1.0", result.backpatch_report)
                self.backpatch_tab.config(state='disabled')

                output_dir = Path(__file__).resolve().parent
                output_asm = output_dir / "output.asm"
                masm_asm = output_dir / "c-code.asm"
                output_ir = output_dir / "output.ir"
                basic_ast_tree = output_dir / "basic_ast_tree.txt"
                annotated_tree = output_dir / "annotated_syntax_tree.txt"
                annotated_tree_html = output_dir / "annotated_syntax_tree.html"
                backpatch_report = output_dir / "backpatch_report.txt"
                output_asm.write_text(result.assembly_code, encoding="utf-8")
                masm_asm.write_text(result.assembly_code, encoding="utf-8")
                output_ir.write_text("\n".join(
                    f"{idx:4d}  {quad.to_readable()}" for idx, quad in enumerate(result.quadruples)
                ), encoding="utf-8")
                basic_ast_tree.write_text(basic_ast_text, encoding="utf-8")
                annotated_tree.write_text(result.annotated_syntax_tree, encoding="utf-8")
                annotated_tree_html.write_text(self.ast_to_html(result.annotated_syntax_tree), encoding="utf-8")
                backpatch_report.write_text(result.backpatch_report, encoding="utf-8")
                
                # 切换到语义分析选项卡
                self.notebook.select(0)
                
                messagebox.showinfo("成功", 
                    f"编译成功！\n"
                    f"- 识别 {len(result.tokens)} 个token\n"
                    f"- 符号表包含 {len(result.symbol_table.global_scope.symbols)} 个符号\n"
                    f"- 生成 {len(result.quadruples)} 条四元式\n"
                    f"- 生成 {len(result.assembly_code.split(chr(10)))} 行汇编代码\n"
                    f"- 已保存基础AST basic_ast_tree.txt\n"
                    f"- 已保存注释语法树 annotated_syntax_tree.txt\n"
                    f"- 已保存彩色语法树 annotated_syntax_tree.html\n"
                    f"- 已保存回填检查 backpatch_report.txt")
            else:
                error_msg = "\n".join(result.errors[:5])
                messagebox.showerror("编译失败", f"编译过程中出现错误：\n\n{error_msg}")
        
        except Exception as e:
            messagebox.showerror("错误", f"编译器内部错误：\n{str(e)}")
            import traceback
            traceback.print_exc()

    def apply_ast_highlights(self):
        """Highlight while/if control-flow lines in the annotated AST tab."""
        self.annotated_tree_tab.tag_remove("control_flow", "1.0", tk.END)
        keywords = ("WHILE_STMT", "IF_STMT", "[control:", "[false ->", "[loop_body:", "[loop_back ->")
        line_count = int(self.annotated_tree_tab.index("end-1c").split(".")[0])
        for line_no in range(1, line_count + 1):
            line_start = f"{line_no}.0"
            line_end = f"{line_no}.end"
            text = self.annotated_tree_tab.get(line_start, line_end)
            if any(keyword in text for keyword in keywords):
                self.annotated_tree_tab.tag_add("control_flow", line_start, line_end)

    def ast_to_html(self, ast_text):
        """Create an HTML copy with while/if control-flow lines highlighted."""
        import html

        keywords = ("WHILE_STMT", "IF_STMT", "[control:", "[false ->", "[loop_body:", "[loop_back ->")
        body_lines = []
        for line in ast_text.splitlines():
            escaped = html.escape(line)
            if any(keyword in line for keyword in keywords):
                body_lines.append(f'<span class="control">{escaped}</span>')
            else:
                body_lines.append(escaped)

        return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
body { font-family: NSimSun, SimSun, "Microsoft YaHei UI", monospace; }
pre { font-size: 15px; line-height: 1.45; white-space: pre; }
.control { color: #c00000; font-weight: 700; }
</style>
</head>
<body>
<pre>""" + "\n".join(body_lines) + """</pre>
</body>
</html>
"""

    def clear_all(self):
        self.input_text.delete("1.0", tk.END)
        self.lexer_tab.config(state='normal')
        self.lexer_tab.delete("1.0", tk.END)
        self.lexer_tab.config(state='disabled')
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.sets_tree.get_children():
            self.sets_tree.delete(item)
        for item in self.semantic_tree.get_children():
            self.semantic_tree.delete(item)
        for item in self.ir_tree.get_children():
            self.ir_tree.delete(item)
        self.asm_tab.config(state='normal')
        self.asm_tab.delete("1.0", tk.END)
        self.asm_tab.config(state='disabled')
        self.basic_ast_tab.config(state='normal')
        self.basic_ast_tab.delete("1.0", tk.END)
        self.basic_ast_tab.config(state='disabled')
        self.annotated_tree_tab.config(state='normal')
        self.annotated_tree_tab.delete("1.0", tk.END)
        self.annotated_tree_tab.config(state='disabled')
        self.backpatch_tab.config(state='normal')
        self.backpatch_tab.delete("1.0", tk.END)
        self.backpatch_tab.config(state='disabled')

if __name__ == '__main__':
    app = LexerApp()
    app.mainloop()

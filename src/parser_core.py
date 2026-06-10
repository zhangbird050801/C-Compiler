from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Set, Optional

from constants import TYPES, EOF

EPS = "epsilon"
# 用于输出的中文别名
ALIAS = {
    "S": "程序",
    "Decl": "声明",
    "TypedefDecl": "类型别名声明",
    "TypedefRhs": "typedef右部",
    "TypedefStruct": "typedef结构体",
    "TypedefStructHead": "typedef结构体头",
    "TypedefStructTail": "typedef结构体尾",
    "TypeAlias": "类型别名",
    "StructDecl": "结构体声明",
    "StructHead": "结构体头",
    "StructAfterTag": "结构体标签后缀",
    "AfterStructBody": "结构体体后缀",
    "Type": "类型",
    "BaseType": "基础类型",
    "Ptr": "指针",
    "DeclSuf": "声明后缀",
    "VarTail": "变量尾部",
    "VarSuf": "变量后缀",
    "InitOpt": "可选初始化",
    "NextDecl": "后续声明",
    "Init": "初始化",
    "InitList": "初始化列表",
    "NextInit": "后续初始化",
    "MemberList": "成员列表",
    "Member": "成员",
    "MemberType": "成员类型",
    "Block": "语句块",
    "StmtList": "语句序列",
    "Stmt": "语句",
    "DeclStmt": "声明语句",
    "RetStmt": "返回语句",
    "RetVal": "返回值",
    "IfStmt": "条件语句",
    "ElsePart": "else分支",
    "ForStmt": "循环语句",
    "ForInit": "循环初始化",
    "ExprOpt": "可选表达式",
    "ForStep": "循环步进",
    "SimpleStmt": "简单语句",
    "AssignOrCall": "赋值或调用",
    "AssignOp": "赋值运算符",
    "Expr": "表达式",
    "E_": "表达式续",
    "Term": "项",
    "Unary": "一元运算",
    "TermSuf": "项后缀",
    "Params": "形参列表",
    "Args": "实参列表",
    "NextArg": "后续实参",
    "int_lit": "整型常量",
    "float_lit": "浮点常量",
    "char_lit": "字符常量",
    "string_lit": "字符串常量",
    "id": "标识符",
    "type_id": "类型标识符",
}


@dataclass(frozen=True)
class Grammar:
    start: str
    prods: Dict[str, List[List[str]]]

    @property
    def nonterminals(self) -> Set[str]:
        return set(self.prods.keys())

    @property
    def terminals(self) -> Set[str]:
        nts = self.nonterminals
        ts: Set[str] = set()
        for alts in self.prods.values():
            for rhs in alts:
                for s in rhs:
                    if s != EPS and s not in nts:
                        ts.add(s)
        ts.add("EOF")
        return ts


def c_grammar() -> Grammar:
    # 这里定义的是当前编译器支持的 C 子集 LL(1) 文法。
    # 语法分析阶段只判断 token 序列是否能按这些产生式推导出来。
    g: Dict[str, List[List[str]]] = {
        # S 是开始符号，表示一个程序由若干声明组成，也可以为空。
        "S": [["Decl", "S"], [EPS]],

        # 顶层声明分为 typedef、结构体声明、普通声明/函数定义。
        "Decl": [["TypedefDecl"], ["StructDecl"], ["NonStructDecl"]],
        "NonStructDecl": [["Type", "id", "DeclSuf"]],

        "TypedefDecl": [["typedef", "TypedefRhs", ";"]],
        "TypedefRhs": [["Type", "TypeAlias"], ["TypedefStruct"]],
        "TypedefStruct": [["struct", "TypedefStructHead"]],
        "TypedefStructHead": [["{", "MemberList", "}", "TypeAlias"], ["id", "TypedefStructTail"]],
        "TypedefStructTail": [["{", "MemberList", "}", "TypeAlias"], ["TypeAlias"]],
        "TypeAlias": [["id"]],

        "StructDecl": [["struct", "StructHead"]],
        "StructHead": [["id", "StructAfterTag"], ["type_id", "StructAfterTag"], ["{", "MemberList", "}", "AfterStructBody"]],
        "StructAfterTag": [["{", "MemberList", "}", "AfterStructBody"], ["Ptr", "id", "DeclSuf"]],
        "AfterStructBody": [[";"], ["Ptr", "id", "DeclSuf"]],

        "Type": [["BaseType", "Ptr"], ["type_id", "Ptr"]],
        "BaseType": [["int"], ["char"], ["float"], ["double"], ["void"], ["long"], ["short"], ["signed"], ["unsigned"]],
        "Ptr": [["*", "Ptr"], [EPS]],

        "DeclSuf": [["(", "Params", ")", "Block"], ["VarTail"]],

        "VarTail": [["VarSuf", "InitOpt", "NextDecl"]],
        "VarSuf": [["[", "int_lit", "]"], [EPS]],
        "InitOpt": [["=", "Init"], [EPS]],
        "NextDecl": [[";"], [",", "id", "VarTail"]],

        "Init": [["{", "InitList", "}"], ["Expr"]],
        "InitList": [["Init", "NextInit"]],
        "NextInit": [[",", "InitList"], [EPS]],

        "MemberList": [["Member", "MemberList"], [EPS]],
        "Member": [["MemberType", "id", "VarSuf", ";"]],
        "MemberType": [["Type"], ["struct", "id", "Ptr"]],

        # 代码块由一对大括号包住，内部是语句序列。
        "Block": [["{", "StmtList", "}"]],
        "StmtList": [["Stmt", "StmtList"], [EPS]],

        # Stmt 是语句分发入口；遇到 while/if/for 时会选择对应产生式。
        "Stmt": [["DeclStmt"], ["RetStmt"], ["IfStmt"], ["WhileStmt"], ["ForStmt"], ["Block"], ["SimpleStmt", ";"]],

        "DeclStmt": [["Decl"]],

        "RetStmt": [["return", "RetVal", ";"]],
        "RetVal": [["Expr"], [EPS]],

        # if 后必须是括号表达式，再跟一个语句；这个语句可以是单句或代码块。
        "IfStmt": [["if", "(", "Expr", ")", "Stmt", "ElsePart"]],
        "ElsePart": [["else", "Stmt"], [EPS]],

        # while 后必须是括号表达式，再跟循环体语句。
        "WhileStmt": [["while", "(", "Expr", ")", "Stmt"]],

        # for 括号内固定拆成 init、condition、step 三段。
        "ForStmt": [["for", "(", "ForInit", ";", "ExprOpt", ";", "ForStep", ")", "Stmt"]],
        "ForInit": [["DeclStmt"], ["SimpleStmt"], [EPS]],
        "ExprOpt": [["Expr"], [EPS]],
        "ForStep": [["SimpleStmt"], [EPS]],

        "SimpleStmt": [["id", "AssignOrCall"]],
        "AssignOrCall": [["AssignOp", "Expr"], ["(", "Args", ")"], ["++"], ["--"], [".", "id", "AssignOrCall"], ["[", "Expr", "]", "AssignOrCall"]],
        "AssignOp": [["="]],

        "Expr": [["Term", "E_"]],
        "E_": [["OP", "Term", "E_"], [EPS]],

        "Term": [["id", "TermSuf"], ["int_lit"], ["float_lit"], ["string_lit"], ["char_lit"], ["(", "Expr", ")"], ["Unary", "Term"]],
        "Unary": [["OP"], ["*"]],

        # Term 后缀支持数组、成员访问以及函数调用
        "TermSuf": [["[", "Expr", "]", "TermSuf"], [".", "id", "TermSuf"], ["(", "Args", ")", "TermSuf"], [EPS]],

        "Params": [["void"], [EPS]],
        "Args": [["Expr", "NextArg"], [EPS]],
        "NextArg": [[",", "Args"], [EPS]],
    }
    return Grammar("S", g)


def first_sets(g: Grammar) -> Dict[str, Set[str]]:
    # FIRST(A) 表示非终结符 A 可以推导出的串的第一个终结符集合。
    nts = g.nonterminals
    ts = g.terminals
    first: Dict[str, Set[str]] = {A: set() for A in nts}

    def f_sym(x: str) -> Set[str]:
        # 终结符的 FIRST 就是它自身，epsilon 的 FIRST 是 epsilon。
        if x == EPS:
            return {EPS}
        if x in ts and x not in nts:
            return {x}
        if x not in nts:
            return {x}
        return first[x]

    # 反复扫描所有产生式，直到没有 FIRST 集继续扩大。
    changed = True
    while changed:
        changed = False
        for A, alts in g.prods.items():
            for rhs in alts:
                # 计算某个产生式右部 rhs 的 FIRST，并合并到 FIRST(A)。
                acc: Set[str] = set()
                nullable = True
                for s in rhs:
                    fs = f_sym(s)
                    acc |= {t for t in fs if t != EPS}
                    if EPS not in fs:
                        nullable = False
                        break
                if nullable:
                    acc.add(EPS)
                if not acc.issubset(first[A]):
                    first[A] |= acc
                    changed = True
    return first


def first_seq(seq: List[str], g: Grammar, first: Dict[str, Set[str]]) -> Set[str]:
    # 计算一个符号串的 FIRST 集，用于 FOLLOW/SELECT 计算。
    ts = g.terminals
    nts = g.nonterminals

    def f_sym(x: str) -> Set[str]:
        if x == EPS:
            return {EPS}
        if x in ts and x not in nts:
            return {x}
        if x not in nts:
            return {x}
        return first[x]

    if not seq:
        return {EPS}
    out: Set[str] = set()
    for s in seq:
        fs = f_sym(s)
        out |= {t for t in fs if t != EPS}
        if EPS not in fs:
            return out
    out.add(EPS)
    return out


def follow_sets(g: Grammar, first: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    # FOLLOW(A) 表示在某个句型里可以紧跟在 A 后面的终结符集合。
    nts = g.nonterminals
    follow: Dict[str, Set[str]] = {A: set() for A in nts}
    # EOF 可以跟在开始符号后面。
    follow[g.start].add("EOF")

    # 反复应用 FOLLOW 规则，直到集合稳定。
    changed = True
    while changed:
        changed = False
        for A, alts in g.prods.items():
            for rhs in alts:
                for i, B in enumerate(rhs):
                    if B not in nts:
                        continue
                    # beta 是 B 后面的符号串；FIRST(beta) 中的非 epsilon 进入 FOLLOW(B)。
                    beta = rhs[i + 1:]
                    fb = first_seq(beta, g, first)
                    add1 = {t for t in fb if t != EPS}
                    if not add1.issubset(follow[B]):
                        follow[B] |= add1
                        changed = True
                    if EPS in fb:
                        # 如果 beta 可以为空，则 FOLLOW(A) 也应该传给 FOLLOW(B)。
                        if not follow[A].issubset(follow[B]):
                            follow[B] |= follow[A]
                            changed = True
    return follow


def select_sets(g: Grammar, first: Dict[str, Set[str]], follow: Dict[str, Set[str]]):
    # SELECT(A -> rhs) 决定预测分析表中何时选择这一条产生式。
    sel: Dict[Tuple[str, Tuple[str, ...]], Set[str]] = {}
    for A, alts in g.prods.items():
        for rhs in alts:
            frhs = first_seq(rhs, g, first)
            s = {t for t in frhs if t != EPS}
            if EPS in frhs:
                # 如果右部能推出空串，则还要加入 FOLLOW(A)。
                s |= follow.get(A, set())
            sel[(A, tuple(rhs))] = s
    return sel


def build_parse_table(select: Dict[Tuple[str, Tuple[str, ...]], Set[str]]):
    # 根据 SELECT 集构造 LL(1) 预测分析表，键是 (非终结符, 当前输入终结符)。
    table: Dict[Tuple[str, str], List[str]] = {}
    conflicts: List[Tuple[str, str, List[str], List[str]]] = []
    for (A, rhs), terms in select.items():
        rhs_list = list(rhs)
        for a in terms:
            key = (A, a)
            if key in table and table[key] != rhs_list:
                conflicts.append((A, a, table[key], rhs_list))
            else:
                table[key] = rhs_list
    return table, conflicts


class LL1Parser:
    def __init__(self, grammar: Optional[Grammar] = None):
        # 默认使用当前文件定义的 C 子集文法。
        self.grammar = grammar or c_grammar()

        # 预测分析表需要 FIRST、FOLLOW、SELECT 三类集合。
        self.first = first_sets(self.grammar)
        self.follow = follow_sets(self.grammar, self.first)
        self.select = select_sets(self.grammar, self.first, self.follow)

        # table 是 LL(1) 分析时真正查询的表。
        self.table, self.conflicts = build_parse_table(self.select)
        self.terminals = self.grammar.terminals

        # typedef/struct 标签会影响标识符是否应被看成 type_id。
        self.typedef_names: Set[str] = set()
        self._capture_typedef_alias = False

    def display(self, sym: str) -> str:
        return ALIAS.get(sym, sym)

    def symbolize(self, tok) -> str:
        # 把词法 token 映射成文法终结符，例如 IDENTIFIER -> id。
        tname = TYPES.get(tok.type, "UNKNOWN")
        attr = tok.attribute

        if tname == "PREPROCESSOR":
            return ""
        if tok.type == EOF or tname == "EOF":
            return "EOF"

        if tname == "KEYWORD":
            # 关键字直接用自身作为终结符，例如 while、if、return。
            return attr
        if tname == "DELIMITER":
            return attr
        if tname == "OPERATOR":
            # 文法只把少数操作符作为字面终结符，其余算术/比较操作符统一成 OP。
            if attr in ["=", ".", "*", "++", "--"]:
                return attr
            return "OP"
        if tname == "IDENTIFIER":
            # 已知类型别名或结构体名在声明场景下映射为 type_id。
            if attr in self.typedef_names:
                return "type_id"
            return "id"
        if tname in ["CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"]:
            return "int_lit"
        if tname == "CONST_FLOAT":
            return "float_lit"
        if tname == "CONST_CHAR":
            return "char_lit"
        if tname == "STRING_LITERAL":
            return "string_lit"

        return tname

    def analyze(self, tokens):
        # 过滤掉预处理和 const，减少文法覆盖压力。
        filtered = [t for t in tokens if TYPES.get(t.type) != "PREPROCESSOR" and t.attribute != "const"]
        # 提前收集 struct 标签名，使后续 student Li 这类声明可识别为类型名。
        for idx, tok in enumerate(filtered[:-2]):
            if self.symbolize(tok) == "struct" and TYPES.get(filtered[idx + 1].type) == "IDENTIFIER" and filtered[idx + 2].attribute == "{":
                self.typedef_names.add(filtered[idx + 1].attribute)

        # 分析栈底是 EOF，栈顶从开始符号 S 开始。
        stack: List[str] = ["EOF", self.grammar.start]
        # ptr 指向当前输入 token。
        ptr = 0
        # records 保存每一步的栈、输入、产生式和动作，用于展示分析过程。
        records = []
        step = 0

        def rest_input_str(i: int) -> str:
            if i >= len(filtered):
                return "#"
            attrs = [t.attribute for t in filtered[i:]]
            return " ".join(attrs) + " #"

        while stack:
            # top 是当前需要处理的栈顶符号。
            top = stack[-1]
            stack_str = " ".join(self.display(s) for s in stack).replace("EOF", "#")
            input_str = rest_input_str(ptr)

            if ptr < len(filtered):
                # lookahead 是当前输入 token 在文法中的终结符形式。
                curr = filtered[ptr]
                lookahead = self.symbolize(curr)
                attr = curr.attribute
                line = curr.line
            else:
                lookahead = "EOF"
                attr = "EOF"
                line = -1

            if top in self.terminals or top == "EOF":
                # “*” 可能被文法当成 OP（乘法）或字面“*”（指针相关）。栈顶若是 OP，允许把“*”视作 OP 匹配。
                if top == "OP" and attr == "*":
                    lookahead = "OP"

                if top == lookahead:
                    # 终结符匹配成功：弹出栈顶，输入指针前进。
                    if top == "id" and self._capture_typedef_alias:
                        self.typedef_names.add(attr)
                        self._capture_typedef_alias = False
                    records.append((step, stack_str, input_str, "", f"“{attr}” 匹配"))
                    stack.pop()
                    ptr += 1
                    if top == "EOF":
                        break
                else:
                    # 栈顶终结符和输入不一致，说明语法匹配失败。
                    return records, False, f"匹配失败：期望 {self.display(top)} 但看到 {attr} (行 {line})"
            else:
                # 非终结符需要查预测分析表，选择一条产生式展开。
                key = (top, lookahead)
                # “*” 既可能是指针/解引用（文法里用"*"），也可能是乘法（文法用 OP）。
                # 如果按字面"*"查不到表项，尝试把它视作 OP 再查一次。
                if key not in self.table and attr == "*":
                    lookahead = "OP"
                    key = (top, lookahead)
                if key not in self.table:
                    # 表项不存在，说明当前 token 无法由该非终结符推导。
                    return records, False, f"文法错误：无法用 {self.display(top)} 匹配 {attr} (行 {line})"

                prod = self.table[key]
                if top == "TypeAlias" and prod == ["id"]:
                    # typedef 别名在匹配 id 时记录下来。
                    self._capture_typedef_alias = True

                prod_disp = " ".join(self.display(s) for s in prod)
                top_disp = self.display(top)
                prod_str = f"{top_disp} -> {prod_disp}" if prod != [EPS] else f"{top_disp} -> ε"
                action_str = f"{top_disp} 弹栈, {prod_disp} 逆序压栈" if prod != [EPS] else f"{top_disp} 弹栈 (空推导)"
                records.append((step, stack_str, input_str, prod_str, action_str))

                stack.pop()
                if prod != [EPS]:
                    # 产生式右部逆序压栈，这样下一步会先处理右部最左符号。
                    for s in reversed(prod):
                        stack.append(s)

            step += 1

        return records, True, "语法分析成功！"

    def calc_sets(self):
        return {"first": self.first, "follow": self.follow, "select": self.select}

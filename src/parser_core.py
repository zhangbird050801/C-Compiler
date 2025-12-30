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
    g: Dict[str, List[List[str]]] = {
        "S": [["Decl", "S"], [EPS]],

        "Decl": [["TypedefDecl"], ["StructDecl"], ["NonStructDecl"]],
        "NonStructDecl": [["Type", "id", "DeclSuf"]],

        "TypedefDecl": [["typedef", "TypedefRhs", ";"]],
        "TypedefRhs": [["Type", "TypeAlias"], ["TypedefStruct"]],
        "TypedefStruct": [["struct", "TypedefStructHead"]],
        "TypedefStructHead": [["{", "MemberList", "}", "TypeAlias"], ["id", "TypedefStructTail"]],
        "TypedefStructTail": [["{", "MemberList", "}", "TypeAlias"], ["TypeAlias"]],
        "TypeAlias": [["id"]],

        "StructDecl": [["struct", "StructHead"]],
        "StructHead": [["id", "StructAfterTag"], ["{", "MemberList", "}", "AfterStructBody"]],
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

        "Block": [["{", "StmtList", "}"]],
        "StmtList": [["Stmt", "StmtList"], [EPS]],

        "Stmt": [["DeclStmt"], ["RetStmt"], ["IfStmt"], ["ForStmt"], ["Block"], ["SimpleStmt", ";"]],

        "DeclStmt": [["Decl"]],

        "RetStmt": [["return", "RetVal", ";"]],
        "RetVal": [["Expr"], [EPS]],

        "IfStmt": [["if", "(", "Expr", ")", "Stmt", "ElsePart"]],
        "ElsePart": [["else", "Stmt"]],

        "ForStmt": [["for", "(", "ForInit", ";", "ExprOpt", ";", "ForStep", ")", "Stmt"]],
        "ForInit": [["DeclStmt"], ["SimpleStmt"], [EPS]],
        "ExprOpt": [["Expr"], [EPS]],
        "ForStep": [["SimpleStmt"], [EPS]],

        "SimpleStmt": [["id", "AssignOrCall"]],
        "AssignOrCall": [["AssignOp", "Expr"], ["(", "Args", ")"], [".", "id", "AssignOrCall"], ["[", "Expr", "]", "AssignOrCall"]],
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
    nts = g.nonterminals
    ts = g.terminals
    first: Dict[str, Set[str]] = {A: set() for A in nts}

    def f_sym(x: str) -> Set[str]:
        if x == EPS:
            return {EPS}
        if x in ts and x not in nts:
            return {x}
        if x not in nts:
            return {x}
        return first[x]

    changed = True
    while changed:
        changed = False
        for A, alts in g.prods.items():
            for rhs in alts:
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
    nts = g.nonterminals
    follow: Dict[str, Set[str]] = {A: set() for A in nts}
    follow[g.start].add("EOF")

    changed = True
    while changed:
        changed = False
        for A, alts in g.prods.items():
            for rhs in alts:
                for i, B in enumerate(rhs):
                    if B not in nts:
                        continue
                    beta = rhs[i + 1:]
                    fb = first_seq(beta, g, first)
                    add1 = {t for t in fb if t != EPS}
                    if not add1.issubset(follow[B]):
                        follow[B] |= add1
                        changed = True
                    if EPS in fb:
                        if not follow[A].issubset(follow[B]):
                            follow[B] |= follow[A]
                            changed = True
    return follow


def select_sets(g: Grammar, first: Dict[str, Set[str]], follow: Dict[str, Set[str]]):
    sel: Dict[Tuple[str, Tuple[str, ...]], Set[str]] = {}
    for A, alts in g.prods.items():
        for rhs in alts:
            frhs = first_seq(rhs, g, first)
            s = {t for t in frhs if t != EPS}
            if EPS in frhs:
                s |= follow.get(A, set())
            sel[(A, tuple(rhs))] = s
    return sel


def build_parse_table(select: Dict[Tuple[str, Tuple[str, ...]], Set[str]]):
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
        self.grammar = grammar or c_grammar()

        self.first = first_sets(self.grammar)
        self.follow = follow_sets(self.grammar, self.first)
        self.select = select_sets(self.grammar, self.first, self.follow)

        self.table, self.conflicts = build_parse_table(self.select)
        self.terminals = self.grammar.terminals

        self.typedef_names: Set[str] = set()
        self._capture_typedef_alias = False

    def display(self, sym: str) -> str:
        return ALIAS.get(sym, sym)

    def symbolize(self, tok) -> str:
        tname = TYPES.get(tok.type, "UNKNOWN")
        attr = tok.attribute

        if tname == "PREPROCESSOR":
            return ""
        if tok.type == EOF or tname == "EOF":
            return "EOF"

        if tname == "KEYWORD":
            return attr
        if tname == "DELIMITER":
            return attr
        if tname == "OPERATOR":
            if attr in ["=", ".", "*"]:
                return attr
            return "OP"
        if tname == "IDENTIFIER":
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
        filtered = [t for t in tokens if TYPES.get(t.type) != "PREPROCESSOR"]

        stack: List[str] = ["EOF", self.grammar.start]
        ptr = 0
        records = []
        step = 0

        def rest_input_str(i: int) -> str:
            if i >= len(filtered):
                return "#"
            attrs = [t.attribute for t in filtered[i:]]
            return " ".join(attrs) + " #"

        while stack:
            top = stack[-1]
            stack_str = " ".join(self.display(s) for s in stack).replace("EOF", "#")
            input_str = rest_input_str(ptr)

            if ptr < len(filtered):
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
                    if top == "id" and self._capture_typedef_alias:
                        self.typedef_names.add(attr)
                        self._capture_typedef_alias = False
                    records.append((step, stack_str, input_str, "", f"“{attr}” 匹配"))
                    stack.pop()
                    ptr += 1
                    if top == "EOF":
                        break
                else:
                    return records, False, f"匹配失败：期望 {self.display(top)} 但看到 {attr} (行 {line})"
            else:
                key = (top, lookahead)
                # “*” 既可能是指针/解引用（文法里用"*"），也可能是乘法（文法用 OP）。
                # 如果按字面"*"查不到表项，尝试把它视作 OP 再查一次。
                if key not in self.table and attr == "*":
                    lookahead = "OP"
                    key = (top, lookahead)
                if key not in self.table:
                    return records, False, f"文法错误：无法用 {self.display(top)} 匹配 {attr} (行 {line})"

                prod = self.table[key]
                if top == "TypeAlias" and prod == ["id"]:
                    self._capture_typedef_alias = True

                prod_disp = " ".join(self.display(s) for s in prod)
                top_disp = self.display(top)
                prod_str = f"{top_disp} -> {prod_disp}" if prod != [EPS] else f"{top_disp} -> ε"
                action_str = f"{top_disp} 弹栈, {prod_disp} 逆序压栈" if prod != [EPS] else f"{top_disp} 弹栈 (空推导)"
                records.append((step, stack_str, input_str, prod_str, action_str))

                stack.pop()
                if prod != [EPS]:
                    for s in reversed(prod):
                        stack.append(s)

            step += 1

        return records, True, "语法分析成功！"

    def calc_sets(self):
        return {"first": self.first, "follow": self.follow, "select": self.select}

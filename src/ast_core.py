from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from constants import TYPES
from ir_generator import IRGenerator
from symbol_table import Symbol, SymbolKind, SymbolTable, Type


@dataclass
class ASTNode:
    """Compiler AST node shared by semantic analysis and IR generation."""
    kind: str
    value: Any = None
    children: List["ASTNode"] = field(default_factory=list)
    line: int = 0
    attrs: Dict[str, Any] = field(default_factory=dict)
    data_type: Optional[str] = None
    place: Optional[str] = None
    false_list: List[int] = field(default_factory=list)
    true_list: List[int] = field(default_factory=list)


class ASTBuilder:
    """Build a compact AST from the token stream after LL(1) validation."""

    type_keywords = {"int", "float", "double", "char", "void", "long", "short", "signed", "unsigned"}
    compare_ops = {"<", ">", "<=", ">=", "==", "!="}
    binary_precedence = [
        {"=", "+=", "-="},
        {"||"},
        {"&&"},
        {"==", "!="},
        {"<", ">", "<=", ">="},
        {"+", "-"},
        {"*", "/", "%"},
    ]

    def __init__(self, tokens: List):
        self.tokens = [
            t for t in tokens
            if TYPES.get(t.type, "") not in {"PREPROCESSOR", "EOF"} and t.attribute != "const"
        ]
        self.n = len(self.tokens)
        self.i = 0
        self.struct_defs: Dict[str, List[Dict[str, Any]]] = {}

    def ttype(self, idx: int) -> str:
        if 0 <= idx < self.n:
            return TYPES.get(self.tokens[idx].type, "")
        return ""

    def attr(self, idx: int) -> str:
        if 0 <= idx < self.n:
            return self.tokens[idx].attribute
        return ""

    def line(self, idx: int) -> int:
        if 0 <= idx < self.n:
            return self.tokens[idx].line
        return 0

    def build(self) -> ASTNode:
        root = ASTNode("PROGRAM", line=1)
        while self.i < self.n:
            if self.attr(self.i) == "struct" and self.ttype(self.i + 1) == "IDENTIFIER" and self.attr(self.i + 2) == "{":
                root.children.append(self.parse_struct_decl())
                continue

            func = self.try_parse_function()
            if func:
                root.children.append(func)
                continue

            stmt = self.parse_statement()
            if stmt:
                root.children.append(stmt)
            else:
                self.i += 1
        return root

    def find_matching(self, idx: int, left: str = "{", right: str = "}") -> int:
        depth = 0
        while idx < self.n:
            if self.attr(idx) == left:
                depth += 1
            elif self.attr(idx) == right:
                depth -= 1
                if depth == 0:
                    return idx
            idx += 1
        return self.n - 1

    def collect_until(self, stops: set) -> List:
        start = self.i
        depth = 0
        while self.i < self.n:
            a = self.attr(self.i)
            if a in {"(", "[", "{"}:
                depth += 1
            elif a in {")", "]", "}"}:
                depth -= 1
            elif depth == 0 and a in stops:
                break
            self.i += 1
        return self.tokens[start:self.i]

    def collect_parenthesized(self, idx: int) -> Tuple[List, int]:
        if self.attr(idx) != "(":
            return [], idx
        end = self.find_matching(idx, "(", ")")
        return self.tokens[idx + 1:end], end + 1

    def split_top_level(self, token_list: List, delimiter: str = ",") -> List[List]:
        parts, cur = [], []
        depth = 0
        for tk in token_list:
            a = tk.attribute
            if a in {"(", "[", "{"}:
                depth += 1
            elif a in {")", "]", "}"}:
                depth -= 1
            if a == delimiter and depth == 0:
                parts.append(cur)
                cur = []
            else:
                cur.append(tk)
        parts.append(cur)
        return parts

    def strip_outer_braces(self, token_list: List) -> List:
        if len(token_list) >= 2 and token_list[0].attribute == "{" and token_list[-1].attribute == "}":
            return token_list[1:-1]
        return token_list

    def parse_type_at(self, idx: int) -> Tuple[Optional[str], int, bool]:
        if self.attr(idx) == "struct" and self.ttype(idx + 1) == "IDENTIFIER":
            return self.attr(idx + 1), idx + 2, True
        if self.ttype(idx) == "KEYWORD" and self.attr(idx) in self.type_keywords:
            return self.attr(idx), idx + 1, False
        if self.ttype(idx) == "IDENTIFIER" and self.attr(idx) in self.struct_defs:
            return self.attr(idx), idx + 1, True
        return None, idx, False

    def parse_declarator_at(self, idx: int) -> Tuple[Optional[Dict[str, Any]], int]:
        pointer = 0
        while self.attr(idx) == "*":
            pointer += 1
            idx += 1
        if self.ttype(idx) != "IDENTIFIER":
            return None, idx
        decl = {"name": self.attr(idx), "line": self.line(idx), "pointer": pointer, "dims": []}
        idx += 1
        while self.attr(idx) == "[":
            idx += 1
            if self.ttype(idx) in {"CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"}:
                decl["dims"].append(int(self.attr(idx), 0))
            while idx < self.n and self.attr(idx) != "]":
                idx += 1
            if self.attr(idx) == "]":
                idx += 1
        return decl, idx

    def parse_struct_decl(self) -> ASTNode:
        line = self.line(self.i)
        name = self.attr(self.i + 1)
        self.i += 3
        fields = []
        children = []
        while self.i < self.n and self.attr(self.i) != "}":
            field_type, after_type, is_struct = self.parse_type_at(self.i)
            if field_type is None:
                self.i += 1
                continue
            decl, idx = self.parse_declarator_at(after_type)
            if decl:
                field = {
                    "name": decl["name"],
                    "type": field_type,
                    "pointer": decl["pointer"],
                    "dims": decl["dims"],
                    "is_struct": is_struct,
                    "line": decl["line"],
                }
                fields.append(field)
                children.append(ASTNode("FIELD_DECL", decl["name"], line=decl["line"], attrs=field))
            self.i = idx
            while self.i < self.n and self.attr(self.i) not in {";", "}"}:
                self.i += 1
            if self.attr(self.i) == ";":
                self.i += 1
        if self.attr(self.i) == "}":
            self.i += 1
        if self.attr(self.i) == ";":
            self.i += 1
        self.struct_defs[name] = fields
        return ASTNode("STRUCT_DECL", name, children=children, line=line, attrs={"fields": fields})

    def try_parse_function(self) -> Optional[ASTNode]:
        ret_type, after_type, _ = self.parse_type_at(self.i)
        if ret_type is None or self.ttype(after_type) != "IDENTIFIER" or self.attr(after_type + 1) != "(":
            return None
        name = self.attr(after_type)
        line = self.line(after_type)
        _, after_params = self.collect_parenthesized(after_type + 1)
        self.i = after_params
        body = self.parse_block() if self.attr(self.i) == "{" else ASTNode("COMPOUND_STMT", line=line)
        return ASTNode("FUNC_DEF", name, children=[body], line=line, attrs={"return_type": ret_type})

    def parse_statement(self) -> Optional[ASTNode]:
        if self.i >= self.n:
            return None
        a = self.attr(self.i)
        if a == "}":
            return None
        if a == "{":
            return self.parse_block()
        if a == "struct" and self.ttype(self.i + 1) == "IDENTIFIER" and self.attr(self.i + 2) == "{":
            return self.parse_struct_decl()
        if a == "if":
            return self.parse_if()
        if a == "while":
            return self.parse_while()
        if a == "for":
            return self.parse_for()
        if a == "return":
            return self.parse_return()
        if a in {"printf", "scanf"}:
            return self.parse_call_statement()

        type_name, _, _ = self.parse_type_at(self.i)
        if type_name is not None and not (self.ttype(self.i + 1) == "IDENTIFIER" and self.attr(self.i + 2) == "("):
            return self.parse_declaration()

        expr_tokens = self.collect_until({";"})
        line = expr_tokens[0].line if expr_tokens else self.line(self.i)
        if self.attr(self.i) == ";":
            self.i += 1
        if not expr_tokens:
            return None
        return ASTNode("EXPR_STMT", children=[self.parse_expr(expr_tokens)], line=line)

    def parse_block(self) -> ASTNode:
        line = self.line(self.i)
        self.i += 1
        children = []
        while self.i < self.n and self.attr(self.i) != "}":
            stmt = self.parse_statement()
            if stmt:
                children.append(stmt)
            else:
                self.i += 1
        if self.attr(self.i) == "}":
            self.i += 1
        return ASTNode("COMPOUND_STMT", children=children, line=line)

    def parse_declaration(self) -> ASTNode:
        type_name, after_type, is_struct = self.parse_type_at(self.i)
        line = self.line(self.i)
        self.i = after_type
        decl_nodes = []
        while self.i < self.n and self.attr(self.i) != ";":
            decl, idx = self.parse_declarator_at(self.i)
            if not decl:
                self.i += 1
                continue
            self.i = idx
            init = None
            if self.attr(self.i) == "=":
                self.i += 1
                init_tokens = self.collect_until({",", ";"})
                init = self.parse_initializer(init_tokens)
            attrs = {
                "type": type_name,
                "is_struct": is_struct,
                "pointer": decl["pointer"],
                "dims": decl["dims"],
            }
            children = [init] if init else []
            decl_nodes.append(ASTNode("VAR_DECL", decl["name"], children=children, line=decl["line"], attrs=attrs))
            if self.attr(self.i) == ",":
                self.i += 1
                continue
            break
        if self.attr(self.i) == ";":
            self.i += 1
        if len(decl_nodes) == 1:
            return decl_nodes[0]
        return ASTNode("DECL_STMT", children=decl_nodes, line=line)

    def parse_initializer(self, token_list: List) -> ASTNode:
        if len(token_list) >= 2 and token_list[0].attribute == "{" and token_list[-1].attribute == "}":
            children = [self.parse_initializer(part) for part in self.split_top_level(self.strip_outer_braces(token_list), ",") if part]
            return ASTNode("INIT_LIST", children=children, line=token_list[0].line)
        return self.parse_expr(token_list)

    def parse_if(self) -> ASTNode:
        line = self.line(self.i)
        cond_tokens, after_cond = self.collect_parenthesized(self.i + 1)
        self.i = after_cond
        then_node = self.parse_statement()
        children = [self.parse_expr(cond_tokens), then_node or ASTNode("EMPTY_STMT", line=line)]
        if self.attr(self.i) == "else":
            self.i += 1
            children.append(self.parse_statement() or ASTNode("EMPTY_STMT", line=line))
        return ASTNode("IF_STMT", children=children, line=line)

    def parse_while(self) -> ASTNode:
        line = self.line(self.i)
        cond_tokens, after_cond = self.collect_parenthesized(self.i + 1)
        self.i = after_cond
        body = self.parse_statement()
        return ASTNode("WHILE_STMT", children=[self.parse_expr(cond_tokens), body or ASTNode("EMPTY_STMT", line=line)], line=line)

    def parse_for(self) -> ASTNode:
        line = self.line(self.i)
        inside_tokens, after_paren = self.collect_parenthesized(self.i + 1)
        sections = self.split_top_level(inside_tokens, ";")
        while len(sections) < 3:
            sections.append([])
        self.i = after_paren
        body = self.parse_statement()
        children = [
            self.parse_expr(sections[0]) if sections[0] else ASTNode("EMPTY_EXPR", line=line),
            self.parse_expr(sections[1]) if sections[1] else ASTNode("EMPTY_EXPR", line=line),
            self.parse_expr(sections[2]) if sections[2] else ASTNode("EMPTY_EXPR", line=line),
            body or ASTNode("EMPTY_STMT", line=line),
        ]
        return ASTNode("FOR_STMT", children=children, line=line)

    def parse_return(self) -> ASTNode:
        line = self.line(self.i)
        self.i += 1
        expr_tokens = self.collect_until({";"})
        if self.attr(self.i) == ";":
            self.i += 1
        children = [self.parse_expr(expr_tokens)] if expr_tokens else []
        return ASTNode("RETURN_STMT", children=children, line=line)

    def parse_call_statement(self) -> ASTNode:
        name = self.attr(self.i)
        line = self.line(self.i)
        args, after_paren = self.collect_parenthesized(self.i + 1)
        self.i = after_paren
        if self.attr(self.i) == ";":
            self.i += 1
        arg_nodes = [self.parse_expr(part) for part in self.split_top_level(args, ",") if part]
        return ASTNode("EXPR_STMT", children=[ASTNode("FUNC_CALL", name, children=arg_nodes, line=line)], line=line)

    def parse_expr(self, token_list: List) -> ASTNode:
        if not token_list:
            return ASTNode("EMPTY_EXPR")

        depth = 0
        for ops in self.binary_precedence:
            scan = range(len(token_list)) if ops == {"=", "+=", "-="} else range(len(token_list) - 1, -1, -1)
            depth = 0
            for idx in scan:
                a = token_list[idx].attribute
                if a in {")", "]", "}"}:
                    depth += 1
                elif a in {"(", "[", "{"}:
                    depth -= 1
                elif depth == 0 and a in ops:
                    left = self.parse_expr(token_list[:idx])
                    right = self.parse_expr(token_list[idx + 1:])
                    kind = "ASSIGN_EXPR" if a in {"=", "+=", "-="} else "BINARY_EXPR"
                    return ASTNode(kind, a, children=[left, right], line=token_list[idx].line)

        if len(token_list) == 2 and token_list[1].attribute in {"++", "--"}:
            return ASTNode("UNARY_EXPR", token_list[1].attribute, children=[self.parse_expr([token_list[0]])], line=token_list[1].line)

        if len(token_list) >= 2 and token_list[0].attribute == "-" and TYPES.get(token_list[0].type, "") == "OPERATOR":
            return ASTNode("UNARY_EXPR", "-", children=[self.parse_expr(token_list[1:])], line=token_list[0].line)

        return self.parse_postfix(token_list)

    def parse_postfix(self, token_list: List) -> ASTNode:
        if not token_list:
            return ASTNode("EMPTY_EXPR")
        if len(token_list) == 1:
            tk = token_list[0]
            ttype = TYPES.get(tk.type, "")
            if ttype == "IDENTIFIER":
                return ASTNode("IDENTIFIER", tk.attribute, line=tk.line)
            return ASTNode("LITERAL", tk.attribute, line=tk.line, attrs={"token_type": ttype})

        if TYPES.get(token_list[0].type, "") != "IDENTIFIER":
            return ASTNode("RAW_EXPR", " ".join(t.attribute for t in token_list), line=token_list[0].line)

        cur = ASTNode("IDENTIFIER", token_list[0].attribute, line=token_list[0].line)
        idx = 1
        while idx < len(token_list):
            a = token_list[idx].attribute
            if a == "." and idx + 1 < len(token_list):
                cur = ASTNode("MEMBER_EXPR", token_list[idx + 1].attribute, children=[cur], line=token_list[idx].line)
                idx += 2
                continue
            if a == "[":
                depth = 1
                start = idx + 1
                idx += 1
                while idx < len(token_list) and depth > 0:
                    if token_list[idx].attribute == "[":
                        depth += 1
                    elif token_list[idx].attribute == "]":
                        depth -= 1
                    idx += 1
                cur = ASTNode("ARRAY_SUBSCRIPT", children=[cur, self.parse_expr(token_list[start:idx - 1])], line=token_list[start - 1].line)
                continue
            if a == "(":
                inside = token_list[idx + 1:-1]
                args = [self.parse_expr(part) for part in self.split_top_level(inside, ",") if part]
                cur = ASTNode("FUNC_CALL", token_list[0].attribute, children=args, line=token_list[0].line)
                break
            break
        return cur


class ASTSemanticAnalyzer:
    """Semantic pass that derives the symbol table by visiting the AST."""

    def __init__(self):
        self.symbol_table = SymbolTable()
        self.errors: List[str] = []

    def analyze(self, root: ASTNode) -> SymbolTable:
        self.visit(root)
        return self.symbol_table

    def error(self, message: str, line: int = 0):
        self.errors.append(f"语义错误 (行 {line}): {message}")

    def visit(self, node: Optional[ASTNode]):
        if node is None:
            return
        method = getattr(self, f"visit_{node.kind.lower()}", self.visit_default)
        return method(node)

    def visit_default(self, node: ASTNode):
        for child in node.children:
            self.visit(child)

    def visit_struct_decl(self, node: ASTNode):
        if self.symbol_table.lookup_struct(node.value):
            self.error(f"结构体重定义: {node.value}", node.line)
            return
        members = {}
        for field in node.attrs.get("fields", []):
            member_type = self.make_type(field)
            members[field["name"]] = Symbol(field["name"], SymbolKind.VARIABLE, member_type)
        self.symbol_table.define(Symbol(node.value, SymbolKind.STRUCT, members=members))

    def visit_func_def(self, node: ASTNode):
        for child in node.children:
            self.visit(child)

    def visit_compound_stmt(self, node: ASTNode):
        for child in node.children:
            self.visit(child)

    def visit_decl_stmt(self, node: ASTNode):
        for child in node.children:
            self.visit(child)

    def visit_var_decl(self, node: ASTNode):
        symbol = Symbol(node.value, SymbolKind.VARIABLE, self.make_type(node.attrs))
        if not self.symbol_table.define(symbol):
            self.error(f"变量重定义: {node.value}", node.line)
        for child in node.children:
            self.visit(child)

    def make_type(self, attrs: Dict[str, Any]) -> Type:
        type_info = Type(
            base=attrs.get("type", "int"),
            pointer_level=attrs.get("pointer", 0),
            is_struct=attrs.get("is_struct", False),
            struct_name=attrs.get("type") if attrs.get("is_struct", False) else None,
        )
        type_info.array_dims.extend(attrs.get("dims", []))
        return type_info


class ASTIRGenerator:
    """Generate quadruples by visiting the AST."""

    supported_compare_ops = {"<", ">", "<=", ">=", "==", "!="}
    inverse_compare = {"<": ">=", ">": "<=", "<=": ">", ">=": "<", "==": "!=", "!=": "=="}

    def __init__(self, ir: IRGenerator, struct_defs: Dict[str, List[Dict[str, Any]]], macros: Optional[Dict[str, str]] = None):
        self.ir = ir
        self.struct_defs = struct_defs
        self.macros = macros or {}
        self.expr_cache: Dict[Tuple, str] = {}

    def generate(self, root: ASTNode):
        self.ir.clear()
        self.gen_stmt(root)

    def gen_stmt(self, node: Optional[ASTNode]):
        if node is None:
            return
        if node.kind in {"PROGRAM", "COMPOUND_STMT", "DECL_STMT"}:
            for child in node.children:
                self.gen_stmt(child)
        elif node.kind == "STRUCT_DECL":
            return
        elif node.kind == "FUNC_DEF":
            for child in node.children:
                self.gen_stmt(child)
        elif node.kind == "VAR_DECL":
            self.gen_var_decl(node)
        elif node.kind == "EXPR_STMT":
            if node.children:
                self.gen_expr(node.children[0])
        elif node.kind == "IF_STMT":
            self.gen_if(node)
        elif node.kind == "WHILE_STMT":
            self.gen_while(node)
        elif node.kind == "FOR_STMT":
            self.gen_for(node)
        elif node.kind == "RETURN_STMT":
            value = self.gen_expr(node.children[0]) if node.children else "_"
            self.ir.emit("return", value or "_", "_", "_")

    def clear_expr_cache(self):
        self.expr_cache.clear()

    def gen_var_decl(self, node: ASTNode):
        if not node.children:
            return
        init = node.children[0]
        if node.attrs.get("is_struct"):
            self.emit_struct_initializer(node.attrs.get("type"), node.value, init)
        elif node.attrs.get("dims"):
            self.emit_array_initializer(node.value, node.attrs.get("dims", [None])[0], init)
        else:
            value = self.gen_expr(init)
            if value is not None:
                self.ir.emit("=", value, "_", node.value)
                self.clear_expr_cache()

    def emit_struct_initializer(self, type_name: str, var_name: str, init: ASTNode):
        members = self.struct_defs.get(type_name, [])
        values = init.children if init and init.kind == "INIT_LIST" else []
        for idx, value_node in enumerate(values):
            if idx >= len(members):
                break
            member = members[idx]
            target = f"{var_name}_{member['name']}"
            if member.get("dims"):
                self.emit_array_initializer(target, member["dims"][0], value_node)
            else:
                value = self.gen_expr(value_node)
                if value is not None:
                    self.ir.emit("=", value, "_", target)
                    self.clear_expr_cache()

    def emit_array_initializer(self, array_name: str, array_size, init: ASTNode):
        values = init.children if init and init.kind == "INIT_LIST" else [init]
        for idx, value_node in enumerate(values):
            if array_size is not None and idx >= array_size:
                break
            value = self.gen_expr(value_node)
            if value is not None:
                self.ir.emit("[]=", value, str(idx), array_name)
                self.clear_expr_cache()

    def gen_if(self, node: ASTNode):
        cond = self.gen_condition(node.children[0])
        false_jumps = self.emit_false_jumps(cond)
        self.gen_stmt(node.children[1])
        if len(node.children) > 2:
            j_end = self.ir.emit("j", "_", "_", "0")
            self.patch_jumps(false_jumps, self.ir.next_quad())
            self.gen_stmt(node.children[2])
            self.patch_jump(j_end, self.ir.next_quad())
        else:
            self.patch_jumps(false_jumps, self.ir.next_quad())

    def gen_while(self, node: ASTNode):
        cond_start = self.ir.next_quad()
        cond = self.gen_condition(node.children[0])
        false_jumps = self.emit_false_jumps(cond)
        self.gen_stmt(node.children[1])
        self.ir.emit("j", "_", "_", str(cond_start))
        self.patch_jumps(false_jumps, self.ir.next_quad())

    def gen_for(self, node: ASTNode):
        self.gen_expr(node.children[0])
        cond_start = self.ir.next_quad()
        false_jumps = []
        if node.children[1].kind != "EMPTY_EXPR":
            false_jumps = self.emit_false_jumps(self.gen_condition(node.children[1]))
        self.gen_stmt(node.children[3])
        self.gen_expr(node.children[2])
        self.ir.emit("j", "_", "_", str(cond_start))
        self.patch_jumps(false_jumps, self.ir.next_quad())

    def gen_condition(self, node: ASTNode):
        if node.kind == "BINARY_EXPR" and node.value == "&&":
            return ("&&", [self.gen_condition(child) for child in node.children])
        if node.kind == "BINARY_EXPR" and node.value in self.supported_compare_ops:
            return self.gen_expr(node.children[0]), node.value, self.gen_expr(node.children[1])
        value = self.gen_expr(node)
        return value, "!=", "0"

    def emit_false_jumps(self, cond) -> List[int]:
        if cond and cond[0] == "&&":
            return [self.emit_inverse_cond_jump(part) for part in cond[1]]
        return [self.emit_inverse_cond_jump(cond)]

    def emit_inverse_cond_jump(self, cond) -> int:
        left, op, right = cond
        return self.ir.emit(f"j{self.inverse_compare.get(op, '==')}", left, right, "0")

    def patch_jump(self, jump_idx: int, target_idx: int):
        if 0 <= jump_idx < len(self.ir.quadruples):
            self.ir.quadruples[jump_idx].result = str(target_idx)

    def patch_jumps(self, jumps: List[int], target_idx: int):
        for jump in jumps:
            self.patch_jump(jump, target_idx)

    def gen_expr(self, node: Optional[ASTNode]) -> Optional[str]:
        if node is None or node.kind == "EMPTY_EXPR":
            return None
        key = self.expr_key(node)
        if key is not None and key in self.expr_cache:
            return self.expr_cache[key]
        if node.kind == "LITERAL":
            value = self.literal_operand(node)
        elif node.kind == "IDENTIFIER":
            value = self.macros.get(node.value, node.value)
        elif node.kind == "MEMBER_EXPR":
            base = self.gen_reference(node.children[0])
            value = f"{base}_{node.value}"
        elif node.kind == "ARRAY_SUBSCRIPT":
            array_name = self.gen_reference(node.children[0])
            index = self.gen_expr(node.children[1])
            temp = self.ir.new_temp()
            self.ir.emit("=[]", array_name, index, temp)
            value = temp
        elif node.kind == "ASSIGN_EXPR":
            target = self.gen_lvalue(node.children[0])
            if node.value in {"+=", "-="}:
                old_value = self.gen_expr(node.children[0])
                rhs = self.gen_expr(node.children[1])
                temp = self.ir.new_temp()
                self.ir.emit("+" if node.value == "+=" else "-", old_value, rhs, temp)
                self.ir.emit("=", temp, "_", target)
                value = target
            else:
                rhs = self.gen_expr(node.children[1])
                self.ir.emit("=", rhs, "_", target)
                value = target
            self.clear_expr_cache()
        elif node.kind == "UNARY_EXPR" and node.value in {"++", "--"}:
            target = self.gen_lvalue(node.children[0])
            temp = self.ir.new_temp()
            self.ir.emit("+" if node.value == "++" else "-", target, "1", temp)
            self.ir.emit("=", temp, "_", target)
            self.clear_expr_cache()
            value = target
        elif node.kind == "UNARY_EXPR" and node.value == "-":
            operand = self.gen_expr(node.children[0])
            if operand and operand.replace(".", "", 1).isdigit():
                value = f"-{operand}"
            else:
                temp = self.ir.new_temp()
                self.ir.emit("-", "0", operand, temp)
                value = temp
        elif node.kind == "BINARY_EXPR":
            left = self.gen_expr(node.children[0])
            right = self.gen_expr(node.children[1])
            temp = self.ir.new_temp()
            self.ir.emit(node.value, left, right, temp)
            value = temp
        elif node.kind == "FUNC_CALL":
            value = self.gen_func_call(node)
        elif node.kind == "INIT_LIST":
            value = None
        else:
            value = node.value
        if key is not None and value is not None:
            self.expr_cache[key] = value
        return value

    def gen_func_call(self, node: ASTNode) -> Optional[str]:
        if node.value == "printf":
            self.emit_printf(node.children)
            return None
        if node.value == "scanf":
            for arg in node.children[1:]:
                self.ir.emit("scanf", "_", "_", self.gen_lvalue(arg))
            return None
        args = [self.gen_expr(arg) for arg in node.children]
        for arg in args:
            self.ir.emit("param", arg, "_", "_")
        temp = self.ir.new_temp()
        self.ir.emit("call", node.value, str(len(args)), temp)
        return temp

    def emit_printf(self, args: List[ASTNode]):
        if not args:
            return
        first = args[0]
        if first.kind == "LITERAL" and first.attrs.get("token_type") == "STRING_LITERAL":
            fmt = first.value
            value_args = [self.gen_expr(arg) for arg in args[1:]]
            value_idx = 0
            literal_buf = []

            def flush_literal():
                if literal_buf:
                    text = "".join(literal_buf)
                    if text:
                        self.ir.emit("printf", "_", "_", f'"{text}"')
                    literal_buf.clear()

            k = 0
            while k < len(fmt):
                ch = fmt[k]
                if ch == "%" and k + 1 < len(fmt):
                    if fmt[k + 1] == "%":
                        literal_buf.append("%")
                        k += 2
                        continue
                    p = k + 1
                    while p < len(fmt) and fmt[p] in "-+ #0":
                        p += 1
                    while p < len(fmt) and fmt[p].isdigit():
                        p += 1
                    precision = None
                    if p < len(fmt) and fmt[p] == ".":
                        p += 1
                        start = p
                        while p < len(fmt) and fmt[p].isdigit():
                            p += 1
                        precision = int(fmt[start:p]) if p > start else 0
                    if p < len(fmt) and fmt[p] in "hlLzjt":
                        p += 1
                    spec = fmt[p] if p < len(fmt) else ""
                    if spec in "diuoxXfFcs":
                        flush_literal()
                        if value_idx < len(value_args):
                            arg_value = value_args[value_idx]
                            value_idx += 1
                            if spec in "fF":
                                op_name = f"printf_f{6 if precision is None else precision}"
                            elif spec == "c":
                                op_name = "printf_c"
                            else:
                                op_name = "printf"
                            self.ir.emit(op_name, "_", "_", arg_value)
                        k = p + 1
                        continue
                literal_buf.append(ch)
                k += 1
            flush_literal()
            while value_idx < len(value_args):
                self.ir.emit("printf", "_", "_", value_args[value_idx])
                value_idx += 1
            return

        for arg in args:
            value = self.gen_expr(arg)
            if value is not None:
                self.ir.emit("printf", "_", "_", value)

    def gen_reference(self, node: ASTNode) -> str:
        if node.kind == "IDENTIFIER":
            return node.value
        if node.kind == "MEMBER_EXPR":
            return f"{self.gen_reference(node.children[0])}_{node.value}"
        return self.gen_expr(node) or "_"

    def gen_lvalue(self, node: ASTNode) -> str:
        if node.kind in {"IDENTIFIER", "MEMBER_EXPR"}:
            return self.gen_reference(node)
        if node.kind == "ARRAY_SUBSCRIPT":
            return self.gen_expr(node) or "_"
        return self.gen_expr(node) or "_"

    def literal_operand(self, node: ASTNode) -> str:
        ttype = node.attrs.get("token_type", "")
        if ttype == "STRING_LITERAL":
            return f'"{node.value}"'
        if ttype == "CONST_CHAR":
            return self.char_to_int(node.value)
        return str(node.value)

    def char_to_int(self, value: str) -> str:
        if not value:
            return "0"
        if len(value) == 1:
            return str(ord(value))
        escapes = {r"\n": 10, r"\r": 13, r"\t": 9, r"\\": 92, r"\'": 39, r'\"': 34, r"\0": 0}
        return str(escapes.get(value, ord(value[-1])))

    def expr_key(self, node: ASTNode):
        if node.kind in {"ARRAY_SUBSCRIPT", "MEMBER_EXPR"}:
            return self.render_expr_key(node)
        return None

    def render_expr_key(self, node: ASTNode):
        return (
            node.kind,
            node.value,
            tuple(self.render_expr_key(child) for child in node.children),
        )


class ASTRenderer:
    """Render AST for debug and answer reports."""

    def render(self, root: ASTNode, quadruples: Optional[List[Any]] = None) -> str:
        self.prepare_control_annotations(quadruples or [])
        lines = [self.label(root)]

        def walk(node: ASTNode, prefix: str, parent: Optional[ASTNode] = None):
            for idx, child in enumerate(node.children):
                last = idx == len(node.children) - 1
                lines.append(prefix + ("`-- " if last else "|-- ") + self.label(child, parent))
                walk(child, prefix + ("    " if last else "|   "), child)

        walk(root, "")
        return "\n".join(lines)

    def prepare_control_annotations(self, quads: List[Any]):
        self.while_false_targets: List[Tuple[int, int]] = []
        self.if_false_targets: List[Tuple[int, int]] = []
        self.loop_back_targets: List[Tuple[int, int]] = []

        for idx, quad in enumerate(quads):
            if quad.op == "j" and quad.result.isdigit() and int(quad.result) <= idx:
                self.loop_back_targets.append((idx, int(quad.result)))

        for idx, quad in enumerate(quads):
            if not (quad.op.startswith("j") and quad.op != "j" and quad.result.isdigit()):
                continue
            has_loop_back = any(back_quad == int(quad.result) - 1 or back_target == idx for back_quad, back_target in self.loop_back_targets)
            if has_loop_back:
                self.while_false_targets.append((idx, int(quad.result)))
            else:
                self.if_false_targets.append((idx, int(quad.result)))

    def label(self, node: ASTNode, parent: Optional[ASTNode] = None) -> str:
        parts = [node.kind]
        if node.value is not None:
            parts.append(f'"{node.value}"')
        if node.line:
            parts.append(f"@{node.line}")
        if node.attrs:
            type_text = self.type_text(node.attrs)
            if type_text:
                parts.append(f"[type: {type_text}]")
            if node.attrs.get("return_type"):
                parts.append(f"[return: {node.attrs['return_type']}]")
        if node.kind == "WHILE_STMT":
            cond_text = self.expr_text(node.children[0]) if node.children else ""
            parts.append(f"[control: while({cond_text})]")
            if self.while_false_targets:
                jump_idx, target = self.while_false_targets.pop(0)
                parts.append(f"[false_list: {{{jump_idx}}} -> quad {target}: exit loop]")
        elif node.kind == "IF_STMT":
            cond_text = self.expr_text(node.children[0]) if node.children else ""
            parts.append(f"[control: if({cond_text})]")
            if self.if_false_targets:
                jump_idx, target = self.if_false_targets.pop(0)
                parts.append(f"[false_list: {{{jump_idx}}} -> quad {target}: skip then]")
        elif node.kind == "COMPOUND_STMT" and parent and parent.kind == "WHILE_STMT":
            parts.append("[loop_body: execute nested statements, then jump back to while condition]")
            if self.loop_back_targets:
                jump_idx, target = self.loop_back_targets.pop(0)
                parts.append(f"[loop_back: quad {jump_idx} -> quad {target}]")
        return "  ".join(parts)

    def type_text(self, attrs: Dict[str, Any]) -> str:
        base = attrs.get("type")
        if not base:
            return ""
        pointer = attrs.get("pointer", 0) or 0
        dims = attrs.get("dims", []) or []
        prefix = f"struct {base}" if attrs.get("is_struct") else str(base)
        return prefix + ("*" * pointer) + "".join(f"[{dim}]" for dim in dims)

    def expr_text(self, node: ASTNode) -> str:
        if node.kind == "BINARY_EXPR":
            return f"{self.expr_text(node.children[0])} {node.value} {self.expr_text(node.children[1])}"
        if node.kind == "ASSIGN_EXPR":
            return f"{self.expr_text(node.children[0])} {node.value} {self.expr_text(node.children[1])}"
        if node.kind == "UNARY_EXPR":
            if node.value in {"++", "--"}:
                return f"{self.expr_text(node.children[0])}{node.value}"
            return f"{node.value}{self.expr_text(node.children[0])}"
        if node.kind == "ARRAY_SUBSCRIPT":
            return f"{self.expr_text(node.children[0])}[{self.expr_text(node.children[1])}]"
        if node.kind == "MEMBER_EXPR":
            return f"{self.expr_text(node.children[0])}.{node.value}"
        if node.kind == "FUNC_CALL":
            return f"{node.value}({', '.join(self.expr_text(child) for child in node.children)})"
        if node.kind in {"IDENTIFIER", "LITERAL"}:
            return str(node.value)
        if node.kind == "INIT_LIST":
            return "{" + ", ".join(self.expr_text(child) for child in node.children) + "}"
        return str(node.value or "")

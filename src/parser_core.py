# parser_core.py
from constants import TYPES, EOF


class LL1Parser:
    def __init__(self):
        # 1. 终结符集合
        self.terminals = [
            'KEYWORD', 'IDENTIFIER', 'OPERATOR', 'DELIMITER',
            'CONST_DECIMAL', 'CONST_OCTAL', 'CONST_HEX',
            'CONST_FLOAT', 'CONST_CHAR', 'STRING_LITERAL', 'EOF'
        ]

        # 2. 预测分析表 (包含针对 DeclSuffix = 的修复)
        self.table = {
            # --- 程序骨架 ---
            ('S', 'struct'): ['Decl', 'S'],
            ('S', 'KEYWORD'): ['Decl', 'S'],
            ('S', 'IDENTIFIER'): ['Decl', 'S'],
            ('S', 'EOF'): ['epsilon'],

            # --- 声明 ---
            ('Decl', 'struct'): ['struct', 'IDENTIFIER', '{', 'MemberList', '}', 'OptSemicolon'],
            ('Decl', 'KEYWORD'): ['Type', 'IDENTIFIER', 'DeclSuffix'],
            ('Decl', 'IDENTIFIER'): ['Type', 'IDENTIFIER', 'DeclSuffix'],

            ('OptSemicolon', ';'): [';'],
            ('OptSemicolon', 'EOF'): ['epsilon'],
            ('OptSemicolon', 'KEYWORD'): ['epsilon'],
            ('OptSemicolon', 'struct'): ['epsilon'],
            ('OptSemicolon', '}'): ['epsilon'],
            ('OptSemicolon', 'IDENTIFIER'): ['epsilon'],

            # --- 结构体成员 ---
            ('MemberList', 'KEYWORD'): ['Member', 'MemberList'],
            ('MemberList', 'IDENTIFIER'): ['Member', 'MemberList'],
            ('MemberList', '}'): ['epsilon'],
            ('Member', 'KEYWORD'): ['Type', 'IDENTIFIER', 'VarSuffix', ';'],
            ('Member', 'IDENTIFIER'): ['Type', 'IDENTIFIER', 'VarSuffix', ';'],

            ('VarSuffix', '['): ['[', 'CONST_DECIMAL', ']'],
            ('VarSuffix', ';'): ['epsilon'],

            # --- 类型系统 (双保险策略) ---
            ('Type', 'KEYWORD'): ['KEYWORD', 'Ptr'],
            ('Type', 'IDENTIFIER'): ['IDENTIFIER', 'Ptr'],

            ('Ptr', '*'): ['*', 'Ptr'],
            ('Ptr', 'OPERATOR'): ['*', 'Ptr'],  # 兼容 * 被识别为 OPERATOR 的情况
            ('Ptr', 'IDENTIFIER'): ['epsilon'],

            # --- 声明后缀 (核心修复点：添加 OPERATOR 映射) ---
            ('DeclSuffix', '('): ['(', 'Params', ')', 'Block'],
            ('DeclSuffix', ';'): [';'],
            ('DeclSuffix', '='): ['=', 'Initializer', 'NextDecl'],
            ('DeclSuffix', 'OPERATOR'): ['=', 'Initializer', 'NextDecl'],  # 修复：int a = 0; 匹配 OPERATOR
            ('DeclSuffix', '['): ['[', 'CONST_DECIMAL', ']', 'OptInitSemicolon'],
            ('DeclSuffix', ','): [',', 'IDENTIFIER', 'DeclSuffix'],

            ('NextDecl', ';'): [';'],
            ('NextDecl', ','): [',', 'IDENTIFIER', 'DeclSuffix'],

            ('OptInitSemicolon', ';'): [';'],
            ('OptInitSemicolon', '='): ['=', 'Initializer', ';'],
            ('OptInitSemicolon', 'OPERATOR'): ['=', 'Initializer', ';'],  # 修复：数组初始化

            # --- 初始化 ---
            ('Initializer', '{'): ['{', 'InitList', '}'],
            ('Initializer', 'IDENTIFIER'): ['Expr'],
            ('Initializer', 'CONST_DECIMAL'): ['Expr'],
            ('Initializer', 'CONST_OCTAL'): ['Expr'],
            ('Initializer', 'CONST_FLOAT'): ['Expr'],
            ('Initializer', 'STRING_LITERAL'): ['Expr'],
            ('Initializer', 'OPERATOR'): ['Expr'],  # 负数
            ('Initializer', '*'): ['Expr'],

            ('InitList', 'IDENTIFIER'): ['Initializer', 'NextInit'],
            ('InitList', 'CONST_DECIMAL'): ['Initializer', 'NextInit'],
            ('InitList', 'CONST_OCTAL'): ['Initializer', 'NextInit'],
            ('InitList', 'CONST_FLOAT'): ['Initializer', 'NextInit'],
            ('InitList', 'STRING_LITERAL'): ['Initializer', 'NextInit'],
            ('InitList', '{'): ['Initializer', 'NextInit'],
            ('InitList', 'OPERATOR'): ['Initializer', 'NextInit'],
            ('InitList', '*'): ['Initializer', 'NextInit'],

            ('NextInit', ','): [',', 'InitList'],
            ('NextInit', '}'): ['epsilon'],

            # --- 语句 ---
            ('Block', '{'): ['{', 'StmtList', '}'],
            ('StmtList', 'KEYWORD'): ['Stmt', 'StmtList'],
            ('StmtList', 'IDENTIFIER'): ['Stmt', 'StmtList'],
            ('StmtList', 'for'): ['Stmt', 'StmtList'],
            ('StmtList', 'if'): ['Stmt', 'StmtList'],
            ('StmtList', '}'): ['epsilon'],

            ('Stmt', 'KEYWORD'): ['Decl'],
            ('Stmt', 'for'): ['ForStmt'],
            ('Stmt', 'if'): ['IfStmt'],
            ('Stmt', '{'): ['Block'],
            ('Stmt', 'IDENTIFIER'): ['DeclOrAssign'],

            # --- If/For ---
            ('IfStmt', 'if'): ['if', '(', 'Expr', ')', 'Stmt', 'ElsePart'],
            ('ElsePart', 'else'): ['else', 'Stmt'],
            ('ElsePart', ';'): ['epsilon'],
            ('ElsePart', '}'): ['epsilon'],
            ('ElsePart', 'KEYWORD'): ['epsilon'],
            ('ElsePart', 'IDENTIFIER'): ['epsilon'],
            ('ElsePart', 'for'): ['epsilon'],
            ('ElsePart', 'if'): ['epsilon'],
            ('ElsePart', 'EOF'): ['epsilon'],

            ('ForStmt', 'for'): ['for', '(', 'ForInit', 'Expr', ';', 'ForStep', ')', 'Stmt'],
            ('ForInit', 'KEYWORD'): ['Decl'],
            ('ForInit', 'IDENTIFIER'): ['SimpleStmt', ';'],
            ('ForStep', 'IDENTIFIER'): ['IDENTIFIER', 'StepSuffix'],
            ('StepSuffix', 'OPERATOR'): ['OPERATOR', 'ExprOpt'],
            ('ExprOpt', 'IDENTIFIER'): ['Expr'],
            ('ExprOpt', 'CONST_DECIMAL'): ['Expr'],
            ('ExprOpt', ')'): ['epsilon'],

            # --- 语句操作 ---
            ('SimpleStmt', 'IDENTIFIER'): ['IDENTIFIER', 'AssignOrCall'],
            ('AssignOrCall', 'OPERATOR'): ['AssignOp', 'Expr'],
            ('AssignOrCall', '('): ['(', 'Args', ')'],
            ('AssignOrCall', '.'): ['.', 'IDENTIFIER', 'AssignOrCall'],
            ('AssignOrCall', '['): ['[', 'Expr', ']', 'AssignOrCall'],

            ('AssignOp', 'OPERATOR'): ['OPERATOR'],

            # --- 表达式 (右递归链式处理) ---
            ('Expr', 'IDENTIFIER'): ['Term', 'E_Prime'],
            ('Expr', 'CONST_DECIMAL'): ['Term', 'E_Prime'],
            ('Expr', 'CONST_OCTAL'): ['Term', 'E_Prime'],
            ('Expr', 'CONST_FLOAT'): ['Term', 'E_Prime'],
            ('Expr', 'STRING_LITERAL'): ['Term', 'E_Prime'],
            ('Expr', 'OPERATOR'): ['Term', 'E_Prime'],
            ('Expr', '*'): ['Term', 'E_Prime'],

            ('E_Prime', 'OPERATOR'): ['OPERATOR', 'Term', 'E_Prime'],
            ('E_Prime', '*'): ['OPERATOR', 'Term', 'E_Prime'],
            ('E_Prime', ';'): ['epsilon'],
            ('E_Prime', ')'): ['epsilon'],
            ('E_Prime', ']'): ['epsilon'],
            ('E_Prime', ','): ['epsilon'],
            ('E_Prime', '}'): ['epsilon'],

            # Term
            ('Term', 'IDENTIFIER'): ['IDENTIFIER', 'TermSuffix'],
            ('Term', 'CONST_DECIMAL'): ['CONST_DECIMAL'],
            ('Term', 'CONST_OCTAL'): ['CONST_OCTAL'],
            ('Term', 'CONST_FLOAT'): ['CONST_FLOAT'],
            ('Term', 'STRING_LITERAL'): ['STRING_LITERAL'],
            ('Term', 'OPERATOR'): ['OPERATOR', 'Term'],
            ('Term', '*'): ['OPERATOR', 'Term'],

            ('TermSuffix', '['): ['[', 'Expr', ']', 'TermSuffix'],
            ('TermSuffix', '.'): ['.', 'IDENTIFIER', 'TermSuffix'],
            ('TermSuffix', 'OPERATOR'): ['epsilon'],
            ('TermSuffix', '*'): ['epsilon'],
            ('TermSuffix', ';'): ['epsilon'],
            ('TermSuffix', ')'): ['epsilon'],
            ('TermSuffix', ','): ['epsilon'],
            ('TermSuffix', ']'): ['epsilon'],

            ('Params', ')'): ['epsilon'],
            ('Args', 'IDENTIFIER'): ['Expr', 'NextArg'],
            ('Args', 'CONST_DECIMAL'): ['Expr', 'NextArg'],
            ('Args', 'STRING_LITERAL'): ['Expr', 'NextArg'],
            ('Args', ')'): ['epsilon'],
            ('NextArg', ','): [',', 'Args'],
            ('NextArg', ')'): ['epsilon']
        }

    def analyze(self, tokens):
        filtered = [t for t in tokens if t.type != 89]
        stack = ['EOF', 'S']
        ptr = 0
        records = []
        step_count = 0

        while len(stack) > 0:
            top = stack[-1]
            stack_str = " ".join(stack).replace("EOF", "#")
            input_str = "".join([t.attribute for t in filtered[ptr:]]) + "#" if ptr < len(filtered) else "#"

            if ptr < len(filtered):
                curr_t = filtered[ptr]
                curr_type = TYPES.get(curr_t.type, 'UNKNOWN')
                if curr_t.type == -1: curr_type = 'EOF'

                # --- 核心逻辑 ---
                # 显式包含 '*' 以支持指针
                # 即使 '=' 没在这里，它会被识别为 OPERATOR，然后命中 DeclSuffix 的 OPERATOR 规则
                if curr_t.attribute in [';', '{', '}', '(', ')', '[', ']', ',', '.', 'for', 'struct', 'if', 'else',
                                        '*']:
                    lookahead = curr_t.attribute
                else:
                    lookahead = curr_type
                attr = curr_t.attribute
            else:
                lookahead = 'EOF'
                attr = 'EOF'

            # --- 运行时消歧 ---
            if top == 'DeclOrAssign' and ptr + 1 < len(filtered):
                next_t = filtered[ptr + 1]
                if TYPES.get(next_t.type) == 'IDENTIFIER' or next_t.attribute == '*':
                    lookahead = 'IDENTIFIER'
                    self.table[('DeclOrAssign', 'IDENTIFIER')] = ['Decl']
                else:
                    stack.pop()
                    stack.append(';')
                    stack.append('SimpleStmt')
                    records.append((step_count, stack_str, input_str, "DeclOrAssign -> SimpleStmt", "预读判定: 语句"))
                    step_count += 1
                    continue

            # --- 匹配逻辑 ---
            match_keyword = (top == 'KEYWORD' and lookahead == 'KEYWORD')

            if top in self.terminals or top in [';', '{', '}', '(', ')', '[', ']', ',', '.', 'for', 'struct', 'if',
                                                'else', 'EOF', '*', '=']:
                if top == lookahead or top == attr or match_keyword:
                    records.append((step_count, stack_str, input_str, "", f"“{attr}” 匹配"))
                    stack.pop()
                    ptr += 1
                    if top == 'EOF': break
                else:
                    return records, False, f"匹配失败：期望 {top} 但看到 {attr} (行 {filtered[ptr].line})"
            else:
                if (top, lookahead) in self.table:
                    prod = self.table[(top, lookahead)]
                    prod_str = f"{top} -> {' '.join(prod)}" if prod != ['epsilon'] else f"{top} -> ε"
                    action_str = f"{top} 弹栈, {' '.join(prod)} 逆序压栈" if prod != [
                        'epsilon'] else f"{top} 弹栈 (空推导)"
                    records.append((step_count, stack_str, input_str, prod_str, action_str))
                    stack.pop()
                    if prod != ['epsilon']:
                        for s in reversed(prod):
                            stack.append(s)
                else:
                    return records, False, f"文法错误：无法用 {top} 匹配 {attr} (行 {filtered[ptr].line})"
            step_count += 1

        return records, True, "语法分析成功！"
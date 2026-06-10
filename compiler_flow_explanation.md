# C Compiler 从 `c-code.c` 到最终结果完整讲解

本文档用于答辩准备。目标是把当前仓库里的实现逻辑讲通：输入 `c-code.c` 后，如何经过词法分析、语法分析、语义分析、四元式生成、回填、目标代码生成，最后得到运行结果。

重点文件位置：

- 输入源码：`C:\Users\Birdy\files\code\C-Compiler\src\c-code.c`
- 编译主流程：`C:\Users\Birdy\files\code\C-Compiler\src\compiler.py`
- 词法分析：`C:\Users\Birdy\files\code\C-Compiler\src\lexer_core.py`
- LL(1) 语法分析：`C:\Users\Birdy\files\code\C-Compiler\src\parser_core.py`
- 语义分析：`C:\Users\Birdy\files\code\C-Compiler\src\semantic_analyzer.py`
- 符号表：`C:\Users\Birdy\files\code\C-Compiler\src\symbol_table.py`
- 四元式类和 IR 生成器：`C:\Users\Birdy\files\code\C-Compiler\src\ir_generator.py`
- 目标代码生成：`C:\Users\Birdy\files\code\C-Compiler\src\codegen.py`
- 当前四元式输出：`C:\Users\Birdy\files\code\C-Compiler\src\output.ir`
- 当前汇编输出：`C:\Users\Birdy\files\code\C-Compiler\src\output.asm`
- 回填报告：`C:\Users\Birdy\files\code\C-Compiler\src\backpatch_report.txt`
- 带注释语法树：`C:\Users\Birdy\files\code\C-Compiler\src\annotated_syntax_tree.txt`

---

## 1. 输入程序整体功能

输入文件 `src/c-code.c`：

```c
#include <stdio.h>

struct student {
    char *name;     // 姓名
    int num;        // 学号
    int age;        // 年龄
    int score[5];   // 成绩
};

int main() {
    int i = 0;
    int max = 0;
    struct student Li = {"Li ping", 5, 18, {80, 90, 100, 86, 95}};

    while (i < 5) {
        if (Li.score[i] > max) {
            max = Li.score[i];
        }
        i++;
    }

    printf("%d", max);
    return 0;
}
```

程序功能：

1. 定义结构体 `student`，里面有姓名、学号、年龄、成绩数组。
2. 在 `main` 中定义变量 `i` 和 `max`。
3. 初始化一个结构体变量 `Li`。
4. 通过 `while (i < 5)` 遍历 `Li.score[0]` 到 `Li.score[4]`。
5. 每次循环用 `if (Li.score[i] > max)` 判断当前成绩是否更大。
6. 如果更大，就更新 `max`。
7. 最后输出最大值。

当前成绩数组是：

```text
80, 90, 100, 86, 95
```

所以最终结果是：

```text
100
```

---

## 2. 主流程：`Compiler.compile()`

位置：`src/compiler.py:61`

主流程代码结构是：

```python
def compile(self, source_code: str, verbose: bool = True) -> CompilerResult:
    self.result = CompilerResult()
    source_code = self._normalize_source(source_code)
    self.source_code = source_code

    success, tokens = self.lexical_analysis(source_code, verbose)
    success, parse_records = self.syntax_analysis(tokens, verbose)
    success, symbol_table = self.semantic_analysis(tokens, verbose)
    success, ir_gen = self.intermediate_code_generation(symbol_table, tokens, verbose)
    self.result.annotated_syntax_tree = self._generate_annotated_syntax_tree()
    self.result.backpatch_report = self._generate_backpatch_report()
    success, asm_code = self.target_code_generation(ir_gen, symbol_table, verbose)
    self.result.success = True
```

逐行解释：

- `self.result = CompilerResult()`：初始化一个结果对象，用来保存 tokens、语法分析记录、符号表、四元式、汇编代码、错误和警告。
- `source_code = self._normalize_source(source_code)`：把中文全角标点转成英文半角标点。例如 `；` 转成 `;`，避免复制代码时出错。
- `self.source_code = source_code`：保存源码，后面生成带注释语法树时还要用。
- `self.lexical_analysis(...)`：第一阶段，词法分析，源码字符串变成 token 序列。
- `self.syntax_analysis(...)`：第二阶段，语法分析，使用 LL(1) 分析器判断 token 是否符合文法。
- `self.semantic_analysis(...)`：第三阶段，语义分析，主要构建符号表并做基础语义检查。
- `self.intermediate_code_generation(...)`：第四阶段，中间代码生成，也就是生成四元式。
- `_generate_annotated_syntax_tree()`：根据 token、符号表、四元式生成带注释的语法树文本。
- `_generate_backpatch_report()`：根据四元式生成回填说明报告。
- `self.target_code_generation(...)`：第五阶段，把四元式翻译成 8086 汇编。
- `self.result.success = True`：如果前面没有失败，标记编译成功。

答辩时可以总结为：

```text
compile() 是总控函数，严格按 词法 -> 语法 -> 语义 -> 四元式 -> 汇编 的顺序执行。
```

---

## 3. 词法分析：源码如何变成 token

入口位置：`src/compiler.py:165`

```python
def lexical_analysis(self, source_code: str, verbose: bool = True):
    self.lexer = Lexer(source_code)
    tokens = self.lexer.tokenize()
    self.result.tokens = tokens
```

逐行解释：

- `self.lexer = Lexer(source_code)`：创建词法分析器对象，输入是完整 C 源码字符串。
- `tokens = self.lexer.tokenize()`：调用词法分析器扫描源码，生成 token 列表。
- `self.result.tokens = tokens`：保存 token，后续语法、语义、IR 都使用同一批 token。

词法分析器位置：`src/lexer_core.py`

关键函数：

- `Lexer` 类：`src/lexer_core.py:31`
- `skip()`：`src/lexer_core.py:79`，跳过空白和注释。
- `_id()`：`src/lexer_core.py:109`，识别关键字和标识符。
- `_num()`：`src/lexer_core.py:144`，识别数字常量。
- `tokenize()`：`src/lexer_core.py:358`，主扫描循环。

例如源码：

```c
while (i < 5) {
```

会被拆成：

```text
KEYWORD      while
DELIMITER    (
IDENTIFIER   i
OPERATOR     <
CONST_DECIMAL 5
DELIMITER    )
DELIMITER    {
```

再比如：

```c
Li.score[i] > max
```

会被拆成：

```text
IDENTIFIER Li
OPERATOR   .
IDENTIFIER score
DELIMITER  [
IDENTIFIER i
DELIMITER  ]
OPERATOR   >
IDENTIFIER max
```

这一步不理解语义，只负责“切词”。比如它知道 `while` 是关键字，`i` 是标识符，`5` 是十进制常量，但它不判断 `i < 5` 是循环条件。

---

## 4. 语法分析：LL(1) 如何判断结构合法

入口位置：`src/compiler.py:186`

```python
def syntax_analysis(self, tokens: List, verbose: bool = True):
    self.parser = LL1Parser()
    records, success, message = self.parser.analyze(tokens)
    self.result.parse_records = records
```

逐行解释：

- `self.parser = LL1Parser()`：创建 LL(1) 分析器。
- `self.parser.analyze(tokens)`：对 token 做预测分析。
- `records`：保存每一步分析栈、剩余输入、使用的产生式。
- `success`：表示是否成功匹配完整输入。
- `self.result.parse_records = records`：保存语法分析过程。

文法定义位置：`src/parser_core.py:91`

和当前程序最相关的文法：

```python
"Stmt": [["DeclStmt"], ["RetStmt"], ["IfStmt"], ["WhileStmt"], ["ForStmt"], ["Block"], ["SimpleStmt", ";"]],
"IfStmt": [["if", "(", "Expr", ")", "Stmt", "ElsePart"]],
"WhileStmt": [["while", "(", "Expr", ")", "Stmt"]],
"ForStmt": [["for", "(", "ForInit", ";", "ExprOpt", ";", "ForStep", ")", "Stmt"]],
"Block": [["{", "StmtList", "}"]],
"SimpleStmt": [["id", "AssignOrCall"]],
```

这些产生式说明：

- 一个语句 `Stmt` 可以是声明、返回、if、while、for、代码块、简单语句。
- `while` 的结构必须是 `while ( Expr ) Stmt`。
- `if` 的结构必须是 `if ( Expr ) Stmt ElsePart`。
- 循环体和 if 体本质上都是一个 `Stmt`，所以可以是 `{ ... }` 代码块，也可以是单条语句。

LL(1) 分析器类位置：`src/parser_core.py:281`

主分析函数位置：`src/parser_core.py:330`

核心过程：

```python
stack = ["EOF", self.grammar.start]
ptr = 0
while stack:
    top = stack[-1]
    curr = filtered[ptr]
    lookahead = self.symbolize(curr)
    if top in self.terminals or top == "EOF":
        if top == lookahead:
            stack.pop()
            ptr += 1
    else:
        key = (top, lookahead)
        prod = self.table[key]
        stack.pop()
        for s in reversed(prod):
            stack.append(s)
```

逐行解释：

- `stack = ["EOF", self.grammar.start]`：初始化分析栈，底部是文件结束符，顶部是开始符号 `S`。
- `ptr = 0`：当前读到第几个 token。
- `top = stack[-1]`：取分析栈顶符号。
- `curr = filtered[ptr]`：取当前输入 token。
- `lookahead = self.symbolize(curr)`：把真实 token 映射成文法终结符。例如标识符映射成 `id`，整数映射成 `int_lit`。
- 如果 `top` 是终结符，就要求它和 `lookahead` 一致。一致则匹配成功，弹栈并前进。
- 如果 `top` 是非终结符，就用 `(top, lookahead)` 查预测分析表。
- `prod = self.table[key]`：找到应该使用的产生式。
- `stack.pop()`：弹出当前非终结符。
- `for s in reversed(prod)`：把产生式右部逆序压栈。

例如遇到 `while`：

```text
栈顶 Stmt，当前输入 while
查表得到 Stmt -> WhileStmt
再展开 WhileStmt -> while ( Expr ) Stmt
```

所以语法分析能确认：

```c
while (i < 5) {
    if (...) { ... }
    i++;
}
```

这个结构是合法的。

注意：当前项目的后续语义和四元式生成不是直接遍历 LL(1) 生成的完整语法树，而是复用 token 再扫描。语法分析主要负责结构合法性和推导记录。

---

## 5. 语义分析：符号表如何建立

入口位置：`src/compiler.py:205`

```python
def semantic_analysis(self, tokens: List, verbose: bool = True):
    self.semantic_analyzer = SemanticAnalyzer(tokens)
    symbol_table = self.semantic_analyzer.symbol_table
    self._check_invalid_identifier_usage(tokens)
    self._build_symbol_table_from_tokens(tokens, symbol_table)
    self.result.symbol_table = symbol_table
```

逐行解释：

- `SemanticAnalyzer(tokens)`：创建语义分析器，内部带一个空符号表。
- `symbol_table = self.semantic_analyzer.symbol_table`：取出符号表对象。
- `_check_invalid_identifier_usage(tokens)`：检查声明位置是否把关键字当标识符用。
- `_build_symbol_table_from_tokens(tokens, symbol_table)`：扫描 token，把结构体、变量、数组等声明加入符号表。
- `self.result.symbol_table = symbol_table`：保存符号表。

符号表类位置：`src/symbol_table.py`

关键结构：

- `Type`：`src/symbol_table.py:15`，记录基础类型、指针层级、数组维度、是否结构体。
- `Symbol`：`src/symbol_table.py:36`，记录符号名、符号种类、类型。
- `Scope.define()`：`src/symbol_table.py:65`，在当前作用域定义符号。
- `SymbolTable`：`src/symbol_table.py:98`，管理全局作用域、当前作用域、结构体表。
- `SymbolTable.define()`：`src/symbol_table.py:120`，把符号加入符号表。
- `SymbolTable.lookup()`：`src/symbol_table.py:132`，查找符号。
- `SymbolTable.lookup_struct()`：`src/symbol_table.py:142`，查找结构体。

当前程序里符号表会关心这些东西：

```text
student         结构体名
name            char*
num             int
age             int
score           int[5]
i               int
max             int
Li              struct student
```

语义分析和语法分析的结合方式：

```text
语法分析：证明 token 序列符合 C 子集文法。
语义分析：在 token 基础上识别声明，把名字和类型放入符号表。
IR 生成：再结合 token 结构和符号表，把语句翻译成四元式。
```

---

## 6. 四元式结构

四元式定义位置：`src/ir_generator.py:8`

```python
class Quadruple:
    op: str
    arg1: str
    arg2: str
    result: str
```

四元式格式：

```text
(op, arg1, arg2, result)
```

例如：

```text
(+, i, 1, T2)
```

表示：

```text
T2 = i + 1
```

再比如：

```text
(j>=, i, 5, 17)
```

表示：

```text
if i >= 5 goto 17
```

生成四元式的函数位置：`src/ir_generator.py:78`

```python
def emit(self, op, arg1="_", arg2="_", result="_", line=0):
    quad = Quadruple(op, arg1, arg2, result, line)
    self.quadruples.append(quad)
    return len(self.quadruples) - 1
```

逐行解释：

- `quad = Quadruple(...)`：创建一条四元式对象。
- `self.quadruples.append(quad)`：把它加入四元式列表。
- `return len(self.quadruples) - 1`：返回这条四元式的编号。这个编号后面回填时会用。

临时变量生成位置：`src/ir_generator.py:68`

```python
def new_temp(self):
    self.temp_count += 1
    return f"T{self.temp_count}"
```

逐行解释：

- 每次生成临时变量时，计数器加 1。
- 返回 `T1`、`T2` 这样的临时变量名。

下一条四元式编号位置：`src/ir_generator.py:90`

```python
def next_quad(self):
    return len(self.quadruples)
```

这行非常重要。它返回“下一条将要生成的四元式编号”，回填和循环入口都靠它。

---

## 7. 中间代码生成入口

入口位置：`src/compiler.py:298`

```python
def intermediate_code_generation(self, symbol_table, tokens, verbose=True):
    self.ir_generator = IRGenerator(symbol_table)
    self._generate_sample_ir(tokens)
    self.result.quadruples = self.ir_generator.quadruples
```

逐行解释：

- `IRGenerator(symbol_table)`：创建四元式生成器，它持有符号表。
- `_generate_sample_ir(tokens)`：真正扫描 token 并生成四元式。
- `self.result.quadruples = ...`：把生成好的四元式保存到结果对象。

真正核心函数位置：`src/compiler.py:500`

```python
def _generate_sample_ir(self, tokens: List):
    ir = self.ir_generator
    ir.clear()
    supported_value_types = {...}
    type_keywords = {...}
    compare_ops = {"<", ">", "<=", ">=", "==", "!="}
    inverse_compare = {"<": ">=", ">": "<=", "<=": ">", ">=": "<", "==": "!=", "!=": "=="}
```

逐行解释：

- `ir = self.ir_generator`：为了书写方便，把成员变量保存成局部变量。
- `ir.clear()`：清空旧四元式，保证每次编译从空列表开始。
- `supported_value_types`：规定哪些 token 可以直接作为表达式操作数，例如字符串、标识符、整数、浮点数、字符。
- `type_keywords`：记录内置类型关键字，用于识别变量声明。
- `compare_ops`：支持的比较运算符。
- `inverse_compare`：反向比较运算符表。比如 `<` 的反条件是 `>=`，`>` 的反条件是 `<=`。回填控制流时主要用这个表。

然后它过滤 token：

```python
filtered_tokens = [
    t for t in tokens
    if TYPES.get(t.type, "") not in {"PREPROCESSOR", "EOF"} and t.attribute != "const"
]
```

逐行解释：

- 去掉预处理指令，例如 `#include <stdio.h>`。
- 去掉 EOF。
- 去掉当前简化实现里不处理的 `const`。
- 后续 IR 生成只处理真正的 C 语句 token。

---

## 8. 表达式如何翻译：`emit_expr()`

位置：`src/compiler.py:627`

`emit_expr(expr_tokens)` 的作用是：把表达式 token 翻译成一个“结果操作数”。如果表达式很简单，直接返回变量名或常量；如果表达式需要计算，就生成四元式和临时变量。

### 8.1 单 token 表达式

```python
if len(expr_tokens) == 1:
    return token_to_operand(expr_tokens[0])
```

解释：

- 如果表达式只有一个 token，比如 `0`、`i`、`max`，直接转成操作数。
- `int i = 0` 中的右值 `0` 就走这里。
- `printf("%d", max)` 里的 `max` 也走这里。

### 8.2 负号表达式

```python
if len(expr_tokens) == 2 and expr_tokens[0].attribute == "-":
    operand = token_to_operand(expr_tokens[1])
    if operand.replace(".", "", 1).isdigit():
        return f"-{operand}"
    temp = ir.new_temp()
    ir.emit("-", "0", operand, temp)
    return temp
```

解释：

- 如果是 `-5` 这种负常量，直接返回 `-5`。
- 如果是 `-x`，生成 `T = 0 - x` 的四元式。

### 8.3 数组和结构体引用

```python
ref_operand = parse_reference_operand(expr_tokens)
if ref_operand is not None:
    return ref_operand
```

解释：

- 如果表达式是 `Li.score[i]` 这种结构体成员加数组下标，交给 `parse_reference_operand()`。
- 当前程序的 `Li.score[i]` 就在这里被翻译成数组读取四元式。

### 8.4 算术表达式

```python
operators = {"+", "-", "*", "/", "%"}
precedence = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2}
```

解释：

- 支持加减乘除取余。
- 用优先级表保证乘除优先级高于加减。

后面逻辑类似“中缀表达式转后缀表达式”：

```python
for tk in expr_tokens:
    if operand is not None:
        output.append(("operand", operand))
    elif attr in operators:
        while op_stack and precedence[op_stack[-1]] >= precedence[attr]:
            output.append(("operator", op_stack.pop()))
        op_stack.append(attr)
```

解释：

- 遇到操作数，放入输出队列。
- 遇到运算符，根据优先级处理运算符栈。
- 最后得到后缀表达式。

生成四元式：

```python
for kind, value in output:
    if kind == "operand":
        val_stack.append(value)
    else:
        right = val_stack.pop()
        left = val_stack.pop()
        temp = ir.new_temp()
        ir.emit(value, left, right, temp)
        val_stack.append(temp)
```

解释：

- 遇到操作数就压栈。
- 遇到运算符就弹出两个操作数。
- 生成临时变量。
- 生成四元式。
- 把临时变量再压回去。

例如：

```c
i + 1
```

生成：

```text
14 T2 = i + 1
```

返回值是 `T2`，后面再生成：

```text
15 i = T2
```

---

## 9. 结构体成员和数组访问如何翻译

位置：`src/compiler.py:586`

函数：`parse_reference_operand(expr_tokens)`

它专门处理：

```c
Li.score[i]
```

关键代码：

```python
idx = 1
ref = expr_tokens[0].attribute
```

解释：

- 第一个 token 是 `Li`。
- `ref = "Li"`。
- `idx = 1` 从第二个 token 开始继续看后缀。

处理点号成员：

```python
if attr == "." and idx + 1 < len(expr_tokens):
    ref = f"{ref}_{expr_tokens[idx + 1].attribute}"
    idx += 2
    continue
```

解释：

- 遇到 `.`，说明是结构体成员访问。
- `Li.score` 被转换成 `Li_score`。
- 这样做是为了方便后面汇编变量命名，因为汇编变量名里不直接使用点号。

处理数组下标：

```python
if attr == "[":
    index_tokens = []
    ...
    index_value = emit_expr(index_tokens)
    temp = ir.new_temp()
    ir.emit("=[]", ref, index_value, temp)
    ref = temp
```

逐行解释：

- 遇到 `[`，说明是数组访问。
- 收集括号里的下标 token。当前是 `i`。
- `index_value = emit_expr(index_tokens)`：把下标表达式翻译成操作数。当前返回 `"i"`。
- `temp = ir.new_temp()`：生成临时变量。当前是 `T1`。
- `ir.emit("=[]", ref, index_value, temp)`：生成数组读取四元式。
- `ref = temp`：后续表达式用临时变量代表这个数组元素。

所以：

```c
Li.score[i]
```

被翻译成：

```text
11 T1 = Li_score[i]
```

四元式原始形式：

```text
(=[], Li_score, i, T1)
```

---

## 10. 条件表达式如何翻译

### 10.1 简单条件解析

位置：`src/compiler.py:733`

```python
def parse_simple_condition(cond_tokens):
    depth = 0
    cmp_idx = -1
    for idx, tk in enumerate(cond_tokens):
        a = tk.attribute
        if a == "(":
            depth += 1
        elif a == ")":
            depth -= 1
        elif depth == 0 and a in compare_ops:
            cmp_idx = idx
            break
```

逐行解释：

- `depth = 0`：记录括号嵌套层数。
- `cmp_idx = -1`：比较运算符的位置，初始表示没找到。
- 遍历条件 token。
- 遇到 `(`，嵌套层数加 1。
- 遇到 `)`，嵌套层数减 1。
- 只有在 `depth == 0` 时找到的比较运算符才是当前条件最外层的比较运算符。

例如：

```c
i < 5
```

找到 `<`。

```python
left = emit_expr(cond_tokens[:cmp_idx])
right = emit_expr(cond_tokens[cmp_idx + 1:])
return left, cond_tokens[cmp_idx].attribute, right
```

解释：

- 左边 `i` 调用 `emit_expr()`，返回 `"i"`。
- 右边 `5` 调用 `emit_expr()`，返回 `"5"`。
- 返回条件三元组：

```text
("i", "<", "5")
```

再比如：

```c
Li.score[i] > max
```

- 左边 `Li.score[i]` 会先生成 `T1 = Li_score[i]`。
- 右边 `max` 返回 `"max"`。
- 最后返回：

```text
("T1", ">", "max")
```

### 10.2 复合条件

位置：`src/compiler.py:758`

```python
def parse_condition_tokens(cond_tokens):
    and_parts = [part for part in split_top_level(cond_tokens, "&&") if part]
    if len(and_parts) > 1:
        conds = []
        for part in and_parts:
            cond = parse_simple_condition(part)
            conds.append(cond)
        return ("&&", conds)
    return parse_simple_condition(cond_tokens)
```

逐行解释：

- 先按顶层 `&&` 拆分条件。
- 如果有多个 `&&` 子条件，就分别解析。
- 返回 `("&&", conds)`，表示一个逻辑与条件。
- 如果没有 `&&`，直接按简单条件处理。

当前程序的 `while (i < 5)` 和 `if (Li.score[i] > max)` 都是简单条件。

---

## 11. 回填相关代码逐行解释

回填的本质：

```text
先生成跳转四元式，但目标未知，先写占位符。
等目标位置确定后，再把四元式的 result 字段改成真实目标编号。
```

### 11.1 单条跳转回填

位置：`src/compiler.py:771`

```python
def patch_jump(jump_idx: int, target_idx: int):
    if 0 <= jump_idx < len(ir.quadruples):
        ir.quadruples[jump_idx].result = str(target_idx)
```

逐行解释：

- `jump_idx`：要回填的四元式编号。
- `target_idx`：真实跳转目标编号。
- `if 0 <= jump_idx < len(ir.quadruples)`：防止编号越界。
- `ir.quadruples[jump_idx].result = str(target_idx)`：直接修改这条四元式的 `result` 字段。

例如：

```text
回填前：10 if i >= 5 goto 0
回填后：10 if i >= 5 goto 17
```

实际改的是 quad 10 的 `result`。

### 11.2 生成反条件跳转

位置：`src/compiler.py:775`

```python
def emit_inverse_cond_jump(cond, placeholder: str = "0") -> int:
    left, op, right = cond
    inv = inverse_compare.get(op, "==")
    return ir.emit(f"j{inv}", left, right, placeholder)
```

逐行解释：

- `cond` 是条件三元组，例如 `("i", "<", "5")`。
- `left, op, right = cond` 拆成左操作数、操作符、右操作数。
- `inv = inverse_compare.get(op, "==")` 查反条件。例如 `<` 反过来是 `>=`。
- `ir.emit(f"j{inv}", left, right, placeholder)` 生成条件跳转四元式。

对 `i < 5`：

```text
op 是 <
inv 是 >=
生成 j>= i 5 0
```

也就是：

```text
if i >= 5 goto 0
```

为什么要反条件？

因为 while 和 if 的常见翻译方式是：

```text
如果条件为假，跳过当前代码块。
如果条件为真，就顺序执行代码块。
```

### 11.3 生成 false list

位置：`src/compiler.py:780`

```python
def emit_false_jumps(cond, placeholder: str = "0") -> List[int]:
    if cond and cond[0] == "&&":
        return [emit_inverse_cond_jump(part, placeholder) for part in cond[1]]
    return [emit_inverse_cond_jump(cond, placeholder)]
```

逐行解释：

- 如果条件是 `&&` 复合条件，每个子条件为假都应该跳到假出口，所以每个子条件都生成一条反条件跳转。
- 如果是普通条件，只生成一条反条件跳转。
- 返回值是一个列表，里面保存所有需要回填的四元式编号。

当前 `while (i < 5)`：

```text
false_jumps = [10]
```

当前 `if (Li.score[i] > max)`：

```text
false_jumps = [12]
```

### 11.4 批量回填

位置：`src/compiler.py:785`

```python
def patch_jumps(jump_indices: List[int], target_idx: int):
    for jump_idx in jump_indices:
        patch_jump(jump_idx, target_idx)
```

逐行解释：

- `jump_indices` 是需要回填的四元式编号列表。
- 遍历列表。
- 每个编号调用 `patch_jump()`，把它的目标改成 `target_idx`。

---

## 12. 声明语句如何生成四元式

位置：`src/compiler.py:965`

函数：`parse_declaration(type_name, is_struct_type)`

它负责处理：

```c
int i = 0;
int max = 0;
struct student Li = {"Li ping", 5, 18, {80, 90, 100, 86, 95}};
```

关键代码：

```python
i += 1
while i < n and tok_attr(i) != ";":
```

解释：

- 进入函数时，当前 token 是类型名，比如 `int` 或 `student`。
- `i += 1` 跳过类型名，移动到变量名。
- 循环直到遇到分号，支持一条声明里有多个变量。

读取变量名：

```python
if tok_type(i) != "IDENTIFIER":
    i += 1
    continue
var_name = tok_attr(i)
i += 1
```

解释：

- 声明里类型后面应该是标识符。
- `var_name` 保存变量名，比如 `i`、`max`、`Li`。

处理数组：

```python
if tok_attr(i) == "[":
    i += 1
    if tok_type(i) in {"CONST_DECIMAL", "CONST_OCTAL", "CONST_HEX"}:
        array_size = int(tok_attr(i), 0)
```

解释：

- 如果变量名后面有 `[`，说明是数组声明。
- 读取数组大小。
- 当前结构体字段 `score[5]` 的数组维度就是这么识别的。

处理初始化：

```python
if tok_attr(i) == "=":
    i += 1
    init_tokens = []
    depth = 0
    while i < n:
        ...
        if depth == 0 and a in {",", ";"}:
            break
        init_tokens.append(filtered_tokens[i])
        i += 1
```

逐行解释：

- 如果变量后面是 `=`，说明有初始化。
- `init_tokens` 用来保存初始化表达式。
- `depth` 用来处理 `{...}`、`(...)`、`[...]` 嵌套。
- 只有在最外层遇到 `,` 或 `;`，才说明当前变量初始化结束。

普通变量初始化：

```python
rhs = emit_expr(init_tokens)
if rhs is not None:
    ir.emit("=", rhs, "_", var_name)
```

解释：

- 右值表达式用 `emit_expr()` 翻译。
- 生成赋值四元式。

所以：

```c
int i = 0;
```

生成：

```text
0 i = 0
```

```c
int max = 0;
```

生成：

```text
1 max = 0
```

结构体初始化：

```python
if is_struct_type:
    emit_struct_initializer(type_name, var_name, array_size, init_tokens)
```

解释：

- 如果是结构体变量初始化，就交给 `emit_struct_initializer()`。
- 它会根据结构体成员顺序，把 `Li` 展开成多个变量：

```text
Li_name
Li_num
Li_age
Li_score
```

当前：

```c
struct student Li = {"Li ping", 5, 18, {80, 90, 100, 86, 95}};
```

生成：

```text
2 Li_name = "Li ping"
3 Li_num = 5
4 Li_age = 18
5 Li_score[0] = 80
6 Li_score[1] = 90
7 Li_score[2] = 100
8 Li_score[3] = 86
9 Li_score[4] = 95
```

---

## 13. 语句扫描总入口：`parse_statement()`

位置：`src/compiler.py:1022`

`parse_statement()` 是中间代码生成阶段最核心的语句分发函数。它根据当前 token 判断当前是什么语句。

### 13.1 右大括号

位置：`src/compiler.py:1030`

```python
if cur_attr == "}":
    i += 1
    return
```

解释：

- 如果遇到 `}`，说明当前代码块结束。
- 指针前进一位并返回。

### 13.2 代码块

位置：`src/compiler.py:1034`

```python
if cur_attr == "{":
    i += 1
    while i < n and tok_attr(i) != "}":
        parse_statement()
    if tok_attr(i) == "}":
        i += 1
    return
```

逐行解释：

- 如果当前 token 是 `{`，说明进入一个复合语句块。
- `i += 1` 跳过 `{`。
- 循环解析块内每一条语句。
- 遇到 `}` 后跳过它。
- 返回外层。

当前 while 循环体：

```c
{
    if (...) { ... }
    i++;
}
```

就是在这里递归解析的。

### 13.3 结构体定义

位置：`src/compiler.py:1042`

```python
if cur_attr == "struct" and tok_attr(i + 2) == "{":
    i += 3
    depth = 1
    while i < n and depth > 0:
        ...
    if tok_attr(i) == ";":
        i += 1
    return
```

解释：

- 如果看到 `struct student {`，说明这是结构体类型定义。
- 中间代码生成阶段不为类型定义生成四元式。
- 它只跳过整个结构体定义。
- 结构体成员信息在前面的 `_collect_struct_defs()` 和语义分析里已经收集。

所以：

```c
struct student { ... };
```

不会直接生成四元式。

### 13.4 结构体变量声明

位置：`src/compiler.py:1055`

```python
if cur_attr == "struct" and tok_type(i + 1) == "IDENTIFIER" and tok_attr(i + 1) in custom_type_names:
    i += 1
    parse_declaration(tok_attr(i), True)
    return
```

解释：

- 当前 token 是 `struct`。
- 下一个 token 是结构体名，比如 `student`。
- `student` 在 `custom_type_names` 里，说明这是已知结构体类型。
- `i += 1` 移到结构体名。
- `parse_declaration(tok_attr(i), True)` 解析结构体变量声明。
- 第二个参数 `True` 表示这是结构体类型。

当前：

```c
struct student Li = ...
```

就是这里处理的。

### 13.5 普通变量声明

位置：`src/compiler.py:1064`

```python
if cur_attr in type_keywords and not (tok_type(i + 1) == "IDENTIFIER" and tok_attr(i + 2) == "("):
    parse_declaration(cur_attr, False)
    return
```

解释：

- 如果当前 token 是 `int`、`float`、`char` 等类型关键字。
- 并且后面不是函数定义形态 `id(`。
- 那它就是变量声明。
- 调用 `parse_declaration()` 生成初始化四元式。

当前：

```c
int i = 0;
int max = 0;
```

都在这里处理。

### 13.6 函数定义

位置：`src/compiler.py:1068`

```python
if cur_attr in type_keywords:
    if tok_type(i + 1) == "IDENTIFIER" and tok_attr(i + 2) == "(":
        _, next_idx = parse_parenthesized_tokens(i + 2)
        i = next_idx
        if tok_attr(i) == "{":
            parse_statement()
        return
```

逐行解释：

- 如果当前是类型关键字，比如 `int`。
- 后面是标识符，再后面是 `(`，说明这是函数定义。
- `parse_parenthesized_tokens(i + 2)` 跳过参数列表。
- `i = next_idx` 移动到参数右括号后面。
- 如果后面是 `{`，调用 `parse_statement()` 解析函数体。

当前：

```c
int main() {
    ...
}
```

就是这里进入 `main` 函数体的。

### 13.7 printf

位置：`src/compiler.py:1109`

```python
if cur_attr == "printf":
    _, after_paren = parse_parenthesized_tokens(i + 1)
    arg_tokens, _ = parse_parenthesized_tokens(i + 1)
    arg_exprs = [part for part in split_top_level(arg_tokens, ",") if part]
    parse_printf_from_args(arg_exprs)
    i = after_paren
    if tok_attr(i) == ";":
        i += 1
    return
```

逐行解释：

- 当前 token 是 `printf`。
- `parse_parenthesized_tokens(i + 1)` 取出括号里的参数，并得到括号后的位置。
- 对 `printf("%d", max)`，参数 token 是 `"%d"` 和 `max`。
- `split_top_level(..., ",")` 按逗号分割参数。
- `parse_printf_from_args(arg_exprs)` 根据格式串生成输出四元式。
- `i = after_paren` 把扫描位置移到右括号后。
- 如果后面是分号，跳过分号。

当前：

```c
printf("%d", max);
```

生成：

```text
17 printf max
```

### 13.8 if

位置：`src/compiler.py:1132`

```python
if cur_attr == "if":
    cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
    cond = parse_condition_tokens(cond_tokens)
    i = after_cond
    if cond is None:
        parse_statement()
        return

    false_jumps = emit_false_jumps(cond)
    parse_statement()
    if tok_attr(i) == "else":
        j_end = ir.emit("j", "_", "_", "0")
        patch_jumps(false_jumps, ir.next_quad())
        i += 1
        parse_statement()
        patch_jump(j_end, ir.next_quad())
    else:
        patch_jumps(false_jumps, ir.next_quad())
    return
```

逐行解释：

- `if cur_attr == "if"`：当前语句是 if。
- `cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)`：取出 if 括号里的条件。
- 当前条件是 `Li.score[i] > max`。
- `cond = parse_condition_tokens(cond_tokens)`：把条件解析成 `("T1", ">", "max")`，同时因为左边是数组访问，会先生成 `T1 = Li_score[i]`。
- `i = after_cond`：移动到 if 条件右括号后，也就是 then 语句开始处。
- `if cond is None`：容错逻辑，如果条件无法解析，就只解析 then 语句，不生成跳转。
- `false_jumps = emit_false_jumps(cond)`：生成反条件跳转。当前生成 `if T1 <= max goto 0`，并返回 `[12]`。
- `parse_statement()`：解析 then 语句块。当前 then 块生成 `max = T1`。
- `if tok_attr(i) == "else"`：如果有 else，要额外生成一条跳过 else 的无条件跳转。
- 当前程序没有 else，所以进入 `else:` 分支。
- `patch_jumps(false_jumps, ir.next_quad())`：把 if 假出口回填到 then 块结束后的下一条四元式。
- 当前 then 块结束后下一条是 quad 14，所以 quad 12 被回填成 `goto 14`。

当前 if 最终生成：

```text
11 T1 = Li_score[i]
12 if T1 <= max goto 14
13 max = T1
```

其中：

- quad 11 是条件左操作数 `Li.score[i]` 的数组读取。
- quad 12 是 if 条件为假时跳过 then 块。
- quad 13 是 then 块。

### 13.9 while

位置：`src/compiler.py:1152`

```python
if cur_attr == "while":
    cond_start = ir.next_quad()
    cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
    cond = parse_condition_tokens(cond_tokens)
    i = after_cond
    if cond is None:
        parse_statement()
        return

    false_jumps = emit_false_jumps(cond)
    parse_statement()
    ir.emit("j", "_", "_", str(cond_start))
    patch_jumps(false_jumps, ir.next_quad())
    return
```

逐行解释：

- `if cur_attr == "while"`：当前语句是 while。
- `cond_start = ir.next_quad()`：记录循环条件开始的四元式编号。当前前面已经生成 0 到 9，所以这里是 10。
- `cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)`：取出 while 括号里的条件 token。当前是 `i < 5`。
- `cond = parse_condition_tokens(cond_tokens)`：解析条件，得到 `("i", "<", "5")`。
- `i = after_cond`：移动到右括号后面，也就是循环体开始 `{`。
- `if cond is None`：容错逻辑，如果条件不支持，就只解析循环体。
- `false_jumps = emit_false_jumps(cond)`：生成反条件跳转。`i < 5` 的反条件是 `i >= 5`，所以生成 `10 if i >= 5 goto 0`，返回 `[10]`。
- `parse_statement()`：解析循环体，也就是 `{ if (...) { ... } i++; }`。
- 循环体内部生成 quad 11 到 quad 15。
- `ir.emit("j", "_", "_", str(cond_start))`：循环体结束后生成无条件跳转，跳回条件入口。当前生成 `16 goto 10`。
- `patch_jumps(false_jumps, ir.next_quad())`：此时下一条四元式是 17，所以把 quad 10 的目标从 `0` 回填成 `17`。
- `return`：while 已经翻译完成。

while 最终结果：

```text
10 if i >= 5 goto 17
11 T1 = Li_score[i]
12 if T1 <= max goto 14
13 max = T1
14 T2 = i + 1
15 i = T2
16 goto 10
17 printf max
```

### 13.10 for

位置：`src/compiler.py:1167`

虽然当前 `c-code.c` 没有 `for`，但代码支持。答辩可能会问。

```python
if cur_attr == "for":
    inside_tokens, after_cond = parse_parenthesized_tokens(i + 1)
    sections = split_top_level(inside_tokens, ";")
    while len(sections) < 3:
        sections.append([])

    parse_inline_assignment(sections[0])
    cond_start = ir.next_quad()
    false_jumps = []
    if sections[1]:
        cond = parse_condition_tokens(sections[1])
        if cond is not None:
            false_jumps = emit_false_jumps(cond)

    i = after_cond
    parse_statement()
    parse_inline_assignment(sections[2])
    ir.emit("j", "_", "_", str(cond_start))
    patch_jumps(false_jumps, ir.next_quad())
    return
```

逐行解释：

- `inside_tokens`：取出 `for (...)` 括号里的所有 token。
- `sections = split_top_level(inside_tokens, ";")`：按分号拆成三段：初始化、条件、步进。
- `while len(sections) < 3`：如果某段省略，补空列表。
- `parse_inline_assignment(sections[0])`：翻译初始化部分，例如 `i = 0`。
- `cond_start = ir.next_quad()`：记录条件判断入口。
- `false_jumps = []`：初始化假出口列表。
- `if sections[1]`：如果有条件表达式，就解析条件。
- `false_jumps = emit_false_jumps(cond)`：生成条件为假时跳出循环的占位跳转。
- `i = after_cond`：移动到循环体开始。
- `parse_statement()`：翻译循环体。
- `parse_inline_assignment(sections[2])`：翻译步进部分，例如 `i++`。
- `ir.emit("j", "_", "_", str(cond_start))`：步进后跳回条件。
- `patch_jumps(false_jumps, ir.next_quad())`：把假出口回填到循环结束位置。

所以：

```c
for (i = 0; i < 5; i++) {
    body;
}
```

会翻译成：

```text
i = 0
cond_start:
if i >= 5 goto exit
body
i = i + 1
goto cond_start
exit:
```

### 13.11 return

位置：`src/compiler.py:1188`

```python
if cur_attr == "return":
    i += 1
    expr_tokens = []
    while i < n and tok_attr(i) != ";":
        expr_tokens.append(filtered_tokens[i])
        i += 1
    ret_val = emit_expr(expr_tokens) if expr_tokens else "_"
    if ret_val is None:
        ret_val = "_"
    ir.emit("return", ret_val, "_", "_")
    if tok_attr(i) == ";":
        i += 1
    return
```

逐行解释：

- 当前 token 是 `return`。
- `i += 1` 跳过 `return`。
- 收集分号前的表达式 token。
- 当前是 `0`。
- `emit_expr(expr_tokens)` 把 `0` 转成操作数 `"0"`。
- `ir.emit("return", ret_val, "_", "_")` 生成返回四元式。
- 跳过分号。

当前：

```c
return 0;
```

生成：

```text
18 return 0
```

### 13.12 普通赋值

位置：`src/compiler.py:1204`

```python
if tok_attr(i + 1) == "=":
    lhs = tok_attr(i)
    i += 2
    expr_tokens = []
    while i < n and tok_attr(i) != ";":
        expr_tokens.append(filtered_tokens[i])
        i += 1
    rhs = emit_expr(expr_tokens)
    if rhs is not None:
        ir.emit("=", rhs, "_", lhs)
        clear_expr_cache()
```

逐行解释：

- 如果当前 token 是标识符，并且下一个 token 是 `=`，说明是赋值。
- `lhs` 保存左值变量名。
- 跳过变量名和等号。
- 收集右值表达式。
- 用 `emit_expr()` 翻译右值。
- 生成赋值四元式。

当前 then 块的源码是：

```c
max = Li.score[i];
```

因为条件判断时已经生成过 `T1 = Li_score[i]`，表达式缓存会让这里复用 `T1`，所以生成：

```text
13 max = T1
```

### 13.13 自增自减

位置：`src/compiler.py:1220`

```python
if tok_attr(i + 1) in {"++", "--"}:
    parse_inline_assignment([filtered_tokens[i], filtered_tokens[i + 1]])
    clear_expr_cache()
    i += 2
    if tok_attr(i) == ";":
        i += 1
    return
```

逐行解释：

- 如果标识符后面是 `++` 或 `--`，说明是自增自减语句。
- 调用 `parse_inline_assignment()` 翻译。
- 清空表达式缓存，因为变量值变化了。
- 跳过变量和 `++`。
- 跳过分号。

`parse_inline_assignment()` 对 `i++` 的逻辑：

```python
temp = ir.new_temp()
ir.emit("+", "i", "1", temp)
ir.emit("=", temp, "_", "i")
```

所以：

```c
i++;
```

生成：

```text
14 T2 = i + 1
15 i = T2
```

---

## 14. 当前源码每一段对应哪些四元式

当前四元式文件：`src/output.ir`

```text
0  i = 0
1  max = 0
2  Li_name = "Li ping"
3  Li_num = 5
4  Li_age = 18
5  Li_score[0] = 80
6  Li_score[1] = 90
7  Li_score[2] = 100
8  Li_score[3] = 86
9  Li_score[4] = 95
10 if i >= 5 goto 17
11 T1 = Li_score[i]
12 if T1 <= max goto 14
13 max = T1
14 T2 = i + 1
15 i = T2
16 goto 10
17 printf max
18 return 0
```

源码到四元式映射：

| 源码位置 | 源码 | 四元式 | 说明 |
|---|---|---|---|
| `c-code.c:3-8` | `struct student { ... };` | 无直接四元式 | 类型定义，只进入符号表/结构体定义 |
| `c-code.c:10` | `int main() {` | 无直接四元式 | 函数体入口，代码扫描进入块 |
| `c-code.c:11` | `int i = 0;` | `0 i = 0` | 普通变量初始化 |
| `c-code.c:12` | `int max = 0;` | `1 max = 0` | 普通变量初始化 |
| `c-code.c:13` | `struct student Li = ...` | `2-9` | 结构体初始化被展开成成员和数组赋值 |
| `c-code.c:15` | `while (i < 5)` | `10`, `16` | quad 10 是 while 假出口，quad 16 是循环回跳 |
| `c-code.c:16` | `if (Li.score[i] > max)` | `11`, `12` | quad 11 取数组元素，quad 12 是 if 假出口 |
| `c-code.c:17` | `max = Li.score[i];` | `13 max = T1` | then 块赋值 |
| `c-code.c:19` | `i++;` | `14`, `15` | 自增拆成加法和赋值 |
| `c-code.c:22` | `printf("%d", max);` | `17 printf max` | 格式串 `%d` 使输出参数 `max` |
| `c-code.c:23` | `return 0;` | `18 return 0` | 返回语句 |

---

## 15. 嵌套 while-if 的完整控制流

源码：

```c
while (i < 5) {
    if (Li.score[i] > max) {
        max = Li.score[i];
    }
    i++;
}
```

四元式：

```text
10 if i >= 5 goto 17
11 T1 = Li_score[i]
12 if T1 <= max goto 14
13 max = T1
14 T2 = i + 1
15 i = T2
16 goto 10
17 printf max
```

逐条解释：

- quad 10：while 条件的反条件。源码是 `i < 5`，反条件是 `i >= 5`。如果成立，说明循环应该结束，跳到 17。
- quad 11：进入循环体后，先取 `Li.score[i]`，保存到临时变量 `T1`。
- quad 12：if 条件的反条件。源码是 `T1 > max`，反条件是 `T1 <= max`。如果成立，就跳过 then 块，到 14。
- quad 13：then 块，执行 `max = T1`。
- quad 14：计算 `i + 1`，保存到 `T2`。
- quad 15：把 `T2` 赋值给 `i`，完成 `i++`。
- quad 16：无条件跳回 quad 10，重新判断 while 条件。
- quad 17：循环结束后的第一条语句，输出 `max`。

控制流图：

```text
        +----------------------+
        | 10 if i >= 5 goto 17 |
        +----------+-----------+
                   |
              false| 进入循环
                   v
        +----------------------+
        | 11 T1 = Li_score[i]  |
        +----------+-----------+
                   v
        +----------------------+
        | 12 if T1 <= max ->14 |
        +------+---------------+
               |
          false| 执行 then
               v
        +----------------------+
        | 13 max = T1          |
        +----------+-----------+
                   v
        +----------------------+
        | 14 T2 = i + 1        |
        | 15 i = T2            |
        +----------+-----------+
                   v
        +----------------------+
        | 16 goto 10           |
        +----------------------+

quad 10 为 true 时跳到：

        +----------------------+
        | 17 printf max        |
        +----------------------+
```

---

## 16. while 回填完整过程

while 生成代码位置：`src/compiler.py:1152`

当前进入 while 前已有四元式 0 到 9，所以：

```python
cond_start = ir.next_quad()
```

得到：

```text
cond_start = 10
```

解析条件：

```python
cond_tokens = [i, <, 5]
cond = ("i", "<", "5")
```

生成反条件假出口：

```python
false_jumps = emit_false_jumps(cond)
```

生成：

```text
10 if i >= 5 goto 0
```

并返回：

```text
false_jumps = [10]
```

这里 `0` 是占位符。

然后翻译循环体：

```text
11 T1 = Li_score[i]
12 if T1 <= max goto 14
13 max = T1
14 T2 = i + 1
15 i = T2
```

循环体结束后：

```python
ir.emit("j", "_", "_", str(cond_start))
```

生成：

```text
16 goto 10
```

此时下一条四元式编号是 17：

```python
ir.next_quad() == 17
```

所以：

```python
patch_jumps(false_jumps, ir.next_quad())
```

等价于：

```python
patch_jumps([10], 17)
```

把：

```text
10 if i >= 5 goto 0
```

改成：

```text
10 if i >= 5 goto 17
```

这就是 while 的回填。

---

## 17. if 回填完整过程

if 生成代码位置：`src/compiler.py:1132`

当前 if 条件：

```c
Li.score[i] > max
```

先处理左操作数：

```text
11 T1 = Li_score[i]
```

条件变成：

```text
T1 > max
```

反条件是：

```text
T1 <= max
```

所以：

```text
12 if T1 <= max goto 0
```

并记录：

```text
false_jumps = [12]
```

然后翻译 then 块：

```text
13 max = T1
```

then 块结束后，下一条是 quad 14：

```text
14 T2 = i + 1
```

所以回填：

```text
12 if T1 <= max goto 14
```

含义是：

```text
如果 Li.score[i] 不大于 max，就跳过 max = T1，直接执行 i++。
```

---

## 18. for 循环如果被问到，怎么讲

虽然当前输入没有 for，但实现位置是 `src/compiler.py:1167`。

模板：

```c
for (init; cond; step) {
    body;
}
```

生成逻辑：

```text
翻译 init
cond_start = next_quad
生成 cond 的反条件假出口跳转
翻译 body
翻译 step
goto cond_start
回填假出口到 exit
```

如果是：

```c
for (i = 0; i < 5; i++) {
    if (Li.score[i] > max) {
        max = Li.score[i];
    }
}
```

大致四元式会是：

```text
i = 0
cond_start:
if i >= 5 goto exit
T1 = Li_score[i]
if T1 <= max goto step
max = T1
step:
T2 = i + 1
i = T2
goto cond_start
exit:
```

核心和 while 一样：

- 条件位置要保存。
- 假出口先占位。
- 循环体结束要回到条件。
- 最后回填假出口。

---

## 19. 四元式如何生成汇编

目标代码生成入口：`src/compiler.py:314`

```python
def target_code_generation(self, ir_gen, symbol_table, verbose=True):
    self.code_generator = CodeGenerator(ir_gen, symbol_table)
    asm_code = self.code_generator.generate()
    self.result.assembly_code = asm_code
```

逐行解释：

- 创建 `CodeGenerator`。
- 调用 `generate()` 生成完整汇编。
- 保存汇编代码。

`CodeGenerator.generate()` 位置：`src/codegen.py:838`

生成顺序：

```python
self.generate_code_section()
self.generate_helpers()
self.emit_code("CODE ENDS")
self.generate_data_section()
...
```

解释：

- 先生成代码段，因为处理 `printf` 时会收集字符串字面量。
- 再生成辅助函数，比如整数输出 `dispsiw`。
- 再生成数据段和栈段。
- 最后拼接成完整汇编。

---

## 20. 标签如何从四元式编号变成汇编标签

位置：`src/codegen.py:226`

```python
def scan_labels(self):
    for i, quad in enumerate(self.ir_gen.quadruples):
        if quad.op.startswith("j"):
            if quad.result.isdigit():
                target = int(quad.result)
                if target not in self.label_map:
                    self.label_map[target] = f"L{len(self.label_map)}"
```

逐行解释：

- 遍历所有四元式。
- 如果操作符以 `j` 开头，说明是跳转。
- 如果跳转目标是数字，比如 `17`，说明它指向某条四元式编号。
- 把这个编号映射成汇编标签。

当前跳转目标有：

```text
quad 10 -> result 17
quad 12 -> result 14
quad 16 -> result 10
```

所以会生成类似映射：

```text
17 -> L0
14 -> L1
10 -> L2
```

这就是为什么四元式里写 `goto 17`，汇编里写 `JGE L0`。

---

## 21. 遍历四元式生成汇编

位置：`src/codegen.py:240`

核心代码：

```python
def generate_code_section(self):
    self.emit_code("CODE SEGMENT")
    ...
    self.scan_labels()
    for i, quad in enumerate(self.ir_gen.quadruples):
        if i in self.label_map:
            self.emit_code(f"{self.label_map[i]}:")
        self.emit_comment(f"[{i}] {quad}")
        self.translate_quadruple(quad, i)
        self.emit_code("")
```

逐行解释：

- 先输出 `CODE SEGMENT`。
- 调用 `scan_labels()`，建立“四元式编号 -> 汇编标签”的映射。
- 遍历每一条四元式。
- 如果当前四元式编号是某个跳转目标，就先输出标签。例如 quad 10 前输出 `L2:`。
- 输出注释 `; [编号] 四元式`。这让我们能直接在汇编里找到某条四元式。
- 调用 `translate_quadruple()` 翻译当前四元式。
- 输出空行分隔。

所以查“四元式生成汇编的位置”最简单的方法就是在 `output.asm` 里搜：

```text
; [四元式编号]
```

例如搜：

```text
; [12]
```

就能找到 quad 12 对应的汇编。

---

## 22. 单条四元式如何分派到具体汇编生成函数

位置：`src/codegen.py:268`

```python
def translate_quadruple(self, quad, index):
    op = quad.op
    arg1, arg2, result = quad.arg1, quad.arg2, quad.result

    if op == "=":
        self.gen_assignment(arg1, result)
    elif op in ["+", "-", "*", "/", "%"]:
        self.gen_arithmetic(op, arg1, arg2, result)
    elif op.startswith("j"):
        self.gen_jump(op, arg1, arg2, result)
    elif op == "printf":
        self.gen_printf(result)
    elif op == "=[]":
        self.gen_array_load(arg1, arg2, result)
    elif op == "[]=":
        self.gen_array_store(result, arg2, arg1)
```

逐行解释：

- 先取出四元式的 `op`、`arg1`、`arg2`、`result`。
- 如果 `op == "="`，说明是赋值，交给 `gen_assignment()`。
- 如果是算术运算，交给 `gen_arithmetic()`。
- 如果以 `j` 开头，说明是跳转，交给 `gen_jump()`。
- 如果是 `printf`，交给 `gen_printf()`。
- 如果是 `=[]`，说明数组读取，交给 `gen_array_load()`。
- 如果是 `[]=`，说明数组写入，交给 `gen_array_store()`。

---

## 23. 赋值四元式如何生成汇编

位置：`src/codegen.py:334`

四元式：

```text
0 i = 0
```

原始形式：

```text
(=, 0, _, i)
```

生成汇编：

```asm
; [0] (=, 0, _, i)
    MOV AX, 0
    MOV i, AX
```

解释：

- 先把右值 `0` 放到 AX。
- 再把 AX 存入变量 `i`。

同理：

```text
13 max = T1
```

生成：

```asm
; [13] (=, T1, _, max)
    MOV AX, T1
    MOV max, AX
```

---

## 24. 算术四元式如何生成汇编

位置：`src/codegen.py:383`

四元式：

```text
14 T2 = i + 1
```

原始形式：

```text
(+, i, 1, T2)
```

生成汇编：

```asm
; [14] (+, i, 1, T2)
    MOV AX, i
    MOV BX, 1
    ADD AX, BX
    MOV T2, AX
```

解释：

- `MOV AX, i`：左操作数放 AX。
- `MOV BX, 1`：右操作数放 BX。
- `ADD AX, BX`：执行加法。
- `MOV T2, AX`：结果存入临时变量 `T2`。

---

## 25. 条件跳转四元式如何生成汇编

位置：`src/codegen.py:485`

四元式：

```text
10 if i >= 5 goto 17
```

原始形式：

```text
(j>=, i, 5, 17)
```

生成汇编位置：`src/output.asm` 中 `; [10]` 附近。

```asm
L2:
; [10] (j>=, i, 5, 17)
    MOV AX, i
    MOV BX, 5
    CMP AX, BX
    JGE L0
```

逐行解释：

- `L2:`：因为 quad 16 会跳回 quad 10，所以 quad 10 是一个标签位置。
- `MOV AX, i`：把左操作数 `i` 放到 AX。
- `MOV BX, 5`：把右操作数 `5` 放到 BX。
- `CMP AX, BX`：比较 `i` 和 `5`。
- `JGE L0`：如果 `i >= 5`，跳到 `L0`。`L0` 对应 quad 17。

另一个例子：

```text
12 if T1 <= max goto 14
```

汇编：

```asm
; [12] (j<=, T1, max, 14)
    MOV AX, T1
    MOV BX, max
    CMP AX, BX
    JLE L1
```

解释：

- 比较 `T1` 和 `max`。
- 如果 `T1 <= max`，说明 if 条件 `T1 > max` 不成立。
- 跳到 `L1`，也就是 quad 14，跳过 `max = T1`。

---

## 26. 无条件跳转如何生成汇编

四元式：

```text
16 goto 10
```

原始形式：

```text
(j, _, _, 10)
```

汇编：

```asm
; [16] (j, _, _, 10)
    JMP L2
```

解释：

- `op == "j"` 表示无条件跳转。
- 目标 quad 10 被 `scan_labels()` 映射成 `L2`。
- 所以生成 `JMP L2`。

这条指令就是 while 循环体结束后回到条件判断的位置。

---

## 27. 数组读取如何生成汇编

位置：`src/codegen.py:583`

四元式：

```text
11 T1 = Li_score[i]
```

原始形式：

```text
(=[], Li_score, i, T1)
```

汇编：

```asm
; [11] (=[], Li_score, i, T1)
    MOV BX, i
    SHL BX, 1
    MOV AX, Li_score[BX]
    MOV T1, AX
```

逐行解释：

- `MOV BX, i`：把数组下标 `i` 放到 BX。
- `SHL BX, 1`：BX 左移一位，相当于乘以 2。
- 为什么乘以 2：因为数据段里数组是 `DW`，一个元素 2 字节。
- `MOV AX, Li_score[BX]`：从数组 `Li_score` 的偏移位置读取元素。
- `MOV T1, AX`：把读取结果保存到临时变量 `T1`。

所以 `Li.score[i]` 的实际汇编访问是：

```text
Li_score + i * 2
```

---

## 28. 数组写入如何生成汇编

位置：`src/codegen.py:599`

四元式：

```text
5 Li_score[0] = 80
```

原始形式：

```text
([]=, 80, 0, Li_score)
```

汇编：

```asm
; [5] ([]=, 80, 0, Li_score)
    MOV AX, 80
    MOV Li_score[0], AX
```

解释：

- 把值 `80` 放到 AX。
- 因为下标是常量 0，直接计算偏移 `0 * 2 = 0`。
- 写入 `Li_score[0]`。

quad 6：

```text
Li_score[1] = 90
```

汇编里是：

```asm
MOV Li_score[2], AX
```

原因是下标 1 对应字节偏移 2。

---

## 29. printf 如何生成汇编

位置：`src/codegen.py:540`

四元式：

```text
17 printf max
```

汇编：

```asm
L0:
; [17] (printf, _, _, max)
    MOV AX, max
    CALL dispsiw
```

解释：

- `L0:` 是 while 假出口跳转到的位置，也就是循环结束后的位置。
- `MOV AX, max`：把要输出的值放到 AX。
- `CALL dispsiw`：调用辅助函数输出带符号整数。

为什么只输出 `max`，没有输出 `"%d"`？

因为 `parse_printf_from_args()` 会解析格式串 `"%d"`，发现它是一个整数占位符，于是只为对应参数 `max` 生成输出四元式。

---

## 30. return 如何生成汇编

四元式：

```text
18 return 0
```

汇编：

```asm
; [18] (return, 0, _, _)
    MOV AX, 0
    JMP EXIT
```

解释：

- 把返回值 0 放到 AX。
- 跳到程序退出标签 `EXIT`。

退出代码：

```asm
EXIT:
    MOV AH, 4CH
    INT 21H
```

这是 DOS 中断退出程序。

---

## 31. 数据段如何生成

位置：`src/codegen.py:94`

当前 `output.asm` 数据段：

```asm
DATA SEGMENT
STR0 DB 'Li ping', '$'
Li_age DW 0
Li_name DW 0
Li_num DW 0
Li_score DW 5 DUP(0)
T1 DW 0
T2 DW 0
i DW 0
max DW 0
DATA ENDS
```

解释：

- `STR0 DB 'Li ping', '$'`：字符串字面量，DOS 09H 输出用 `$` 结尾。
- `Li_age`, `Li_name`, `Li_num`：结构体成员展开后的变量。
- `Li_score DW 5 DUP(0)`：成绩数组，5 个 word。
- `T1`, `T2`：中间代码临时变量。
- `i`, `max`：源程序变量。

---

## 32. 最终执行过程模拟

初始：

```text
i = 0
max = 0
Li_score = [80, 90, 100, 86, 95]
```

循环过程：

| i | Li_score[i] | max 原值 | 是否更新 | max 新值 |
|---|---:|---:|---|---:|
| 0 | 80 | 0 | 是 | 80 |
| 1 | 90 | 80 | 是 | 90 |
| 2 | 100 | 90 | 是 | 100 |
| 3 | 86 | 100 | 否 | 100 |
| 4 | 95 | 100 | 否 | 100 |
| 5 | - | 100 | while 条件结束 | 100 |

当 `i = 5` 时：

```text
quad 10: if i >= 5 goto 17
```

条件成立，跳到 `printf max`。

最终输出：

```text
100
```

---

## 33. 答辩常见问题速答

### 问：for/while 是怎么做语法分析的？

答：

语法分析阶段使用 LL(1) 文法。`WhileStmt -> while ( Expr ) Stmt`，`ForStmt -> for ( ForInit ; ExprOpt ; ForStep ) Stmt`。分析器用栈和预测分析表，根据当前 token 选择产生式。遇到 `while` 时，`Stmt` 展开为 `WhileStmt`，再匹配 `while`、括号条件和循环体语句。

### 问：语法分析和语义分析怎么结合？

答：

它们共同使用词法分析得到的 token。语法分析负责判断 token 是否符合文法结构；语义分析扫描 token 里的声明，建立符号表，记录变量、数组、结构体类型。后续 IR 生成结合 token 结构和符号表生成四元式。

### 问：回填改的是什么？

答：

改的是四元式对象的 `result` 字段。比如 while 的 quad 10 一开始是：

```text
if i >= 5 goto 0
```

循环体生成完以后知道出口是 quad 17，于是把 quad 10 的 `result` 改成 `17`：

```text
if i >= 5 goto 17
```

### 问：为什么生成反条件跳转？

答：

因为控制流翻译采用“条件为假就跳过当前代码块”的方式。while 中条件为假就跳出循环；if 中条件为假就跳过 then 块。所以 `i < 5` 会生成 `i >= 5 goto exit`，`T1 > max` 会生成 `T1 <= max goto after_then`。

### 问：`Li.score[i]` 怎么处理？

答：

先把结构体成员 `Li.score` 转成汇编友好的变量名 `Li_score`。再处理数组下标 `[i]`，生成数组读取四元式：

```text
T1 = Li_score[i]
```

汇编里用 `i * 2` 做偏移，因为数组元素是 word：

```asm
MOV BX, i
SHL BX, 1
MOV AX, Li_score[BX]
MOV T1, AX
```

### 问：某个源码对应的四元式在哪里找？

答：

看 `src/output.ir`。例如 `if (Li.score[i] > max)` 对应：

```text
11 T1 = Li_score[i]
12 if T1 <= max goto 14
```

因为条件里包含数组访问，所以先生成取数组元素，再生成条件跳转。

### 问：某个四元式对应的汇编在哪里找？

答：

看 `src/output.asm` 里的注释 `; [编号]`。例如四元式 12：

```asm
; [12] (j<=, T1, max, 14)
    MOV AX, T1
    MOV BX, max
    CMP AX, BX
    JLE L1
```

### 问：while 嵌套 if 的跳转关系怎么讲？

答：

quad 10 是 while 假出口，跳到 17；quad 12 是 if 假出口，跳到 14；quad 16 是循环回跳，跳回 10。

```text
10 if i >= 5 goto 17
11 T1 = Li_score[i]
12 if T1 <= max goto 14
13 max = T1
14 T2 = i + 1
15 i = T2
16 goto 10
17 printf max
```

---

## 34. 一段可以直接背的总结

我们的编译器从 `c-code.c` 读入源码，先由词法分析器把字符流拆成 token；然后 LL(1) 语法分析器根据文法规则和预测分析表判断程序结构是否合法，比如 `while` 必须符合 `while ( Expr ) Stmt`，`if` 必须符合 `if ( Expr ) Stmt ElsePart`。语义分析阶段扫描同一批 token，建立符号表，记录结构体、变量、数组等类型信息。

中间代码生成阶段再次扫描 token。普通声明通过 `parse_declaration()` 生成赋值四元式；结构体初始化会展开成成员赋值和数组赋值；表达式通过 `emit_expr()` 生成临时变量和算术四元式；结构体数组访问 `Li.score[i]` 会被转换为 `Li_score[i]`，并生成 `T1 = Li_score[i]`。

控制流通过反条件跳转和回填实现。比如 `while (i < 5)` 先记录条件入口 `cond_start = 10`，再生成反条件跳转 `if i >= 5 goto 0`，其中 `0` 是占位。循环体生成完后生成 `goto 10` 回到条件入口，此时知道循环出口是 quad 17，于是把 quad 10 的目标回填成 17。if 也是一样，`if (T1 > max)` 生成反条件 `if T1 <= max goto 14`，条件为假时跳过 then 块。

最后目标代码生成器遍历四元式。它先把跳转目标四元式编号映射成汇编标签，然后每条四元式调用对应的生成函数：赋值生成 `MOV`，算术生成 `ADD/SUB/...`，条件跳转生成 `CMP + 条件跳转指令`，数组读取生成带偏移的内存访问，`printf` 调用输出辅助函数。最终程序遍历成绩数组，得到最大值 `100` 并输出。

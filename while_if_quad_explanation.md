# while-if 语法树、四元式和回填过程演示讲解

这份文档按“演示时可以直接讲出来”的顺序组织。讲解时先介绍语法树是怎么生成的，再落到 `src/c-code.c` 里的 while-if 代码，最后顺着 AST 生成四元式、回填和汇编控制流。

---

## 一、先介绍整体流程：源码如何走到语法树

演示可以先这样开头：

> 整个编译流程不是一上来就生成四元式，而是先经过词法分析、语法分析和 AST 构建。词法分析负责把 `c-code.c` 里的字符流切成 token；LL(1) 语法分析负责检查这些 token 的排列是否符合文法；确认语法合法以后，`ASTBuilder` 才把 token 组织成一棵更适合后续处理的抽象语法树。

对应总流程是：

```text
c-code.c 源码
  -> Lexer.tokenize()        生成 token 流
  -> LL1Parser.analyze()     用 LL(1) 预测分析表验证语法
  -> ASTBuilder.build()      把 token 流组织成 AST
  -> ASTSemanticAnalyzer     遍历 AST 建符号表
  -> ASTIRGenerator          遍历 AST 生成四元式
  -> CodeGenerator           把四元式翻译成汇编
```

这里要强调两点：

```text
LL(1) 语法分析：只判断结构是否合法，并记录分析过程。
AST 构建：把合法 token 流整理成树，后面的语义分析和四元式生成都按树节点来走。
```

也就是说，LL(1) 分析和 AST 构建不是重复关系。LL(1) 像“验票”，确认源码符合文法；ASTBuilder 像“整理座位表”，把源码结构整理成 `PROGRAM`、`FUNC_DEF`、`WHILE_STMT`、`IF_STMT`、`BINARY_EXPR` 这些节点。

---

## 二、语法树如何生成：`ASTBuilder` 的大致工作方式

接着讲 ASTBuilder：

> `ASTBuilder` 拿到 token 后，会先过滤预处理指令和 EOF，然后从 `build()` 开始顺序扫描。遇到 `struct student { ... };`，就调用 `parse_struct_decl()` 生成结构体定义节点；遇到 `int main() { ... }`，就调用 `try_parse_function()` 生成函数定义节点；进入函数体以后，每一条语句由 `parse_statement()` 分发。

可以用这张流程图讲：

```text
ASTBuilder.build()
├── 遇到 struct ... { ... }  -> parse_struct_decl() -> STRUCT_DECL
├── 遇到 int main() { ... }  -> try_parse_function() -> FUNC_DEF
└── 进入 main 的 { ... }     -> parse_block() -> COMPOUND_STMT
    ├── int i = 0            -> parse_declaration() -> VAR_DECL
    ├── int max = 0          -> parse_declaration() -> VAR_DECL
    ├── struct student Li... -> parse_declaration() -> VAR_DECL + INIT_LIST
    ├── while (...) {...}    -> parse_while() -> WHILE_STMT
    ├── printf(...)          -> parse_call_statement() -> FUNC_CALL
    └── return 0             -> parse_return() -> RETURN_STMT
```

其中 `parse_statement()` 是语句分发入口，可以这样理解：

```text
看到 "while"  -> parse_while()
看到 "if"     -> parse_if()
看到 "return" -> parse_return()
看到 "{"      -> parse_block()
看到 类型名   -> parse_declaration()
否则          -> 当作表达式语句 parse_expr()
```

表达式也会继续拆树：

```text
i < 5              -> BINARY_EXPR "<"
Li.score[i] > max  -> BINARY_EXPR ">"
Li.score           -> MEMBER_EXPR "score"
Li.score[i]        -> ARRAY_SUBSCRIPT
i++                -> UNARY_EXPR "++"
max = Li.score[i]  -> ASSIGN_EXPR "="
```

这一步结束后，我们已经不再面对零散 token，而是面对一棵能直接表达程序结构的 AST。

---

## 三、落到 `c-code.c`：先定位要讲的 while-if 片段

现在再进入具体代码：

```c
while (i < 5) {
    if (Li.score[i] > max) {
        max = Li.score[i];
    }
    i++;
}
```

这段代码位于 `main` 函数体内。在 AST 里，它不是孤立存在的，而是 `FUNC_DEF "main"` 下面 `COMPOUND_STMT` 的一条子语句。它前面还有三个声明：

```c
int i = 0;
int max = 0;
struct student Li = {"Li ping", 5, 18, {80, 90, 100, 86, 95}};
```

所以从四元式角度看，进入 while-if 之前，编译器已经完成了变量和结构体初始化，前面已经有 0 到 9 号四元式：

```text
0  (=, 0, _, i)
1  (=, 0, _, max)
2  (=, "Li ping", _, Li_name)
3  (=, 5, _, Li_num)
4  (=, 18, _, Li_age)
5  ([]=, 80, 0, Li_score)
6  ([]=, 90, 1, Li_score)
7  ([]=, 100, 2, Li_score)
8  ([]=, 86, 3, Li_score)
9  ([]=, 95, 4, Li_score)
```

也就是说，开始讲 while-if 时，当前下一条四元式编号正好是 10。

---

## 四、这段 while-if 对应的语法树

可以这样讲：

> 现在把视角聚焦到 while 这棵子树。`ASTBuilder.parse_while()` 看到 `while` 后，会先收集括号里的条件 token，也就是 `i < 5`，并把它交给 `parse_expr()` 生成 `BINARY_EXPR "<"`。然后它继续解析 while 后面的 `{ ... }`，生成一个 `COMPOUND_STMT` 作为循环体。循环体里面第一条是 if，所以 `parse_statement()` 会调用 `parse_if()`；第二条是 `i++`，会被解析成 `UNARY_EXPR "++"`。

对应结构是：

```text
WHILE_STMT
├── BINARY_EXPR "<"
│   ├── IDENTIFIER "i"
│   └── LITERAL "5"
└── COMPOUND_STMT
    ├── IF_STMT
    │   ├── BINARY_EXPR ">"
    │   │   ├── ARRAY_SUBSCRIPT
    │   │   │   ├── MEMBER_EXPR "score"
    │   │   │   │   └── IDENTIFIER "Li"
    │   │   │   └── IDENTIFIER "i"
    │   │   └── IDENTIFIER "max"
    │   └── COMPOUND_STMT
    │       └── ASSIGN_EXPR "="
    │           ├── IDENTIFIER "max"
    │           └── ARRAY_SUBSCRIPT
    │               ├── MEMBER_EXPR "score"
    │               │   └── IDENTIFIER "Li"
    │               └── IDENTIFIER "i"
    └── UNARY_EXPR "++"
        └── IDENTIFIER "i"
```

然后继续讲：

> 这棵树决定了后面的生成顺序。`ASTIRGenerator` 看到 `WHILE_STMT` 后，会先处理 while 条件；条件成立时顺序进入循环体；循环体里面第一个语句又是 `IF_STMT`，所以再进入 if 的生成逻辑；if 结束后再生成 `i++`；最后生成一条跳回 while 条件的无条件跳转。

这句话把 AST 和四元式生成顺序接上了。

---

## 五、有关代码逐段讲解：这棵树是怎么变成四元式的

这一节是演示时最重要的代码讲解部分。可以按“先建 AST，再生成四元式，再翻译汇编”的顺序讲。

### 1. `parse_while()`：把源码 while 变成 `WHILE_STMT`

相关代码在 `src/ast_core.py`：

```python
def parse_while(self) -> ASTNode:  # 解析 while 语句，返回 WHILE_STMT 节点。
    line = self.line(self.i)  # 记录 while 所在行号，方便 AST 展示和错误定位。
    cond_tokens, after_cond = self.collect_parenthesized(self.i + 1)  # 收集 while(...) 里的条件 token。
    self.i = after_cond  # 条件括号结束后，当前位置移动到循环体开头。
    body = self.parse_statement()  # 解析 while 后面的循环体，可能是单句或代码块。
    return ASTNode("WHILE_STMT", children=[self.parse_expr(cond_tokens), body or ASTNode("EMPTY_STMT", line=line)], line=line)  # 条件作为孩子 0，循环体作为孩子 1。
```

这段代码可以这样讲：

> `parse_while()` 做两件事。第一，它从 `while (` 后面取出括号里的条件 token，也就是 `i < 5`，然后用 `parse_expr()` 把它变成 `BINARY_EXPR "<"`。第二，它把括号后面的循环体 `{ ... }` 交给 `parse_statement()`，循环体会被解析成 `COMPOUND_STMT`。最后返回一个 `WHILE_STMT`，它的第 0 个孩子是条件，第 1 个孩子是循环体。

所以源码：

```c
while (i < 5) { ... }
```

会先变成：

```text
WHILE_STMT
├── BINARY_EXPR "<"
└── COMPOUND_STMT
```

### 2. `parse_if()`：把源码 if 变成 `IF_STMT`

相关代码：

```python
def parse_if(self) -> ASTNode:  # 解析 if 语句，返回 IF_STMT 节点。
    line = self.line(self.i)  # 记录 if 所在行号。
    cond_tokens, after_cond = self.collect_parenthesized(self.i + 1)  # 收集 if(...) 里的条件 token。
    self.i = after_cond  # 条件解析完后，当前位置指向 then 分支。
    then_node = self.parse_statement()  # 解析 then 分支，支持单句或 { ... }。
    children = [self.parse_expr(cond_tokens), then_node or ASTNode("EMPTY_STMT", line=line)]  # 前两个孩子固定是条件和 then。
    if self.attr(self.i) == "else":  # 如果 then 后面还有 else，就继续处理 else 分支。
        self.i += 1  # 跳过 else 关键字。
        children.append(self.parse_statement() or ASTNode("EMPTY_STMT", line=line))  # 把 else 分支作为第三个孩子。
    return ASTNode("IF_STMT", children=children, line=line)  # 返回完整 if 节点，后续用于生成跳转和回填。
```

这段代码对应源码：

```c
if (Li.score[i] > max) {
    max = Li.score[i];
}
```

讲解时可以这样说：

> `parse_if()` 先取出 if 括号里的条件 `Li.score[i] > max`。这个条件会被 `parse_expr()` 解析成一个 `BINARY_EXPR ">"`。它的左边 `Li.score[i]` 继续被拆成 `MEMBER_EXPR "score"` 和 `ARRAY_SUBSCRIPT`。然后 `parse_if()` 继续解析 then 块 `{ max = Li.score[i]; }`，最后返回 `IF_STMT`，它的孩子 0 是条件，孩子 1 是 then 块。

### 3. `gen_while()`：根据 `WHILE_STMT` 生成循环四元式

相关代码：

```python
def gen_while(self, node: ASTNode):  # 根据 WHILE_STMT 生成循环四元式。
    cond_start = self.ir.next_quad()  # 记录 while 条件入口，当前样例是第 10 条。
    cond = self.gen_condition(node.children[0])  # 把条件 AST 转成条件三元组，例如 ("i", "<", "5")。
    false_jumps = self.emit_false_jumps(cond)  # 生成反条件跳转，目标先用 0 占位。
    self.gen_stmt(node.children[1])  # 生成循环体，本例中包括 if 和 i++。
    self.ir.emit("j", "_", "_", str(cond_start))  # 循环体末尾跳回条件入口，形成回边。
    self.patch_jumps(false_jumps, self.ir.next_quad())  # 循环体结束后，把假出口回填到循环出口。
```

逐行对应当前四元式：

```text
cond_start = next_quad() = 10
cond = ("i", "<", "5")
emit_false_jumps(cond)  -> 10 (j>=, i, 5, 0)
gen_stmt(body)          -> 生成 11 到 15
emit("j", ..., 10)      -> 16 (j, _, _, 10)
patch_jumps(..., 17)    -> 10 (j>=, i, 5, 17)
```

这里最关键的是两点：

```text
1. cond_start 记录循环入口，所以第 16 条能跳回 10。
2. false_jumps 先占位，循环体全部生成完后才知道出口是 17。
```

### 4. `gen_if()`：根据 `IF_STMT` 生成 if 四元式

相关代码：

```python
def gen_if(self, node: ASTNode):  # 根据 IF_STMT 生成 if 控制流四元式。
    cond = self.gen_condition(node.children[0])  # 把 if 条件 AST 转成条件三元组，例如 ("T1", ">", "max")。
    false_jumps = self.emit_false_jumps(cond)  # 生成条件为假时的跳转，目标暂时占位。
    self.gen_stmt(node.children[1])  # 生成 then 分支；条件为真时会顺序执行到这里。
    if len(node.children) > 2:  # 有第三个孩子，说明存在 else 分支。
        j_end = self.ir.emit("j", "_", "_", "0")  # then 执行完后要跳过 else，目标先占位。
        self.patch_jumps(false_jumps, self.ir.next_quad())  # 假出口回填到 else 分支入口。
        self.gen_stmt(node.children[2])  # 生成 else 分支。
        self.patch_jump(j_end, self.ir.next_quad())  # then 末尾跳转回填到整个 if-else 后面。
    else:  # 当前 c-code.c 的 if 没有 else。
        self.patch_jumps(false_jumps, self.ir.next_quad())  # 假出口直接回填到 then 后面的下一条。
```

当前样例没有 `else`，所以走最后的 `else:` 分支。对应过程是：

```text
gen_condition(if 条件)  -> 先生成 11 (=[], Li_score, i, T1)，条件变成 T1 > max
emit_false_jumps(cond) -> 12 (j<=, T1, max, 0)
gen_stmt(then)         -> 13 (=, T1, _, max)
patch_jumps(..., 14)   -> 12 (j<=, T1, max, 14)
```

讲解时可以强调：

> if 的核心也是反条件跳转。`T1 > max` 为真时顺序执行 then；如果反条件 `T1 <= max` 成立，就跳到 then 后面，也就是第 14 条。

### 5. `gen_condition()` 和反条件跳转

相关代码：

```python
def gen_condition(self, node: ASTNode):  # 把条件 AST 统一转成后续跳转能用的结构。
    if node.kind == "BINARY_EXPR" and node.value == "&&":  # 逻辑与需要多个子条件都成立。
        return ("&&", [self.gen_condition(child) for child in node.children])  # 递归整理每个 && 子条件。
    if node.kind == "BINARY_EXPR" and node.value in self.supported_compare_ops:  # 普通比较条件，例如 <、>、==。
        return self.gen_expr(node.children[0]), node.value, self.gen_expr(node.children[1])  # 返回 left、op、right。
    value = self.gen_expr(node)  # 非比较条件先当作普通表达式求值。
    return value, "!=", "0"  # 例如 while(x) 按 x != 0 判断真假。
```

当前两个条件分别被整理成：

```text
i < 5              -> ("i", "<", "5")
Li.score[i] > max  -> ("T1", ">", "max")
```

注意第二个条件左边会先触发数组读取：

```text
Li.score[i] -> 11 (=[], Li_score, i, T1)
```

反条件跳转代码：

```python
def emit_inverse_cond_jump(self, cond) -> int:  # 生成“条件为假就跳走”的四元式。
    left, op, right = cond  # 拆出条件三元组，例如 ("i", "<", "5")。
    return self.ir.emit(f"j{self.inverse_compare.get(op, '==')}", left, right, "0")  # 发出反条件跳转，目标先占位。
```

反条件表是：

```python
inverse_compare = {"<": ">=", ">": "<=", "<=": ">", ">=": "<", "==": "!=", "!=": "=="}  # 比较符到反比较符的映射表。
```

所以：

```text
i < 5      -> j>=
T1 > max   -> j<=
```

### 6. `patch_jump()`：为什么要回填

相关代码：

```python
def patch_jump(self, jump_idx: int, target_idx: int):  # 回填单条跳转四元式。
    if 0 <= jump_idx < len(self.ir.quadruples):  # 确认保存的四元式编号有效。
        self.ir.quadruples[jump_idx].result = str(target_idx)  # 把占位目标 0 改成真实出口编号。

def patch_jumps(self, jumps: List[int], target_idx: int):  # 回填一组跳转四元式。
    for jump in jumps:  # 逐条处理需要跳到同一出口的四元式。
        self.patch_jump(jump, target_idx)  # 复用单条回填逻辑。
```

当前样例里有两次关键回填：

```text
if 回填：
12 (j<=, T1, max, 0)  ->  12 (j<=, T1, max, 14)

while 回填：
10 (j>=, i, 5, 0)     ->  10 (j>=, i, 5, 17)
```

可以这样讲：

> 生成条件跳转时，编译器还不知道要跳到哪里，因为 then 块或循环体还没生成完。所以先把目标写成 0，并保存这条四元式编号。等后面的代码生成完，`next_quad()` 就是正确出口，再用 `patch_jump()` 把 0 改成真正目标。

### 7. `gen_expr()`：`Li.score[i]` 和 `i++` 怎么生成四元式

成员访问和数组访问相关代码：

```python
elif node.kind == "MEMBER_EXPR":  # 处理结构体成员访问，例如 Li.score。
    base = self.gen_reference(node.children[0])  # 先拿到结构体变量名 Li。
    value = f"{base}_{node.value}"  # 把成员名扁平化成 Li_score，方便四元式和汇编使用。
elif node.kind == "ARRAY_SUBSCRIPT":  # 处理数组读取，例如 Li.score[i]。
    array_name = self.gen_reference(node.children[0])  # 数组本体 Li.score 会变成 Li_score。
    index = self.gen_expr(node.children[1])  # 生成下标表达式，本例是变量 i。
    temp = self.ir.new_temp()  # 申请临时变量保存数组元素值，例如 T1。
    self.ir.emit("=[]", array_name, index, temp)  # 生成 T1 = Li_score[i]。
    value = temp  # 这个数组表达式后续就用 T1 表示。
```

所以：

```text
Li.score     -> Li_score
Li.score[i]  -> 11 (=[], Li_score, i, T1)
```

自增相关代码：

```python
elif node.kind == "UNARY_EXPR" and node.value in {"++", "--"}:  # 处理 i++ 或 i--。
    target = self.gen_lvalue(node.children[0])  # 找到要被修改的左值，本例是 i。
    temp = self.ir.new_temp()  # 申请临时变量保存 i+1 的结果，本例是 T2。
    self.ir.emit("+" if node.value == "++" else "-", target, "1", temp)  # 生成 T2 = i + 1。
    self.ir.emit("=", temp, "_", target)  # 生成 i = T2，完成写回。
    self.clear_expr_cache()  # 变量值变了，清掉旧的表达式缓存。
    value = target  # 表达式结果仍看作这个变量本身。
```

所以：

```text
i++ -> 14 (+, i, 1, T2)
       15 (=, T2, _, i)
```

### 8. `codegen.py`：四元式如何翻译成汇编

先看标签扫描：

```python
def scan_labels(self):  # 预扫描四元式，为所有跳转目标准备汇编标签。
    """扫描四元式，为跳转目标生成标签"""  # 函数说明：数字目标要变成 L0/L1。
    for i, quad in enumerate(self.ir_gen.quadruples):  # 按编号遍历每一条四元式。
        if quad.op.startswith("j"):  # 只关心跳转类四元式，例如 j>=、j<=、j。
            if quad.result.isdigit():  # 跳转目标是数字编号时才需要映射。
                target = int(quad.result)  # 把目标编号字符串转成整数。
                if target not in self.label_map:  # 同一个目标只分配一次标签。
                    self.label_map[target] = f"L{len(self.label_map)}"  # 分配 L0、L1、L2 这样的标签名。
```

当前跳转目标是：

```text
17、14、10
```

它们会被映射成汇编标签，例如：

```text
17 -> L0
14 -> L1
10 -> L2
```

条件跳转翻译代码：

```python
def gen_jump(self, op: str, arg1: str, arg2: str, label: str):  # 把跳转四元式翻译成汇编跳转。
    """生成跳转代码"""  # 函数说明：处理 j、j>=、j<= 等。
    if op == "j":  # 无条件跳转，例如 16 (j, _, _, 10)。
        target = self.label_map.get(int(label) if label.isdigit() else -1, label)  # 把数字目标换成标签名。
        self.emit_code(f"    JMP {target}")  # 输出无条件跳转指令。
    else:  # 条件跳转需要先比较两个操作数。
        float_compare = self.is_float_operand(arg1) or self.is_float_operand(arg2)  # 判断是否按定点浮点方式比较。
        if self.is_number(arg1):  # 左操作数是常量。
            left_value = round(float(arg1) * self.fixed_scale) if float_compare else int(float(arg1))  # 常量转成汇编立即数。
            self.emit_code(f"    MOV AX, {left_value}")  # 左操作数放入 AX。
        else:  # 左操作数是变量或临时变量。
            self.emit_code(f"    MOV AX, {self.normalize_var_name(arg1)}")  # 从变量加载到 AX。

        if self.is_number(arg2):  # 右操作数是常量。
            right_value = round(float(arg2) * self.fixed_scale) if float_compare else int(float(arg2))  # 常量转成汇编立即数。
            self.emit_code(f"    MOV BX, {right_value}")  # 右操作数放入 BX。
        else:  # 右操作数是变量或临时变量。
            self.emit_code(f"    MOV BX, {self.normalize_var_name(arg2)}")  # 从变量加载到 BX。

        self.emit_code(f"    CMP AX, BX")  # 比较 AX 和 BX，为后面的条件跳转设置标志位。

        target = self.label_map.get(int(label) if label.isdigit() else -1, label)  # 找到要跳转到的汇编标签。
        jump_map = {  # 四元式跳转操作到汇编跳转指令的映射。
            "j<": "JL",  # 小于跳转。
            "j>": "JG",  # 大于跳转。
            "j<=": "JLE",  # 小于等于跳转。
            "j>=": "JGE",  # 大于等于跳转。
            "j==": "JE",  # 相等跳转。
            "j!=": "JNE"  # 不等跳转。
        }
        jump_inst = jump_map.get(op, "JMP")  # 根据四元式 op 选汇编跳转指令。
        self.emit_code(f"    {jump_inst} {target}")  # 输出条件跳转，例如 JGE L0。
```

对应关系：

```text
10 (j>=, i, 5, 17)       -> CMP i, 5 后 JGE L0
12 (j<=, T1, max, 14)    -> CMP T1, max 后 JLE L1
16 (j, _, _, 10)         -> JMP L2
```

数组读取翻译代码：

```python
def gen_array_load(self, array: str, index: str, result: str):  # 翻译 =[] 数组读取四元式。
    """生成数组读取代码"""  # 函数说明：result = array[index]。
    clean_array = array.replace('.', '_')  # 统一数组名格式，成员数组写成 Li_score。

    if self.is_number(index):  # 下标是常量时，可以直接算偏移。
        offset = int(index) * 2  # DW 数组每个元素 2 字节，所以偏移是 index * 2。
        self.emit_code(f"    MOV AX, {clean_array}[{offset}]")  # 直接从数组固定偏移读取。
    else:  # 下标是变量时，需要运行时计算偏移。
        self.emit_code(f"    MOV BX, {index}")  # 把下标值放入 BX。
        self.emit_code(f"    SHL BX, 1  ; 乘以2")  # BX 左移一位，相当于乘 2。
        self.emit_code(f"    MOV AX, {clean_array}[BX]")  # 用 BX 作为数组偏移读取元素。

    self.emit_code(f"    MOV {result}, AX")  # 把读出的数组元素保存到目标临时变量。
```

第 11 条：

```text
11 (=[], Li_score, i, T1)
```

会变成：

```asm
MOV BX, i              ; 把下标 i 放入 BX
SHL BX, 1              ; 下标乘 2，换算成 DW 数组的字节偏移
MOV AX, Li_score[BX]   ; 从 Li_score[i] 读取成绩到 AX
MOV T1, AX             ; 把数组元素保存到临时变量 T1
```

这里 `SHL BX, 1` 是因为 `Li_score` 是 `DW` 数组，一个元素占 2 字节，数组下标要换算成字节偏移。

---

## 六、进入 while：先记住循环入口

演示时接着讲：

> 现在进入 `ASTIRGenerator.gen_while()`。生成 while 的第一步不是立刻输出跳转，而是先记录“循环条件从哪一条四元式开始”。因为前面初始化已经生成到 9 号，所以下一条就是 10。

对应代码逻辑：

```python
cond_start = self.ir.next_quad()  # 记录 while 条件入口编号。
```

此时：

```text
cond_start = 10
```

这个 10 很重要，因为循环体执行完以后，要靠它跳回条件判断。

---

## 七、生成 while 条件：`i < 5` 变成 `j>=`

然后讲 while 条件：

> while 的源码条件是 `i < 5`。编译器先把这个条件节点交给 `gen_condition()`，得到一个逻辑条件三元组，可以理解成 `("i", "<", "5")`。但是生成控制流时，编译器采用的是“反条件跳转”：条件为假就跳出，条件为真就自然往下执行。

所以：

```text
源码条件：i < 5
反条件：i >= 5
```

于是先生成一条“假出口”跳转：

```text
10 (j>=, i, 5, 0)
```

这里先写成目标 `0`，不是因为真的要跳到 0，而是因为此时还不知道循环出口在哪里。循环体还没生成完，出口编号暂时未知，所以先占位。

演示时可以强调：

> 第 10 条四元式的意思是：如果 `i >= 5`，说明 while 条件 `i < 5` 为假，就应该跳出循环。跳出到哪儿现在还不知道，所以目标先占位，稍后回填。

---

## 八、进入 while 循环体：先遇到 if

第 10 条生成以后，如果条件为真，也就是 `i < 5` 成立，程序不会跳走，而是顺序执行下一条四元式。接下来进入循环体，循环体第一条语句是：

```c
if (Li.score[i] > max) {
    max = Li.score[i];
}
```

可以这样讲：

> 现在 `gen_while()` 调用 `gen_stmt()` 生成循环体。循环体里面首先遇到 `IF_STMT`，于是进入 `ASTIRGenerator.gen_if()`。if 也采用同样的反条件跳转策略：条件为假就跳过 then 块，条件为真就顺序执行 then 块。

---

## 九、生成 if 条件前，先计算 `Li.score[i]`

if 的条件是：

```c
Li.score[i] > max
```

它左边不是普通变量，而是结构体成员数组访问。这里要先把 `Li.score[i]` 取出来。

AST 中它长这样：

```text
ARRAY_SUBSCRIPT
├── MEMBER_EXPR "score"
│   └── IDENTIFIER "Li"
└── IDENTIFIER "i"
```

可以这样讲：

> 编译器处理成员访问时，会把 `Li.score` 扁平化成一个汇编友好的名字 `Li_score`。然后处理数组下标 `[i]` 时，需要生成一条数组读取四元式，把 `Li_score[i]` 的值读到临时变量里。

所以生成第 11 条：

```text
11 (=[], Li_score, i, T1)
```

它的含义是：

```text
T1 = Li_score[i]
```

这里的 `T1` 是 `IRGenerator.new_temp()` 生成的临时变量。

---

## 十、if 条件 `T1 > max` 变成 `j<=`

现在 if 条件已经从：

```c
Li.score[i] > max
```

变成了：

```text
T1 > max
```

继续讲：

> if 也用反条件跳转。源码判断是 `T1 > max`，它的反条件就是 `T1 <= max`。如果 `T1 <= max` 成立，说明当前成绩没有超过最大值，就不需要执行 `max = T1`，应该直接跳到 if 后面的语句，也就是 `i++`。

于是先生成占位跳转：

```text
12 (j<=, T1, max, 0)
```

这里目标也先写 `0`，因为 then 块还没有生成，暂时不知道 then 块后面的第一条四元式编号是多少。

---

## 十一、生成 if 的 then 块：`max = Li.score[i]`

如果第 12 条条件不成立，也就是 `T1 > max`，程序会顺序进入 then 块：

```c
max = Li.score[i];
```

这里可以自然接上前面：

> 注意，条件里刚刚已经读取过一次 `Li.score[i]`，并且结果保存在 `T1` 里。当前 `ASTIRGenerator` 有表达式缓存，同一个数组表达式在 then 块里会复用前面生成的 `T1`，所以这里不再生成第二条数组读取，而是直接把 `T1` 赋值给 `max`。

生成第 13 条：

```text
13 (=, T1, _, max)
```

含义是：

```text
max = T1
```

到这里，if 的 then 块生成完了。下一条四元式编号变成 14。

---

## 十二、回填 if 的假出口到 14

现在可以回到第 12 条的占位目标。

刚才第 12 条是：

```text
12 (j<=, T1, max, 0)
```

then 块生成完后，下一条四元式编号是 14，也就是 if 后面的 `i++`。所以把第 12 条回填成：

```text
12 (j<=, T1, max, 14)
```

演示时可以这样讲：

> 这就是 if 的回填。`j<=` 代表 if 条件为假时跳过 then 块。then 块结束后，编译器才知道“跳过 then 块”应该跳到 14，于是把原来的占位目标改成 14。

此时 if 语句完整生成完成：

```text
11 (=[], Li_score, i, T1)
12 (j<=, T1, max, 14)
13 (=, T1, _, max)
```

---

## 十三、生成 while 体里的 `i++`

if 结束后，循环体里还有一条语句：

```c
i++;
```

AST 是：

```text
UNARY_EXPR "++"
└── IDENTIFIER "i"
```

可以这样讲：

> 自增运算不会作为一条特殊机器指令保留在四元式里，而是拆成“先加一，再写回”两步。

所以生成：

```text
14 (+, i, 1, T2)
15 (=, T2, _, i)
```

含义是：

```text
T2 = i + 1
i = T2
```

到这里，while 循环体已经全部生成完。

---

## 十四、循环体结束：跳回 while 条件入口 10

现在要完成 while 的循环结构。

前面进入 while 时记录过：

```text
cond_start = 10
```

所以循环体结束后，必须生成一条无条件跳转，回到第 10 条重新判断 `i < 5`：

```text
16 (j, _, _, 10)
```

可以这样讲：

> 第 16 条就是 while 的回边。它把控制流从循环体末尾拉回条件入口 10。没有这条回跳，while 就只会执行一次。

---

## 十五、回填 while 的假出口到 17

现在循环体和回跳都生成完了。下一条四元式编号是 17，也就是循环后面的：

```c
printf("%d", max);
```

所以最开始占位的 while 假出口：

```text
10 (j>=, i, 5, 0)
```

可以回填成：

```text
10 (j>=, i, 5, 17)
```

演示时可以这样讲：

> 这就是 while 的回填。第 10 条表示 while 条件为假时跳出循环。只有当整个循环体和回跳都生成完以后，编译器才知道循环出口是第 17 条，所以把第 10 条的目标从占位值改成 17。

至此，while-if 这段代码完整生成了：

```text
10 (j>=, i, 5, 17)
11 (=[], Li_score, i, T1)
12 (j<=, T1, max, 14)
13 (=, T1, _, max)
14 (+, i, 1, T2)
15 (=, T2, _, i)
16 (j, _, _, 10)
```

---

## 十六、把四元式按执行顺序讲一遍

演示时可以直接照这段讲：

> 第 10 条先判断 while 条件的反条件：如果 `i >= 5`，就跳到 17，退出循环；如果不跳，说明 `i < 5` 成立，就进入循环体。第 11 条读取当前成绩 `Li_score[i]` 到临时变量 `T1`。第 12 条判断 if 的反条件：如果 `T1 <= max`，说明当前成绩不比最大值大，就跳到 14，跳过更新 max；如果不跳，就执行第 13 条，把 `T1` 赋给 `max`。接着第 14、15 条完成 `i++`，最后第 16 条无条件跳回 10，开始下一轮循环。

四元式含义表：

```text
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

---

## 十七、汇编层面怎么对应

接着从四元式过渡到汇编：

> 汇编生成时，四元式里的跳转目标是数字编号，例如 17、14、10。但是汇编需要标签，所以 `CodeGenerator.scan_labels()` 会先扫描所有跳转四元式，把这些数字目标映射成标签。然后 `translate_quadruple()` 再逐条翻译。

相关目标是：

```text
17 -> while 出口
14 -> if 假出口，也就是 i++ 开始处
10 -> while 条件入口
```

汇编结构可以这样理解：

```asm
L2:                         ; while 条件入口，对应四元式 10
    ; [10] (j>=, i, 5, 17)  ; 如果 i >= 5，就退出 while
    MOV AX, i               ; 左操作数 i 放入 AX
    MOV BX, 5               ; 右操作数 5 放入 BX
    CMP AX, BX              ; 比较 i 和 5
    JGE L0                  ; i >= 5 时跳到 while 出口 L0

    ; [11] (=[], Li_score, i, T1) ; 读取 Li_score[i]
    MOV BX, i               ; 下标 i 放入 BX
    SHL BX, 1               ; DW 数组元素占 2 字节，下标乘 2
    MOV AX, Li_score[BX]    ; 读取 Li_score[i] 到 AX
    MOV T1, AX              ; 保存数组元素到临时变量 T1

    ; [12] (j<=, T1, max, 14) ; 如果 T1 <= max，就跳过 then 块
    MOV AX, T1              ; 左操作数 T1 放入 AX
    MOV BX, max             ; 右操作数 max 放入 BX
    CMP AX, BX              ; 比较 T1 和 max
    JLE L1                  ; T1 <= max 时跳到 i++ 的入口 L1

    ; [13] (=, T1, _, max)  ; then 块：max = T1
    MOV AX, T1              ; 把 T1 先放入 AX
    MOV max, AX             ; 再写回 max

L1:                         ; if 假出口，也是 i++ 的开始
    ; [14] (+, i, 1, T2)    ; 计算 i + 1
    MOV AX, i               ; i 放入 AX
    MOV BX, 1               ; 常量 1 放入 BX
    ADD AX, BX              ; AX = i + 1
    MOV T2, AX              ; 保存结果到 T2

    ; [15] (=, T2, _, i)    ; 把 T2 写回 i
    MOV AX, T2              ; T2 放入 AX
    MOV i, AX               ; i = T2

    ; [16] (j, _, _, 10)    ; while 体结束后回到条件
    JMP L2                  ; 无条件跳回 L2

L0:                         ; while 出口，对应四元式 17
    ; [17] (printf, _, _, max) ; 输出 max
    MOV AX, max             ; 把 max 放入 AX，供输出例程使用
    CALL dispsiw            ; 调用整数输出过程
```

这里可以补一句：

> `=[]` 读取数组时，汇编里用 `BX` 保存下标偏移。因为数组元素是 `DW`，一个元素 2 字节，所以会先 `SHL BX, 1`，相当于把下标乘以 2。

---

## 十八、最后用运行效果收尾

最后把控制流和程序结果接起来：

```text
初始：i = 0, max = 0

i = 0: Li_score[0] = 80,  80 > 0,   max = 80
i = 1: Li_score[1] = 90,  90 > 80,  max = 90
i = 2: Li_score[2] = 100, 100 > 90, max = 100
i = 3: Li_score[3] = 86,  86 <= 100, max 不变
i = 4: Li_score[4] = 95,  95 <= 100, max 不变
i = 5: i >= 5 成立，跳到 17，退出循环
```

最终：

```text
printf("%d", max) 输出 100
```

---

## 十九、完整口播版

如果演示时间比较短，可以直接用这一版：

```text
整个流程先从源码开始。Lexer 把 c-code.c 切成 token，LL(1) 语法分析先验证 token 序列符合文法。语法通过后，ASTBuilder 才开始建语法树：遇到 struct student 生成 STRUCT_DECL，遇到 int main 生成 FUNC_DEF，进入 main 的代码块后，变量声明生成 VAR_DECL，while 语句生成 WHILE_STMT。

具体到这段 while-if，ASTBuilder.parse_while() 先把 while 条件 i<5 解析成 BINARY_EXPR "<"，再把循环体解析成 COMPOUND_STMT。循环体里第一条 if 由 parse_if() 解析成 IF_STMT，if 条件 Li.score[i]>max 解析成 BINARY_EXPR ">"，其中 Li.score[i] 又被拆成 MEMBER_EXPR "score" 和 ARRAY_SUBSCRIPT。循环体第二条 i++ 被解析成 UNARY_EXPR "++"。所以后面四元式生成不是再从 token 硬扫，而是按这棵 AST 的节点顺序往下走。

进入 IR 生成时，前面初始化已经生成了 0 到 9 号四元式，所以下一条是 10。编译器先处理外层 WHILE_STMT，记录条件入口 cond_start=10。while 条件是 i<5，但我们的控制流采用反条件跳转，所以生成 j>=，先得到 10: if i>=5 goto 占位。

然后进入循环体，第一条语句是 if。if 的条件是 Li.score[i]>max。由于 Li.score[i] 是结构体成员数组访问，先把 Li.score 扁平化成 Li_score，再生成数组读取：11: T1=Li_score[i]。
现在 if 条件就变成 T1>max，同样采用反条件跳转，所以生成 12: if T1<=max goto 占位。

接着生成 if 的 then 块。then 块是 max=Li.score[i]，因为条件中已经读过 Li_score[i] 并保存在 T1，所以这里直接生成 13: max=T1。
then 块结束后，下一条是 14，也就是 if 后面的 i++，所以把第 12 条回填成 if T1<=max goto 14。

然后生成 i++，它被拆成两条四元式：14: T2=i+1，15: i=T2。
循环体结束后，要跳回 while 条件入口，所以生成 16: goto 10。
这时整个循环体已经结束，下一条四元式是 17，也就是循环后面的 printf，所以把第 10 条 while 假出口回填成 if i>=5 goto 17。

最终 while-if 片段就是 10 到 16：第 10 条负责退出循环，第 11 条读取当前成绩，第 12 条负责跳过 if then 块，第 13 条更新 max，第 14 和 15 条完成 i++，第 16 条跳回条件入口。执行完五轮后 i 变成 5，第 10 条跳到 17，输出 max，也就是 100。
```

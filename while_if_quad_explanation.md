# while-if 语法树、四元式和回填过程讲解

本文专门解释 `src/c-code.c` 中这段代码如何变成四元式和汇编控制流：

```c
while (i < 5) {
    if (Li.score[i] > max) {
        max = Li.score[i];
    }
    i++;
}
```

当前有效实现位置：

- AST 中 while 节点构建：`src/ast_core.py` 的 `ASTBuilder.parse_while()`
- AST 中 if 节点构建：`src/ast_core.py` 的 `ASTBuilder.parse_if()`
- 成员和数组表达式构建：`src/ast_core.py` 的 `ASTBuilder.parse_postfix()`
- while 四元式生成：`src/ast_core.py` 的 `ASTIRGenerator.gen_while()`
- if 四元式生成：`src/ast_core.py` 的 `ASTIRGenerator.gen_if()`
- 条件反跳转生成：`src/ast_core.py` 的 `gen_condition()`、`emit_false_jumps()`、`emit_inverse_cond_jump()`
- 数组读取四元式：`src/ast_core.py` 的 `gen_expr()` 中 `ARRAY_SUBSCRIPT` 分支
- 自增四元式：`src/ast_core.py` 的 `gen_expr()` 中 `UNARY_EXPR ++` 分支
- 汇编标签扫描和四元式翻译：`src/codegen.py` 的 `scan_labels()`、`translate_quadruple()`、`gen_jump()`、`gen_array_load()`

---

## 1. 这段代码对应的 AST

源码：

```c
while (i < 5) {
    if (Li.score[i] > max) {
        max = Li.score[i];
    }
    i++;
}
```

抽象成 AST 后，关键结构是：

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
    │       └── EXPR_STMT
    │           └── ASSIGN_EXPR "="
    │               ├── IDENTIFIER "max"
    │               └── ARRAY_SUBSCRIPT
    │                   ├── MEMBER_EXPR "score"
    │                   │   └── IDENTIFIER "Li"
    │                   └── IDENTIFIER "i"
    └── EXPR_STMT
        └── UNARY_EXPR "++"
            └── IDENTIFIER "i"
```

这里有三个重点：

1. `while (i < 5)` 是一个 `WHILE_STMT`，条件是 `BINARY_EXPR "<"`。
2. `if (Li.score[i] > max)` 是一个 `IF_STMT`，条件是 `BINARY_EXPR ">"`。
3. `Li.score[i]` 被拆成 `MEMBER_EXPR "score"` 和 `ARRAY_SUBSCRIPT`，后续 IR 会把 `Li.score` 扁平化成 `Li_score`。

---

## 2. 对应四元式

完整程序生成的四元式中，while-if 片段是第 10 到 16 条：

```text
10 (j>=, i, 5, 17)
11 (=[], Li_score, i, T1)
12 (j<=, T1, max, 14)
13 (=, T1, _, max)
14 (+, i, 1, T2)
15 (=, T2, _, i)
16 (j, _, _, 10)
```

加上循环后的输出和返回：

```text
17 (printf, _, _, max)
18 (return, 0, _, _)
```

四元式含义：

```text
10 如果 i >= 5，跳到 17，退出 while
11 T1 = Li_score[i]
12 如果 T1 <= max，跳到 14，跳过 if 的 then 块
13 max = T1
14 T2 = i + 1
15 i = T2
16 goto 10，回到 while 条件
17 输出 max
18 返回 0
```

---

## 3. while 为什么生成 `j>=`

源码条件是：

```c
i < 5
```

但四元式是：

```text
10 (j>=, i, 5, 17)
```

原因是当前 IR 生成采用“反条件跳转”：

```text
条件为假时跳出去，条件为真时顺序执行下一条。
```

`i < 5` 的反条件是：

```text
i >= 5
```

所以 while 开头生成：

```text
if i >= 5 goto 循环出口
```

在 `ASTIRGenerator.gen_while()` 中，核心逻辑是：

```python
cond_start = self.ir.next_quad()
cond = self.gen_condition(node.children[0])
false_jumps = self.emit_false_jumps(cond)
self.gen_stmt(node.children[1])
self.ir.emit("j", "_", "_", str(cond_start))
self.patch_jumps(false_jumps, self.ir.next_quad())
```

逐句解释：

- `cond_start = self.ir.next_quad()`：记录 while 条件入口。当前前面已有 0 到 9 号初始化四元式，所以下一条是 10。
- `gen_condition()`：把 AST 条件 `i < 5` 转成三元组 `("i", "<", "5")`。
- `emit_false_jumps()`：根据反条件生成跳转，也就是 `j>=`。
- `gen_stmt(body)`：生成循环体里的 if 和 `i++`。
- `emit("j", ..., cond_start)`：循环体末尾跳回条件入口 10。
- `patch_jumps(false_jumps, next_quad)`：循环体生成完后，下一条四元式是 17，所以把第 10 条的目标回填为 17。

---

## 4. if 为什么生成 `j<=`

源码条件是：

```c
Li.score[i] > max
```

这个条件左边不是简单变量，而是数组读取。IR 先生成：

```text
11 (=[], Li_score, i, T1)
```

含义是：

```text
T1 = Li_score[i]
```

然后再判断：

```text
12 (j<=, T1, max, 14)
```

源码条件是 `T1 > max`，反条件是 `T1 <= max`，所以生成 `j<=`。它的含义是：

```text
如果 T1 <= max，说明 if 条件为假，跳到 14，跳过 max = T1。
```

在 `ASTIRGenerator.gen_if()` 中，核心逻辑是：

```python
cond = self.gen_condition(node.children[0])
false_jumps = self.emit_false_jumps(cond)
self.gen_stmt(node.children[1])
self.patch_jumps(false_jumps, self.ir.next_quad())
```

当前 if 没有 `else`，所以 then 块结束后，假出口直接回填到 then 后面的下一条四元式。then 块只有：

```c
max = Li.score[i];
```

由于条件里已经生成过 `Li_score[i]` 的读取，并且 `ASTIRGenerator` 有表达式缓存，then 中同一个数组表达式复用 `T1`，所以 then 块只生成：

```text
13 (=, T1, _, max)
```

then 块结束后下一条是 `i++` 的第一条四元式，也就是 14。因此第 12 条被回填成：

```text
12 (j<=, T1, max, 14)
```

---

## 5. `Li.score[i]` 如何变成 `Li_score[i]`

AST 中的成员访问和数组访问是嵌套的：

```text
ARRAY_SUBSCRIPT
├── MEMBER_EXPR "score"
│   └── IDENTIFIER "Li"
└── IDENTIFIER "i"
```

IR 生成时：

```python
elif node.kind == "MEMBER_EXPR":
    base = self.gen_reference(node.children[0])
    value = f"{base}_{node.value}"
elif node.kind == "ARRAY_SUBSCRIPT":
    array_name = self.gen_reference(node.children[0])
    index = self.gen_expr(node.children[1])
    temp = self.ir.new_temp()
    self.ir.emit("=[]", array_name, index, temp)
    value = temp
```

所以：

```text
IDENTIFIER "Li"           -> Li
MEMBER_EXPR "score"       -> Li_score
ARRAY_SUBSCRIPT [i]       -> (=[], Li_score, i, T1)
```

这里的 `T1` 是 `IRGenerator.new_temp()` 生成的临时变量。

---

## 6. `i++` 如何变成两条四元式

源码：

```c
i++;
```

AST：

```text
UNARY_EXPR "++"
└── IDENTIFIER "i"
```

IR 生成逻辑：

```python
target = self.gen_lvalue(node.children[0])
temp = self.ir.new_temp()
self.ir.emit("+", target, "1", temp)
self.ir.emit("=", temp, "_", target)
```

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

---

## 7. 回填全过程

进入 while 之前，已经生成 0 到 9 号初始化四元式：

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
```

### 7.1 记录 while 入口

```text
cond_start = next_quad() = 10
```

### 7.2 生成 while 假出口，占位

先生成：

```text
10 (j>=, i, 5, 0)
```

此时还不知道循环出口是哪一条，所以目标先填 `"0"`。

### 7.3 生成 if 条件左值

```text
11 (=[], Li_score, i, T1)
```

### 7.4 生成 if 假出口，占位

先生成：

```text
12 (j<=, T1, max, 0)
```

### 7.5 生成 if then 块

```text
13 (=, T1, _, max)
```

### 7.6 回填 if 假出口

then 块结束后，下一条四元式编号是 14，所以：

```text
12 (j<=, T1, max, 14)
```

### 7.7 生成 `i++`

```text
14 (+, i, 1, T2)
15 (=, T2, _, i)
```

### 7.8 生成 while 回跳

```text
16 (j, _, _, 10)
```

### 7.9 回填 while 假出口

循环体和回跳都生成完后，下一条四元式编号是 17，所以：

```text
10 (j>=, i, 5, 17)
```

最终得到：

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

## 8. 汇编控制流如何对应四元式

`CodeGenerator.scan_labels()` 会把四元式中的数字目标转换为汇编标签。当前相关目标有：

```text
17: while 出口
14: if 假出口，也就是 i++ 开始处
10: while 条件入口
```

汇编结构大致是：

```asm
L2:
    ; [10] (j>=, i, 5, 17)
    MOV AX, i
    MOV BX, 5
    CMP AX, BX
    JGE L0

    ; [11] (=[], Li_score, i, T1)
    MOV BX, i
    SHL BX, 1
    MOV AX, Li_score[BX]
    MOV T1, AX

    ; [12] (j<=, T1, max, 14)
    MOV AX, T1
    MOV BX, max
    CMP AX, BX
    JLE L1

    ; [13] (=, T1, _, max)
    MOV AX, T1
    MOV max, AX

L1:
    ; [14] (+, i, 1, T2)
    MOV AX, i
    MOV BX, 1
    ADD AX, BX
    MOV T2, AX

    ; [15] (=, T2, _, i)
    MOV AX, T2
    MOV i, AX

    ; [16] (j, _, _, 10)
    JMP L2

L0:
    ; [17] (printf, _, _, max)
    MOV AX, max
    CALL dispsiw
```

关键对应关系：

```text
j>= -> JGE
j<= -> JLE
j   -> JMP
=[] -> 用 BX 计算 index * 2，然后读取 array[BX]
+   -> ADD + 赋值
```

---

## 9. 执行结果

四元式执行效果：

```text
初始：i=0, max=0

i=0: Li_score[0]=80  > 0   -> max=80
i=1: Li_score[1]=90  > 80  -> max=90
i=2: Li_score[2]=100 > 90  -> max=100
i=3: Li_score[3]=86  <=100 -> max 不变
i=4: Li_score[4]=95  <=100 -> max 不变
i=5: i >= 5，跳出循环
```

最后：

```text
printf("%d", max) -> 100
```

---

## 10. 一句话答辩版

```text
while 和 if 都采用反条件跳转。while(i<5) 先生成 j>=，目标暂时占位，循环体结束后回填到循环出口 17；
if(Li.score[i]>max) 先用 =[] 把数组元素读到 T1，再生成 j<=，then 块结束后回填到 14。
i++ 被拆成 T2=i+1 和 i=T2。最后无条件 j 回到 10，形成循环。
```

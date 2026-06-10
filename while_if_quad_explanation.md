# while-if 语法树、四元式和代码实现讲解

本文档专门解释图中的这一段：

```c
while (i < 5) {
    if (Li.score[i] > max) {
        max = Li.score[i];
    }

    i++;
}
```

对应四元式：

```text
10 (j>=, i, 5, 17)
11 (=[], Li_score, i, T1)
12 (j<=, T1, max, 14)
13 (=, T1, _, max)
14 (+, i, 1, T2)
15 (=, T2, _, i)
16 (j, _, _, 10)
17 (printf, _, _, max)
18 (return, 0, _, _)
```

相关代码位置：

- while 翻译：`src/compiler.py:1214`
- if 翻译：`src/compiler.py:1183`
- 结构体/数组引用翻译：`src/compiler.py:616`
- 表达式翻译：`src/compiler.py:657`
- 条件解析：`src/compiler.py:763`、`src/compiler.py:788`
- false list 生成：`src/compiler.py:810`
- 回填：`src/compiler.py:801`、`src/compiler.py:815`
- 四元式生成 `emit()`：`src/ir_generator.py:78`
- 汇编标签扫描：`src/codegen.py:231`
- 四元式到汇编分发：`src/codegen.py:281`
- 跳转汇编生成：`src/codegen.py:512`
- 数组读取汇编生成：`src/codegen.py:616`

---

## 1. 这段源码的语法结构

源码：

```c
while (i < 5) {
    if (Li.score[i] > max) {
        max = Li.score[i];
    }

    i++;
}
```

语法树可以抽象成：

```text
WHILE_STMT
├── condnode: i < 5
└── bodynode:
    ├── IF_STMT
    │   ├── condnode: Li.score[i] > max
    │   └── thennode: max = Li.score[i]
    └── EXPR_STMT: i++
```

也就是说：

- `WHILE_STMT` 的条件节点是 `i < 5`。
- `WHILE_STMT` 的循环体是一个 `COMPOUND_STMT`。
- 这个循环体里有两条语句：
  - 一个 `IF_STMT`
  - 一个 `i++`
- `IF_STMT` 的条件是 `Li.score[i] > max`。
- `IF_STMT` 的 then 块是 `max = Li.score[i]`。

---

## 2. while 条件如何生成四元式 10

while 的条件节点是：

```text
BINARY_EXPR
├── op: <
├── IDENTIFIER: i
└── LITERAL_INT: 5
```

也就是：

```c
i < 5
```

代码进入 while 分支：

```python
if cur_attr == "while":
```

位置：

```text
src/compiler.py:1214
```

核心代码：

```python
cond_start = ir.next_quad()
cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
cond = parse_condition_tokens(cond_tokens)
i = after_cond
```

逐行解释：

```python
cond_start = ir.next_quad()
```

进入 while 前，已经生成了 0 到 9 号四元式：

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

所以下一条四元式编号是 10：

```text
cond_start = 10
```

这个 10 就是 while 条件判断入口。循环体结束后要跳回这里。

```python
cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
```

这行从 `while (` 后面取出括号里的条件 token：

```text
i < 5
```

所以得到：

```python
cond_tokens = [i, <, 5]
```

```python
cond = parse_condition_tokens(cond_tokens)
```

`parse_condition_tokens()` 最终调用 `parse_simple_condition()`，把：

```text
i < 5
```

拆成：

```python
cond = ("i", "<", "5")
```

这就对应语法树里的 while 条件节点。

---

## 3. 为什么四元式 10 是反条件

源码是：

```c
while (i < 5)
```

但四元式是：

```text
10 (j>=, i, 5, 17)
```

可读形式：

```text
10 if i >= 5 goto 17
```

原因是代码生成控制流时采用“反条件跳转”。

while 的执行逻辑是：

```text
如果 i < 5 为真：进入循环体
如果 i < 5 为假：跳出循环
```

`i < 5` 的反条件是：

```text
i >= 5
```

所以生成：

```text
if i >= 5 goto 循环出口
```

对应代码：

```python
false_jumps = emit_false_jumps(cond)
```

位置：

```text
src/compiler.py:1227
```

`emit_false_jumps()` 位置：

```text
src/compiler.py:810
```

它内部调用：

```python
emit_inverse_cond_jump(cond, placeholder)
```

位置：

```text
src/compiler.py:805
```

反条件表是：

```python
inverse_compare = {
    "<": ">=",
    ">": "<=",
    "<=": ">",
    ">=": "<",
    "==": "!=",
    "!=": "=="
}
```

所以：

```python
("i", "<", "5")
```

会生成：

```text
10 (j>=, i, 5, 0)
```

注意：刚生成时目标是 `0`，因为这时还不知道 while 结束后是哪一条四元式。

此时记录：

```text
while.false_list = {10}
```

意思是：

```text
第 10 条四元式的跳转目标以后要回填。
```

最终会执行：

```text
bp({10}, 17)
```

也就是把第 10 条四元式的目标从 `0` 改成 `17`。

---

## 4. while 的 bodynode 如何展开

while 的循环体是：

```c
{
    if (Li.score[i] > max) {
        max = Li.score[i];
    }

    i++;
}
```

语法树中对应：

```text
COMPOUND_STMT
├── IF_STMT
└── EXPR_STMT i++
```

代码里 while 分支执行：

```python
parse_statement()
```

位置：

```text
src/compiler.py:1229
```

因为当前 token 是 `{`，所以进入代码块分支：

```python
if cur_attr == "{":
```

位置：

```text
src/compiler.py:1077
```

代码块分支会循环解析块内语句：

```python
while i < n and tok_attr(i) != "}":
    parse_statement()
```

因此它先解析 `if`，再解析 `i++`。

---

## 5. if 条件如何生成四元式 11 和 12

if 的条件节点是：

```text
BINARY_EXPR
├── op: >
├── ARRAY_SUBSCRIPT: Li.score[i]
└── IDENTIFIER: max
```

源码：

```c
if (Li.score[i] > max)
```

代码进入 if 分支：

```python
if cur_attr == "if":
```

位置：

```text
src/compiler.py:1183
```

核心代码：

```python
cond_tokens, after_cond = parse_parenthesized_tokens(i + 1)
cond = parse_condition_tokens(cond_tokens)
i = after_cond
false_jumps = emit_false_jumps(cond)
parse_statement()
patch_jumps(false_jumps, ir.next_quad())
```

首先取出 if 条件：

```text
Li.score[i] > max
```

条件解析时会拆成：

```text
左边：Li.score[i]
操作符：>
右边：max
```

右边 `max` 是普通标识符，直接返回 `"max"`。

左边 `Li.score[i]` 要先翻译成数组读取四元式。

---

## 6. `Li.score[i]` 如何变成四元式 11

处理位置：

```text
src/compiler.py:616
```

函数：

```python
parse_reference_operand(expr_tokens)
```

`Li.score[i]` 的 token 大致是：

```text
Li . score [ i ]
```

第一步，先读到 `Li`：

```python
ref = "Li"
```

第二步，遇到点号 `.`：

```python
ref = f"{ref}_{成员名}"
```

所以：

```text
Li.score -> Li_score
```

这样做是因为汇编变量名里不方便使用点号，所以结构体成员被展开成下划线形式。

第三步，遇到 `[i]`，说明是数组访问。

先把下标表达式 `i` 翻译成操作数：

```python
index_value = emit_expr(index_tokens)
```

得到：

```text
index_value = "i"
```

然后生成临时变量：

```python
temp = ir.new_temp()
```

当前是：

```text
T1
```

最后生成数组读取四元式：

```python
ir.emit("=[]", ref, index_value, temp)
```

也就是：

```text
11 (=[], Li_score, i, T1)
```

可读形式：

```text
11 T1 = Li_score[i]
```

这对应语法树中的：

```text
ARRAY_SUBSCRIPT
├── MEMBER_EXPR Li.score
└── IDENTIFIER i
```

---

## 7. if 的 false_list 如何变成四元式 12

原始 if 条件是：

```c
Li.score[i] > max
```

因为第 11 条四元式已经把 `Li.score[i]` 读到了 `T1`：

```text
11 T1 = Li_score[i]
```

所以 if 条件等价于：

```text
T1 > max
```

`parse_condition_tokens()` 返回：

```python
cond = ("T1", ">", "max")
```

然后执行：

```python
false_jumps = emit_false_jumps(cond)
```

位置：

```text
src/compiler.py:1196
```

控制流仍然使用反条件跳转。

`T1 > max` 的反条件是：

```text
T1 <= max
```

所以生成：

```text
12 (j<=, T1, max, 0)
```

也就是：

```text
12 if T1 <= max goto 0
```

刚开始目标仍然是占位 `0`。

记录：

```text
if.false_list = {12}
```

意思是：

```text
第 12 条四元式的目标以后要回填。
```

---

## 8. if 的 thennode 如何变成四元式 13

if 的 then 块是：

```c
{
    max = Li.score[i];
}
```

语法树中对应：

```text
ASSIGN_EXPR
├── IDENTIFIER max
└── ARRAY_SUBSCRIPT Li.score[i]
```

代码里生成 if 假出口后执行：

```python
parse_statement()
```

位置：

```text
src/compiler.py:1198
```

这会进入 then 块并处理赋值语句。

赋值语句分支位置：

```text
src/compiler.py:1285
```

源码：

```c
max = Li.score[i];
```

左边：

```text
max
```

右边：

```text
Li.score[i]
```

这里有一个重要细节：

```text
右边没有再次生成新的数组读取四元式。
```

原因是前面 if 条件里已经生成过：

```text
11 T1 = Li_score[i]
```

`emit_expr()` 里有表达式缓存 `expr_cache`，同一个 `Li.score[i]` 会复用之前的 `T1`。

所以 then 块生成：

```text
13 (=, T1, _, max)
```

可读形式：

```text
13 max = T1
```

---

## 9. if 回填：`bp({12}, 14)`

if 的 then 块生成完以后，代码执行：

```python
patch_jumps(false_jumps, ir.next_quad())
```

位置：

```text
src/compiler.py:1209
```

此时四元式是：

```text
11 T1 = Li_score[i]
12 if T1 <= max goto 0
13 max = T1
```

下一条四元式编号是 14。

所以：

```python
patch_jumps([12], 14)
```

意思是：

```text
把第 12 条四元式的 result 从 0 改成 14。
```

回填前：

```text
12 if T1 <= max goto 0
```

回填后：

```text
12 if T1 <= max goto 14
```

含义：

```text
如果 T1 <= max，说明 if 条件 T1 > max 不成立，
就跳过 then 块 max = T1，
直接执行 14，也就是 i++。
```

这就是：

```text
if.false_list = {12}
bp({12}, 14)
```

---

## 10. `i++` 如何变成四元式 14 和 15

语法树中：

```text
EXPR_STMT
└── UNARY_EXPR
    ├── op: ++
    └── IDENTIFIER i
```

源码：

```c
i++;
```

代码分支位置：

```text
src/compiler.py:1305
```

代码：

```python
if tok_attr(i + 1) in {"++", "--"}:
    parse_inline_assignment([filtered_tokens[i], filtered_tokens[i + 1]])
```

`parse_inline_assignment()` 位置：

```text
src/compiler.py:841
```

它把：

```c
i++;
```

拆成：

```text
T2 = i + 1
i = T2
```

所以生成：

```text
14 (+, i, 1, T2)
15 (=, T2, _, i)
```

---

## 11. while 体结束后为什么有四元式 16

while 循环体翻译完后，代码回到 while 分支，执行：

```python
ir.emit("j", "_", "_", str(cond_start))
```

位置：

```text
src/compiler.py:1231
```

前面记录过：

```text
cond_start = 10
```

所以生成：

```text
16 (j, _, _, 10)
```

可读形式：

```text
16 goto 10
```

含义：

```text
循环体执行完以后，跳回第 10 条四元式，重新判断 while 条件。
```

---

## 12. while 回填：`bp({10}, 17)`

while 条件最开始生成的是：

```text
10 if i >= 5 goto 0
```

记录：

```text
while.false_list = {10}
```

整个 while 循环体翻译完以后，已经生成：

```text
16 goto 10
```

此时下一条四元式是：

```text
17 printf max
```

所以执行：

```python
patch_jumps(false_jumps, ir.next_quad())
```

位置：

```text
src/compiler.py:1233
```

等价于：

```python
patch_jumps([10], 17)
```

也就是：

```text
把第 10 条四元式的 result 从 0 改成 17。
```

回填后：

```text
10 if i >= 5 goto 17
```

含义：

```text
如果 while 条件为假，也就是 i >= 5，
就跳到第 17 条四元式，执行循环后面的 printf。
```

这就是：

```text
while.false_list = {10}
bp({10}, 17)
```

---

## 13. 为什么四元式 17、18 不在 while-if 语法树里

图右侧还有：

```text
17 (printf, _, _, max)
18 (return, 0, _, _)
```

它们对应的是 while 后面的源码：

```c
printf("%d", max);
return 0;
```

它们不是 while 的子节点，所以不在 `WHILE_STMT` 语法树里。

但是 while 的假出口必须跳到 while 后面的第一条语句，所以第 10 条四元式回填到 17。

也就是说：

```text
quad 17 是 while 的出口。
quad 18 是 main 函数返回。
```

---

## 14. 右侧四元式完整串讲

```text
10 (j>=, i, 5, 17)
```

while 条件假出口。源码条件是 `i < 5`，反条件是 `i >= 5`。如果 `i >= 5`，跳到循环出口 17。

```text
11 (=[], Li_score, i, T1)
```

读取数组元素 `Li.score[i]`。结构体成员 `Li.score` 被展开成 `Li_score`，读取结果保存到临时变量 `T1`。

```text
12 (j<=, T1, max, 14)
```

if 条件假出口。源码条件是 `T1 > max`，反条件是 `T1 <= max`。如果成立，跳过 then 块，直接去 14。

```text
13 (=, T1, _, max)
```

then 块。执行 `max = T1`。

```text
14 (+, i, 1, T2)
15 (=, T2, _, i)
```

执行 `i++`。先算 `T2 = i + 1`，再赋值 `i = T2`。

```text
16 (j, _, _, 10)
```

循环回跳。跳回第 10 条四元式，重新判断 while 条件。

```text
17 (printf, _, _, max)
```

while 结束后输出 `max`。

```text
18 (return, 0, _, _)
```

函数返回 0。

---

## 15. 执行路径模拟

初始：

```text
i = 0
max = 0
Li_score = [80, 90, 100, 86, 95]
```

第一次循环：

```text
10: i=0，i>=5 不成立，进入循环
11: T1 = Li_score[0] = 80
12: 80 <= 0 不成立，不跳
13: max = 80
14-15: i = 1
16: goto 10
```

第二次循环：

```text
T1 = 90
90 <= 80 不成立
max = 90
i = 2
```

第三次循环：

```text
T1 = 100
100 <= 90 不成立
max = 100
i = 3
```

第四次循环：

```text
T1 = 86
86 <= 100 成立
跳到 14，不执行 max = T1
i = 4
```

第五次循环：

```text
T1 = 95
95 <= 100 成立
跳到 14
i = 5
```

第六次判断：

```text
10: i >= 5 成立
跳到 17
17: printf max
```

最终输出：

```text
100
```

---

## 16. 一句话总结

图里的语法树说明结构：

```text
while 的条件是 i < 5，循环体里有 if 和 i++；
if 的条件是 Li.score[i] > max，then 是 max = Li.score[i]。
```

右边四元式说明控制流：

```text
10 是 while 假出口，12 是 if 假出口，16 是循环回跳；
11 是数组取值，13 是更新 max，14/15 是 i++；
17 是 while 出口后的 printf。
```

代码实现上：

```text
while 分支先记录 cond_start=10，
生成 while.false_list={10}，
翻译循环体，
生成 goto 10，
最后 bp({10}, 17)。

if 分支先生成 Li.score[i] 的取值 T1，
再生成 if.false_list={12}，
翻译 then 块 max=T1，
最后 bp({12}, 14)。
```

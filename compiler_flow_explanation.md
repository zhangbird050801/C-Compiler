# C Compiler 从 `c-code.c` 到四元式和汇编代码的完整过程

这份文档按当前代码实现讲解编译流程。当前主链路已经改成 AST 驱动：

```text
src/c-code.c
  -> Lexer.tokenize()
  -> LL1Parser.analyze()
  -> ASTBuilder.build()
  -> ASTSemanticAnalyzer.analyze()
  -> ASTIRGenerator.generate()
  -> CodeGenerator.generate()
```

也就是说，语义分析和四元式生成不再直接扫描 token 流。旧的 token 扫描式语义分析器和 `_generate_sample_ir()` 已经删除，当前有效逻辑集中在 `src/compiler.py`、`src/ast_core.py`、`src/ir_generator.py` 和 `src/codegen.py`。

相关文件：

- 输入源码：`src/c-code.c`
- 总控流程：`src/compiler.py`
- 词法分析：`src/lexer_core.py`
- LL(1) 语法分析：`src/parser_core.py`
- AST 构建、AST 语义分析、AST 四元式生成：`src/ast_core.py`
- 四元式数据结构：`src/ir_generator.py`
- 8086 汇编生成：`src/codegen.py`
- GUI 入口：`src/main.py`、`src/lexer_gui.py`

---

## 1. 输入程序做了什么

`src/c-code.c` 的核心逻辑是：

```c
struct student {
    char *name;
    int num;
    int age;
    int score[5];
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

程序语义是遍历 `Li.score[0..4]`，找出最大成绩并输出。数组内容是 `80, 90, 100, 86, 95`，因此最终输出是 `100`。

---

## 2. 总控流程：`Compiler.compile()`

入口在 `src/compiler.py` 的 `Compiler.compile()`。

当前阶段顺序是：

```python
self.result = CompilerResult()
source_code = self._normalize_source(source_code)
self.source_code = source_code

success, tokens = self.lexical_analysis(source_code, verbose)
success, parse_records = self.syntax_analysis(tokens, verbose)
success, ast = self.ast_construction(tokens, verbose)
success, symbol_table = self.semantic_analysis(ast, verbose)
success, ir_gen = self.intermediate_code_generation(symbol_table, ast, tokens, verbose)
self.result.annotated_syntax_tree = self._generate_annotated_syntax_tree()
self.result.backpatch_report = self._generate_backpatch_report()
success, asm_code = self.target_code_generation(ir_gen, symbol_table, verbose)
self.result.success = True
```

各阶段职责：

1. `_normalize_source()`：把中文全角标点转换成 C 代码常用半角标点，例如 `；` 转为 `;`。
2. `lexical_analysis()`：调用 `Lexer.tokenize()`，把字符流变成 token 流。
3. `syntax_analysis()`：调用 `LL1Parser.analyze()`，用预测分析表检查 token 序列是否符合文法。
4. `ast_construction()`：调用 `ASTBuilder.build()`，把 token 流组织成 AST。
5. `semantic_analysis()`：调用 `ASTSemanticAnalyzer.analyze(ast)`，遍历 AST 建符号表。
6. `intermediate_code_generation()`：调用 `ASTIRGenerator.generate(ast)`，遍历 AST 生成四元式。
7. `target_code_generation()`：调用 `CodeGenerator.generate()`，把四元式翻译为 8086 汇编文本。

答辩时可以概括为：

```text
compile() 是流水线调度器；真正的语义和 IR 逻辑由 AST 统一驱动，避免 token 扫描器和语法树逻辑各维护一套规则。
```

---

## 3. 词法分析：源码到 token

入口是 `Compiler.lexical_analysis()`：

```python
self.lexer = Lexer(source_code)
tokens = self.lexer.tokenize()
self.result.tokens = tokens
```

词法分析只负责识别单词，不判断语法结构。例如：

```c
while (i < 5) {
```

会被识别为：

```text
KEYWORD       while
DELIMITER     (
IDENTIFIER    i
OPERATOR      <
CONST_DECIMAL 5
DELIMITER     )
DELIMITER     {
```

再比如：

```c
Li.score[i] > max
```

会被识别为：

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

这一步不关心 `Li.score[i]` 是结构体成员数组访问，也不关心 `i < 5` 是循环条件。它只把源代码切成带类型、属性和行号的 token。

---

## 4. LL(1) 语法分析：检查 token 排列是否合法

入口是 `Compiler.syntax_analysis()`：

```python
self.parser = LL1Parser()
records, success, message = self.parser.analyze(tokens)
self.result.parse_records = records
```

`LL1Parser` 会把真实 token 映射为文法终结符。例如：

- 标识符 token 映射成 `id`
- 整数字面量映射成 `int_lit`
- `while`、`if`、`return` 这类关键字保持关键字形式

预测分析的核心思想是：

```text
看分析栈顶符号 top 和当前输入 lookahead：
  如果 top 是终结符，就要求 top == lookahead。
  如果 top 是非终结符，就查预测分析表 (top, lookahead)，选择产生式展开。
```

和当前样例最相关的结构是：

```text
while ( Expr ) Stmt
if ( Expr ) Stmt ElsePart
{ StmtList }
SimpleStmt ;
```

因此 `while (...) { if (...) { ... } i++; }` 会先被语法分析确认为合法语句嵌套。注意：LL(1) 阶段只判断“结构是否合法”，不生成四元式。

---

## 5. AST 构建：token 到语法树

入口是 `Compiler.ast_construction()`：

```python
self.ast_builder = ASTBuilder(tokens)
self.ast = self.ast_builder.build()
self.result.ast = self.ast
```

`ASTBuilder` 在 `src/ast_core.py` 中。它会过滤预处理 token 和 EOF，然后用递归下降方式构建紧凑 AST。

主要节点类型：

- `PROGRAM`：整棵树根节点。
- `STRUCT_DECL`：结构体定义。
- `FUNC_DEF`：函数定义。
- `COMPOUND_STMT`：`{ ... }` 代码块。
- `VAR_DECL`：变量声明。
- `IF_STMT`：if 语句。
- `WHILE_STMT`：while 语句。
- `RETURN_STMT`：return 语句。
- `EXPR_STMT`：表达式语句。
- `BINARY_EXPR`：二元表达式，例如 `<`、`>`、`+`。
- `UNARY_EXPR`：一元表达式，例如 `i++`。
- `MEMBER_EXPR`：成员访问，例如 `Li.score`。
- `ARRAY_SUBSCRIPT`：数组下标，例如 `Li.score[i]`。
- `FUNC_CALL`：函数调用，例如 `printf("%d", max)`。
- `INIT_LIST`：聚合初始化列表，例如 `{80, 90, 100, 86, 95}`。

当前样例的关键 AST 结构可以抽象为：

```text
PROGRAM
├── STRUCT_DECL "student"
└── FUNC_DEF "main"
    └── COMPOUND_STMT
        ├── VAR_DECL "i" = 0
        ├── VAR_DECL "max" = 0
        ├── VAR_DECL "Li" = INIT_LIST(...)
        ├── WHILE_STMT
        │   ├── BINARY_EXPR "<"
        │   │   ├── IDENTIFIER "i"
        │   │   └── LITERAL "5"
        │   └── COMPOUND_STMT
        │       ├── IF_STMT
        │       │   ├── BINARY_EXPR ">"
        │       │   │   ├── ARRAY_SUBSCRIPT
        │       │   │   │   ├── MEMBER_EXPR "score"
        │       │   │   │   │   └── IDENTIFIER "Li"
        │       │   │   │   └── IDENTIFIER "i"
        │       │   │   └── IDENTIFIER "max"
        │       │   └── COMPOUND_STMT
        │       │       └── ASSIGN_EXPR "="
        │       └── UNARY_EXPR "++"
        ├── FUNC_CALL "printf"
        └── RETURN_STMT
```

AST 的价值是：后续语义分析和 IR 生成不用再靠 token 指针猜测当前语句边界，而是直接按节点类型分发。

---

## 6. 语义分析：AST 到符号表

入口是 `Compiler.semantic_analysis()`：

```python
self.semantic_analyzer = ASTSemanticAnalyzer()
symbol_table = self.semantic_analyzer.analyze(ast)
self.result.symbol_table = symbol_table
```

`ASTSemanticAnalyzer` 在 `src/ast_core.py` 中。它只遍历 AST，不再扫描 token。

主要逻辑：

- `visit_struct_decl()`：把 `struct student` 及其成员放入符号表。
- `visit_var_decl()`：把 `i`、`max`、`Li` 等变量放入符号表。
- `make_type()`：根据 AST 节点属性构造 `Type`，包括基础类型、指针层级、数组维度、结构体类型。

当前样例中，符号表会记录：

```text
student: STRUCT
i: int
max: int
Li: struct student
```

`student` 的成员包括：

```text
name: char*
num: int
age: int
score: int[5]
```

符号表在汇编生成阶段也会使用：`CodeGenerator.generate_data_section()` 会根据符号表和四元式收集变量、数组、临时变量，并输出 `DATA SEGMENT`。

---

## 7. 四元式生成：AST 到 IR

入口是 `Compiler.intermediate_code_generation()`：

```python
self.ir_generator = IRGenerator(symbol_table)
struct_defs = self.ast_builder.struct_defs if self.ast_builder else {}
macros = self._collect_object_macros(tokens)
ASTIRGenerator(self.ir_generator, struct_defs, macros).generate(ast)
self.result.quadruples = self.ir_generator.quadruples
```

`IRGenerator` 负责保存四元式列表，提供：

- `emit(op, arg1, arg2, result)`：追加四元式。
- `new_temp()`：生成 `T1`、`T2` 这类临时变量。
- `next_quad()`：返回下一条四元式编号，用于控制流回填。

`ASTIRGenerator` 负责遍历 AST：

- `gen_stmt()`：根据节点类型分发。
- `gen_var_decl()`：处理变量初始化。
- `emit_struct_initializer()`：把结构体初始化展开成成员赋值。
- `emit_array_initializer()`：把数组初始化展开成多条 `[]=`。
- `gen_if()`：生成 if 条件跳转并回填。
- `gen_while()`：生成 while 条件跳转、循环体和回跳。
- `gen_expr()`：生成表达式四元式。
- `emit_printf()`：根据格式串生成输出四元式。

当前 `src/c-code.c` 生成的 19 条四元式是：

```text
00 (=, 0, _, i)
01 (=, 0, _, max)
02 (=, "Li ping", _, Li_name)
03 (=, 5, _, Li_num)
04 (=, 18, _, Li_age)
05 ([]=, 80, 0, Li_score)
06 ([]=, 90, 1, Li_score)
07 ([]=, 100, 2, Li_score)
08 ([]=, 86, 3, Li_score)
09 ([]=, 95, 4, Li_score)
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

这些四元式可以分成四段：

```text
0..1   初始化普通变量 i 和 max
2..9   展开结构体 Li 的初始化，尤其是 Li_score[0..4]
10..16 while + if + i++ 的控制流和循环体
17..18 printf 和 return
```

结构体成员访问在 IR 中被扁平化：

```text
Li.name  -> Li_name
Li.num   -> Li_num
Li.age   -> Li_age
Li.score -> Li_score
```

数组访问使用专门四元式：

```text
([]=, value, index, array)    表示 array[index] = value
(=[], array, index, temp)     表示 temp = array[index]
```

---

## 8. while/if 的回填思想

当前控制流采用“反条件跳转”：

```text
while (i < 5)
```

不是生成“真则进入循环体”，而是生成：

```text
10 (j>=, i, 5, 17)
```

含义是：

```text
如果 i >= 5，跳到 17，也就是跳出循环。
否则自然落到 11，进入循环体。
```

if 条件：

```c
if (Li.score[i] > max)
```

先读取数组元素：

```text
11 (=[], Li_score, i, T1)
```

再生成反条件跳转：

```text
12 (j<=, T1, max, 14)
```

含义是：

```text
如果 T1 <= max，跳到 14，跳过 max = T1。
否则自然落到 13，执行 max = T1。
```

循环体结束后：

```text
16 (j, _, _, 10)
```

无条件跳回 10，重新判断 `i < 5`。

---

## 9. 汇编生成：四元式到 8086 汇编

入口是 `Compiler.target_code_generation()`：

```python
self.code_generator = CodeGenerator(ir_gen, symbol_table)
asm_code = self.code_generator.generate()
self.result.assembly_code = asm_code
```

`CodeGenerator.generate()` 做三件主要事情：

1. `generate_code_section()`：遍历四元式，生成代码段。
2. `generate_helpers()`：追加输出整数、字符串、字符、定点小数、读整数等辅助过程。
3. `generate_data_section()`：收集字符串字面量、变量、数组和临时变量，生成数据段。

### 9.1 标签扫描

四元式中的跳转目标是数字编号，例如：

```text
10 (j>=, i, 5, 17)
16 (j, _, _, 10)
```

汇编不能直接 `JMP 17`，所以 `scan_labels()` 会把目标四元式编号映射成汇编标签：

```text
17 -> L0
14 -> L1
10 -> L2
```

生成代码时，如果当前四元式编号在 `label_map` 中，就先输出标签：

```asm
L2:
    ; [10] (j>=, i, 5, 17)
    MOV AX, i
    MOV BX, 5
    CMP AX, BX
    JGE L0
```

### 9.2 单条四元式翻译

`translate_quadruple()` 按 `op` 分发：

```text
=      -> gen_assignment()
+ - *  -> gen_arithmetic()
j...   -> gen_jump()
printf -> gen_printf()
return -> MOV AX, value; JMP EXIT
=[]    -> gen_array_load()
[]=    -> gen_array_store()
```

例子：

```text
(=, 0, _, i)
```

生成：

```asm
MOV AX, 0
MOV i, AX
```

例子：

```text
([], 不是实际 op)
([]=, 100, 2, Li_score)
```

生成数组写入，大意是：

```asm
MOV AX, 100
MOV Li_score[4], AX
```

因为 `DW` 元素占 2 字节，下标 2 对应字节偏移 4。

例子：

```text
(=[], Li_score, i, T1)
```

生成数组读取，大意是：

```asm
MOV BX, i
SHL BX, 1
MOV AX, Li_score[BX]
MOV T1, AX
```

例子：

```text
(j<=, T1, max, 14)
```

生成条件跳转：

```asm
MOV AX, T1
MOV BX, max
CMP AX, BX
JLE L1
```

### 9.3 数据段

`generate_data_section()` 会从符号表和四元式里收集需要定义的名字。

当前样例中会出现：

```asm
i DW 0
max DW 0
Li_name DW 0
Li_num DW 0
Li_age DW 0
Li_score DW 5 DUP(0)
T1 DW 0
T2 DW 0
```

字符串 `"Li ping"` 作为初始化值时会进入字符串字面量表，`printf("%d", max)` 的格式串不会直接输出 `%d`，而是由 `ASTIRGenerator.emit_printf()` 识别格式串后只生成：

```text
(printf, _, _, max)
```

所以最终输出的是 `max` 的整数值。

---

## 10. 当前样例的执行路径

四元式层面的执行过程：

```text
0..9   初始化 i=0、max=0、Li_score={80,90,100,86,95}
10     判断 i >= 5 是否成立；成立就跳到 17
11     T1 = Li_score[i]
12     判断 T1 <= max 是否成立；成立就跳到 14
13     max = T1
14     T2 = i + 1
15     i = T2
16     goto 10
17     printf max
18     return 0
```

循环过程：

```text
i=0, T1=80,  max=80
i=1, T1=90,  max=90
i=2, T1=100, max=100
i=3, T1=86,  max=100
i=4, T1=95,  max=100
i=5, 条件 i>=5 成立，跳出循环
```

最终 `printf("%d", max)` 输出：

```text
100
```

---

## 11. 答辩总结

可以按下面这段话总结：

```text
本编译器先用 Lexer 把 c-code.c 切成 token，再用 LL(1) 预测分析器验证语法结构。
语法合法后，ASTBuilder 把 token 组织成 AST；ASTSemanticAnalyzer 遍历 AST 生成符号表；
ASTIRGenerator 再遍历同一棵 AST 生成四元式。while 和 if 使用反条件跳转加回填：
while(i<5) 生成 j>= 跳出循环，if(score>max) 生成 j<= 跳过 then 块。
最后 CodeGenerator 扫描四元式，把数字跳转目标转换成汇编标签，并逐条翻译成 8086 汇编。
```

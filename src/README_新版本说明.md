# C 语言词法分析器 - 项目结构说明

## 📁 项目文件结构

```
src/
├── main.py              # 主程序入口（运行此文件启动程序）
├── lexer_core.py        # 词法分析器核心模块
├── lexer_gui.py         # GUI 界面模块
├── line_number_text.py  # 带行号的文本编辑器组件
└── Lexer.py             # 旧版本（已废弃，可删除）
```

## 🚀 如何运行

在 `src` 目录下运行：

```bash
python main.py
```

## 📝 各模块说明

### 1. `main.py` - 主入口文件
- 简洁的启动器，负责启动 GUI 应用
- 仅包含必要的导入和启动代码

### 2. `lexer_core.py` - 词法分析器核心
包含：
- **常量定义**：关键字、操作符、界符、错误信息等
- **数据结构**：Token 定义
- **SymbolTable 类**：符号表管理
- **Lexer 类**：词法分析器核心逻辑
  - 识别关键字、标识符
  - 识别各类常量（整数、浮点数、字符、字符串）
  - 识别操作符、界符
  - 错误处理和报告

### 3. `lexer_gui.py` - 图形界面
包含：
- **LexerApp 类**：主应用窗口
- GUI 组件创建和布局
- 文件加载功能
- 词法分析结果展示
- 使用带行号的代码编辑器

### 4. `line_number_text.py` - 行号文本组件
包含：
- **LineNumberText 类**：自定义 Tkinter 组件
- 自动更新行号
- 同步滚动
- 提供与标准 Text 组件兼容的接口

## ✨ 新增功能

### 1. 代码输入框显示行号
- 左侧灰色区域显示行号
- 行号自动更新
- 支持滚动同步

### 2. 模块化设计
- 代码分离，职责清晰
- 便于维护和扩展
- 核心逻辑可独立使用（不依赖 GUI）

## 🔧 模块间依赖关系

```
main.py
  └─> lexer_gui.py
        ├─> line_number_text.py
        └─> lexer_core.py
```

## 💡 使用示例

### GUI 模式（推荐）
```python
# 运行 main.py
python main.py
```

### 命令行模式（仅核心功能）
```python
from lexer_core import Lexer

code = """
int main() {
    printf("Hello, World!");
    return 0;
}
"""

lexer = Lexer(code)
tokens = lexer.tokenize()

for token in tokens:
    print(token)

print(lexer.table)  # 打印符号表
```

## 📌 注意事项

1. **旧文件处理**：`Lexer.py` 是旧版本的单文件实现，现在已被拆分为多个模块。如果确认新版本运行正常，可以删除 `Lexer.py`。

2. **运行路径**：建议在 `src` 目录下运行 `main.py`，以确保模块导入正常。

3. **Python 版本**：需要 Python 3.6 及以上版本（使用了 f-string 等特性）。

## 🎯 优势

- **可维护性**：代码模块化，修改某一部分不影响其他模块
- **可扩展性**：可以轻松添加新的 GUI 功能或词法分析规则
- **可复用性**：核心词法分析器可以在其他项目中复用
- **可读性**：每个文件职责单一，代码更清晰

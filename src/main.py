"""
C 语言词法分析器 - 主程序入口
启动 GUI 应用
"""
from lexer_gui import LexerApp


if __name__ == '__main__':
    app = LexerApp()
    app.mainloop()

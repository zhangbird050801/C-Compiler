"""
带行号显示的文本编辑器组件
(修复了滚动同步 Bug)
"""
import tkinter as tk
from tkinter import scrolledtext


class LineNumberText(tk.Frame):
    """带行号的文本编辑器组件"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent)

        # 创建行号显示区域
        self.line_numbers = tk.Text(
            self,
            width=4,
            padx=4,
            takefocus=0,
            border=0,
            background='lightgray',
            foreground='black',
            state='disabled',
            wrap='none'
        )
        self.line_numbers.pack(side='left', fill='y')

        # 创建主文本编辑区
        self.text_widget = scrolledtext.ScrolledText(self, **kwargs)
        self.text_widget.pack(side='right', fill='both', expand=True)

        # 绑定事件以更新行号
        # --- 修复 1: 移除了 <MouseWheel> 和 <ButtonRelease> 的错误绑定 ---
        self.text_widget.bind('<KeyRelease>', self._on_change)
        # 增加对粘贴和剪切的支持
        self.text_widget.bind('<<Paste>>', self._on_change)
        self.text_widget.bind('<<Cut>>', self._on_change)

        # 同步滚动
        self.text_widget.config(yscrollcommand=self._on_text_scroll)

        # 初始化行号
        self._update_line_numbers()

    def _on_change(self, event=None):
        """当文本改变时更新行号"""
        # --- 修复 2: 延迟更新 ---
        # 增加 1ms 延迟，确保在更新行号前，文本框的索引(index)已经更新
        self.after(1, self._update_line_numbers)

    def _on_text_scroll(self, *args):
        """同步滚动行号和文本 (此函数原逻辑正确)"""
        # 当 text_widget 滚动时，强制 line_numbers 滚动到相同位置
        self.line_numbers.yview_moveto(args[0])
        # 并且更新 text_widget 自己的滚动条 (vbar)
        self.text_widget.vbar.set(*args)

    def _update_line_numbers(self):
        """更新行号显示"""

        # --- 修复 3: 保存和恢复滚动位置 ---

        # 1. 在重建列表前，保存主文本框的当前滚动位置
        current_scroll_pos = self.text_widget.yview()

        self.line_numbers.config(state='normal')
        self.line_numbers.delete('1.0', 'end')

        # 获取文本总行数
        # 'end-1c' (end minus 1 char) 用于正确处理末尾的换行符
        line_count_str = self.text_widget.index('end-1c').split('.')[0]

        # 处理空文本框的特殊情况 (应显示 "1")
        if not line_count_str or line_count_str == "0":
            line_count = 1
        else:
            line_count = int(line_count_str)

        # 检查文本框是否真的为空
        if line_count == 1 and not self.text_widget.get("1.0", "end-1c"):
             line_numbers_string = "1"
        else:
             line_numbers_string = "\n".join(str(i) for i in range(1, line_count + 1))

        self.line_numbers.insert('1.0', line_numbers_string)
        self.line_numbers.config(state='disabled')

        # 2. 重建列表后，强制行号框滚动回保存的位置
        self.line_numbers.yview_moveto(current_scroll_pos[0])

    # 代理方法，使外部调用更方便
    def get(self, *args, **kwargs):
        """获取文本内容"""
        return self.text_widget.get(*args, **kwargs)

    def insert(self, *args, **kwargs):
        """插入文本"""
        result = self.text_widget.insert(*args, **kwargs)
        # 同样需要延迟更新
        self.after(1, self._update_line_numbers)
        return result

    def delete(self, *args, **kwargs):
        """删除文本"""
        result = self.text_widget.delete(*args, **kwargs)
        # 同样需要延迟更新
        self.after(1, self._update_line_numbers)
        return result
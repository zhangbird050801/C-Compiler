"""
带行号显示的文本编辑器组件
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
        self.text_widget.bind('<KeyRelease>', self._on_change)
        self.text_widget.bind('<MouseWheel>', self._on_change)
        self.text_widget.bind('<ButtonRelease>', self._on_change)
        
        # 同步滚动
        self.text_widget.config(yscrollcommand=self._on_text_scroll)
        
        # 初始化行号
        self._update_line_numbers()
    
    def _on_change(self, event=None):
        """当文本改变时更新行号"""
        self._update_line_numbers()
    
    def _on_text_scroll(self, *args):
        """同步滚动行号和文本"""
        self.line_numbers.yview_moveto(args[0])
        self.text_widget.vbar.set(*args)
    
    def _update_line_numbers(self):
        """更新行号显示"""
        self.line_numbers.config(state='normal')
        self.line_numbers.delete('1.0', 'end')
        
        # 获取文本总行数
        line_count = int(self.text_widget.index('end-1c').split('.')[0])
        
        # 生成行号
        line_numbers_string = "\n".join(str(i) for i in range(1, line_count + 1))
        self.line_numbers.insert('1.0', line_numbers_string)
        self.line_numbers.config(state='disabled')
    
    # 代理方法，使外部调用更方便
    def get(self, *args, **kwargs):
        """获取文本内容"""
        return self.text_widget.get(*args, **kwargs)
    
    def insert(self, *args, **kwargs):
        """插入文本"""
        result = self.text_widget.insert(*args, **kwargs)
        self._update_line_numbers()
        return result
    
    def delete(self, *args, **kwargs):
        """删除文本"""
        result = self.text_widget.delete(*args, **kwargs)
        self._update_line_numbers()
        return result

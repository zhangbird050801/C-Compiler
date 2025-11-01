// 测试词法分析器的示例 C 代码
#include <stdio.h>

int main() {
    // 变量声明
    int x = 10;
    float y = 3.14;
    char c = 'A';
    
    /* 多行注释
       测试注释功能 */
    
    // 字符串测试
    printf("Hello, World!\n");
    
    // 算术运算
    int result = x + 5;
    
    // 条件语句
    if (x > 0) {
        printf("Positive\n");
    } else {
        printf("Non-positive\n");
    }
    
    return 0;
}

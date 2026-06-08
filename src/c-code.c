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

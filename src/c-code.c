#include <stdio.h>

typedef struct student {
    char *name;    // 姓名
    int num;       // 学号
    int age;       // 年龄
    float score;   // 成绩
} student;

int main(void) {
    int i, num_140 = 0;
    float sum = 0.0f;
    int flag = 0;

    student sts[2] = {
        {"Li ping",   5, 18, 145.0f},
        {"Wang ming", 6, 18, 150.0f}
    };

    if (sts[1].score < 140.0f) flag = -1;
    else flag = 1;

    printf("%d ", flag);
    return 0;
}

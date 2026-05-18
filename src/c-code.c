#include <stdio.h>

struct student {
    char *name;      // 姓名
    int num;         // 学号
    int age;         // 年龄
    float score;     // 成绩
};

int main() {
    int i, num_140 = 0;
    float sum = 0;
    int flag;

    struct student sts[2] = {
        {"Li ping", 5, 18, 145.0},
        {"Wang ming", 6, 18, 150.0}
    };

    if (sts[1].score < 140) {
        flag = -1;
    } else {
        flag = 1;
    }

    printf("%d ", flag);

    return 0;
}
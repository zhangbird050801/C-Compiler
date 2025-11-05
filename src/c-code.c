#include<stdio.h>
#define N 5

int a = 6;

int aaa(int a, int b) {
    return a + b;
}

int main() {
    int a = 0, b = 2;
    printf("Hello, world!\n");
    // 这是一行注释

    /*
        这是很多行注释
        abcsd
        qw
    */

    // float a, b;
    double c = 123.0007;
    int f = 0xF5;
    int q = 077;
    int test2 = 0xfz;
    int test1 = 099;
    //int 1ab;
    float x = 1e4;
    float y = 1.2e-5;
    double a_123;
    // float 13.1;
    //int ff = 0xQQ;
    //int xx = 099;

    char ff = '\n';

    printf("Birdy：\"Hello！\"");
    printf("HEllo\n");
    printf("qweqwe";
    char *s = "Hello World\f";
    char c = 'abc';
    int i = 0;
    /* 这是一个未闭合的注释
int main() {
// 错误: 未闭合的块注释 at line X

    do {
        i ++;
    } while(i < 10);

    return 0;
}
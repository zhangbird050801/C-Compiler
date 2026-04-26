#include <stdio.h>
#include <string.h>

int main() {
   int a = 0, b = 3;
   scanf("%d", &a);

   if (a > b) {
      printf("gt %d\n", a);
   } else {
      printf("le %d\n", b);
   }

   while (a < 5) {
      a = a + 1;
   }

   for (b = 0; b < 3; b++) {
      printf("%d ", b);
   }

   char c = 'A';
   printf("\n%c %s\n", c, "ok");

   double x = 3.14;
   printf("%.6f\n", a + x);

   return 0;
}
// typedef struct Books
// {
//    char  title[50];
//    char  author[50];
//    char  version[50];
//    int   book_id;
//    float   price_and_discount[2];
// } Book;

// int main( )
// {
//    Book book = {"Compilers: Principles, Techniques, and Tools", "Alfred V. Aho et al.", " 2nd", 13, {100, 0.8}};

//    float discount_price = book.price_and_discount[0] * book.price_and_discount[1];

//    printf("Price of book %s is: %.2f\n", strcat(book.title, book.version), discount_price);
// }
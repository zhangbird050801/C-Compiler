#include <stdio.h>
#include <string.h>

typedef struct Books
{
   char  title[50];
   char  author[50];
   char  version[50];
   int   book_id;
   float   price_and_discount[2];
} Book;

int main( )
{
   Book book = {"Compilers: Principles, Techniques, and Tools", "Alfred V. Aho et al.", " 2nd", 13, {100, 0.8}};

   float discount_price = book.price_and_discount[0] * book.price_and_discount[1];

   printf("Price of book %s is: %.2f\n", strcat(book.title, book.version), discount_price);
}
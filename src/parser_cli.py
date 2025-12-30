import sys
import os
from lexer_core import Lexer, TYPES
from parser_core import LL1Parser


def show_sets(p):
    disp = p.display
    s = p.calc_sets()
    print("FIRST:")
    for k in sorted(s['first']):
        print(" ", disp(k), "->", [disp(x) for x in sorted(s['first'][k])])
    print("\nFOLLOW:")
    for k in sorted(s['follow']):
        print(" ", disp(k), "->", [disp(x) for x in sorted(s['follow'][k])])
    print("\nSELECT:")
    for (h, prod), v in s['select'].items():
        r = " ".join(disp(x) for x in prod) if prod else "epsilon"
        print(" ", disp(h), "->", r, ":", [disp(x) for x in sorted(v)])


def show_tokens(tokens):
    print("\nTOKENS:")
    for i, t in enumerate(tokens, 1):
        tn = TYPES.get(t.type, 'UNK')
        mark = " ERR" if t.error else ""
        print(f"{i:4d} {tn:<15} {t.attribute:<20} L{t.line}{mark}")


def show_records(records):
    print("\nPARSE STEPS:")
    for step, stack, inp, prod, act in records:
        print(f"{step:4d} | {stack:<40} | {inp:<30} | {prod:<20} | {act}")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'src/c-code.c'
    if not os.path.exists(path):
        print("file not found:", path)
        return

    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    show_tokens(tokens)

    parser = LL1Parser()
    if parser.conflicts:
        print("\nLL(1) 冲突:")
        for A, a, old, new in parser.conflicts:
            print(f"  M[{parser.display(A)}, {a}] : {parser.display(A)} -> {' '.join(old)}  AND  {parser.display(A)} -> {' '.join(new)}")
        return

    records, ok, msg = parser.analyze(tokens)
    show_records(records)
    print("\nRESULT:", msg)

    print("\nSETS:")
    show_sets(parser)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Replace one section of a book3 chapter with translated prose.

Usage:
    python tr/splice.py book3/01-intro.mkd "English heading" "Next English heading" prose.txt

Use "--eof" as the next heading for the last section of a file.

prose.txt holds the translated section. Each line that is exactly @@CODE@@
is replaced, in order, by the next fenced code block (~~~~ ... ~~~~) copied
verbatim from the current English section, so code is never retyped.
Line endings of the chapter file are preserved.
"""

import sys


def main():
    path, head, next_head, prose_path = sys.argv[1:5]
    raw = open(path, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)
    start = lines.index(head)
    # "--eof" replaces through the end of the file (keeping a final newline).
    end = len(lines) - (lines[-1] == "") if next_head == "--eof" else lines.index(next_head)
    orig = lines[start:end]

    codes = []
    i = 0
    while i < len(orig):
        if orig[i].startswith("~~~"):
            j = i + 1
            while not orig[j].startswith("~~~"):
                j += 1
            codes.append(orig[i:j + 1])
            i = j + 1
        else:
            i += 1

    prose = open(prose_path, encoding="utf-8").read().rstrip("\n").split("\n")
    slots = prose.count("@@CODE@@")
    if slots != len(codes):
        sys.exit(f"@@CODE@@ slots ({slots}) != code blocks in section ({len(codes)})")

    new = []
    k = 0
    for line in prose:
        if line == "@@CODE@@":
            new += codes[k]
            k += 1
        else:
            new.append(line)
    lines[start:end] = new + [""]
    open(path, "w", encoding="utf-8", newline="").write(eol.join(lines))
    print(f"spliced {len(new)} lines, {len(codes)} code blocks")


if __name__ == "__main__":
    main()

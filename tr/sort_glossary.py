#!/usr/bin/env python3
"""Sort the entries of a chapter's "Sözlükçe" section in Turkish alphabetical order.

Usage:
    python tr/sort_glossary.py book3/01-intro.mkd

An entry is a blank-line-separated block (term line, ":   definition"
lines and its \\index lines). The heading and everything outside the
section are left untouched; line endings are preserved.
"""

import sys

TR_ALPHABET = "abcçdefgğhıijklmnoöprsştuüvyz"
ORDER = {ch: i for i, ch in enumerate(TR_ALPHABET)}


def tr_lower(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_key(s):
    # Space first (dictionary order: "anlam hatası" < "anlambilim"),
    # then letters by Turkish order, anything else after z.
    return [-1 if ch == " " else ORDER.get(ch, 100 + ord(ch)) for ch in tr_lower(s)]


def main():
    path = sys.argv[1]
    raw = open(path, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)

    start = lines.index("Sözlükçe") + 2          # skip heading + underline
    end = lines.index("Alıştırmalar")

    blocks, cur = [], []
    for line in lines[start:end]:
        if line.strip():
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)

    blocks.sort(key=lambda b: tr_key(b[0]))
    body = [""]
    for b in blocks:
        body += b + [""]
    lines[start:end] = body
    open(path, "w", encoding="utf-8", newline="").write(eol.join(lines))
    for b in blocks:
        print(b[0])


if __name__ == "__main__":
    main()

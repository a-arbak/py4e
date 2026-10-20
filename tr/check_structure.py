#!/usr/bin/env python3
"""Structural diff of a translated book3 chapter against upstream English.

Usage:
    python tr/check_structure.py book3/02-variables.mkd [--done] [--ref upstream/master]

Text between <!-- TR-EK-BASLA --> and <!-- TR-EK-BITIS --> is a translator's
addition without an English counterpart and is ignored.

Fails (exit 1) if code fences, code block contents, \\VerbatimInput lines,
image targets, title block, heading count/levels, \\index count or paragraph
count differ from the English original. Leftover TR-SORU comments are a
warning, or a failure with --done.
"""

import argparse
import os
import re
import subprocess
import sys

FENCE_RE = re.compile(r"^(~~~|```)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]*)\)")
INDEX_RE = re.compile(r"\\index\{")
VERBATIM_RE = re.compile(r"\\VerbatimInput\{[^}]*\}")
SETEXT_RE = re.compile(r"^(=+|-+)\s*$")
ATX_RE = re.compile(r"^(#{1,6})\s")
TRSORU_RE = re.compile(r"<!--\s*TR-SORU")
EK_START_RE = re.compile(r"<!--\s*TR-EK-BASLA")
EK_END_RE = re.compile(r"<!--\s*TR-EK-BITIS")
COMMENT_ONLY_RE = re.compile(r"^\s*<!--.*-->\s*$")
LIST_RE = re.compile(r"^ {0,3}([-*+]|\d+[.)])\s")


def parse(text):
    """Split text into blocks and collect structural facts."""
    lines = text.replace("\r\n", "\n").split("\n")
    info = {
        "title": [],
        "fences": [],        # (lineno, fence line)
        "code": [],          # (lineno, contents)
        "verbatim": [],      # (lineno, text)
        "images": [],        # (lineno, target)
        "headings": [],      # (lineno, level)
        "blocks": [],        # (lineno, kind, index_count)
        "trsoru": [],        # lineno
        "underline": [],     # lineno of setext underlines not matching title length
    }

    i = 0
    n = len(lines)
    while i < n and lines[i].startswith("%"):
        info["title"].append(lines[i].rstrip())
        i += 1

    cur = []          # (lineno, line) of current prose block

    def flush():
        # Drop lines that are only HTML comments (e.g. TR-SORU notes).
        real = [(ln, l) for ln, l in cur if not COMMENT_ONLY_RE.match(l)]
        if real:
            body = "\n".join(l for _, l in real)
            first = real[0][1]
            if any(SETEXT_RE.match(l) for _, l in real[1:2]) or ATX_RE.match(first):
                kind = "heading"
            elif first.startswith("!["):
                kind = "image"
            elif any(l.startswith(":   ") for _, l in real):
                kind = "deflist"
            elif VERBATIM_RE.search(body):
                kind = "verbatim"
            elif LIST_RE.match(first):
                kind = "list"
            elif all(l.startswith(("    ", "\t")) for _, l in real):
                prev = info["blocks"][-1][1] if info["blocks"] else None
                if prev in ("list", "listcont", "deflist"):
                    kind = "listcont"
                else:
                    # Indented code block: contents must stay identical.
                    kind = "code"
                    info["code"].append((real[0][0], body.rstrip()))
            else:
                kind = "para"
            info["blocks"].append((real[0][0], kind, len(INDEX_RE.findall(body))))
        cur.clear()

    while i < n:
        line = lines[i]
        ln = i + 1
        if EK_START_RE.search(line):
            # Translator's addition (e.g. "Türkçe Baskıya Önsöz"): no English
            # counterpart, so it is skipped -- but TR-SORU notes still count.
            flush()
            while i < n and not EK_END_RE.search(lines[i]):
                if TRSORU_RE.search(lines[i]):
                    info["trsoru"].append(i + 1)
                i += 1
            i += 1
            continue
        if TRSORU_RE.search(line):
            info["trsoru"].append(ln)
        m = FENCE_RE.match(line)
        if m:
            flush()
            info["fences"].append((ln, line.rstrip()))
            marker = m.group(1)
            body = []
            i += 1
            while i < n and not lines[i].startswith(marker):
                body.append(lines[i].rstrip())
                i += 1
            if i < n:
                info["fences"].append((i + 1, lines[i].rstrip()))
            info["code"].append((ln, "\n".join(body)))
            info["blocks"].append((ln, "code", 0))
            i += 1
            continue
        if line.strip() == "":
            flush()
        else:
            if cur and SETEXT_RE.match(line) and len(cur) == 1:
                info["headings"].append((cur[0][0], 1 if line.lstrip().startswith("=") else 2))
                if len(line.rstrip()) != len(cur[0][1].rstrip()):
                    info["underline"].append(ln)
            else:
                am = ATX_RE.match(line)
                if am and not cur:
                    info["headings"].append((ln, len(am.group(1))))
            for vm in VERBATIM_RE.finditer(line):
                info["verbatim"].append((ln, vm.group(0)))
            for im in IMAGE_RE.finditer(line):
                info["images"].append((ln, im.group(1)))
            cur.append((ln, line))
        i += 1
    flush()
    return info


def upstream_text(path, ref):
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, check=True).stdout.strip()
    rel = os.path.relpath(os.path.abspath(path), root).replace("\\", "/")
    out = subprocess.run(["git", "-C", root, "show", f"{ref}:{rel}"],
                         capture_output=True, check=True).stdout
    return out.decode("utf-8")


def compare_seq(name, en, tr, errors, show=lambda x: repr(x)):
    """Compare two lists of (lineno, value); report first differences."""
    if len(en) != len(tr):
        errors.append(f"{name}: count differs (EN {len(en)}, TR {len(tr)})")
    shown = 0
    for (eln, ev), (tln, tv) in zip(en, tr):
        if ev != tv:
            errors.append(f"{name}: EN line {eln} vs TR line {tln}: {show(ev)} != {show(tv)}")
            shown += 1
            if shown >= 5:
                errors.append(f"{name}: ... further differences suppressed")
                break
    if len(en) != len(tr) and shown == 0:
        k = min(len(en), len(tr))
        extra = en[k:] if len(en) > len(tr) else tr[k:]
        side = "EN" if len(en) > len(tr) else "TR"
        errors.append(f"{name}: first unmatched item in {side} at line {extra[0][0]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--ref", default="upstream/master")
    ap.add_argument("--done", action="store_true",
                    help="treat leftover TR-SORU comments as failures")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    with open(args.file, encoding="utf-8") as f:
        tr = parse(f.read())
    en = parse(upstream_text(args.file, args.ref))

    errors = []
    # The Turkish title page is owner-approved (tr/PROGRESS.md), so only the
    # number of title-block lines has to match.
    if len(en["title"]) != len(tr["title"]):
        errors.append(f"title block line count differs: EN {len(en['title'])} vs TR {len(tr['title'])}")
    compare_seq("code fence lines", en["fences"], tr["fences"], errors)
    compare_seq("code block contents", en["code"], tr["code"], errors,
                show=lambda s: repr(s[:60] + ("..." if len(s) > 60 else "")))
    compare_seq("\\VerbatimInput", en["verbatim"], tr["verbatim"], errors)
    compare_seq("image targets", en["images"], tr["images"], errors)
    compare_seq("heading levels", en["headings"], tr["headings"], errors)

    en_idx = sum(c for _, _, c in en["blocks"])
    tr_idx = sum(c for _, _, c in tr["blocks"])
    if en_idx != tr_idx:
        errors.append(f"\\index count differs (EN {en_idx}, TR {tr_idx})")

    # Paragraphs: compare block kinds 1:1 to locate where alignment breaks.
    eb, tb = en["blocks"], tr["blocks"]
    if len(eb) != len(tb):
        errors.append(f"paragraph/block count differs (EN {len(eb)}, TR {len(tb)})")
    for (eln, ek, ei), (tln, tk, ti) in zip(eb, tb):
        if ek != tk:
            errors.append(f"block alignment breaks: EN line {eln} ({ek}) vs TR line {tln} ({tk})")
            break
        if ei != ti and ek != "deflist":
            errors.append(f"\\index count differs in block: EN line {eln} ({ei}) vs TR line {tln} ({ti})")

    # Glossary entries are re-sorted into Turkish alphabetical order, so within
    # each run of definition-list blocks only the multiset of \index counts
    # has to match.
    def deflist_runs(blocks):
        runs, cur = [], []
        for _, kind, idx in blocks:
            if kind == "deflist":
                cur.append(idx)
            elif cur:
                runs.append(sorted(cur))
                cur = []
        if cur:
            runs.append(sorted(cur))
        return runs

    if deflist_runs(eb) != deflist_runs(tb):
        errors.append("\\index counts differ inside a definition list (glossary)")

    warnings = [f"TR-SORU left at line {ln}" for ln in tr["trsoru"]]
    en_bad = len(en["underline"])
    if len(tr["underline"]) > en_bad:
        errors.extend(f"heading underline length does not match title at line {ln}"
                      for ln in tr["underline"])

    for e in errors:
        print("ERROR:", e)
    for w in warnings:
        print("ERROR:" if args.done else "WARN: ", w)

    if errors or (args.done and warnings):
        print(f"FAIL: {args.file}")
        return 1
    print(f"OK: {args.file} ({len(tb)} blocks, {len(tr['code'])} code blocks, "
          f"{tr_idx} index entries, {len(warnings)} TR-SORU)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

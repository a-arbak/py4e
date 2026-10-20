#!/usr/bin/env python3
"""Translate the text in book figures (images/*.svg) and export EPS.

Usage:
    python tr/figures.py arch [pda ...] [--out DIR]

Translations live in tr/figures.json: for each figure, one entry per
<text> block in document order, with the English lines ("en", lines
separated by " / ") and the Turkish lines ("tr"), plus an optional font
"size" for text that would not fit its box. The English is checked
against the SVG so a stale entry fails loudly instead of mislabeling.

Each block is rewritten as centered lines at the same box center and
line spacing. The SVG keeps real text (for HTML/EPUB); the EPS is
exported by Inkscape with text converted to paths, so the PDF build does
not depend on fonts installed on the build server. A 100 dpi PNG (used by
the EPUB/HTML builds) is written too.

By default output goes to tr/preview/figs/ for review. Use --out images
to overwrite the book's figures once approved.
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INKSCAPE = os.environ.get("INKSCAPE", r"C:\Program Files\Inkscape\bin\inkscape.exe")
TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
TSPAN_RE = re.compile(r"<tspan\b([^>]*)>([^<]*)</tspan>")
ATTR_RE = re.compile(r'([\w:-]+)="([^"]*)"')
CANVAS_RE = re.compile(r'<rect fill="white" width="\d+(?:\.\d+)?" height="\d+(?:\.\d+)?"/>')
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"


def parse_lines(body):
    """Group tspans by y into lines: [(y, x_left, x_right, text, attrs)]."""
    lines = {}
    for attrs, text in TSPAN_RE.findall(body):
        a = dict(ATTR_RE.findall(attrs))
        x, y = float(a["x"]), float(a["y"])
        width = float(a.get("textLength", 0))
        if y in lines:
            _, left, right, t, first = lines[y]
            lines[y] = (y, min(left, x), max(right, x + width), t + text, first)
        else:
            lines[y] = (y, x, x + width, text, a)
    return [lines[y] for y in sorted(lines)]


def translate_svg(svg, entries, name):
    blocks = list(TEXT_RE.finditer(svg))
    if len(blocks) != len(entries):
        sys.exit(f"{name}: {len(blocks)} text blocks in SVG, {len(entries)} in figures.json")
    out, pos = [], 0
    for m, entry in zip(blocks, entries):
        lines = parse_lines(m.group(2))
        english = " / ".join(html.unescape(t).strip() for _, _, _, t, _ in lines)
        if english != entry["en"]:
            sys.exit(f"{name}: expected {entry['en']!r}, SVG has {english!r}")
        first = lines[0][4]
        center = sum((l + r) / 2 for _, l, r, _, _ in lines) / len(lines)
        ys = [y for y, *_ in lines]
        step = (ys[-1] - ys[0]) / (len(ys) - 1) if len(ys) > 1 else 18
        # Optional "size" shrinks the font (and line spacing) when the
        # Turkish is too wide for its box.
        orig_size = float(first.get("font-size", "16"))
        size = float(entry.get("size", orig_size))
        step *= size / orig_size
        # Keep the block vertically centered where the English was; a
        # smaller font sits lower on its baseline, so nudge it down.
        mid = (ys[0] + ys[-1]) / 2 - (orig_size - size) * 0.35
        tr_lines = entry["tr"]
        y0 = mid - step * (len(tr_lines) - 1) / 2
        spans = "".join(
            f'<tspan font-family="{FONT}" font-size="{size:g}" '
            f'font-weight="{first.get("font-weight", "500")}" x="{center:.3f}" '
            f'y="{y0 + i * step:.3f}" text-anchor="middle">{html.escape(t)}</tspan>'
            for i, t in enumerate(tr_lines))
        out.append(svg[pos:m.start()])
        out.append(f"<text{m.group(1)}>{spans}</text>")
        pos = m.end()
    out.append(svg[pos:])
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("figures", nargs="+")
    ap.add_argument("--out", default=os.path.join(ROOT, "tr", "preview", "figs"))
    ap.add_argument("--ref", default="upstream/master", help="git ref of the English figures")
    args = ap.parse_args()

    with open(os.path.join(ROOT, "tr", "figures.json"), encoding="utf-8") as f:
        table = json.load(f)
    os.makedirs(args.out, exist_ok=True)

    for name in args.figures:
        if name not in table:
            sys.exit(f"{name}: no entry in tr/figures.json")
        # Always start from the English original, so reruns are idempotent
        # even after images/ has been overwritten with the translation.
        english = subprocess.run(["git", "-C", ROOT, "show", f"{args.ref}:images/{name}.svg"],
                                 capture_output=True, check=True).stdout.decode("utf-8")
        svg = translate_svg(english, table[name], name)
        svg_out = os.path.join(args.out, name + ".svg")
        with open(svg_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        # OmniGraffle puts a large invisible white canvas rect behind every
        # figure. Drop it for export and crop to the drawing, matching the
        # originals ("Export Area: All Objects, margin 0", figures/README.md).
        fd, export_svg = tempfile.mkstemp(suffix=".svg")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(CANVAS_RE.sub("", svg, count=1))
        try:
            eps_out = os.path.join(args.out, name + ".eps")
            subprocess.run([INKSCAPE, export_svg, "--export-type=eps", "--export-text-to-path",
                            "--export-area-drawing", f"--export-filename={eps_out}"],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # PNG at 100 dpi matches the originals used by pre-html.py (EPUB/HTML).
            subprocess.run([INKSCAPE, export_svg, "--export-type=png", "--export-dpi=100",
                            "--export-area-drawing", "--export-background=white",
                            f"--export-filename={os.path.join(args.out, name + '.png')}"],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            os.remove(export_svg)
        print(f"{name}: {svg_out} (+ .eps + .png)")


if __name__ == "__main__":
    main()

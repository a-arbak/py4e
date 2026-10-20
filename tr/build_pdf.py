#!/usr/bin/env python3
"""Build the full Turkish book locally (PDF, EPUB, DOCX) with book3/book.sh.

Usage:
    python tr/build_pdf.py

Requires book3/.turkish, bash (Git Bash on Windows), pandoc, xelatex and
makeindex. Handles the Windows-specific pitfalls of running book.sh:

- the checkout has CRLF line endings, so a LF copy of book.sh is run;
- PYTHONUTF8=1 so verbatim.py/texpatch.py read and write UTF-8;
- stdin is closed, so a TeX error stops the build instead of waiting for
  input (or reading the rest of the script as TeX answers).

Outputs are copied to tr/preview/ (ignored by git); the log is
tr/preview/build.log.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "book3")
PREVIEW = os.path.join(ROOT, "tr", "preview")


def main():
    if not os.path.exists(os.path.join(BOOK, ".turkish")):
        sys.exit("book3/.turkish is missing; refusing to run the English build")
    os.makedirs(PREVIEW, exist_ok=True)

    with open(os.path.join(BOOK, "book.sh"), encoding="utf-8", newline="") as f:
        script = f.read().replace("\r\n", "\n")
    fd, lf_script = tempfile.mkstemp(suffix=".sh")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)

    env = dict(os.environ, PYTHONUTF8="1")
    log_path = os.path.join(PREVIEW, "build.log")
    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as log:
            subprocess.run(["bash", lf_script], cwd=BOOK, env=env,
                           stdin=subprocess.DEVNULL, stdout=log,
                           stderr=subprocess.STDOUT)
    finally:
        os.remove(lf_script)

    with open(log_path, encoding="utf-8", errors="replace") as f:
        log_text = f.read()
    errors = [l for l in log_text.splitlines()
              if l.startswith("! ") or "cannot move" in l]
    pages = re.findall(r"Output written on tmp\.pdf \((\d+) pages?\)", log_text)

    for name in ("x.pdf", "x.epub", "x.docx"):
        src = os.path.join(BOOK, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(PREVIEW, name))

    for e in errors[:10]:
        print("ERROR:", e)
    if errors or not pages:
        print(f"FAIL: see {log_path}")
        return 1
    print(f"OK: {pages[-1]} pages -> tr/preview/x.pdf (also x.epub, x.docx)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

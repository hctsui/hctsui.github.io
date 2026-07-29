#!/usr/bin/env python3
"""Point both website CV buttons to the generated PDF without changing layout."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX_FILE = ROOT / "cv" / "Hung-Chun-Tsui-CV.tex"
PDF_PATH = "files/Hung-Chun-Tsui-CV.pdf"
PAGES = [ROOT / "cv.html", ROOT / "zh" / "cv.html"]


def main() -> None:
    if not TEX_FILE.exists():
        raise SystemExit("Run tools/build_cv.py before update_cv_links.py")
    version = hashlib.sha256(TEX_FILE.read_bytes()).hexdigest()[:12]
    url = f"https://hctsui.github.io/{PDF_PATH}?v={version}"
    pattern = re.compile(
        r'(<a\b[^>]*\bclass="[^"]*\bcv-download\b[^"]*"[^>]*\bhref=")[^"]*(")',
        re.I,
    )
    for page in PAGES:
        text = page.read_text(encoding="utf-8")
        updated, count = pattern.subn(rf"\g<1>{url}\g<2>", text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not find CV download button in {page.relative_to(ROOT)}")
        page.write_text(updated, encoding="utf-8")
        print(f"Updated {page.relative_to(ROOT)} -> {url}")


if __name__ == "__main__":
    main()

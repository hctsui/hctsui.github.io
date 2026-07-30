#!/usr/bin/env python3
"""Point English and Chinese website buttons to their matching generated CV."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    (ROOT / "cv.html", ROOT / "cv" / "Hung-Chun-Tsui-CV.tex", "files/Hung-Chun-Tsui-CV.pdf"),
    (ROOT / "zh" / "cv.html", ROOT / "cv" / "Hung-Chun-Tsui-CV-zh.tex", "files/Hung-Chun-Tsui-CV-zh.pdf"),
]
PATTERN = re.compile(r'(<a\b[^>]*\bclass="[^"]*\bcv-download\b[^"]*"[^>]*\bhref=")[^"]*(")', re.I)


def main() -> None:
    for page, tex_file, pdf_path in TARGETS:
        if not tex_file.exists():
            raise SystemExit(f"Missing generated LaTeX source: {tex_file.relative_to(ROOT)}")
        version = hashlib.sha256(tex_file.read_bytes()).hexdigest()[:12]
        url = f"https://hctsui.github.io/{pdf_path}?v={version}"
        text = page.read_text(encoding="utf-8")
        updated, count = PATTERN.subn(rf"\g<1>{url}\g<2>", text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not find CV download button in {page.relative_to(ROOT)}")
        page.write_text(updated, encoding="utf-8")
        print(f"Updated {page.relative_to(ROOT)} -> {url}")


if __name__ == "__main__":
    main()

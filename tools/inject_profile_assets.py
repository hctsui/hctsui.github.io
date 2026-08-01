#!/usr/bin/env python3
"""Inject mixed-category styles into generated public HTML pages."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    changed = 0
    for path in sorted(ROOT.glob("*.html")) + sorted((ROOT / "zh").glob("*.html")):
        if path.name == "404.html" or "admin" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "assets/profile.css" in text or "</head>" not in text:
            continue
        prefix = "../" if path.relative_to(ROOT).as_posix().startswith("zh/") else ""
        text = text.replace("</head>", f'<link rel="stylesheet" href="{prefix}assets/profile.css">\n</head>', 1)
        path.write_text(text, encoding="utf-8")
        changed += 1
    print(f"Injected profile styles into {changed} pages.")


if __name__ == "__main__":
    main()

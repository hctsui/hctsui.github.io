
#!/usr/bin/env python3
"""Inject the self-hosted instant-navigation script into public HTML pages."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def script_for(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    prefix = "../" if rel.startswith("zh/") else ""
    return f'<script defer src="{prefix}assets/prefetch.js"></script>'

def main() -> None:
    changed = 0
    for path in sorted(ROOT.glob("*.html")) + sorted((ROOT / "zh").glob("*.html")):
        if path.name == "404.html" or "admin" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "assets/prefetch.js" in text or "</head>" not in text:
            continue
        text = text.replace("</head>", script_for(path) + "\n</head>", 1)
        path.write_text(text, encoding="utf-8")
        changed += 1
    print(f"Injected self-hosted prefetch into {changed} pages.")

if __name__ == "__main__":
    main()

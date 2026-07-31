#!/usr/bin/env python3
"""Build a public manifest for repository-managed images and downloadable files."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "content" / "media.json"
IMAGE_ROOT = ROOT / "assets" / "images"
COLLECTIONS = {
    "images": (IMAGE_ROOT, {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}),
    "slides": (ROOT / "files" / "slides", {".pdf", ".ppt", ".pptx"}),
    "papers": (ROOT / "files" / "papers", {".pdf"}),
}


def label_for(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip()


def build_manifest() -> dict:
    groups: dict[str, list[dict]] = {}
    for kind, (folder, extensions) in COLLECTIONS.items():
        rows = []
        if folder.exists():
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in extensions:
                    continue
                rel = path.relative_to(ROOT).as_posix()
                rows.append({
                    "path": rel,
                    "name": path.name,
                    "label": label_for(path),
                    "extension": path.suffix.lower(),
                    "size": path.stat().st_size,
                    "kind": kind,
                })
        groups[kind] = rows
    return {"schema_version": 1, **groups}


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()

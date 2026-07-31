#!/usr/bin/env python3
"""Apply the current CV subtitle-style update to an hctsui.github.io checkout.

The Admin JavaScript and documentation are regular replacement files in this
package.  This helper only performs the small, identical LaTeX macro update in
both CV templates and both currently generated TeX files, so the package does
not need to replace the user's entire CV documents.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

OLD_MACRO = r"""\newcommand{\cvgroup}[1]{%
    \needspace{3\baselineskip}%
    \vspace{0.08cm}%
    {\large\bfseries #1}\par%
    \vspace{0.08cm}%
}"""

NEW_MACRO = r"""\newcommand{\cvgroup}[1]{%
    \needspace{3\baselineskip}%
    \vspace{0.08cm}%
    {\large\bfseries #1}\hspace{0.15cm}%
    {\color{primaryColor!28}\titlerule[0.45pt]}\hspace{-0.1cm}\par%
    \vspace{0.08cm}%
}"""

TARGETS = (
    Path("cv/Hung-Chun-Tsui-CV.template.tex"),
    Path("cv/Hung-Chun-Tsui-CV-zh.template.tex"),
    Path("cv/Hung-Chun-Tsui-CV.tex"),
    Path("cv/Hung-Chun-Tsui-CV-zh.tex"),
)

# Fallback for harmless whitespace changes around the known macro.  It stops
# at the first line that contains only the closing brace of the definition.
MACRO_PATTERN = re.compile(
    r"\\newcommand\{\\cvgroup\}\[1\]\{%.*?^\}",
    flags=re.MULTILINE | re.DOTALL,
)


def repository_root() -> Path:
    script_root = Path(__file__).resolve().parent
    candidates = (script_root, Path.cwd().resolve())
    for candidate in candidates:
        if (candidate / "admin/homepage-v1.js").exists() and (candidate / "cv").is_dir():
            return candidate
    raise SystemExit(
        "找不到 repository 根目錄。請把更新包解壓到 hctsui.github.io 根目錄後，"
        "在該目錄執行 python3 apply-update.py。"
    )


def patch_file(path: Path) -> str:
    if not path.exists():
        # Generated TeX files may be absent in a fresh checkout; templates are
        # mandatory, generated files are optional because the build recreates them.
        if ".template." in path.name:
            raise RuntimeError(f"必要模板不存在：{path}")
        return "略過（檔案不存在，之後建置時會由模板產生）"

    text = path.read_text(encoding="utf-8")
    if NEW_MACRO in text:
        return "已是新版"
    if OLD_MACRO in text:
        updated = text.replace(OLD_MACRO, NEW_MACRO, 1)
    else:
        match = MACRO_PATTERN.search(text)
        if not match or r"\large\bfseries #1" not in match.group(0):
            raise RuntimeError(f"找不到可安全更新的 \\cvgroup 定義：{path}")
        updated = text[: match.start()] + NEW_MACRO + text[match.end() :]

    path.write_text(updated, encoding="utf-8")
    return "已更新"


def main() -> int:
    root = repository_root()
    print(f"Repository：{root}")
    failures: list[str] = []
    for relative in TARGETS:
        try:
            status = patch_file(root / relative)
            print(f"- {relative}: {status}")
        except RuntimeError as exc:
            failures.append(str(exc))
            print(f"- {relative}: 失敗", file=sys.stderr)

    if failures:
        print("\n更新未完整套用：", file=sys.stderr)
        for failure in failures:
            print(f"  • {failure}", file=sys.stderr)
        return 1

    print("\nCV 子標題樣式已套用。作品類別與教學機構會共用淡色右側橫線。")
    print("接著可執行：python3 -m unittest discover -s tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

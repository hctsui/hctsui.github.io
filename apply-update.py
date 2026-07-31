#!/usr/bin/env python3
"""Apply the v9 Admin identity and CV subtitle updates safely.

Regular replacement files in this package update the Admin JavaScript,
documentation, and homepage generation logic. This helper performs the small
in-place changes that should not replace whole user-maintained files:

* update the shared ``\\cvgroup`` macro in both CV templates and generated TeX;
* add the Admin favicon/header icon and a ``返回網站`` button to admin/index.html.

The operation is idempotent and can be run more than once.
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

CV_TARGETS = (
    Path("cv/Hung-Chun-Tsui-CV.template.tex"),
    Path("cv/Hung-Chun-Tsui-CV-zh.template.tex"),
    Path("cv/Hung-Chun-Tsui-CV.tex"),
    Path("cv/Hung-Chun-Tsui-CV-zh.tex"),
)

MACRO_PATTERN = re.compile(
    r"\\newcommand\{\\cvgroup\}\[1\]\{%.*?^\}",
    flags=re.MULTILINE | re.DOTALL,
)

ADMIN_IDENTITY_MARKER = "/* v9 admin identity */"
ADMIN_IDENTITY_CSS = r"""
      /* v9 admin identity */
      .admin-title-row {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .admin-title-row h1 {
        margin: 0;
      }
      .admin-brand-icon {
        width: 46px;
        height: 46px;
        flex: 0 0 auto;
        border-radius: 13px;
        box-shadow: 0 7px 18px rgba(75, 40, 34, 0.2);
      }
      .header-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }
""".rstrip()

GUIDE_LINK_PATTERN = re.compile(
    r'(<a\b[^>]*href="guide\.html"[^>]*>.*?開啟完整使用手冊.*?</a\s*>)',
    flags=re.DOTALL,
)
TITLE_PATTERN = re.compile(r"(<title>.*?</title>)", flags=re.DOTALL)


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


def patch_cv_file(path: Path) -> str:
    if not path.exists():
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


def patch_admin_index(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Admin 首頁不存在：{path}")
    text = path.read_text(encoding="utf-8")
    original = text

    if 'href="admin-icon.svg"' not in text:
        match = TITLE_PATTERN.search(text)
        if not match:
            raise RuntimeError(f"找不到 Admin <title>：{path}")
        addition = (
            match.group(1)
            + '\n    <link rel="icon" href="admin-icon.svg" type="image/svg+xml">'
            + '\n    <meta name="theme-color" content="#8d493d">'
        )
        text = text[: match.start()] + addition + text[match.end() :]

    if ADMIN_IDENTITY_MARKER not in text:
        closing = text.find("</style>")
        if closing < 0:
            raise RuntimeError(f"找不到 Admin </style>：{path}")
        text = text[:closing] + ADMIN_IDENTITY_CSS + "\n    " + text[closing:]

    if 'class="admin-title-row"' not in text:
        old_heading = "<h1>網站批次管理</h1>"
        if old_heading not in text:
            raise RuntimeError(f"找不到 Admin 主標題：{path}")
        new_heading = (
            '<div class="admin-title-row">'
            '<img class="admin-brand-icon" src="admin-icon.svg" alt="">'
            '<h1>網站批次管理</h1>'
            "</div>"
        )
        text = text.replace(old_heading, new_heading, 1)

    if "data-return-site" not in text:
        match = GUIDE_LINK_PATTERN.search(text)
        if not match:
            raise RuntimeError(f"找不到「開啟完整使用手冊」按鈕：{path}")
        site_button = (
            match.group(1)
            + '\n        <a class="button" href="../index.html" data-return-site>返回網站</a>'
        )
        text = text[: match.start()] + site_button + text[match.end() :]

    if text == original:
        return "已是新版"
    path.write_text(text, encoding="utf-8")
    return "已更新"


def main() -> int:
    root = repository_root()
    print(f"Repository：{root}")
    failures: list[str] = []

    for relative in CV_TARGETS:
        try:
            status = patch_cv_file(root / relative)
            print(f"- {relative}: {status}")
        except RuntimeError as exc:
            failures.append(str(exc))
            print(f"- {relative}: 失敗", file=sys.stderr)

    try:
        status = patch_admin_index(root / "admin/index.html")
        print(f"- admin/index.html: {status}")
    except RuntimeError as exc:
        failures.append(str(exc))
        print("- admin/index.html: 失敗", file=sys.stderr)

    if failures:
        print("\n更新未完整套用：", file=sys.stderr)
        for failure in failures:
            print(f"  • {failure}", file=sys.stderr)
        return 1

    print("\n更新已套用：")
    print("- CV 作品類別與教學機構使用淡色右側橫線。")
    print("- Admin 使用專用圖示，並在使用手冊旁提供「返回網站」。")
    print("接著可執行：python3 -m unittest discover -s tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

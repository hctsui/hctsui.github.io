#!/usr/bin/env python3
"""Regenerate Issue Forms from the group registry in content/site.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import process_request_v4 as groups

ROOT = Path(__file__).resolve().parents[1]
FORMS = ROOT / ".github" / "ISSUE_TEMPLATE"


def option(value: str, indent: int = 8) -> str:
    return " " * indent + "- " + json.dumps(value, ensure_ascii=False)


def label(group: dict[str, Any]) -> str:
    en = groups.group_label(group, "en")
    zh = groups.group_label(group, "zh")
    return f"{en} / {zh} [{group['id']}]"


def sorted_groups(data: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return sorted(groups.content_groups(data, kind), key=lambda g: (int(g.get("order", 999999)), str(g.get("id", ""))))


def add_publication(data: dict[str, Any]) -> str:
    group_options = ["Auto detect from metadata / 依期刊資訊自動判斷"]
    group_options += [label(g) for g in sorted_groups(data, "publication")]
    group_options += ["Other / 其他（建立新大標題）"]
    options = "\n".join(option(x) for x in group_options)
    return f'''name: Add publication / 新增論文
description: Add a paper, article, survey, or another publication type.
title: "[Website: Add publication] "
body:
  - type: markdown
    attributes:
      value: |
        **欄位標示**
        - **[必填]**：送出前一定要填。
        - **[選填]**：可以留空；留空時網站不輸出空白文字或按鈕。
        - 中文題目留空時預設照抄英文，避免誤配其他論文的舊翻譯。
        - 大標題可選既有分類；選 Other 後，新分類會自動加入未來表單。
  - type: dropdown
    id: chinese-mode
    attributes:
      label: Chinese handling / 中文欄位處理 [必填]
      options:
        - "Keep English title if Chinese title is blank / 中文題目留空時照抄英文"
        - "Auto translate blank Chinese fields / 自動翻譯空白中文欄位"
        - "I will fill Chinese fields myself / 中文由我自行填寫"
      default: 0
    validations: {{required: true}}
  - type: dropdown
    id: publication-section
    attributes:
      label: Publication section / 論文大標題 [必填]
      description: Auto 會在有 DOI、期刊頁面或正式期刊資訊時歸入 Journal Articles；其餘歸入 Preprints。Survey Papers 請明確選取。
      options:
{options}
      default: 0
    validations: {{required: true}}
  - type: input
    id: custom-section-en
    attributes:
      label: Custom publication section (English) / 自訂論文大標題英文 [選填]
      description: 只有選 Other 時填寫，例如 Book Chapters。
  - type: input
    id: custom-section-zh
    attributes:
      label: Custom publication section (Chinese) / 自訂論文大標題中文 [選填・可自動翻譯]
  - type: input
    id: date
    attributes:
      label: Public date / 公開日期 [必填]
      placeholder: "2026-04-05"
    validations: {{required: true}}
  - type: input
    id: title-en
    attributes:
      label: Title (English) / 英文題目 [必填]
    validations: {{required: true}}
  - type: input
    id: title-zh
    attributes:
      label: Title (Chinese) / 中文題目 [選填・可自動翻譯]
  - type: input
    id: authors-en
    attributes:
      label: Authors (English) / 作者英文 [必填]
    validations: {{required: true}}
  - type: input
    id: authors-zh
    attributes:
      label: Authors (Chinese) / 作者中文 [選填・可自動翻譯]
      description: 未知中文姓名會保留英文，不會擅自音譯。
  - type: input
    id: arxiv
    attributes:
      label: arXiv number / arXiv 編號 [選填]
      placeholder: "2604.03618"
  - type: input
    id: arxiv-url
    attributes:
      label: arXiv URL / arXiv 連結 [選填]
  - type: input
    id: pdf-url
    attributes:
      label: PDF URL / PDF 連結 [選填]
  - type: input
    id: doi-url
    attributes:
      label: DOI URL / DOI 連結 [選填]
      placeholder: "https://doi.org/..."
  - type: input
    id: journal-url
    attributes:
      label: Journal page URL / 期刊頁面連結 [選填]
  - type: input
    id: code-url
    attributes:
      label: Code URL / 程式碼連結 [選填]
  - type: input
    id: venue-en
    attributes:
      label: Venue or status (English) / 期刊或狀態英文 [選填]
      description: 例如 Submitted，或完整期刊名稱、卷期與頁碼。
  - type: input
    id: venue-zh
    attributes:
      label: Venue or status (Chinese) / 期刊或狀態中文 [選填・可自動翻譯]
'''


def add_teaching(data: dict[str, Any]) -> str:
    institution_options = [label(g) for g in sorted_groups(data, "teaching")]
    institution_options += ["Other / 其他（建立新機構大標題）"]
    options = "\n".join(option(x) for x in institution_options)
    return f'''name: Add teaching course / 新增教學課程
description: Add a teaching course under an institution heading.
title: "[Website: Add teaching] "
body:
  - type: markdown
    attributes:
      value: |
        **分組邏輯**
        - Teaching 頁面依「機構」自動產生大標題。
        - 選 Other 可新增任何學校；新增後，該學校會出現在未來表單選單。
        - 課程內仍顯示 Teaching Assistant、Lecturer 或自訂身分，不再另外產生重複的身分大標題。
        - 排序請在 Admin 的「網站排序」功能調整。
  - type: dropdown
    id: chinese-mode
    attributes:
      label: Chinese handling / 中文欄位處理 [必填]
      options:
        - "Auto translate blank Chinese fields / 自動翻譯空白中文欄位"
        - "I will fill Chinese fields myself / 中文由我自行填寫"
      default: 0
    validations: {{required: true}}
  - type: dropdown
    id: institution-section
    attributes:
      label: Institution section / 機構大標題 [必填]
      options:
{options}
      default: 0
    validations: {{required: true}}
  - type: input
    id: custom-institution-en
    attributes:
      label: Custom institution (English) / 自訂機構英文 [選填]
      description: 只有選 Other 時填寫。
  - type: input
    id: custom-institution-zh
    attributes:
      label: Custom institution (Chinese) / 自訂機構中文 [選填・可自動翻譯]
  - type: dropdown
    id: role
    attributes:
      label: Role / 教學身分 [必填]
      options:
        - "Teaching Assistant / 助教"
        - "Lecturer / 講師"
        - "Other / 其他（下方自訂）"
      default: 0
    validations: {{required: true}}
  - type: input
    id: custom-role-en
    attributes:
      label: Custom role (English) / 自訂身分英文 [選填]
  - type: input
    id: custom-role-zh
    attributes:
      label: Custom role (Chinese) / 自訂身分中文 [選填・可自動翻譯]
  - type: input
    id: term-en
    attributes:
      label: Term (English) / 學期英文 [必填]
      placeholder: "Fall 2026"
    validations: {{required: true}}
  - type: input
    id: term-zh
    attributes:
      label: Term (Chinese) / 學期中文 [選填・可自動翻譯]
      placeholder: "2026 秋"
  - type: input
    id: course-en
    attributes:
      label: Course (English) / 課程英文 [必填]
      placeholder: "MATH2410 Algebra I"
    validations: {{required: true}}
  - type: input
    id: course-zh
    attributes:
      label: Course (Chinese) / 課程中文 [選填・可自動翻譯]
'''


def edit_entry(data: dict[str, Any]) -> str:
    pub_options = ["Keep unchanged / 維持不變", "Auto detect from updated metadata / 依更新後資訊自動判斷"]
    pub_options += [label(g) for g in sorted_groups(data, "publication")]
    pub_options += ["Other / 其他（建立新大標題）"]
    institution_options = ["Keep unchanged / 維持不變"]
    institution_options += [label(g) for g in sorted_groups(data, "teaching")]
    institution_options += ["Other / 其他（建立新機構大標題）"]
    pubs = "\n".join(option(x) for x in pub_options)
    institutions = "\n".join(option(x) for x in institution_options)
    return f'''name: Edit existing entry / 編輯既有項目
description: Change selected fields and automatically move entries between sections when needed.
title: "[Website: Edit] "
body:
  - type: markdown
    attributes:
      value: |
        從 `/admin/` 複製 Entry ID。只填要修改的欄位，其餘留空。
        Publication 新增 DOI、期刊頁面或正式期刊資訊時，即使分類保持不變，系統也會自動移到 Journal Articles。
  - type: dropdown
    id: chinese-mode
    attributes:
      label: Chinese handling / 中文欄位處理 [必填]
      options:
        - "Auto translate blank Chinese fields / 自動翻譯空白中文欄位"
        - "I will fill Chinese fields myself / 中文由我自行填寫"
      default: 0
    validations: {{required: true}}
  - type: input
    id: entry-id
    attributes:
      label: Entry ID / 項目 ID [必填]
    validations: {{required: true}}
  - type: input
    id: title-en
    attributes:
      label: New English title/name/course / 新英文題目、名稱或課名 [選填]
  - type: input
    id: title-zh
    attributes:
      label: New Chinese title/name/course / 新中文題目、名稱或課名 [選填・可自動翻譯]
  - type: input
    id: start
    attributes:
      label: New start/public date / 新開始或公開日期 [選填]
      placeholder: "YYYY-MM-DD"
  - type: input
    id: end
    attributes:
      label: New end date / 新結束日期 [選填]
      placeholder: "YYYY-MM-DD"
  - type: input
    id: year
    attributes:
      label: New year / 新年份 [選填]
  - type: input
    id: url
    attributes:
      label: New main URL / 新主要連結 [選填]
  - type: textarea
    id: desc-en
    attributes:
      label: New English description/organization/term / 新英文說明、單位或學期 [選填]
  - type: textarea
    id: desc-zh
    attributes:
      label: New Chinese description/organization/term / 新中文說明、單位或學期 [選填・可自動翻譯]
  - type: input
    id: authors-en
    attributes:
      label: New authors (English) / 新作者英文 [選填]
  - type: input
    id: authors-zh
    attributes:
      label: New authors (Chinese) / 新作者中文 [選填・可自動翻譯]
  - type: input
    id: auxiliary
    attributes:
      label: New slides or PDF URL / 新投影片或 PDF 連結 [選填]
  - type: dropdown
    id: publication-section
    attributes:
      label: New publication section / 新論文大標題 [選填]
      description: 只適用於 Publication。增加期刊資訊時會優先自動移到 Journal Articles。
      options:
{pubs}
      default: 0
  - type: input
    id: custom-pub-section-en
    attributes:
      label: New custom publication section (English) / 新自訂論文大標題英文 [選填]
  - type: input
    id: custom-pub-section-zh
    attributes:
      label: New custom publication section (Chinese) / 新自訂論文大標題中文 [選填・可自動翻譯]
  - type: input
    id: venue-en
    attributes:
      label: New venue or status (English) / 新期刊或狀態英文 [選填]
  - type: input
    id: venue-zh
    attributes:
      label: New venue or status (Chinese) / 新期刊或狀態中文 [選填・可自動翻譯]
  - type: input
    id: arxiv
    attributes:
      label: New arXiv number / 新 arXiv 編號 [選填]
  - type: input
    id: pdf-url
    attributes:
      label: New PDF URL / 新 PDF 連結 [選填]
  - type: input
    id: doi-url
    attributes:
      label: New DOI URL / 新 DOI 連結 [選填]
  - type: input
    id: journal-url
    attributes:
      label: New journal page URL / 新期刊頁面連結 [選填]
  - type: input
    id: code-url
    attributes:
      label: New code URL / 新程式碼連結 [選填]
  - type: dropdown
    id: institution-section
    attributes:
      label: New institution section / 新機構大標題 [選填]
      description: 只適用於 Teaching。
      options:
{institutions}
      default: 0
  - type: input
    id: custom-institution-en
    attributes:
      label: New custom institution (English) / 新自訂機構英文 [選填]
  - type: input
    id: custom-institution-zh
    attributes:
      label: New custom institution (Chinese) / 新自訂機構中文 [選填・可自動翻譯]
  - type: dropdown
    id: teaching-role
    attributes:
      label: New teaching role / 新教學身分 [選填]
      options:
        - "Keep unchanged / 維持不變"
        - "Teaching Assistant / 助教"
        - "Lecturer / 講師"
        - "Other / 其他（下方自訂）"
      default: 0
  - type: input
    id: custom-role-en
    attributes:
      label: New custom role (English) / 新自訂身分英文 [選填]
  - type: input
    id: custom-role-zh
    attributes:
      label: New custom role (Chinese) / 新自訂身分中文 [選填・可自動翻譯]
  - type: dropdown
    id: upcoming
    attributes:
      label: Upcoming setting / Upcoming 設定 [選填]
      options:
        - "Keep unchanged / 維持不變"
        - "Yes / 是"
        - "No / 否"
      default: 0
'''


def reorder_form() -> str:
    return '''name: Save website ordering / 儲存網站排序
description: Save the order copied by the Admin page for any website category.
title: "[Website: Reorder] "
body:
  - type: markdown
    attributes:
      value: |
        請從 `/admin/` 選擇一個類別，進入網站排序模式，調整後按「儲存目前順序」。
        Conference、Talk、Visit、Honor、Publication、Teaching 都支援；Publication 與 Teaching 也可調整大標題順序。
  - type: textarea
    id: ordering
    attributes:
      label: Ordering payload / 排序資料 [必填]
      description: 直接貼上 Admin 複製的 JSON；不要手動刪改 Entry ID。
      placeholder: 貼上完整 JSON
    validations:
      required: true
'''


def main() -> None:
    data = groups.migrate_data(json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8")))
    FORMS.mkdir(parents=True, exist_ok=True)
    outputs = {
        "add-publication.yml": add_publication(data),
        "add-teaching.yml": add_teaching(data),
        "edit-entry.yml": edit_entry(data),
        "reorder-entries.yml": reorder_form(),
    }
    for name, text in outputs.items():
        (FORMS / name).write_text(text, encoding="utf-8")
    print("Generated dynamic Issue Forms: " + ", ".join(outputs))


if __name__ == "__main__":
    main()

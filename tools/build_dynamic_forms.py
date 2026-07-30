#!/usr/bin/env python3
"""Regenerate all Issue Forms from the current group registry."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import process_request as core

ROOT = Path(__file__).resolve().parents[1]
FORMS = ROOT / ".github" / "ISSUE_TEMPLATE"


def option(value: str, indent: int = 8) -> str:
    return " " * indent + "- " + json.dumps(value, ensure_ascii=False)


def group_option(group: dict[str, Any]) -> str:
    en = core.group_label(group, "en")
    zh = core.group_label(group, "zh")
    visible = " / ".join(x for x in (en, zh) if x) or "Unnamed group / 未命名群組"
    return f"{visible} [{group['id']}]"


def sorted_groups(data: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return sorted(core.content_groups(data, kind), key=lambda g: (int(g.get("order", 999999)), str(g.get("id", ""))))


def mode_block() -> str:
    return '''  - type: dropdown
    id: bilingual-mode
    attributes:
      label: Bilingual completion / 雙語欄位補全 [必填]
      description: 對照表只做完整字串的一對一比對；不使用 AI、相似名稱、舊網站內容或模糊推測。
      options:
        - "Keep blanks / 空白保持空白"
        - "Use Admin dictionary / 使用 Admin 中英對照表補全"
      default: 0
    validations: {required: true}
'''


def conference_form() -> str:
    return f'''name: Add conference / 新增會議
description: Add a conference or workshop; it can appear in Upcoming first.
title: "[Website: Add conference] "
body:
  - type: markdown
    attributes:
      value: |
        日期請使用 `YYYY-MM-DD`。會議英文／中文名稱至少填一個；其他雙語欄位可各自留空。
{mode_block()}  - type: input
    id: start-date
    attributes: {{label: Start date / 開始日期 [必填], placeholder: "2026-08-24"}}
    validations: {{required: true}}
  - type: input
    id: end-date
    attributes: {{label: End date / 結束日期 [選填], description: 單日活動可留空。}}
  - type: dropdown
    id: upcoming
    attributes:
      label: Show on Upcoming? / 是否先顯示於 Upcoming [必填]
      options: ["Yes / 是", "No / 否"]
      default: 0
    validations: {{required: true}}
  - type: input
    id: title-en
    attributes: {{label: Conference name (English) / 會議英文名稱 [條件必填]}}
  - type: input
    id: title-zh
    attributes: {{label: Conference name (Chinese) / 會議中文名稱 [條件必填]}}
  - type: input
    id: url
    attributes: {{label: Conference URL / 會議連結 [選填]}}
  - type: input
    id: venue-en
    attributes: {{label: Venue (English) / 地點英文 [選填]}}
  - type: input
    id: venue-zh
    attributes: {{label: Venue (Chinese) / 地點中文 [選填・可由對照表補全]}}
  - type: input
    id: city-en
    attributes: {{label: City (English) / 城市英文 [選填]}}
  - type: input
    id: city-zh
    attributes: {{label: City (Chinese) / 城市中文 [選填・可由對照表補全]}}
  - type: input
    id: country-en
    attributes: {{label: Country (English) / 國家英文 [選填]}}
  - type: input
    id: country-zh
    attributes: {{label: Country (Chinese) / 國家中文 [選填・可由對照表補全]}}
'''


def talk_form() -> str:
    return f'''name: Add talk / 新增學術報告
description: Add a talk, seminar, or conference presentation.
title: "[Website: Add talk] "
body:
  - type: markdown
    attributes:
      value: |
        演講英文／中文題目至少填一個。需要斜體可寫 `[i]u[/i]`。
{mode_block()}  - type: input
    id: date
    attributes: {{label: Talk date / 演講日期 [必填], placeholder: "2026-07-06"}}
    validations: {{required: true}}
  - type: input
    id: end-date
    attributes: {{label: End date (optional) / 結束日期（選填） [選填]}}
  - type: dropdown
    id: upcoming
    attributes:
      label: Show on Upcoming? / 是否先顯示於 Upcoming [必填]
      options: ["Yes / 是", "No / 否"]
      default: 0
    validations: {{required: true}}
  - type: input
    id: title-en
    attributes: {{label: Talk title (English) / 演講英文題目 [條件必填]}}
  - type: input
    id: title-zh
    attributes: {{label: Talk title (Chinese) / 演講中文題目 [條件必填]}}
  - type: input
    id: url
    attributes: {{label: Talk or event URL / 演講或活動連結 [選填]}}
  - type: input
    id: event-en
    attributes: {{label: Event (English) / 活動英文名稱 [選填]}}
  - type: input
    id: event-zh
    attributes: {{label: Event (Chinese) / 活動中文名稱 [選填・可由對照表補全]}}
  - type: input
    id: institution-en
    attributes: {{label: Institution (English) / 機構英文 [選填]}}
  - type: input
    id: institution-zh
    attributes: {{label: Institution (Chinese) / 機構中文 [選填・可由對照表補全]}}
  - type: input
    id: city-en
    attributes: {{label: City (English) / 城市英文 [選填]}}
  - type: input
    id: city-zh
    attributes: {{label: City (Chinese) / 城市中文 [選填・可由對照表補全]}}
  - type: input
    id: country-en
    attributes: {{label: Country (English) / 國家英文 [選填]}}
  - type: input
    id: country-zh
    attributes: {{label: Country (Chinese) / 國家中文 [選填・可由對照表補全]}}
  - type: input
    id: slides
    attributes: {{label: Slides URL / 投影片連結 [選填]}}
'''


def visit_form() -> str:
    return f'''name: Add academic visit / 新增學術訪問
description: Add an academic visit, including optional funding information.
title: "[Website: Add visit] "
body:
  - type: markdown
    attributes:
      value: 訪問機構英文／中文至少填一個；未補全的另一語言保持空白。
{mode_block()}  - type: input
    id: start-date
    attributes: {{label: Start date / 開始日期 [必填], placeholder: "2026-07-02"}}
    validations: {{required: true}}
  - type: input
    id: end-date
    attributes: {{label: End date / 結束日期 [選填]}}
  - type: dropdown
    id: upcoming
    attributes:
      label: Show on Upcoming? / 是否先顯示於 Upcoming [必填]
      options: ["Yes / 是", "No / 否"]
      default: 1
    validations: {{required: true}}
  - type: input
    id: institution-en
    attributes: {{label: Institution (English) / 機構英文 [條件必填]}}
  - type: input
    id: institution-zh
    attributes: {{label: Institution (Chinese) / 機構中文 [條件必填]}}
  - type: input
    id: url
    attributes: {{label: Institution or visit URL / 機構或訪問連結 [選填]}}
  - type: input
    id: city-en
    attributes: {{label: City (English) / 城市英文 [選填]}}
  - type: input
    id: city-zh
    attributes: {{label: City (Chinese) / 城市中文 [選填・可由對照表補全]}}
  - type: input
    id: country-en
    attributes: {{label: Country (English) / 國家英文 [選填]}}
  - type: input
    id: country-zh
    attributes: {{label: Country (Chinese) / 國家中文 [選填・可由對照表補全]}}
  - type: textarea
    id: description-en
    attributes: {{label: Description (English) / 說明英文 [選填]}}
  - type: textarea
    id: description-zh
    attributes: {{label: Description (Chinese) / 說明中文 [選填・可由對照表補全]}}
  - type: input
    id: funding-en
    attributes:
      label: Funding institution or program (English) / 補助機構或計畫英文 [選填]
      description: 填寫後會自動在說明末尾加入「Supported by …」。
  - type: input
    id: funding-zh
    attributes:
      label: Funding institution or program (Chinese) / 補助機構或計畫中文 [選填・可由對照表補全]
      description: 填寫後會自動在說明末尾加入「本次訪問獲……支持。」
'''


def honor_form() -> str:
    return f'''name: Add honor or award / 新增獎項
description: Add an honor, scholarship, fellowship, or award.
title: "[Website: Add honor] "
body:
  - type: markdown
    attributes:
      value: 獎項英文／中文名稱至少填一個。
{mode_block()}  - type: input
    id: year
    attributes: {{label: Year / 年份 [必填], placeholder: "2026"}}
    validations: {{required: true}}
  - type: input
    id: name-en
    attributes: {{label: Honor name (English) / 獎項英文名稱 [條件必填]}}
  - type: input
    id: name-zh
    attributes: {{label: Honor name (Chinese) / 獎項中文名稱 [條件必填]}}
  - type: input
    id: org-en
    attributes: {{label: Organization (English) / 頒發單位英文 [選填]}}
  - type: input
    id: org-zh
    attributes: {{label: Organization (Chinese) / 頒發單位中文 [選填・可由對照表補全]}}
  - type: input
    id: url
    attributes: {{label: Honor URL / 獎項連結 [選填]}}
'''


def publication_form(data: dict[str, Any]) -> str:
    opts = ["Auto detect from metadata / 依期刊資訊自動判斷"] + [group_option(g) for g in sorted_groups(data, "publication")] + ["Other / 其他（建立新大標題）"]
    options = "\n".join(option(x) for x in opts)
    return f'''name: Add publication / 新增論文
description: Add a paper, article, survey, or another publication type.
title: "[Website: Add publication] "
body:
  - type: markdown
    attributes:
      value: |
        題目英文／中文至少填一個；作者英文／中文至少填一個。各分組在 PDF CV 中會各自從 `[1]` 重新編號。
{mode_block()}  - type: dropdown
    id: publication-section
    attributes:
      label: Publication section / 論文大標題 [必填]
      options:
{options}
      default: 0
    validations: {{required: true}}
  - type: input
    id: custom-section-en
    attributes: {{label: Custom publication section (English) / 自訂論文大標題英文 [選填]}}
  - type: input
    id: custom-section-zh
    attributes: {{label: Custom publication section (Chinese) / 自訂論文大標題中文 [選填・可由對照表補全]}}
  - type: input
    id: date
    attributes: {{label: Public date / 公開日期 [必填], placeholder: "2026-04-05"}}
    validations: {{required: true}}
  - type: input
    id: title-en
    attributes: {{label: Title (English) / 英文題目 [條件必填]}}
  - type: input
    id: title-zh
    attributes: {{label: Title (Chinese) / 中文題目 [條件必填]}}
  - type: input
    id: authors-en
    attributes: {{label: Authors (English) / 作者英文 [條件必填]}}
  - type: input
    id: authors-zh
    attributes: {{label: Authors (Chinese) / 作者中文 [條件必填]}}
  - type: input
    id: arxiv
    attributes: {{label: arXiv number / arXiv 編號 [選填], placeholder: "2604.03618"}}
  - type: input
    id: arxiv-url
    attributes: {{label: arXiv URL / arXiv 連結 [選填]}}
  - type: input
    id: pdf-url
    attributes: {{label: PDF URL / PDF 連結 [選填]}}
  - type: input
    id: doi-url
    attributes: {{label: DOI URL / DOI 連結 [選填]}}
  - type: input
    id: journal-url
    attributes: {{label: Journal page URL / 期刊頁面連結 [選填]}}
  - type: input
    id: code-url
    attributes: {{label: Code URL / 程式碼連結 [選填]}}
  - type: input
    id: venue-en
    attributes: {{label: Venue or status (English) / 期刊或狀態英文 [選填]}}
  - type: input
    id: venue-zh
    attributes: {{label: Venue or status (Chinese) / 期刊或狀態中文 [選填・可由對照表補全]}}
'''


def teaching_form(data: dict[str, Any]) -> str:
    options = "\n".join(option(x) for x in [group_option(g) for g in sorted_groups(data, "teaching")] + ["Other / 其他（建立新機構大標題）"])
    return f'''name: Add teaching course / 新增教學課程
description: Add a teaching course under an institution heading.
title: "[Website: Add teaching] "
body:
  - type: markdown
    attributes:
      value: 學期英文／中文至少填一個；課程英文／中文至少填一個。機構大標題會動態建立並自動移除空群組。
{mode_block()}  - type: dropdown
    id: institution-section
    attributes:
      label: Institution section / 機構大標題 [必填]
      options:
{options}
      default: 0
    validations: {{required: true}}
  - type: input
    id: custom-institution-en
    attributes: {{label: Custom institution (English) / 自訂機構英文 [選填]}}
  - type: input
    id: custom-institution-zh
    attributes: {{label: Custom institution (Chinese) / 自訂機構中文 [選填・可由對照表補全]}}
  - type: dropdown
    id: role
    attributes:
      label: Role / 教學身分 [必填]
      options: ["Teaching Assistant / 助教", "Lecturer / 講師", "Other / 其他（下方自訂）"]
      default: 0
    validations: {{required: true}}
  - type: input
    id: custom-role-en
    attributes: {{label: Custom role (English) / 自訂身分英文 [選填]}}
  - type: input
    id: custom-role-zh
    attributes: {{label: Custom role (Chinese) / 自訂身分中文 [選填・可由對照表補全]}}
  - type: input
    id: term-en
    attributes: {{label: Term (English) / 學期英文 [條件必填], placeholder: "Fall 2026"}}
  - type: input
    id: term-zh
    attributes: {{label: Term (Chinese) / 學期中文 [條件必填], placeholder: "2026 秋"}}
  - type: input
    id: course-en
    attributes: {{label: Course (English) / 課程英文 [條件必填], placeholder: "MATH2410 Algebra I"}}
  - type: input
    id: course-zh
    attributes: {{label: Course (Chinese) / 課程中文 [條件必填]}}
'''


def edit_form(data: dict[str, Any]) -> str:
    pubs = "\n".join(option(x) for x in ["Keep unchanged / 維持不變", "Auto detect from updated metadata / 依更新後資訊自動判斷"] + [group_option(g) for g in sorted_groups(data, "publication")] + ["Other / 其他（建立新大標題）"])
    institutions = "\n".join(option(x) for x in ["Keep unchanged / 維持不變"] + [group_option(g) for g in sorted_groups(data, "teaching")] + ["Other / 其他（建立新機構大標題）"])
    return f'''name: Edit existing entry / 編輯既有項目
description: Change selected fields and automatically move entries between sections when needed.
title: "[Website: Edit] "
body:
  - type: markdown
    attributes:
      value: 從 `/admin/` 複製 Entry ID。空白欄位代表維持原值；若只填其中一種語言，另一種只有在對照表命中時才更新。要清除既有的某個語言欄位，請在該欄輸入 `[CLEAR]`。
{mode_block()}  - type: input
    id: entry-id
    attributes: {{label: Entry ID / 項目 ID [必填]}}
    validations: {{required: true}}
  - type: input
    id: title-en
    attributes: {{label: New English title/name/course / 新英文題目、名稱或課名 [選填]}}
  - type: input
    id: title-zh
    attributes: {{label: New Chinese title/name/course / 新中文題目、名稱或課名 [選填・可由對照表補全]}}
  - type: input
    id: start
    attributes: {{label: New start/public date / 新開始或公開日期 [選填], placeholder: "YYYY-MM-DD"}}
  - type: input
    id: end
    attributes: {{label: New end date / 新結束日期 [選填], placeholder: "YYYY-MM-DD"}}
  - type: input
    id: year
    attributes: {{label: New year / 新年份 [選填]}}
  - type: input
    id: url
    attributes: {{label: New main URL / 新主要連結 [選填]}}
  - type: textarea
    id: desc-en
    attributes: {{label: New English description/organization/term / 新英文說明、單位或學期 [選填]}}
  - type: textarea
    id: desc-zh
    attributes: {{label: New Chinese description/organization/term / 新中文說明、單位或學期 [選填・可由對照表補全]}}
  - type: input
    id: authors-en
    attributes: {{label: New authors (English) / 新作者英文 [選填]}}
  - type: input
    id: authors-zh
    attributes: {{label: New authors (Chinese) / 新作者中文 [選填・可由對照表補全]}}
  - type: input
    id: auxiliary
    attributes: {{label: New slides or PDF URL / 新投影片或 PDF 連結 [選填]}}
  - type: dropdown
    id: publication-section
    attributes:
      label: New publication section / 新論文大標題 [選填]
      options:
{pubs}
      default: 0
  - type: input
    id: custom-pub-section-en
    attributes: {{label: New custom publication section (English) / 新自訂論文大標題英文 [選填]}}
  - type: input
    id: custom-pub-section-zh
    attributes: {{label: New custom publication section (Chinese) / 新自訂論文大標題中文 [選填・可由對照表補全]}}
  - type: input
    id: venue-en
    attributes: {{label: New venue or status (English) / 新期刊或狀態英文 [選填]}}
  - type: input
    id: venue-zh
    attributes: {{label: New venue or status (Chinese) / 新期刊或狀態中文 [選填・可由對照表補全]}}
  - type: input
    id: arxiv
    attributes: {{label: New arXiv number / 新 arXiv 編號 [選填]}}
  - type: input
    id: pdf-url
    attributes: {{label: New PDF URL / 新 PDF 連結 [選填]}}
  - type: input
    id: doi-url
    attributes: {{label: New DOI URL / 新 DOI 連結 [選填]}}
  - type: input
    id: journal-url
    attributes: {{label: New journal page URL / 新期刊頁面連結 [選填]}}
  - type: input
    id: code-url
    attributes: {{label: New code URL / 新程式碼連結 [選填]}}
  - type: dropdown
    id: institution-section
    attributes:
      label: New institution section / 新機構大標題 [選填]
      options:
{institutions}
      default: 0
  - type: input
    id: custom-institution-en
    attributes: {{label: New custom institution (English) / 新自訂機構英文 [選填]}}
  - type: input
    id: custom-institution-zh
    attributes: {{label: New custom institution (Chinese) / 新自訂機構中文 [選填・可由對照表補全]}}
  - type: dropdown
    id: teaching-role
    attributes:
      label: New teaching role / 新教學身分 [選填]
      options: ["Keep unchanged / 維持不變", "Teaching Assistant / 助教", "Lecturer / 講師", "Other / 其他（下方自訂）"]
      default: 0
  - type: input
    id: custom-role-en
    attributes: {{label: New custom role (English) / 新自訂身分英文 [選填]}}
  - type: input
    id: custom-role-zh
    attributes: {{label: New custom role (Chinese) / 新自訂身分中文 [選填・可由對照表補全]}}
  - type: dropdown
    id: upcoming
    attributes:
      label: Upcoming setting / Upcoming 設定 [選填]
      options: ["Keep unchanged / 維持不變", "Yes / 是", "No / 否"]
      default: 0
'''


def category_edit_forms(data: dict[str, Any]) -> dict[str, str]:
    """Generate short category-specific edit forms.

    GitHub Issue Forms cannot conditionally hide fields, so each content type
    gets its own form. All forms intentionally keep the legacy field labels
    expected by process_request.py.
    """
    generic = edit_form(data)

    def extract(start_id: str, next_id: str | None = None) -> str:
        start = generic.index(f"  - type:", generic.index(f"    id: {start_id}") - 30)
        if next_id is None:
            return generic[start:]
        end = generic.index("  - type:", generic.index(f"    id: {next_id}") - 30)
        return generic[start:end]

    header = generic.split("  - type: input\n    id: title-en", 1)[0]
    title = extract("title-en", "start")
    dates = extract("start", "year")
    year = extract("year", "url")
    url = extract("url", "desc-en")
    desc = extract("desc-en", "authors-en")
    authors = extract("authors-en", "auxiliary")
    auxiliary = extract("auxiliary", "publication-section")
    publication = extract("publication-section", "institution-section")
    teaching = extract("institution-section", "upcoming")
    upcoming = extract("upcoming")

    visit_details = """  - type: input
    id: visit-city-en
    attributes: {label: New city (English) / 新城市英文 [選填]}
  - type: input
    id: visit-city-zh
    attributes: {label: New city (Chinese) / 新城市中文 [選填・可由對照表補全]}
  - type: input
    id: visit-country-en
    attributes: {label: New country (English) / 新國家英文 [選填]}
  - type: input
    id: visit-country-zh
    attributes: {label: New country (Chinese) / 新國家中文 [選填・可由對照表補全]}
  - type: textarea
    id: visit-description-en
    attributes: {label: New description (English) / 新說明英文 [選填]}
  - type: textarea
    id: visit-description-zh
    attributes: {label: New description (Chinese) / 新說明中文 [選填・可由對照表補全]}
  - type: input
    id: visit-funding-en
    attributes:
      label: New funding institution or program (English) / 新補助機構或計畫英文 [選填]
      description: 填寫後會自動加入 Supported by …
  - type: input
    id: visit-funding-zh
    attributes:
      label: New funding institution or program (Chinese) / 新補助機構或計畫中文 [選填・可由對照表補全]
      description: 填寫後會自動加入本次訪問獲……支持。
"""

    def named(name: str, description: str, body: str) -> str:
        prefix = f"name: {name}\ndescription: {description}\ntitle: \"[Website: Edit] \"\n"
        body_start = header.index("body:")
        common = header[header.index("body:") + len("body:\n"):]
        return prefix + "body:\n" + common + body

    return {
        "edit-conference.yml": named("Edit conference / 編輯會議", "Only conference fields are shown.", title + dates + url + desc + upcoming),
        "edit-talk.yml": named("Edit talk / 編輯學術報告", "Only talk fields are shown.", title + dates + url + desc + auxiliary + upcoming),
        "edit-visit.yml": named("Edit academic visit / 編輯學術訪問", "Only visit fields are shown.", title + dates + url + visit_details + upcoming),
        "edit-honor.yml": named("Edit honor or award / 編輯獎項", "Only honor fields are shown.", title + year + url + desc),
        "edit-publication.yml": named("Edit publication / 編輯論文或作品", "Only publication fields are shown.", title + extract("start", "end") + authors + publication),
        "edit-teaching.yml": named("Edit teaching entry / 編輯教學經驗", "Only teaching fields are shown.", title + desc + teaching),
    }


def reorder_form() -> str:
    return '''name: Save website ordering / 儲存網站排序
description: Save the order copied by the Admin page for any website category.
title: "[Website: Reorder] "
body:
  - type: textarea
    id: ordering
    attributes:
      label: Ordering payload / 排序資料 [必填]
      description: 直接貼上 Admin 複製的 JSON。
    validations: {required: true}
'''


def quote_flow_labels(text: str) -> str:
    """Quote label values inside compact YAML flow mappings."""
    import re

    pattern = re.compile(
        r"^(\s*attributes:\s*\{label:\s*)(.*?)(,\s*(?:placeholder|description):|\})$",
        re.MULTILINE,
    )

    def repl(match: re.Match[str]) -> str:
        return match.group(1) + json.dumps(match.group(2).strip(), ensure_ascii=False) + match.group(3)

    return pattern.sub(repl, text)


def main() -> None:
    data = core.migrate_data(json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8")))
    FORMS.mkdir(parents=True, exist_ok=True)
    outputs = {
        "add-conference.yml": conference_form(),
        "add-talk.yml": talk_form(),
        "add-visit.yml": visit_form(),
        "add-honor.yml": honor_form(),
        "add-publication.yml": publication_form(data),
        "add-teaching.yml": teaching_form(data),
        "edit-entry.yml": edit_form(data),
        "reorder-entries.yml": reorder_form(),
        **category_edit_forms(data),
    }
    for name, text in outputs.items():
        (FORMS / name).write_text(quote_flow_labels(text), encoding="utf-8")
    print("Generated Issue Forms: " + ", ".join(outputs))


if __name__ == "__main__":
    main()

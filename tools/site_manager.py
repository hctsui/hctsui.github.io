#!/usr/bin/env python3
"""Small bilingual content manager for hctsui.github.io.

- GUI mode: python tools/site_manager.py
- Sync/rollover: python tools/site_manager.py --sync
- Test a date: python tools/site_manager.py --sync --today 2026-08-29
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from bs4 import BeautifulSoup, Tag
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: beautifulsoup4\n"
        "Run: python3 -m pip install -r tools/requirements.txt"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "tools" / "content.json"
MANAGED_ATTR = "data-entry-id"

PAGE_CONFIG = {
    "en": {
        "index": ROOT / "index.html",
        "activities": ROOT / "activities.html",
        "cv": ROOT / "cv.html",
        "headings": {
            "conference": "Conferences and workshops",
            "talk": "Presentations",
            "visit": "Academic visit",
            "honor": "Honors and Awards",
        },
        "footer_prefix": "Last updated:",
    },
    "zh": {
        "index": ROOT / "zh" / "index.html",
        "activities": ROOT / "zh" / "activities.html",
        "cv": ROOT / "zh" / "cv.html",
        "headings": {
            "conference": "會議與工作坊",
            "talk": "學術報告",
            "visit": "學術訪問",
            "honor": "獎項與榮譽",
        },
        "footer_prefix": "最後更新：",
    },
}

KIND_LABELS = {
    "conference": "Conference participation / 會議參與",
    "talk": "Talk / 學術報告",
    "honor": "Honor or award / 獎項與榮譽",
    "visit": "Academic visit / 學術訪問",
}


def load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"version": 1, "entries": []}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_data(data: dict[str, Any]) -> None:
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_iso(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD.") from exc


def format_date(value: str) -> str:
    d = parse_iso(value, "Date")
    return f"{d.year}/{d.month}/{d.day}"


def display_range(entry: dict[str, Any]) -> str:
    start = entry.get("start_date", "")
    end = entry.get("end_date", "")
    if not start:
        return str(entry.get("year", ""))
    if not end or end == start:
        return format_date(start)
    return f"{format_date(start)}–{format_date(end)}"


def entry_end(entry: dict[str, Any]) -> date | None:
    if entry["kind"] == "honor":
        return None
    value = entry.get("end_date") or entry.get("start_date")
    return parse_iso(value, "End date") if value else None


def entry_start_key(entry: dict[str, Any]) -> date:
    if entry["kind"] == "honor":
        return date(int(entry["year"]), 1, 1)
    return parse_iso(entry["start_date"], "Start date")


def should_be_upcoming(entry: dict[str, Any], today: date) -> bool:
    if not entry.get("show_upcoming") or entry["kind"] == "honor":
        return False
    end = entry_end(entry)
    return bool(end and end >= today)


def should_be_archived(entry: dict[str, Any], today: date) -> bool:
    if entry["kind"] == "honor":
        return True
    return not should_be_upcoming(entry, today)


def make_id(entry: dict[str, Any]) -> str:
    raw_title = (
        entry.get("title", {}).get("en")
        or entry.get("name", {}).get("en")
        or entry.get("institution", {}).get("en")
        or entry["kind"]
    )
    slug = re.sub(r"[^a-z0-9]+", "-", raw_title.lower()).strip("-")[:46]
    anchor = entry.get("start_date") or str(entry.get("year", ""))
    digest = hashlib.sha1(
        json.dumps(entry, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:7]
    return f"{entry['kind']}-{anchor}-{slug}-{digest}".strip("-")


def add_link(soup: BeautifulSoup, parent: Tag, text: str, url: str | None) -> None:
    if url:
        a = soup.new_tag("a", href=url, target="_blank", rel="noopener")
        a.string = text
        parent.append(a)
    else:
        parent.string = text


def localized(entry: dict[str, Any], key: str, lang: str) -> str:
    value = entry.get(key, {})
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "").strip()
    return str(value or "").strip()


def join_location(entry: dict[str, Any], lang: str, include_event: bool = False) -> str:
    keys: list[str] = []
    if include_event:
        keys.extend(["event", "institution"])
    else:
        keys.append("venue")
    keys.extend(["city", "country"])
    return ", ".join(filter(None, (localized(entry, key, lang) for key in keys)))


def build_article(soup: BeautifulSoup, entry: dict[str, Any], lang: str, upcoming: bool) -> Tag:
    article = soup.new_tag("article")
    article["class"] = ["timeline-item"]
    article[MANAGED_ATTR] = entry["id"]

    time_tag = soup.new_tag("time")
    time_tag.string = display_range(entry)
    article.append(time_tag)

    body = soup.new_tag("div")
    h3 = soup.new_tag("h3")
    kind = entry["kind"]

    if kind == "conference":
        add_link(soup, h3, localized(entry, "title", lang), entry.get("url"))
        description = join_location(entry, lang)
    elif kind == "talk":
        add_link(soup, h3, localized(entry, "title", lang), entry.get("url"))
        description = join_location(entry, lang, include_event=True)
    elif kind == "honor":
        add_link(soup, h3, localized(entry, "name", lang), entry.get("url"))
        description = localized(entry, "organization", lang)
    elif kind == "visit":
        add_link(soup, h3, localized(entry, "institution", lang), entry.get("url"))
        base = ", ".join(
            filter(None, [localized(entry, "city", lang), localized(entry, "country", lang)])
        )
        support = localized(entry, "support", lang)
        description = f"{base} · {support}" if base and support else (base or support)
    else:
        raise ValueError(f"Unknown kind: {kind}")

    body.append(h3)
    if description:
        p = soup.new_tag("p")
        p.string = description
        body.append(p)

    if kind == "talk" and entry.get("slides_url") and not upcoming:
        links = soup.new_tag("div")
        links["class"] = ["pub-links"]
        a = soup.new_tag(
            "a", href=entry["slides_url"], target="_blank", rel="noopener"
        )
        a.string = "投影片" if lang == "zh" else "Slides"
        links.append(a)
        body.append(links)

    article.append(body)
    return article


def find_section_timeline(soup: BeautifulSoup, heading: str) -> Tag:
    for h2 in soup.find_all("h2"):
        if h2.get_text(" ", strip=True).casefold() == heading.casefold():
            section = h2.find_parent("section")
            if section:
                timeline = section.find(class_="timeline")
                if isinstance(timeline, Tag):
                    return timeline
    raise RuntimeError(f"Cannot find section heading: {heading}")


def article_date(article: Tag) -> date:
    raw = article.find("time").get_text(strip=True) if article.find("time") else ""
    first = raw.split("–", 1)[0].strip()
    match = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", first)
    if match:
        return date(int(match[1]), int(match[2]), int(match[3]))
    year_match = re.search(r"\d{4}", first)
    return date(int(year_match.group()), 1, 1) if year_match else date.min


def sync_timeline(
    soup: BeautifulSoup,
    timeline: Tag,
    desired: Iterable[dict[str, Any]],
    lang: str,
    upcoming: bool,
    ascending: bool,
) -> bool:
    desired_list = list(desired)
    desired_ids = {entry["id"] for entry in desired_list}
    changed = False

    existing_managed = {
        article.get(MANAGED_ATTR): article
        for article in timeline.find_all("article", class_="timeline-item", recursive=False)
        if article.get(MANAGED_ATTR)
    }

    for entry_id, article in list(existing_managed.items()):
        if entry_id not in desired_ids:
            article.decompose()
            changed = True

    for entry in desired_list:
        new_article = build_article(soup, entry, lang, upcoming)
        old_article = timeline.find("article", attrs={MANAGED_ATTR: entry["id"]}, recursive=False)
        if old_article is None:
            timeline.append(new_article)
            changed = True
        elif str(old_article) != str(new_article):
            old_article.replace_with(new_article)
            changed = True

    articles = timeline.find_all("article", class_="timeline-item", recursive=False)
    sorted_articles = sorted(articles, key=article_date, reverse=not ascending)
    current_order = [id(article) for article in articles]
    desired_order = [id(article) for article in sorted_articles]
    if current_order != desired_order:
        for article in sorted_articles:
            timeline.append(article.extract())
        changed = True

    return changed


def update_footer(soup: BeautifulSoup, lang: str, today: date) -> None:
    footer = soup.find("footer", class_="site-footer")
    if not footer:
        return
    paragraphs = footer.find_all("p")
    if len(paragraphs) < 2:
        return
    stamp = f"{today.year}/{today.month}/{today.day}"
    paragraphs[-1].string = (
        f"最後更新：{stamp}" if lang == "zh" else f"Last updated: {stamp}"
    )


def sync_site(today: date | None = None) -> list[Path]:
    today = today or datetime.now().astimezone().date()
    data = load_data()
    entries = data.get("entries", [])
    changed_files: list[Path] = []

    for lang, cfg in PAGE_CONFIG.items():
        # Homepage Upcoming.
        path = cfg["index"]
        original = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(original, "html.parser")
        upcoming_timeline = soup.select_one(".home-upcoming .timeline")
        if not isinstance(upcoming_timeline, Tag):
            raise RuntimeError(f"Cannot find Upcoming timeline in {path}")
        active = sorted(
            (entry for entry in entries if should_be_upcoming(entry, today)),
            key=entry_start_key,
        )
        changed = sync_timeline(
            soup, upcoming_timeline, active, lang, upcoming=True, ascending=True
        )
        if changed:
            update_footer(soup, lang, today)
            path.write_text(str(soup), encoding="utf-8")
            changed_files.append(path)

        # Activities sections.
        path = cfg["activities"]
        original = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(original, "html.parser")
        changed = False
        for kind in ("conference", "talk", "visit"):
            timeline = find_section_timeline(soup, cfg["headings"][kind])
            desired = sorted(
                (
                    entry
                    for entry in entries
                    if entry["kind"] == kind and should_be_archived(entry, today)
                ),
                key=entry_start_key,
                reverse=True,
            )
            changed |= sync_timeline(
                soup, timeline, desired, lang, upcoming=False, ascending=False
            )
        if changed:
            update_footer(soup, lang, today)
            path.write_text(str(soup), encoding="utf-8")
            changed_files.append(path)

        # Honors section.
        path = cfg["cv"]
        original = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(original, "html.parser")
        timeline = find_section_timeline(soup, cfg["headings"]["honor"])
        desired = sorted(
            (entry for entry in entries if entry["kind"] == "honor"),
            key=entry_start_key,
            reverse=True,
        )
        changed = sync_timeline(
            soup, timeline, desired, lang, upcoming=False, ascending=False
        )
        if changed:
            update_footer(soup, lang, today)
            path.write_text(str(soup), encoding="utf-8")
            changed_files.append(path)

    return changed_files



def git_commit_and_push(message: str) -> None:
    if not (ROOT / ".git").exists():
        raise RuntimeError(
            "This folder is not a Git clone. The HTML files were updated locally, "
            "but automatic push requires cloning the repository first."
        )
    managed_paths = [
        "tools/content.json",
        "index.html",
        "zh/index.html",
        "activities.html",
        "zh/activities.html",
        "cv.html",
        "zh/cv.html",
    ]
    subprocess.run(["git", "add", *managed_paths], cwd=ROOT, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if diff.returncode == 0:
        return
    if diff.returncode != 1:
        raise RuntimeError("Could not inspect staged Git changes.")
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    subprocess.run(["git", "push"], cwd=ROOT, check=True)

def validate_entry(entry: dict[str, Any]) -> None:
    kind = entry["kind"]
    if kind == "honor":
        year = str(entry.get("year", ""))
        if not re.fullmatch(r"\d{4}", year):
            raise ValueError("Year must contain four digits.")
        for key in ("name", "organization"):
            if not localized(entry, key, "en") or not localized(entry, key, "zh"):
                raise ValueError(f"Both English and Chinese {key} are required.")
        return

    start = parse_iso(entry.get("start_date", ""), "Start date")
    end = parse_iso(entry.get("end_date") or entry.get("start_date", ""), "End date")
    if end < start:
        raise ValueError("End date cannot be earlier than start date.")

    required_by_kind = {
        "conference": ("title", "venue", "city", "country"),
        "talk": ("title", "event", "institution", "city", "country"),
        "visit": ("institution", "city", "country"),
    }
    for key in required_by_kind[kind]:
        if not localized(entry, key, "en") or not localized(entry, key, "zh"):
            raise ValueError(f"Both English and Chinese {key} are required.")


def launch_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    class Manager(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("HC Tsui Site Manager")
            self.geometry("820x820")
            self.minsize(720, 650)
            self.fields: dict[str, tk.StringVar] = {}
            self.kind_var = tk.StringVar(value="conference")
            self.upcoming_var = tk.BooleanVar(value=True)

            outer = ttk.Frame(self, padding=16)
            outer.pack(fill="both", expand=True)

            heading = ttk.Label(
                outer,
                text="Add website entry / 新增網站資料",
                font=("TkDefaultFont", 16, "bold"),
            )
            heading.pack(anchor="w", pady=(0, 12))

            row = ttk.Frame(outer)
            row.pack(fill="x", pady=(0, 8))
            ttk.Label(row, text="Record type / 類型", width=24).pack(side="left")
            combo = ttk.Combobox(
                row,
                state="readonly",
                textvariable=self.kind_var,
                values=list(KIND_LABELS.keys()),
            )
            combo.pack(side="left", fill="x", expand=True)
            combo.bind("<<ComboboxSelected>>", lambda _e: self.rebuild())

            self.upcoming_check = ttk.Checkbutton(
                outer,
                text="Show in Upcoming until the end date / 結束日前顯示於近期活動",
                variable=self.upcoming_var,
            )
            self.upcoming_check.pack(anchor="w", pady=(0, 10))

            canvas = tk.Canvas(outer, highlightthickness=0)
            scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
            self.form = ttk.Frame(canvas)
            self.form.bind(
                "<Configure>",
                lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
            )
            canvas.create_window((0, 0), window=self.form, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            canvas.bind_all(
                "<MouseWheel>",
                lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
            )

            buttons = ttk.Frame(self.form)
            buttons.grid(row=99, column=0, columnspan=2, sticky="ew", pady=(18, 6))
            ttk.Button(buttons, text="Save locally / 儲存到本機", command=self.save).pack(side="left")
            ttk.Button(buttons, text="Save + push / 儲存並上傳", command=self.save_and_push).pack(side="left", padx=8)
            ttk.Button(buttons, text="Sync now / 立即同步", command=self.sync_now).pack(side="left")
            ttk.Button(buttons, text="Delete entry / 刪除資料", command=self.delete_dialog).pack(side="left", padx=8)
            self.status = ttk.Label(self.form, text="")
            self.status.grid(row=100, column=0, columnspan=2, sticky="w")

            self.rebuild()

        def add_field(self, row: int, key: str, label: str, hint: str = "") -> None:
            ttk.Label(self.form, text=label, width=31).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            var = tk.StringVar()
            self.fields[key] = var
            entry = ttk.Entry(self.form, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            if hint:
                entry.insert(0, hint)
            self.form.columnconfigure(1, weight=1)

        def rebuild(self) -> None:
            for widget in self.form.winfo_children():
                info = widget.grid_info()
                if info and int(info.get("row", 0)) < 99:
                    widget.destroy()
            self.fields = {}
            kind = self.kind_var.get()
            self.upcoming_check.configure(state="disabled" if kind == "honor" else "normal")
            if kind == "honor":
                self.upcoming_var.set(False)

            defs: list[tuple[str, str, str]]
            if kind == "conference":
                defs = [
                    ("start_date", "Start date / 開始日期", "YYYY-MM-DD"),
                    ("end_date", "End date / 結束日期", "YYYY-MM-DD"),
                    ("title_en", "Conference name (EN)", ""),
                    ("title_zh", "會議名稱（中文）", ""),
                    ("url", "Conference URL / 會議連結", ""),
                    ("venue_en", "Venue (EN)", ""),
                    ("venue_zh", "地點（中文）", ""),
                    ("city_en", "City (EN)", ""),
                    ("city_zh", "城市（中文）", ""),
                    ("country_en", "Country (EN)", ""),
                    ("country_zh", "國家（中文）", ""),
                ]
            elif kind == "talk":
                defs = [
                    ("start_date", "Date / 日期", "YYYY-MM-DD"),
                    ("end_date", "End date (optional) / 結束日期", ""),
                    ("title_en", "Talk title (EN)", ""),
                    ("title_zh", "報告題目（中文）", ""),
                    ("event_en", "Event or seminar (EN)", ""),
                    ("event_zh", "會議或演講系列（中文）", ""),
                    ("institution_en", "Institution (EN)", ""),
                    ("institution_zh", "機構（中文）", ""),
                    ("city_en", "City (EN)", ""),
                    ("city_zh", "城市（中文）", ""),
                    ("country_en", "Country (EN)", ""),
                    ("country_zh", "國家（中文）", ""),
                    ("url", "Event URL / 活動連結", ""),
                    ("slides_url", "Slides URL / 投影片連結", ""),
                ]
            elif kind == "honor":
                defs = [
                    ("year", "Year / 年份", "YYYY"),
                    ("name_en", "Honor name (EN)", ""),
                    ("name_zh", "獎項名稱（中文）", ""),
                    ("organization_en", "Organization (EN)", ""),
                    ("organization_zh", "頒發或補助單位（中文）", ""),
                    ("url", "URL (optional) / 連結", ""),
                ]
            else:
                defs = [
                    ("start_date", "Start date / 開始日期", "YYYY-MM-DD"),
                    ("end_date", "End date / 結束日期", "YYYY-MM-DD"),
                    ("institution_en", "Institution (EN)", ""),
                    ("institution_zh", "機構（中文）", ""),
                    ("city_en", "City (EN)", ""),
                    ("city_zh", "城市（中文）", ""),
                    ("country_en", "Country (EN)", ""),
                    ("country_zh", "國家（中文）", ""),
                    ("support_en", "Support note (EN, optional)", ""),
                    ("support_zh", "補助說明（中文，可留空）", ""),
                    ("url", "Institution URL / 機構連結", ""),
                ]
            for i, (key, label, hint) in enumerate(defs):
                self.add_field(i, key, label, hint)

        def field(self, key: str) -> str:
            value = self.fields.get(key, tk.StringVar()).get().strip()
            return "" if value in {"YYYY", "YYYY-MM-DD"} else value

        def collect(self) -> dict[str, Any]:
            kind = self.kind_var.get()
            entry: dict[str, Any] = {
                "kind": kind,
                "show_upcoming": bool(self.upcoming_var.get()) if kind != "honor" else False,
            }
            if kind == "conference":
                entry.update({
                    "start_date": self.field("start_date"),
                    "end_date": self.field("end_date"),
                    "title": {"en": self.field("title_en"), "zh": self.field("title_zh")},
                    "url": self.field("url"),
                    "venue": {"en": self.field("venue_en"), "zh": self.field("venue_zh")},
                    "city": {"en": self.field("city_en"), "zh": self.field("city_zh")},
                    "country": {"en": self.field("country_en"), "zh": self.field("country_zh")},
                })
            elif kind == "talk":
                start = self.field("start_date")
                entry.update({
                    "start_date": start,
                    "end_date": self.field("end_date") or start,
                    "title": {"en": self.field("title_en"), "zh": self.field("title_zh")},
                    "event": {"en": self.field("event_en"), "zh": self.field("event_zh")},
                    "institution": {"en": self.field("institution_en"), "zh": self.field("institution_zh")},
                    "city": {"en": self.field("city_en"), "zh": self.field("city_zh")},
                    "country": {"en": self.field("country_en"), "zh": self.field("country_zh")},
                    "url": self.field("url"),
                    "slides_url": self.field("slides_url"),
                })
            elif kind == "honor":
                entry.update({
                    "year": self.field("year"),
                    "name": {"en": self.field("name_en"), "zh": self.field("name_zh")},
                    "organization": {"en": self.field("organization_en"), "zh": self.field("organization_zh")},
                    "url": self.field("url"),
                })
            else:
                entry.update({
                    "start_date": self.field("start_date"),
                    "end_date": self.field("end_date"),
                    "institution": {"en": self.field("institution_en"), "zh": self.field("institution_zh")},
                    "city": {"en": self.field("city_en"), "zh": self.field("city_zh")},
                    "country": {"en": self.field("country_en"), "zh": self.field("country_zh")},
                    "support": {"en": self.field("support_en"), "zh": self.field("support_zh")},
                    "url": self.field("url"),
                })
            validate_entry(entry)
            entry["id"] = make_id(entry)
            return entry

        def _save(self, push: bool) -> None:
            try:
                entry = self.collect()
                data = load_data()
                data.setdefault("entries", []).append(entry)
                save_data(data)
                changed = sync_site()
                if push:
                    title = localized(entry, "title", "en") or localized(entry, "name", "en") or localized(entry, "institution", "en")
                    git_commit_and_push(f"Add {entry['kind']}: {title}")
            except Exception as exc:  # GUI boundary
                messagebox.showerror("Cannot save", str(exc))
                return
            action = "saved and pushed" if push else "saved locally"
            self.status.configure(text=f"{action.capitalize()} {entry['id']}; updated {len(changed)} HTML file(s).")
            messagebox.showinfo("Saved", f"The entry was {action}; both language versions were updated.")

        def save(self) -> None:
            self._save(push=False)

        def save_and_push(self) -> None:
            self._save(push=True)

        def sync_now(self) -> None:
            try:
                changed = sync_site()
            except Exception as exc:
                messagebox.showerror("Sync failed", str(exc))
                return
            self.status.configure(text=f"Sync complete; updated {len(changed)} HTML file(s).")

        def delete_dialog(self) -> None:
            data = load_data()
            entries = data.get("entries", [])
            if not entries:
                messagebox.showinfo("No entries", "There are no managed entries.")
                return
            win = tk.Toplevel(self)
            win.title("Delete managed entry")
            win.geometry("760x380")
            tree = ttk.Treeview(win, columns=("kind", "date", "title"), show="headings")
            tree.heading("kind", text="Type")
            tree.heading("date", text="Date")
            tree.heading("title", text="Title")
            tree.column("kind", width=100)
            tree.column("date", width=130)
            tree.column("title", width=480)
            for entry in entries:
                title = localized(entry, "title", "en") or localized(entry, "name", "en") or localized(entry, "institution", "en")
                tree.insert("", "end", iid=entry["id"], values=(entry["kind"], display_range(entry), title))
            tree.pack(fill="both", expand=True, padx=12, pady=12)

            def delete_selected() -> None:
                selected = tree.selection()
                if not selected:
                    return
                entry_id = selected[0]
                if not messagebox.askyesno("Delete", f"Delete {entry_id}?"):
                    return
                current = load_data()
                current["entries"] = [e for e in current.get("entries", []) if e["id"] != entry_id]
                save_data(current)
                sync_site()
                win.destroy()
                self.status.configure(text=f"Deleted {entry_id}.")

            ttk.Button(win, text="Delete selected / 刪除選取項目", command=delete_selected).pack(pady=(0, 12))

    Manager().mainloop()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync", action="store_true", help="Synchronize HTML and roll over expired Upcoming entries")
    parser.add_argument("--today", help="Override today for testing, using YYYY-MM-DD")
    parser.add_argument("--list", action="store_true", help="List managed entries")
    args = parser.parse_args()

    if args.list:
        for entry in load_data().get("entries", []):
            print(entry["id"], entry["kind"], display_range(entry))
        return 0

    if args.sync:
        today = parse_iso(args.today, "Today") if args.today else None
        changed = sync_site(today)
        if changed:
            print("Updated:")
            for path in changed:
                print("-", path.relative_to(ROOT))
        else:
            print("No HTML changes were needed.")
        return 0

    launch_gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())

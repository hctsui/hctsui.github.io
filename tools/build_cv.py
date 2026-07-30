#!/usr/bin/env python3
"""Generate English and Traditional-Chinese LaTeX CVs from site.json."""
from __future__ import annotations
import argparse
import html as html_lib
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import process_request as core
from heading_config import heading_value

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"
TEMPLATES = {
    "en": ROOT / "cv" / "Hung-Chun-Tsui-CV.template.tex",
    "zh": ROOT / "cv" / "Hung-Chun-Tsui-CV-zh.template.tex",
}
OUTPUTS = {
    "en": ROOT / "cv" / "Hung-Chun-Tsui-CV.tex",
    "zh": ROOT / "cv" / "Hung-Chun-Tsui-CV-zh.tex",
}
LATEX_ESCAPES = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def load_data() -> dict[str, Any]:
    return core.migrate_data(json.loads(DATA_FILE.read_text(encoding="utf-8")))


def site_today(data: dict[str, Any], override: str | None = None) -> date:
    value = override or os.environ.get("SITE_TODAY", "")
    if value:
        return date.fromisoformat(value)
    return datetime.now(ZoneInfo(data.get("settings", {}).get("timezone", "Asia/Tokyo"))).date()


def latex_escape(value: Any) -> str:
    text = html_lib.unescape(str(value or "")).replace("\u00a0", " ").replace("–", "--").replace("—", "---").replace("−", "-")
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in text)


def latex_url(value: Any) -> str:
    return str(value or "").strip().replace("%", r"\%").replace("#", r"\#").replace("&", r"\&")


def rich_to_latex(value: Any, *, author: bool = False) -> str:
    source = html_lib.unescape(str(value or "")).replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    tokens: dict[str, str] = {}
    def token(content: str) -> str:
        key = f"@@CVTOKEN{len(tokens)}@@"; tokens[key] = content; return key
    def strong(match: re.Match[str]) -> str:
        inner = re.sub(r"<[^>]+>", "", match.group(1))
        return token(rf"\underline{{{latex_escape(inner)}}}" if author else rf"\textbf{{{latex_escape(inner)}}}")
    def emphasis(match: re.Match[str]) -> str:
        inner = re.sub(r"<[^>]+>", "", match.group(1)).strip(); escaped = latex_escape(inner)
        return token(rf"${escaped}$" if re.fullmatch(r"[A-Za-z0-9]+", inner) else rf"\textit{{{escaped}}}")
    source = re.sub(r"<(?:strong|b)>(.*?)</(?:strong|b)>", strong, source, flags=re.I|re.S)
    source = re.sub(r"<(?:em|i)>(.*?)</(?:em|i)>", emphasis, source, flags=re.I|re.S)
    source = re.sub(r"<[^>]+>", "", source)
    result = latex_escape(source)
    for key, replacement in tokens.items():
        result = result.replace(latex_escape(key), replacement)
    return result.strip()


def field_rich(entry: dict[str, Any], field: str, lang: str, *, author: bool = False) -> str:
    rich = entry.get(f"{field}_html", {})
    if isinstance(rich, dict) and rich.get(lang):
        return rich_to_latex(rich[lang], author=author)
    plain = entry.get(field, {})
    if isinstance(plain, dict):
        return latex_escape(plain.get(lang) or "")
    return latex_escape(plain)


def pair(entry: dict[str, Any], field: str, lang: str) -> str:
    value = entry.get(field)
    return str(value.get(lang) or "") if isinstance(value, dict) else str(value or "")


def display_date(value: str, lang: str) -> str:
    # Keep dates identical in the English and Chinese CVs.
    d = date.fromisoformat(value)
    return f"{d.year}/{d.month}/{d.day}"


def display_range(entry: dict[str, Any], lang: str) -> str:
    start = str(entry.get("start_date", "")); end = str(entry.get("end_date") or start)
    if not start: return latex_escape(entry.get("year", ""))
    if end == start: return display_date(start, lang)
    return f"{display_date(start, lang)} -- {display_date(end, lang)}"


def activity_is_upcoming(entry: dict[str, Any], today: date) -> bool:
    if not entry.get("show_upcoming"): return False
    end = str(entry.get("end_date") or entry.get("start_date") or "")
    return bool(end and date.fromisoformat(end) >= today)


def linked_bold(title: str, url: str) -> str:
    content = rf"\textbf{{{title}}}"
    return rf"\hrefWithoutArrow{{{latex_url(url)}}}{{{content}}}" if url and title else content


def render_activity(entry: dict[str, Any], lang: str, *, kind: str) -> str:
    title = field_rich(entry, "title", lang)
    url = str(entry.get("url", "")).strip()
    description = field_rich(entry, "description", lang)
    title_line = linked_bold(title, url)
    if kind == "talk" and entry.get("slides_url"):
        label = "投影片" if lang == "zh" else "slides"
        title_line += r" {\color{secondaryColor}[" + rf"\hrefWithoutArrow{{{latex_url(entry['slides_url'])}}}{{{label}}}" + "]}"
    if kind == "conference":
        role = field_rich(entry, "role", lang)
        if role:
            title_line += r" \quad {\color{secondaryColor}\textit{" + role + "}}"
    body = title_line
    if description:
        body += r"\\" + description
    return rf"\begin{{conf}}{{{display_range(entry, lang)}}}" + "\n" + body + "\n" + r"\end{conf}"


def render_organization(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, "title", lang)
    url = str(entry.get("url", "")).strip()
    description = field_rich(entry, "description", lang)
    kind = field_rich(entry, "organization_kind", lang)
    role = field_rich(entry, "role", lang)
    meta = " · ".join(value for value in (kind, role) if value)
    body = linked_bold(title, url)
    if meta:
        body += r"\\" + rf"\textit{{{meta}}}"
    if description:
        body += r"\\" + description
    return rf"\begin{{conf}}{{{display_range(entry, lang)}}}" + "\n" + body + "\n" + r"\end{conf}"


def cv_organization_section(data: dict[str, Any], entries: list[dict[str, Any]], lang: str) -> str:
    if not entries:
        return ""
    heading = latex_escape(heading_value(data, "activity_organization", "title", lang))
    rows = "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_organization(entry, lang) for entry in entries)
    return rf"\section{{{heading}}}" + "\n" + rows + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"


def publication_links(entry: dict[str, Any], lang: str) -> str:
    preferred = {"PDF":0,"arXiv":1,"Journal":2,"DOI":3,"Code":4}
    links = [x for x in entry.get("links", []) if x.get("url")]
    links.sort(key=lambda x: preferred.get((x.get("label") or {}).get("en", ""), 99))
    rendered=[]
    for link in links:
        labels=link.get("label") or {}; canonical=str(labels.get("en") or "Link")
        display = str(labels.get(lang) or "")
        if not display:
            display = {"PDF":"pdf","Journal":"journal","Code":"code"}.get(canonical, canonical)
        rendered.append(rf"\hrefWithoutArrow{{{latex_url(link['url'])}}}{{{latex_escape(display)}}}")
    return r" {\color{secondaryColor}[" + "|".join(rendered) + "]}" if rendered else ""


def publication_status(entry: dict[str, Any], lang: str) -> str:
    """Render only status text explicitly present in this language."""
    venue = pair(entry, "venue", lang).strip()
    year = str(entry.get("year", ""))
    if venue:
        return rf"\textit{{{latex_escape(venue)}}}, {latex_escape(year)}."
    return latex_escape(year) + "."


def render_publication(entry: dict[str, Any], number: int, lang: str) -> str:
    authors=field_rich(entry,"authors",lang,author=True); title=field_rich(entry,"title",lang)
    return rf"\begin{{pub}}{{{authors}}}" + "\n" + rf"{{[{number}]}} \textbf{{{title}}}{publication_links(entry,lang)} \\" + "\n" + publication_status(entry,lang) + "\n" + r"\end{pub}"


def render_honor(entry: dict[str, Any], lang: str) -> str:
    title=field_rich(entry,"title",lang); org=field_rich(entry,"organization",lang); body=linked_bold(title,str(entry.get("url","")).strip())
    if org: body += r"\\"+org
    return rf"\begin{{conf}}{{{latex_escape(entry.get('year',''))}}}"+"\n"+body+"\n"+r"\end{conf}"


def sorted_groups(data: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return sorted(core.content_groups(data,kind), key=lambda g:(int(g.get("order",999999)),str(g.get("id",""))))


def entries_for(data: dict[str, Any], kind: str, gid: str) -> list[dict[str, Any]]:
    section="publications" if kind=="publication" else "teaching"
    return sorted([x for x in data.get(section,[]) if x.get("group_id")==gid], key=lambda x:(int(x.get("order",999999)),str(x.get("id",""))))


def cv_publications(data: dict[str, Any], lang: str) -> str:
    chunks=[]
    for group in sorted_groups(data,"publication"):
        entries=entries_for(data,"publication",str(group.get("id")))
        if not entries: continue
        label=core.group_label(group,lang)
        heading = ""
        if label:
            heading="\\begin{one}\n"+f"    {{\\textbf{{\\large {latex_escape(label)}}}}}\n"+"\\end{one}\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
        # Numbering intentionally restarts inside every publication section.
        rows="\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_publication(entry,index,lang) for index,entry in enumerate(entries,1))
        chunks.append(heading+rows)
    return "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(chunks)


def cv_teaching(data: dict[str, Any], lang: str) -> str:
    chunks=[]
    for group in sorted_groups(data,"teaching"):
        entries=entries_for(data,"teaching",str(group.get("id")))
        if not entries: continue
        label=core.group_label(group,lang); heading=""
        if label:
            heading="\\begin{one}\n"+f"    {{\\textbf{{\\large {latex_escape(label)}}}}}\n"+"\\end{one}\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
        rows=[]
        for entry in entries:
            term=pair(entry,"term",lang); course=pair(entry,"course",lang); role=pair(entry,"role",lang)
            parts=[]
            if role: parts.append(rf"\textit{{{latex_escape(role)}}}")
            if course: parts.append(latex_escape(course))
            body=r"\quad ".join(parts)
            rows.append(f"\\begin{{conf}}{{{latex_escape(term)}}}\n{body}\n\\end{{conf}}")
        chunks.append(heading+"\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(rows))
    return "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(chunks)


def replace_block(text: str, marker: str, content: str) -> str:
    start=f"% CMS:{marker}:START"; end=f"% CMS:{marker}:END"
    pattern=re.compile(rf"({re.escape(start)}\n)(.*?)({re.escape(end)})",re.S)
    updated,count=pattern.subn(lambda m:m.group(1)+content.rstrip()+"\n"+m.group(3),text,count=1)
    if count!=1: raise RuntimeError(f"Missing or duplicated CV marker: {marker}")
    return updated


def ordered_ungrouped(data: dict[str, Any], kind: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids=data.get("settings",{}).get("entry_order",{}).get(kind,[])
    if isinstance(ids,list) and ids:
        rank={str(x):i for i,x in enumerate(ids)}
        return sorted(entries,key=lambda x:(rank.get(str(x.get("id")),999999),str(x.get("id",""))))
    if kind=="honor": return sorted(entries,key=lambda x:(-int(x.get("year",0)),int(x.get("order",999999)),str(x.get("id",""))))
    return sorted(entries,key=lambda x:(x.get("start_date",""),x.get("id","")),reverse=True)


def updated_text(today: date, lang: str) -> str:
    # Use the same Last updated date format in both CVs.
    months=["January","February","March","April","May","June","July","August","September","October","November","December"]
    return f"{months[today.month-1]} {today.day}, {today.year}"


def build_language(data: dict[str, Any], today: date, lang: str) -> Path:
    activities=data.get("activities",[]); archived=[x for x in activities if not activity_is_upcoming(x,today)]
    visits=ordered_ungrouped(data,"visit",[x for x in archived if x.get("type")=="visit"])
    talks=ordered_ungrouped(data,"talk",[x for x in archived if x.get("type")=="talk"])
    conferences=ordered_ungrouped(data,"conference",[x for x in archived if x.get("type")=="conference"])
    organization_only=ordered_ungrouped(data,"organization",[x for x in archived if x.get("type")=="organization"])
    organization_entries=sorted(
        organization_only+[x for x in conferences if x.get("show_in_organization")],
        key=lambda x:(x.get("start_date",""),x.get("id","")),
        reverse=True,
    )
    honors=ordered_ungrouped(data,"honor",list(data.get("honors",[])))
    blocks={
        "PUBLICATIONS":cv_publications(data,lang),
        "VISITS":"\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_activity(x,lang,kind="visit") for x in visits),
        "TALKS":"\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_activity(x,lang,kind="talk") for x in talks),
        "ORGANIZATION_SECTION":cv_organization_section(data,organization_entries,lang),
        "HONORS":"\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_honor(x,lang) for x in honors),
        "CONFERENCES":"\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_activity(x,lang,kind="conference") for x in conferences),
        "TEACHING":cv_teaching(data,lang),
    }
    text=TEMPLATES[lang].read_text(encoding="utf-8").replace("__CV_LAST_UPDATED__",updated_text(today,lang))
    heading_tokens={
        "__CV_RESEARCH__":heading_value(data,"cv_research","title",lang),
        "__CV_EDUCATION__":heading_value(data,"cv_education","title",lang),
        "__CV_PUBLICATIONS__":heading_value(data,"publications_page","title",lang),
        "__CV_VISITS__":heading_value(data,"activity_visit","title",lang),
        "__CV_TALKS__":heading_value(data,"activity_talk","title",lang),
        "__CV_HONORS__":heading_value(data,"cv_honors","title",lang),
        "__CV_CONFERENCES__":heading_value(data,"activity_conference","title",lang),
        "__CV_TEACHING__":heading_value(data,"teaching_page","title",lang),
        "__CV_PERSONAL__":heading_value(data,"cv_personal","title",lang),
    }
    for token,value in heading_tokens.items():
        text=text.replace(token,latex_escape(value))
    for marker,content in blocks.items(): text=replace_block(text,marker,content)
    OUTPUTS[lang].write_text(text,encoding="utf-8")
    return OUTPUTS[lang]


def build(today: date) -> list[Path]:
    data=load_data()
    return [build_language(data,today,lang) for lang in ("en","zh")]


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--today"); args=parser.parse_args()
    data=load_data(); outputs=build(site_today(data,args.today))
    for output in outputs: print(f"Generated {output.relative_to(ROOT)}")


if __name__=="__main__": main()

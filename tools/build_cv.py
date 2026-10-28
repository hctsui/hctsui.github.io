#!/usr/bin/env python3
"""Build the two academic CVs from the live bilingual CMS categories.

English: pdflatex; Chinese: xelatex.  Content is never duplicated in templates.
The legacy render_publication/render_education interfaces are retained for
existing repository tests and site_fixes.patch_build_cv.
"""
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
from category_config import (
    category_map, items_for_category, migrate_category_data,
    normalized_cv_order, normalized_pages,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'content/site.json'
TEMPLATES = {
    'en': ROOT / 'cv/Hung-Chun-Tsui-CV.template.tex',
    'zh': ROOT / 'cv/Hung-Chun-Tsui-CV-zh.template.tex',
}
OUTPUTS = {
    'en': ROOT / 'cv/Hung-Chun-Tsui-CV.tex',
    'zh': ROOT / 'cv/Hung-Chun-Tsui-CV-zh.tex',
}
LATEX_ESCAPES = {
    '\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
    '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
}


def load_data() -> dict[str, Any]:
    return migrate_category_data(core.migrate_data(json.loads(DATA_FILE.read_text(encoding='utf-8'))))


def site_today(data: dict[str, Any], override: str | None = None) -> date:
    value = override or os.environ.get('SITE_TODAY', '')
    if value:
        return date.fromisoformat(value)
    return datetime.now(ZoneInfo(data.get('settings', {}).get('timezone', 'Asia/Tokyo'))).date()


def latex_escape(value: Any) -> str:
    text = core.strip_invisible_chars(html_lib.unescape(str(value or '')))
    text = text.replace('\u00a0', ' ').replace('–', '--').replace('—', '---').replace('−', '-')
    return ''.join(LATEX_ESCAPES.get(ch, ch) for ch in text)


def latex_url(value: Any) -> str:
    return str(core.strip_invisible_chars(str(value or ''))).strip().replace('%', r'\%').replace('#', r'\#').replace('&', r'\&')


def rich_to_latex(value: Any, *, author: bool = False, auto_math: bool = False) -> str:
    """Preserve inline $...$, [i]/[b], and simple HTML while escaping text."""
    source = str(core.strip_invisible_chars(html_lib.unescape(str(value or ''))))
    source = re.sub(r'<br\s*/?>', ' ', source, flags=re.I)
    tokens: dict[str, str] = {}

    def token(content: str) -> str:
        key = f'@@CVTOKEN{len(tokens)}@@'
        tokens[key] = content
        return key

    def math_token(match: re.Match[str]) -> str:
        return token('$' + match.group(1).strip() + '$')

    source = re.sub(r'\$([^$\n]+)\$', math_token, source)
    source = re.sub(r'\\\((.+?)\\\)', math_token, source)
    if auto_math and re.search(r'[\u3400-\u9fff]', source):
        source = re.sub(r'(?<![A-Za-z])zeta(?![A-Za-z])', lambda _: token(r'$\zeta$'), source, flags=re.I)
        source = re.sub(r'(?<![A-Za-z])Gamma(?![A-Za-z])', lambda _: token(r'$\Gamma$'), source)
        source = re.sub(r'(?<![A-Za-z])([qtuvL])(?=(?:-|\s|、|，|。|／|$))', lambda m: token('$' + m.group(1) + '$'), source)

    def strong(match: re.Match[str]) -> str:
        inner = re.sub(r'<[^>]+>', '', match.group(1))
        return token((r'\underline{' if author else r'\textbf{') + latex_escape(inner) + '}')

    def emphasis(match: re.Match[str]) -> str:
        inner = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        return token('$' + latex_escape(inner) + '$' if re.fullmatch(r'[A-Za-z0-9_+\-]+', inner)
                     else r'\textit{' + latex_escape(inner) + '}')

    source = re.sub(r'<(?:strong|b)>(.*?)</(?:strong|b)>', strong, source, flags=re.I | re.S)
    source = re.sub(r'<(?:em|i)>(.*?)</(?:em|i)>', emphasis, source, flags=re.I | re.S)
    source = re.sub(r'\[b\](.*?)\[/b\]', strong, source, flags=re.I | re.S)
    source = re.sub(r'\[i\](.*?)\[/i\]', emphasis, source, flags=re.I | re.S)
    source = re.sub(r'<[^>]+>', '', source)
    result = latex_escape(source)
    for key, replacement in tokens.items():
        result = result.replace(latex_escape(key), replacement)
    return result.strip()


def pair(entry: dict[str, Any], field: str, lang: str) -> str:
    value = entry.get(field)
    return str(value.get(lang) or value.get('en') or value.get('zh') or '') if isinstance(value, dict) else str(value or '')


def field_rich(entry: dict[str, Any], field: str, lang: str, *, author: bool = False) -> str:
    rich = entry.get(field + '_html', {})
    plain = entry.get(field, {})
    if isinstance(rich, dict) and 'data-tex-inline' in str(rich.get(lang) or '') and isinstance(plain, dict) and '$' in str(plain.get(lang) or ''):
        return rich_to_latex(plain[lang], author=author, auto_math=lang == 'zh')
    if isinstance(rich, dict) and rich.get(lang):
        return rich_to_latex(rich[lang], author=author, auto_math=lang == 'zh')
    return rich_to_latex(pair(entry, field, lang), author=author, auto_math=lang == 'zh')


def display_date(value: str) -> str:
    d = date.fromisoformat(value)
    return f'{d.year}/{d.month}/{d.day}'


def display_range(entry: dict[str, Any], lang: str) -> str:
    # Respect the CMS's explicitly authored dates first.
    explicit = pair(entry, 'date_label', lang).strip()
    if explicit:
        return latex_escape(explicit)
    start = str(entry.get('start_date') or '')
    end = str(entry.get('end_date') or start)
    if not start:
        return latex_escape(entry.get('year', ''))
    if not end or end == start:
        return display_date(start)
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    # Compact ranges keep the date column readable even for multi-day events.
    if first.year == last.year:
        return f'{first.year}/{first.month}/{first.day}--{last.month}/{last.day}'
    return f'{display_date(start)}--{display_date(end)}'


def linked_bold(title: str, url: str) -> str:
    content = r'\textbf{' + title + '}'
    return r'\href{' + latex_url(url) + '}{' + content + '}' if url and title else content


def cv_link(url: str, label: str) -> str:
    return r'\cvlink{' + latex_url(url) + '}{' + latex_escape(label) + '}'


def activity_finished(entry: dict[str, Any], today: date) -> bool:
    if entry.get('type') not in {'visit', 'talk', 'conference', 'organization'}:
        return True
    end = str(entry.get('end_date') or entry.get('start_date') or '')
    try:
        return not end or date.fromisoformat(end) < today
    except ValueError:
        return True


def cv_items_for_category(data: dict[str, Any], category: dict[str, Any], today: date) -> list[dict[str, Any]]:
    return [item for item in items_for_category(data, category['id']) if activity_finished(item, today)]


# Modern renderers -- match the two user-selected templates exactly.
def render_interest_modern(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, 'title', lang)
    description = field_rich(entry, 'description', lang)
    return title + (', ' + description if description else '')


def render_education_modern(entry: dict[str, Any], lang: str) -> str:
    return (r'\cvedu{' + display_range(entry, lang) + '}{' + field_rich(entry, 'title', lang)
            + '}{' + field_rich(entry, 'organization', lang) + '}{' + field_rich(entry, 'description', lang) + '}')


def render_activity_modern(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, 'title', lang)
    url = str(entry.get('url') or '').strip()
    if url:
        title = r'\href{' + latex_url(url) + '}{' + title + '}'
    # Slides appear IMMEDIATELY after the talk title, not on the location line.
    if entry.get('type') == 'talk' and entry.get('slides_url'):
        title += cv_link(str(entry['slides_url']), 'Slides')
    role = field_rich(entry, 'role', lang)
    if entry.get('type') == 'conference' and role and role.casefold() != 'participant' and role != '一般參與者':
        title += r' {\normalfont\color{cvAccentDark}(' + role + ')}'
    detail = field_rich(entry, 'description', lang)
    return r'\cvdated{' + display_range(entry, lang) + '}{' + title + '}{' + detail + '}'


def render_honor_modern(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, 'title', lang)
    url = str(entry.get('url') or '')
    if url:
        title = r'\href{' + latex_url(url) + '}{' + title + '}'
    return (r'\cvdated{' + latex_escape(entry.get('year', '')) + '}{' + title
            + '}{' + field_rich(entry, 'organization', lang) + '}')


def render_teaching_modern(entry: dict[str, Any], lang: str) -> str:
    # The course's role is managed by the CMS rather than hardcoded.
    role = field_rich(entry, 'role', lang) or ('助教' if lang == 'zh' else 'Teaching Assistant')
    return (r'\cvteaching{' + field_rich(entry, 'term', lang) + '}{'
            + field_rich(entry, 'course', lang) + '}{' + role + '}')


def publication_links_modern(entry: dict[str, Any], lang: str) -> str:
    priority = {'journal': 0, 'arxiv': 1, 'pdf': 2, 'code': 3}
    links = [x for x in entry.get('links', []) if x.get('url') and str((x.get('label') or {}).get('en', '')).casefold() != 'doi']
    links.sort(key=lambda x: priority.get(str((x.get('label') or {}).get('en') or '').casefold(), 99))
    return ''.join(cv_link(str(x['url']), str((x.get('label') or {}).get('en') or 'Link').replace('arXiv', 'ArXiv')) for x in links)


def bold_author(entry: dict[str, Any], lang: str) -> str:
    names = pair(entry, 'authors', lang)
    # Preserve the site's exact author list while emphasizing only the CV owner.
    if lang == 'zh':
        names = names.replace('崔鴻竣', '[[CVOWNER]]')
    else:
        names = names.replace('Hung-Chun Tsui', '[[CVOWNER]]')
    result = rich_to_latex(names)
    return result.replace('[[CVOWNER]]', r'\textbf{' + ('崔鴻竣' if lang == 'zh' else 'Hung-Chun Tsui') + '}')


def render_publication_modern(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, 'title', lang)
    authors = bold_author(entry, lang)
    year = str(entry.get('year') or '')
    published = entry.get('publication_state') == 'published' or str(entry.get('group_id') or '') == 'journal-articles'
    if published:
        title_part = "``" + title + ",''" if lang == "en" else "「" + title + "」"
        # Keep the journal citation maintained in CMS (including volume, issue, article number).
        venue = field_rich(entry, 'venue', lang)
        # Convert CMS bold journal title to italic, as in the user-selected sample.
        venue = re.sub(r'\\textbf\{([^{}]+)\}', lambda m: r'\emph{' + m.group(1) + '}', venue)
        citation = (', ' + venue.rstrip(' .。') + '.' if venue else (', ' + year + '.' if year else '.'))
    else:
        title_part = r'\emph{' + title + '}'
        citation = ', ' + year + '.' if year else '.'
    return r'\item ' + authors + ', ' + title_part + citation + publication_links_modern(entry, lang)


def render_organization_modern(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, 'title', lang)
    if entry.get('url'):
        title = r'\href{' + latex_url(entry['url']) + '}{' + title + '}'
    meta = ' · '.join(x for x in (field_rich(entry, 'organization_kind', lang), field_rich(entry, 'role', lang)) if x)
    detail = (meta + '. ' if meta else '') + field_rich(entry, 'description', lang)
    return r'\cvdated{' + display_range(entry, lang) + '}{' + title + '}{' + detail + '}'


def render_personal_modern(items: list[dict[str, Any]], lang: str) -> str:
    rows = []
    for item in items:
        title = field_rich(item, 'title', lang)
        val = field_rich(item, 'description', lang)
        url = str(item.get('url') or '').strip()
        if url:
            val = r'\href{' + latex_url(url) + '}{' + val + '}'
        rows.append(r'\textbf{' + title + '} & ' + val + r' \\')
    return (r'\renewcommand{\arraystretch}{1.15}' + '\n'
            + r'\begin{tabularx}{\linewidth}{@{}p{2.8cm}@{\hspace{.30cm}}>{\raggedright\arraybackslash}X@{}}'
            + '\n' + '\n'.join(rows) + '\n' + r'\end{tabularx}')


def render_generic_modern(entry: dict[str, Any], lang: str) -> str:
    return render_activity_modern(entry, lang)


# Compatibility APIs for the repository's existing unit tests and site_fixes.
def publication_links(entry: dict[str, Any], lang: str) -> str:
    links = [x for x in entry.get('links', []) if x.get('url')]
    return r'{\small\color{secondaryColor}[' + ' | '.join(
        r'\hrefWithoutArrow{' + latex_url(x['url']) + '}{' + latex_escape((x.get('label') or {}).get(lang) or (x.get('label') or {}).get('en') or 'Link') + '}'
        for x in links) + ']}' if links else ''


def render_publication(entry: dict[str, Any], number: int, lang: str) -> str:
    title = field_rich(entry, 'title', lang)
    authors = field_rich(entry, 'authors', lang, author=True)
    links = publication_links(entry, lang)
    venue = pair(entry, 'venue', lang).strip()
    year = str(entry.get('year') or '')
    lines = ['{(' + str(number) + ')} ' + r'\textbf{' + title + '}']
    if links:
        lines.append(links)
    if venue or year:
        lines.append((r'\textit{' + rich_to_latex(venue) + '}, ' if venue else '') + latex_escape(year) + '.')
    return r'\begin{pub}{' + authors + '}' + '\n' + r'\\'.join(lines) + '\n' + r'\end{pub}'


def render_education(entry: dict[str, Any], lang: str) -> str:
    return (r'\begin{edu}{\textbf{' + field_rich(entry, 'title', lang) + '}}{'
            + display_range(entry, lang) + '}' + '\n' + field_rich(entry, 'organization', lang)
            + '\n' + r'\end{edu}')


def render_category_rows(data: dict[str, Any], category: dict[str, Any], lang: str,
                         today: date, publication_start: int = 1) -> tuple[list[str], int]:
    items = cv_items_for_category(data, category, today)
    if not items:
        return [], publication_start
    kind = category['kind']
    if kind == 'publication':
        rows = [render_publication_modern(x, lang) for x in items]
        return rows, publication_start + len(rows)
    if kind == 'teaching':
        return [render_teaching_modern(x, lang) for x in items], publication_start
    if kind == 'interest':
        return [render_interest_modern(x, lang) for x in items], publication_start
    if kind == 'education':
        return [render_education_modern(x, lang) for x in items], publication_start
    if kind in {'visit', 'talk', 'conference'}:
        return [render_activity_modern(x, lang) for x in items], publication_start
    if kind == 'organization':
        return [render_organization_modern(x, lang) for x in items], publication_start
    if kind == 'honor':
        return [render_honor_modern(x, lang) for x in items], publication_start
    if kind == 'personal':
        return [render_personal_modern(items, lang)], publication_start
    return [render_generic_modern(x, lang) for x in items], publication_start


def render_category(data: dict[str, Any], category: dict[str, Any], lang: str,
                    today: date | None = None) -> str:
    today = today or site_today(data)
    rows, _ = render_category_rows(data, category, lang, today)
    if not rows:
        return ''
    title = rich_to_latex((category.get('title') or {}).get(lang, ''), auto_math=lang == 'zh')
    if category['kind'] == 'interest':
        body = '; '.join(rows) + '.' if lang == 'en' else '；'.join(rows) + '。'
    else:
        body = '\n'.join(rows)
    return r'\section{' + title + '}' + '\n' + body


def page_heading(data: dict[str, Any], page_id: str, lang: str) -> str:
    page = next((p for p in normalized_pages(data) if p['id'] == page_id), None)
    value = (page.get('header') or {}).get('title', {}).get(lang, '') if page else ''
    return rich_to_latex(value, auto_math=lang == 'zh')


def render_grouped_categories(data: dict[str, Any], categories: list[dict[str, Any]], lang: str,
                              today: date) -> str:
    if not categories:
        return ''
    title = page_heading(data, str(categories[0].get('page_id') or ''), lang)
    groups = []
    for c in categories:
        rows, _ = render_category_rows(data, c, lang, today, 1)
        if not rows:
            continue
        subtitle = rich_to_latex((c.get('title') or {}).get(lang, ''), auto_math=lang == 'zh')
        if c['kind'] == 'publication':
            content = r'\begin{cvpubs}' + '\n' + '\n'.join(rows) + '\n' + r'\end{cvpubs}'
        else:
            content = '\n'.join(rows)
        groups.append(r'\cvgroup{' + subtitle + '}' + '\n' + content)
    return (r'\section{' + title + '}' + '\n' + '\n'.join(groups)) if groups else ''


def build_sections(data: dict[str, Any], lang: str, today: date | None = None) -> str:
    today = today or site_today(data)
    cmap = category_map(data)
    ordered = [cmap[cid] for cid in normalized_cv_order(data)
               if cid in cmap and cmap[cid].get('show_on_cv')]
    chunks: list[str] = []
    consumed: set[str] = set()
    for category in ordered:
        if category['id'] in consumed:
            continue
        if category['kind'] in {'publication', 'teaching'}:
            grouped = [c for c in ordered if c['kind'] == category['kind']]
            consumed.update(c['id'] for c in grouped)
            rendered = render_grouped_categories(data, grouped, lang, today)
        else:
            consumed.add(category['id'])
            rendered = render_category(data, category, lang, today)
        if rendered:
            chunks.append(rendered)
    return '\n\n'.join(chunks)


def build(lang: str, today: date, data: dict[str, Any] | None = None) -> Path:
    data = data or load_data()
    template = TEMPLATES[lang].read_text(encoding='utf-8')
    if template.count('__CV_SECTIONS__') != 1:
        raise RuntimeError(f'Template must have exactly one __CV_SECTIONS__: {TEMPLATES[lang]}')
    text = template.replace('__CV_SECTIONS__', build_sections(data, lang, today))
    text = text.replace('__CV_LAST_UPDATED__', f'{today.year}/{today.month}/{today.day}')
    OUTPUTS[lang].write_text(core.strip_invisible_chars(text), encoding='utf-8')
    return OUTPUTS[lang]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--today')
    args = parser.parse_args()
    data = load_data()
    today = site_today(data, args.today)
    for lang in ('en', 'zh'):
        print('Generated', build(lang, today, data).relative_to(ROOT))


if __name__ == '__main__':
    main()

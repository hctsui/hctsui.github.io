#!/usr/bin/env python3
"""Generate a readable entry-ID catalog for edit/remove forms."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'content/site.json').read_text(encoding='utf-8'))
lines=[
'# Website content catalog / 網站內容目錄','',
'這個檔案由程式自動產生。需要編輯或刪除項目時，複製最右欄的 `Entry ID`。','',
]
def table(title,rows):
    lines.extend([f'## {title}','', '| Date / Year | English title | 中文名稱 | Entry ID |','|---|---|---|---|'])
    for d,en,zh,i in rows:
        def clean(x): return str(x).replace('|','\\|').replace('\n',' ')
        lines.append(f'| {clean(d)} | {clean(en)} | {clean(zh)} | `{clean(i)}` |')
    lines.append('')
acts=sorted(data.get('activities',[]),key=lambda x:x.get('start_date',''),reverse=True)
table('Activities / 學術活動',[(f"{x.get('start_date','')} – {x.get('end_date','')}",x.get('title',{}).get('en',''),x.get('title',{}).get('zh',''),x['id']) for x in acts])
hon=sorted(data.get('honors',[]),key=lambda x:(-int(x.get('year',0)),int(x.get('order',0))))
table('Honors / 獎項',[(x.get('year',''),x.get('title',{}).get('en',''),x.get('title',{}).get('zh',''),x['id']) for x in hon])
pubs=sorted(data.get('publications',[]),key=lambda x:x.get('date',''),reverse=True)
table('Publications / 論文',[(x.get('date',''),x.get('title',{}).get('en',''),x.get('title',{}).get('zh',''),x['id']) for x in pubs])
teach=sorted(data.get('teaching',[]),key=lambda x:int(x.get('order',0)))
table('Teaching / 教學',[(x.get('term',{}).get('en',''),x.get('course',{}).get('en',''),x.get('course',{}).get('zh',''),x['id']) for x in teach])
(ROOT/'CONTENT-CATALOG.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

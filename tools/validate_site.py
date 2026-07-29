#!/usr/bin/env python3
"""Validate database IDs, dates, required markers, and bilingual fields."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'content/site.json').read_text(encoding='utf-8'))
errors=[]
ids=[]
for section in ('activities','honors','publications','teaching'):
    if not isinstance(data.get(section),list): errors.append(f'{section} must be a list'); continue
    for item in data[section]:
        eid=item.get('id','')
        if not eid: errors.append(f'{section}: missing id')
        ids.append(eid)
        if section in ('activities','honors','publications'):
            field='title'
        else:
            field='course'
        value=item.get(field,{})
        if not value.get('en') or not value.get('zh'):
            errors.append(f'{eid}: missing bilingual {field}')
        if section=='activities':
            try:
                start=date.fromisoformat(item['start_date']); end=date.fromisoformat(item.get('end_date') or item['start_date'])
                if end<start: errors.append(f'{eid}: end date before start date')
            except Exception: errors.append(f'{eid}: invalid activity date')
        if section=='publications':
            try: date.fromisoformat(item['date'])
            except Exception: errors.append(f'{eid}: invalid publication date')
if len(ids)!=len(set(ids)): errors.append('Entry IDs are not unique')
markers={
 'index.html':['HOME_PUBLICATIONS','UPCOMING'], 'zh/index.html':['HOME_PUBLICATIONS','UPCOMING'],
 'activities.html':['VISITS','TALKS','CONFERENCES'], 'zh/activities.html':['VISITS','TALKS','CONFERENCES'],
 'cv.html':['HONORS'], 'zh/cv.html':['HONORS'],
 'publications.html':['PUBLICATIONS'], 'zh/publications.html':['PUBLICATIONS'],
 'teaching.html':['TEACHING'], 'zh/teaching.html':['TEACHING'],
}
for rel,names in markers.items():
    text=(ROOT/rel).read_text(encoding='utf-8')
    for name in names:
        if text.count(f'<!-- CMS:{name}:START -->')!=1 or text.count(f'<!-- CMS:{name}:END -->')!=1:
            errors.append(f'{rel}: invalid marker {name}')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'Validated {len(ids)} entries and {len(markers)} pages.')

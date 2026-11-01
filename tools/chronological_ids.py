"""Canonical chronological order in the CMS; record IDs stay permanent.

Loaded once from repository sitecustomize.py after other CMS extensions.
"""
from __future__ import annotations
import re
from typing import Any

AUTO_KINDS = frozenset({'teaching','publication','conference','talk','visit','organization','honor'})
UNGROUPED = frozenset({'conference','talk','visit','organization','honor'})
SECTIONS = ('activities','honors','publications','teaching','profile_items')
_INSTALLED = False

def all_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [x for name in SECTIONS for x in data.get(name,[]) if isinstance(x,dict)]

def date_key(x: dict[str, Any]) -> str:
    kind=str(x.get('type') or '')
    if kind=='teaching':
        term=x.get('term') or {}
        label=(' '.join(str(term.get(lang) or '') for lang in ('en','zh'))
               if isinstance(term,dict) else str(term))
        year=re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)',label)
        season=next((n for n,pat in [('03',r'spring|春'),('06',r'summer|夏'),('09',r'fall|autumn|秋'),('12',r'winter|冬')]
                     if re.search(pat,label,re.I)),'01')
        return f'{year.group(1) if year else "0000"}-{season}-01'
    if kind=='honor':return f'{int(x.get("year") or 0):04d}-01-01'
    return str(x.get('date') or x.get('start_date') or '')[:10]

def chronological_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    original=sorted(records,key=lambda x:(int(x.get('order',999999)),str(x.get('_source_id') or x.get('id') or '')))
    return sorted(original,key=date_key,reverse=True)

def sync_orders(data: dict[str, Any]) -> None:
    settings=data.setdefault('settings',{})
    manual=set(settings.get('manually_ordered_kinds') or [])
    records=all_records(data)
    for category in settings.get('categories') or []:
        kind,cid=category.get('kind'),category.get('id')
        if kind not in AUTO_KINDS or kind in manual:continue
        for i,x in enumerate(chronological_items([x for x in records if x.get('type')==kind and x.get('category_id')==cid])):
            x['order']=i
    orders=settings.setdefault('entry_order',{})
    for kind in UNGROUPED-manual:
        orders[kind]=[x['id'] for x in chronological_items([x for x in records if x.get('type')==kind])]

def set_mode(data: dict[str, Any],kind:str,mode:str)->None:
    if kind not in AUTO_KINDS:return
    settings=data.setdefault('settings',{})
    manual=set(settings.get('manually_ordered_kinds') or [])
    if mode=='auto':manual.discard(kind)
    elif mode=='manual':manual.add(kind)
    else:raise ValueError('Unrecognized order mode: '+str(mode))
    settings['manually_ordered_kinds']=sorted(manual)
    if mode=='auto':sync_orders(data)

def install()->None:
    global _INSTALLED
    if _INSTALLED:return
    import category_config as category
    old_migrate=category.migrate_category_data
    old_items=category.items_for_category
    def migrate_category_data(data):
        result=old_migrate(data)
        sync_orders(result)
        return result
    def items_for_category(data,cid):
        items=old_items(data,cid)
        kinds={str(x.get('type') or '') for x in items}
        if len(kinds)!=1:return items
        kind=next(iter(kinds))
        if kind in AUTO_KINDS and kind not in set(data.get('settings',{}).get('manually_ordered_kinds') or []):
            return chronological_items(items)
        return items
    category.migrate_category_data=migrate_category_data
    category.items_for_category=items_for_category

    # Legacy Issue Forms are still accepted by the repository.
    import process_request as form
    original_form_process=form.process
    def process(title, fields, data):
        outcome=original_form_process(title,fields,data)
        sync_orders(data)
        return outcome
    form.process=process

    # Only load the batch processor when the actual batch command is executed.
    # Building a page or running unrelated tests must not preload its heavy
    # dependencies. All operations still sort via the migrated category model.
    import sys
    from pathlib import Path
    if Path(sys.argv[0]).name in {'run_process_batch_request.py','process_batch_request.py'}:
        import process_batch_request as batch
        old_special=batch.apply_special
        def apply_special(data, translations, history, op, *args, **kwargs):
            if op.get('op')!='reorder':
                return old_special(data,translations,history,op,*args,**kwargs)
            mode=str((op.get('after') or {}).get('sort_mode') or 'manual')
            if mode not in {'auto','manual'}:raise ValueError('Invalid sort mode: '+mode)
            outcome=old_special(data,translations,history,op,*args,**kwargs)
            set_mode(data,str(op.get('type') or ''),mode)
            return outcome
        batch.apply_special=apply_special
    _INSTALLED=True

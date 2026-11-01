"""Immutable typed CMS IDs, durable counters, and all-reference ID renames.

Loaded from sitecustomize, after category/profile/chronological extensions. No
repository write is performed until batch validation succeeds. Batch operations
are applied in memory by the existing processor and persisted in one Git commit.
"""
from __future__ import annotations
import copy
import re
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

SECTIONS=('activities','honors','publications','teaching','profile_items')
KINDS=('publication','teaching','visit','honor','talk','conference','organization','interest','education','contact','personal','generic')
ID_PATTERN=re.compile(r'^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$')
COUNTRY_NUMERIC={'Taiwan':'158','臺灣':'158','台灣':'158','Japan':'392','日本':'392'}
ISO_COUNTRY_CODES=frozenset('004 008 010 012 016 020 024 028 031 032 036 040 044 048 050 051 052 056 060 064 068 070 072 074 076 084 086 090 092 096 100 104 108 112 116 120 124 132 136 140 144 148 152 156 158 162 166 170 174 175 178 180 184 188 191 192 196 203 204 208 212 214 218 222 226 231 232 233 234 238 239 242 246 248 250 254 258 260 262 266 268 270 275 276 288 292 296 300 304 308 312 316 320 324 328 332 334 336 340 344 348 352 356 360 364 368 372 376 380 384 388 392 398 400 404 408 410 414 417 418 422 426 428 430 434 438 440 442 446 450 454 458 462 466 470 474 478 480 484 492 496 498 499 500 504 508 512 516 520 524 528 531 533 534 535 540 548 554 558 562 566 570 574 578 580 581 583 584 585 586 591 598 600 604 608 612 616 620 624 626 630 634 638 642 643 646 652 654 659 660 662 663 666 670 674 678 682 686 688 690 694 702 703 704 705 706 710 716 724 728 729 732 740 744 748 752 756 760 762 764 768 772 776 780 784 788 792 795 796 798 800 804 807 818 826 831 832 833 834 840 850 854 858 860 862 876 882 887 894'.split())
_INSTALLED=False

def current_year():
    return str(datetime.now(ZoneInfo('Asia/Taipei')).year)


def all_items(data):
    return [row for name in SECTIONS for row in data.get(name,[]) if isinstance(row,dict) and row.get('id')]


def term_parts(entry):
    term=entry.get('term') or {}
    text=' '.join(str(term.get(k) or '') for k in ('en','zh')) if isinstance(term,dict) else str(term)
    match=re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)',text)
    year=match.group(1) if match else current_year()
    season=next((code for regex,code in [(r'spring|春','01'),(r'summer|夏','02'),(r'fall|autumn|秋','03'),(r'winter|冬','04')] if re.search(regex,text,re.I)),'05')
    return year[-2:],season


def event_date(entry):
    raw=str(entry.get('start_date') or entry.get('date') or '')
    return raw if re.fullmatch(r'\d{4}-\d{2}-\d{2}',raw) else datetime.now(ZoneInfo('Asia/Taipei')).date().isoformat()


def country_numeric(entry):
    value=str(entry.get('country_numeric') or '').strip()
    if value:
        if value in ISO_COUNTRY_CODES:return value
        raise ValueError('The ISO 3166-1 numeric country code must be valid (e.g., 158 or 392)')
    org=entry.get('organization') or {}
    name=' '.join(str(org.get(k) or '') for k in ('en','zh')) if isinstance(org,dict) else str(org)
    # Historical bilateral award is administered by a Japanese organization.
    if 'Japan–Taiwan' in name or '日本台灣交流協會' in name:return '392'
    return '158'


def counter_for_id(kind,identifier):
    if not isinstance(identifier,str) or not identifier.startswith(kind+'-'):return 0
    tail=identifier[len(kind)+1:]
    if kind=='teaching' and re.fullmatch(r'\d{7}',tail):return int(tail[4:])
    if kind in ('publication','visit') and re.fullmatch(r'\d{7}',tail):return int(tail[-3:])
    if kind=='honor' and re.fullmatch(r'\d{8}',tail):return int(tail[-3:])
    if kind in ('talk','conference') and re.fullmatch(r'\d{7,}',tail):return 0
    if re.fullmatch(r'\d{7}',tail):return int(tail[-5:])
    return 0


def ensure_counters(data):
    settings=data.setdefault('settings',{})
    stored=settings.get('id_counters')
    if not isinstance(stored,dict):stored={}
    for item in all_items(data):
        kind=str(item.get('type') or '')
        if kind in KINDS:
            stored[kind]=max(int(stored.get(kind,0) or 0),counter_for_id(kind,item['id']))
    settings['id_counters']=stored
    return stored


def next_id(data,entry):
    kind=str(entry.get('type') or 'generic')
    if kind not in KINDS:raise ValueError('Unsupported item ID type: '+kind)
    counters=ensure_counters(data)
    used={str(item['id']) for item in all_items(data)}
    if kind in ('talk','conference'):
        prefix=f'{kind}-{event_date(entry)[2:4]}{event_date(entry)[5:7]}{event_date(entry)[8:10]}'
        i=1
        while f'{prefix}{i}' in used:i+=1
        return f'{prefix}{i}'
    if kind=='teaching':
        year,season=term_parts(entry);prefix=f'{kind}-{year}{season}';width=3
    elif kind=='honor':
        year=str(entry.get('year') or current_year())[-2:]
        prefix=f'{kind}-{year}{country_numeric(entry)}';width=3
    elif kind in ('publication','visit'):
        when=event_date(entry);prefix=f'{kind}-{when[2:4]}{when[5:7]}';width=3
    else:
        raw=str(entry.get('start_date') or entry.get('date') or entry.get('year') or current_year())
        match=re.search(r'(?:19|20)\d{2}',raw)
        prefix=f'{kind}-{(match.group(0) if match else current_year())[-2:]}';width=5
    i=int(counters.get(kind,0) or 0)+1
    if i>=10**width:raise ValueError(f'{kind} counter exhausted at {10**width-1}; widen the schema first.')
    while f'{prefix}{i:0{width}d}' in used:
        i+=1
        if i>=10**width:raise ValueError(f'{kind} counter exhausted.')
    return f'{prefix}{i:0{width}d}'


def reserve_counter(data,entry):
    counters=ensure_counters(data)
    kind=str(entry.get('type') or '')
    if kind in KINDS:counters[kind]=max(int(counters.get(kind,0) or 0),counter_for_id(kind,entry.get('id')))


def rewrite_references(root,old,new):
    """Change exact entry references and fragment URLs, not unrelated prose."""
    if isinstance(root,dict):
        out={}
        for key,value in root.items():
            mapped_key=new if key==old else key
            if mapped_key in out and mapped_key!=key:raise ValueError('Duplicate reference key during ID rename')
            out[mapped_key]=rewrite_references(value,old,new)
        return out
    if isinstance(root,list):return [rewrite_references(value,old,new) for value in root]
    if isinstance(root,str):
        if root==old:return new
        if root.startswith(old+'--at--'):return new+root[len(old):]
        # Preserve the URL path while updating only the exact fragment identifier.
        if '#' in root:
            base,sep,fragment=root.rpartition('#')
            if fragment==old:return base+sep+new
            if fragment.startswith(old+'--at--'):return base+sep+new+fragment[len(old):]
        return root
    return root


def rename_item(data,history,kind,old,new,expected=None):
    if not ID_PATTERN.fullmatch(new) or not new.startswith(kind+'-'):
        raise ValueError('New ID must be lowercase ASCII and start with '+kind+'-')
    if old==new:raise ValueError('The new ID is the same as the old ID')
    records=all_items(data)
    record=next((row for row in records if row['id']==old and row.get('type')==kind),None)
    if record is None:raise ValueError('Original ID not found; reload Admin: '+old)
    if any(row['id']==new for row in records):raise ValueError('New ID is already used: '+new)
    if expected is not None:
        # The submitted record may have been updated earlier in this batch; ID
        # existence and uniqueness are always authoritative at this point.
        if expected.get('id')!=old:raise ValueError('Stale ID-change request')
    updated=rewrite_references(data,old,new)
    data.clear();data.update(updated)
    if history is not None:
        normalized=rewrite_references(history,old,new)
        history.clear();history.update(normalized)
    new_record=next(row for row in all_items(data) if row['id']==new)
    reserve_counter(data,new_record)
    return new_record


def install():
    global _INSTALLED
    if _INSTALLED:return
    import category_config as category
    prior_migrate=category.migrate_category_data
    def migrate_category_data(data):
        result=prior_migrate(data)
        ensure_counters(result)
        return result
    category.migrate_category_data=migrate_category_data

    # The profile extension historically addressed managed contact items by
    # fixed English IDs. Resolve those semantic names through personal_key so
    # users may rename every profile item without recreation of obsolete IDs.
    import cms_extensions as profiles
    semantic_aliases={
        'profile-name':'name','contact-affiliation':'affiliation','profile-position':'position',
        'contact-institutional-email':'institutional_email',
        'contact-personal-email':'personal_email','contact-address-office':'office',
        'personal-languages':'languages','personal-address':'address',
        'personal-email':'email','personal-website':'website','personal-orcid':'orcid',
    }
    previous_find=profiles._find_item
    previous_upsert=profiles._upsert
    def find_managed(data,item_id):
        key=semantic_aliases.get(item_id)
        if key:
            found=next((x for x in data.get('profile_items',[]) if x.get('personal_key')==key),None)
            if found:return found
        return previous_find(data,item_id)
    def upsert_managed(profile_items,item_id):
        key=semantic_aliases.get(item_id)
        if key:
            found=next((x for x in profile_items if isinstance(x,dict) and x.get('personal_key')==key),None)
            if found:return found
            # A new database without managed profile items also gets canonical
            # IDs. Existing migrated databases preserve their user-selected IDs.
            data={'settings':{'id_counters':{}},'profile_items':profile_items}
            kind='contact' if item_id.startswith('contact-') and item_id!='contact-affiliation' else 'personal'
            created={'type':kind,'id':next_id(data,{'type':kind})}
            profile_items.append(created)
            return created
        return previous_upsert(profile_items,item_id)
    profiles._find_item=find_managed
    profiles._upsert=upsert_managed

    # The legacy Issue-form handler remains able to create entries. Canonicalize
    # IDs even there, without changing the form's public contract.
    import process_request as forms
    for name in ('add_conference','add_talk','add_visit','add_honor','add_publication','add_teaching'):
        prior=getattr(forms,name)
        def wrapper(data, fields, _prior=prior):
            old=_prior(data,fields)
            item=next((row for row in all_items(data) if row.get('id')==old),None)
            if item is None:return old
            candidate=next_id(data,item)
            rename_item(data,None,item['type'],old,candidate)
            reserve_counter(data,next(row for row in all_items(data) if row['id']==candidate))
            return candidate
        setattr(forms,name,wrapper)

    if Path(sys.argv[0]).name in {'run_process_batch_request.py','process_batch_request.py'}:
        import process_batch_request as batch
        old_validate=batch.validate_operation
        old_apply=batch.apply_content
        def validate_operation(op):
            if isinstance(op,dict) and op.get('op')=='rename_id':
                kind=str(op.get('type') or '')
                old=str(op.get('id') or '')
                new=str(op.get('new_id') or '')
                if kind not in KINDS or not old or not ID_PATTERN.fullmatch(new) or not new.startswith(kind+'-'):
                    raise ValueError('Invalid ID rename operation')
                if old==new:raise ValueError('ID is unchanged')
                return
            return old_validate(op)
        def apply_content(data, history, op, hid, issue, n, rd):
            if op.get('op')=='rename_id':
                kind,old,new=op['type'],op['id'],op['new_id']
                changed=rename_item(data,history,kind,old,new,op.get('before'))
                # Do not retain an old-ID snapshot in the website history.
                current=copy.deepcopy(changed)
                batch.append_history(history,history_id=hid,issue_number=issue,
                    applied_at=n,request_digest=rd,request_action='rename_id',
                    action='update',type=kind,entry_id=new,
                    label={'en':'Item ID updated','zh':'項目 ID 已更新'},
                    before=current,after=current,index_before=None,index_after=None,undo_of=None)
                return 'update',new
            action,item_id=old_apply(data,history,op,hid,issue,n,rd)
            if action=='add':
                added=next((x for x in all_items(data) if x['id']==item_id),None)
                if added:reserve_counter(data,added)
            return action,item_id
        batch.validate_operation=validate_operation
        batch.apply_content=apply_content
    _INSTALLED=True

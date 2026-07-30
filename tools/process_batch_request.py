#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, copy, gzip, hashlib, html, json, re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from translation_validation import normalize_translation_tags, validate_translation_data
from heading_config import normalized_headings, validate_headings
from category_config import migrate_category_data, validate_category_data, all_items
from homepage_config import apply_homepage_config, normalized_homepage_config, validate_homepage_config
from process_request import strip_invisible_chars
ROOT=Path(__file__).resolve().parents[1]; SITE=ROOT/'content/site.json'; TRANS=ROOT/'content/translations.json'; HISTORY=ROOT/'content/change-history.json'; RETENTION=7
SECTIONS={'conference':'activities','talk':'activities','visit':'activities','organization':'activities','honor':'honors','publication':'publications','teaching':'teaching','interest':'profile_items','education':'profile_items','contact':'profile_items','personal':'profile_items','generic':'profile_items'}
def parse_body(body):
 m=re.search(r'### Batch payload / 批次資料\s+(.+)',body,re.S);raw=(m.group(1) if m else body).strip();f=re.search(r'```(?:json)?\s*(.*?)```',raw,re.S);text=(f.group(1) if f else raw).strip()
 if text.startswith('gzip-base64:'):
  try:text=gzip.decompress(base64.b64decode(text.split(':',1)[1])).decode('utf-8')
  except Exception as exc:raise ValueError('Invalid compressed batch payload.') from exc
 return json.loads(text)
def now():return datetime.now(timezone.utc)
def iso(d):return d.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def semantic(x):
 if isinstance(x,list):return [semantic(v) for v in x]
 if not isinstance(x,dict):return x
 ignored={'order','group_label'}
 return {k:semantic(v) for k,v in x.items() if k not in ignored and not k.endswith('_html')}
def clean(s):return html.escape(str(s or '').strip(),quote=False)
def normalize_item(x):
 x=copy.deepcopy(x);t=x['type']
 for k in ('title','description','organization','authors','venue','role','organization_kind','date_label'):
  if isinstance(x.get(k),dict):x[k+'_html']={l:clean(v) for l,v in x[k].items()}
 if t=='publication':x['year']=int(str(x.get('date',''))[:4] or x.get('year') or 0)
 return x
def empty_history():return {'schema_version':2,'retention_days':RETENTION,'operations':[]}
def load_history():
 if not HISTORY.exists():return empty_history()
 h=json.load(open(HISTORY,encoding='utf-8'));h.setdefault('operations',[]);h['schema_version']=2;h['retention_days']=RETENTION;return h
def prune(h,n):h['operations']=[x for x in h['operations'] if x.get('expires_at') and dt(x['expires_at'])>n]
def label(item):
 if not item:return {'en':'','zh':''}
 for k in ('title','course'):
  if isinstance(item.get(k),dict):return {'en':str(item[k].get('en') or ''),'zh':str(item[k].get('zh') or '')}
 return {'en':str(item.get('id') or ''),'zh':''}
def hist_id(issue,i):return f'issue-{issue}-op-{i}'
def append_history(h,**kw):
 n=kw.pop('applied_at');e={'history_id':kw.pop('history_id'),'batch_issue':kw.pop('issue_number'),'applied_at':iso(n),'expires_at':iso(n+timedelta(days=RETENTION)),'reverted_by':None,**kw};h['operations'].append(e);return e
def find(data,t,eid):
 a=data.setdefault(SECTIONS[t],[]);i=next((i for i,x in enumerate(a) if x.get('id')==eid),None);return a,i
def capture_order(data,kind):
 items=[x for x in data.get(SECTIONS[kind],[]) if x.get('type')==kind]
 if kind not in ('publication','teaching'):
  stored=data.get('settings',{}).get('entry_order',{}).get(kind,[]);ids={x['id'] for x in items};return {'kind':kind,'entries':[x for x in stored if x in ids]+[x['id'] for x in items if x['id'] not in stored]}
 groups=copy.deepcopy(data.get('settings',{}).get('content_groups',{}).get(kind,[]));known={g.get('id') for g in groups}
 for x in items:
  gid=x.get('group_id') or ('preprints' if kind=='publication' else 'institution')
  if gid not in known:groups.append({'id':gid,'label':x.get('institution') or x.get('group_label') or {'en':gid,'zh':''},'order':len(groups)});known.add(gid)
 groups.sort(key=lambda g:g.get('order',999));return {'kind':kind,'groups':[{'id':g['id'],'label':g.get('label',{'en':g['id'],'zh':''}),'preset':bool(g.get('preset')),'entries':[x['id'] for x in sorted(items,key=lambda z:z.get('order',999)) if x.get('group_id')==g['id']]} for g in groups if any(x.get('group_id')==g['id'] for x in items)]}
def apply_order(data,state):
 kind=state['kind'];items=[x for x in data.get(SECTIONS[kind],[]) if x.get('type')==kind];ids={x['id'] for x in items}
 if 'entries' in state:
  if set(state['entries'])!=ids or len(state['entries'])!=len(ids):raise ValueError(f'Ordering must contain every {kind} entry exactly once.')
  data.setdefault('settings',{}).setdefault('entry_order',{})[kind]=list(state['entries']);return
 flat=[eid for g in state.get('groups',[]) for eid in g.get('entries',[])]
 if set(flat)!=ids or len(flat)!=len(ids):raise ValueError(f'Grouped ordering must contain every {kind} entry exactly once.')
 data.setdefault('settings',{}).setdefault('content_groups',{})[kind]=[{'id':g['id'],'label':g.get('label',{'en':g['id'],'zh':''}),'order':i,'preset':bool(g.get('preset'))} for i,g in enumerate(state['groups'])]
 by={x['id']:x for x in items}
 for g in state['groups']:
  for i,eid in enumerate(g['entries']):by[eid]['group_id']=g['id'];by[eid]['order']=i
  if kind=='teaching':
   for eid in g['entries']:by[eid]['institution']=copy.deepcopy(g.get('label',{}))
def merge_sequence(current,desired):
 # Reorder the IDs mentioned by the Admin while preserving unknown/new IDs
 # in their current slots. This safely rebases stale ordering drafts.
 current=list(current);desired=list(desired);curset=set(current)
 if len(desired)!=len(set(desired)):raise ValueError('Ordering contains duplicate entry IDs.')
 missing=[x for x in desired if x not in curset]
 if missing:raise ValueError('Ordering refers to missing entries: '+', '.join(missing[:5]))
 wanted=set(desired);slots=[i for i,x in enumerate(current) if x in wanted]
 result=list(current)
 for i,x in zip(slots,desired):result[i]=x
 return result

def rebase_order(current,desired):
 kind=current['kind']
 if 'entries' in current:
  return {'kind':kind,'entries':merge_sequence(current.get('entries',[]),desired.get('entries',[]))}
 current_groups=current.get('groups',[]);desired_groups=desired.get('groups',[])
 cur_entries=[eid for g in current_groups for eid in g.get('entries',[])]
 desired_entries=[eid for g in desired_groups for eid in g.get('entries',[])]
 if len(desired_entries)!=len(set(desired_entries)):raise ValueError('Grouped ordering contains duplicate entry IDs.')
 missing=[eid for eid in desired_entries if eid not in set(cur_entries)]
 if missing:raise ValueError('Grouped ordering refers to missing entries: '+', '.join(missing[:5]))
 cur_group_by_entry={eid:g['id'] for g in current_groups for eid in g.get('entries',[])}
 desired_group_by_entry={eid:g['id'] for g in desired_groups for eid in g.get('entries',[])}
 cur_meta={g['id']:g for g in current_groups};desired_meta={g['id']:g for g in desired_groups}
 # Groups explicitly mentioned by the draft follow the desired order. Groups
 # that appeared later are retained afterwards in their current order.
 active_desired=[]
 for g in desired_groups:
  if any(eid in set(cur_entries) for eid in g.get('entries',[])) and g['id'] not in active_desired:active_desired.append(g['id'])
 extra=[g['id'] for g in current_groups if g['id'] not in active_desired]
 group_ids=active_desired+extra
 assigned={gid:[] for gid in group_ids}
 for eid in cur_entries:
  gid=desired_group_by_entry.get(eid,cur_group_by_entry[eid])
  if gid not in assigned:
   assigned[gid]=[];group_ids.append(gid)
  assigned[gid].append(eid)
 result=[]
 for gid in group_ids:
  base=assigned.get(gid,[])
  wanted=[eid for eid in desired_meta.get(gid,{}).get('entries',[]) if eid in set(base)]
  entries=merge_sequence(base,wanted) if wanted else base
  if not entries:continue
  meta=desired_meta.get(gid) or cur_meta.get(gid) or {'id':gid,'label':{'en':gid,'zh':''}}
  result.append({'id':gid,'label':copy.deepcopy(meta.get('label',{'en':gid,'zh':''})),'preset':bool(meta.get('preset')),'entries':entries})
 return {'kind':kind,'groups':result}
def validate_trans(d):
 validate_translation_data(d)
def current_group_labels(data):
 result={'publication':{},'teaching':{}}
 groups=data.get('settings',{}).get('content_groups',{})
 for kind in ('publication','teaching'):
  for group in groups.get(kind,[]):
   gid=str(group.get('id') or '')
   if gid:result[kind][gid]={'en':str((group.get('label') or {}).get('en') or ''),'zh':str((group.get('label') or {}).get('zh') or '')}
 return result
def normalized_heading_bundle(data,value):
 current_labels=current_group_labels(data)
 if isinstance(value,dict) and 'headings' in value:
  headings=normalized_headings(value.get('headings',{}));supplied=value.get('group_labels',{})
 else:
  headings=normalized_headings(value or {});supplied={}
 labels=copy.deepcopy(current_labels)
 if isinstance(supplied,dict):
  for kind in ('publication','teaching'):
   source=supplied.get(kind,{})
   if not isinstance(source,dict):continue
   for gid in labels[kind]:
    pair=source.get(gid)
    if isinstance(pair,dict):labels[kind][gid]={'en':str(pair.get('en') or '').strip(),'zh':str(pair.get('zh') or '').strip()}
 return {'headings':headings,'group_labels':labels}
def validate_heading_bundle(data,bundle):
 validate_headings(bundle['headings'])
 current=current_group_labels(data)
 for kind in ('publication','teaching'):
  if set(bundle['group_labels'].get(kind,{}))!=set(current.get(kind,{})):raise ValueError(f'Heading groups changed for {kind}; reload Admin.')
  for gid,pair in bundle['group_labels'][kind].items():
   for lang in ('en','zh'):
    if not str(pair.get(lang) or '').strip():raise ValueError(f'{kind} group {gid} {lang} label cannot be blank.')
def apply_heading_bundle(data,bundle):
 validate_heading_bundle(data,bundle);settings=data.setdefault('settings',{});settings['headings']=copy.deepcopy(bundle['headings'])
 for kind in ('publication','teaching'):
  labels=bundle['group_labels'][kind]
  for group in settings.setdefault('content_groups',{}).get(kind,[]):
   gid=str(group.get('id') or '')
   if gid in labels:group['label']=copy.deepcopy(labels[gid])

def layout_bundle(data):
 settings=data.get('settings',{})
 return {
  'pages':copy.deepcopy(settings.get('pages',[])),
  'categories':copy.deepcopy(settings.get('categories',[])),
  'cv_category_order':copy.deepcopy(settings.get('cv_category_order',[])),
  'assignments':{str(x.get('id')):{'category_id':str(x.get('category_id') or ''),'order':int(x.get('order',999999))} for x in all_items(data)},
 }
def normalized_layout_bundle(data,value):
 if not isinstance(value,dict):raise ValueError('Layout operation requires an object.')
 result={
  'pages':copy.deepcopy(value.get('pages',[])),
  'categories':copy.deepcopy(value.get('categories',[])),
  'cv_category_order':copy.deepcopy(value.get('cv_category_order',[])),
  'assignments':copy.deepcopy(value.get('assignments',{})),
 }
 probe=copy.deepcopy(data);settings=probe.setdefault('settings',{});settings['pages']=result['pages'];settings['categories']=result['categories'];settings['cv_category_order']=result['cv_category_order']
 current_ids={str(x.get('id')) for x in all_items(probe)}
 if set(result['assignments'])!=current_ids:raise ValueError('Layout assignments changed; reload Admin before submitting.')
 for item in all_items(probe):
  state=result['assignments'][str(item.get('id'))]
  item['category_id']=str(state.get('category_id') or '')
  item['order']=int(state.get('order',999999))
 validate_category_data(probe)
 return layout_bundle(probe)
def apply_layout_bundle(data,bundle):
 normalized=normalized_layout_bundle(data,bundle);settings=data.setdefault('settings',{});settings['pages']=copy.deepcopy(normalized['pages']);settings['categories']=copy.deepcopy(normalized['categories']);settings['cv_category_order']=copy.deepcopy(normalized['cv_category_order'])
 by={str(x.get('id')):x for x in all_items(data)}
 for iid,state in normalized['assignments'].items():
  by[iid]['category_id']=state['category_id'];by[iid]['order']=int(state['order'])
 return normalized
def normalize_groups(data):
 groups=data.setdefault('settings',{}).setdefault('content_groups',{})
 for kind,sec in (('publication','publications'),('teaching','teaching')):
  used={x.get('group_id') for x in data.get(sec,[]) if x.get('group_id')};groups[kind]=[g for g in groups.get(kind,[]) if g.get('preset') or g.get('id') in used];known={g.get('id') for g in groups[kind]}
  for x in data.get(sec,[]):
   gid=x.get('group_id');
   if gid and gid not in known:
    lab=x.pop('group_label',None) or (x.get('institution') if kind=='teaching' else {'en':gid,'zh':''});groups[kind].append({'id':gid,'label':lab,'order':len(groups[kind])});known.add(gid)
def apply_content(data,h,op,hid,issue,n,rd):
 action=op['op'];t=op['type'];eid=op.get('id') or op.get('after',{}).get('id');a,i=find(data,t,eid)
 if action=='add':
  after=normalize_item(op['after']);eid=after['id'];allids={x.get('id') for s in set(SECTIONS.values()) for x in data.get(s,[])}
  if eid in allids:raise ValueError(f'Add target ID already exists: {eid}. Reload Admin and submit again.')
  a,_=find(data,t,eid);idx=len(a);a.append(after);append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='add',action='add',type=t,entry_id=eid,label=label(after),before=None,after=copy.deepcopy(after),index_before=None,index_after=idx,undo_of=None);return 'add',eid
 if i is None:raise ValueError(f'{action.title()} target not found: {eid}')
 cur=copy.deepcopy(a[i]);expected=op.get('before')
 if expected and semantic(cur)!=semantic(expected):raise ValueError(f'Conflict: {eid} changed after Admin loaded.')
 if action=='delete':a.pop(i);append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='delete',action='delete',type=t,entry_id=eid,label=label(cur),before=cur,after=None,index_before=i,index_after=None,undo_of=None);return 'delete',eid
 after=normalize_item(op['after']);after['id']=eid;a[i]=after;append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='update',action='update',type=t,entry_id=eid,label=label(after),before=cur,after=copy.deepcopy(after),index_before=i,index_after=i,undo_of=None);return 'update',eid
def layout_structure(value):
 if not isinstance(value,dict):return {'pages':[],'categories':[],'cv_category_order':[]}
 return {
  'pages':copy.deepcopy(value.get('pages',[])),
  'categories':copy.deepcopy(value.get('categories',[])),
  'cv_category_order':copy.deepcopy(value.get('cv_category_order',[])),
 }
def layout_expected_matches(current,expected):
 if not isinstance(expected,dict):return True
 if layout_structure(current)!=layout_structure(expected):return False
 expected_assignments=expected.get('assignments',{}) if isinstance(expected.get('assignments'),dict) else {}
 current_assignments=current.get('assignments',{}) if isinstance(current.get('assignments'),dict) else {}
 # Add/delete operations may have run earlier in this same batch. Compare only
 # IDs that still exist on both sides; newly added and already deleted items are
 # validated against the submitted `after` bundle below.
 for iid in set(expected_assignments)&set(current_assignments):
  left=expected_assignments[iid] if isinstance(expected_assignments[iid],dict) else {}
  right=current_assignments[iid] if isinstance(current_assignments[iid],dict) else {}
  if str(left.get('category_id') or '')!=str(right.get('category_id') or ''):return False
  if int(left.get('order',999999))!=int(right.get('order',999999)):return False
 return True
def apply_special(data,trans,h,op,hid,issue,n,rd):
 if op['op']=='homepage':
  before=normalized_homepage_config(data);expected=op.get('before')
  if expected and before!=normalized_homepage_config(data,expected):raise ValueError('Conflict: homepage settings changed after Admin loaded.')
  after=apply_homepage_config(data,copy.deepcopy(op['after']));append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='homepage',action='homepage',type='homepage',entry_id='homepage',label={'en':'Homepage selections','zh':'首頁精選'},before=before,after=copy.deepcopy(after),index_before=None,index_after=None,undo_of=None);return 'homepage','homepage'
 if op['op']=='layout':
  before=layout_bundle(data);expected=op.get('before')
  if expected and not layout_expected_matches(before,expected):raise ValueError('Conflict: page/category layout changed after Admin loaded.')
  after=apply_layout_bundle(data,copy.deepcopy(op['after']));append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='layout',action='layout',type='layout',entry_id='layout',label={'en':'Page and category layout','zh':'頁面與類別'},before=before,after=copy.deepcopy(after),index_before=None,index_after=None,undo_of=None);return 'layout','layout'
 if op['op']=='reorder':
  before=capture_order(data,op['type'])
  # Ordering is safely rebased onto the current database. This handles items
  # added/deleted earlier in the same batch and stale Admin tabs without
  # dropping entries that were created later.
  requested=rebase_order(before,op['after'])
  apply_order(data,requested);after=capture_order(data,op['type']);append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='reorder',action='reorder',type=op['type'],entry_id='order:'+op['type'],label={'en':op['type']+' order','zh':'排序'},before=before,after=after,index_before=None,index_after=None,undo_of=None);return 'reorder','order:'+op['type']
 if op['op']=='headings':
  before=normalized_heading_bundle(data,{'headings':data.get('settings',{}).get('headings',{}),'group_labels':current_group_labels(data)});expected=op.get('before')
  if expected and before!=normalized_heading_bundle(data,expected):raise ValueError('Conflict: website headings changed after Admin loaded.')
  after=normalized_heading_bundle(data,copy.deepcopy(op['after']));apply_heading_bundle(data,after);append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='headings',action='headings',type='headings',entry_id='headings',label={'en':'Website headings','zh':'網站標題'},before=before,after=copy.deepcopy(after),index_before=None,index_after=None,undo_of=None);return 'headings','headings'
 before=copy.deepcopy(trans);expected=op.get('before')
 if expected and before!=expected:raise ValueError('Conflict: translations changed after Admin loaded.')
 after=copy.deepcopy(op['after']);normalize_translation_tags(after);validate_trans(after);trans.clear();trans.update(after);append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='translations',action='translations',type='translations',entry_id='translations',label={'en':'Translation dictionary','zh':'中英對照表'},before=before,after=copy.deepcopy(after),index_before=None,index_after=None,undo_of=None);return 'translations','translations'
def apply_undo(data,trans,h,op,hid,issue,n,rd):
 tid=op.get('history_id');target=next((x for x in h['operations'] if x.get('history_id')==tid),None)
 if not target:raise ValueError(f'Undo target unavailable or expired: {tid}')
 if target.get('reverted_by'):raise ValueError(f'{tid} was already undone.')
 if dt(target['expires_at'])<=n:raise ValueError(f'Undo expired: {tid}')
 act=target['action'];t=target['type'];eid=target['entry_id']
 if act=='homepage':
  cur=normalized_homepage_config(data)
  if cur!=normalized_homepage_config(data,target['after']):raise ValueError('Cannot undo homepage settings: settings changed later.')
  restored=apply_homepage_config(data,target['before']);new=append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='undo',action='homepage',type='homepage',entry_id='homepage',label=target['label'],before=cur,after=copy.deepcopy(restored),index_before=None,index_after=None,undo_of=tid)
 elif act=='layout':
  cur=layout_bundle(data)
  if cur!=normalized_layout_bundle(data,target['after']):raise ValueError('Cannot undo layout: layout changed later.')
  restored=apply_layout_bundle(data,target['before']);new=append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='undo',action='layout',type='layout',entry_id='layout',label=target['label'],before=cur,after=copy.deepcopy(restored),index_before=None,index_after=None,undo_of=tid)
 elif act=='reorder':
  cur=capture_order(data,t)
  # Restore the old relative order while retaining entries/groups that were
  # added after the original ordering operation.
  restored=rebase_order(cur,target['before'])
  apply_order(data,restored);after=capture_order(data,t);new=append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='undo',action='reorder',type=t,entry_id=eid,label=target['label'],before=cur,after=after,index_before=None,index_after=None,undo_of=tid)
 elif act=='headings':
  cur=normalized_heading_bundle(data,{'headings':data.get('settings',{}).get('headings',{}),'group_labels':current_group_labels(data)})
  if cur!=normalized_heading_bundle(data,target['after']):raise ValueError('Cannot undo headings: headings changed later.')
  restored=normalized_heading_bundle(data,target['before']);apply_heading_bundle(data,restored);new=append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='undo',action='headings',type='headings',entry_id='headings',label=target['label'],before=cur,after=copy.deepcopy(restored),index_before=None,index_after=None,undo_of=tid)
 elif act=='translations':
  if trans!=target['after']:raise ValueError('Cannot undo translations: dictionary changed later.')
  before=copy.deepcopy(trans);trans.clear();trans.update(copy.deepcopy(target['before']));new=append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='undo',action='translations',type='translations',entry_id='translations',label=target['label'],before=before,after=copy.deepcopy(trans),index_before=None,index_after=None,undo_of=tid)
 else:
  a,i=find(data,t,eid)
  if act=='add':
   if i is None or semantic(a[i])!=semantic(target['after']):raise ValueError(f'Cannot undo add: {eid} changed later.')
   cur=copy.deepcopy(a[i]);a.pop(i);new=append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='undo',action='delete',type=t,entry_id=eid,label=target['label'],before=cur,after=None,index_before=i,index_after=None,undo_of=tid)
  elif act=='update':
   if i is None or semantic(a[i])!=semantic(target['after']):raise ValueError(f'Cannot undo update: {eid} changed later.')
   cur=copy.deepcopy(a[i]);a[i]=copy.deepcopy(target['before']);new=append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='undo',action='update',type=t,entry_id=eid,label=target['label'],before=cur,after=copy.deepcopy(a[i]),index_before=i,index_after=i,undo_of=tid)
  elif act=='delete':
   if i is not None:raise ValueError(f'Cannot undo delete: ID {eid} is in use.')
   restored=copy.deepcopy(target['before']);idx=min(max(target.get('index_before') or 0,0),len(a));a.insert(idx,restored);new=append_history(h,history_id=hid,issue_number=issue,applied_at=n,request_digest=rd,request_action='undo',action='add',type=t,entry_id=eid,label=target['label'],before=None,after=copy.deepcopy(restored),index_before=None,index_after=idx,undo_of=tid)
  else:raise ValueError(f'Unsupported undo action: {act}')
 target['reverted_by']=new['history_id'];return 'undo',eid
def validate_operation(op):
 if not isinstance(op,dict):raise ValueError('Every batch operation must be an object.')
 action=op.get('op')
 if action not in {'add','update','delete','undo','reorder','translations','headings','layout','homepage'}:raise ValueError(f'Unsupported batch operation: {action}')
 if action=='undo':
  if not str(op.get('history_id') or '').strip():raise ValueError('Undo operation is missing history_id.')
  return
 if action=='translations':
  if not isinstance(op.get('before'),dict) or not isinstance(op.get('after'),dict):raise ValueError('Translations operation requires before and after objects.')
  validate_translation_data(op['after']);return
 if action=='layout':
  if not isinstance(op.get('before'),dict) or not isinstance(op.get('after'),dict):raise ValueError('Layout operation requires before and after objects.')
  return
 if action=='homepage':
  if not isinstance(op.get('before'),dict) or not isinstance(op.get('after'),dict):raise ValueError('Homepage operation requires before and after objects.')
  return
 if action=='headings':
  if not isinstance(op.get('before'),dict) or not isinstance(op.get('after'),dict):raise ValueError('Headings operation requires before and after objects.')
  # Full validation needs the current content-group IDs and is performed while applying.
  return
 t=op.get('type')
 if t not in SECTIONS:raise ValueError(f'Unsupported content type: {t}')
 if action=='reorder':
  if not isinstance(op.get('after'),dict) or op['after'].get('kind')!=t:raise ValueError(f'Reorder operation for {t} has an invalid state.')
  return
 if action in {'add','update'}:
  after=op.get('after')
  if not isinstance(after,dict) or after.get('type')!=t or not str(after.get('id') or '').strip():raise ValueError(f'{action.title()} operation for {t} has invalid after data.')
 if action in {'update','delete'} and not str(op.get('id') or op.get('after',{}).get('id') or '').strip():raise ValueError(f'{action.title()} operation is missing an ID.')
def main():
 p=argparse.ArgumentParser();p.add_argument('event');p.add_argument('--result-file',required=True);a=p.parse_args();ev=json.load(open(a.event));issue=int(ev['issue']['number']);payload=parse_body(ev['issue']['body']);ops=payload.get('operations',[])
 if payload.get('schema_version')!=2 or not isinstance(ops,list):raise ValueError('Invalid batch payload.')
 data=migrate_category_data(json.load(open(SITE,encoding='utf-8')));trans=json.load(open(TRANS,encoding='utf-8'));normalize_translation_tags(trans);h=load_history();n=now();prune(h,n);existing={x['history_id']:x for x in h['operations']};counts={k:0 for k in ('add','update','delete','undo','reorder','translations','headings','layout','homepage','replayed')};ids=[]
 for i,op in enumerate(ops,1):
  validate_operation(op);hid=f'issue-{issue}-op-{i}';rd=digest(op)
  if hid in existing:
   if existing[hid].get('request_digest')!=rd:raise ValueError(f'{hid} exists with different content.')
   counts['replayed']+=1;continue
  if op['op']=='undo':act,eid=apply_undo(data,trans,h,op,hid,issue,n,rd)
  elif op['op'] in ('reorder','translations','headings','layout','homepage'):act,eid=apply_special(data,trans,h,op,hid,issue,n,rd)
  else:act,eid=apply_content(data,h,op,hid,issue,n,rd)
  counts[act]+=1;ids.append(eid);existing[hid]=h['operations'][-1]
 normalize_groups(data);data=strip_invisible_chars(migrate_category_data(data));trans=strip_invisible_chars(trans);h=strip_invisible_chars(h);validate_category_data(data);validate_homepage_config(data,normalized_homepage_config(data));validate_trans(trans);SITE.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');TRANS.write_text(json.dumps(trans,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');HISTORY.write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 summary='批次完成：'+ '、'.join(f'{k} {counts[k]}' for k in ('add','update','delete','undo','reorder','translations','headings','layout','homepage') if counts[k]);res={'action':summary or '沒有新操作','entry_id':', '.join(ids[:8]),'notes':['每筆操作已保存七天，可在 Admin 單筆 Undo。'],'warnings':[]};Path(a.result_file).write_text(json.dumps(res,ensure_ascii=False),encoding='utf-8')
if __name__=='__main__':main()

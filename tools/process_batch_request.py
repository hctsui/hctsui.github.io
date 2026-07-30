#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, html, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"content/site.json"
SECTIONS={"conference":"activities","talk":"activities","visit":"activities","honor":"honors","publication":"publications","teaching":"teaching"}
def parse_body(body):
    m=re.search(r"### Batch payload / 批次資料\s+(.+)",body,re.S); raw=(m.group(1) if m else body).strip()
    f=re.search(r"```(?:json)?\s*(.*?)```",raw,re.S); return json.loads((f.group(1) if f else raw).strip())
def clean_html(s): return html.escape(str(s or "").strip(),quote=False)
def normalize(x):
    t=x["type"]; x=copy.deepcopy(x)
    for k in ("title","description","organization","authors","venue"):
        if isinstance(x.get(k),dict): x[k+"_html"]={a:clean_html(b) for a,b in x[k].items()}
    if t=="publication":
        x["year"]=int(str(x.get("date",""))[:4] or x.get("year") or 0)
    return x
def main():
    ap=argparse.ArgumentParser();ap.add_argument("event");ap.add_argument("--result-file",required=True);a=ap.parse_args()
    ev=json.load(open(a.event)); payload=parse_body(ev["issue"]["body"]); ops=payload.get("operations",[])
    if payload.get("schema_version")!=1 or not isinstance(ops,list): raise ValueError("Invalid batch payload")
    data=json.load(open(DATA,encoding="utf-8")); counts={"add":0,"update":0,"delete":0}; ids=[]
    for op in ops:
        action=op["op"]; t=op["type"]; sec=SECTIONS[t]; arr=data.setdefault(sec,[]); eid=op.get("id") or op.get("after",{}).get("id")
        if action=="delete":
            n=len(arr); data[sec]=[x for x in arr if x.get("id")!=eid]
            if len(data[sec])==n: raise ValueError(f"Delete target not found: {eid}")
        elif action=="update":
            i=next((i for i,x in enumerate(arr) if x.get("id")==eid),None)
            if i is None: raise ValueError(f"Update target not found: {eid}")
            before=op.get("before")
            if before and arr[i]!=before: raise ValueError(f"Conflict: {eid} changed after Admin loaded")
            after=normalize(op["after"]);after["id"]=eid;arr[i]=after
        elif action=="add":
            after=normalize(op["after"]); eid=after["id"]
            if any(x.get("id")==eid for s in SECTIONS.values() for x in data.get(s,[])):
                base=eid;n=2
                while any(x.get("id")==f"{base}-{n}" for s in SECTIONS.values() for x in data.get(s,[])): n+=1
                after["id"]=eid=f"{base}-{n}"
            arr.append(after)
        else: raise ValueError(f"Unknown operation: {action}")
        counts[action]+=1;ids.append(eid)
    # normalize order and remove empty custom groups
    for sec in ("honors","publications","teaching"):
        for i,x in enumerate(data.get(sec,[])): x["order"]=i
    groups=data.setdefault("settings",{}).setdefault("content_groups",{})
    for kind,sec in (("publication","publications"),("teaching","teaching")):
        used={x.get("group_id") for x in data.get(sec,[])}
        groups[kind]=[g for g in groups.get(kind,[]) if g.get("preset") or g.get("id") in used]
        known={g.get("id") for g in groups[kind]}
        for x in data.get(sec,[]):
            gid=x.get("group_id")
            if gid and gid not in known:
                label=x.pop("group_label",None) or (x.get("institution") if kind=="teaching" else {"en":gid,"zh":""})
                groups[kind].append({"id":gid,"label":label,"order":len(groups[kind])});known.add(gid)
    DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    result={"action":f"批次完成：新增 {counts['add']}、修改 {counts['update']}、刪除 {counts['delete']}","entry_id":", ".join(ids[:8])+("…" if len(ids)>8 else ""),"notes":[],"warnings":[]}
    Path(a.result_file).write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
if __name__=="__main__": main()

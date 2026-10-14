#!/usr/bin/env python3
"""spec.py — the living spec for a project ($SKETCH_ROOT/<project>/spec.json; versions keep a copy in vN/spec.json)
  spec.py show <project>                 values with source (USER vs ASSUMED) + the assumptions list to confirm
  spec.py set <project> key=value ...    set values (become src=user); expressions allowed: key="=other*2"
  spec.py assume <project> key=value     set a value as an ASSUMPTION (Sketch's guess)
  spec.py note <project> key "text"      attach a note
Then run design.sh <project> to regenerate EVERYTHING (model, renders, drawings, cut/print files, quote) as the next version."""
import sys,os,json,datetime
R=os.environ.get("SKETCH_ROOT",os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
cmd,proj=sys.argv[1],sys.argv[2]; F=os.path.join(proj if os.path.isdir(proj) else os.path.join(R,proj),"spec.json"); S=json.load(open(F))
def parse(v):
    try: return json.loads(v)
    except Exception: return v
if cmd=="show":
    print(f'{S.get("title",proj)}  [{S.get("domain")}, {S.get("units")}]')
    for k,v in S["values"].items(): print(f'  {"USER   " if v.get("src")=="user" else "READ   " if v.get("src")=="read" else "ASSUMED"} {k} = {v["v"]} {v.get("unit","")}  {v.get("note","")}')
    r=[k for k,v in S["values"].items() if v.get("src")=="read"]
    if r: print("\nRead from your drawing/file - please confirm: "+", ".join(f'{k}={S["values"][k]["v"]}' for k in r))
    a=[k for k,v in S["values"].items() if v.get("src") not in("user","read")]
    print("\nAssumptions to confirm or change: "+(", ".join(f'{k}={S["values"][k]["v"]}' for k in a) if a else "none"))
elif cmd in("set","assume"):
    for kv in sys.argv[3:]:
        k,v=kv.split("=",1); e=S["values"].setdefault(k,{}); e["v"]=parse(v); e["src"]="user" if cmd=="set" else "assumed"
    S.setdefault("history",[]).append(dict(at=datetime.datetime.now().isoformat(timespec="seconds"),change=" ".join(sys.argv[3:]),by="user" if cmd=="set" else "sketch"))
    json.dump(S,open(F,"w"),indent=1); print("spec updated:"," ".join(sys.argv[3:]))
elif cmd=="note": S["values"][sys.argv[3]]["note"]=sys.argv[4]; json.dump(S,open(F,"w"),indent=1)
else: sys.exit(__doc__)

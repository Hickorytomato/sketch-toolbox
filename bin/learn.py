"""learn.py - the owner's shop corrections (bin/learned.json, kept by the installer), keyed "machine|material".
feedback.py writes them; spec_build/kerf/coupons read them. get(machine, material) -> {key: delta}."""
import os,json,time
B=os.path.dirname(os.path.abspath(__file__)); P=os.path.join(B,"learned.json")
def load(): return json.load(open(P)) if os.path.exists(P) else {}
def norm(m): return str(m or "").strip().lower()
def get(machine,material):
    L=load(); out={}
    for k in (f"{norm(machine)}|*",f"{norm(machine)}|{norm(material)}"):
        for kk,v in L.get(k,{}).items():
            if not kk.startswith("_"): out[kk]=v
    return out
def put(machine,material,key,value,why):
    L=load(); k=f"{norm(machine)}|{norm(material)}"; e=L.setdefault(k,{}); e[key]=round(value,4)
    e.setdefault("_log",[]).append(dict(at=time.strftime("%Y-%m-%d %H:%M"),key=key,value=round(value,4),why=why)); json.dump(L,open(P,"w"),indent=1); return k

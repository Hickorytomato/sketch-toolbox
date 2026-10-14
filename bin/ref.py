#!/usr/bin/env python3
"""ref.py: shop reference data (bin/ref/*.json, every value with its source) + the owner's overrides (bin/ref_user.json,
kept by the installer).  ref.get("shop_reference")["tap_drill_75pct"] ...  ref.py --show NAME"""
import os,json,sys,copy
B=os.path.dirname(os.path.abspath(__file__))
def _merge(a,b):
    if isinstance(a,dict) and isinstance(b,dict):
        o=copy.deepcopy(a)
        for k,v in b.items(): o[k]=_merge(a.get(k),v) if k in a else v
        return o
    return copy.deepcopy(b)
_C={}
def get(name):
    if name not in _C:
        d=json.load(open(f"{B}/ref/{name}.json")); u=f"{B}/ref_user.json"
        if os.path.exists(u):
            uo=json.load(open(u)).get(name)
            if uo is not None: d=_merge(d,uo)
        _C[name]=d
    return _C[name]
def profile():
    p=f"{B}/profile.json"; return json.load(open(p)) if os.path.exists(p) else {}
if __name__=="__main__" and "--show" in sys.argv: print(json.dumps(get(sys.argv[sys.argv.index("--show")+1]),indent=1))

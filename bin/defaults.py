"""defaults.py (v1.0.6): which rates and prices are still Sketch's shipped defaults (not the owner's).
A value is a default when it equals ref/defaults.json AND the owner has not confirmed it (profile.json confirmed_rates,
written by tools_setup.py --rates / --shop). Prices that come from prices_default.json are always defaults."""
import os,json
B=os.path.dirname(os.path.abspath(__file__))
SET="python3 bin/tools_setup.py --rates"
def _j(p,d=None):
    try: return json.load(open(p))
    except Exception: return d if d is not None else {}
def D(): return _j(f"{B}/ref/defaults.json")
def confirmed(): return set(_j(f"{B}/profile.json").get("confirmed_rates",[]))
def is_default(key,value):
    """key: 'labor_rate' | 'margin_pct' | 'shop_hours_per_day' | 'machine_rate.<m>' | '<price_section>.<item>'"""
    if key in confirmed(): return False
    d=D()
    if key.startswith("machine_rate."): ref=d.get("machine_rate_per_h",{}).get(key.split(".",1)[1])
    elif "." in key: s,i=key.split(".",1); ref=d.get("prices",{}).get(s,{}).get(i,d.get("prices_default",{}).get(s,{}).get(i))
    else: ref=d.get("shop",{}).get(key)
    try: return ref is not None and abs(float(value)-float(ref))<1e-9
    except Exception: return False
def src_default(src):
    """a price source string (prices.json price_per_ft[2x4] ...) -> True if that price is still a Sketch default"""
    import re
    if "prices_default.json" in src or "Sketch default" in src or "toolbox default" in src: return True
    m=re.search(r"prices\.json (price_per_\w+|buy_each)\[([^\]]+)\]",src)
    if m:
        P=_j(f"{B}/prices.json"); v=P.get(m[1],{}).get(m[2]); return is_default(f"{m[1]}.{m[2]}",v) if v is not None else True
    return False
def flags():
    """list of (key, value, label) still default, for HOW_TO_USE / quote footers"""
    M=_j(f"{B}/machines.json"); sh=M.get("shop",{}); out=[]
    for k in ("labor_rate","margin_pct"):
        v=sh.get(k,D().get("shop",{}).get(k))
        if is_default(k,v): out.append((k,v,f"{k.replace('_',' ')} {v:g}"))
    for m,v in sh.get("machine_rate_per_h",{}).items():
        if not m.startswith("_") and M.get(m,{}).get("enabled",m=="printer") and is_default(f"machine_rate.{m}",v): out.append((f"machine_rate.{m}",v,f"{m} rate ${v:g}/h"))
    return out

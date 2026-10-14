#!/usr/bin/env python3
"""kerf.py: kerf for a cut = the owner's measured test cut > sourced table (bin/ref/kerf_table.json) > machines.json default.
lookup(machine_name, machine, material, thickness_in) -> (kerf_in, label).  saw(tool=None) -> (kerf_in, label) for hand/power saws.
CLI: kerf.py plasma steel 0.25"""
import os,sys,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import ref
CLS={"mild steel":"steel","steel":"steel","plate":"steel","galvanized":"steel","stainless":"stainless","ss":"stainless","304":"stainless","316":"stainless",
     "aluminum":"aluminum","aluminium":"aluminum","plywood":"plywood","baltic_birch":"plywood","wood":"plywood","mdf":"mdf","acrylic":"acrylic"}
def mcls(mat): 
    m=str(mat).lower()
    for k,v in CLS.items():
        if k in m: return v
    return m
def _key(mn,mat,t): return f"{mn}|{mcls(mat)}|{round(float(t),4)}"
def lookup(mn,m,mat,t):
    t=float(t or 0); typ=m.get("type",mn); cl=mcls(mat)
    meas=ref.profile().get("kerf_measured",{})
    for k in (_key(mn,mat,t),f"{mn}|{cl}|*",f"{mn}|*|*"):
        if k in meas: return float(meas[k]),f"measured test cut ({k})"
    if typ=="router": return float(m.get("tool_dia",0.25)),"router bit diameter (machines.json tool_dia)"
    T=ref.get("kerf_table")
    if typ=="plasma":
        amps=m.get("amps",T["plasma"].get("default_amps","45 A")); amps=amps if str(amps).endswith("A") else f"{amps} A"
        rows=[r for r in T["plasma"]["rows"] if r["material"]==cl and r["gas"]=="Air" and r["amps"]==amps and not r.get("suspect")]
        if rows:
            r=min(rows,key=lambda r:abs(r["t_in"]-t))
            if abs(r["t_in"]-t)<=max(0.07,0.35*t): return r["kerf_in"],f'Hypertherm {r["torch"]} {r["amps"]} {r["consumables"]} cut chart, {cl} {r["t_in"]:g} in (table; measure yours)'
    if typ=="laser":
        src=m.get("source","co2"); tm=t*25.4
        rows=[r for r in T["laser"]["rows"] if r["material"]==cl and r["source"]==src]
        if rows:
            r=min(rows,key=lambda r:0 if r["t_mm"][0]<=tm<=r["t_mm"][1] else min(abs(tm-r["t_mm"][0]),abs(tm-r["t_mm"][1])))
            k=sum(r["kerf_mm"])/2/25.4; return round(k,4),f'{src.upper()} laser table {cl} {r["t_mm"][0]:g}-{r["t_mm"][1]:g} mm: {r["kerf_mm"][0]}-{r["kerf_mm"][1]} mm, midpoint (source {r["src"]}; measure yours)'
    return float(m.get("kerf",0.06)),f"machines.json {mn} kerf default (no table row for {cl} {t:g} in - measure a test cut)"
def saw(tool=None):
    p=ref.profile(); tools=p.get("saws",{}); meas=p.get("kerf_measured",{})
    if tool is None and tools: tool=next(iter(tools))
    if tool and f"saw|{tool}" in meas: return float(meas[f"saw|{tool}"]),f"measured test cut ({tool})"
    S=ref.get("shop_reference")["saw_kerf"]
    if tool:
        for r in S:
            if tool.lower() in r.get("tool","").lower() and isinstance(r.get("kerf_in"),(int,float)): return float(r["kerf_in"]),f'{r["tool"]} {r["kerf_in"]} in ({r["src"]})'
    r=S[0]; return float(r["kerf_in"]),f'saw unknown: assumed {r["tool"]} {r["kerf_in"]} in ({r["src"]}) - set yours with tools_setup.py --saw'
if __name__=="__main__":
    a=sys.argv[1:]
    if a[0]=="saw": print(saw(a[1] if len(a)>1 else None))
    else:
        M=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"machines.json"))); print(lookup(a[0],M[a[0]],a[1],a[2]))

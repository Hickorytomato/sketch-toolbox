#!/usr/bin/env python3
"""wood_plan.py VDIR OUT.txt -> hand-tool / table-saw friendly plan for sheet-good and lumber parts:
rip/crosscut list (largest first), dado/rabbet layout measured from part edges, and how to cut them without a CNC."""
import sys,json
V,O=sys.argv[1],sys.argv[2]; d=json.load(open(f"{V}/parts.json")); U=d["params"].get("units","in")
f3=lambda v:f'{v:.3f}"' if U=="in" else f"{v:.1f} mm"
def frac(v):
    if U!="in": return ""
    n=round(v*16); w,r=divmod(n,16); 
    from math import gcd
    g=gcd(r,16) if r else 16; return f' (~{w}{" " if w and r else ""}{f"{r//g}/{16//g}" if r else ""}")'.replace('(~0 ','(~')
L=[f"HAND-TOOL / SHOP PLAN - {d.get('title')}   (units {U}; measure your actual plywood thickness and update the spec)",""]
_buy=[r for r in d.get("cutlist",[]) if "BUY" in str(r.get("notes",""))]
if _buy:
    L.append("0. BUY (store-bought - not printed or cut from sheet):")
    for r in _buy: L.append(f'   - {r["qty"]} x {r["part"]}: {r["material"]}, {r["length"]}  ({r.get("est. cost","")})')
    L.append("")
L.append("1. BREAK DOWN THE SHEETS (circular saw + straightedge or table saw). Rip to width first, then crosscut to length:")
for f in sorted(d["flats"],key=lambda f:-f["w"]*f["h"]):
    L.append(f'   - {f["name"]:10} {f3(max(f["w"],f["h"]))}{frac(max(f["w"],f["h"]))} x {f3(min(f["w"],f["h"]))}{frac(min(f["w"],f["h"]))}  from {f.get("thickness")} {f.get("material")}')
pk=[(f,p) for f in d["flats"] for p in f.get("pockets",[])]
if pk:
    L+=["","2. LAY OUT AND CUT THE DADOS / RABBETS (mark both edges of each with a knife, test-fit with an offcut):"]
    for f in d["flats"]:
        for p in f.get("pockets",[]):
            xs=[q[0] for q in p["poly"]]; ys=[q[1] for q in p["poly"]]; w,h=max(xs)-min(xs),max(ys)-min(ys)
            if w<h: a0,a1,ax="X",(min(xs),max(xs)),"from the left end"
            else: a0,a1,ax="Y",(min(ys),max(ys)),"from the bottom edge"
            run=max(w,h); width=min(w,h); thru=run>=min(f["w"],f["h"])-1e-3 if a0=="Y" else run>=f["h"]-1e-3
            L.append(f'   - {f["name"]}: {f3(width)} wide x {f3(p["depth"])} deep, edges at {f3(a1[0])} and {f3(a1[1])} {ax}{" (through)" if thru else " (stopped)"}')
    L+=["   How: router + straight bit against a clamped straightedge (two passes to depth), or dado stack on the table saw,",
        "   or by hand: knife both walls, saw to depth with a back-saw/kerfing guide, chop out with a chisel, flatten with a router plane."]
L+=["","3. DRY FIT everything, check the case is square (equal diagonals), then glue and clamp. Screw the back on to hold it square.",
    "","CNC users: gcode_wood/ has router programs (outline + pocket toolpaths). Verify tool, feeds and zero in a simulator first."]
open(O,"w").write("\n".join(L)+"\n"); print(O)

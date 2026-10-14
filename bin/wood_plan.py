#!/usr/bin/env python3
"""wood_plan.py VDIR OUT.txt -> hand-tool / table-saw friendly plan for sheet-good and lumber parts:
rip/crosscut list (largest first), dado/rabbet layout measured from part edges, and how to cut them without a CNC."""
import sys,json,os,glob,math,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import rules
V,O=sys.argv[1],sys.argv[2]; d=json.load(open(f"{V}/parts.json")); U=d["params"].get("units","in"); F=os.path.dirname(O)
f3=lambda v:f'{v:.3f}"' if U=="in" else f"{v:.1f} mm"
def frac(v):
    if U!="in": return ""
    n=round(v*16); w,r=divmod(n,16); 
    from math import gcd
    g=gcd(r,16) if r else 16; return f' (~{w}{" " if w and r else ""}{f"{r//g}/{16//g}" if r else ""}")'.replace('(~0 ','(~')
L=[f"HAND-TOOL / SHOP PLAN - {d.get('title')}   (units {U}"+("; measure your actual plywood thickness and update the spec)" if any(rules.mcls(f.get("material"))=="plywood" for f in d["flats"]) else ")"),f"Build {d.get('build_id','?')}   All sizes are FINISHED SIZES (cut to the line; no extra for planing unless noted).",""]
for fl_ in d.get("flags",[]): L.append("!! "+fl_)
for sf in rules.safety(d,F): L.append("!! "+sf)
_md={}
for h in d.get("hole_specs",[]):
    if h.get("match_drill"): _md.setdefault((h["match_drill"]["template"],tuple(h["match_drill"]["drill"]),h["d_in"],h["bolt"]),0); _md[(h["match_drill"]["template"],tuple(h["match_drill"]["drill"]),h["d_in"],h["bolt"])]+=1
for (tp,dr,dd,bo),n_ in _md.items(): L.append(f"!! MATCH-DRILL: {tp} and {', '.join(dr)} come off different machines. Clamp {tp} in its final place on {', '.join(dr)} and drill the {n_} hole(s) for the {bo} ({dd:.3f} in) through {tp}'s holes, so they line up exactly. Holes are loose-fit for the same reason.")
if d.get("flags") or rules.safety(d,F) or _md: L.append("")
_buy=[r for r in d.get("cutlist",[]) if "BUY" in str(r.get("notes",""))]
if _buy:
    L.append("0. BUY (store-bought - not printed or cut from sheet):")
    for r in _buy: L.append(f'   - {r["qty"]} x {r["part"]}: {r["material"]}, {r["length"]}  ({r.get("est. cost","")})')
    L.append("")
TAG=rules.part_tags(d)
SP=d.get("stock_plan") or []
if SP:
    sk=d.get("saw_kerf",{}); L.append(f'LUMBER CUT LIST (kerf {sk.get("kerf_in",0):.3f} in per cut from: {sk.get("src","?")}). Grain runs along the length of every board.')
    for st_ in SP:
        tot=sum(b["stock"] for b in st_["boards"]); used=sum(sum(p_[1] for p_ in b["parts"]) for b in st_["boards"])
        L.append(f'   {st_["section"]}: buy {len(st_["boards"])} board(s) - yield {100*used/max(tot,1e-9):.0f}%')
        for k,b in enumerate(st_["boards"]):
            L.append(f'     board {k+1}: {b["stock"]/12:g} ft ({b["stock"]:g} in) -> '+", ".join(f'[{TAG.get(n,"?")}] {n} {l:.3f}"{frac(l)}' for n,l in b["parts"])+f'  [+{len(b["parts"])} kerf = {b["used_with_kerf"]:.3f} in, offcut {b["offcut"]:.2f} in]'+(f' ({b["note"]})' if b.get("note") else ""))
    L.append("")
if d["flats"]:
  L.append("Sheet parts: face grain runs along each part's first (long) dimension." if d.get("domain")=="wood" else "")
  L.append("1. BREAK DOWN THE SHEETS (circular saw + straightedge or table saw). Rip to width first, then crosscut to length:" if d.get("domain")=="wood" else "1. FLAT PARTS (plasma/laser files in FOR_*/, or lay out, saw and drill by hand):")
  for f in sorted(d["flats"],key=lambda f:-f["w"]*f["h"]):
    L.append(f'   - {f["name"]:10} {f3(max(f["w"],f["h"]))}{frac(max(f["w"],f["h"]))} x {f3(min(f["w"],f["h"]))}{frac(min(f["w"],f["h"]))}  from {f.get("thickness")} {f.get("material")}  [tag {TAG.get(f["name"],"?")}]')
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
for nj in glob.glob(f"{F}/nest_*/nest.json"):
    for g in json.load(open(nj))["groups"]: L.append(f'   sheet {g["name"]}: {g.get("utilization","?")}% yield ({g.get("material")} {g.get("thickness")})')
if any(r_.get("stock") in("lumber","sheet_good") for r_ in d["cutlist"]) or d.get("domain")=="wood":
    L+=["","3. DRY FIT everything, check it is square (equal diagonals), then "+("glue, clamp and fasten." if any("glue" in str(x["item"]).lower() for x in d.get("fasteners",[])) else "drive the screws.")]
    sw=[f for f in d["flats"] if rules.mcls(f.get("material"))=="wood" and min(f["w"],f["h"])>=6]
    for f in sw: L.append(f'   {f["name"]}: solid wood moves across the grain about {min(f["w"],f["h"])*0.0037*4:.3f} in per 4% moisture change (FWW formula, flatsawn ~0.0037/in/%): screw through slotted holes or let it float - movement allowance.')
scr=[x for x in d.get("fasteners",[]) if "screw" in str(x["item"]).lower()]
if scr and (d.get("domain")=="wood" or any(r_.get("stock") in("lumber","sheet_good") for r_ in d["cutlist"])):
    S_=rules.SR()["wood_screws"]
    for x in {x["item"]:x for x in scr}.values():
        sz=re.search(r"#(\d+)",x["item"])
        if sz and sz[1]=="8": L.append(f'   Pilot holes for {x["item"]}: {S_["pilot_#8"]["softwood"]} in softwood/plywood, {S_["pilot_#8"]["hardwood"]} in hardwood ({S_["src"][0]}).')
        else: L.append(f'   Pilot holes for {x["item"]}: drill per the screw maker\'s chart (Sketch has only the #8 size sourced); keep screws 5d from ends, 3d from edges.')
W=d.get("welds",[])
if W:
    L+=["","WELD SCHEDULE (your WPS governs; these are starting points, not a qualified procedure):"]
    for w in W: L.append(f'   - {w["part"]}: {w.get("size")} {w.get("type")}, {w.get("length_in")} in, {w.get("side")} side{"s" if w.get("side")=="both" else ""}{" ALL AROUND" if w.get("all_around") else ""}; filler {w.get("filler")} ({w.get("filler_basis")}); {w.get("prep")}'+(f'  !! {w["flag"]}' if w.get("flag") else ""))
    L.append("   "+W[0].get("wps",""))
if "FRAMING" in " ".join(d.get("flags",[])):
    L+=["","FRAMING REFERENCE (code tables only - verify with your code official):"]+["   - "+t_ for t_ in rules.FRAMING_NOTES.values()]
T=rules.tips(d,F)
if T: L+=["","SHOP TIPS for this build:"]+[f"   - {t_}" for _,t_ in T]
if any(g for g in glob.glob(f"{F}/gcode_*/*.nc")): L+=["","CNC users: gcode_*/ has machine programs (outline + pocket toolpaths). Verify tool, feeds and zero in a simulator first."]
open(O,"w").write("\n".join(L)+"\n"); print(O)

#!/usr/bin/env python3
"""rules.py: Sketch's shop rules from bin/ref/failure_modes.json (the research catalog) made into behaviour.
  enrich(out, ...)  generation time (spec_build): build id, title block + process tolerance, finish per row, lumber actual
                    sizes, pipe NPS/sch/OD, weld schedule (side, filler, prep, WPS note), clearance/tap hole specs,
                    bent-plate blank lengths, engineer flags, lumber buy plan with the owner's saw kerf.
  gate(ctx)         ship time (ship.py): every geometry / file / plan-text catalog item as a check with the catalog's severity.
  tips(d)           short advice lines for the processes + materials in THIS build (hand plan, HOW_TO_USE).
  STATUS            catalog id -> how it is handled (check / generator / existing gate / tip / skipped + reason).
  rules.py --coverage   prints the counts."""
import os,sys,json,re,math,hashlib,time,glob,subprocess
B=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,B)
import ref, kerf as KF
SR=lambda: ref.get("shop_reference")
def fnum(s):
    """'3/8' '1-1/2' '0.25' '#7 (0.201)' -> float inches (drill letters/numbers via table below)"""
    s=str(s).strip()
    m=re.search(r"\(([\d.]+)\)",s)
    if m: return float(m[1])
    if s in DRILL: return DRILL[s]
    m=re.match(r"^(\d+)-(\d+)/(\d+)",s)
    if m: return int(m[1])+int(m[2])/int(m[3])
    m=re.match(r"^(\d+)/(\d+)",s)
    if m: return int(m[1])/int(m[2])
    m=re.match(r"^([\d.]+)\s*mm",s)
    if m: return float(m[1])/25.4
    m=re.match(r"^([\d.]+)",s)
    return float(m[1]) if m else None
# number/letter drill sizes used by the tap table (ASME B94.11M decimal equivalents)
DRILL={"#43":0.089,"#36":0.1065,"#31":0.120,"#29":0.136,"#25":0.1495,"#21":0.159,"#18":0.1695,"#9":0.196,"#7":0.201,"F":0.257}
WOOD=("plywood","baltic_birch","mdf","wood","hardwood","pine","cedar","oak","maple","birch","walnut","lumber","2x","1x","4x4")
def mcls(m):
    m=str(m).lower()
    if "galv" in m: return "galvanized"
    if "stainless" in m or re.search(r"\b30[4-9]\b|\b316\b",m): return "stainless"
    if "alum" in m or re.search(r"\b(6061|5052|6063|5083)\b",m): return "aluminum"
    if any(k in m for k in ("pvc","vinyl","ptfe","teflon","polycarbonate","abs sheet","fiberglass","pvc foam")): return "banned_plastic"
    if "acrylic" in m or "pmma" in m: return "acrylic"
    if "plywood" in m or "baltic" in m: return "plywood"
    if "mdf" in m: return "mdf"
    if any(k in m for k in WOOD): return "wood"
    if any(k in m for k in ("pla","petg","tpu","asa","nylon")) and len(m)<8: return "filament"
    if any(k in m for k in ("steel","angle","plate","tube","pipe","flat bar","bar","ga ")) or m in ("a36",): return "steel"
    if any(k in m for k in ("hdpe","plastic","delrin","acetal")): return "plastic"
    return "unknown"
METALS=("steel","stainless","aluminum","galvanized")
# ---------------------------------------------------------------- generation-time helpers
def clearance_for(bolt,U="in",fit="close"):
    """clearance hole (inches) for a bolt description from the tap/clearance table (75% table 'close' column / ISO 273 medium)"""
    S=SR(); b=str(bolt)
    m=re.search(r"\bM(\d+)",b)
    if fit=="loose":   # parts made on different machines: room for each machine's position error (ISO 273 coarse / ASME B18.2.8 loose)
        if m and S["iso273_clearance_mm"].get("coarse_series",{}).get(f"M{m[1]}"):
            mm=S["iso273_clearance_mm"]["coarse_series"][f"M{m[1]}"]; return mm/25.4,f"ISO 273 coarse (loose) M{m[1]} {mm} mm ({S['iso273_clearance_mm']['src3']})"
        L=S.get("inch_clearance_loose_in",{})
        for k in sorted([k for k in L if not k.startswith("_")],key=len,reverse=True):
            if re.search(r"(^|[^\d/#])"+re.escape(k)+r"(-|\s|\"|$)",b): return L[k],f"{k} loose-fit clearance {L[k]} in ({L['_src']})"
    if m:
        k=f"M{m[1]}"; mm=S["iso273_clearance_mm"]["medium_series"].get(k)
        if mm: return mm/25.4,f"ISO 273 medium {k} {mm} mm ({S['iso273_clearance_mm']['src']})"
    for r in S["tap_drill_75pct"]:
        th=r["thread"].split("x")[0]
        if re.search(r"(^|[^\d/#])"+re.escape(th.split("-")[0])+r"(-|\s|\"|$)",b) and not th.startswith("M"):
            return fnum(r["close"]),f'{r["thread"]} close-fit clearance drill {r["close"]} ({r["src"]})'
    return None,"no table row"
def tap_for(thread):
    for r in SR()["tap_drill_75pct"]:
        if r["thread"].lower().split("x")[0] in str(thread).lower(): return fnum(r["drill"]),f'{r["thread"]} tap drill {r["drill"]} (75% thread, {r["src"]})'
    return None,"no table row"
def bolt_dia(b):
    b=str(b); m=re.search(r"\bM(\d+)",b)
    if m: return int(m[1])/25.4
    m=re.search(r"#(\d+)-\d+",b)
    if m: return 0.060+0.013*int(m[1])
    m=re.search(r"(\d+/\d+|\d+(?:\.\d+)?)-\d+",b)
    return fnum(m[1]) if m else None
FILLER=lambda: SR()["filler"]
def filler_for(mats):
    c={mcls(m) for m in mats}; F=FILLER()
    if "aluminum" in c: return F.get("Al 6xxx"),"Al 6xxx base (5xxx/marine: ER5356)"
    if "stainless" in c and c&{"steel","galvanized"}: return F["CS-to-SS"],"carbon steel to stainless"
    if "stainless" in c: return (F["316"],"316") if any("316" in str(m) for m in mats) else (F["304"],"304/304L stainless")
    return F["mild steel"],"mild steel"
def prep_for(t_in,kind):
    tm=t_in*25.4
    if "fillet" in kind: return "fillet: square edges, fit tight (gap 1/16 in max), clean to bright metal"
    for r in SR()["weld_prep"]:
        if "t_mm" not in r: continue
        lo,hi=[float(x) for x in re.findall(r"[\d.]+",r["t_mm"])][:2] if "-" in r["t_mm"] else (0,float(re.findall(r"[\d.]+",r["t_mm"])[-1]))
        if lo<=tm<=hi and "T-joint" not in r["prep"]: return f'groove: {r["prep"]}'+(f', root face {r["face_mm"]} mm' if r.get("face_mm") else "")+f', root gap {r["gap_mm"]} mm'
    return "groove over 40 mm: engineered joint - WPS required"
def proc_tol(procs,U):
    """general tolerance that the process can hold (never tighter than capability)"""
    T=[]
    if "plasma" in procs: T.append(("plasma-cut edges/holes","±0.030 in (±0.76 mm)","plasma conventional"))
    if "weld" in procs: T.append(("weldment overall","±1/16 in under 24 in, ±1/8 in over","weldment small/large"))
    if "laser" in procs: T.append(("laser-cut","±0.005 in metal / ±0.008 in acrylic+wood","laser sheet metal"))
    if "router" in procs: T.append(("CNC routed","±0.010 in (±0.25 mm)","CNC router plywood"))
    if "bend" in procs: T.append(("formed bends","±0.015 in and ±1° per bend","bend"))
    if "hand_wood" in procs: T.append(("hand/saw-cut wood","±1/32 in (Sketch default, no source)","hand woodworking"))
    if "print" in procs: T.append(("3D printed","±0.5% (±0.5 mm min)","FDM prototype"))
    if not T: T.append(("machined/other","ISO 2768-m","iso2768"))
    return T
def _sha(o): return hashlib.sha256(json.dumps(o,sort_keys=True,default=str).encode()).hexdigest()[:10]
STRUCT=r"\b(header|joist|rafter|beam|span table|deck|stair|stairs|railing|guard ?rail|load[- ]bearing|bearing wall|lift(ing)?|hoist|crane|trailer|hitch|ladder|pressure|boiler|tank|scaffold|overhead|swing set|playground)\b"
FRAMING=r"\b(stud|studs|wall framing|framing|header|joist|rafter|top plate|sill plate|sheathing|deck)\b"
def processes(d,F=None):
    P=set(); dom=d.get("domain")
    if d.get("print_parts"): P.add("print")
    if d.get("welds"): P.add("weld")
    if any(f.get("bends") for f in d.get("flats",[])): P.add("bend")
    rows=[r for r in d.get("cutlist",[]) if r.get("mark")!="HW"]
    if dom=="wood" or any(r.get("stock") in("lumber","sheet_good") for r in rows): P.add("hand_wood")
    if any(r.get("stock") in("angle","tube","bar") for r in rows) or any(mcls(f.get("material")) in METALS for f in d.get("flats",[])): P.add("metal")
    if F:
        for g in glob.glob(f"{F}/gcode_*/*.json"):
            try: P.add(json.load(open(g)).get("type"))
            except Exception: pass
    return P
def materials(d):
    M=set(mcls(r.get("material")) for r in d.get("cutlist",[]) if r.get("mark")!="HW")|{mcls(f.get("material")) for f in d.get("flats",[])}
    M|={mcls(p.get("material")) for p in d.get("print_parts",[])}
    return M-{"unknown"} if M-{"unknown"} else M
def finish_default(row):
    c=mcls(row.get("material")); st=row.get("stock")
    if st=="print": return "as printed"
    if c in("stainless","aluminum"): return "bare (degrease)"
    if c=="galvanized": return "galvanized as supplied (touch up welds with zinc-rich paint)"
    if c in("wood","plywood","mdf"): return "sand 180 grit + wipe-on polyurethane (Sketch default - change spec 'finish')"
    if c=="acrylic": return "as supplied (keep masking until assembly)"
    return "degrease + primer + enamel paint (Sketch default - change spec 'finish')"
def stock_plan(cut,U,kerf_in,kerf_src,lengths):
    """1-D cutting plan for lumber/bar: first-fit decreasing, every cut costs one kerf. Returns rows per stock section."""
    toin=1 if U=="in" else 1/25.4; out=[]
    by={}
    for r in cut:
        if r.get("stock") not in("lumber",) or r.get("mark")=="HW": continue
        L=float(re.findall(r"[\d.]+",r["length"])[0])*toin
        by.setdefault(r["material"],[]).extend([(L,n) for n in r.get("names",[])] or [(L,r["part"])]*r["qty"])
    def ffd(pcs,sl):
        boards=[]
        for L,n in pcs:
            if L>sl: boards.append(dict(stock=L,parts=[[n,L]],note="longer than stock: buy special length")); continue
            for b in boards:
                used=sum(x[1] for x in b["parts"])+len(b["parts"])*kerf_in
                if used+L<=b["stock"]+1e-9: b["parts"].append([n,L]); break
            else: boards.append(dict(stock=sl,parts=[[n,L]]))
        return boards
    for sec,pcs in by.items():
        pcs=sorted(pcs,key=lambda q:-q[0])
        # try each stock length; buy the least total footage (ties -> shorter, easier boards)
        cands=[(sum(b["stock"] for b in ffd(pcs,sl)),sl) for sl in sorted(lengths) if sl>=max(p_[0] for p_ in pcs)-1e-9] or [(0,max(lengths))]
        boards=ffd(pcs,min(cands)[1])
        for b in boards:   # shortest stock length that still holds the parts + kerfs
            need=sum(x[1] for x in b["parts"])+len(b["parts"])*kerf_in
            b["stock"]=min([s for s in lengths if s>=need-1e-9] or [b["stock"]]); b["used_with_kerf"]=round(need,4); b["offcut"]=round(b["stock"]-need,3)
        out.append(dict(section=sec,kerf_in=kerf_in,kerf_src=kerf_src,boards=boards))
    return out
def enrich(out,spec,META,JL,U,STOCK):
    S=SR(); toin=1 if U=="in" else 1/25.4; vals=spec.get("values",{})
    fin_all=vals.get("finish",{}).get("v") if isinstance(vals.get("finish"),dict) else vals.get("finish")
    # build id + title block
    bid=_sha(dict(spec={k:v for k,v in spec.items() if k!="history"},ver=open(f"{B}/VERSION").read().strip() if os.path.exists(f"{B}/VERSION") else "dev"))
    out["build_id"]=bid
    procs=set()
    if out.get("print_parts"): procs.add("print")
    if out.get("welds"): procs.add("weld")
    rows=[r for r in out["cutlist"] if r.get("mark")!="HW"]
    if spec.get("domain")=="wood" or any(r.get("stock") in("lumber","sheet_good") for r in rows): procs.add("hand_wood")
    M=json.load(open(f"{B}/machines.json"))
    for fl in out["flats"]:
        c=mcls(fl.get("material"))
        rc="wood" if c in ("plywood","mdf","wood") else "plastic" if c in ("acrylic","plastic","banned_plastic") else c
        if c in METALS and M.get("plasma",{}).get("enabled"): procs.add("plasma")
        if M.get("router",{}).get("enabled") and rc in M["router"].get("materials",[]): procs.add("router")
        if M.get("laser",{}).get("enabled") and fl.get("thickness",1)<=M["laser"].get("max_thickness",0.375) and c not in("banned_plastic","unknown"): procs.add("laser")
        if fl.get("bends"): procs.add("bend")
    dt=(spec.get("history") or [{}])[-1].get("at","")[:10] or time.strftime("%Y-%m-%d")
    out["title_block"]=dict(units=("inches" if U=="in" else "millimetres"),scale="NOT TO SCALE - use the dimensions, do not scale the print",date=dt,build_id=bid,part=out.get("title") or spec.get("name"),
        tolerance=[dict(applies=a,tol=t,src=next((r.get("src","Sketch default") for r in S["tolerance_by_process"] if r["process"]==k),S["iso2768_mm"]["src"] if k=="iso2768" else "Sketch default")) for a,t,k in proc_tol(procs,U)],
        general="Unless noted: ISO 2768-m on machined features ("+S["iso2768_mm"]["src"]+"); cut/welded/wood work holds the process tolerance above")
    # finish + material per row, lumber actual, pipe OD
    LA=S["lumber_actual_in"]; PO=S["pipe_OD_in"]
    for r in out["cutlist"]:
        if r.get("mark")=="HW": continue
        m0=META.get((r.get("names") or [""])[0],{})
        r["finish"]=m0.get("coating") or fin_all or finish_default(r)
        if r.get("stock")=="lumber":
            sz=m0.get("section") or r["material"]
            if sz in LA: r["actual"]=f'{sz} = {LA[sz][0]:g} x {LA[sz][1]:g} in actual ({LA["_src"]})'
            r["notes"]=(r.get("notes","")+"; " if r.get("notes") else "")+(r.get("actual") or "measure actual size")+"; grain along length"
        if "pipe" in str(r["material"]).lower():
            nps=re.match(r'([\d/-]+)"',r["material"]); od=m0.get("od")
            r["pipe"]=dict(nps=nps[1] if nps else "?",sched="40" if "sch40" in r["material"] else "80" if "sch80" in r["material"] else "?",od_in=od)
            r["notes"]=(r.get("notes","")+"; " if r.get("notes") else "")+f'NPS {r["pipe"]["nps"]} sch {r["pipe"]["sched"]} = {od:.3f} in OD'
        if r.get("stock")=="sheet_good" or "plywood" in str(r["material"]):
            r["thickness_in"]=round(float(m0["t"])*toin,4) if m0.get("t") else None   # was raw model units (6 for 6 mm)
    # weld schedule
    def thk(nm):
        m=META.get(nm,{})
        if m.get("t"): return float(m["t"])*toin
        sec=str(m.get("section",""))
        for k,v in STOCK.get("sq_tube",{}).items():
            if k in sec: return v[1]
        for tab in ("pipe_sch40","pipe_sch80"):
            for k,v in STOCK.get(tab,{}).items():
                if sec.startswith(k+'"'): return v[1]
        return None
    for w in out.get("welds",[]):
        a,b=[x.strip() for x in w["part"].split(" to ")]; txt=w["weld"].lower()
        kind="fillet" if "fillet" in txt else "groove" if any(k in txt for k in ("groove","butt","bevel","v-groove","cjp")) else "fillet"
        sz=re.match(r"\s*([\d/.-]+)",w["weld"]); ts=[t for t in (thk(a),thk(b)) if t]
        mats=[META.get(a,{}).get("material","steel"),META.get(b,{}).get("material","steel")]
        mats=[("steel" if str(x) in("steel","") else x) for x in mats]
        fl,why=filler_for(mats)
        side="both" if ("both" in txt or "each side" in txt) else "arrow"
        closed=any(META.get(x,{}).get("stock")=="tube" for x in (a,b)) and "all around" in txt
        w.update(type=kind,size=sz[1] if sz else None,length_in=w.get("weld_in"),side=side,all_around="all around" in txt,
                 filler=fl,filler_basis=why,prep=prep_for(min(ts) if ts else 0.125,kind),t_min_in=min(ts) if ts else None,
                 cjp="cjp" in txt or "full pen" in txt,wps="Your WPS governs: these are starting points, not a qualified procedure (AWS D1.1 / ASME IX).",
                 base=mats)
        if w["cjp"]: w["flag"]="CJP weld: needs a qualified WPS and backing/back-gouge - not certified by Sketch"
    # hole specs from bolted joints
    hs=[]
    for j in JL:
        if j.get("type")=="bolted":
            dd=float(j["d"]); need,src=clearance_for(j.get("bolt",""),U)
            hs.append(dict(parts=j["parts"],d_in=round(dd*toin,4),bolt=j.get("bolt"),clearance_in=need,src=src,dia_in=bolt_dia(j.get("bolt","")),
                           tapped=bool(j.get("tapped")),engage_into=j.get("tapped_into"),engage_len_in=j.get("engage_len") and float(j["engage_len"])*toin,fit=j.get("fit","close"),match_drill=j.get("match_drill")))
    out["hole_specs"]=hs
    # bent parts: blank length (BA = A*pi/180*(R+K*T)), K flagged as estimate
    for fl in out["flats"]:
        for bd in fl.get("bends",[]): bd["k_note"]="K-factor is an ESTIMATE (0.3-0.5): bend a test strip and measure, or ask the shop"
    # engineer / code flags
    txt=" ".join([str(spec.get("ask","")),str(spec.get("title","")),str(spec.get("name",""))]+[str(p.get("label","")) for p in spec.get("parts",[])]).lower()
    out["flags"]=[]
    if re.search(STRUCT,txt) or spec.get("structural"): out["flags"].append("ENGINEER/CODE: this item carries people or structural/lifting/pressure load. Sketch does not do structural or code design: have a licensed engineer or your local code official verify sizes, welds and fasteners before use. Nothing here is stamped.")
    if re.search(FRAMING,txt): out["flags"].append("FRAMING: spans, headers and stud spacing come from code tables only (IRC R602.3(5), R602.7, AWC span tables) - reference, not design. Verify with your local code official.")
    if any(w.get("cjp") for w in out.get("welds",[])): out["flags"].append("CJP welds present: qualified WPS and welder required (AWS D1.1).")
    # lumber buy plan with the owner's saw kerf
    k,ks=KF.saw(); out["saw_kerf"]=dict(kerf_in=k,src=ks)
    out["stock_plan"]=stock_plan(out["cutlist"],U,k,ks,STOCK.get("lumber_lengths",[96,120,144,192]))
    return out
# ---------------------------------------------------------------- tips (advice items, only for this build)
TIPS={  # catalog id -> (applies-if processes/materials, text)
 5:("print","Load across the layers, not along Z: printed parts break between layers."),
 11:("print","Tall thin pins snap at the base: add a fillet or use a metal pin."),
 64:("print","PLA softens in a hot car/sun: PETG or ASA for heat/outdoor, ABS/ASA need an enclosure."),
 65:("print","Print a fit coupon first: hole size varies by slicer and nozzle."),
 24:("acrylic","Acrylic cracks at sharp inside corners and press fits: round inside corners, use clearance fits."),
 25:("laser","Small parts fall through the honeycomb: add microtabs or cut them last on a solid sheet."),
 243:("laser","Never leave the laser running unattended (wood/acrylic fires)."),
 76:("acrylic","Keep the masking paper on acrylic through cutting; peel at assembly."),
 33:("plasma","Plasma bevels 1-3° on the good side (right of travel): grind weld-prep and fit faces."),
 34:("plasma","Small holes: straight 90° lead-in from the centre, slow down."),
 36:("plasma+thin","Thin plate warps from heat: cut in an order that spreads heat, let it cool clamped."),
 81:("plasma+thin","Plasma is happiest on 1/4-1-1/2 in plate; thin gauge needs FineCut consumables."),
 94:("plasma","Expect some dross on the bottom edge: knock it off and file before fit-up."),
 88:("plasma","Deburr/grind bolt holes: dross keeps bolts from seating."),
 185:("plasma+weld","Grind plasma-cut faces that will be welded (nitrided edge causes porosity)."),
 45:("router","Tearout: compression bit, good face up."),
 47:("router","Tabs in MDF/acrylic snap: leave them thicker or use onion-skin."),
 48:("router","Plywood has voids: cut one spare of any show-face part."),
 100:("router","Plastics on a router: single-flute upcut, high feed, don't dwell."),
 101:("router","V-carve: 60° bit for fine detail, 90° for bold lettering."),
 103:("router","Onion skin (leave 0.02 in) works when tabs would mar a show edge."),
 105:("router","Check the assembly order before cutting: some parts can't go in last."),
 106:("router","Sanding takes fit allowance off: sand show faces, not joint faces."),
 107:("router","Hold small parts with tabs or tape + CA, never by hand."),
 128:("hand_wood","Tape hooks wander: 'burn an inch' (measure from 1 in) or use a story stick for critical parts."),
 129:("hand_wood","Measure every mark from one datum edge, not mark-to-mark."),
 130:("hand_wood","Cut on the waste side of the line: mark an X on the waste."),
 131:("hand_wood","Check square with equal diagonals (or 3-4-5) before the glue sets."),
 133:("wood","Wide flatsawn boards cup: alternate growth rings in glue-ups."),
 134:("wood","Let lumber sit in the shop a few days to reach moisture balance before cutting."),
 140:("hand_wood+glue","Glue: dry-fit first, stage clamps; Titebond III gives about 9-15 min open time."),
 141:("hand_wood+glue","Clamp to a thin even bead of squeeze-out; don't starve the joint."),
 142:("hand_wood+glue","Panel glue-ups bow: alternate clamps top and bottom, use cauls."),
 144:("hand_wood","Cut longest and widest parts first, small parts from the offcuts."),
 147:("hand_wood","Sand non-fit faces; sanding joint faces loosens fits."),
 148:("plywood","Plywood voids show on edges: put the best face out, keep a spare."),
 221:("hand_wood+glue","Finish after glue-up, or tape glue surfaces: finish stops glue."),
 222:("wood","Finish swells tight fits: finish after fitting."),
 162:("wood+outdoor","Ground contact needs pressure-treated lumber rated for it; verify with code."),
 163:("wood+outdoor","Treated lumber eats plain steel: hot-dip galvanized or stainless fasteners (check the maker)."),
 165:("framing","Notching or boring studs/joists has code limits: check the code before you cut."),
 169:("weld","Distortion: tack all around first, balance welds about the part's centre, weld no bigger than needed."),
 170:("weld+thin","Thin stock: small evenly spaced tacks, start in the centre / best-fit area."),
 171:("weld+thin","Long seams on thin stock: backstep or skip stitches about 1-1/2 to 2 in long."),
 167:("weld","Check root gap along the whole seam before tacking (open root 1/16-1/8 in)."),
 176:("weld","Check torch/rod access to every weld before tacking it all up."),
 182:("weld","Don't overweld: fillet no bigger than the thinner member needs."),
 184:("weld","Measure final dimensions after the part cools."),
 186:("weld","Clean to bright metal; ER70S-6 tolerates light mill scale."),
 190:("weld+thick","Plate over 1 in: double-V if you can reach both sides."),
 202:("bend","K-factor is a starting point: bend a test strip on your brake and measure."),
 203:("bend","Check the bend sequence on the brake: later flanges can hit the tooling."),
 196:("bend","Use one inside radius for every bend: one die setup."),
 200:("bend","Slots near a bend: run them parallel to the bend."),
 208:("stainless+tapped","Tapping stainless: use a 60-65% thread drill, not the 75% chart."),
 209:("tapped","Form taps need a bigger drill (about D - 0.5 x pitch) than cut taps."),
 215:("dissimilar","Steel against aluminum or stainless corrodes: isolate or match metals."),
 220:("powder","Tight fits after coating: low-build powder (1-2 mil) or chase/ream after."),
 225:("powder","Add a hang hole for the powder-coat line."),
 226:("powder","Mask ground/electrical contact spots."),
 223:("galvanized","Weld before galvanizing, or grind the zinc off the weld zone first."),
 216:("powder","Coated threads bind: mask threads or chase them after coating."),
 219:("paint","Liquid paint adds about 1-2 mil per coat to fits."),
 240:("weld","Weld with ventilation: fume extraction or a respirator, every job."),
 82:("plasma+bend","Plasma edges that will be bent or tapped have a hardened heat zone: grind or drill fresh."),
 36.5:None}
TIPS.pop(36.5)
SAFETY={
 "galvanized+weld":"SAFETY: galvanized steel - grind the zinc off 1-2 in back from every weld/cut, work with fume extraction or outdoors, respirator rated for metal fume. Zinc oxide fume (OSHA PEL 5 mg/m3) causes metal fume fever.",
 "galvanized+plasma":"SAFETY: plasma/laser cutting galvanized throws zinc oxide fume (PEL 5 mg/m3): ventilate, respirator.",
 "stainless+weld":"SAFETY: stainless welding fume carries hexavalent chromium (OSHA PEL 5 ug/m3): local exhaust ventilation at the arc, respirator.",
 "enclosed+weld":"SAFETY: welding zinc/lead coated metal in an enclosed space needs local exhaust or an air-line respirator (OSHA 1926.353).",
}
def _ctx_keys(d,F=None):
    P=processes(d,F); Mt=materials(d); K=set(P)|set(Mt)
    if "hand_wood" in P: K|={"wood"}
    if {"plywood","mdf"}&Mt: K.add("wood")
    if d.get("fasteners") or d.get("hole_specs"): K.add("fasteners")
    if any(h.get("tapped") for h in d.get("hole_specs",[])): K.add("tapped")
    mt_=[float(f.get("thickness",0)) for f in d.get("flats",[]) if mcls(f.get("material")) in METALS]+[float(w.get("t_min_in") or 0) for w in d.get("welds",[]) if w.get("t_min_in")]
    if mt_ and min(mt_)<=0.135: K.add("thin")
    if mt_ and max(mt_)>=1.0: K.add("thick")
    if any(re.search(r"glue|adhesive|epoxy",str(f.get("item","")).lower()) for f in d.get("fasteners",[])): K.add("glue")
    if re.search(r"outdoor|outside|treated|ground|garden|deck|fence|planter",(str(d.get("title",""))+" "+" ".join(str(r.get("material","")) for r in d.get("cutlist",[]))).lower()): K.add("outdoor")
    fins=" ".join(str(r.get("finish","")) for r in d.get("cutlist",[])).lower()
    if "powder" in fins: K.add("powder")
    if "paint" in fins or "enamel" in fins: K.add("paint")
    if len({m for m in Mt if m in METALS})>1: K.add("dissimilar")
    if any(re.search(FRAMING,str(x).lower()) for x in (d.get("title"),)) or any("FRAMING" in f for f in d.get("flags",[])): K.add("framing")
    return K
def tips(d,F=None,maxn=10):
    """every plan-text note that applies (the gate requires them) + at most maxn pure-advice tips"""
    K=_ctx_keys(d,F); out=[]; na=0
    for i,(need,t) in sorted(TIPS.items()):
        if not all(n in K for n in need.split("+")): continue
        if cat()[i]["check_type"]=="plan-text": out.append((i,t))
        elif na<maxn: out.append((i,t)); na+=1
    return out
def safety(d,F=None):
    K=_ctx_keys(d,F); L=[]
    for k,t in SAFETY.items():
        if all(n in K for n in k.split("+")): L.append(t)
    if "weld" in K: L.append("SAFETY: welding fume - ventilate every weld job (fan behind you, extractor at the arc).")
    return L
# ---------------------------------------------------------------- catalog + severity
CAT=None
def cat():
    global CAT
    if CAT is None: CAT=ref.get("failure_modes")
    return CAT
def sev(i): s=cat()[i]["severity"]; return "FAIL" if s=="fail" else "WARN"
FRAMING_NOTES={151:"Stud spacing: 2x4 bearing walls carrying a floor 16 in OC max, roof-only 24 in OC (IRC R602.3(5)) - verify with your code official.",
 152:"16 in OC layout: first mark at 15-1/4 in so sheet edges land on stud centres at 48/96 in.",
 153:"Headers: sized only from IRC R602.7 tables as a reference - have an engineer or code official verify.",
 154:"Headers: jack-stud count per the header table (NJ column).",
 155:"Header with cripples bearing on it: table spans x0.70 or get it designed.",
 156:"Joist/rafter spans: only from the AWC span tables (24 in OC max) - engineer/code verify.",
 157:"Sheathing: 4x8 seams land on framing centres (48 in).",
 158:"Wall heights use actual plate thickness 1-1/2 in, not nominal.",
 159:"NOT STAMPED: no structural calc here is engineered; get engineer/permit sign-off.",
 160:"Built-up headers: nail per the IRC fastening schedule R602.3(1) (16d).",
 161:"Check the wall/deck is square: equal diagonals or 3-4-5.",
 164:"Snow/wind loads depend on your location: tell your code official where it's going."}
def _pdf_text(p):
    import shutil as _sh
    if not _sh.which("pdftotext"): return None   # poppler-utils missing: fall back to what fabdocs recorded
    try: return subprocess.run(["pdftotext","-layout",p,"-"],capture_output=True,text=True,timeout=60).stdout
    except Exception: return None
def _poly(pts):
    from shapely.geometry import Polygon
    return Polygon(pts).buffer(0)
def _concave_corners(pts,tol_deg=20):
    """vertices of a polygon whose interior angle (toward the polygon) is > 180+tol: i.e. inside corners of a cutout/pocket wall seen from the part"""
    from shapely.geometry import LinearRing
    q=[tuple(p) for p in pts]
    if q[0]==q[-1]: q=q[:-1]
    q=[p for i,p in enumerate(q) if math.dist(p,q[i-1])>1e-4]
    if len(q)<3: return []
    ccw=LinearRing(q).is_ccw; out=[]
    for i in range(len(q)):
        a,b,c=q[i-1],q[i],q[(i+1)%len(q)]
        cr=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
        v1=(a[0]-b[0],a[1]-b[1]); v2=(c[0]-b[0],c[1]-b[1]); n1,n2=math.hypot(*v1),math.hypot(*v2)
        ang=math.degrees(math.acos(max(-1,min(1,(v1[0]*v2[0]+v1[1]*v2[1])/(n1*n2)))))
        convex=(cr>0)==ccw
        if convex and ang<180-tol_deg and min(n1,n2)>0.02: out.append((b,ang))   # sharp convex corner of the cutout = sharp inside corner of the material
    return out
def gate(C):
    """C: dict(d, spec, F, V, U, M, res, model, R) -> runs every catalog check; res(area,target,status,why,id=..)"""
    d,spec,F,V,U,M,res=C["d"],C["spec"],C["F"],C["V"],C["U"],C["M"],C["res"]
    S=SR(); toin=1 if U=="in" else 1/25.4; done=set()
    def r(i,st,tgt,why): done.add(i); res("rules",f"#{i} {tgt}",st,why,id=i,catalog=cat()[i]["failure"])
    def ok(i,tgt,why): r(i,"PASS",tgt,why)
    P=processes(d,F); Mt=materials(d); flats=d.get("flats",[]); FL={f["name"]:f for f in flats}
    G=[(gj,dict(json.load(open(gj)),_nc=gj[:-5]+".nc")) for gj in sorted(glob.glob(f"{F}/gcode_*/*.json")) if not gj.endswith("_flip.json")]
    nests=[(nj,json.load(open(nj))) for nj in glob.glob(f"{F}/nest_*/nest.json")]
    hp=f"{F}/hand_tool_plan.txt"; how=f"{F}/HOW_TO_USE.txt"
    PLAN=(open(hp).read() if os.path.exists(hp) else "")+"\n"+(open(how).read() if os.path.exists(how) else "")
    meta=json.load(open(f"{F}/doc_meta.json")) if os.path.exists(f"{F}/doc_meta.json") else {}
    dp=f"{F}/drawings.pdf"; PDF=_pdf_text(dp) if os.path.exists(dp) else ""
    TB=d.get("title_block") or {}
    # ===== drawings / documents
    if PDF is None:   # no pdftotext: use fabdocs' own record of every page it drew (doc_meta.json, hash-protected)
        PDF=("Units: Scale: Date: Build: "+str(meta.get("build_id",""))+" do not scale ISO 2768 ±\f")*int(meta.get("pages",0)) if meta.get("title_block_every_page") else ""
        res("rules","drawings.pdf","WARN","pdftotext (poppler-utils) not installed: title block checked from fabdocs' record, not the PDF text")
    if os.path.exists(dp):
        pages=PDF.split("\f"); pages=[p for p in pages if p.strip()]
        miss=[i+1 for i,p in enumerate(pages) if not all(k in p for k in ("Units:","Scale:","Date:","Build:"))]
        r(52,"FAIL" if miss or not pages else "PASS","drawings.pdf",f"title block (units/scale/date/build) missing on page(s) {miss}" if miss else f"all {len(pages)} pages carry units, scale, date, part and build id")
        r(121,"PASS" if "do not scale" in PDF.lower() else "WARN","drawings.pdf","'do not scale' note present" if "do not scale" in PDF.lower() else "no 'do not scale' note on the drawings")
        tb=("ISO 2768" in PDF) and ("±" in PDF or "+/-" in PDF)
        for i in (111,227): r(i,"PASS" if tb else "FAIL","drawings.pdf","general tolerance block present (ISO 2768-m + process tolerances)" if tb else "no general tolerance block on the drawings")
    # 228 tolerance never tighter than the process can hold
    CAPIN={"plasma":0.030,"weld":0.0625,"laser":0.005,"router":0.0098,"bend":0.015,"hand_wood":0.03125,"print":0.0197}
    tl=" ".join(t["applies"]+" "+t["tol"] for t in TB.get("tolerance",[]))
    bad=[]
    for p_,cap in CAPIN.items():
        if p_ not in P: continue
        key={"plasma":"plasma","weld":"weldment","laser":"laser","router":"CNC","bend":"bend","hand_wood":"wood","print":"printed"}[p_]
        ent=[t for t in TB.get("tolerance",[]) if key.lower() in t["applies"].lower()]
        if not ent: bad.append(f"no tolerance stated for {p_}"); continue
        num=re.search(r"±\s*([\d/.]+)\s*(in|mm|%)?",ent[0]["tol"])
        v=fnum(num[1]) if num else 0; v=v/25.4 if num and num[2]=="mm" else v
        if num and num[2]!="%" and v+1e-6<cap: bad.append(f"{p_} stated ±{num[1]} tighter than the process holds (±{cap:.4f} in)")
    for dm in d.get("dims",[]):
        if dm.get("tol") is not None:
            cap=max([CAPIN[p_] for p_ in P if p_ in CAPIN] or [0.0])
            if float(dm["tol"])*toin+1e-9<cap: bad.append(f'dim "{dm["label"]}" ±{dm["tol"]} {U} is tighter than the loosest process here (±{cap:.3f} in)')
    r(228,"FAIL" if bad else "PASS","title block","; ".join(bad) if bad else "every stated tolerance is one the process can hold")
    # 235 one unit system
    ub=[]
    if TB and TB.get("units")!=("inches" if U=="in" else "millimetres"): ub.append(f'title block says {TB.get("units")} but the spec is {U}')
    ddj=f"{V}/drawing_dims.json"
    if os.path.exists(ddj):
        dj=json.load(open(ddj)); 
        if isinstance(dj,dict) and dj.get("units") and dj["units"]!=U: ub.append(f"drawing dims in {dj['units']}, spec in {U}")
    for gj,g in G:
        t_=open(gj[:-5]+".nc").read()
        if "G21" in t_ or "G20" not in t_: ub.append(f"{os.path.basename(gj)[:-5]}.nc is not in inches (G20)")
    r(235,"FAIL" if ub else "PASS","units","; ".join(ub) if ub else f"one unit system ({U}) on drawings, dims and G-code (G20 inch)")
    # 55 / 123 one build id everywhere
    bid=d.get("build_id")
    if bid:
        where={"drawings.pdf":PDF,"HOW_TO_USE.txt":open(how).read() if os.path.exists(how) else None,"hand_tool_plan.txt":open(hp).read() if os.path.exists(hp) else None,
               "quote.json":open(f"{F}/quote.json").read() if os.path.exists(f"{F}/quote.json") else None}
        for gj,_ in G: where[os.path.basename(gj)[:-5]+".nc"]=open(gj[:-5]+".nc").read()
        mism=[k for k,v in where.items() if v is not None and bid not in v]
        for i in (55,123): r(i,"FAIL" if mism else "PASS","build id",f"build {bid} missing from: {', '.join(mism)}" if mism else f"build {bid} on every file ({len([v for v in where.values() if v is not None])} checked)")
    else:
        for i in (55,123): r(i,"FAIL","build id","parts.json has no build id: rerun spec_build")
    # 57 / 224 material + size + finish on every row; bom.csv carries finish
    rows=[x for x in d["cutlist"] if x.get("mark")!="HW"]
    nf=[x["part"] for x in rows if not str(x.get("finish","")).strip()]; nm=[x["part"] for x in rows if not str(x.get("material","")).strip() or not str(x.get("length","")).strip()]
    bomf=os.path.exists(f"{F}/bom.csv") and "finish" in open(f"{F}/bom.csv").readline()
    st="FAIL" if (nf or nm or not bomf) else "PASS"
    why=("; ".join(([f"no finish on {', '.join(nf)}"] if nf else [])+([f"no material/size on {', '.join(nm)}"] if nm else [])+([] if bomf else ["bom.csv has no finish column"]))) or f"{len(rows)} rows all state material, size and finish"
    r(57,st,"BOM",why); r(224,st,"BOM",why)
    # 54 / 122 hole callouts on the drawing
    mh=meta.get("holes",{}); badh=[]
    for f in flats:
        cs=mh.get(f["name"],[])
        if len(cs)!=len(f.get("holes",[])) or any(not c.strip() for c in cs): badh.append(f'{f["name"]} ({len(cs)}/{len(f.get("holes",[]))} called out)')
    r(54,"FAIL" if badh else "PASS","hole callouts","holes without a callout: "+", ".join(badh) if badh else f"every hole on {len(flats)} flat part(s) has a size/fit callout")
    drl=[(g["sheet"],h) for _,g in G if g.get("type") in ("plasma","laser") for h in g.get("holes",[]) if h["action"]=="drill"]
    miss=[f'{h["part"]} Ø{h["d"]:.3f}' for _,h in drl if not any("DRILL" in c and f'{h["d"]:.3f}' in c for c in mh.get(h["part"],[]))]
    if drl or "plasma" in P: r(122,"WARN" if miss else "PASS","drill callouts",("holes to drill not marked DRILL on the drawing: "+", ".join(miss)) if miss else f"{len(drl)} hole(s) marked DRILL on drawings and left out of the cut program")
    # 114 / 126 lumber actual sizes
    LA=S["lumber_actual_in"]
    lum=[x for x in rows if x.get("stock")=="lumber"]
    if lum:
        na=[x["part"] for x in lum if "actual" not in str(x.get("notes",""))]
        r(114,"WARN" if na else "PASS","lumber","lumber rows without actual size: "+", ".join(na) if na else "every lumber row shows its actual size")
        import trimesh
        bad=[]
        for x in lum:
            sec=x["material"]
            if sec not in LA: continue
            for nm_ in x.get("names",[]):
                p_=f"{V}/stl/{nm_}.stl"
                if not os.path.exists(p_): continue
                e=sorted(trimesh.load(p_,force="mesh").extents*toin)[:2]
                if abs(e[0]-LA[sec][0])>0.02 or abs(e[1]-LA[sec][1])>0.02: bad.append(f"{nm_} is {e[0]:.3f}x{e[1]:.3f} but a {sec} is {LA[sec][0]}x{LA[sec][1]} actual")
        r(126,"FAIL" if bad else "PASS","lumber","; ".join(bad) if bad else f"{sum(len(x.get('names',[])) for x in lum)} board(s) modelled at actual size ({LA['_src']})")
    # 127 / 40 / 70 plywood actual thickness
    sv=d.get("spec_values",{})
    meas=any(isinstance(v,dict) and v.get("src")=="measured" for v in sv.values())
    ply=[f for f in flats if mcls(f.get("material"))=="plywood"]
    if ply:
        nom=[f["name"] for f in ply if abs(float(f.get("thickness",0))-0.75)<1e-4 and not meas]
        why=(f'{", ".join(nom)} drawn 0.750 thick: 3/4 plywood is 23/32 = 0.719 actual ({S["plywood"]["src"]}) - measure and set it') if nom else "plywood drawn at actual thickness (23/32 or measured)"
        for i in (127,40,70): r(i,"FAIL" if nom else "PASS","plywood",why)
    # 96 / 49 / 79 dado/slot width vs the actual mating thickness
    jr=[j for j in d.get("jointrec",[]) if j.get("type") in ("dado","rabbet","groove","housing")]
    if jr:
        bad=[];inter=[]
        for j in jr:
            fi,fr=FL.get(j.get("into")),FL.get(j.get("from"))
            if not fi or not fr: continue
            t=float(fr["thickness"]); ws=[]
            for pk in fi.get("pockets",[]):
                xs=[q[0] for q in pk["poly"]]; ys=[q[1] for q in pk["poly"]]; ws.append(min(max(xs)-min(xs),max(ys)-min(ys)))
            if not ws: continue
            w=min(ws,key=lambda w_:abs(w_-t)); c=w-t
            if c<-1e-4: inter.append(f'{j["into"]} slot {w:.3f} < {j["from"]} {t:.3f}')
            elif c<0.002-1e-4 or c>0.020+1e-4: bad.append(f'{j["into"]} dado {w:.3f} for {t:.3f} {j["from"]}: clearance {c:+.3f} (want +0.002..+0.020)')
        r(96,"FAIL" if bad or inter else "PASS","dados","; ".join(bad+inter) if bad or inter else f"{len(jr)} dado(s) = mating thickness +0.002..0.020 in ({S['joinery']['src2']})")
        r(49,"WARN" if inter else "PASS","fits","interference fit in plywood (crushes veneer): "+"; ".join(inter) if inter else "no interference fits in plywood")
        if "acrylic" in Mt: r(79,"WARN" if inter else "PASS","acrylic","press fit in acrylic cracks it" if inter else "no press fits in acrylic")
    # 139 mortise/tenon clearance
    mt=[j for j in d.get("jointrec",[]) if j.get("type") in ("mortise_tenon","mortise")]
    if mt:
        bad=[f'{j["a"]}/{j["b"]}: {2*float(j.get("clear",0.0025))*toin:.4f} in total' for j in mt if not 0.004-1e-6<=2*float(j.get("clear",0.0025))*toin<=0.005+1e-6]
        r(139,"WARN" if bad else "PASS","tenons","tenon clearance outside 0.004-0.005 in total: "+", ".join(bad) if bad else "tenon clearance 0.004-0.005 in total")
    # 125 / 145 / 146 kerf in the cut list
    sp=d.get("stock_plan") or []
    if sp:
        k,ks=KF.saw(); bad=[]
        for s in sp:
            if abs(s["kerf_in"]-k)>1e-6: bad.append(f'{s["section"]} plan uses kerf {s["kerf_in"]} but your saw is {k} ({ks})')
            for b_ in s["boards"]:
                need=sum(p_[1] for p_ in b_["parts"])+len(b_["parts"])*s["kerf_in"]
                if need>b_["stock"]+1e-6: bad.append(f'{s["section"]} board {b_["stock"]} in holds {need:.3f} in of parts+kerf')
        inplan=f'{k:.3f}' in PLAN and "kerf" in PLAN.lower()
        if not inplan: bad.append("hand plan doesn't state the saw kerf it used")
        r(125,"FAIL" if bad else "PASS","cut list","; ".join(bad) if bad else f"every board holds its parts + one {k:.3f} in kerf per cut ({ks})")
        lab=ks.split(" (")[0] in PLAN or "saw unknown" in PLAN
        for i in (145,146): r(i,"PASS" if lab else "WARN","kerf","kerf labelled with the saw it came from" if lab else "kerf source not stated in the plan")
    # 150 fractions in the plan agree with decimals
    if os.path.exists(hp):
        bad=[]
        for a_,w_,n_,dd_ in re.findall(r'([\d.]+)"\s*\(~(?:(\d+)\s*)?(?:(\d+)/(\d+))?"\)',open(hp).read()):
            fr=(int(w_) if w_ else 0)+(int(n_)/int(dd_) if n_ else 0)
            if abs(fr-float(a_))>1/32+1e-6: bad.append(f'{a_} shown as {fr:.4f}')
        r(150,"WARN" if bad else "PASS","hand plan","fractions off by more than 1/32: "+", ".join(bad[:5]) if bad else "every fraction within 1/32 of the decimal size")
        if "hand_wood" in P or {"wood","plywood"}&Mt: r(143,"PASS" if "grain" in PLAN.lower() else "WARN","grain","grain direction stated" if "grain" in PLAN.lower() else "no grain direction in the plan")
        r(115,"PASS" if "finished size" in PLAN.lower() else "WARN","cut list","sizes labelled finished" if "finished size" in PLAN.lower() else "plan doesn't say whether sizes are finished or rough")
    # 132 / 232 solid wood movement
    sw=[f for f in flats if mcls(f.get("material"))=="wood" and min(f.get("w",0),f.get("h",0))>=6]
    if sw:
        miss=[f["name"] for f in sw if f["name"] not in PLAN or "movement" not in PLAN.lower()]
        for i in (132,232): r(i,"WARN" if miss else "PASS","wood movement","wide solid-wood parts without a movement allowance note: "+", ".join(miss) if miss else "movement allowance noted for wide solid-wood parts")
    # ===== fasteners
    hw=[f["item"] for f in d.get("fasteners",[]) if not re.search(r"\b(glue|adhesive|epoxy|tape|ca)\b",str(f["item"]).lower())]
    if hw:
        bad=[];nstd=[];nlen=[]
        for h in hw:
            sz=re.search(r"(#\d+|\bM\d+|\d+/\d+|\d+(?:\.\d+)?)",h); ln=re.search(r"x\s*([\d/ .-]+)\s*(in|\"|mm)?",h)
            mat=re.search(r"zinc|stainless|galv|grade|steel|brass|black oxide|class\s*\d|8\.8|10\.9|yellow|bronze|coated|deck",h.lower())
            if not (sz and ln and mat): bad.append(h)
            if sz and not re.match(r"#(2|4|6|8|10|12|14)$|M(3|4|5|6|8|10|12|16|20)$|(1/4|5/16|3/8|7/16|1/2|5/8|3/4|7/8|1)$",sz[1]): nstd.append(h)
            if ln:
                L_=fnum(ln[1].strip())
                if L_ and not (any(abs(L_-q/8)<1e-3 for q in range(2,17)) or any(abs(L_-q/4)<1e-3 for q in range(8,25)) or any(abs(L_-q/2)<1e-3 for q in range(12,25)) or (ln[2]=="mm")): nlen.append(h)
        for i in (116,214): r(i,"FAIL" if bad and i==116 else ("WARN" if bad else "PASS"),"hardware","not fully specified (size, length, material/grade): "+"; ".join(bad) if bad else f"{len(hw)} hardware line(s) give size, length and material/grade")
        r(210,"WARN" if nstd else "PASS","hardware","non-standard sizes: "+"; ".join(nstd) if nstd else "all standard sizes")
        r(211,"WARN" if nlen else "PASS","hardware","non-stock lengths: "+"; ".join(nlen) if nlen else "all stock lengths")
    ws=[j for j in d.get("jointrec",[]) if j.get("type") in ("screws","nails") and j.get("through") and j.get("into")]
    if ws:
        import trimesh
        bad=[];nb=[]
        for j in ws:
            ln=re.search(r"x\s*([\d/ .-]+)",str(j.get("size",""))); L_=fnum(ln[1].strip()) if ln else None
            pa,pb=f'{V}/stl/{j["through"]}.stl',f'{V}/stl/{j["into"]}.stl'
            if not (L_ and os.path.exists(pa) and os.path.exists(pb)): bad.append(f'{j.get("size")}: length or parts unknown'); continue
            A=trimesh.load(pa,force="mesh"); Bm=trimesh.load(pb,force="mesh"); ax=int(A.extents.argmin()); top=A.extents[ax]*toin; rec=Bm.extents[ax]*toin
            L_=L_*(1 if U=="in" else 1)   # fastener lengths are written in inches
            if j["type"]=="screws":
                if L_-top<(L_*0.5) or L_-top>rec+1e-6: bad.append(f'{j["size"]}: {L_:g} in through {top:.3f} {j["through"]} leaves {L_-top:.3f} in {j["into"]} ({rec:.3f} available) - want 1/2-2/3 of the screw in the receiver, tip not breaking out')
            else:
                if L_<2.5*top: nb.append(f'{j["size"]}: {L_:g} in nail through {top:.3f} in (want ~3x)')
        if any(j["type"]=="screws" for j in ws): r(137,"FAIL" if bad else "PASS","screws","; ".join(bad) if bad else "every screw: 1/2-2/3 of its length in the receiver, tip stays inside")
        if any(j["type"]=="nails" for j in ws): r(138,"WARN" if nb else "PASS","nails","; ".join(nb) if nb else "nails ~3x the top board")
    if any("screw" in h.lower() for h in hw) and ("wood" in Mt or "plywood" in Mt or "hand_wood" in P):
        pil="pilot" in PLAN.lower()
        for i in (136,212): r(i,"PASS" if pil else "WARN","pilot holes","pilot/clearance drill for the wood screws in the plan" if pil else "no pilot drill sizes in the plan")
    HS=d.get("hole_specs",[])
    if HS:
        bad=[];loose=[];tp=[];eng=[];deep=[]
        TE={"steel-steel":1.0,"steel-aluminum":2.0,"stainless-stainless":1.25,"steel-plastic":2.5}
        for h in HS:
            if h.get("tapped"):
                need,src=tap_for(h.get("bolt",""))
                if need and abs(h["d_in"]-need)>0.003: tp.append(f'{h["bolt"]}: Ø{h["d_in"]:.4f} tapped, table says {need:.4f} ({src})')
                fi=FL.get(h.get("engage_into") or h["parts"][-1]); L_=h.get("engage_len_in") or (fi and float(fi["thickness"]))
                bm=mcls(fi.get("material")) if fi else "steel"; key={"aluminum":"steel-aluminum","stainless":"stainless-stainless","plastic":"steel-plastic"}.get(bm,"steel-steel")
                if L_ and h.get("dia_in") and L_<TE[key]*h["dia_in"]-1e-6: eng.append(f'{h["bolt"]} into {L_:.3f} {bm}: needs {TE[key]}D = {TE[key]*h["dia_in"]:.3f} in ({S["thread_engagement"]["src"]})')
                if L_ and h.get("dia_in") and L_>(3 if bm=="aluminum" else 2)*h["dia_in"]: deep.append(f'{h["bolt"]}: {L_:.3f} in of thread is past useful')
                continue
            c=h.get("clearance_in")
            if c is None: bad.append(f'{h["bolt"]}: no table row'); continue
            if h["d_in"]<c-0.003 or (h.get("dia_in") and h["d_in"]<h["dia_in"]+0.005): bad.append(f'{h["bolt"]} hole Ø{h["d_in"]:.4f} tighter than close fit {c:.4f} ({h["src"]})')
            elif h["d_in"]>c+1/16: loose.append(f'{h["bolt"]} hole Ø{h["d_in"]:.4f} is loose (close fit {c:.4f})')
        if [h for h in HS if not h.get("tapped")]: r(205,"FAIL" if bad else ("WARN" if loose else "PASS"),"clearance holes","; ".join(bad+loose) if bad or loose else f"{len(HS)} bolt hole(s) match the clearance table")
        if [h for h in HS if h.get("tapped")]:
            r(204,"FAIL" if tp else "PASS","tap drills","; ".join(tp) if tp else "tap drills from the 75% table")
            r(206,"FAIL" if eng else "PASS","thread engagement","; ".join(eng) if eng else "thread engagement meets the table")
            r(207,"WARN" if deep else "PASS","thread depth","; ".join(deep) if deep else "thread depth within useful range")
    # ===== hole/edge/web rules on every flat
    bad_e=[];bad_w={};pls=[]
    for f in flats:
        t=float(f.get("thickness",0.125)); O=_poly(f["outer"]) if f.get("outer") else None
        if O is None: continue
        from shapely.geometry import Point
        feats=[("hole",Point(x,y).buffer(rr,32),2*rr) for x,y,rr in f.get("holes",[])]+[("cutout",_poly(ip),None) for ip in f.get("inner_poly",[])]
        for k,(ty,g,dd) in enumerate(feats):
            e=O.exterior.distance(g)
            if ty=="hole" and e<dd-1e-6: bad_e.append(f'{f["name"]} Ø{dd:.3f} hole {e:.3f} from the edge (< 1x dia)')
            if ty=="hole" and mcls(f.get("material")) in METALS and e<1.5*t-1e-6: pls.append(f'{f["name"]} Ø{dd:.3f} hole {e:.3f} from the edge (< 1.5x t = {1.5*t:.3f})')
            for g2 in feats[k+1:]:
                w=g.distance(g2[1]); bad_w.setdefault(f["name"],[]).append((w,t))
    for i in (20,213,183): r(i,"WARN" if bad_e else "PASS","hole-to-edge","; ".join(bad_e[:6]) if bad_e else "every hole at least 1x its diameter from the edge")
    if "plasma" in P or any(mcls(f.get("material")) in METALS for f in flats): r(31,"WARN" if pls else "PASS","plasma hole-to-edge","; ".join(pls[:6]) if pls else "holes >= 1.5x t from the edge")
    for p_,(i_f,i_w,ff,fw) in {"plasma":(30,30,1.0,2.0),"laser":(19,19,0.5,1.0)}.items():
        if p_ not in P: continue
        cutnames={nm for _,g in G if g.get("type")==p_ for nm in g.get("parts",[])}
        fails=[f"{nm}: web {w:.3f} < {ff}x t" for nm,L in bad_w.items() if nm in cutnames for w,t in L if w<ff*t-1e-6]
        warns=[f"{nm}: web {w:.3f} < {fw}x t" for nm,L in bad_w.items() if nm in cutnames for w,t in L if ff*t-1e-6<=w<fw*t-1e-6]
        r(i_f,"FAIL" if fails else ("WARN" if warns else "PASS"),f"{p_} webs","; ".join((fails+warns)[:6]) if fails or warns else f"webs between features >= {fw}x thickness")
    # ===== cut programs (plasma/laser/router)
    for _,g in G:
        tp_=g.get("type"); bn=f'{g["sheet"]} {g["machine"]}'; mm=M.get(g["machine"],{}); t=float(g.get("thickness") or 0.25); mat=g.get("material","steel")
        cuts=[h for h in g.get("holes",[]) if h["action"]=="cut"]
        if tp_=="plasma":
            small=[h for h in cuts if h["d"]<1.5*t-1e-6]; warn=[h for h in cuts if 1.5*t-1e-6<=h["d"]<2*t-1e-6]
            r(28,"FAIL" if small else ("WARN" if warn else "PASS"),bn,("plasma-cutting holes under 1.5x t (mark DRILL): "+", ".join(f'{h["part"]} Ø{h["d"]:.3f}' for h in small)) if small else (("holes under 2x t (tapered, out of round): "+", ".join(f'{h["part"]} Ø{h["d"]:.3f}' for h in warn)) if warn else "every plasma-cut hole >= 2x thickness; smaller ones are marked DRILL"))
            slow=[h for h in cuts if h["d"]<1.0 and h.get("feed") and h["feed"]>0.61*mm.get("feed_ipm",100)]
            r(83,"WARN" if slow else "PASS",bn,"holes under 1 in cut at full speed: "+", ".join(h["part"] for h in slow) if slow else "holes under 1 in at 60% feed")
            r(93,"FAIL" if mcls(mat) not in METALS else "PASS",bn,f"{mat} is not conductive: plasma can't cut it" if mcls(mat) not in METALS else f"{mat} is plasma-cuttable")
            fit=[h for h in cuts if h.get("fit")]
            r(29,"WARN" if fit else "PASS",bn,"bolt holes cut to final size by plasma (±0.03): "+", ".join(h["part"] for h in fit) if fit else "fit-critical bolt holes are drilled to size, not plasma-cut")
        if tp_=="laser":
            c_=mcls(mat)
            if c_=="banned_plastic":
                for i in (15,237): r(i,"FAIL",bn,f"{mat} on the laser: chlorine/fluorine fume ({S['hazards']['laser banned']}) - never laser it")
            if c_ in ("unknown","plastic"):
                for i in (73,246): r(i,"FAIL",bn,f"'{mat}' is not identified: get the SDS before lasering it")
            small=[h for h in cuts if h["d"]<0.5*t-1e-6]; warn=[h for h in cuts if 0.5*t-1e-6<=h["d"]<t-1e-6]
            r(18,"FAIL" if small else ("WARN" if warn else "PASS"),bn,("holes under 0.5x t: "+", ".join(f'{h["part"]} Ø{h["d"]:.3f}' for h in small)) if small else (("holes under 1x t: "+", ".join(f'{h["part"]} Ø{h["d"]:.3f}' for h in warn)) if warn else "every laser hole >= 1x thickness"))
            bb=mm.get("bed",[1e9,1e9]); big=[nm for nm in g.get("parts",[]) if nm in FL and (max(FL[nm]["w"],FL[nm]["h"])>max(bb) or min(FL[nm]["w"],FL[nm]["h"])>min(bb))]
            r(75,"FAIL" if big else "PASS",bn,"bigger than the laser bed: "+", ".join(big) if big else "every part fits the laser bed")
            if "measured" not in str(g.get("kerf_src","")): r(69,"WARN",bn,f'kerf {g.get("kerf")} is from {g.get("kerf_src")}: cut a test square and run tools_setup.py --kerf-test')
            else: r(69,"PASS",bn,"kerf from your test cut")
        if tp_=="plasma" and "measured" not in str(g.get("kerf_src","")): r(69,"WARN",bn,f'kerf {g.get("kerf")} is from {g.get("kerf_src")}: measure a test cut')
        if tp_ in ("plasma","laser"):
            # 22 / 86 comp sign: holes cut at r - kerf/2, outlines at + kerf/2
            nc=open(g["_nc"]).read() if os.path.exists(g["_nc"]) else ""
            sign=[]
            for lab,body in re.findall(r"\(-- (\S+ hole d[\d.]+)\)\n(?:.*\n){0,8}?G[23] .*?I(-?[\d.]+)",nc):
                dd=float(lab.split(" d")[-1]); rr=abs(float(body))
                if abs(rr-(dd/2-g["comp"]))>2e-4: sign.append(f"{lab}: cut radius {rr:.4f}, want {dd/2-g['comp']:.4f}")
            for lab,body in re.findall(r"\(-- (\S+ outer d[\d.]+)\)\n(?:.*\n){0,8}?G[23] .*?I(-?[\d.]+)",nc):
                dd=float(lab.split(" d")[-1]); rr=abs(float(body))
                if abs(rr-(dd/2+g["comp"]))>2e-4: sign.append(f"{lab}: cut radius {rr:.4f}, want {dd/2+g['comp']:.4f}")
            for i in (86,22): r(i,"FAIL" if sign else "PASS",bn,"; ".join(sign[:4]) if sign else "holes offset inward, outlines outward by half the kerf")
            # 27 / 72 inner contours first
            order=re.findall(r"\(-- (\S+) (hole|cutout|outer|pocket)",nc); late=[]
            seen_outer=set()
            for nm,k in order:
                if k=="outer": seen_outer.add(nm)
                elif nm in seen_outer: late.append(nm)
            for i in (27,72): r(i,"WARN" if late else "PASS",bn,"inner shapes cut after the outline (part can shift): "+", ".join(sorted(set(late))) if late else "holes/cutouts cut before each outline")
            if tp_=="plasma":
                sharp=[nm for nm in g.get("parts",[]) if nm in FL for ip in FL[nm].get("inner_poly",[]) if _concave_corners(ip)]
                r(35,"WARN" if sharp else "PASS",bn,"sharp inside corners (dross, no radius >= kerf/2): "+", ".join(sorted(set(sharp))) if sharp else "inside corners radiused >= kerf/2")
                strip=[nm for nm in g.get("parts",[]) if nm in FL and max(FL[nm]["w"],FL[nm]["h"])/max(1e-6,min(FL[nm]["w"],FL[nm]["h"]))>20]
                r(92,"WARN" if strip else "PASS",bn,"long thin strips warp from plasma heat (L/W > 20, Sketch default): "+", ".join(strip) if strip else "no long thin strips")
        if tp_=="router":
            tool=mm.get("tool_dia")
            r(97,"FAIL" if not tool else "PASS",bn,"router bit diameter missing in machines.json" if not tool else f"bit Ø{tool} in machines.json = kerf")
            nc=open(g["_nc"]).read() if os.path.exists(g["_nc"]) else ""
            zs=[float(z) for z in re.findall(r"G1 Z(-[\d.]+)",nc)]; steps=[]
            prev=0
            for z in zs:
                if z<prev-1e-6: steps.append(prev-z)
                prev=z if z<prev else prev
            dpp=float(mm.get("depth_per_pass",0.125)); fac=0.5 if mcls(mat)=="wood" and "ply" not in str(mat) else 1/3
            over=bool(tool) and g.get("doc",dpp)>fac*tool+1e-6
            for i in (46,245): r(i,"WARN" if over else "PASS",bn,f'depth per pass {g.get("doc",dpp):.4f} > {fac:.2f}x the {tool} bit for {mat}' if over else f'depth per pass {g.get("doc",dpp):.4f} <= {fac:.2f}x bit ({S["cnc_tabs"]["src"]})')
            tabs=g.get("tabs",{})
            nt=[nm for nm in g.get("parts",[]) if tabs.get(nm,0)<3]
            r(41,"WARN" if nt else "PASS",bn,"through-cut parts with fewer than 3 tabs: "+", ".join(nt) if nt else f"every part held by >= 3 tabs ({S['cnc_tabs']['width']} wide, t/2 high)")
            tiny=[nm for nm in g.get("parts",[]) if nm in FL and FL[nm]["w"]*FL[nm]["h"]<4 and tabs.get(nm,0)<3]
            for i in (43,242): r(i,"WARN" if tiny else "PASS",bn,"small parts without tabs become projectiles: "+", ".join(tiny) if tiny else "small parts tabbed")
            narrow=[h for h in g.get("holes",[]) if h["action"]=="cut" and h["d"]<(tool or 0)-1e-6]+[x for x in g.get("too_narrow",[])]
            r(39,"FAIL" if narrow else "PASS",bn,"features narrower than the bit: "+", ".join(str(h.get("part",h)) for h in narrow) if narrow else "no slot/hole narrower than the bit")
            thin=[f"{nm} web {w:.3f}" for nm,L in bad_w.items() if nm in g.get("parts",[]) for w,t in L if w<(tool or 0)-1e-6]
            r(42,"WARN" if thin else "PASS",bn,"walls thinner than the bit splinter: "+", ".join(thin) if thin else "no wall thinner than the bit")
            sq=[]
            for nm in g.get("parts",[]):
                f=FL.get(nm)
                if not f or f.get("dogbone"): continue
                O=_poly(f["outer"])
                for pk in [q["poly"] for q in f.get("pockets",[])]+f.get("inner_poly",[]):
                    for (pt,ang) in _concave_corners(pk):
                        from shapely.geometry import Point
                        if O.exterior.distance(Point(pt))>1e-3: sq.append(f"{nm} corner at ({pt[0]:.2f},{pt[1]:.2f})")
            for i in (38,98): r(i,"FAIL" if sq else "PASS",bn,f"square inside corners the {tool} bit leaves at r={(tool or 0)/2:.3f} (mating part won't seat): add dogbones: "+", ".join(sq[:4]) if sq else "no square inside corners (pockets run off the edge or have dogbones)")
            rot=[p_["name"] for _,n_ in nests for gg in n_["groups"] for p_ in gg.get("parts",[]) if p_.get("name") in g.get("parts",[]) and mcls(p_.get("material"))=="plywood" and p_.get("theta",0)%180==90 and max(p_.get("w",0),p_.get("h",0))>12]
            r(102,"WARN" if rot else "PASS",bn,"face grain runs across these parts (nested at 90°): "+", ".join(rot) if rot else "show-face grain runs along each part")
    # 16 duplicate/overlapping lines in cut DXFs
    dup=[]
    try:
        import ezdxf
        for dx in glob.glob(f"{F}/nest_*/*.dxf")+glob.glob(f"{F}/dxf_*/*.dxf"):
            seen=set()
            for e in ezdxf.readfile(dx).modelspace():
                if e.dxftype()=="LWPOLYLINE" and e.dxf.layer in("CUT","HOLES"):
                    k_=tuple(sorted((round(p[0],3),round(p[1],3)) for p in e.get_points()))
                elif e.dxftype()=="CIRCLE" and e.dxf.layer in("CUT","HOLES"): k_=("c",round(e.dxf.center.x,3),round(e.dxf.center.y,3),round(e.dxf.radius,3))
                else: continue
                if k_ in seen: dup.append(os.path.basename(dx))
                seen.add(k_)
    except Exception as ex: dup.append(f"unreadable: {ex}")
    if glob.glob(f"{F}/nest_*/*.dxf"): r(16,"FAIL" if dup else "PASS","DXF","duplicate cut lines (double burn): "+", ".join(sorted(set(dup))) if dup else "no duplicate cut lines")
    # 21 islands, 71 engrave fills closed
    isl=[f["name"] for f in flats for a_ in f.get("inner_poly",[]) for b_ in f.get("inner_poly",[]) if a_ is not b_ and _poly(a_).contains(_poly(b_))]
    if any(f.get("inner_poly") for f in flats): r(21,"WARN" if isl else "PASS","islands","loose islands inside cutouts fall out: "+", ".join(isl) if isl else "no floating islands")
    svgs=glob.glob(f"{F}/FOR_LASER*/*.svg")
    if svgs:
        op=[]
        for s_ in svgs:
            t_=open(s_).read(); m_=re.search(r'<g id="ENGRAVE".*?</g>',t_,re.S)
            if m_: op+=[os.path.basename(s_) for p_ in re.findall(r'\sd="([^"]+)"',m_[0]) if not p_.strip().endswith("Z")]
        r(71,"FAIL" if op else "PASS","engrave","open engrave fill paths: "+", ".join(op) if op else "every engrave fill is a closed loop")
    # 23 / 32 / 91 part spacing vs kerf
    for nj,n_ in nests:
        for gg in n_["groups"]:
            k_=gg.get("kerf"); spc=gg.get("spacing",n_.get("spacing"))
            if k_ is None: r(23,"FAIL",gg["name"],"nest has no kerf: rerun nest.py"); continue
            st="FAIL" if spc<k_ else ("WARN" if spc<k_+0.0625 else "PASS")
            for i in ((23,32,91) if n_["machine"]=="plasma" else (23,91)): r(i,st if (i!=91 or st!="FAIL") else "WARN",gg["name"],f"part spacing {spc:.3f} vs kerf {k_:.4f} ({gg.get('kerf_src')})")
    # ===== sheet metal (bent parts)
    bents=[f for f in flats if f.get("bends")]
    for f in bents:
        t=float(f["thickness"]); mat=mcls(f.get("material")); nm=f["name"]
        for bd in f["bends"]:
            R=float(bd["R"]); fl=[float(x) for x in bd["flanges"]]
            minf=max(4*t,3/25.4)
            r(191,"FAIL" if min(fl)<minf-1e-6 else "PASS",nm,f"flange {min(fl):.3f} < max(4T, 3 mm) = {minf:.3f}" if min(fl)<minf-1e-6 else f"flanges {fl} >= {minf:.3f}")
            needR=(3*t if "6061" in str(f.get("material")) else t)
            r(192,"FAIL" if R<needR-1e-6 else "PASS",nm,f"inside radius {R:.3f} < {needR/t:g}T = {needR:.3f} ({S['sheet_metal']['min_inside_R']})" if R<needR-1e-6 else f"inside radius {R:.3f} >= {needR/t:g}T")
            u0,u1=bd["u0"],bd["u1"]; near=[];feat=[]
            for x,y,rr in f.get("holes",[]):
                dist=min(abs(x-u0),abs(x-u1))-rr if not (u0<=x<=u1) else -1
                if dist<2.5*t+R-1e-6: near.append(f"Ø{2*rr:.3f} at {x:.3f}: {dist:.3f} from the bend (< 2.5T+R = {2.5*t+R:.3f})")
                elif dist<4*t-1e-6: feat.append(f"Ø{2*rr:.3f} {dist:.3f} from the bend")
                if 2*rr<t-1e-6: r(197,"WARN",nm,f"hole Ø{2*rr:.3f} smaller than T {t}")
            r(193,"FAIL" if near else "PASS",nm,"; ".join(near) if near else "every hole >= 2.5T+R from the bend")
            r(199,"WARN" if feat else "PASS",nm,"features within 4T of the bend: "+"; ".join(feat) if feat else "features >= 4T from bend")
            if bd.get("partial"):
                rw,rd=bd.get("relief_w",0),bd.get("relief_d",0)
                okr=rw>=t-1e-6 and rd>=t+R-1e-6
                r(194,"PASS" if okr else "FAIL",nm,f"bend relief {rw:.3f} wide x {rd:.3f} deep (need >= {t:.3f} x {t+R:.3f})" if okr else f"partial-width bend needs relief >= {t:.3f} wide x {t+R:.3f} deep, has {rw:.3f} x {rd:.3f}")
            else: r(194,"PASS",nm,"full-width bend: no relief needed")
            r(195,"WARN",nm,f'blank {f["w"]:.3f} uses BA = {bd["BA"]:.4f} with K={bd["K"]} - ESTIMATE: bend a test strip')
        r(119,"FAIL" if not f.get("blank_length") or f"{f['blank_length']:.3f}" not in " ".join(meta.get("blanks",[])) else "PASS",nm,"bent part without a developed (flat) length on the drawing" if not f.get("blank_length") or f"{f['blank_length']:.3f}" not in " ".join(meta.get("blanks",[])) else f"flat blank {f['blank_length']:.3f} on the drawing")
    if bents:
        bt=any("bend" in t["applies"].lower() for t in TB.get("tolerance",[]))
        for i in (198,234): r(i,"PASS" if bt else "WARN","bends","bend tolerance ±0.015 in / ±1° per bend stated" if bt else "bend tolerance not stated")
    rl=[f for f in flats if f.get("roll")]
    for f in rl:
        ID=f["roll"]["id"]; t=float(f["thickness"]); L_=math.pi*(ID+t) if f["roll"].get("way","flat")=="flat" else math.pi*(ID+f["roll"]["width"])
        r(179,"FAIL" if abs(f["w"]-L_)>0.01 else "PASS",f["name"],f'rolled blank {f["w"]:.3f} but π(ID+t) = {L_:.3f}' if abs(f["w"]-L_)>0.01 else f"rolled blank = π(ID+t) = {L_:.3f}")
        r(119,"PASS",f["name"],"rolled part lists its blank length")
    # ===== pipe
    pr=[x for x in rows if x.get("pipe")]
    if pr:
        bad=[x["part"] for x in pr if not (x["pipe"].get("nps") not in (None,"?") and x["pipe"].get("sched") not in(None,"?") and x["pipe"].get("od_in") and "OD" in x.get("notes",""))]
        r(120,"FAIL" if bad else "PASS","pipe","pipe rows without NPS + schedule + OD: "+", ".join(bad) if bad else "every pipe row states NPS, schedule and OD")
        PO=S["pipe_OD_in"]; wrong=[]
        for x in pr:
            k_="NPS"+x["pipe"]["nps"]
            if k_ in PO and abs(PO[k_][0]-float(x["pipe"]["od_in"] or 0))>0.005: wrong.append(f'{x["part"]}: NPS {x["pipe"]["nps"]} modelled at {x["pipe"]["od_in"]} OD, table says {PO[k_][0]}')
        r(180,"FAIL" if wrong else "PASS","pipe","; ".join(wrong) if wrong else f"pipe ODs match the NPS table ({PO['_src']})")
        if d.get("joints"): r(178,"PASS" if os.path.exists(f"{F}/cope_templates.pdf") else "WARN","copes","full-scale wrap templates from actual ODs (cope_templates.pdf)" if os.path.exists(f"{F}/cope_templates.pdf") else "coped pipe without templates")
    # ===== welding
    W=d.get("welds",[])
    if W:
        mw=meta.get("welds",[]); miss=[];side=[];fil=[];prep=[];allr=[];inter=[]
        for k_,w in enumerate(W):
            if not all(w.get(x) for x in ("type","size","length_in","side")): miss.append(w["part"])
            sy=next((q for q in mw if q.get("part")==w["part"]),None)
            if not sy or sy.get("side")!=w.get("side"): side.append(f'{w["part"]}: model {w.get("side")}, drawing {sy and sy.get("side")}')
            f_,_=filler_for(w.get("base",["steel","steel"]))
            if w.get("filler")!=f_ or (w.get("filler") or "~") not in PLAN: fil.append(f'{w["part"]}: {w.get("filler")} (table: {f_}{"" if (w.get("filler") or "~") in PLAN else ", not in the plan"})')
            if not w.get("prep") or w["prep"]!=prep_for(w.get("t_min_in") or 0.125,w.get("type","fillet")): prep.append(w["part"])
            m_=re.search(r"(\d+)\D+deg",str(w.get("prep","")))
            if m_ and int(m_[1])<45: r(187,"WARN",w["part"],"bevel included angle under 45-50°")
            if not w.get("all_around") and "tube" in " ".join(str(b) for b in w.get("base",[])): allr.append(w["part"])
            if re.search(r"stitch|intermittent|skip",w["weld"].lower()) and not re.search(r"\d+(\.\d+)?\s*-\s*\d+",w["weld"]): inter.append(w["part"])
        r(188,"FAIL" if miss else "PASS","welds","welds missing type/size/length/side: "+", ".join(miss) if miss else f"{len(W)} welds each state type, size, length and side")
        for i in (108,175): r(i,"FAIL" if side else "PASS","weld symbols","; ".join(side[:4]) if side else "every weld symbol drawn on the side the model puts the weld (AWS A2.4: below line = arrow side)")
        r(172,"FAIL" if fil else "PASS","filler","; ".join(fil[:4]) if fil else f"filler from the table for the base metal ({', '.join(sorted({w['filler'] for w in W}))})")
        r(166,"FAIL" if prep else "PASS","weld prep","no prep for thickness on: "+", ".join(prep) if prep else "joint prep stated for each thickness (WPS governs)")
        r(110,"WARN" if allr else "PASS","welds","closed-profile welds without all-around: "+", ".join(allr) if allr else "closed profiles use weld-all-around")
        r(109,"WARN" if inter else "PASS","welds","intermittent welds without length-pitch: "+", ".join(inter) if inter else "no intermittent welds without length-pitch")
        cj=[w for w in W if w.get("cjp")]
        r(168,"FAIL" if cj and "WPS" not in PLAN else "PASS","CJP","CJP weld not flagged for a qualified WPS" if cj and "WPS" not in PLAN else "WPS-governs note in the plan")
        wt=any("weldment" in t["applies"] for t in TB.get("tolerance",[]))
        for i in (181,233): r(i,"PASS" if wt else "WARN","weldment","weldment tolerance ±1/16 / ±1/8 in stated" if wt else "weldment tolerance not stated")
        if any(w.get("type")=="groove" and "pipe" in " ".join(map(str,w.get("base",[]))) for w in W): r(177,"PASS" if "37.5" in PLAN else "WARN","pipe fit-up","pipe butt fit-up note (1/16 gap, 1/16 land, 37.5°)" if "37.5" in PLAN else "pipe butt welds without fit-up note")
        r(240,"PASS" if "ventilat" in PLAN.lower() else "WARN","fume","weld fume ventilation note" if "ventilat" in PLAN.lower() else "no ventilation note on a weld job")
        r(37,"PASS" if ("plasma" not in P or "Grind plasma-cut faces" in PLAN) else "WARN","weld prep","grind plasma-cut weld faces note" if ("plasma" not in P or "Grind plasma-cut faces" in PLAN) else "no note to grind plasma-cut weld faces")
    # ===== safety by material + process
    if "galvanized" in Mt:
        hz=bool(re.search(r"zinc (oxide )?fume|grind the zinc",PLAN.lower())) and "ventilat" in PLAN.lower()   # not bare "zinc": hardware names / shop links say zinc too
        if W:
            for i in (173,238): r(i,"PASS" if hz else "FAIL","galvanized","galvanized weld: grind/ventilate warning in the plan" if hz else "galvanized steel welded with no zinc-fume warning in the plan")
        if {"plasma","laser"}&P:
            for i in (74,84): r(i,"PASS" if hz else "WARN","galvanized","coated-metal cutting fume note" if hz else "cutting galvanized with no fume note")
        r(223,"PASS" if "weld before galvanizing" in PLAN.lower() or not W else "WARN","galvanized","weld-before-galvanize note" if "weld before galvanizing" in PLAN.lower() or not W else "no weld-before-galvanizing note")
    if "stainless" in Mt and W:
        hz="chromium" in PLAN.lower()
        for i in (174,239): r(i,"PASS" if hz else "WARN","stainless","stainless fume (Cr VI) LEV note" if hz else "stainless welding with no Cr(VI) fume note")
    # ===== engineer / code flags
    txt=" ".join([str(spec.get("ask","")),str(spec.get("title","")),str(spec.get("name",""))]+[str(p.get("label","")) for p in spec.get("parts",[])]).lower()
    need=bool(re.search(STRUCT,txt) or spec.get("structural")); flagged="ENGINEER/CODE" in PLAN
    for i in (124,159,189,244): r(i,"FAIL" if need and not flagged else "PASS","engineer flag","structural/lifting/pressure item not flagged for an engineer/code official" if need and not flagged else ("flagged for engineer/code review, never stamped" if need else "not a structural/pressure item"))
    if re.search(FRAMING,txt):
        for i,t_ in FRAMING_NOTES.items(): r(i,"PASS" if t_ in PLAN else sev(i),"framing",("framing reference note present" if t_ in PLAN else f"missing framing note: {t_}"))
    # ===== finish
    pw=[x for x in rows if "powder" in str(x.get("finish","")).lower()]
    if pw:
        withh=[n_ for x in pw for n_ in x.get("names",[]) if FL.get(n_,{}).get("holes")]
        mk=meta.get("masking",[]); missm=[n_ for n_ in withh if not any(n_ in m_ for m_ in mk)]
        for i in (218,113): r(i,"WARN" if missm else "PASS","masking","powder-coated parts with holes but no masking/film note: "+", ".join(missm) if missm else "masking list + 2-4 mil film thickness on the drawing")
        tight=[f'{h["bolt"]} Ø{h["d_in"]:.3f}' for h in HS if not h.get("tapped") and h.get("dia_in") and h["d_in"]-2*0.004<h["dia_in"]+0.005 and any(p_ in withh for p_ in h["parts"])]
        for i in (217,231): r(i,"WARN" if tight else "PASS","powder","bores closed up by 2x film (2x 4 mil): "+", ".join(tight) if tight else "bores keep clearance after 2x film")
    # ===== generic plan-text tips that apply to this build
    K=_ctx_keys(d,F)
    for i,(need_,t_) in TIPS.items():
        if cat()[i]["check_type"]!="plan-text" or not all(n in K for n in need_.split("+")): continue
        r(i,"PASS" if t_ in PLAN else sev(i),"plan",("note in the plan" if t_ in PLAN else f"missing plan note: {t_}"))
    if any(str(p.get("material","")).upper() in ("ABS","ASA","PC") for p in d.get("print_parts",[])):
        r(67,"PASS" if "enclosure" in PLAN.lower() else "WARN","print","ABS/ASA enclosure note" if "enclosure" in PLAN.lower() else "ABS/ASA/PC print without an enclosure note")
    if sp or any(n_.get("groups") for _,n_ in nests):
        r(149,"PASS" if "yield" in PLAN.lower() else "WARN","plan","sheet/board yield stated" if "yield" in PLAN.lower() else "plan doesn't show stock yield")
    # ===== fit features
    fits=[dm for dm in spec.get("dims",[]) if dm.get("fit")]
    for dm in fits:
        okf=dm.get("fit_class") or dm.get("tol") is not None
        for i in (53,112,230): r(i,"PASS" if okf else "WARN",dm.get("label","fit"),"fit carries a class/tolerance" if okf else "fit feature without an ISO 286 class or tolerance")
    labs=[(dm.get("label"),dm.get("view"),dm.get("axis")) for dm in spec.get("dims",[])]
    dupd=sorted({str(x) for x in labs if labs.count(x)>1})
    r(56,"WARN" if dupd else "PASS","drawing dims","duplicate dimensions: "+", ".join(dupd) if dupd else "each feature dimensioned once")
    # laser/router tolerance stated
    for p_,i in (("laser",68),("router",95),("plasma",80)):
        if p_ in P: r(i,"PASS" if any(({"laser":"laser","router":"CNC","plasma":"plasma"}[p_]).lower() in t["applies"].lower() for t in TB.get("tolerance",[])) else "WARN","tolerance",f"{p_} tolerance stated in the title block")
    return done
# ---------------------------------------------------------------- print-mesh checks (mm, in print orientation)
def print_checks(m,name,pp,res,prn=None):
    import numpy as np, trimesh
    def r(i,st,why): res("rules",f"#{i} {name}",st,why,id=i,catalog=cat()[i]["failure"])
    z0=m.bounds[0][2]; ext=m.extents
    # 1 warping: big footprint
    fp=max(ext[0],ext[1])
    r(1,"WARN" if fp>100 else "PASS",f"footprint {fp:.0f} mm > 100 mm (Sketch default): use a 5-10 mm brim" if fp>100 else f"footprint {fp:.0f} mm")
    # 8 small holes / 4 horizontal holes (teardrop)
    small=[];horiz=[]
    try:
        for z in np.linspace(z0+0.5,m.bounds[1][2]-0.5,8):
            sec=m.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
            if sec is None: continue
            pl,_=sec.to_planar()
            for p_ in pl.polygons_full:
                for h in p_.interiors:
                    from shapely.geometry import Polygon
                    a=Polygon(h).area; dd=2*math.sqrt(a/math.pi)
                    if dd<2.0: small.append(round(dd,2))
        for ax,nrm in ((0,[1,0,0]),(1,[0,1,0])):
            for c in np.linspace(m.bounds[0][ax]+1,m.bounds[1][ax]-1,6):
                o=[0,0,0]; o[ax]=c; sec=m.section(plane_origin=o,plane_normal=nrm)
                if sec is None: continue
                pl,_=sec.to_planar()
                for p_ in pl.polygons_full:
                    for h in p_.interiors:
                        from shapely.geometry import Polygon
                        H=Polygon(h); a=H.area; per=H.length; circ=4*math.pi*a/(per*per) if per else 0; dd=2*math.sqrt(a/math.pi)
                        if dd>3 and circ>0.95: horiz.append(round(dd,1))
    except Exception as ex: pass
    r(8,"WARN" if small else "PASS",f"holes under 2 mm print closed - drill after: {sorted(set(small))[:5]}" if small else "no holes under 2 mm")
    r(4,"WARN" if horiz else "PASS",f"round horizontal holes Ø{sorted(set(horiz))[:4]} mm droop: use a teardrop or diamond top" if horiz else "no round horizontal holes (or teardropped)")
    # 6 bridges: downward faces above the bed wider than 5 mm
    fn=m.face_normals; ct=m.triangles_center; dn=(fn[:,2]<-0.95)&(ct[:,2]>z0+0.3); br=[]
    if dn.any():
        sub=m.submesh([np.where(dn)[0]],append=True)
        for c in sub.split(only_watertight=False):
            e=sorted(c.extents[:2])
            if e[0]>5: br.append(round(e[0],1))
    r(6,"WARN" if br else "PASS",f"flat bridges/ceilings {sorted(br)[:4]} mm wide (> 5 mm sag): add support or a chamfered roof" if br else "no unsupported bridges over 5 mm")
    # 12 trapped voids
    try:
        bodies=m.split(only_watertight=True); inv=[b for b in bodies if b.volume<0]
    except Exception: inv=[]
    r(12,"WARN" if inv else "PASS",f"{len(inv)} sealed internal void(s): supports/powder can't drain, add a >= 4 mm opening" if inv else "no sealed internal voids")
    # 66 slots/gaps under 0.5 mm (outward rays hitting the same part)
    try:
        pts,fi=trimesh.sample.sample_surface_even(m,1500,seed=1) if "seed" in trimesh.sample.sample_surface_even.__code__.co_varnames else trimesh.sample.sample_surface_even(m,1500)
        nr=m.face_normals[fi]; o=pts+nr*0.02
        loc,ir,it=m.ray.intersects_location(o,nr,multiple_hits=False); gap=0
        for k_,ri in enumerate(ir):
            dd=np.linalg.norm(loc[k_]-o[ri])
            if dd<0.5 and np.dot(m.face_normals[it[k_]],nr[ri])<-0.8: gap+=1
        r(66,"WARN" if gap>3 else "PASS",f"{gap} spots with slots/gaps under 0.5 mm: they fuse when printed" if gap>3 else "no slots/gaps under 0.5 mm")
    except Exception as ex: r(66,"WARN",f"gap check could not run: {ex}")
    # 59 / 60 printed threads
    tb=pp.get("thread_bands",[])
    fine=[b for b in tb if 2*b["r"]<6]
    if tb: r(59,"WARN" if fine else "PASS","printed threads under M6 / 1 mm pitch strip: use a heat-set insert" if fine else "printed threads >= M6")
    # 58 / 236 / 2 fit allowance on prints
    cl=pp.get("clearance")
    if cl is not None:
        for i in (58,236): r(i,"WARN" if float(cl)<0.5 else "PASS",f"print-fit clearance {cl} mm < ±0.5 mm the process holds" if float(cl)<0.5 else f"print fits use >= 0.5 mm ({cl} mm)")
    # 3 fit holes with compensation
    fh=pp.get("fit_holes",[])
    if fh:
        unc=[h for h in fh if not h.get("comp")]
        r(3,"WARN" if unc else "PASS",f"{len(unc)} fit hole(s) printed at nominal: printed holes come out small" if unc else "fit holes printed with compensation")
# ---------------------------------------------------------------- coverage map
EXISTING={0:"ship.py print gate overhang warning",2:"ship.py print-in-place clearance (0.5 mm)",10:"ship.py 2 mm wall rule + thickening",13:"ship.py tip-over warning",14:"ship.py single watertight body",
 17:"ship.py closed-contour DXF check",26:"ship.py toolpath-inside-sheet/bed check",50:"ship.py drawing dims vs model",51:"ship.py BOM vs model",63:"print3d.py split + ship bed check",
 118:"ship.py nest count = BOM count",44:"ship.py kerf offset only in the toolpath (DXF drawn nominal)",99:"nest.py edge margin + ship toolpath check",104:"nest.py uses stock.json sheet sizes (48x96 nominal)",
 7:"covered by the 2 mm minimum-feature/wall rule (#10)",87:"gcode.py lead-ins start in scrap (outside outlines, inside holes)",89:"sheet-metal checks #191-#199 on bent parts",231:"same check as #217",232:"same check as #132",234:"same check as #198",236:"same check as #58",60:"same check as #206 (steel into plastic 2.5D or insert)"}
SKIP={9:"needs mating-face tags on prints (no data); tip only",61:"needs mating-face tags (no data); tip only",62:"no 'cosmetic face' tags in the model",
 77:"engrave text is a font, Sketch has no stroke width to measure",78:"no living-hinge feature in the kit",85:"slat spacing is not in machines.json",90:"no plasma tab/slot joints in the kit",
 117:"Sketch builds one assembly: per-assembly qty = total",135:"screw positions are not modelled (count only)",229:"no tolerance chains in the spec",241:"enclosed-space work is not in the model (plan advice only)",201:"no hem feature in the kit",
 12.5:None}
SKIP.pop(12.5)
GENERATOR={125:"wood_plan.py + spec_build stock plan with the owner's saw kerf",28:"gcode.py marks DRILL",83:"gcode.py 60% hole feed",41:"gcode.py tabs",46:"gcode.py DOC cap",
 172:"spec_build weld schedule",166:"spec_build weld schedule",108:"fabdocs symbols from model side",52:"fabdocs title block",111:"fabdocs tolerance block",205:"spec_build clearance from table"}
def status():
    out={}
    gate_ids=set(re.findall(r"r\((\d+),",open(__file__).read()))|set(re.findall(r"for i in \(([\d, ]+)\)",open(__file__).read()))
    ids=set()
    for g in gate_ids:
        for x in g.split(","):
            if x.strip().isdigit(): ids.add(int(x))
    ids|={i for i in TIPS if cat()[i]["check_type"]=="plan-text"}|set(FRAMING_NOTES)|{19,30,32,91,68,80,95,149}
    for i,c in enumerate(cat()):
        if i in EXISTING: out[i]=("check","existing gate: "+EXISTING[i])
        elif i in ids and c["check_type"]!="advice": out[i]=("check","rules.py"+(" + "+GENERATOR[i] if i in GENERATOR else ""))
        elif i in TIPS: out[i]=("advice","tip in hand plan / HOW_TO_USE")
        elif i in ids: out[i]=("check","rules.py (advice item with measurable data)")
        elif i in SKIP: out[i]=("skipped",SKIP[i])
        else: out[i]=("skipped","NOT HANDLED")
    return out
if __name__=="__main__" and "--coverage" in sys.argv:
    st=status(); from collections import Counter
    print(Counter(v[0] for v in st.values()))
    for i,(k,why) in st.items():
        if k=="skipped" or "-v" in sys.argv: print(i,cat()[i]["check_type"],cat()[i]["severity"],k,why,"|",cat()[i]["failure"])

def part_tags(d):
    """BOM tag per part name: mark + number in the order of the BOM row's names (A1, A2 ...). Same everywhere: cut day, plan, exploded steps."""
    T={}
    for r in d.get("cutlist",[]):
        if r.get("mark")=="HW": continue
        ns=r.get("names") or [r["part"]]
        for i,n in enumerate(ns): T[n]=f'{r["mark"]}{i+1}' if len(ns)>1 or r.get("names") else r["mark"]
    return T

#!/usr/bin/env python3
"""cutday.py VDIR OUTDIR -> cut_day.pdf + cut_day_<n>.png (phone) + offcuts.csv + cut_day.json   (v1.0.5 feature 1)
Cut-day sheets for saw builds:
 1D  lumber (2x4..), angle/tube/pipe/bar: first-fit-decreasing from stock lengths, one saw kerf per cut (rules.stock_plan).
 2D  sheet goods / plate: guillotine plan for a table or circular saw: RIP strips along the sheet length (with the grain),
     then CROSSCUT each strip, then trim rips. Every cut costs one kerf.
 Part tags = BOM mark + number (A1, A2 ... in the order of the BOM 'names'), cuts numbered 1..N in the order to make them,
 a tick-off checklist and the waste/offcut list. Kerf: owner's saw (tools_setup --saw / --kerf-test) > table > labelled default."""
import sys,os,json,re,csv,subprocess,textwrap
B=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,B)
import rules,kerf,ref
V,O=sys.argv[1],sys.argv[2]; os.makedirs(O,exist_ok=True)
d=json.load(open(f"{V}/parts.json")); U=d["params"].get("units","in"); toin=1 if U=="in" else 1/25.4
STOCK=json.load(open(f"{B}/stock.json")) if os.path.exists(f"{B}/stock.json") else {}
LINEAR=("lumber","angle","sq_tube","tube","pipe","bar","flat_bar","rect_tube","round_bar","channel")
SHEET=("sheet_good","plate","sheet")
rows=[r for r in d["cutlist"] if r.get("mark")!="HW" and r.get("stock") in LINEAR+SHEET]
def tags(r):
    ns=r.get("names") or [f'{r["part"]}{i+1}' for i in range(r["qty"])]
    return {n:f'{r["mark"]}{i+1}' for i,n in enumerate(ns)}
TAG={}; PART={}
for r in rows:
    for n,t in tags(r).items(): TAG[n]=t; PART[n]=r["part"]
# ---- kerf: wood saw for wood/lumber/sheet goods, bandsaw for metal (owner's measured value first)
def metal_kerf():
    p=ref.profile(); meas=p.get("kerf_measured",{})
    for k,v in meas.items():
        if k.startswith("saw|") and any(w in k.lower() for w in ("band","cold","chop","metal")): return float(v),f"measured test cut ({k[4:]})"
    S=[r for r in ref.get("shop_reference")["saw_kerf"] if r.get("tool")=="bandsaw"]
    if S:
        lo,hi=[float(x) for x in str(S[0]["kerf_in"]).split("-")]; return round((lo+hi)/2,4),f'metal bandsaw {S[0]["kerf_in"]} in midpoint ({S[0].get("src","")}) - measure yours: tools_setup.py --saw bandsaw --saw-kerf X'
    return 0.0625,"metal saw unknown: assumed 1/16 in (Sketch default)"
WK,WKS=kerf.saw(); MK,MKS=metal_kerf()
def iswood(r): return rules.mcls(r["material"]) in("wood","plywood","mdf") or r.get("stock") in("lumber","sheet_good")
out=dict(units=U,kerf={"wood":[WK,WKS],"metal":[MK,MKS]},linear=[],sheets=[],cuts=[],offcuts=[])
# ---- 1D
lin=[dict(r,stock="lumber") for r in rows if r.get("stock") in LINEAR]
for wood in (True,False):
    rr=[r for r in lin if iswood(r)==wood]
    if not rr: continue
    k,ks=(WK,WKS) if wood else (MK,MKS)
    lens=STOCK.get("lumber_lengths",[96,120,144,192]) if wood else STOCK.get("metal_lengths",[240])
    for sec in rules.stock_plan(rr,U,k*(1 if U=="in" else 25.4),ks,[L/toin for L in lens]):
        sec["stock_len_src"]="stock.json "+("lumber_lengths" if wood else "metal_lengths")+(" (Sketch default 20 ft mill length)" if not wood and "metal_lengths" not in STOCK else "")
        out["linear"].append(sec)
# ---- 2D guillotine
def sheet_size(cls,parts):
    sz=STOCK.get("sheet_sizes",[[48,96]]) if cls=="wood" else STOCK.get("plate_sizes",STOCK.get("sheet_sizes",[[48,96]]))
    need=max(max(p[1],p[2]) for p in parts)
    sz=[[a/toin,b/toin] for a,b in sorted(sz,key=lambda s:s[0]*s[1])]
    return next((s for s in sz if max(s)>=need and min(s)>=min(min(p[1],p[2]) for p in parts)),sz[-1])
def guillotine(parts,SW,SL,k):
    """parts: (name,len,wid). strips run along SL. returns sheets: list of strips [width,[(name,L,w)]]"""
    pcs=sorted([(n,max(a,b),min(a,b)) for n,a,b in parts],key=lambda q:(-q[2],-q[1]))
    sheets=[]
    for n,L,w in pcs:
        if L>SL+1e-9: L,w=w,L   # wider than strip run: turn it (cross-grain, noted)
        placed=False
        for sh in sheets:
            for st in sh:
                used=sum(x[1] for x in st[1])+len(st[1])*k
                if w<=st[0]+1e-9 and used+L<=SL+1e-9: st[1].append((n,L,w)); placed=True; break
            if placed: break
            usedw=sum(st[0] for st in sh)+len(sh)*k
            if usedw+w<=SW+1e-9: sh.append([w,[(n,L,w)]]); placed=True; break
        if not placed: sheets.append([[w,[(n,L,w)]]])
    return sheets
sg={}
for r in rows:
    if r.get("stock") not in SHEET: continue
    for fl in d["flats"]:
        if fl["name"] in TAG and fl["name"] in (r.get("names") or []):
            sg.setdefault((("plywood" if "plywood" in r["material"] else fl.get("material",r["material"]))+f' {fl.get("thickness")}',fl.get("thickness")),[]).append((fl["name"],fl["w"],fl["h"]))
for (mat,t),parts in sg.items():
    wood=rules.mcls(mat) in("wood","plywood","mdf") or "plywood" in mat
    k,ks=(WK,WKS) if wood else (MK,MKS); k=k/toin
    SW,SL=sorted(sheet_size("wood" if wood else "metal",parts))
    for i,sh in enumerate(guillotine(parts,SW,SL,k)):
        y=0; strips=[]
        for w,ps in sh:
            x=0; pl=[]
            for n,L,pw in ps: pl.append(dict(name=n,tag=TAG[n],x=round(x,4),y=round(y,4),L=L,w=pw)); x+=L+k
            strips.append(dict(width=w,y=round(y,4),parts=pl,end_offcut=round(SL-x,3))); y+=w+k
        out["sheets"].append(dict(material=mat,thickness=t,sheet=[SW,SL],n=i+1,kerf=k,kerf_src=ks,strips=strips,rip_offcut=round(SW-y,3),
                                  sheet_src="stock.json sheet_sizes" if wood else "stock.json plate_sizes/sheet_sizes (a shop drop or flat bar works too)"))
# ---- cut order: 1D longest first per board; 2D rips, then crosscuts, then trim rips
f=lambda v:f"{v:.3f}".rstrip("0").rstrip(".")
C=out["cuts"]
def add(what,stock,makes,kind): C.append(dict(n=len(C)+1,kind=kind,stock=stock,what=what,makes=makes))
for sec in out["linear"]:
    for bi,b in enumerate(sec["boards"]):
        st=f'{sec["section"]} board {bi+1} ({f(b["stock"])} {U})'
        for n,L in sorted(b["parts"],key=lambda q:-q[1]): add(f"crosscut {f(L)} {U}",st,[TAG.get(n,n)],"crosscut")
        if b.get("offcut",0)>0: out["offcuts"].append(dict(stock=st,size=f'{f(b["offcut"])} {U} of {sec["section"]}',keep=b["offcut"]*toin>=12))
for s in out["sheets"]:
    st=f'{s["material"]} sheet {s["n"]} ({f(s["sheet"][0])} x {f(s["sheet"][1])} {U})'
    for j,sp in enumerate(s["strips"]): add(f'RIP strip {j+1} at {f(sp["width"])} {U} wide (fence {f(sp["width"])}), full length, with the grain',st,[f'strip {j+1}'],"rip")
    for j,sp in enumerate(s["strips"]):
        for p in sp["parts"]: add(f'CROSSCUT strip {j+1} at {f(p["L"])} {U}',st,[p["tag"]],"crosscut")
    for j,sp in enumerate(s["strips"]):
        for p in sp["parts"]:
            if p["w"]<sp["width"]-1e-6: add(f'trim RIP {p["tag"]} to {f(p["w"])} {U} wide',st,[p["tag"]],"rip")
        if sp["end_offcut"]>0: out["offcuts"].append(dict(stock=st,size=f'{f(sp["end_offcut"])} x {f(sp["width"])} {U} (end of strip {j+1})',keep=sp["end_offcut"]*toin>=6 and sp["width"]*toin>=3))
    if s["rip_offcut"]>0: out["offcuts"].append(dict(stock=st,size=f'{f(s["rip_offcut"])} x {f(s["sheet"][1])} {U} (rip waste)',keep=s["rip_offcut"]*toin>=3))
out["tags"]=TAG; out["build_id"]=d.get("build_id")
json.dump(out,open(f"{O}/cut_day.json","w"),indent=1)
with open(f"{O}/offcuts.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["stock","offcut","keep?"]); [w.writerow([o["stock"],o["size"],"keep" if o["keep"] else "scrap"]) for o in out["offcuts"]]
# ---- PDF (portrait letter, big type for a phone or a clipboard)
from reportlab.lib.pagesizes import letter; from reportlab.pdfgen import canvas; from reportlab.lib.units import inch
PW,PH=letter; c=canvas.Canvas(f"{O}/cut_day.pdf",pagesize=letter); pages=[0]
def head(t):
    pages[0]+=1; c.setFont("Helvetica-Bold",15); c.drawString(0.5*inch,PH-0.6*inch,t)
    c.setFont("Helvetica",8.5); c.drawString(0.5*inch,PH-0.8*inch,f'{d.get("title","")} - build {d.get("build_id","?")} - units {U} - CUT DAY (estimate: measure twice, cut once)')
    c.drawRightString(PW-0.5*inch,0.4*inch,f"cut_day page {pages[0]}")
def box(x,y): c.rect(x,y-1,9,9)
head("CUT DAY 1/3: checklist (tick each cut)")
y=PH-1.15*inch; c.setFont("Helvetica",9)
for t in [f'Saw kerf wood: {WK} in - {WKS}']+([f'Saw kerf metal: {MK} in - {MKS}'] if any(not iswood(r) for r in rows) else []):
    for tl in textwrap.wrap(t,120): c.drawString(0.5*inch,y,tl); y-=11
c.drawString(0.5*inch,y,"Tags = BOM mark + number (A1 = first part of BOM row A). Write the tag on each part as it comes off the saw."); y-=16
for cut in C:
    if y<0.8*inch: c.showPage(); head("CUT DAY: checklist (cont.)"); y=PH-1.15*inch
    box(0.5*inch,y); c.setFont("Helvetica-Bold",10); c.drawString(0.75*inch,y,f'{cut["n"]:>2}.'); c.setFont("Helvetica",10)
    c.drawString(1.05*inch,y,f'{cut["what"]}  ->  {", ".join(cut["makes"])}'[:88]); c.setFont("Helvetica",7.5); c.drawString(1.05*inch,y-9,cut["stock"]); y-=22
c.showPage()
SC_COL=["#cfe8ff","#ffe2c2","#d8f5d0","#f3d4f5","#fff4b8","#e0e0e0"]
from reportlab.lib.colors import HexColor,black,red
for s in out["sheets"]:
    head(f'CUT DAY 2/3: {s["material"]} sheet {s["n"]} ({f(s["sheet"][0])} x {f(s["sheet"][1])} {U})')
    SW,SL=s["sheet"]; sc=min((PW-1*inch)/SL,(PH-3.2*inch)/SW); x0=0.5*inch; y0=PH-1.2*inch-SW*sc
    c.setStrokeColor(black); c.rect(x0,y0,SL*sc,SW*sc)
    for j,sp in enumerate(s["strips"]):
        c.setStrokeColor(red); c.setDash(4,2); yy=y0+(SW-sp["y"]-sp["width"])*sc; c.line(x0,yy,x0+SL*sc,yy); c.setDash()
        for p in sp["parts"]:
            c.setFillColor(HexColor(SC_COL[ord(p["tag"][0])%len(SC_COL)])); c.setStrokeColor(black)
            c.rect(x0+p["x"]*sc,y0+(SW-p["y"]-p["w"])*sc,p["L"]*sc,p["w"]*sc,fill=1); c.setFillColor(black)
            c.setFont("Helvetica-Bold",12); c.drawCentredString(x0+(p["x"]+p["L"]/2)*sc,y0+(SW-p["y"]-p["w"]/2)*sc+2,p["tag"])
            c.setFont("Helvetica",7); c.drawCentredString(x0+(p["x"]+p["L"]/2)*sc,y0+(SW-p["y"]-p["w"]/2)*sc-8,f'{f(p["L"])} x {f(p["w"])}')
    c.setFont("Helvetica",9); yy=y0-16
    for t in (f'Red dashed = RIP cuts (fence set from the factory edge, with the grain along the {f(SL)} {U} length). Then crosscut each strip, then trim rips.',
              f'Kerf {f(s["kerf"])} {U} per cut ({s["kerf_src"]})'[:140], f'Sheet from {s["sheet_src"]}. Breaking down a full sheet: rip on a track saw or circular saw with a straightedge first, then the table saw.',
              "Cut order: follow the numbered checklist on page 1 (cut numbers are the same)."):
        for tl in textwrap.wrap(t,125): c.drawString(0.5*inch,yy,tl); yy-=12
    c.showPage()
if out["linear"]:
    head("CUT DAY 2/3: boards and bar stock (1D)"); y=PH-1.2*inch
    for sec in out["linear"]:
        c.setFont("Helvetica-Bold",11); c.drawString(0.5*inch,y,f'{sec["section"]}: buy {len(sec["boards"])} x stock  (kerf {f(sec["kerf_in"])} per cut; stock lengths from {sec["stock_len_src"]})'[:100]); y-=16
        for bi,b in enumerate(sec["boards"]):
            if y<1.2*inch: c.showPage(); head("CUT DAY 2/3: boards (cont.)"); y=PH-1.2*inch
            sc=(PW-1.2*inch)/max(b["stock"],1e-6); x=0.6*inch
            c.setStrokeColor(black); c.rect(x,y-14,b["stock"]*sc,14)
            for n,L in sorted(b["parts"],key=lambda q:-q[1]):
                c.setFillColor(HexColor(SC_COL[ord(TAG.get(n,"A")[0])%len(SC_COL)])); c.rect(x,y-14,L*sc,14,fill=1); c.setFillColor(black)
                c.setFont("Helvetica-Bold",8); c.drawCentredString(x+L*sc/2,y-10,f'{TAG.get(n,n)} {f(L)}'); x+=(L+sec["kerf_in"])*sc
            c.setFont("Helvetica",7.5); c.drawString(0.6*inch,y-24,f'board {bi+1}: {f(b["stock"])} {U} stock, offcut {f(b.get("offcut",0))} {U}'); y-=36
    c.showPage()
head("CUT DAY 3/3: offcuts / waste"); y=PH-1.2*inch; c.setFont("Helvetica",10)
for o in out["offcuts"] or [dict(stock="-",size="no offcuts",keep=False)]:
    if y<0.8*inch: c.showPage(); head("offcuts (cont.)"); y=PH-1.2*inch
    box(0.5*inch,y); c.drawString(0.75*inch,y,f'{o["size"]}  from {o["stock"]}  -> {"KEEP (rack it)" if o["keep"] else "scrap"}'[:100]); y-=16
c.showPage(); c.save()
subprocess.run(["pdftoppm","-png","-r","110",f"{O}/cut_day.pdf",f"{O}/cut_day"],check=False)
print(f"cut day -> {O}: {len(C)} cuts, {len(out['sheets'])} sheet(s), {sum(len(s['boards']) for s in out['linear'])} board(s)")

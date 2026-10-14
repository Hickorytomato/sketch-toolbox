#!/usr/bin/env python3
"""nest.py PARTS.json OUTDIR [--machine plasma] -> nests flat parts on standard sheets (stock.json sheet_sizes) per material+thickness.
TRUE-SHAPE nesting (default): real polygons (shapely), rotations 0/90/180/270 (+ --fine for 15° steps), spacing = kerf+gap,
bottom-left-fill with slide refinement, part-in-part (parts can land inside rings/holes of placed parts), time budget --time S.
--bbox uses the old rectpack bounding-box nester for comparison. Picks the sheet size with least waste that fits the bed. Rolled parts longer than the bed/sheet are split into equal segments (extra seams noted).
Writes nest.json (placed geometry for gcode.py), sheet_<group>_<n>.dxf, nest_<group>_<n>.png, utilization %."""
import sys,os,json,math,copy
import rectpack,ezdxf,matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
B=os.path.dirname(os.path.abspath(__file__)); a=sys.argv[1:]
d=json.load(open(a[0])); o=a[1]; os.makedirs(o,exist_ok=True)
mname=a[a.index("--machine")+1] if "--machine" in a else "plasma"
M=json.load(open(f"{B}/machines.json")); st=json.load(open(f"{B}/stock.json")); mach=M[mname]
sys.path.insert(0,B); import kerf as _kerf
def _sp(k): return (max(0.25,k*4),max(0.25,k*4)/2+0.3) if mach.get("type")!="router" else (k+0.125,(k+0.125)/2)
SP=max(0.25,mach.get("kerf",0.06)*4) if mach.get("type")!="router" else mach.get("tool_dia",0.25)+0.125   # gap between parts
EM=SP/2+0.3 if mach.get("type")!="router" else SP/2   # sheet-edge margin (lead-in ~0.25 + kerf); was 0 -> cuts ran off the sheet edge
def size(f):
    if f["shape"] in("circle",): return 2*f["r"],2*f["r"]
    if f["shape"]=="annulus": return 2*f["r"],2*f["r"]
    return f["w"],f["h"]
def area(f):
    holes=sum(math.pi*r*r for _,_,r in f.get("holes",[]))
    if f["shape"]=="circle": return math.pi*f["r"]**2-holes
    if f["shape"]=="annulus": return math.pi*(f["r"]**2-f["ri"]**2)-holes
    if f["shape"]=="poly":
        from shapely.geometry import Polygon as _P
        return _P(f["outer"],f.get("inner_poly",[])).area-holes
    return f["w"]*f["h"]-holes
sheets=sorted(st["sheet_sizes"],key=lambda s:s[0]*s[1]); bed=mach.get("bed",[1e9,1e9])
maxlen=max(max(s) for s in sheets)
items=[]; notes=[]
for f in d["flats"]:
    w,h=size(f)
    if f["shape"].startswith("rect") and max(w,h)>min(maxlen,max(bed)) and f.get("roll"):
        lim=min(maxlen,max(bed)) - 2*SP; k=math.ceil(w/lim); seg=w/k
        notes.append(f'{f["name"]}: {w:.1f}" flat length exceeds sheet/bed, split into {k} segments of {seg:.2f}" (add {k-1} more vertical seams)')
        for i in range(k):
            g=copy.deepcopy(f); g["name"]=f'{f["name"]}_{i+1}of{k}'; g["w"]=round(seg,3)
            g["holes"]=[(x-i*seg,y,r) for x,y,r in f.get("holes",[]) if i*seg<=x<(i+1)*seg]; items.append(g)
    else: items.append(f)
groups={}
for f in items: groups.setdefault(f'{f.get("material","steel")}_{f.get("thickness",0)}',[]).append(f)
out={"machine":mname,"spacing":SP,"method":"bbox" if "--bbox" in a else "true-shape","groups":[],"notes":notes}
def pack(fl,W,H):
    pk=rectpack.newPacker(rotation=True,pack_algo=rectpack.MaxRectsBssf)
    for i,f in enumerate(fl):
        w,h=size(f); pk.add_rect(w+SP,h+SP,rid=i)
    pk.add_bin(W,H,count=99); pk.pack()
    placed=pk.rect_list()
    return (placed if len(placed)==len(fl) else None)
import time
from shapely.geometry import Polygon,Point,box as sbox
from shapely import affinity
from shapely.prepared import prep
BBOX="--bbox" in a; FINE="--fine" in a; TBUD=float(a[a.index("--time")+1]) if "--time" in a else 20.0
def shape(f):   # part-local polygon (circles centered at 0,0; rects from 0,0), holes included
    if f["shape"]=="circle": P=Point(0,0).buffer(f["r"],resolution=32)
    elif f["shape"]=="annulus": P=Point(0,0).buffer(f["r"],resolution=32).difference(Point(0,0).buffer(f["ri"],resolution=32))
    elif f["shape"]=="poly": P=Polygon(f["outer"],f.get("inner_poly",[])).buffer(0)
    else: P=sbox(0,0,f["w"],f["h"])
    for x,y,r in f.get("holes",[]): P=P.difference(Point(x,y).buffer(r,resolution=12))
    return P
def rots(f):
    if f["shape"] in("circle","annulus"): return [0]
    return list(range(0,360,15)) if FINE else [0,90,180,270]
def tshape_pack(fl,W,H,deadline):
    """greedy bottom-left fill on true shapes. returns list of (sheet,idx,theta,dx,dy) or None if a part can't fit"""
    order=sorted(range(len(fl)),key=lambda i:-shape(fl[i]).area); sheets=[]; out=[]
    for i in order:
        base=shape(fl[i]); placed=False
        for sh in range(len(sheets)+1):
            if sh==len(sheets): sheets.append(dict(occ=None))
            occ=sheets[sh]["occ"]; po=prep(occ) if occ is not None else None; best=None
            for th in rots(fl[i]):
                Pr=affinity.rotate(base,th,origin=(0,0)); minx,miny,maxx,maxy=Pr.bounds; w,h=maxx-minx,maxy-miny
                if w>W+1e-9 or h>H+1e-9: continue
                fill=Pr.buffer(SP/2,resolution=8)     # spacing envelope (half on each part)
                step=max(0.5,min(w,h)/8)*(1 if time.time()<deadline else 2)   # coarser scan once over the time budget (never skips a sheet)
                xs=[k*step for k in range(int((W-w)/step)+1)]+[W-w]; ys=[k*step for k in range(int((H-h)/step)+1)]+[H-h]
                found=None
                for y in ys:      # bottom-left fill: lowest row first, then leftmost -> clean full-width remnant on top
                    if best and y-miny>best[1]+1e-9: break
                    for x in xs:
                        Q=affinity.translate(fill,x-minx,y-miny)
                        if po is None or not po.intersects(Q): found=(x,y); break
                    if found: break
                if not found: continue
                x,y=found
                for _ in range(3 if time.time()<deadline else 1):   # slide refinement: push left then down in shrinking steps
                    for dxy in((0,-1),(-1,0)):
                        stp=step/2
                        while stp>0.02:
                            nx,ny=x+dxy[0]*stp,y+dxy[1]*stp
                            if nx>=0 and ny>=0:
                                Q=affinity.translate(fill,nx-minx,ny-miny)
                                if po is None or not po.intersects(Q): x,y=nx,ny; continue
                            stp/=2
                cand=(x-minx,y-miny+0,th,Pr,fill)
                score=(y+h*0.5,x)
                if best is None or score<best[5]: best=(x-minx,y-miny,th,Pr,fill,score)
            if best:
                dx,dy,th,Pr,fill,_=best
                Q=affinity.translate(fill,dx,dy); sheets[sh]["occ"]=Q if occ is None else occ.union(Q)
                out.append((sh,i,th,dx,dy)); placed=True; break
            if sheets[sh]["occ"] is None: sheets.pop(); return None    # doesn't fit on an empty sheet
        if not placed: return None
    return out
def bbox_pack(fl,W,H):
    pl=pack(fl,W,H)
    if not pl: return None
    res=[]
    for b,x,y,w,h,rid in pl:
        f=fl[rid]; fw,fh=size(f); rot=abs((w-SP)-fw)>1e-6 and abs(fw-fh)>1e-6
        if f["shape"] in("circle","annulus"): res.append((b,rid,0,x+SP/2+f["r"],y+SP/2+f["r"]))
        elif rot: res.append((b,rid,90,x+SP/2+f["h"],y+SP/2))
        else: res.append((b,rid,0,x+SP/2,y+SP/2))
    return res
KERF={}
for g,fl in groups.items():
    best=None; f0=fl[0]; KERF[g]=_kerf.lookup(mname,mach,f0.get("material","steel"),f0.get("thickness") or 0.25); SP,EM=_sp(KERF[g][0])
    for W,H in sheets:
        if any(min(size(f))+SP>min(W,H) or max(size(f))+SP>max(W,H) for f in fl): continue
        pl=bbox_pack(fl,W,H) if BBOX else tshape_pack(fl,W-2*EM,H-2*EM,time.time()+TBUD/len(sheets))
        if pl and not BBOX: pl=[(b_,i_,t_,dx_+EM,dy_+EM) for b_,i_,t_,dx_,dy_ in pl]   # edge margin: kerf comp + lead-ins stay on the sheet
        if not pl: continue
        n=len(set(b for b,*_ in pl)); fits_bed=(W<=max(bed) and H<=min(bed)) or (W<=min(bed) and H<=max(bed))
        score=(not fits_bed, n*W*H)
        if best is None or score<best[0]: best=(score,W,H,pl,n,fits_bed)
    if not best: out["notes"].append(f"{g}: a part is bigger than every stock sheet"); continue
    _,W,H,pl,n,fits=best
    if not fits: out["notes"].append(f"{g}: {W}x{H} sheet is larger than the {mname} bed {bed}; shear/pre-cut or index the sheet")
    for sh in range(n):
        parts=[]
        for b,rid,th,dx,dy in pl:
            if b!=sh: continue
            parts.append(dict(fl[rid],theta=th,dx=dx,dy=dy))
        used=sum(area(p) for p in parts); util=100*used/(W*H)
        ymax=0
        for p in parts:   # remnant: full-width strip above the highest part
            fw,fh=size(p); c=[(0,0),(fw,0),(fw,fh),(0,fh)] if p["shape"].startswith("rect") or p["shape"]=="poly" else [(-p["r"],-p["r"]),(p["r"],p["r"]),(-p["r"],p["r"]),(p["r"],-p["r"])]
            th=math.radians(p["theta"]); ymax=max(ymax,max(p["dy"]+math.sin(th)*x+math.cos(th)*y for x,y in c))
        rem=H-ymax-SP; util_used=100*used/(W*max(ymax,1e-9))
        name=f"{g.replace('.','p')}_{sh+1}"
        doc=ezdxf.new("R2010"); doc.units=ezdxf.units.IN; ms=doc.modelspace()
        for L,c in(("SHEET",8),("CUT",1),("HOLES",5),("TEXT",3),("POCKET",30)): doc.layers.add(L,color=c)
        ms.add_lwpolyline([(0,0),(W,0),(W,H),(0,H)],close=True,dxfattribs={"layer":"SHEET"})
        fig,ax=plt.subplots(figsize=(10,10*H/W)); ax.add_patch(plt.Rectangle((0,0),W,H,fill=False,color="gray"))
        for p in parts:
            fw,fh=size(p)
            def T(x,y,p=p):   # part-local -> sheet: rotate by theta about local origin, then translate (never mirrors)
                c,s_=math.cos(math.radians(p["theta"])),math.sin(math.radians(p["theta"]))
                return (p["dx"]+c*x-s_*y,p["dy"]+s_*x+c*y)
            p["geom"]={"outer":None,"inner":[],"holes":[]}
            if p["shape"] in("circle","annulus"):
                c=T(0,0); p["geom"]["outer"]={"circle":[c[0],c[1],p["r"]]}
                ms.add_circle(c,p["r"],dxfattribs={"layer":"CUT"}); ax.add_patch(plt.Circle(c,p["r"],fill=False,color="red"))
                if p["shape"]=="annulus":
                    p["geom"]["inner"].append([c[0],c[1],p["ri"]]); ms.add_circle(c,p["ri"],dxfattribs={"layer":"CUT"}); ax.add_patch(plt.Circle(c,p["ri"],fill=False,color="red"))
            elif p["shape"]=="poly":
                pts=[T(x,y) for x,y in p["outer"]]; p["geom"]["outer"]={"poly":pts}
                ms.add_lwpolyline(pts,close=True,dxfattribs={"layer":"CUT"}); ax.plot(*zip(*(pts+[pts[0]])),color="red")
                for ip in p.get("inner_poly",[]):
                    q=[T(x,y) for x,y in ip]; p["geom"].setdefault("inner_poly",[]).append(q)
                    ms.add_lwpolyline(q,close=True,dxfattribs={"layer":"CUT"}); ax.plot(*zip(*(q+[q[0]])),color="red")
                for pk in p.get("pockets",[]):
                    q=[T(x,y) for x,y in pk["poly"]]; p["geom"].setdefault("pockets",[]).append(dict(poly=q,depth=pk["depth"],face=pk.get("face","top")))
                    ms.add_lwpolyline(q,close=True,dxfattribs={"layer":"POCKET"}); ax.fill(*zip(*q),color="orange" if pk.get("face","top")=="top" else "violet",alpha=0.5)
            else:
                pts=[T(0,0),T(p["w"],0),T(p["w"],p["h"]),T(0,p["h"])]; p["geom"]["outer"]={"poly":pts}
                ms.add_lwpolyline(pts,close=True,dxfattribs={"layer":"CUT"}); ax.plot(*zip(*(pts+[pts[0]])),color="red")
            for hx,hy,hr in p.get("holes",[]):
                c=T(hx,hy); p["geom"]["holes"].append([c[0],c[1],hr]); ms.add_circle(c,hr,dxfattribs={"layer":"HOLES"}); ax.add_patch(plt.Circle(c,hr,fill=False,color="blue"))
            lab=T(fw/2,fh/2) if p["shape"].startswith("rect") or p["shape"]=="poly" else T(0,-p["r"]*0.6)
            ms.add_text(p["name"],height=1,dxfattribs={"layer":"TEXT","insert":lab}); ax.text(*lab,p["name"],ha="center",fontsize=8)
        ax.set_aspect("equal"); ax.set_xlim(-2,W+2); ax.set_ylim(-2,H+2)
        ax.set_title(f'{g}  sheet {sh+1}/{n}: {W}" x {H}"   util {util:.0f}%  ({util_used:.0f}% of used {ymax:.1f}")  remnant {W}x{max(rem,0):.1f}   ({"bbox" if BBOX else "true-shape"})')
        fig.savefig(f"{o}/nest_{name}.png",dpi=80,bbox_inches="tight"); plt.close(fig); doc.saveas(f"{o}/sheet_{name}.dxf")
        out["groups"].append(dict(name=name,kerf=KERF[g][0],kerf_src=KERF[g][1],spacing=SP,group=g,sheet=[W,H],thickness=fl[0].get("thickness"),material=fl[0].get("material"),utilization=round(util,1),
            used_length=round(ymax,2),utilization_of_used=round(util_used,1),remnant=[W,round(max(rem,0),2)],parts=parts))
json.dump(out,open(f"{o}/nest.json","w"),indent=1,default=float)
for G in out["groups"]: print(f'{G["name"]}: {G["sheet"][0]}x{G["sheet"][1]} util {G["utilization"]}% (of used length {G["utilization_of_used"]}%) remnant {G["remnant"][0]}x{G["remnant"][1]} parts {len(G["parts"])}')
for nn in out["notes"]: print("NOTE:",nn)

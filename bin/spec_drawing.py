#!/usr/bin/env python3
"""spec_drawing.py VDIR -> VDIR/drawing.png + drawing_views.svg-free PNG pages: hidden-line orthographic views (front/top/side)
of VDIR/step/*.step, dimensioned ONLY from the spec's "dims" (values come from spec.json; * = Sketch assumption),
plus the spec table (USER vs ASSUMED). Check every dimension before cutting."""
import sys,os,glob,json,matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import cadquery as cq
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from OCP.HLRBRep import HLRBRep_Algo,HLRBRep_HLRToShape
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.BRepLib import BRepLib
V=sys.argv[1]; d=json.load(open(f"{V}/parts.json")); U=d["params"].get("units","in")
shapes=[cq.importers.importStep(f).val() for f in sorted(glob.glob(f"{V}/step/*.step"))]
comp=cq.Compound.makeCompound(shapes)
VIEWS={"front":((0,-1,0),(1,0,0),(0,2)),"top":((0,0,1),(1,0,0),(0,1)),"side":((1,0,0),(0,1,0),(1,2))}
def hlr(dirv,xd):
    h=HLRBRep_Algo(); h.Add(comp.wrapped); h.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(),gp_Dir(*dirv),gp_Dir(*xd)))); h.Update(); h.Hide()
    s=HLRBRep_HLRToShape(h); out={"vis":[],"hid":[]}
    for key,cs in(("vis",[s.VCompound(),s.OutLineVCompound()]),("hid",[s.HCompound()])):
        for c in cs:
            if c.IsNull(): continue
            BRepLib.BuildCurves3d_s(c,1e-4)
            for e in cq.Shape.cast(c).Edges():
                n=max(2,int(e.Length()/(0.1 if U=="in" else 2))+2); pts=[e.positionAt(t) for t in [i/(n-1) for i in range(n)]]
                out[key].append([(p.x,p.y) for p in pts])
    return out
bb=comp.BoundingBox(); ext={"x":(bb.xmin,bb.xmax),"y":(bb.ymin,bb.ymax),"z":(bb.zmin,bb.zmax)}
import re
def base(n): return re.sub(r'(_?[A-Z]?\d+|_[LRFB])$','',str(n))
def group_rows(d):
    """Merge identical parts (same base name + material + size) into one row with a quantity."""
    out={}; order=[]
    for r in d["cutlist"]:
        if r["mark"]=="HW": k=("HW",r["material"])
        else: k=(base(r["part"]).lower(),str(r["material"]),str(r["length"]))
        if k not in out: out[k]=dict(r,marks=[r["mark"]],part=(r["part"] if r["mark"]=="HW" else base(r["part"]))); order.append(k)
        else: out[k]["qty"]+=r["qty"]; out[k]["marks"].append(r["mark"])
    rows=[]
    for k in order:
        r=out[k]; m=r["marks"]; r["markstr"]=m[0] if len(m)==1 else f"{m[0]}-{m[-1]}"
        rows.append(r)
    return rows
def short(s,n): s=str(s); return s if len(s)<=n else s[:n-1]+"~"
rows=group_rows(d)
specs=list(d.get("spec_values",{}).items())
fmt=(lambda v:f'{v:.3f}"'.replace('.000"','"')) if U=="in" else (lambda v:f"{v:.1f} mm".replace(".0 mm"," mm"))
# sheet 1: views (left 64%) + title/spec/part table (right). Fixed row pitch in figure fraction -> never overlaps.
W,H=17,11; PITCH=0.19/H  # ~0.19 in per row
fig=plt.figure(figsize=(W,H))
fig.patches.append(plt.Rectangle((0.01,0.01),0.98,0.98,transform=fig.transFigure,fill=False,lw=1.5))
DRAWN=[]   # every dimension printed on the sheet -> drawing_dims.json (ship.py cross-checks them against the model)
VIEWBOX={"top":(0.03,0.52,0.30,0.42),"front":(0.03,0.06,0.30,0.42),"side":(0.35,0.06,0.28,0.42)}
for vn,(dv,xd,(ia,ib)) in VIEWS.items():
    ax=fig.add_axes(VIEWBOX[vn]); ax.set_aspect("equal",adjustable="datalim"); ax.axis("off"); ax.set_title(vn.upper()+" VIEW",fontsize=11,loc="left",weight="bold")
    L=hlr(dv,xd)
    for pl in L["hid"]: ax.plot(*zip(*pl),color="0.6",lw=0.5,ls=(0,(3,2)))
    for pl in L["vis"]: ax.plot(*zip(*pl),color="k",lw=1.0)
    xs=[p[0] for pl in L["vis"] for p in pl]; ys=[p[1] for pl in L["vis"] for p in pl]
    if not xs: continue
    x0,x1,y0,y1=min(xs),max(xs),min(ys),max(ys); size=max(x1-x0,y1-y0); off=size*0.08; nh=nv=0
    for dm in [q for q in d.get("dims",[]) if q["view"]==vn]:
        col="tab:red" if dm["src"]!="user" else "tab:blue"; txt=f'{dm["label"]} {fmt(dm["value"])}'+(" *" if dm["src"]!="user" else "")
        DRAWN.append(dict(label=dm["label"],value=dm["value"],text=txt,view=vn,axis=dm["axis"],span=dm.get("span"),expr=dm.get("expr")))
        if dm["axis"]=="h":
            a,b=dm["span"] if dm.get("span") else (x0,x0+dm["value"]); nh+=1; yy=y0-off*nh*1.3
            ax.annotate("",(a,yy),(b,yy),arrowprops=dict(arrowstyle="<->",color=col,lw=0.9)); ax.plot([a,a],[y0,yy],color=col,lw=0.4); ax.plot([b,b],[y0,yy],color=col,lw=0.4)
            ax.text((a+b)/2,yy-off*0.15,txt,ha="center",va="top",color=col,fontsize=9)
        else:
            a,b=dm["span"] if dm.get("span") else (y0,y0+dm["value"]); nv+=1; xx=x1+off*nv*1.4
            ax.annotate("",(xx,a),(xx,b),arrowprops=dict(arrowstyle="<->",color=col,lw=0.9)); ax.plot([x1,xx],[a,a],color=col,lw=0.4); ax.plot([x1,xx],[b,b],color=col,lw=0.4)
            ax.text(xx+off*0.1,(a+b)/2,txt,rotation=90,va="center",ha="left",color=col,fontsize=9)
    ax.set_xlim(x0-off*1.2,x1+off*(1.2+1.6*nv)); ax.set_ylim(y0-off*(1.5+1.3*nh),y1+off*0.8)
X0=0.655; COLS=[(0,"MARK"),(0.045,"QTY"),(0.08,"PART"),(0.15,"MATERIAL"),(0.245,"SIZE")]
def T(x,y,s,**k): fig.text(x,y,s,va="top",**k)
def table_header(y):
    for dx,h in COLS: T(X0+dx,y,h,fontsize=8.5,weight="bold")
    fig.add_artist(plt.Line2D([X0,0.985],[y-PITCH*0.95]*2,lw=0.8,color="k")); return y-PITCH*1.1
def row(y,r,i):
    if i%2==0: fig.patches.append(plt.Rectangle((X0-0.003,y-PITCH*0.95),0.985-X0+0.003,PITCH,transform=fig.transFigure,color="0.94",zorder=0))
    vals=[r["markstr"],f'{r["qty"]}',short(r["part"],15),short(r["material"],21),short(re.sub(r"\.0+\b","",str(r["length"] or "-")),19)]
    for (dx,_),v in zip(COLS,vals): T(X0+dx,y,v,fontsize=8,family="monospace")
y=0.965
import textwrap
tl=textwrap.wrap(d.get("title") or "Design",38)[:2]
for t_ in tl: T(X0,y,t_,fontsize=14,weight="bold"); y-=0.03
y-=0.005
T(X0,y,f"Units: {U}.  Blue = your value.  Red * = Sketch assumption (confirm or change).",fontsize=7.5); y-=PITCH*1.4
T(X0,y,"SPECIFICATION",fontsize=10,weight="bold"); y-=PITCH*1.1
half=(len(specs)+1)//2
for i,(k,v) in enumerate(specs):
    cx=X0+(0 if i<half else 0.165); cy=y-PITCH*(i if i<half else i-half)
    T(cx,cy,short(f'{"" if v["src"]=="user" else "* "}{k} = {v["v"]} {v.get("unit","")}',30),fontsize=7.8,family="monospace",color="tab:blue" if v["src"]=="user" else "tab:red")
y-=PITCH*(half+0.8)
T(X0,y,"CUT / PART LIST",fontsize=10,weight="bold"); y-=PITCH*1.2
y=table_header(y); FOOT=0.05; rest=[]
for i,r in enumerate(rows):
    if y-PITCH<FOOT: rest=rows[i:]; T(X0,y,f"... continued on sheet 2 ({len(rest)} more rows)",fontsize=8,style="italic"); break
    row(y,r,i); y-=PITCH
T(0.03,0.03,"Drawn by Sketch from spec.json. CHECK ALL DIMENSIONS BEFORE CUTTING.",fontsize=9,style="italic")
T(0.80,0.03,f"SHEET 1 OF {2 if rest else 1}",fontsize=9,weight="bold")
fig.savefig(f"{V}/drawing.png",dpi=110); plt.close(fig); print(f"{V}/drawing.png")
import hashlib
json.dump(dict(units=U,dims=DRAWN,png_sha256=hashlib.sha256(open(f"{V}/drawing.png","rb").read()).hexdigest(),note="written by spec_drawing.py; every value comes from parts.json dims (spec formulas)"),open(f"{V}/drawing_dims.json","w"),indent=1,default=float)
if os.path.exists(f"{V}/drawing_2.png"): os.remove(f"{V}/drawing_2.png")
if rest:
    fig=plt.figure(figsize=(W,H)); X0=0.05; y=0.95
    fig.patches.append(plt.Rectangle((0.01,0.01),0.98,0.98,transform=fig.transFigure,fill=False,lw=1.5))
    COLS=[(0,"MARK"),(0.06,"QTY"),(0.11,"PART"),(0.30,"MATERIAL"),(0.48,"SIZE")]
    T(X0,y,"CUT / PART LIST (continued)",fontsize=13,weight="bold"); y-=0.04; y=table_header(y)
    for i,r in enumerate(rest):
        if y-PITCH<FOOT: T(X0,y,"... list truncated; see bom.csv for every row",fontsize=8,style="italic"); break
        row(y,r,i); y-=PITCH
    T(0.80,0.03,"SHEET 2 OF 2",fontsize=9,weight="bold")
    fig.savefig(f"{V}/drawing_2.png",dpi=110); plt.close(fig); print(f"{V}/drawing_2.png")

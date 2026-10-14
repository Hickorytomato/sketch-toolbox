#!/usr/bin/env python3
"""export_dxf.py PARTS.json OUTDIR -> one DXF per flat part (inches) for plasma/laser cutting + flats_preview.png"""
import sys,os,json,ezdxf,matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
d=json.load(open(sys.argv[1])); o=sys.argv[2]; os.makedirs(o,exist_ok=True); outs=[]
for f in d["flats"]:
    doc=ezdxf.new("R2010"); doc.units=ezdxf.units.IN; msp=doc.modelspace(); doc.layers.add("CUT",color=1); doc.layers.add("HOLES",color=5); doc.layers.add("POCKET",color=30)
    s=f["shape"]
    if s=="circle": msp.add_circle((0,0),f["r"],dxfattribs={"layer":"CUT"})
    elif s=="annulus": msp.add_circle((0,0),f["r"],dxfattribs={"layer":"CUT"}); msp.add_circle((0,0),f["ri"],dxfattribs={"layer":"CUT"})
    elif s in("rect","rect_holes"): msp.add_lwpolyline([(0,0),(f["w"],0),(f["w"],f["h"]),(0,f["h"])],close=True,dxfattribs={"layer":"CUT"})
    elif s=="poly":
        msp.add_lwpolyline(f["outer"],close=True,dxfattribs={"layer":"CUT"})
        for ip in f.get("inner_poly",[]): msp.add_lwpolyline(ip,close=True,dxfattribs={"layer":"CUT"})
        for pk in f.get("pockets",[]): msp.add_lwpolyline(pk["poly"],close=True,dxfattribs={"layer":"POCKET"})   # depth in parts.json / drawings
    for x,y,r in f.get("holes",[]): msp.add_circle((x,y),r,dxfattribs={"layer":"HOLES"})
    p=f"{o}/{f['name']}.dxf"; doc.saveas(p); outs.append(p)
import math
n=max(1,len(outs)); nc=min(4,n); nr=math.ceil(n/nc)
fig,axs=plt.subplots(nr,nc,figsize=(4.5*nc,3.8*nr),squeeze=False); axs=axs.ravel()
for ax in axs[len(outs):]: ax.axis("off")
for ax,p in zip(axs,outs):
    doc=ezdxf.readfile(p); ax.set_title(os.path.basename(p)+'  (inches)',fontsize=11); ax.set_aspect("equal"); ax.grid(alpha=0.3)
    for e in doc.modelspace():
        if e.dxftype()=="CIRCLE": ax.add_patch(plt.Circle((e.dxf.center.x,e.dxf.center.y),e.dxf.radius,fill=False,color="red" if e.dxf.layer=="CUT" else "blue"))
        elif e.dxftype()=="LWPOLYLINE": pts=list(e.get_points("xy"))+[e.get_points("xy")[0]]; ax.plot(*zip(*pts),color="orange" if e.dxf.layer=="POCKET" else "red")
    ax.autoscale_view()
fig.tight_layout(); fig.savefig(f"{o}/flats_preview.png",dpi=80); print("\n".join(outs+[f"{o}/flats_preview.png"]))

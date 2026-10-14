#!/usr/bin/env python3
"""coupons.py VDIR OUTDIR -> coupons/ (tiny STL/DXF test pieces) + coupons.pdf + coupons-<n>.png + coupons.json   (v1.0.5 feature 2)
Fit-test coupons for the tight-fit features in THIS build, so the user tests a 5-minute piece before the real part:
  thread      print: short external stud + 3 nut rings at clearance c-0.2 / c / c+0.2 mm (1/2/3 notches)
  pip_gap     print-in-place: blocks in pockets at gap g-0.2 .. g+0.3 mm (notch count = step)
  slot        printed slides/press fits: slot gauge -0.2..+0.4 mm around the clearance + a key
  dado        wood dados: router/laser step gauge t-0.010 .. t+0.020 in, + table-saw test-cut card
  kerf_comb   laser/plasma: 1.000 in square + 5-strip comb (kerf = gap / 5) + hole row
  saw_kerf    hand/saw builds with no measured saw kerf: test-cut card
Each coupon says how to read it and the exact feedback.py command that stores the result (applied to future builds)."""
import sys,os,json,math,glob,subprocess,textwrap
B=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,B)
import numpy as np, trimesh, ezdxf
V,O=sys.argv[1],sys.argv[2]; CD=f"{O}/coupons"; os.makedirs(CD,exist_ok=True)
d=json.load(open(f"{V}/parts.json")); S=json.load(open(f"{V}/spec.json")); PRM=d["params"]; U=d["params"].get("units","in")
M=json.load(open(f"{B}/machines.json")); import learn, kerf as _k
PROJ=os.path.basename(os.path.dirname(os.path.abspath(V)))
def ev(x):
    if isinstance(x,str) and x.startswith("="): return eval(x[1:],{"math":math},dict(PRM))
    return x
FIL=str(PRM.get("filament") or next((p.get("material") for p in d.get("print_parts",[])),"PLA"))
C=[]
def box(x0,y0,z0,x1,y1,z1): return trimesh.creation.box(extents=[x1-x0,y1-y0,z1-z0],transform=trimesh.transformations.translation_matrix([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]))
def mesh_of(man): k=man.to_mesh(); return trimesh.Trimesh(k.vert_properties[:,:3],k.tri_verts,process=True)
def notches(man,R,n,z,h):
    import manifold3d as mf
    for i in range(n): man=man-mf.Manifold.cube([1.2,2.2,h+0.2]).translate([R-1.0,-1.1,z-0.1]).rotate([0,0,18*i])
    return man
# ---- print: threads
import kit
for p in S.get("parts",[]):
    for t in (p.get("args",{}).get("threads") or []):
        if t.get("side")!="internal": continue
        r=ev(t["r"]); P_=ev(t["pitch"]); dep=ev(t.get("depth",P_*0.6)); c0=ev(t.get("clearance",0.4))
        L=learn.get("printer",FIL).get("thread_clearance_mm",0); cs=[round(max(0.1,c0+dx),2) for dx in (-0.2,0,0.2)]
        stud=kit.round_mesh(r=r,h=3+P_*2.5,threads=[dict(side="external",r=r,z=3,pitch=P_,turns=1.5,depth=dep)])
        import manifold3d as mf
        stud=stud+mf.Manifold.cylinder(3,r+dep+4,r+dep+4,96)
        files=[f"coupons/thread_stud.stl"]; mesh_of(stud).export(f"{O}/{files[0]}")
        for i,c in enumerate(cs):
            Ro=r+dep+c+3; ring=kit.round_mesh(r=Ro,h=P_*2.5,threads=[dict(side="internal",r=r,z=0,pitch=P_,turns=1.5,depth=dep,clearance=c)])
            ring=notches(ring,Ro,i+1,0,P_*2.5); fn=f"coupons/thread_ring_{i+1}_c{c:.2f}mm.stl"; mesh_of(ring).export(f"{O}/{fn}"); files.append(fn)
        C.append(dict(id="thread",part=p["name"],machine="printer",material=FIL,process="3D print",files=files,steps=cs,current=c0,learned=L,unit="mm",
            read=[f"Print the stud and the 3 rings ({FIL}, same settings as the real part, ~15 min).",
                  "Screw each ring onto the stud. Notches on the ring = ring number (1 = tightest).",
                  "Pick the ring that turns by hand with no wobble. Ring 2 = the clearance in this build."],
            feedback=f'bin/feedback.py {PROJ} --coupon thread --pick N   (N = ring that fits; ring 1/2/3 = {cs[0]}/{cs[1]}/{cs[2]} mm)'))
# ---- print: print-in-place gap
pip=[pp for pp in d.get("print_parts",[]) if pp.get("assembly")=="print_in_place"]
if pip:
    import manifold3d as mf
    g0=float(pip[0].get("clearance") or 0.5); gs=[round(max(0.1,g0+dx),2) for dx in (-0.2,-0.1,0,0.1,0.2,0.3)]
    base=mf.Manifold.cube([8+14*len(gs),18,3]); blocks=[]
    for i,g in enumerate(gs):
        x=6+14*i; base=base-mf.Manifold.cube([10,10,3.2]).translate([x,4,1.0])
        blk=mf.Manifold.cube([10-2*g,10-2*g,2.4]).translate([x+g,4+g,1.0+g])
        for k in range(i+1): blk=blk-mf.Manifold.cube([0.8,1.5,0.8]).translate([x+g+1+1.4*k,4+g+0.5,1.0+g+1.7])
        blocks.append(blk)
    man=base+mf.Manifold.batch_boolean(blocks,mf.OpType.Add); fn="coupons/pip_gap_gauge.stl"; mesh_of(man).export(f"{O}/{fn}")
    C.append(dict(id="pip_gap",part=pip[0]["name"],machine="printer",material=FIL,process="3D print (print in place)",files=[fn],steps=gs,current=g0,unit="mm",learned=learn.get("printer",FIL).get("pip_gap_mm",0),
        read=["Print flat as-is (~10 min). Each block floats in its pocket at a bigger gap, left to right (notches on the block = step).",
              "Push each block with a fingernail. The first block that breaks free cleanly = the smallest gap your printer can do.",
              f"Steps: "+", ".join(f"{i+1}={g} mm" for i,g in enumerate(gs))],
        feedback=f"bin/feedback.py {PROJ} --coupon pip_gap --pick N"))
# ---- print: slides / press fits (dovetails, fit dims, *_clear values that aren't threads)
sl=[(k,v["v"]) for k,v in S.get("values",{}).items() if "clear" in k and k!="clear" and isinstance(v.get("v"),(int,float)) and v.get("unit")=="mm"]
fits=[dm for dm in S.get("dims",[]) if dm.get("fit") or dm.get("fit_class")]
if d.get("print_parts") and (sl or fits or any(p.get("kind")=="dovetail" for p in S.get("parts",[]))):
    import manifold3d as mf
    c0=float(sl[0][1]) if sl else 0.2; W=6.0; st=[round(c0+dx,2) for dx in (-0.2,-0.1,0,0.1,0.2,0.3,0.4)]; st=[s for s in st if s>=0] or [0]
    bar=mf.Manifold.cube([6+12*len(st),20,5])
    for i,s in enumerate(st):
        bar=bar-mf.Manifold.cube([W+2*s,14,5.2]).translate([6+12*i,6,-0.1])
        for k in range(i+1): bar=bar-mf.Manifold.cube([0.8,2,0.6]).translate([6+12*i+1.2*k,1,4.5])
    key=mf.Manifold.cube([W,30,5]); fn=["coupons/slot_gauge.stl","coupons/slot_key.stl"]; mesh_of(bar).export(f"{O}/{fn[0]}"); mesh_of(key).export(f"{O}/{fn[1]}")
    C.append(dict(id="slot",part=(sl[0][0] if sl else "fit"),machine="printer",material=FIL,process="3D print (slides / press fits)",files=fn,steps=st,current=c0,unit="mm",learned=learn.get("printer",FIL).get("slot_clearance_mm",0),
        read=["Print the gauge and the key (~12 min). Slot N has N notches; clearance per side grows left to right.",
              "Slide the key into each slot. Press fit = first slot it enters with firm thumb pressure; slide fit = first slot it slides through freely.",
              "Steps per side: "+", ".join(f"{i+1}={s} mm" for i,s in enumerate(st))],
        feedback=f"bin/feedback.py {PROJ} --coupon slot --pick N"))
# ---- wood: dados (router/laser gauge DXF + table-saw test card)
dados=[j for j in d.get("jointrec",[]) if j.get("type")=="dado"]
if dados:
    t=next((fl["thickness"] for fl in d["flats"] if fl["name"]==dados[0]["from"]),0.75); mat=next((fl.get("material","plywood") for fl in d["flats"] if fl["name"]==dados[0]["from"]),"plywood")
    cl0=float(dados[0].get("clear_used",0.01 if U=="in" else 0.2))*(1 if U=="in" else 1/25.4)   # per-side clearance in this build (in)
    # total clearance (dado width - sheet), kept inside the catalog's +0.002..+0.020 in (rules #96) so any pick still ships
    st=sorted({0.002,0.005,0.0075,0.010,0.0125,0.015,0.020,round(min(max(cl0,0.002),0.020),4)}); W_=[round(t+c_,4) for c_ in st]
    doc=ezdxf.new("R2010"); ms=doc.modelspace(); Wd=1.0+0.9*len(st)
    ms.add_lwpolyline([(0,0),(Wd,0),(Wd,2.5),(0,2.5)],close=True,dxfattribs={"layer":"CUT"})
    for i,s in enumerate(st):
        x=0.5+0.9*i; s=W_[i]; ms.add_lwpolyline([(x,0.8),(x+s,0.8),(x+s,2.5),(x,2.5)],close=True,dxfattribs={"layer":"POCKET_DEPTH_0.25"})
        for k in range(i+1): ms.add_circle((x+0.1+0.12*k,0.4),0.04,dxfattribs={"layer":"ENGRAVE"})
    fn="coupons/dado_gauge.dxf"; doc.saveas(f"{O}/{fn}")
    C.append(dict(id="dado",part=dados[0]["into"],machine=("router" if M.get("router",{}).get("enabled") else "saw"),material=mat,process="router / table-saw dado",files=[fn],steps=st,current=round(cl0,4),unit="in",widths=W_,learned=learn.get("router",mat).get("dado_clear_in"),
        read=[f"Router: cut dado_gauge.dxf in a scrap of the SAME sheet (pockets 1/4 in deep; dots = step). Table saw: cut test dados in scrap at the widths below.",
              f"Push an offcut of the real {t} in sheet into each dado. Pick the first one it enters with hand pressure (no mallet).",
              "Dado widths: "+", ".join(f"{i+1}={w} (+{c_})" for i,(w,c_) in enumerate(zip(W_,st)))+" in"],
        feedback=f"bin/feedback.py {PROJ} --coupon dado --pick N"))
# ---- laser / plasma kerf comb (only for machines that got programs in this build)
for mn in ("laser","plasma"):
    progs=[p for p in glob.glob(f"{O}/gcode_*/*.json") if f"_{mn}" in os.path.basename(p)]
    if not progs: continue
    g=json.load(open(progs[0])); mat=g.get("material","steel"); th=g.get("thickness",0.125); kf,ks=_k.lookup(mn,M[mn],mat,th)
    doc=ezdxf.new("R2010"); ms=doc.modelspace(); lay={"layer":"CUT"}
    ms.add_lwpolyline([(0,0),(1,0),(1,1),(0,1)],close=True,dxfattribs=lay)
    for i in range(5): ms.add_lwpolyline([(1.5+0.5*i,0),(2.0+0.5*i,0),(2.0+0.5*i,1),(1.5+0.5*i,1)],close=True,dxfattribs=lay)
    for i,hd in enumerate((0.125,0.1875,0.25,0.3125,0.375)): ms.add_circle((0.3+0.5*i,1.6),hd/2,dxfattribs=lay)
    ms.add_lwpolyline([(-0.1,-0.1),(4.1,-0.1),(4.1,2.0),(-0.1,2.0)],close=True,dxfattribs=lay)
    fn=f"coupons/kerf_comb_{mn}.dxf"; doc.saveas(f"{O}/{fn}")
    C.append(dict(id=f"kerf_{mn}",part="all cut parts",machine=mn,material=mat,process=f"{mn} kerf",files=[fn],steps=[],current=kf,current_src=ks,unit="in",thickness=th,
        read=[f"Cut kerf_comb_{mn}.dxf in {th} in {mat} with kerf compensation OFF (raw lines). ~1 min.",
              "Measure the square with calipers across the flats: kerf = 1.000 - measured.",
              "Check: push the 5 strips together in their frame slot; the leftover gap / 5 = kerf. Hole row = 1/8..3/8 in: smallest clean hole."],
        feedback=f"bin/tools_setup.py --kerf-test {mn} {mat} {th} --drawn 1.0 --measured M   (or bin/feedback.py {PROJ} --coupon kerf_{mn} --measured M)"))
# ---- v1.0.6 tolerance coupon: parts bolted across machines -> measure each machine's real hole position/size error
try:
    import pro as _pro; _P=_pro._procs(d,O); toin_=1 if U=="in" else 1/25.4; _tm={}
    for j in d.get("jointrec",[]):
        if j.get("type")!="bolted": continue
        ms_={m_ for n_ in j["parts"] for m_,p_,_g in _P.get(n_,[])}
        if len(ms_)<2: continue
        for n_ in j["parts"]:
            for m_,p_,_g in _P.get(n_,[]):
                if p_!="drill": _tm.setdefault(m_,(float(j.get("d"))*toin_,(_g or {}).get("material") or FIL,(_g or {}).get("thickness")))
    for mn,(hd,mat,th) in sorted(_tm.items()):
        hd=round(hd,4); L_=learn.get(mn,"*")
        if mn=="printer":
            sp=40.0; pl=box(0,0,0,60,60,3)
            import manifold3d as mf
            P_=mf.Manifold(mf.Mesh(vert_properties=np.asarray(pl.vertices,np.float32),tri_verts=np.asarray(pl.faces,np.uint32)))
            for cx,cy in ((10,10),(50,10),(10,50),(50,50)):
                cyl=trimesh.creation.cylinder(radius=hd*25.4/2,height=10,sections=64); cyl.apply_translation([cx,cy,1.5])
                P_=P_-mf.Manifold(mf.Mesh(vert_properties=np.asarray(cyl.vertices,np.float32),tri_verts=np.asarray(cyl.faces,np.uint32)))
            fn=f"coupons/tolerance_{mn}.stl"; mesh_of(P_).export(f"{O}/{fn}"); uu="mm"; dd=round(hd*25.4,2)
        else:
            sp=2.0; doc=ezdxf.new("R2010"); ms=doc.modelspace(); lay={"layer":"CUT"}
            for cx,cy in ((0.5,0.5),(2.5,0.5),(0.5,2.5),(2.5,2.5)): ms.add_circle((cx,cy),hd/2,dxfattribs=lay)
            ms.add_lwpolyline([(0,0),(3,0),(3,3),(0,3)],close=True,dxfattribs=lay)
            fn=f"coupons/tolerance_{mn}.dxf"; doc.saveas(f"{O}/{fn}"); uu="in"; dd=hd
        C.append(dict(id=f"tol_{mn}",part="bolt holes shared with other machines",machine=mn,material=mat,process=f"{mn} hole position/size",files=[fn],steps=[],
            current=dict(pos=_pro.xtol(mn,"printer" if mn=="printer" else ("router" if mn=="router" else mn))[0],size=_pro.xtol(mn,mn)[1],src=_pro.xtol(mn,mn)[2]),unit=uu,drawn_spacing=sp,drawn_dia=dd,
            read=[f"Make {os.path.basename(fn)} on the {mn} exactly like a real part ({'normal print settings' if mn=='printer' else 'kerf compensation ON, as the real program'}).",
                  f"Calipers: measure the 4 hole diameters (drawn {dd:g} {uu}) and the 4 side spacings centre to centre (drawn {sp:g} {uu}; = outside-to-outside of two holes minus one diameter).",
                  "The cross-machine bolt check then uses your machine's measured error (x1.25 margin) instead of Sketch's default tolerance."],
            feedback=f"bin/feedback.py {PROJ} --coupon tol_{mn} --dia D1,D2,D3,D4 --spacing S1,S2,S3,S4"))
except Exception as e: print("tolerance coupon skipped:",e)
# ---- saw kerf (hand / saw builds) when the owner never measured it
if os.path.exists(f"{O}/cut_day.json"):
    wk,ws=_k.saw()
    if not ws.startswith("measured"):
        C.append(dict(id="saw_kerf",part="all saw cuts",machine="saw",material="scrap",process="saw kerf",files=[],steps=[],current=wk,current_src=ws,unit="in",
            read=["Mark two lines exactly 4.000 in apart on a scrap. Cut on the waste side of line 1 (blade just touching it).",
                  "Measure the slot the blade left with calipers (or: the board width before minus after one rip).",
                  f"This build assumed {wk} in ({ws[:70]})."],
            feedback=f'bin/tools_setup.py --saw "your saw" --saw-kerf K'))
json.dump(dict(build_id=d.get("build_id"),coupons=C),open(f"{O}/coupons.json","w"),indent=1)
# ---- PDF + phone PNGs (pictures of each coupon)
from reportlab.lib.pagesizes import letter; from reportlab.pdfgen import canvas; from reportlab.lib.units import inch; from reportlab.lib.utils import ImageReader
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
def pic(cp,path):
    fig=plt.figure(figsize=(5,3),dpi=110)
    stl=[f for f in cp["files"] if f.endswith(".stl")]; dxf=[f for f in cp["files"] if f.endswith(".dxf")]
    if stl:
        ax=fig.add_subplot(111,projection="3d"); x0=0
        for f in stl:
            m=trimesh.load(f"{O}/{f}"); m.apply_translation([x0-m.bounds[0][0],-m.bounds[0][1],0]); x0+=m.extents[0]+5
            ax.add_collection3d(__import__("mpl_toolkits.mplot3d.art3d",fromlist=["x"]).Poly3DCollection(m.triangles,facecolors=[(0.35+0.55*max(0,float(np.dot(nn,[0.4,-0.5,0.77]))),)*2+(0.95,) for nn in m.face_normals],edgecolor="none"))
        ym=max(trimesh.load(f"{O}/{f}").extents[1] for f in stl); zm=max(trimesh.load(f"{O}/{f}").extents[2] for f in stl)
        ax.set_xlim(0,x0); ax.set_ylim(0,ym); ax.set_zlim(0,zm); ax.set_box_aspect((x0,ym,zm)); ax.set_axis_off(); ax.view_init(40,-70)
    elif dxf:
        ax=fig.add_subplot(111); doc=ezdxf.readfile(f"{O}/{dxf[0]}")
        for e in doc.modelspace():
            col={"CUT":"red","ENGRAVE":"black"}.get(e.dxf.layer,"blue")
            if e.dxftype()=="LWPOLYLINE": q=[p[:2] for p in e.get_points()]; q.append(q[0]); ax.plot(*zip(*q),color=col,lw=1)
            if e.dxftype()=="CIRCLE": ax.add_patch(plt.Circle((e.dxf.center.x,e.dxf.center.y),e.dxf.radius,fill=False,color=col))
        ax.set_aspect("equal"); ax.axis("off")
    else:
        ax=fig.add_subplot(111); ax.axis("off"); ax.plot([0,4],[0,0],"k-",lw=6); ax.plot([0,0],[-.3,.3],"r-"); ax.plot([4,4],[-.3,.3],"r-"); ax.text(2,0.4,"4.000 in",ha="center"); ax.set_xlim(-.5,4.5); ax.set_ylim(-1,1)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)
PW,PH=letter; c=canvas.Canvas(f"{O}/coupons.pdf",pagesize=letter)
for i,cp in enumerate(C or [dict(id="none",read=["No tight-fit features in this build: no coupons needed."],files=[],feedback="",process="-",part="-",material="-",machine="-",steps=[],unit="")]):
    c.setFont("Helvetica-Bold",16); c.drawString(0.5*inch,PH-0.6*inch,f'FIT-TEST COUPON {i+1}/{max(len(C),1)}: {cp["id"]}')
    c.setFont("Helvetica",9); c.drawString(0.5*inch,PH-0.8*inch,f'{d.get("title","")} - build {d.get("build_id","?")} - test before cutting/printing the real part')
    y=PH-1.1*inch
    if cp["files"] or cp["id"]=="saw_kerf":
        pp=f"{CD}/_{cp['id']}.png"; pic(cp,pp); c.drawImage(ImageReader(pp),0.5*inch,y-3.3*inch,5.5*inch,3.3*inch); os.remove(pp); y-=3.5*inch
    c.setFont("Helvetica",11)
    for t in [f'For: {cp["part"]}   process: {cp["process"]}   machine: {cp["machine"]}   material: {cp["material"]}']+([f'Current value: {cp["current"]} {cp["unit"]}'+(f' ({cp.get("current_src")})' if cp.get("current_src") else "")] if cp.get("current") is not None else [])+(["Files: "+", ".join(cp["files"])] if cp["files"] else []):
        for tl in textwrap.wrap(t,95): c.drawString(0.5*inch,y,tl); y-=14
    y-=6; c.setFont("Helvetica-Bold",12); c.drawString(0.5*inch,y,"HOW TO READ IT"); y-=16; c.setFont("Helvetica",11)
    for k,t in enumerate(cp["read"]):
        for j,tl in enumerate(textwrap.wrap(f"{k+1}. {t}",95)): c.drawString(0.5*inch,y,tl); y-=14
    if cp["feedback"]:
        y-=6; c.setFont("Helvetica-Bold",12); c.drawString(0.5*inch,y,"THEN TELL SKETCH (future builds use it)"); y-=16; c.setFont("Courier",9.5)
        for tl in textwrap.wrap(cp["feedback"],100): c.drawString(0.5*inch,y,tl); y-=12
    c.showPage()
c.save(); subprocess.run(["pdftoppm","-png","-r","100",f"{O}/coupons.pdf",f"{O}/coupons"],check=False)
print(f"coupons -> {O}: {len(C)} ("+", ".join(x["id"] for x in C)+")")

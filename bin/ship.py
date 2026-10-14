#!/usr/bin/env python3
"""ship.py PROJECT [--v N] [FILE ...]   THE SHIP GATE: nothing goes to a user unless it passed here.
   ship.py --verify FILE                 is this exact file (sha256) in a ship manifest?
   ship.py --check-print STL [--assembly print_in_place] [--bodies N] [--clearance MM] [--units mm|in]   gate one mesh (tests)
Checks every deliverable of PROJECT/vN (made by design.sh --final), writes PROJECT/vN/ship/ only when all pass:
 PRINT   per part: fuse overlapping shells into one manifold watertight solid; exactly 1 connected body (print-in-place assemblies:
         each body on its own + gaps >= clearance (default 0.5 mm, printers.json pip_clearance_mm), [WARN] > 1 mm); 2 mm min wall/feature (3D print only; thin spots thickened when safe);
         flat base (<= 0.4 mm trim when safe); bed fit (split by print3d); real PrusaSlicer time/grams/cost. [WARN]: overhangs, tiny bed
         contact / tip-over, unsupported islands, + an auto-orient suggestion.
 DRAWING every dimension comes from a spec formula, equals the spec, matches the model geometry; units match.
 CUT     closed contours, kerf/tool offset applied, everything inside the sheet, nested count == BOM count per material+thickness.
 BOM     every model part exactly once with right qty; every BUY item + hardware on shopping_list.csv; no orphan rows.
 COST    every line from prices.json / prices_default.json / slicer / nest; sources recorded.
 HAND    every step references a real part; its sizes match the model.
 ALSO    every file must be byte-identical to what the toolbox generated (fab/.gen.json).
Output: ship/<MACHINE>/ files, ship/ship_manifest.json (file, sha256, checks, slicer numbers, cost sources), ship/send_list.txt,
ship/<project>_vN_all.zip (send last). Exit 0 = shipped, 1 = [FAIL] (no ship/ folder is left behind)."""
import sys,os,json,glob,hashlib,shutil,re,math,csv,subprocess,time,zipfile
B=os.path.dirname(os.path.abspath(__file__)); ROOT=os.environ.get("SKETCH_ROOT") or os.path.dirname(B)
a=sys.argv[1:]
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
REG=os.path.join(ROOT,".ship_registry.jsonl")
# ---------------------------------------------------------------- verify
if a and a[0]=="--verify":
    f=a[1]; h=sha(f); hits=[]
    if os.path.exists(REG):
        for l in open(REG):
            try: r=json.loads(l)
            except Exception: continue
            if r.get("sha256")==h: hits.append(r)
    for m in glob.glob(f"{ROOT}/**/ship/ship_manifest.json",recursive=True):
        try:
            for e in json.load(open(m))["files"]:
                if e["sha256"]==h: hits.append(dict(manifest=m,path=e["path"]))
        except Exception: pass
    if hits: print(f"[SHIPPED] {os.path.basename(f)} passed the ship gate: {hits[0].get('manifest',hits[0].get('project'))} ({hits[0].get('path')})"); sys.exit(0)
    print(f"[NOT SHIPPED] {os.path.basename(f)} (sha256 {h[:12]}) is not in any ship manifest. Do not send it; run ship.py on its project."); sys.exit(1)
import numpy as np, trimesh, manifold3d as mf
PR=json.load(open(f"{B}/printers.json"))
MIN=float(PR.get("rules",{}).get("min_print_feature_mm",2.0))
R=[]   # check results
def res(area,target,status,why,**k): R.append(dict(area=area,target=target,status=status,why=why,**k)); print(f"[{status}] {area} {target}: {why}")
def tomf(m): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices,np.float32),tri_verts=np.asarray(m.faces,np.uint32)))
def totm(M): k=M.to_mesh(); return trimesh.Trimesh(k.vert_properties[:,:3],k.tri_verts,process=True)
# ---------------------------------------------------------------- print gate
sys.path.insert(0,B); import meshfuse
def fuse(m,name): return meshfuse.fuse(m,name)
def thickness(m,n=2500):
    """inward ray from each surface sample; only counts as wall thickness when it lands on an opposite-facing wall
    (normals within ~45 deg of antiparallel) - grazing hits at edges/fillets are not walls"""
    n=int(max(n,min(80000,m.area/0.5)))   # >= 2 samples per mm2 so small thin features (petals) are seen
    pts,fi=trimesh.sample.sample_surface_even(m,n); nrm=m.face_normals[fi]
    loc,ri,ti=m.ray.intersects_location(pts-nrm*1e-3,-nrm,multiple_hits=False)
    th=np.full(len(pts),np.inf); opp=(m.face_normals[ti]*nrm[ri]).sum(1)<-0.7
    th[ri[opp]]=np.linalg.norm(loc[opp]-pts[ri[opp]],axis=1)
    return pts,nrm,th
def _thin_bad(m,pts,th,mask):
    """thin if >= 3 mm2 of surface is under MIN (absolute area, so a small petal on a big vase still counts)"""
    a=m.area/len(pts); return float(mask.sum()*a)
def _exempt(pts,bands):
    ex=np.zeros(len(pts),bool)
    for p0,p1,r,dep in bands or ():
        ax=p1-p0; L=np.linalg.norm(ax); ax=ax/L; v=pts-p0; t=v@ax; rad=np.linalg.norm(v-np.outer(t,ax),axis=1)
        ex|=(t>-0.5)&(t<L+0.5)&(rad>r-dep-0.8)&(rad<r+dep+0.8)
    return ex
def thin_fix(m,name,bands=None):
    """thin spots -> union 2 mm balls on the mid-line of each thin chord (local offset to MIN). Returns (mesh, note) or (None, reason)."""
    pts,nrm,th=thickness(m); thin=(th<MIN-0.1)&~_exempt(pts,bands); pct=100*thin.mean(); ta=_thin_bad(m,pts,th,thin)
    if ta<3: return m,("thread teeth exempt (form feature)" if bands else None),round(float(th[np.isfinite(th)].min()),2)
    th0=th[thin].min() if thin.any() else MIN
    if pct>45: return None,f"{pct:.0f}% of {name} is thinner than {MIN:g} mm - too much to thicken safely; make it at least {MIN:g} mm thick in the design",None
    for it in range(8):
        pts,nrm,th=thickness(m,12000); thin=(th<MIN-0.1)&~_exempt(pts,bands)
        if _thin_bad(m,pts,th,thin)<1.0 and it: break
        mids=pts[thin]-nrm[thin]*(th[thin][:,None]/2)
        ball=trimesh.creation.icosphere(subdivisions=1,radius=MIN/2+0.15+0.1*it)
        Bs=[tomf(ball.copy().apply_translation(c)) for c in mids]
        z0=float(m.bounds[0][2]); M=mf.Manifold.batch_boolean([tomf(m)]+Bs,mf.OpType.Add).trim_by_plane([0,0,1],z0); m=totm(M)   # never grow below the bed face
    pts,nrm,th=thickness(m); k2=(th<MIN-0.1)&~_exempt(pts,bands); pct2=100*k2.mean()
    if _thin_bad(m,pts,th,k2)>=3: return None,f"{name}: thin spots under {MIN:g} mm remain after thickening ({pct2:.1f}% of the surface) - thicken them in the design",None
    return m,f"thickened {ta:.0f} mm2 of features thinner than {MIN:g} mm (thinnest {float(th0):.2f} mm) to {MIN:g} mm",round(float(th[np.isfinite(th)].min()),2)
def body_gap(A,Bm,n=4000):
    p,_=trimesh.sample.sample_surface_even(A,n); q,_=trimesh.sample.sample_surface_even(Bm,n)
    d1=trimesh.proximity.closest_point(Bm,p)[1]; d2=trimesh.proximity.closest_point(A,q)[1]
    return float(min(d1.min(),d2.min()))
def base(m):
    z0=m.bounds[0][2]; nz=m.face_normals[:,2]; zc=m.triangles_center[:,2]
    return float(m.area_faces[(nz<-0.98)&(zc<z0+0.2)].sum())
def islands(m,fil):
    zs=np.arange(m.bounds[0][2]+0.3,m.bounds[1][2],0.4); prev=None; n=0; at=[]
    try: secs=m.section_multiplane([0,0,0],[0,0,1],list(zs))
    except Exception: return 0,[]
    for z,s in zip(zs,secs):
        polys=list(s.polygons_full) if s is not None else []
        if prev is not None:
            for P in polys:
                if P.area>2 and not any(P.intersects(Q) for Q in prev): n+=1; at.append(round(float(z),1))
        prev=polys
    return n,at
def overhang(m,fil):
    lim=math.radians(90-PR["filaments"].get(fil,PR["filaments"]["PLA"])["max_overhang_deg"]); nz=m.face_normals[:,2]; zc=m.triangles_center[:,2]
    return float(m.area_faces[(nz<-math.cos(lim))&(zc>m.bounds[0][2]+0.3)].sum())
ORIENTS=[[0,0,0],[180,0,0],[90,0,0],[-90,0,0],[0,90,0],[0,-90,0]]
def rot(m,r,T=False):
    m=m.copy(); M4=np.eye(4)
    for ax,ang in zip(((1,0,0),(0,1,0),(0,0,1)),r):
        if ang: Rm=trimesh.transformations.rotation_matrix(math.radians(ang),ax); m.apply_transform(Rm); M4=Rm@M4
    t=-m.bounds[0]; m.apply_translation(t); M4=trimesh.transformations.translation_matrix(t)@M4
    return (m,M4) if T else m
def gate_print(m,name,fil="PLA",assembly=None,nbodies=None,clearance=None,prn=None,bands=None):
    """returns fused, gated mesh or None (FAIL recorded)"""
    np.random.seed(20261014)   # same mesh -> same verdict every run
    prn=prn or PR["printers"][PR["active"]]
    clr=float(clearance if clearance is not None else prn.get("pip_clearance_mm",PR.get("rules",{}).get("pip_clearance_mm",0.5)))
    r,err=fuse(m,name)
    if err: res("print",name,"FAIL",err); return None
    bodies,nshell=r
    if nshell>1 and len(bodies)<nshell: res("print",name,"FIXED",f"fused {nshell} overlapping shells into {len(bodies)} solid bod" + ("y" if len(bodies)==1 else "ies"))
    pip=assembly=="print_in_place"
    if not pip and len(bodies)>1:
        vols=sorted((b.volume for b in bodies),reverse=True)
        res("print",name,"FAIL",f"{len(bodies)} separate pieces after fusing: {len(bodies)-1} floating piece(s) ({', '.join(f'{v:.0f} mm3' for v in vols[1:4])}) don't touch the main body. Move them into the part (overlap >= 0.5 mm) or, for a moving print-in-place assembly, set \"assembly\": \"print_in_place\"."); return None
    if pip and nbodies and len(bodies)!=int(nbodies):
        res("print",name,"FAIL",f"print-in-place assembly should have {nbodies} bodies but has {len(bodies)} (pieces fused together or a loose bit)"); return None
    out=[]
    for i,b in enumerate(bodies):
        bn=name if len(bodies)==1 else f"{name} body {i+1}"
        if not b.is_watertight: res("print",bn,"FAIL","not watertight after fusing"); return None
        b2,note,mw=thin_fix(b,bn,bands)
        if b2 is None: res("print",bn,"FAIL",note); return None
        if note and note.startswith("thread"): res("print",bn,"PASS",f"one watertight solid, walls >= {MIN:g} mm ({note})")
        elif note: res("print",bn,"FIXED",note)
        else: res("print",bn,"PASS",f"one watertight solid, min wall {mw} mm >= {MIN:g} mm")
        out.append(b2)
    if pip:
        gmin=min(body_gap(out[i],out[j]) for i in range(len(out)) for j in range(i+1,len(out)))
        if gmin<clr-0.02: res("print",name,"FAIL",f"print-in-place gap {gmin:.2f} mm is under the {clr:g} mm clearance: the parts will fuse while printing. Open the gap to >= {clr:g} mm."); return None
        if gmin>1.0: res("print",name,"WARN",f"print-in-place gap {gmin:.2f} mm is over 1.0 mm: the joint will be sloppy")
        else: res("print",name,"PASS",f"print-in-place: {len(out)} bodies, smallest gap {gmin:.2f} mm (clearance {clr:g} mm)")
        M=mf.Manifold.batch_boolean([tomf(b) for b in out],mf.OpType.Add); g=totm(M)
    else: g=out[0]
    g.apply_translation(-g.bounds[0])
    ba=base(g); foot=trimesh.path.polygons.projected(g,normal=[0,0,1]) if False else None
    if ba<20:
        for cut in (0.2,0.3,0.4):
            box=trimesh.creation.box(extents=[g.extents[0]+10,g.extents[1]+10,cut*2]); box.apply_translation([g.extents[0]/2,g.extents[1]/2,0])
            g2=totm(tomf(g)-tomf(box)); g2.apply_translation(-g2.bounds[0])
            if base(g2)>=20 or base(g2)>=0.5*min(g.extents[:2])**2*0.1: res("print",name,"FIXED",f"no flat base: trimmed {cut} mm off the bottom for a {base(g2):.0f} mm2 bed contact"); g=g2; ba=base(g2); break
        else: res("print",name,"FAIL",f"no flat base ({ba:.0f} mm2 touches the bed even after a 0.4 mm trim). Give it a flat bottom or set print_orient."); return None
    else: res("print",name,"PASS",f"flat base {ba:.0f} mm2")
    # printability warnings (never block)
    oh=overhang(g,fil)
    if oh>150: res("print",name,"WARN",f"{oh:.0f} mm2 overhangs steeper than the {fil} limit -> supports needed (Sketch turns them on)")
    h=g.extents[2]; w=min(g.extents[:2])
    if ba<0.15*g.extents[0]*g.extents[1] and h>2.5*math.sqrt(max(ba,1)): res("print",name,"WARN",f"small bed contact ({ba:.0f} mm2) for a {h:.0f} mm tall part: tip-over / detach risk -> add a brim or lay it down")
    ni,at=islands(g,fil)
    if ni: res("print",name,"WARN",f"{ni} unsupported island(s) start mid-air (z ~ {', '.join(map(str,at[:4]))} mm) -> needs supports or another orientation")
    sc=lambda q:overhang(q,fil)+(500 if base(q)<20 else 0)+30*islands(q,fil)[0]
    cur=sc(g); best=min(ORIENTS[1:],key=lambda o:sc(rot(g,o)))
    if sc(rot(g,best))<0.6*cur and cur>150: res("print",name,"WARN",f"auto-orient suggestion: print_orient {best} cuts overhang/island score {cur:.0f} -> {sc(rot(g,best)):.0f}",suggest_orient=best)
    return g
if a and a[0]=="--check-print":
    m=trimesh.load(a[1],force="mesh")
    if "--units" in a and a[a.index("--units")+1]=="in": m.apply_scale(25.4)
    g=gate_print(m,os.path.basename(a[1]),assembly=a[a.index("--assembly")+1] if "--assembly" in a else None,
        nbodies=a[a.index("--bodies")+1] if "--bodies" in a else None,clearance=float(a[a.index("--clearance")+1]) if "--clearance" in a else None)
    if g is not None and "--out" in a: g.export(a[a.index("--out")+1])
    sys.exit(0 if g is not None and not any(r["status"]=="FAIL" for r in R) else 1)
# ---------------------------------------------------------------- project gate
P=a[0]; P=P if os.path.isdir(P) else os.path.join(ROOT,P); P=os.path.abspath(P)
vs=sorted([int(x.rsplit("v",1)[1]) for x in glob.glob(f"{P}/v*") if re.search(r"/v\d+$",x) and os.path.isdir(f"{x}/fab")])
if not vs: print(f"[FAIL] no build files in {P}: run design.sh {P} --final first"); sys.exit(1)
n=int(a[a.index("--v")+1]) if "--v" in a else vs[-1]; V=f"{P}/v{n}"; F=f"{V}/fab"; SH=f"{V}/ship"
want=[x for x in a[1:] if not x.startswith("--") and not (a.index(x)>0 and a[a.index(x)-1]=="--v")]
d=json.load(open(f"{V}/parts.json")); spec=json.load(open(f"{V}/spec.json")); U=d["params"].get("units","in")
shutil.rmtree(SH,ignore_errors=True)
# ---- provenance
GEN=json.load(open(f"{F}/.gen.json")) if os.path.exists(f"{F}/.gen.json") else None
if GEN is None: res("files","fab/","FAIL","no fab/.gen.json: these files were not made by design.sh --final (rerun it)")
else:
    bad=[k for k,h in GEN["files"].items() if os.path.exists(f"{F}/{k}") and sha(f"{F}/{k}")!=h]; gone=[k for k in GEN["files"] if not os.path.exists(f"{F}/{k}")]
    extra=[os.path.relpath(x,F) for x in glob.glob(f"{F}/**/*",recursive=True) if os.path.isfile(x) and not x.endswith(".gen.json") and os.path.relpath(x,F) not in GEN["files"]]
    if bad: res("files","fab/","FAIL",f"{len(bad)} file(s) changed after the toolbox made them: {', '.join(bad[:5])}. Never hand-edit build files: change the spec and rerun design.sh --final.")
    elif gone: res("files","fab/","FAIL",f"missing: {', '.join(gone[:5])} - rerun design.sh --final")
    else: res("files","fab/","PASS",f"{len(GEN['files'])} files byte-identical to what the toolbox generated")
    if extra: res("files","fab/","FAIL",f"files not made by the toolbox: {', '.join(extra[:5])}. Custom parts go in the spec (kind custom_stl) so they pass this gate.")
# ---- model parts
model=sorted(os.path.splitext(os.path.basename(x))[0] for x in glob.glob(f"{V}/step/*.step"))
# ---- drawings
dd=f"{V}/drawing_dims.json"
if not os.path.exists(dd): res("drawing","drawing.png","FAIL","no drawing_dims.json: the drawing was not made by spec_drawing.py")
else:
    D=json.load(open(dd)); ok=True
    if D.get("png_sha256")!=sha(f"{F}/drawing.png"): res("drawing","drawing.png","FAIL","drawing.png is not the image spec_drawing.py made (edited or swapped)"); ok=False
    su=spec.get("units",U)
    if not (D["units"]==U==su): res("drawing","units","FAIL",f"units differ: drawing {D['units']}, model {U}, spec {su}"); ok=False
    vals={k:v["v"] for k,v in d.get("spec_values",{}).items()}
    for k_,v_ in spec.get("derived",{}).items():
        try: vals[k_]=eval(v_[1:] if str(v_).startswith("=") else v_,{"__builtins__":{"min":min,"max":max,"round":round,"abs":abs,"int":int}},{"pi":math.pi,"math":math,**vals})
        except Exception: pass
    m_all=trimesh.load(f"{V}/model.stl",force="mesh"); ext=m_all.extents
    pex={nm:trimesh.load(f,force="mesh").extents for f in glob.glob(f"{V}/stl/*.stl") for nm in [os.path.splitext(os.path.basename(f))[0]]}
    AX={("front","h"):0,("front","v"):2,("top","h"):0,("top","v"):1,("side","h"):1,("side","v"):2}
    tol=lambda x:max(0.02*abs(x),0.03 if U=="in" else 0.5)
    for dm in D["dims"]:
        lab=dm["label"]; e=dm.get("expr")
        if not (isinstance(e,str) and e.startswith("=")): res("drawing",lab,"FAIL",f"dimension '{lab}' = {dm['value']} was typed in, not generated from the spec. Make it a formula of spec values."); ok=False; continue
        try: sv=float(eval(e[1:],{"__builtins__":{"min":min,"max":max,"round":round,"abs":abs,"int":int}},{"pi":math.pi,"math":math,**vals}))
        except Exception as ex: sv=None
        if sv is not None and abs(sv-dm["value"])>1e-3: res("drawing",lab,"FAIL",f"drawing shows {lab} {dm['value']:g} but the spec gives {sv:g}"); ok=False; continue
        ax=AX.get((dm["view"],dm["axis"]))
        if dm.get("span"):
            s0,s1=dm["span"]
            if abs((s1-s0)-dm["value"])>tol(dm["value"]): res("drawing",lab,"FAIL",f"{lab}: arrows span {s1-s0:g} but the label says {dm['value']:g}"); ok=False
        elif ax is not None:
            cands=[ext[ax]]+[x[ax] for x in pex.values()]
            key_=re.search(r"(?i)\b(overall|width|height|depth|length|total|dia)\b",lab) or abs(dm["value"]-ext[ax])<=0.15*ext[ax]
            if key_ and min(abs(c-dm["value"]) for c in cands)>tol(dm["value"]):
                res("drawing",lab,"FAIL",f"{lab} {dm['value']:g} {U} does not match the model (overall {ext[ax]:.3g} {U}, no part measures {dm['value']:g})"); ok=False
    if ok: res("drawing","drawing.png/drawings.pdf","PASS",f"{len(D['dims'])} dimensions all generated from the spec and match the model; units {U}")
    if not os.path.exists(f"{F}/drawings.pdf"): res("drawing","drawings.pdf","FAIL","drawings.pdf missing")
# ---- cut files
import ezdxf
from shapely.geometry import Polygon
M=json.load(open(f"{B}/machines.json"))
base_=lambda s:re.sub(r"_\d+of\d+$","",s)
for nj in glob.glob(f"{F}/nest_*/nest.json"):
    N=json.load(open(nj)); cls=os.path.basename(os.path.dirname(nj))[5:]; okc=True
    for G in N["groups"]:
        W,H=G["sheet"]; W,H=float(W),float(H)
        for p in G["parts"]:
            pts=[q for k in ("outer",) for q in p.get("geom",{}).get(k,{}).get("poly",[])]
            if pts:
                xs=[q[0] for q in pts]; ys=[q[1] for q in pts]
                if min(xs)<-1e-3 or min(ys)<-1e-3 or max(xs)>W+1e-3 or max(ys)>H+1e-3: res("cut",p["name"],"FAIL",f"{p['name']} sticks out of sheet {G['name']} ({W:g}x{H:g})"); okc=False
    # nested count vs BOM, per material+thickness
    by={}
    for G in N["groups"]:
        for p in G["parts"]: by.setdefault((G["material"],float(G["thickness"])),set()).add(base_(p["name"]))
    fl={}
    for f_ in d["flats"]: fl.setdefault((f_.get("material","steel"),float(f_.get("thickness",0))),set()).add(f_["name"])
    for k,names in fl.items():
        got=by.get(k,set()); bom=sum(r["qty"] for r in d["cutlist"] if set(r.get("names",[]))&names)
        if got!=names or len(got)!=bom: res("cut",f"{k[0]} {k[1]:g}","FAIL",f"nested {len(got)} parts but the BOM has {bom} of {k[0]} {k[1]:g}"+(f" (missing: {', '.join(sorted(names-got))})" if names-got else "")+(f" (extra: {', '.join(sorted(got-names))})" if got-names else "")); okc=False
    for dx in glob.glob(f"{F}/nest_{cls}/*.dxf")+glob.glob(f"{F}/dxf_{cls}/*.dxf"):
        try: doc=ezdxf.readfile(dx)
        except Exception as ex: res("cut",os.path.basename(dx),"FAIL",f"unreadable DXF: {ex}"); okc=False; continue
        for e in doc.modelspace():
            t=e.dxftype()
            if t=="LWPOLYLINE" and e.dxf.layer in("CUT","POCKET","SHEET"):
                pp=[tuple(q[:2]) for q in e.get_points()]
                if not e.closed and math.dist(pp[0],pp[-1])>1e-4: res("cut",os.path.basename(dx),"FAIL",f"open contour on layer {e.dxf.layer}: the cutter can't follow it"); okc=False; break
            elif t in("LINE","ARC","SPLINE","POLYLINE") and e.dxf.layer=="CUT": res("cut",os.path.basename(dx),"FAIL",f"loose {t} on CUT layer (contour not closed)"); okc=False; break
    for gj in glob.glob(f"{F}/gcode_{cls}/*.json"):
        g=json.load(open(gj)); mm=M.get(g["machine"],{}); bn=os.path.basename(gj)
        exp=mm.get("kerf",0)/2 if g.get("type",mm.get("type"))!="router" else mm.get("tool_dia",0)/2
        if g.get("comp") is None or g["comp"]<=0 or abs(g["comp"]-exp)>1e-6: res("cut",bn,"FAIL",f"kerf/tool offset not applied correctly (G-code offset {g.get('comp')}, machine needs {exp:g})"); okc=False; continue
        W,H=g.get("sheet_size",[1e9,1e9]); W,H=float(W),float(H); nc=gj[:-5]+".nc"; xs=[];ys=[]
        for l in open(nc):
            if l[:2] in("G0","G1","G2","G3"):
                mx=re.search(r"X(-?[\d.]+)",l); my=re.search(r"Y(-?[\d.]+)",l)
                if mx: xs.append(float(mx[1]))
                if my: ys.append(float(my[1]))
        bed=mm.get("bed",[1e9,1e9])
        xs=[x for x in xs if abs(x)>1e-9 or True]
        al=float(mm.get("lead_in",mm.get("tool_dia",0.25)))+float(g["comp"])+0.05; bx,by=float(bed[0]),float(bed[1])
        if xs and (min(xs)<-al or min(ys)<-al or max(xs)>W+al or max(ys)>H+al or max(xs)>bx+0.01 or max(ys)>by+0.01): res("cut",bn,"FAIL",f"toolpath leaves the sheet/bed: X {min(xs):.2f}..{max(xs):.2f}, Y {min(ys):.2f}..{max(ys):.2f} on {W:g}x{H:g}"); okc=False
    if okc: res("cut",cls,"PASS","closed contours, offset applied, all inside the sheet, nested count = BOM")
# ---- BOM / shopping
cl=d["cutlist"]; okb=True; seen={}
for r in cl:
    for nm in r.get("names",[]): seen[nm]=seen.get(nm,0)+1
    if r.get("mark")!="HW" and r["qty"]!=len(r.get("names",[])): res("bom",r["part"],"FAIL",f"BOM says {r['qty']} x {r['part']} but the model has {len(r.get('names',[]))}"); okb=False
miss=[x for x in model if x not in seen]; dup=[k for k,v in seen.items() if v>1]; orph=[k for k in seen if k not in model]
if miss: res("bom","cutlist","FAIL",f"model parts missing from the BOM: {', '.join(miss)}"); okb=False
if dup: res("bom","cutlist","FAIL",f"parts listed more than once: {', '.join(dup)}"); okb=False
if orph: res("bom","cutlist","FAIL",f"BOM rows for parts that aren't in the model: {', '.join(orph)}"); okb=False
rows=list(csv.DictReader(open(f"{F}/bom.csv"))); key=lambda r:(str(r["mark"]),str(r["part"]),str(r["material"]),str(r["qty"]))
A_={key(r) for r in rows}; B_={key(r) for r in cl}
if A_-B_: res("bom","bom.csv","FAIL",f"orphan row(s) in bom.csv not in the model: {'; '.join(' '.join(x) for x in sorted(A_-B_))}"); okb=False
if B_-A_: res("bom","bom.csv","FAIL",f"bom.csv is missing: {'; '.join(' '.join(x) for x in sorted(B_-A_))}"); okb=False
sl=f"{F}/shopping_list.csv"
if not os.path.exists(sl): res("bom","shopping_list.csv","FAIL","no shopping list"); okb=False
else:
    S_={(r["item"],str(r["qty"])) for r in csv.DictReader(open(sl))}
    for r in cl:
        if r.get("mark")=="HW" or r.get("stock")=="buy":
            if (r["material"],str(r["qty"])) not in S_: res("bom","shopping_list.csv","FAIL",f"BUY item missing from the shopping list: {r['qty']} x {r['material']}"); okb=False
if okb: res("bom","bom.csv/shopping_list.csv","PASS",f"{len(model)} model parts each once with the right qty; buy items + hardware on the shopping list")
# ---- cost
Q=json.load(open(f"{F}/quote.json")); okq=True
srcs=Q.get("sources")
if not srcs: res("cost","quote.json","FAIL","quote has no line sources"); okq=False
else:
    for s_ in srcs:
        if not re.match(r"(prices\.json|prices_default\.json|PrusaSlicer|slicer|machines\.json)",s_["source"]): res("cost",s_["line"],"FAIL",f"cost not from prices.json/slicer/nest: {s_['source']}"); okq=False
    tot=sum(float(s_["usd"] or 0) for s_ in srcs if s_["line"]!="labor")
    if abs(tot-Q["material_est"])>max(0.05,0.01*tot): res("cost","quote.json","FAIL",f"material total ${Q['material_est']} doesn't equal the sum of its priced lines ${tot:.2f}"); okq=False
if okq: res("cost","quote.json","PASS",f"{len(srcs)} lines, every one from prices.json / slicer / nest")
# ---- hand plan
hp=f"{F}/hand_tool_plan.txt"
if os.path.exists(hp):
    okh=True; FL={f_["name"]:f_ for f_ in d["flats"]}
    for l in open(hp):
        mt=re.match(r"\s+- (\S+)\s+([\d.]+)\" \(~[^)]*\) x ([\d.]+)\"",l)
        if mt:
            nm,w,h=mt[1],float(mt[2]),float(mt[3])
            if nm not in model: res("hand",nm,"FAIL",f"hand plan cuts '{nm}', which is not a part in the model"); okh=False; continue
            f_=FL.get(nm)
            if f_ and sorted([w,h])!=sorted([round(f_.get("w",0),3),round(f_.get("h",0),3)]) and abs(sorted([w,h])[1]-sorted([f_.get("w",0),f_.get("h",0)])[1])>0.002:
                res("hand",nm,"FAIL",f"hand plan says {nm} is {w}x{h} but the model/drawing has {f_.get('w'):g}x{f_.get('h'):g}"); okh=False
        mt2=re.match(r"\s+- (\S+): [\d.]+\" wide",l)
        if mt2 and mt2[1] not in model: res("hand",mt2[1],"FAIL",f"hand plan step refers to '{mt2[1]}', not a part in the model"); okh=False
    if okh: res("hand","hand_tool_plan.txt","PASS","every step names a real part; sizes match the model")
if os.path.exists(f"{V}/steps.json"):
    bad=[s_[0] for s_ in json.load(open(f"{V}/steps.json")) if s_[0] not in model and s_[0] not in [p.get("group") for p in spec.get("parts",[])]]
    if bad: res("hand","build steps","FAIL",f"build steps refer to parts not in the model: {', '.join(bad)}")
    else: res("hand","build steps","PASS","every build step references an existing part")
# ---- print parts (gate + real slice)
pp_all=d.get("print_parts",[]); SL={}
if pp_all:
    W_=f"{V}/.ship_work"; shutil.rmtree(W_,ignore_errors=True); os.makedirs(f"{W_}/stl")
    pk=d["params"].get("printer",PR["active"]); pk=pk if pk in PR["printers"] else PR["active"]; prn=PR["printers"][pk]; newpp=[]
    for pp in pp_all:
        m=trimesh.load(os.path.join(V,pp["stl"]),force="mesh")
        if U=="in": m.apply_scale(25.4)
        sc_=25.4 if U=="in" else 1.0; m,T4=rot(m,pp.get("orient",[0,0,0]),True); fil=pp.get("material","PLA")
        bands=[(trimesh.transformations.transform_points([[b["c"][0]*sc_,b["c"][1]*sc_,b["z0"]*sc_]],T4)[0],trimesh.transformations.transform_points([[b["c"][0]*sc_,b["c"][1]*sc_,b["z1"]*sc_]],T4)[0],b["r"],b["depth"]) for b in pp.get("thread_bands",[])]; fil=fil if fil in PR["filaments"] else "PLA"
        g=gate_print(m,pp["name"],fil,pp.get("assembly"),len(pp["bodies"]) if isinstance(pp.get("bodies"),list) else pp.get("bodies"),pp.get("clearance"),prn,bands)
        if g is None: continue
        g.export(f"{W_}/stl/{pp['name']}.stl"); newpp.append(dict(pp,stl=f"stl/{pp['name']}.stl",orient=[0,0,0]))
    if not any(r["status"]=="FAIL" and r["area"]=="print" for r in R):
        json.dump(dict(params=dict(d["params"],units="mm",printer=pk),print_parts=newpp),open(f"{W_}/parts.json","w"))
        r_=subprocess.run([sys.executable,f"{B}/print3d.py",W_,f"{W_}/print"],capture_output=True,text=True)
        pj=f"{W_}/print/print.json"
        if r_.returncode or not os.path.exists(pj): res("print","slicer","FAIL","PrusaSlicer run failed: "+(r_.stderr or r_.stdout)[-300:])
        else:
            PJ=json.load(open(pj)); errs=[p.get("slicer_error") for p in PJ.get("plates",[])+[pc for q in PJ["parts"] for pc in q["pieces"]] if p.get("slicer_error")]
            if errs: res("print","slicer","FAIL","PrusaSlicer could not slice: "+errs[0][:200])
            else:
                for q in PJ["parts"]:
                    if not q["fits_bed"]: res("print",q["name"],"PASS",f"bigger than the {prn['label']} bed: split into {len(q['pieces'])} pieces with alignment pins")
                    else: res("print",q["name"],"PASS",f"fits the {prn['label']} bed")
                SL=dict(printer=prn["label"],plates=[{k:p.get(k) for k in ("plate","filament","parts","time","grams","cost","gcode")} for p in PJ.get("plates",[])],
                        parts=[{k:pc.get(k) for k in ("name","time","grams","cost","plate")} for q in PJ["parts"] for pc in q["pieces"]])
                res("print","slicer","PASS",f"PrusaSlicer: {len(SL['plates'])} plate(s), "+", ".join(f"plate {p['plate']} {p['time']} {p['grams']} g ${p['cost']}" for p in SL["plates"]))
# ---------------------------------------------------------------- verdict + delivery
fails=[r for r in R if r["status"]=="FAIL"]
if fails:
    json.dump(dict(project=os.path.basename(P),version=n,shipped=False,checks=R),open(f"{V}/ship_failed.json","w"),indent=1)
    print(f"\n[FAIL] SHIP BLOCKED: {len(fails)} problem(s). Nothing may be sent to the user. Fix in the spec, rerun design.sh --final (it reruns this gate).")
    for r in fails: print(f"  - {r['area']} {r['target']}: {r['why']}")
    sys.exit(1)
if os.path.exists(f"{V}/ship_failed.json"): os.remove(f"{V}/ship_failed.json")
os.makedirs(SH); SEND=[]
def put(src,dst,where,check):
    os.makedirs(os.path.dirname(f"{SH}/{dst}"),exist_ok=True); shutil.copy2(src,f"{SH}/{dst}"); SEND.append((dst,where,check))
pa=[r for r in R if r["area"]=="print" and r["status"]!="WARN"]
if SL:
    WP=f"{V}/.ship_work/print"
    for f in sorted(glob.glob(f"{WP}/plate_*.gcode")): put(f,f"PRINTER/{os.path.basename(f)}","G-code for your printer: share to your printer app, or copy to its SD card / USB stick","print")
    for f in sorted(glob.glob(f"{WP}/plate_*.3mf")): put(f,f"PRINTER/{os.path.basename(f)}","open in PrusaSlicer / Bambu Studio / Orca (settings included), check, slice and send","print")
    for f in sorted(glob.glob(f"{WP}/plate_*.png")): put(f,f"PRINTER/{os.path.basename(f)}","picture of what goes on that print bed","print")
    for f in sorted(glob.glob(f"{WP}/*.stl")): put(f,f"PRINTER/parts_stl/{os.path.basename(f)}","single part for any slicer (Cura etc.)","print")
    put(f"{WP}/print_report.txt","PRINTER/print_report.txt","print times, filament, checks","print")
LAB={"LASER":"open in LightBurn (red = cut, black = engrave, blue = score)","PLASMA":"load the DXF in SheetCAM/Fusion, or the .nc straight into the plasma controller","ROUTER":"load the DXF in SheetCAM/Fusion/VCarve, or the .nc into the router controller"}
for D_ in sorted(glob.glob(f"{F}/FOR_*")):
    mk=os.path.basename(D_)[4:].split("_")[0].upper()
    if mk in("3D",): continue
    for f in sorted(glob.glob(f"{D_}/**/*",recursive=True)):
        if not os.path.isfile(f): continue
        ext=f.rsplit(".",1)[-1].lower(); rel=os.path.relpath(f,D_)
        if mk=="HAND": put(f,f"HAND_TOOLS/{rel}",{"pdf":"build plan: print it at 100% (1:1 templates inside)","csv":"cut list","txt":"step-by-step plan (plain text)"}.get(ext,"hand-tool file"),"hand")
        elif ext in("dxf","svg","nc","png"): put(f,f"{mk}/{rel}",(LAB.get(mk,"cut file") if ext!="png" else "preview of the toolpath/nest"),"cut")
for f,where,c in (("drawings.pdf","DRAWINGS: print on normal paper at 100% (Actual size)","drawing"),("drawing.png","drawing to look at on a phone","drawing"),
                  ("bom_quote.pdf","bill of materials + price estimate (print or read)","bom"),("bom.csv","cut/parts list (spreadsheet)","bom"),
                  ("shopping_list.csv","shopping list: take it to the store","bom"),("build_steps.pdf","illustrated build steps","hand"),("HOW_TO_USE.txt","which file goes into which program","files"),
                  ("quote.json","price estimate data","cost"),("assumptions.txt","values Sketch guessed: confirm them","files")):
    if os.path.exists(f"{F}/{f}"): put(f"{F}/{f}",("DRAWINGS/" if c=="drawing" else "")+f,where,c)
CK={k:[f"{r['area']} {r['target']}: {r['status']}" for r in R if r["area"] in (k,"files")] for k in ("print","cut","hand","drawing","bom","cost","files")}
files=[dict(path=dst,sha256=sha(f"{SH}/{dst}"),bytes=os.path.getsize(f"{SH}/{dst}"),where=where,checks=CK.get(c,[])) for dst,where,c in SEND]
Z=f"{os.path.basename(P)}_v{n}_all.zip"
man=dict(project=os.path.basename(P),version=n,shipped=True,time=time.strftime("%Y-%m-%d %H:%M %Z"),units=U,min_print_feature_mm=MIN,
         files=files,slicer=SL,cost_sources=Q.get("sources"),checks=R,warnings=[r for r in R if r["status"]=="WARN"],bundle=Z)
json.dump(man,open(f"{SH}/ship_manifest.json","w"),indent=1,default=float)
L=["SEND LIST - send each file on its own (one message per file, in this order), the zip LAST as a backup.",""]
for e in files: L.append(f"{e['path']}  ->  {e['where']}")
L+=["ship_manifest.json  ->  proof these files passed Sketch's checks (optional)",f"{Z}  ->  everything in one zip (send last, backup for a computer)"]
open(f"{SH}/send_list.txt","w").write("\n".join(L)+"\n")
with zipfile.ZipFile(f"{SH}/{Z}","w",zipfile.ZIP_DEFLATED) as z:
    for e in files: z.write(f"{SH}/{e['path']}",e["path"])
    z.write(f"{SH}/ship_manifest.json","ship_manifest.json"); z.write(f"{SH}/send_list.txt","send_list.txt")
with open(REG,"a") as fh:
    for p_ in [e["path"] for e in files]+["ship_manifest.json","send_list.txt",Z]:
        fh.write(json.dumps(dict(sha256=sha(f"{SH}/{p_}"),path=p_,project=P,version=n,manifest=f"{SH}/ship_manifest.json"))+"\n")
shutil.rmtree(f"{V}/.ship_work",ignore_errors=True)
w=len(man["warnings"])
print(f"\n[SHIPPED] {len(files)} files passed -> {SH}/  ({w} warning(s) to mention). Send them one by one with {SH}/send_list.txt, the zip last.")

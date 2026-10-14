"""Parametric parts kit (CadQuery/OpenCascade). Every builder returns a Part: exact solid in its LOCAL frame + metadata.
Local frame convention: length along +X, width along +Y, thickness/height along +Z, origin at the min corner (pipes/tubes:
axis along +X starting at origin, centered on Y/Z). Placement in the spec: rot [rx,ry,rz] degrees (applied X then Y then Z
about the local origin) then at [x,y,z].
Fab kinds: plate (metal sheet/plate), panel (plywood/MDF/acrylic sheet), board (dimensional lumber), tube_sq, pipe, angle,
flatbar, gusset.  Print kinds (mm): pbox (rounded box), pcyl, shell (enclosure), bracket, clip, knob, hinge_leaf, boss, snap_hook, pfin (rounded tongue fin), phook (rounded J-hook). Helpers: soften(s,r) fillet-with-fallback, fin(), rounded_profile(). Small printed parts: ALWAYS soften edges (0.8-1.5 mm) - boxes read as blocks.
Features on any part (local coords, on the top face unless 'face'): holes [{x,y,d,(depth)}], slots [{x1,y1,x2,y2,w}],
cutouts [{x,y,w,h,r}], text [{x,y,s,txt,depth,(emboss),(face:auto|top -> auto moves text to the face the hero camera sees (+Y) and mirrors as needed)}], fillet r (vertical edges)."""
import math, json, os
import cadquery as cq
import numpy as np
B=os.path.dirname(os.path.abspath(__file__))
STOCK=json.load(open(os.path.join(B,"stock.json")))
def _box(L,W,T): return cq.Workplane("XY").box(L,W,T,centered=False)
def plate(L,W,t,material="steel",**k):   return _box(L,W,t),dict(stock="plate",section=f'{t}" plate' if t<2 else f"{t} plate",flat=True,t=t)
def panel(L,W,t,material="plywood",**k): return _box(L,W,t),dict(stock="sheet_good",section=f'{t} {material}',flat=True,t=t)
def flatbar(L,w,t,**k): return _box(L,w,t),dict(stock="bar",section=f'{w}x{t} flat bar',length=L)
def board(L,size="2x4",on_edge=False,**k):
    t,w=STOCK["lumber_actual"][size]; s=_box(L,t,w) if on_edge else _box(L,w,t)
    return s,dict(stock="lumber",section=size,length=L)
def tube_sq(L,size="2x2x11ga",**k):
    a,wall=STOCK["sq_tube"][size]
    s=cq.Workplane("YZ").rect(a,a).rect(a-2*wall,a-2*wall).extrude(L)
    return s,dict(stock="tube",section=f"{size} sq tube",length=L,od=a)
def pipe(L,nps="1-1/2",sched="pipe_sch40",**k):
    od,wall=STOCK[sched][nps]
    s=cq.Workplane("YZ").circle(od/2).circle(od/2-wall).extrude(L)
    return s,dict(stock="tube",section=f'{nps}" {sched[-5:]} pipe',length=L,od=od)
def angle(L,size="1.5x1.5x3/16",**k):
    a,t=STOCK["angle"][size]
    s=cq.Workplane("YZ").polyline([(0,0),(a,0),(a,t),(t,t),(t,a),(0,a)]).close().extrude(L)
    return s,dict(stock="angle",section=f"{size} angle",length=L,leg=a,t=t)
def gusset(a,b,t,**k):
    s=cq.Workplane("XY").polyline([(0,0),(a,0),(0,b)]).close().extrude(t); return s,dict(stock="plate",section=f'{t}" plate gusset',flat=True,t=t)
# ---------- 3D print kit (mm) ----------
def pbox(L,W,H,r=0,**k):
    s=cq.Workplane("XY").box(L,W,H,centered=False)
    if r: s=s.edges("|Z").fillet(min(r,min(L,W)/2-0.01))
    return s,dict(stock="print")
def pcyl(d,h,**k): return cq.Workplane("XY").circle(d/2).extrude(h).translate((d/2,d/2,0)),dict(stock="print")
def shell(L,W,H,wall=2.0,r=3,lid_lip=0,**k):
    try: s=cq.Workplane("XY").box(L,W,H,centered=False).edges("|Z").fillet(r).faces(">Z").shell(-wall); s.val().Volume()
    except Exception:   # OCC shell fails when r<=wall: cut an inner box instead (same result)
        s=cq.Workplane("XY").box(L,W,H,centered=False)
        if r: s=s.edges("|Z").fillet(r)
        ib=cq.Workplane("XY").box(L-2*wall,W-2*wall,H,centered=False)
        if r-wall>0.2: ib=ib.edges("|Z").fillet(r-wall)
        s=s.cut(ib.translate((wall,wall,wall)))
    if lid_lip: s=s.union(cq.Workplane("XY").box(L-2*wall-0.4,W-2*wall-0.4,lid_lip,centered=False).translate((wall+0.2,wall+0.2,H)).cut(
        cq.Workplane("XY").box(L-4*wall,W-4*wall,lid_lip,centered=False).translate((2*wall,2*wall,H))))
    return s,dict(stock="print")
def bracket(L,W,H,t=4,fillet=6,**k):
    s=cq.Workplane("XZ").polyline([(0,0),(L,0),(L,t),(t,t),(t,H),(0,H)]).close().extrude(-W)
    try: s=s.edges("|Y").edges(cq.selectors.NearestToPointSelector((t,W/2,t))).fillet(fillet)
    except Exception: pass
    return s,dict(stock="print")
def clip(d,width=10,t=2.5,gap_deg=100,**k):
    r=d/2; s=cq.Workplane("XY").circle(r+t).circle(r).extrude(width)
    g=cq.Workplane("XY").polyline([(0,0),((r+t)*2*math.cos(math.radians(90-gap_deg/2)),(r+t)*2*math.sin(math.radians(90-gap_deg/2))),
        (-(r+t)*2*math.cos(math.radians(90-gap_deg/2)),(r+t)*2*math.sin(math.radians(90-gap_deg/2)))]).close().extrude(width)
    return s.cut(g).translate((r+t,r+t,0)),dict(stock="print")
def knob(d=30,h=15,shaft_d=6,flat=1.0,grip=12,**k):
    s=cq.Workplane("XY").polygon(grip*2,d).extrude(h).edges(">Z").fillet(2)
    hole=cq.Workplane("XY").circle(shaft_d/2+0.15).extrude(h-3).cut(cq.Workplane("XY").box(shaft_d,shaft_d,h,centered=(True,True,False)).translate((0,shaft_d-flat,0)))
    return s.cut(hole).translate((d/2,d/2,0)),dict(stock="print")
def boss(insert="M3",h=6,**k):   # heat-set insert boss: hole per common insert sizes
    hd,od={"M2":(3.2,6),"M2.5":(3.6,6.5),"M3":(4.0,7),"M4":(5.6,9),"M5":(6.4,10)}[insert]
    return cq.Workplane("XY").circle(od/2).circle(hd/2).extrude(h).translate((od/2,od/2,0)),dict(stock="print",insert=insert)
def snap_hook(L=12,t=1.6,w=6,overhang=1.0,**k):
    s=cq.Workplane("XZ").polyline([(0,0),(t,0),(t,L),(t+overhang,L),(t,L+overhang*1.6),(0,L+overhang*1.6)]).close().extrude(-w)
    return s,dict(stock="print")
def hinge_leaf(L=30,W=20,t=3,knuckle_d=7,pin_d=3.2,n=3,which=0,**k):
    s=cq.Workplane("XY").box(L,W,t,centered=False); seg=L/n
    for i in range(n):
        if i%2==which:
            kn=cq.Workplane("YZ").circle(knuckle_d/2).circle(pin_d/2).extrude(seg-0.4).translate((i*seg+0.2,W+knuckle_d/2-0.5,knuckle_d/2))
            s=s.union(kn)
    return s,dict(stock="print")
KINDS=dict(plate=plate,panel=panel,flatbar=flatbar,board=board,tube_sq=tube_sq,pipe=pipe,angle=angle,gusset=gusset,
           pbox=pbox,pcyl=pcyl,shell=shell,bracket=bracket,clip=clip,knob=knob,boss=boss,snap_hook=snap_hook,hinge_leaf=hinge_leaf)
def features(s,f,top):
    """apply hole/slot/cutout/text features in local coords on the top face (z=top)"""
    for h in f.get("holes",[]):
        if "depth" in h: cyl=cq.Workplane("XY").circle(h["d"]/2).extrude(h["depth"]+1).translate((h["x"],h["y"],top-h["depth"]))
        else: cyl=cq.Workplane("XY").circle(h["d"]/2).extrude(top+20).translate((h["x"],h["y"],-10))
        s=s.cut(cyl)
        if h.get("csk"):   # countersink for flat-head screws
            s=s.cut(cq.Workplane("XY").circle(h["csk"]/2).workplane(offset=-h["csk"]/2).circle(0.01).loft().translate((h["x"],h["y"],top)))
    for sl in f.get("slots",[]):
        L=math.hypot(sl["x2"]-sl["x1"],sl["y2"]-sl["y1"]); a=math.degrees(math.atan2(sl["y2"]-sl["y1"],sl["x2"]-sl["x1"]))
        cut=cq.Workplane("XY").slot2D(L+sl["w"],sl["w"],0).extrude(top*3+10).rotate((0,0,0),(0,0,1),a).translate(((sl["x1"]+sl["x2"])/2,(sl["y1"]+sl["y2"])/2,-top-5))
        s=s.cut(cut)
    for c in f.get("cutouts",[]):
        cut=cq.Workplane("XY").rect(c["w"],c["h"]).extrude(top*3+10).translate((c["x"]+c["w"]/2,c["y"]+c["h"]/2,-top-5))
        if c.get("r"): cut=cut.edges("|Z").fillet(c["r"])
        s=s.cut(cut)
    for t in f.get("text",[]):
        dp=t.get("depth",0.6); txt=cq.Workplane("XY").text(t["txt"],t["s"],dp,halign="center",valign="center")
        if t.get("bottom"):   # text on the BOTTOM face (z=0), mirrored so it reads correctly when that face is looked at
            txt=txt.mirror("YZ").translate((t["x"],t["y"],-dp if t.get("emboss") else 0))
        else: txt=txt.translate((t["x"],t["y"],top-(0 if t.get("emboss") else dp)))
        s=s.union(txt) if t.get("emboss") else s.cut(txt)
    return s
def place(s,rot=(0,0,0),at=(0,0,0)):
    for ax,ang in zip(((1,0,0),(0,1,0),(0,0,1)),rot):
        if ang: s=s.rotate((0,0,0),ax,ang)
    return s.translate(tuple(at))

# ---------- imported geometry ----------
def _path(f): return f if os.path.isabs(f) else os.path.join(os.environ.get("SPEC_DIR","."),f)
def mesh_to_solid(path,max_faces=15000,scale=(1,1,1)):
    import trimesh
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace,BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeSolid
    from OCP.gp import gp_Pnt
    from OCP.TopoDS import TopoDS
    m=trimesh.load(path,force="mesh"); m.merge_vertices(); m.apply_translation(-m.bounds[0]); m.apply_scale(scale)
    if len(m.faces)>max_faces:
        try: m=m.simplify_quadric_decimation(face_count=max_faces)
        except Exception: pass
    if not m.is_watertight:   # close holes / fix self-intersections so OCCT gets a real solid
        try:
            import pymeshfix
            v,f_=pymeshfix.clean_from_arrays(np.ascontiguousarray(m.vertices,dtype=np.float64),np.ascontiguousarray(m.faces,dtype=np.int32),joincomp=True,remove_smallest_components=False); r_=trimesh.Trimesh(v,f_)
            if np.allclose(r_.extents,m.extents,rtol=0.02): m=r_   # only accept a repair that keeps the whole part
        except Exception: pass
    sew=BRepBuilderAPI_Sewing(1e-6)
    for f in m.faces:
        try:
            a,b,c=(gp_Pnt(*map(float,m.vertices[i])) for i in f); pg=BRepBuilderAPI_MakePolygon(a,b,c,True)
            fc=BRepBuilderAPI_MakeFace(pg.Wire())
            if fc.IsDone(): sew.Add(fc.Face())
        except Exception: pass   # degenerate triangle
    sew.Perform(); sh=sew.SewedShape()
    try: sol=cq.Solid(BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(sh)).Solid())
    except Exception: sol=cq.Shape.cast(sh)
    return sol
def load_cad(path):
    ext=path.lower().rsplit(".",1)[-1]
    if ext in("step","stp"): return cq.importers.importStep(path).val() if len(cq.importers.importStep(path).vals())==1 else cq.Compound.makeCompound(cq.importers.importStep(path).vals())
    if ext in("iges","igs"):
        from OCP.IGESControl import IGESControl_Reader
        r=IGESControl_Reader(); r.ReadFile(path); r.TransferRoots(); return cq.Shape.cast(r.OneShape())
    if ext=="brep": return cq.Shape.importBrep(path)
    return mesh_to_solid(path)
def imported(file,scale=1.0,sx=None,sy=None,sz=None,stock="print",material="PLA",section=None,**k):
    """an imported STEP/IGES/BREP/STL/3MF/OBJ body, scaled (uniform or per-axis). Its origin is moved to the bbox min corner."""
    f=_path(file); S=(sx or scale,sy or scale,sz or scale)
    if f.lower().rsplit(".",1)[-1] not in("step","stp","iges","igs","brep"):
        sh=mesh_to_solid(f,scale=S)   # meshes: scale the triangles, then sew
    else:
        sh=load_cad(f); bb=sh.BoundingBox(); sh=sh.translate(cq.Vector(-bb.xmin,-bb.ymin,-bb.zmin))
        if max(S)-min(S)>1e-9:
            from OCP.gp import gp_GTrsf,gp_Mat
            from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
            g=gp_GTrsf(); g.SetVectorialPart(gp_Mat(S[0],0,0,0,S[1],0,0,0,S[2])); sh=cq.Shape.cast(BRepBuilderAPI_GTransform(sh.wrapped,g,True).Shape())
        elif abs(S[0]-1)>1e-9: sh=sh.scale(S[0])
    meta=dict(stock=stock,section=section or f"imported {os.path.basename(file)}")
    return cq.Workplane("XY").add(sh),meta
def profile(outer,t,holes=(),inner=(),material="steel",sx=1.0,sy=1.0,**k):
    """flat part from a 2D outline (from DXF/SVG/drawing): outer [[x,y]..], holes [[x,y,d]..], inner cutouts [[[x,y]..]..]"""
    S=lambda pts:[(x*sx,y*sy) for x,y in pts]
    s=cq.Workplane("XY").polyline(S(outer)).close().extrude(t)
    for x,y,d in holes: s=s.cut(cq.Workplane("XY").center(x*sx,y*sy).circle(d/2).extrude(t))   # hole sizes don't scale
    for ip in inner: s=s.cut(cq.Workplane("XY").polyline(S(ip)).close().extrude(t))
    wood=material in("plywood","baltic_birch","mdf","acrylic")
    return s,dict(stock="sheet_good" if wood else "plate",section=f'{t} {material}' if wood else f'{t}" plate',flat=True,t=t,material=material)
KINDS.update(imported=imported,profile=profile)

# ---------- soft-edge helpers (printed parts read as products, not blocks) ----------
def soften(s,r=1.0,sel=None,chamfer_ok=True):
    """fillet edges (all, or a CadQuery selector like '|X') with fallback radii; then chamfer; else unchanged. Never raises."""
    for rr in (r,r*0.6,r*0.35):
        try:
            e=s.edges(sel) if sel else s.edges(); o=e.fillet(rr)
            if o.val().isValid(): return o
        except Exception: pass
    if chamfer_ok:
        try:
            e=s.edges(sel) if sel else s.edges(); o=e.chamfer(r*0.5)
            if o.val().isValid(): return o
        except Exception: pass
    return s
def rounded_profile(pts,r):
    """2D polyline in the YZ plane with every corner rounded (r) -> Workplane wire; extrude along X."""
    w=cq.Workplane("YZ").polyline(pts).close()
    try:
        f=cq.Workplane("YZ").add(cq.Face.makeFromWires(w.val() if isinstance(w.val(),cq.Wire) else w.wire().val()).fillet2D(r,cq.Face.makeFromWires(w.wire().val()).Vertices()))
        return f
    except Exception: return w
def fin(t,depth,height,tip_r=None,root_r=3.0,taper=0.75,edge_r=1.0):
    """tongue-shaped printed fin: rounded tip, tapered, root fillet-ready; thickness t along X (centered), depth along +Y, height along +Z.
    Use instead of a box() for clips, hooks and fins."""
    tip_r=tip_r or min(depth*taper,height)/2.2
    pts=[(0,0),(depth,0),(depth,height*0.55),(depth*(1+taper)/2,height),(0,height)]
    prof=rounded_profile(pts,min(tip_r,depth*0.3))
    try: s=cq.Workplane("YZ").add(prof.val()).toPending().extrude(t).translate((-t/2,0,0)) if isinstance(prof.val(),cq.Face) else prof.extrude(t).translate((-t/2,0,0))
    except Exception: s=cq.Workplane("XY").box(t,depth,height,centered=(True,False,False))
    return soften(s,min(edge_r,t*0.3),"|Y") if edge_r else s
def pfin(t=6,depth=40,height=60,**k): return fin(t,depth,height),dict(stock="print")
def phook(d=20,t=6,w=8,arm=25,**k):
    """rounded J-hook: arm along +Y then a half-ring of inner diameter d; all edges softened."""
    r=d/2; a=cq.Workplane("XY").box(w,arm,t,centered=(True,False,False))
    ring=cq.Workplane("YZ").circle(r+t).circle(r).extrude(w).translate((-w/2,arm,r+t)).cut(cq.Workplane("XY").box(w+2,r+t+1,2*(r+t)+2,centered=(True,False,False)).translate((0,arm-r-t-1,0)))
    return soften(a.union(ring),min(1.2,t*0.25)),dict(stock="print")
KINDS.update(pfin=pfin,phook=phook)

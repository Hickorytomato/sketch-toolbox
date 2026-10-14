"""Parametric parts kit (CadQuery/OpenCascade). Every builder returns a Part: exact solid in its LOCAL frame + metadata.
Local frame convention: length along +X, width along +Y, thickness/height along +Z, origin at the min corner (pipes/tubes:
axis along +X starting at origin, centered on Y/Z). Placement in the spec: rot [rx,ry,rz] degrees (applied X then Y then Z
about the local origin) then at [x,y,z].
Fab kinds: plate (metal sheet/plate), panel (plywood/MDF/acrylic sheet), board (dimensional lumber), tube_sq, pipe, angle,
flatbar, gusset.  Print kinds (mm): round|cylinder|cone (revolved, shells, threads, hole patterns), prism, dovetail, path, arc_plate, ring, link, pbox (rounded box), pcyl, shell (enclosure), bracket, clip, knob, hinge_leaf, boss, snap_hook, pfin (rounded tongue fin), phook (rounded J-hook). Helpers: soften(s,r) fillet-with-fallback, fin(), rounded_profile(). Small printed parts: ALWAYS soften edges (0.8-1.5 mm) - boxes read as blocks.
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
def bent_plate(a,b,W,t,R=None,K=0.44,holes_a=(),holes_b=(),wb=None,relief_w=0,relief_d=0,material="steel",**k):
    """sheet-metal L (90° brake bend). Outside leg a along +X (on the bed, z 0..t), outside leg b up +Z (x 0..t), width W along +Y,
    inside radius R (default 1T). holes_a [{x,y,d}] x from the OUTSIDE corner; holes_b [{z,y,d}] z from the outside corner.
    wb < W: leg b only spans y 0..wb (partial bend) -> needs relief_w x relief_d (catalog #194). K-factor is an estimate."""
    R=t if R is None else R; wb=W if wb is None else wb
    s=_box(a,W,t).union(_box(t,wb,b))
    try: s=s.edges(cq.selectors.NearestToPointSelector((t,min(W,wb)/2,t))).fillet(R)
    except Exception: pass
    try: s=s.edges(cq.selectors.NearestToPointSelector((0,min(W,wb)/2,0))).fillet(R+t)
    except Exception: pass
    if wb<W and relief_w>0: s=s.cut(_box(max(relief_d,1e-3),relief_w,t*3).translate((0,wb,-t)))
    for h in holes_a: s=s.cut(cq.Workplane("XY").circle(h["d"]/2).extrude(3*t).translate((h["x"],h["y"],-t)))
    for h in holes_b: s=s.cut(cq.Workplane("YZ").circle(h["d"]/2).extrude(3*t).translate((-t,h["y"],h["z"])))
    Af,Bf=a-(R+t),b-(R+t); BA=math.pi/2*(R+K*t); L=Af+Bf+BA
    return s,dict(stock="plate",section=f'{t}" plate (bent)',t=t,bent=dict(a=a,b=b,W=W,wb=wb,t=t,R=R,K=K,Af=Af,Bf=Bf,BA=BA,L=L,holes_a=list(holes_a),holes_b=list(holes_b),relief_w=relief_w,relief_d=relief_d))
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
def _path(f):
    """absolute, or relative to the spec's folder, the project folder, or PROJECT/source/ (where custom_stl files live)"""
    if os.path.isabs(f): return f
    sd=os.environ.get("SPEC_DIR",".")
    for c in (os.path.join(sd,f),os.path.join(os.path.dirname(sd),f),os.path.join(os.path.dirname(sd),"source",f),os.path.join(sd,"source",f)):
        if os.path.exists(c): return c
    return os.path.join(sd,f)
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
def custom_stl(file,**k):
    """a one-off mesh the bot generated itself (relief, ornament, organic shape). Same as 'imported', but marked so ship.py
    always fuses it with its group and gates it like every other print part. Put it in the same 'group' as the body it decorates."""
    f=_path(file)
    try:   # generated meshes often touch/overlap themselves (petals meeting at a point): union their shells first so the CAD copy is a real solid
        import trimesh,tempfile,meshfuse
        r,e=meshfuse.fuse(trimesh.load(f,force="mesh"),os.path.basename(f))
        if r and len(r[0])>1:   # separate bodies (print-in-place, or a floating bit ship.py will reject): one solid each, kept in place
            sc=k.get("scale",1.0); S=(k.get("sx") or sc,k.get("sy") or sc,k.get("sz") or sc); lo=np.min([b.bounds[0] for b in r[0]],axis=0); sols=[]
            for b in r[0]:
                t=tempfile.NamedTemporaryFile(suffix=".stl",delete=False); b.export(t.name); so=mesh_to_solid(t.name,scale=S)
                off=(b.bounds[0]-lo)*np.array(S); sols.append(so.translate(cq.Vector(*map(float,off))))
            return cq.Workplane("XY").add(cq.Compound.makeCompound(sols)),dict(stock=k.get("stock","print"),section=f"custom {os.path.basename(file)} ({len(sols)} bodies)")
        if r and r[1]>1:
            t=tempfile.NamedTemporaryFile(suffix=".stl",delete=False); trimesh.util.concatenate(r[0]).export(t.name); f=t.name
    except Exception: pass
    s,meta=imported(f,**k); meta["section"]=f"custom {os.path.basename(file)}"; return s,meta
KINDS.update(imported=imported,profile=profile,custom_stl=custom_stl,bent_plate=bent_plate)

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

# ---------- round parts: revolved bodies, tapers, shells, screw threads, hole patterns (manifold3d, then sewn into a solid) ----------
# Local frame: axis along +Z, centered on X/Y (x=y=0), bottom at z=0.
#   cylinder(r,h) | cone(r1,r2,h) | round(segments=[{h,r1,r2},..] stacked bottom-up, or profile=[[r,z],..] outer outline)
#   wall=W -> hollow shell (inner surface follows the outer one, W in from it); open "top"|"bottom"|"both"|"none"; floor=bottom/top thickness
#   threads=[{side:"external"|"internal", z, r, pitch, turns, depth, clearance}]
#     external: helical ridge ON a neck of radius r (r = thread root), sticking out by depth. Starts at height z.
#     internal: the MATE of an external thread with the same r/pitch/depth: cuts a bore r+depth+clearance from z for the thread length
#               (turns*pitch + pitch) and adds a ridge whose crest sits at r+clearance. clearance default 0.4 mm (FDM).
#   holes=[{face:"top"|"bottom", d, n, pcd, center, depth, angle}] -> n holes on a circle of diameter pcd (+1 on the axis if center).
SEG=96
def _M(): import manifold3d; return manifold3d
def _outline(segments=None,profile=None,r=None,r1=None,r2=None,h=None):
    if profile: return [(float(a),float(b)) for a,b in profile]
    if not segments: segments=[dict(h=h,r1=r1 if r1 is not None else r,r2=r2 if r2 is not None else (r1 if r1 is not None else r))]
    pts=[]; z=0.0
    for s in segments:
        a=s.get("r1",s.get("r")); b=s.get("r2",a); pts.append((a,z)); z+=s["h"]; pts.append((b,z))
    return pts
def _r_at(pts,z):
    for (a,za),(b,zb) in zip(pts,pts[1:]):
        if za<=z<=zb and zb>za: return a+(b-a)*(z-za)/(zb-za)
    return pts[0][0] if z<pts[0][1] else pts[-1][0]
def _revolve(poly):
    mf=_M(); cs=mf.CrossSection([[(max(r,0.0),z) for r,z in poly]]); return mf.Manifold.revolve(cs,SEG)
def _ridge(r_base,r_tip,z0,pitch,turns,w_root,w_tip,n_per_turn=72):
    """helical trapezoid ridge: base at r_base (buried in the wall), crest at r_tip; ends fade out over ~45 deg so they print clean."""
    import trimesh; mf=_M()
    n=max(int(turns*n_per_turn),12); A=np.linspace(0,2*np.pi*turns,n); V=[]; F=[]; fl=0.8
    for a in A:
        f=max(min(1,a/fl,(A[-1]-a)/fl),0.05); rt=r_base+(r_tip-r_base)*f; wr=w_root*max(f,0.4); wt=w_tip*max(f,0.4)
        zc=z0+w_root/2+pitch*a/(2*np.pi)
        V+=[(rr*np.cos(a),rr*np.sin(a),zz) for rr,zz in ((r_base,zc-wr/2),(rt,zc-wt/2),(rt,zc+wt/2),(r_base,zc+wr/2))]
    for i in range(n-1):
        for k in range(4):
            a_,b_=i*4+k,i*4+(k+1)%4; F+=[[a_,a_+4,b_+4],[a_,b_+4,b_]]
    e=(n-1)*4; F+=[[0,1,2],[0,2,3],[e,e+2,e+1],[e,e+3,e+2]]
    t=trimesh.Trimesh(np.array(V),np.array(F),process=True)
    if t.volume<0: t.invert()
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def round_mesh(segments=None,profile=None,r=None,r1=None,r2=None,h=None,wall=0,open="top",floor=None,threads=(),holes=(),knurl=None,side_holes=()):
    mf=_M(); M=mf.Manifold; pts=_outline(segments,profile,r,r1,r2,h); H=pts[-1][1]
    body=_revolve([(0,pts[0][1])]+pts+[(0,H)])
    if wall:
        fl=wall if floor is None else floor
        zb=pts[0][1]-1 if open in("bottom","both") else pts[0][1]+fl; zt=H+1 if open in("top","both") else H-fl
        zs=sorted({zb,zt,*[z for _,z in pts if zb<z<zt]}); inner=[(max(_r_at(pts,min(max(z,0),H))-wall,0.3),z) for z in zs]
        body=body-_revolve([(0,zb)]+inner+[(0,zt)])
    for t in threads or ():
        P_=t["pitch"]; n=t.get("turns",2); d=t.get("depth",P_*0.6); c=t.get("clearance",0.4); z0=t.get("z",0); r0=t["r"]
        L=n*P_+P_; wr,wt=P_*0.6,P_*0.25
        if t.get("side","external")=="external": body=body+_ridge(r0-0.6,r0+d,z0,P_,n,wr,wt)
        else:
            rb=r0+d+c; body=body-M.cylinder(L+0.02,rb,rb,SEG).translate([0,0,z0-0.01])
            body=body+_ridge(rb+0.6,r0+c,z0+P_*0.25,P_,n,wr,wt)
            if z0<=0.01: body=body-M.cylinder(1.0,rb+0.8,rb,SEG).translate([0,0,-0.01])   # lead-in chamfer at the mouth
    for hp in holes or ():
        cut=[]; n=int(hp.get("n",0)); rr=hp.get("pcd",0)/2; dd=hp["d"]; dep=hp.get("depth",H+2); a0=math.radians(hp.get("angle",0))
        xy=[(rr*math.cos(a0+2*math.pi*i/n),rr*math.sin(a0+2*math.pi*i/n)) for i in range(n)]+([(0,0)] if hp.get("center") else [])
        z=(H-dep) if hp.get("face","top")=="top" else -1
        for x,y in xy: cut.append(M.cylinder(dep+1,dd/2,dd/2,24).translate([x,y,z]))
        if cut: body=body-mf.Manifold.batch_boolean(cut,mf.OpType.Add)
    if knurl:   # grip ribs: n round ribs of radius depth on the outer surface, z0..z1 (follow tapers)
        n=int(knurl.get("n",40)); kd=knurl.get("depth",0.8); z0=knurl.get("z0",pts[0][1]); z1=knurl.get("z1",H); ra,rb_=_r_at(pts,z0+kd),_r_at(pts,z1-kd)
        ball=lambda r_,z,a:M.sphere(kd,12).translate([r_*math.cos(a),r_*math.sin(a),z])
        body=body+M.batch_boolean([M.batch_hull([ball(ra,z0+kd,2*math.pi*i/n),ball(rb_,z1-kd,2*math.pi*i/n)]) for i in range(n)],mf.OpType.Add)
    for sh in side_holes or ():   # radial holes through the side wall: n around at height z; h>d makes a vertical slot window
        n=int(sh.get("n",1)); dd=sh["d"]; z=sh["z"]; hh=max(sh.get("h",dd),dd); R_=max(r for r,_ in pts)+2
        c=M.batch_hull([M.cylinder(R_,dd/2,dd/2,24).translate([0,0,0]).rotate([0,90,0]).translate([0,0,dz]) for dz in (-(hh-dd)/2,(hh-dd)/2)])
        for i in range(n): body=body-c.rotate([0,0,sh.get("angle",0)+360*i/n]).translate([0,0,z])
    return body
def _sew(man):
    import trimesh,tempfile
    k=man.to_mesh(); t=trimesh.Trimesh(k.vert_properties[:,:3],k.tri_verts)
    f=tempfile.NamedTemporaryFile(suffix=".stl",delete=False); t.export(f.name)
    try: return mesh_to_solid(f.name,max_faces=10**7)
    finally: os.unlink(f.name)
def round_part(material="PLA",**a):
    man=round_mesh(**{k:v for k,v in a.items() if k in("segments","profile","r","r1","r2","h","wall","open","floor","threads","holes","knurl","side_holes")})
    sol=_sew(man); b=man.bounding_box()   # mesh_to_solid moves the bbox min to the origin: put the axis back on x=y=0
    sol=sol.translate(cq.Vector(b[0],b[1],b[2]))
    return cq.Workplane("XY").add(sol),dict(stock="print",round=True)
def cylinder(r,h,**k): return round_part(r=r,h=h,**k)
def cone(r1,r2,h,**k): return round_part(r1=r1,r2=r2,h=h,**k)
KINDS.update(round=round_part,cylinder=cylinder,cone=cone)

# ---------- profiles, rails, strokes, curved plates, rings, chain links (CadQuery, exact solids) ----------
def _plane_pts(pts,plane): return cq.Workplane(plane).polyline([tuple(map(float,p)) for p in pts]).close()
def prism(pts,L,plane="XY",r=0,**k):
    """any 2D outline [[a,b],..] drawn on plane XY|XZ|YZ, extruded L along that plane's normal. r rounds every corner.
    Wedges, gussets, detent bumps, gates, keyhole/V-slot cutters, dovetail rails..."""
    w=_plane_pts(pts,plane)
    if r:
        try:
            f=cq.Face.makeFromWires(w.wire().val()); f=f.fillet2D(r,f.Vertices())
            return cq.Workplane(plane).add(f).toPending().extrude(L),dict(stock="print")
        except Exception: pass
    return w.extrude(L),dict(stock="print")
def dovetail(L,root=12,depth=5,angle=60,clear=0,**k):
    """dovetail rail along +Z (length L): narrow root (width root) at y=0, wide top at y=depth; angle = flank angle from the base.
    clear>0 grows it on every flank -> use as a cutter (cut_from) to make the matching slot."""
    u=depth/math.tan(math.radians(angle)); a=root/2+clear; b=root/2+u+clear
    return cq.Workplane("XY").polyline([(-a,-0.01-clear*0),(a,-0.01),(b,depth+clear),(-b,depth+clear)]).close().extrude(L),dict(stock="print",rail=dict(root=root,depth=depth,angle=angle))
def path(pts,w=4,t=6,spline=False,closed=False,**k):
    """a stroke of width w along a polyline/spline [[x,y],..] in XY, extruded t along Z (round ends): flat clips, carabiners, J-hooks, frames."""
    from shapely.geometry import LineString,Polygon
    P=np.array(pts,float)
    if spline and len(P)>2:
        from scipy.interpolate import CubicSpline
        s_=np.r_[0,np.cumsum(np.linalg.norm(np.diff(P,axis=0),axis=1))]; P=CubicSpline(s_,P,bc_type="periodic" if closed and np.allclose(P[0],P[-1]) else "not-a-knot")(np.linspace(0,s_[-1],max(40,len(P)*12)))
    ln=LineString(np.vstack([P,P[:1]]) if closed else P); g=ln.buffer(w/2,quad_segs=12)
    s=cq.Workplane("XY").polyline(list(g.exterior.coords)[:-1]).close().extrude(t)
    for ring in g.interiors: s=s.cut(cq.Workplane("XY").polyline(list(ring.coords)[:-1]).close().extrude(t))
    return s,dict(stock="print")
def arc_plate(r,t,h,angle,**k):
    """curved (bent/rolled) plate: inner radius r, thickness t, height h along Z, spanning angle degrees centred on +Y.
    Axis at x=0,y=0, so the plate's inner face is at y=r. Hip plates, curved guards, rolled bands (angle 360 = full band)."""
    if angle>=359.9: return cq.Workplane("XY").circle(r+t).circle(r).extrude(h),dict(stock="print",curved=True)
    a0,a1=math.radians(90-angle/2),math.radians(90+angle/2); am=math.pi/2; R=r+t
    w=(cq.Workplane("XY").moveTo(R*math.cos(a0),R*math.sin(a0)).threePointArc((R*math.cos(am),R*math.sin(am)),(R*math.cos(a1),R*math.sin(a1)))
       .lineTo(r*math.cos(a1),r*math.sin(a1)).threePointArc((r*math.cos(am),r*math.sin(am)),(r*math.cos(a0),r*math.sin(a0))).close())
    return w.extrude(h),dict(stock="print",curved=True,bend_r=r,arc_deg=angle)
def ring(R,r,flat=0,**k):
    """torus in the XY plane, centre at origin (major radius R, tube radius r): eyelets, hanging loops, O-ring style beads.
    flat>0 trims that much off the bottom so it sits on the bed."""
    s=cq.Workplane("XY").add(cq.Solid.makeTorus(R,r))
    if flat: s=s.cut(cq.Workplane("XY").box(4*(R+r),4*(R+r),flat,centered=(True,True,False)).translate((0,0,-r)))
    return s,dict(stock="print")
def link(L=15,R=7.25,wire=2.25,**k):
    """chain link: a round wire of radius `wire` swept around a stadium (straight length L, end radius R) in the XY plane, centred."""
    pth=cq.Workplane("XY").slot2D(L+2*R,2*R).wires().val()
    p0=pth.startPoint(); tg=pth.tangentAt(0)
    prof=cq.Workplane(cq.Plane(origin=p0.toTuple(),xDir=(0,0,1),normal=tg.toTuple())).circle(wire)
    return prof.sweep(cq.Workplane("XY").add(pth)),dict(stock="print")
KINDS.update(prism=prism,dovetail=dovetail,path=path,arc_plate=arc_plate,ring=ring,link=link)

#!/usr/bin/env python3
"""spec_build.py SPEC.json VDIR -> builds a design from a living spec with the parts kit (kit.py).
Outputs: model.glb (parts named finish__name for renders), model.stl, assembly.step, step/<part>.step, stl/<part>.stl,
parts.json (cut list, flats incl. true outlines + pockets, welds, joints, fasteners, print parts, totals), assumptions.txt.
Spec format: see README 'Living spec'. Values: {"key":{"v":..,"src":"user|assumed","note":".."}}; any string starting with
'=' is an expression over values (math allowed), e.g. "=width-2*t"."""
import sys,os,json,math,re
import cadquery as cq, trimesh, numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import kit, rules
B=os.path.dirname(os.path.abspath(__file__))
spec=json.load(open(sys.argv[1])); os.environ["SPEC_DIR"]=os.path.dirname(os.path.abspath(sys.argv[1])); V=sys.argv[2]; os.makedirs(f"{V}/step",exist_ok=True); os.makedirs(f"{V}/stl",exist_ok=True)
U=spec.get("units","in"); toin=1 if U=="in" else 1/25.4
_pf=os.path.join(B,"profile.json"); PROF=json.load(open(_pf)) if os.path.exists(_pf) else {}
for _k in("printer","filament"):   # assumed printer/filament follow the owner's onboarding profile
    _e=spec["values"].get(_k)
    if isinstance(_e,dict) and _e.get("src")!="user" and PROF.get(_k): _e["v"]=PROF[_k]
vals={k:(v["v"] if isinstance(v,dict) else v) for k,v in spec["values"].items()}
NS=dict(math=math,STOCK=kit.STOCK,**{k:getattr(math,k) for k in("pi","sqrt","sin","cos","tan","radians","degrees","atan2","floor","ceil")})
def ev(x):
    if isinstance(x,str) and x.startswith("="):
        return eval(x[1:],{"__builtins__":{"min":min,"max":max,"round":round,"abs":abs,"int":int,"range":range,"len":len}},{**NS,**vals})
    if isinstance(x,list): return [ev(i) for i in x]
    if isinstance(x,dict): return {k:ev(v) for k,v in x.items()}
    return x
# values given as expressions ("=4.5+2", "=width*2", as spec.py set allows) are evaluated in order
for _k,_v in list(vals.items()):
    if isinstance(_v,str) and _v.startswith("="): vals[_k]=ev(_v)
# derived values (in order) may reference earlier ones
for k,v in spec.get("derived",{}).items(): vals[k]=ev(v)
# expand 'repeat' parts: {"repeat":{"var":"i","n":"=shelves"}, ...}
plist=[]
for p in spec["parts"]:
    if "repeat" in p:
        n=int(ev(p["repeat"]["n"])); var=p["repeat"]["var"]
        for i in range(n):
            vals[var]=i; q=ev({k:v for k,v in p.items() if k!="repeat"}); q["name"]=q["name"].format(i=i+1); plist.append(q)
    else: plist.append(ev(p))
P={}; META={}; LOCAL={}
for p in plist:
    fn=kit.KINDS[p["kind"]]; s,meta=fn(**p.get("args",{}),material=p.get("material","steel"))
    bb=s.val().BoundingBox(); top=bb.zmax
    ft=p.get("features",{})
    if ft.get("text"):   # readable-text rule: the hero camera shows the model's +Y side ("front"). If the text face (local +Z) ends up
        import numpy as _np   # pointing toward -Y after rot, put the text on the opposite face (local bottom, mirrored) so it reads from the front.
        n_=_np.array([0.,0.,1.])
        for ax,ang in zip(range(3),p.get("rot",(0,0,0))):
            if ang:
                c_,s_=_np.cos(_np.radians(ang)),_np.sin(_np.radians(ang)); i_,j_=[(1,2),(2,0),(0,1)][ax]; v=n_.copy(); n_[i_]=c_*v[i_]-s_*v[j_]; n_[j_]=s_*v[i_]+c_*v[j_]
        if n_[1]<-0.5: ft=dict(ft,text=[dict(t,bottom=t.get("bottom",True)) if t.get("face","auto")=="auto" else t for t in ft["text"]])
    s=kit.features(s,ft,top)
    if p.get("fillet"):
        try: s=s.edges("|Z").fillet(p["fillet"])
        except Exception: pass
    LOCAL[p["name"]]=s; P[p["name"]]=kit.place(s,p.get("rot",(0,0,0)),p.get("at",(0,0,0))); META[p["name"]]=dict(meta,_args=p.get("args",{}),**{k:p[k] for k in p if k not in("args","features")})
# ---------- cutter parts: {"cut_from":["plate",..]} = a negative body (any kind) subtracted from those parts, never built itself.
# Belt tunnels, windows, keyholes, V-slots, dovetail slots (dovetail kind with clear), relief cuts, serrations...
for nm in [n for n in P if META[n].get("cut_from")]:
    tgt=META[nm]["cut_from"]; tgt=[tgt] if isinstance(tgt,str) else tgt
    for t_ in tgt: P[t_]=P[t_].cut(P[nm])
    P.pop(nm); META.pop(nm); LOCAL.pop(nm)
plist=[p for p in plist if not p.get("cut_from")]
# ---------- joints (world space boolean ops) ----------
jointrec=[]; welds=[]; fasteners=[]; copes=[]
def big_halfspace(Pt,n,keep_sign):
    n=np.array(n,float); n/=np.linalg.norm(n); S=1e4
    pl=cq.Plane(origin=tuple(Pt),xDir=tuple(np.cross(n,[0,0,1]) if abs(n[2])<0.9 else np.cross(n,[1,0,0])),normal=tuple(n*keep_sign))
    return cq.Workplane(pl).rect(S,S).extrude(S)
def axis_of(name):
    m=META[name]; L=m.get("length"); s=P[name].val(); c=s.Center()
    # local +X axis after rotation
    v=cq.Vector(1,0,0); r=m.get("rot",(0,0,0))
    for ax,ang in zip(((1,0,0),(0,1,0),(0,0,1)),r):
        if ang: v=cq.Vector(*cq.Workplane().add(cq.Vertex.makeVertex(v.x,v.y,v.z)).val().rotate((0,0,0),ax,ang).toTuple())
    return np.array([c.x,c.y,c.z]),np.array([v.x,v.y,v.z])
_AX={}
_ax0=axis_of
def axis_of(name):   # axes from the uncut parts, so cut order doesn't shift later miters
    if name not in _AX: _AX[name]=_ax0(name)
    return _AX[name]
for _n in list(P): axis_of(_n)
JL=[]
for j in spec.get("joints",[]):   # expand {"repeat":{"var":"i","n":"=shelves"},"into":"side_L","from":"shelf{i}"}
    if "repeat" in j:
        n=int(ev(j["repeat"]["n"])); var=j["repeat"]["var"]
        for i in range(n):
            vals[var]=i; q={k:(v.format(i=i+1) if isinstance(v,str) and not v.startswith("=") else v) for k,v in j.items() if k!="repeat"}; JL.append(ev(q))
    else: JL.append(j)
for j in JL:
    j=ev(j); t=j["type"]; rec=dict(j)
    if t in("dado","rabbet","groove","housing"):
        cl=j.get("clear",0.01 if U=="in" else 0.2); tool=P[j["from"]].val()
        bb=tool.BoundingBox()   # 'from' part must overlap 'into' by the dado depth; cut its footprint + clearance
        ib=P[j["into"]].val().BoundingBox(); th=min((ib.xlen,0),(ib.ylen,1),(ib.zlen,2))[1]   # don't grow into the depth axis
        gr=[2*cl if k!=th else 0 for k in range(3)]
        g=cq.Workplane("XY").box(bb.xlen+gr[0],bb.ylen+gr[1],bb.zlen+gr[2]).translate((bb.center.x,bb.center.y,bb.center.z))
        P[j["into"]]=P[j["into"]].cut(g)
    elif t=="lap":
        A,Bn=P[j["a"]],P[j["b"]]; ov=A.intersect(Bn); bb=ov.val().BoundingBox(); zmid=bb.zmin+bb.zlen/2
        upper=cq.Workplane("XY").box(bb.xlen+0.02,bb.ylen+0.02,bb.zlen/2+0.01).translate((bb.center.x,bb.center.y,zmid+bb.zlen/4))
        lower=cq.Workplane("XY").box(bb.xlen+0.02,bb.ylen+0.02,bb.zlen/2+0.01).translate((bb.center.x,bb.center.y,zmid-bb.zlen/4))
        P[j["a"]]=A.cut(upper); P[j["b"]]=Bn.cut(lower)
    elif t in("box","finger"):
        A,Bn=P[j["a"]],P[j["b"]]; ov=A.intersect(Bn).val(); bb=ov.BoundingBox(); n=int(j.get("n",5)); ax=j.get("axis","z")
        L={"x":bb.xlen,"y":bb.ylen,"z":bb.zlen}[ax]; seg=L/n
        for i in range(n):
            lo=getattr(bb,ax+"min")+i*seg; dims=[bb.xlen+0.02,bb.ylen+0.02,bb.zlen+0.02]; ctr=[bb.center.x,bb.center.y,bb.center.z]
            k="xyz".index(ax); dims[k]=seg; ctr[k]=lo+seg/2; slab=cq.Workplane("XY").box(*dims).translate(tuple(ctr))
            if i%2==0: A=A.cut(slab)
            else: Bn=Bn.cut(slab)
        P[j["a"]],P[j["b"]]=A,Bn
    elif t in("mortise_tenon","mortise"):
        # tenon = 'b' end inside 'a'; shoulders trimmed by 'shoulder' on the two thin faces; mortise = tenon + clear
        A,Bn=P[j["a"]],P[j["b"]]; ov=A.intersect(Bn).val(); bb=ov.BoundingBox(); sh=j.get("shoulder",0.25 if U=="in" else 6); cl=j.get("clear",0.0025 if U=="in" else 0.06); rec["clear"]=cl   # 0.004-0.005 in total (catalog #139)
        thin=min(("x",bb.xlen),("y",bb.ylen),("z",bb.zlen),key=lambda kv:kv[1])[0]
        dims=[bb.xlen,bb.ylen,bb.zlen]; k="xyz".index(thin); dims[k]=max(dims[k]-2*sh,dims[k]/3)
        ten=cq.Workplane("XY").box(*dims).translate((bb.center.x,bb.center.y,bb.center.z))
        Bn=Bn.cut(cq.Workplane("XY").box(bb.xlen+0.01,bb.ylen+0.01,bb.zlen+0.01).translate((bb.center.x,bb.center.y,bb.center.z)).cut(ten))
        A=A.cut(cq.Workplane("XY").box(*[d+2*cl for d in dims]).translate((bb.center.x,bb.center.y,bb.center.z)))
        P[j["a"]],P[j["b"]]=A,Bn
    elif t=="miter":
        (ca,da),(cb,db)=axis_of(j["a"]),axis_of(j["b"])
        # corner point = closest approach of the two axes
        w0=ca-cb; a_,b_,c_,d_,e_=da@da,da@db,db@db,da@w0,db@w0; den=a_*c_-b_*b_ or 1e-9
        Pt=(ca+da*((b_*e_-c_*d_)/den)+cb+db*((a_*e_-b_*d_)/den))/2
        ua=ca-Pt; ua/=np.linalg.norm(ua); ub=cb-Pt; ub/=np.linalg.norm(ub); n=ua-ub
        P[j["a"]]=P[j["a"]].intersect(big_halfspace(Pt,n,1)); P[j["b"]]=P[j["b"]].intersect(big_halfspace(Pt,n,-1))
        ang=math.degrees(math.acos(np.clip(-(ua@ub)*-1,-1,1)))/2; rec["miter_deg"]=round(ang,1)
        for nm in(j["a"],j["b"]): META[nm].setdefault("ends",[]).append(f"{rec['miter_deg']}° miter")
    elif t=="cope":
        hdr=P[j["header"]]; m=META[j["header"]]; c,d=axis_of(j["header"]); od=m["od"]
        cyl=cq.Workplane(cq.Plane(origin=tuple(c-d*1e3),xDir=tuple(np.cross(d,[0,0,1]) if abs(d[2])<0.9 else (1,0,0)),normal=tuple(d))).circle(od/2).extrude(2e3)
        P[j["branch"]]=P[j["branch"]].cut(cyl); META[j["branch"]].setdefault("ends",[]).append("coped")
        copes.append(dict(branch=j["branch"],header_od=od,branch_od=META[j["branch"]]["od"],angle=j.get("angle",90),ends=1))
    elif t=="bolted":
        if not j.get("d"):   # hole size from the clearance / tap table, never guessed
            _dd,_src=(rules.tap_for(j.get("bolt","")) if j.get("tapped") else rules.clearance_for(j.get("bolt",""),U))
            if _dd is None: raise SystemExit(f"bolted joint: no table size for '{j.get('bolt')}' - give d or a standard bolt (e.g. 3/8-16, M8)")
            j["d"]=_dd/toin; rec["d"]=j["d"]; rec["d_src"]=_src
        d=np.array(j.get("axis",[0,0,1]),float); d/=np.linalg.norm(d); at=np.array(j["at"],float)
        cyl=cq.Workplane(cq.Plane(origin=tuple(at-d*500),xDir=tuple(np.cross(d,[0,0,1]) if abs(d[2])<0.9 else (1,0,0)),normal=tuple(d))).circle(j["d"]/2).extrude(1000)
        for nm in j["parts"]: P[nm]=P[nm].cut(cyl)
        fasteners.append(dict(item=j.get("bolt","bolt"),qty=j.get("qty",1)))
    elif t in("screws","nails","glue"):
        fasteners.append(dict(item=j.get("size",t),qty=j.get("n",1)))
    elif t=="welded":
        A,Bn=P[j["a"]],P[j["b"]]
        try:
            con=A.intersect(Bn); bb=con.val().BoundingBox()
            dims=sorted([bb.xlen,bb.ylen,bb.zlen]); est=2*(dims[1]+dims[2])
        except Exception: est=0
        if est<1e-6:
            bbA=A.val().BoundingBox(); bbB=Bn.val().BoundingBox()
            ix=[max(0,min(getattr(bbA,a+"max"),getattr(bbB,a+"max"))-max(getattr(bbA,a+"min"),getattr(bbB,a+"min"))) for a in "xyz"]
            dims=sorted(ix); est=2*(dims[1]+dims[2])
        wl=j.get("length",est*j.get("fraction",1.0))
        welds.append(dict(part=f'{j["a"]} to {j["b"]}',weld=j.get("weld","fillet all around"),weld_in=round(wl*toin,1)))
    jointrec.append(rec)
# ---------- exports ----------
sc=trimesh.Scene(); asm=cq.Assembly(); dens=json.load(open(f"{B}/prices.json"))["density_lb_in3"]
PM=json.load(open(f"{B}/printers.json")) if os.path.exists(f"{B}/printers.json") else {}
rows={}; flats=[]; printparts=[]; groups={}
_MEMB={p_["name"]:p_ for p_ in plist} if "plist" in globals() else {}
for nm,s in P.items():
    m=META[nm]
    if m.get("group"): groups.setdefault(m["group"],[]).append(nm); continue
for g,names in groups.items():   # print groups -> single body
    u=P[names[0]]
    for n2 in names[1:]: u=u.union(P[n2])
    P[g]=u; META[g]=dict(META[names[0]],name=g,kind=META[names[0]].get("kind") if len(names)==1 else "printed"); [META[g].update({k_:META[n2][k_]}) for n2 in names for k_ in ("assembly","bodies","clearance") if META[n2].get(k_) is not None]; [P.pop(n2) for n2 in names if n2!=g]; [META.pop(n2) for n2 in names if n2!=g]
for nm,s in P.items():
    m=META[nm]; sol=s.val(); vol=sol.Volume()*toin**3
    cq.exporters.export(s,f"{V}/step/{nm}.step"); cq.exporters.export(s,f"{V}/stl/{nm}.stl",tolerance=0.01 if U=="in" else 0.05)
    ar=m.get("_args",{})
    if m.get("kind") in("imported","custom_stl") and str(ar.get("file","")).lower().rsplit(".",1)[-1] not in("step","stp","iges","igs","brep"):
        # renders + printing use the ORIGINAL mesh (scaled/placed like the CAD copy); the sewn CAD copy is only for STEP/drawings
        om=trimesh.load(kit._path(ar["file"]),force="mesh"); om.apply_translation(-om.bounds[0]); sc_=ar.get("scale",1.0)
        om.apply_scale([ar.get("sx") or sc_,ar.get("sy") or sc_,ar.get("sz") or sc_]); bb_=sol.BoundingBox(); om.apply_translation([bb_.xmin,bb_.ymin,bb_.zmin]); om.export(f"{V}/stl/{nm}.stl")
    asm.add(s,name=nm)
    tm=trimesh.load(f"{V}/stl/{nm}.stl")
    if spec.get("render_rot"): tm.apply_transform(trimesh.transformations.rotation_matrix(math.radians(spec["render_rot"]),(0,0,1)))   # renders look from -Y
    _FIL=("PLA","PETG","TPU","ABS","ASA","PA","PC")
    _mat=str(m.get("material","steel"))
    fin=m.get("finish") or ("cedar" if any(k in _mat.lower() for k in ("dowel","oak","maple","birch","walnut")) else "plastic" if _mat.upper() in _FIL or m.get("stock")=="print" else {"plywood":"cedar","baltic_birch":"cedar","pine":"cedar","hardwood":"cedar","cedar":"cedar","wood":"cedar","steel":"raw_steel"}.get(_mat,"raw_steel"))
    sc.add_geometry(tm,geom_name=f"{fin}__{nm}",node_name=f"{fin}__{nm}")
    st=m.get("stock")
    # store-bought stock (dowel, rod, pipe, screws, hinges...) is NEVER printed: it goes on the cut/shopping list as a buy item
    _BUY=("dowel","rod","pipe","conduit","tube","tubing","bolt","screw","nut","washer","nail","hinge","magnet","bearing","spring","hardware","threaded","rivet","pin","bracket","caster","wheel","handle pull","knob","latch","chain","cable","wire","rope","strap","buckle","zip tie","glass","mirror","led")
    if st=="print" and _mat.upper() not in _FIL and any(k in _mat.lower() for k in _BUY):
        st=m["stock"]="buy"; bb_=sol.BoundingBox(); ex_=sorted([bb_.xlen,bb_.ylen,bb_.zlen])
        key=("buy",_mat,round(ex_[2],3),round(ex_[1],3))
        r_=rows.setdefault(key,dict(part=m.get("label",nm),material=_mat,stock="buy",qty=0,length=f"{ex_[2]:.3f} {U} long, {ex_[1]:.3f} {U} dia/width",notes="BUY (store-bought) - cut to length; not printed",_w=0,_names=[]))
        r_["qty"]+=1; r_["_w"]+=vol*dens.get("lumber",0.02); r_["_names"].append(nm)
        continue
    if st=="print":
        _tb=[]   # screw-thread bands (thread teeth are form features: ship.py exempts them from the 2 mm wall rule)
        for _mn in ([x for x in groups.get(nm,[])] or [nm]):
            _mm=_MEMB.get(_mn,{}); _r=_mm.get("rot",[0,0,0]) or [0,0,0]; _at=_mm.get("at",[0,0,0]) or [0,0,0]
            if _mm.get("kind") in("round","cylinder","cone") and not (_r[0] or _r[1]):
                for _t in (_mm.get("args",{}).get("threads") or []):
                    _tb.append(dict(c=[float(_at[0]),float(_at[1])],r=float(_t["r"]),depth=float(_t.get("depth",1))+float(_t.get("clearance",0)),
                        z0=float(_at[2])+float(_t.get("z",0)),z1=float(_at[2])+float(_t.get("z",0))+float(_t.get("pitch",2))*(float(_t.get("turns",2))+1)))
        printparts.append(dict(name=nm,stl=f"stl/{nm}.stl",volume_mm3=round(sol.Volume() if U=="mm" else sol.Volume()*16387.064,1),
            material=m.get("material","PLA"),orient=m.get("print_orient",[0,0,0]),infill=m.get("infill",20),thread_bands=_tb,
            **{k_:m[k_] for k_ in ("assembly","bodies","clearance") if m.get(k_) is not None}))
        # weight estimate for printed parts: filament density x (shell + infill fraction) ~ 45% solid at 20% infill
        _gcc={"PLA":1.24,"PETG":1.27,"TPU":1.21,"ABS":1.04,"ASA":1.07}.get(_mat.upper(),1.24)
        _cm3=(sol.Volume() if U=="mm" else sol.Volume()*16387.064)/1000; _w=_cm3*_gcc*0.6/453.6
        rows[nm]=dict(part=nm,material=_mat,qty=1,length="printed",notes="3D print (weight est.)",_w=_w,_names=[nm],stock="print")
        continue
    dk={"plate":"plate","tube":"tube","angle":"tube","bar":"plate","lumber":"lumber","sheet_good":"plywood"}.get(st,"plate")
    if m.get("material") in("acrylic",): dk="acrylic"
    w=vol*dens.get(dk,0.03)
    if m.get("flat_t"): m["flat"]=True; m["t"]=m["flat_t"]
    if m.get("bent"):   # bent sheet metal: flat blank from the bend allowance (K flagged as estimate), holes mapped onto the blank
        bt=m["bent"]; k_=toin; u0=bt["Bf"]; u1=bt["Bf"]+bt["BA"]; Ln=bt["L"]; RT=bt["R"]+bt["t"]
        hl=[(round((bt["Bf"]+bt["BA"]+(h["x"]-RT))*k_,4),round(h["y"]*k_,4),round(h["d"]/2*k_,4)) for h in bt["holes_a"]]+[(round((bt["Bf"]-(h["z"]-RT))*k_,4),round(h["y"]*k_,4),round(h["d"]/2*k_,4)) for h in bt["holes_b"]]
        if bt["wb"]<bt["W"]:   # partial-width bend: leg b only y<wb, relief notch y wb..wb+rw past the bend
            q_=lambda u,y:(round(u*k_,4),round(y*k_,4)); ue=u1+max(bt["relief_d"]-RT,0)
            ol=[q_(0,0),q_(Ln,0),q_(Ln,bt["W"]),q_(u1-RT,bt["W"]),q_(u1-RT,bt["wb"]+bt["relief_w"]),q_(ue,bt["wb"]+bt["relief_w"]),q_(ue,bt["wb"]),q_(0,bt["wb"])]
        else: ol=[(0,0),(round(Ln*k_,4),0),(round(Ln*k_,4),round(bt["W"]*k_,4)),(0,round(bt["W"]*k_,4))]
        flats.append(dict(name=nm,shape="poly",outer=ol+[ol[0]],inner_poly=[],holes=hl,pockets=[],w=round(Ln*k_,4),h=round(bt["W"]*k_,4),thickness=round(bt["t"]*k_,4),material=m.get("material","steel"),
            blank_length=round(Ln*k_,4),bends=[dict(u0=round(u0*k_,4),u1=round(u1*k_,4),angle=90,R=round(bt["R"]*k_,4),K=bt["K"],BA=round(bt["BA"]*k_,4),flanges=[round(bt["a"]*k_,4),round(bt["b"]*k_,4)],
            partial=bt["wb"]<bt["W"],relief_w=round(bt["relief_w"]*k_,4),relief_d=round(bt["relief_d"]*k_,4))]))
    if m.get("flat") and not m.get("bent"):
        # true outline: section the part at mid-thickness in its local frame (inverse placement)
        loc=P[nm]; at=m.get("at",(0,0,0)); r=m.get("rot",(0,0,0))
        loc=loc.translate(tuple(-a for a in at))
        for ax,ang in reversed(list(zip(((1,0,0),(0,1,0),(0,0,1)),r))):
            if ang: loc=loc.rotate((0,0,0),ax,-ang)
        t=m["t"]
        def section(z):
            from shapely.geometry import Polygon
            from shapely.ops import unary_union
            faces=cq.Workplane("XY").add(loc.val()).section(z).faces().vals()
            polys=[]
            for face in faces:
                def wpts(w_):   # ordered: exact corners for straight edges, 24 pts per curved edge
                    from OCP.BRepTools import BRepTools_WireExplorer
                    from OCP.BRep import BRep_Tool
                    ex=BRepTools_WireExplorer(w_.wrapped); pts=[]
                    while ex.More():
                        e=cq.Edge(ex.Current()); v0=BRep_Tool.Pnt_s(ex.CurrentVertex()); p0=(v0.X(),v0.Y())
                        if e.geomType()=="LINE": pts.append(p0)
                        else:
                            q=[e.positionAt(u) for u in np.linspace(0,1,24)]; q=[(v.x,v.y) for v in q]
                            if math.dist(q[0],p0)>math.dist(q[-1],p0): q=q[::-1]
                            pts+=q[:-1]
                        ex.Next()
                    return pts
                outer=wpts(face.outerWire()); inn=[wpts(w_) for w_ in face.innerWires()]
                polys.append(Polygon(outer,inn).buffer(0))
            return unary_union(polys)
        try:
            mid=section(t/2); top=section(t-1e-3); bot=section(1e-3)
            ext=max(mid.geoms,key=lambda g:g.area) if mid.geom_type=="MultiPolygon" else mid
            mnx,mny,_,_=ext.bounds
            sh=lambda pts:[(round(x-mnx,4),round(y-mny,4)) for x,y in pts]
            holes=[];ipoly=[]
            from shapely.geometry import Polygon
            for ring in ext.interiors:
                c=list(ring.coords); xs=[p[0] for p in c]; ys=[p[1] for p in c]; cx,cy=(max(xs)+min(xs))/2,(max(ys)+min(ys))/2
                rr=[math.hypot(x-cx,y-cy) for x,y in c]
                _ar=Polygon(c).area if len(c)>2 else 0; _rm=sum(rr)/len(rr)
                # a circle, not just "all vertices equidistant" (a rectangle's 4 corners are too: thin slots were becoming 2 in holes)
                if len(c)>=12 and max(rr)-min(rr)<0.01*max(rr)+1e-4 and abs(_ar-math.pi*_rm*_rm)<0.03*math.pi*_rm*_rm: holes.append((round(cx-mnx,4),round(cy-mny,4),round(sum(rr)/len(rr),4)))
                else: ipoly.append(sh(c))
            pockets=[]
            for face_,other,zs in (("top",top,np.linspace(t-1e-3,1e-3,25)),("bottom",bot,np.linspace(1e-3,t-1e-3,25))):
                pk=mid.difference(other).buffer(-1e-4).buffer(1e-4)
                for g_ in (pk.geoms if pk.geom_type=="MultiPolygon" else [pk] if not pk.is_empty else []):
                    if g_.area>1e-3:
                        c_=g_.representative_point(); dep=0
                        for zz in zs:   # probe in from that face until the point is solid
                            if section(zz).contains(c_): dep=abs((t if face_=="top" else 0)-zz); break
                        pockets.append(dict(poly=sh(list(g_.exterior.coords)),depth=round(dep,4),face=face_))
            outer_=sh(list(ext.exterior.coords)); W_=ext.bounds[2]-mnx
            if pockets and all(q["face"]=="bottom" for q in pockets):   # all pockets on one face: flip the part so they face up (one-sided CNC)
                mx=lambda pts:[(round(W_-x,4),y) for x,y in pts]
                outer_=mx(outer_); ipoly=[mx(q) for q in ipoly]; holes=[(round(W_-x,4),y,r) for x,y,r in holes]
                for q in pockets: q["poly"]=mx(q["poly"]); q["face"]="top"
            fl_=dict(name=nm,shape="poly",outer=outer_,inner_poly=ipoly,holes=holes,pockets=pockets,
                              w=round(ext.bounds[2]-mnx,4),h=round(ext.bounds[3]-mny,4),thickness=t,material=m.get("material","steel"))
            if U=="mm":   # nesting / G-code / DXF work in inches
                k_=1/25.4; sc_=lambda pts:[(round(x*k_,4),round(y*k_,4)) for x,y in pts]
                fl_.update(outer=sc_(fl_["outer"]),inner_poly=[sc_(q) for q in ipoly],holes=[(round(x*k_,4),round(y*k_,4),round(r*k_,4)) for x,y,r in holes],
                           pockets=[dict(q,poly=sc_(q["poly"]),depth=round(q["depth"]*k_,4)) for q in pockets],w=round(fl_["w"]*k_,4),h=round(fl_["h"]*k_,4),thickness=round(t*k_,4),units_note="converted from mm")
            flats.append(fl_)
        except Exception as e: print("flat extraction failed",nm,e)
    L=m.get("length"); sec=m.get("section",st); ends=", ".join(m.get("ends",[]))
    dims=sol.BoundingBox(); key=(sec,round((L or 0),3),ends,m.get("material"),m.get("label",nm),tuple(sorted(round(x,2) for x in (dims.xlen,dims.ylen,dims.zlen))))
    dims=sol.BoundingBox(); size_txt=f'{L:.3f}' if L else f'{sorted([dims.xlen,dims.ylen,dims.zlen])[2]:.3f} x {sorted([dims.xlen,dims.ylen,dims.zlen])[1]:.3f}'
    r_=rows.setdefault(key,dict(part=m.get("label",nm),material=sec,stock=st,qty=0,length=size_txt+(" "+U),notes=ends,_w=0,_names=[]))
    r_["qty"]+=1; r_["_w"]+=w; r_["_names"].append(nm)
asm.save(f"{V}/assembly.step"); sc.export(f"{V}/model.glb")
trimesh.util.concatenate([g for g in sc.dump()]).export(f"{V}/model.stl")
pr=json.load(open(f"{B}/prices.json")); cut=[]; tw=tc=0
_PD=json.load(open(f"{B}/prices_default.json")) if os.path.exists(f"{B}/prices_default.json") else {}
def _price(sec,key):
    """(price, source): the owner's prices.json first, then the toolbox defaults file. No hidden numbers in code."""
    if key in pr.get(sec,{}): return pr[sec][key],f"prices.json {sec}[{key}]"
    if key in _PD.get(sec,{}): return _PD[sec][key],f"prices_default.json {sec}[{key}] (toolbox default; set yours in prices.json)"
    return None,f"MISSING: no {sec}[{key}] in prices.json"
for i,r_ in enumerate(rows.values()):
    m0=META[r_["_names"][0]]
    def _c(v,mult): return (v*mult) if v is not None else 0.0
    if m0.get("stock")=="buy":   # store-bought: $/ft if priced, else $ each (prices.json buy_each)
        _L=float(re.findall(r"[\d.]+",r_["length"])[0])*toin; v,src=_price("price_per_ft",r_["material"])
        if v is not None: cost=_c(v,_L/12*r_["qty"])
        else: v,src=_price("buy_each",r_["material"]); cost=_c(v,r_["qty"])
    elif m0.get("stock")=="print": cost=0; src="slicer (print.json filament cost)"
    elif r_["material"] in pr.get("price_per_ft",{}) or r_["material"] in _PD.get("price_per_ft",{}) or m0.get("stock")=="lumber":
        L=float(re.findall(r"[\d.]+",r_["length"])[0])*toin; v,src=_price("price_per_ft",r_["material"]); cost=_c(v,L/12*r_["qty"])
    elif m0.get("stock")=="sheet_good":   # priced by area at $/sqft
        v,src=_price("price_per_sqft",m0.get("material","plywood")); cost=_c(v,sum(P[n].val().Volume()*toin**3/(m0["t"]*toin)/144 for n in r_["_names"]))
    else: v,src=_price("price_per_lb",r_["stock"] if r_["stock"]!="angle" else "tube"); cost=_c(v,r_["_w"])
    tw+=r_["_w"]; tc+=cost
    cut.append({"mark":chr(65+i) if i<26 else f"A{i}","part":r_["part"],"material":r_["material"],"qty":r_["qty"],"length":r_["length"],"weight":f'{r_["_w"]:.1f} lb',"est. cost":f"~${cost:.0f}","notes":r_["notes"],"names":r_["_names"],"stock":m0.get("stock"),"cost_usd":round(cost,2),"cost_src":src})
for f in fasteners: cut.append({"mark":"HW","part":"Hardware","material":f["item"],"qty":f["qty"],"length":"","weight":"","est. cost":"","notes":"","stock":"buy","cost_src":"not priced (hardware)"})
title=spec.get("title",spec.get("name","Design"))
out=dict(params=dict(kind="spec",title=title,units=U,**{k:v for k,v in vals.items() if isinstance(v,(int,float,str))}),cutlist=cut,flats=flats,welds=welds,joints=copes,
         jointrec=jointrec,fasteners=fasteners,print_parts=printparts,total_weight_lb=round(tw,1),est_cost=round(tc,2))
SRC={k:(v.get("src","assumed") if isinstance(v,dict) else "assumed") for k,v in spec["values"].items()}
def srcof(expr):
    if not (isinstance(expr,str) and expr.startswith("=")): return "user"
    names=set(re.findall(r"[A-Za-z_]\w*",expr)); dep={n for n in names if n in SRC}
    for k,v in spec.get("derived",{}).items():
        if k in names: dep|={n for n in re.findall(r"[A-Za-z_]\w*",v) if n in SRC}
    return "assumed" if any(SRC[n]!="user" for n in dep) else "user"
out["dims"]=[dict(expr=dm["v"],label=dm.get("label",""),value=round(float(ev(dm["v"])),4),view=dm.get("view","front"),axis=dm.get("axis","h"),
    span=ev(dm["span"]) if "span" in dm else None,at=ev(dm["at"]) if "at" in dm else None,src=srcof(dm["v"]),**{k_:dm[k_] for k_ in ("tol","fit","fit_class") if k_ in dm}) for dm in spec.get("dims",[])]
out["spec_values"]={k:dict(v=vals.get(k),src=SRC[k],unit=(spec["values"][k].get("unit","") if isinstance(spec["values"][k],dict) else ""),note=(spec["values"][k].get("note","") if isinstance(spec["values"][k],dict) else "")) for k in SRC}
out["title"]=spec.get("title"); out["domain"]=spec.get("domain")
out=rules.enrich(out,spec,META,jointrec,U,kit.STOCK)
json.dump(out,open(f"{V}/parts.json","w"),indent=1,default=float)
VERB={"print":"Printing","wood":"Fitting","metal":"Fitting"}.get(spec.get("domain"),"Adding")
stp=spec.get("steps") or []
seen=set(q[0] for q in stp)
for p in plist:
    nm=p["group"] if p.get("group") else p["name"]
    if nm in seen: continue
    seen.add(nm); stp.append([nm,(f"Printing the {nm.replace('_',' ')}" if p.get("group") else f'{VERB} the {p.get("label",nm).lower()}' + ("s" if sum(1 for q in plist if q.get("label")==p.get("label") and p.get("label"))>1 else ""))])
json.dump(stp,open(f"{V}/steps.json","w"))
A=[f'{k} = {v["v"]} {v.get("unit","")}  ({v.get("note","")})' for k,v in spec["values"].items() if isinstance(v,dict) and v.get("src")=="assumed"]
open(f"{V}/assumptions.txt","w").write("\n".join(A)+"\n")
print(f"{V}: {len(P)} parts, {len(flats)} flats, {len(printparts)} print parts, {len(welds)} welds, weight ~{tw:.1f} lb")

#!/usr/bin/env python3
"""print3d.py VDIR OUTDIR [--printer KEY] [--filament PLA|PETG|TPU]
Full-size FDM pipeline for parts.json print_parts (printers.json profiles):
  orient -> printability checks (manifold/watertight, overhangs vs filament limit, thin walls by inward ray-cast, bed fit)
  -> split parts bigger than the bed into pieces with 2 alignment-pin holes per seam (print or use 3 mm dowel/filament pins)
  -> PrusaSlicer CLI: <part>.gcode + <part>.3mf, time, grams, cost  -> print.json + print_report.txt + preview PNG.
Bambu printers: open the .3mf in Bambu Studio and re-slice there (G-code here is generic Marlin). ESTIMATES: check in your slicer."""
import sys,os,json,re,subprocess,math,trimesh,numpy as np
import manifold3d as mf, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
B=os.path.dirname(os.path.abspath(__file__)); V,O=sys.argv[1],sys.argv[2]; a=sys.argv[3:]; os.makedirs(O,exist_ok=True)
PR=json.load(open(f"{B}/printers.json")); d=json.load(open(f"{V}/parts.json")); U=d["params"].get("units","in")
pk=a[a.index("--printer")+1] if "--printer" in a else d["params"].get("printer",PR["active"])
if pk not in PR["printers"]: pk=PR["active"]
prn=PR["printers"][pk]; rules=PR["rules"]; PS=os.path.join(B,"..","tools","prusaslicer","AppRun")
def tomf(m): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices,np.float32),tri_verts=np.asarray(m.faces,np.uint32)))
def totm(M): mm=M.to_mesh(); return trimesh.Trimesh(mm.vert_properties[:,:3],mm.tri_verts)
def rot(m,r):
    for ax,ang in zip(((1,0,0),(0,1,0),(0,0,1)),r):
        if ang: m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(ang),ax))
    m.apply_translation(-m.bounds[0]); return m
def checks(m,fil):
    r={}; r["watertight"]=bool(m.is_watertight)
    try: r["manifold"]=tomf(m).status()==mf.Error.NoError
    except Exception: r["manifold"]=False
    lim=math.radians(90-PR["filaments"][fil]["max_overhang_deg"]); nz=m.face_normals[:,2]; zc=m.triangles_center[:,2]
    bad=(nz< -math.cos(lim))&(zc>0.3); r["overhang_mm2"]=round(float(m.area_faces[bad].sum()),1)
    r["needs_supports"]=r["overhang_mm2"]>150   # small hole tops bridge fine
    # thin walls: shoot rays inward from sampled surface points
    pts,fi=trimesh.sample.sample_surface_even(m,1500); nrm=m.face_normals[fi]
    loc,ri,_=m.ray.intersects_location(pts-nrm*1e-3,-nrm,multiple_hits=False)
    th=np.full(len(pts),np.inf); th[ri]=np.linalg.norm(loc-pts[ri],axis=1)
    r["min_wall_mm"]=round(float(th.min()),2); r["thin_pct"]=round(100*float((th<rules["min_wall_mm"]).mean()),1)
    r["thin_walls"]=r["thin_pct"]>2
    try: r["bodies"]=int(len(m.split(only_watertight=False)))
    except Exception: r["bodies"]=1
    return r
def split(m,bx,by,bz):
    """cut along the longest overflowing axis into k equal pieces; pin holes (2 per seam) in both faces"""
    ext=m.extents; lims=np.array([bx,by,bz])-10; over=ext/lims; ax=int(np.argmax(over)); k=int(math.ceil(over[ax]))
    if k<=1: return [m],[]
    M=tomf(m); lo,hi=m.bounds[0][ax],m.bounds[1][ax]; pieces=[]; seams=[]
    for i in range(k):
        a0=lo+(hi-lo)*i/k; a1=lo+(hi-lo)*(i+1)/k
        n=np.zeros(3); n[ax]=1
        P=M.trim_by_plane(n.tolist(),float(a0)).trim_by_plane((-n).tolist(),float(-a1)); pieces.append(P)
        if i: seams.append(a0)
    hd=rules["pin_hole_mm"]; dep=6.0; out=[]; npins={}
    for i,P in enumerate(pieces):
        for s_ in seams:
            sec=m.section(plane_origin=[s_ if j==ax else 0 for j in range(3)],plane_normal=[1 if j==ax else 0 for j in range(3)])
            if sec is None: continue
            p2,T3=sec.to_2D(); poly=max(p2.polygons_full,key=lambda g:g.area); inner=poly.buffer(-(hd+1.5))
            if inner.is_empty: npins[s_]=0; continue
            npins[s_]=2
            from shapely.geometry import Point
            ib=inner.bounds; long_x=(ib[2]-ib[0])>=(ib[3]-ib[1])
            cand=[Point(ib[0]+(ib[2]-ib[0])*f,(ib[1]+ib[3])/2) if long_x else Point((ib[0]+ib[2])/2,ib[1]+(ib[3]-ib[1])*f) for f in (0.2,0.8)]
            for q in cand:   # two pins spread along the seam face
                if not inner.contains(q): q=inner.representative_point()
                p3=trimesh.transformations.transform_points([[q.x,q.y,0]],T3)[0]
                cyl=trimesh.creation.cylinder(radius=hd/2,height=2*dep,sections=24)
                if ax==0: cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,(0,1,0)))
                if ax==1: cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,(1,0,0)))
                c3=p3.copy(); c3[ax]=s_; cyl.apply_translation(c3); P=P-tomf(cyl)
        pieces[i]=P; out.append(totm(P))
    return out,[dict(axis="xyz"[ax],at_mm=round(float(s_),1),pins=npins.get(s_,0),pin=(f'{rules["pin_d_mm"]} mm x {2*dep:.0f} mm (dowel, printed pin or filament)' if npins.get(s_) else
        f'none: walls too thin for {hd} mm pin holes - glue with CA/epoxy and add a printed splice plate, or thicken the walls to >= {hd+3:.0f} mm')) for s_ in seams]
def slice_(stl,base,fil,sup,inf):
    F=PR["filaments"][fil]; bx,by,bz=prn["bed"]
    common=["--center",f"{bx/2},{by/2}","--bed-shape",f"0x0,{bx}x0,{bx}x{by},0x{by}","--max-print-height",str(bz),"--nozzle-diameter",str(prn["nozzle"]),
        "--layer-height","0.2","--perimeters","3","--fill-density",f"{inf}%","--filament-type",fil,"--temperature",str(F["temp"]),"--bed-temperature",str(F["bed"]),"--first-layer-temperature",str(F["temp"]),"--first-layer-bed-temperature",str(F["bed"]),
        "--filament-density",str(F["density"]),"--filament-cost",str(F["usd_per_kg"]),"--gcode-flavor",prn.get("flavor","marlin2")]+(["--support-material","--support-material-auto"] if sup else [])
    for k,v in prn.get("speeds",{}).items():   # per-printer speed profile (printers.json); without it PrusaSlicer's generic defaults inflate times ~2x
        if k.startswith("_"): continue
        if isinstance(v,dict): v=v.get(fil)
        if v is not None: common+=[f"--{k}",str(v)]
    info={}
    if not os.path.exists(PS): return dict(slicer_error="PrusaSlicer not installed")
    r=subprocess.run([PS,"--export-gcode"]+common+["-o",base+".gcode",stl],capture_output=True,text=True,timeout=1200)
    subprocess.run([PS,"--export-3mf"]+common+["-o",base+".3mf",stl],capture_output=True,text=True,timeout=600)
    if not os.path.exists(base+".gcode"): return dict(slicer_error=(r.stdout+r.stderr)[-500:])
    t=open(base+".gcode",errors="ignore").read()
    for k,pat in(("time",r"estimated printing time \(normal mode\) = (.+)"),("grams",r"total filament used \[g\] = ([\d.]+)"),("cost",r"total filament cost = ([\d.]+)"),("meters",r"filament used \[mm\] = ([\d.]+)")):
        mt=re.search(pat,t); info[k]=mt.group(1).strip() if mt else None
    if info.get("meters"): info["meters"]=round(float(info["meters"])/1000,2)
    if info.get("grams") in (None,"0.00") and info.get("meters"): info["grams"]=round(info["meters"]*math.pi*0.875**2*F["density"],1)
    info["3mf"]=os.path.exists(base+".3mf")
    if info["3mf"]:   # embed the exact slice profile (PETG temps, supports, speeds) so the 3MF re-opens with Sketch's settings, not the user's last profile
        try:
            import zipfile
            cfg=t[t.index("; prusaslicer_config = begin"):t.index("; prusaslicer_config = end")].splitlines()[1:]
            with zipfile.ZipFile(base+".3mf","a") as z:
                if "Metadata/Slic3r_PE.config" not in z.namelist(): z.writestr("Metadata/Slic3r_PE.config","\n".join(cfg)+"\n")
        except Exception as e: info["3mf_note"]=f"profile not embedded: {e}"
    return info
res=dict(printer=prn["label"],printer_key=pk,parts=[],estimate_note="slicer estimates; verify in your own slicer before printing")
PREV={}  # identical parts (same base name, filament, volume) shown once with xN
def _base(n): return re.sub(r'(_?[A-Z]?\d+|_[LRFB])$','',str(n))
for pp in d.get("print_parts",[]):
    fil=pp.get("material","PLA"); fil=fil if fil in PR["filaments"] else "PLA"
    m=trimesh.load(os.path.join(V,pp["stl"])); m.merge_vertices()
    if U=="in": m.apply_scale(25.4)
    m=rot(m,pp.get("orient",[0,0,0])); c=checks(m,fil); bx,by,bz=prn["bed"]
    fits=all(e<=l-8 for e,l in zip(sorted(m.extents[:2],reverse=True),sorted([bx,by],reverse=True))) and m.extents[2]<=bz
    pieces,seams=([m],[]) if fits else split(m,bx,by,bz)
    rec=dict(name=pp["name"],filament=fil,size_mm=[round(float(v),1) for v in m.extents],fits_bed=bool(fits),checks=c,seams=seams,pieces=[])
    for i,pc in enumerate(pieces):
        nm=pp["name"]+(f"_part{i+1}of{len(pieces)}" if len(pieces)>1 else ""); pc.apply_translation(-pc.bounds[0]); stl=f"{O}/{nm}.stl"; pc.export(stl)
        info=slice_(stl,f"{O}/{nm}",fil,c["needs_supports"],pp.get("infill",20)); rec["pieces"].append(dict(name=nm,stl=os.path.basename(stl),**info))
    res["parts"].append(rec)
    k=(_base(pp["name"]),fil,int(round(float(m.volume)/50)))
    if k in PREV: PREV[k][1]+=1
    else: PREV[k]=[(pp["name"],fil,m,len(pieces)),1]
items=list(PREV.values()); n=max(1,len(items)); nc=min(4,n); nr=math.ceil(n/nc)
fig=plt.figure(figsize=(4.2*nc,4.0*nr+0.6))
fig.suptitle(f"3D PRINT PARTS - {sum(c for _,c in items)} prints, {len(items)} unique  (printer: {prn['label']})",fontsize=13,weight="bold")
for i,((nm,fil,m,npc),cnt) in enumerate(items):
    ax_=fig.add_subplot(nr,nc,i+1,projection="3d")
    ax_.plot_trisurf(m.vertices[:,0],m.vertices[:,1],m.faces,m.vertices[:,2],color="#d9822b",lw=0.1,edgecolor="#7a4510")
    ax_.set_box_aspect(np.array([max(e,1e-3) for e in m.extents],dtype=float)); ax_.set_axis_off()
    lbl=(_base(nm) if cnt>1 else nm)+(f"  x{cnt}" if cnt>1 else "")
    sub=f"{fil}, {m.extents[0]:.0f}x{m.extents[1]:.0f}x{m.extents[2]:.0f} mm"+(f", split in {npc}" if npc>1 else "")
    ax_.set_title(f"{lbl}\n{sub}",fontsize=11,weight="bold" if cnt>1 else "normal")
fig.tight_layout(rect=(0,0,1,0.96)); fig.savefig(f"{O}/print_preview.png",dpi=80); plt.close(fig)
json.dump(res,open(f"{O}/print.json","w"),indent=1,default=float)
L=[f"3D PRINT REPORT - {prn['label']} ({prn['bed'][0]}x{prn['bed'][1]}x{prn['bed'][2]} mm). Estimates: verify in your slicer.",""]
for r in res["parts"]:
    c=r["checks"]; L.append(f'{r["name"]}: {r["size_mm"]} mm, {r["filament"]}, '+("fits the bed" if r["fits_bed"] else f'SPLIT into {len(r["pieces"])} pieces'))
    L.append(f'  manifold/watertight: {"OK" if c["manifold"] and c["watertight"] else "PROBLEM - repair mesh"}; overhangs needing support: {c["overhang_mm2"]} mm2 -> {"supports ON" if c["needs_supports"] else "no supports"}')
    if c.get("bodies",1)>1: L.append(f'  WARNING: {c["bodies"]} separate shells in one part -> pieces are NOT joined (floating island / loose piece); fix the model unless it is meant to print as separate pieces')
    L.append(f'  thinnest wall ~{c["min_wall_mm"]} mm; {c["thin_pct"]}% of surface under {rules["min_wall_mm"]} mm'+(" -> THICKEN" if c["thin_walls"] else " OK"))
    for s in r["seams"]: L.append(f'  seam at {s["axis"]}={s["at_mm"]} mm: '+(f'{s["pins"]} alignment pins {s["pin"]} + CA glue' if s["pins"] else s["pin"]))
    for p in r["pieces"]: L.append(f'  {p["name"]}: {p.get("time")}  {p.get("grams")} g  ~${p.get("cost")}  gcode+3mf: {p.get("3mf")} {p.get("slicer_error","")}')
open(f"{O}/print_report.txt","w").write("\n".join(L)+"\n"); print("\n".join(L))

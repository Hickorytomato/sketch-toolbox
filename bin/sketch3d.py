#!/usr/bin/env python3
"""sketch3d.py MODEL.glb OUT.png [--size 360] [--title "text"]
STAGE 1 fast 3D sketch: Blender WORKBENCH (no path tracing) renders 4 angles (front 3/4, back 3/4, side, top)
of the model into ONE labelled 2x2 PNG in a few seconds. Rough clay/material colors, cavity + outline shading.
Falls back to a trimesh/matplotlib shaded view if Blender is unavailable."""
import sys,os,subprocess,math
HERE=os.path.dirname(os.path.abspath(__file__)); BL=os.path.join(HERE,"..","tools","blender","blender")
try: import bpy
except ImportError: bpy=None
def args(a):
    o=dict(size=360,title="",units=""); pos=[]; i=0
    while i<len(a):
        if a[i].startswith("--"): o[a[i][2:]]=a[i+1]; i+=2
        else: pos.append(a[i]); i+=1
    o["model"],o["out"]=pos[:2]; o["size"]=int(o["size"]); return o
COL={"raw_steel":(.55,.56,.58),"black_paint":(.28,.29,.31),"rust":(.55,.25,.1),"cedar":(.6,.35,.18),"concrete":(.6,.6,.58),"glow":(1,.45,.1),"fire":(1,.5,.1),
     "charcoal":(.1,.08,.07),"soil":(.25,.17,.1),"dark":(.15,.15,.16),"mesh_screen":(.2,.2,.2),"hdpe":(.88,.9,.92),"leather":(.4,.22,.12),"mannequin":(.8,.78,.74),
     "petg":(.1,.5,.58),"petg_teal":(.06,.5,.56),"petg_orange":(.95,.45,.1),"petg_black":(.26,.27,.29),"petg_white":(.9,.9,.87),"petg_yellow":(.95,.75,.1),
     "petg_blue":(.1,.25,.7),"petg_grey":(.45,.46,.47),"petg_red":(.8,.12,.1),"petg_green":(.2,.55,.2),"plywood":(.85,.7,.5),"wood":(.8,.62,.4),"pine":(.88,.74,.52)}
VIEWS=[("front 3/4",-35,22),("back 3/4",145,22),("side",-90,8),("top",-20,80)]
if bpy is None:
    o=args(sys.argv[1:]); d=os.path.dirname(os.path.abspath(o["out"])); os.makedirs(d,exist_ok=True)
    tiles=[os.path.join(d,f"_sk{i}.png") for i in range(4)]
    ok=False
    if os.path.exists(BL) and not os.environ.get("SKETCH_NO_BLENDER"):
        r=subprocess.run([BL,"-b","--factory-startup","-P",os.path.abspath(__file__),"--"]+sys.argv[1:],capture_output=True,text=True,timeout=300)
        ok=all(os.path.exists(t) for t in tiles)
        if not ok: sys.stderr.write(r.stdout[-1500:]+r.stderr[-1500:])
    from PIL import Image,ImageDraw
    S=o["size"]
    if not ok:   # fallback (no Blender yet, e.g. while the heavy tools install): per-part colour, key+fill light, 2x supersampled
        import trimesh,numpy as np,matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        sc_=trimesh.load(o["model"]); parts=[]
        if hasattr(sc_,"graph"):
            for node in sc_.graph.nodes_geometry:
                T_,gn=sc_.graph[node]; g=sc_.geometry[gn].copy(); g.apply_transform(T_); parts.append((gn,g))
        else: parts=[("part",sc_)]
        allv=np.vstack([g.vertices for _,g in parts]); ctr=(allv.min(0)+allv.max(0))/2; r=np.abs(allv-ctr).max()
        budget=max(2000,30000//max(1,len(parts)))
        K=np.array([.45,-.55,.7]); K/=np.linalg.norm(K); Fl=np.array([-.6,-.2,.3]); Fl/=np.linalg.norm(Fl)
        S2=2*S
        for i,(lab,az,el) in enumerate(VIEWS):
            f=plt.figure(figsize=(S2/100,S2/100),dpi=100); ax=f.add_axes([0,0,1,1],projection="3d"); ax.set_axis_off(); ax.set_facecolor("#eceef1")
            P_=[];C_=[]
            for nm,g in parts:
                if len(g.faces)>budget:
                    try: g=g.simplify_quadric_decimation(face_count=budget)
                    except Exception: pass
                k=nm.split("__")[0].lower() if "__" in nm else ""; c=np.array(COL.get(k) or next((v for kk,v in COL.items() if k.startswith(kk)),None) or (.72,.74,.77))
                n_=g.face_normals; sh=.30+.60*np.abs(n_@K)+.15*np.abs(n_@Fl)
                P_.append(g.vertices[g.faces]-ctr); C_.append(np.clip(np.outer(sh,c),0,1))
            pc=Poly3DCollection(np.concatenate(P_),facecolors=np.concatenate(C_),edgecolor="none",antialiased=False); ax.add_collection3d(pc)
            hx=(allv.max(0)-allv.min(0))/2*1.02; ax.set_xlim(-hx[0],hx[0]); ax.set_ylim(-hx[1],hx[1]); ax.set_zlim(-hx[2],hx[2]); ax.set_box_aspect(tuple(hx)); ax.view_init(el,az-90)
            try: ax.set_proj_type("persp",focal_length=0.6)
            except Exception: pass
            f.savefig(tiles[i],facecolor="#eceef1"); plt.close(f)
    import trimesh as _tm
    try: _ex=_tm.load(o["model"]).extents; dims=f'{_ex[0]:.4g} W x {_ex[1]:.4g} D x {_ex[2]:.4g} H {o.get("units","")}'.strip()
    except Exception: dims=""
    from PIL import ImageFont
    def _f(sz):
        for fp in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf","/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
            if os.path.exists(fp): return ImageFont.truetype(fp,sz)
        return ImageFont.load_default()
    TH=40 if o["title"] else 0; DH=34 if dims else 0
    c=Image.new("RGB",(2*S+6,2*S+6+TH+DH),"white"); y0=TH; dr=ImageDraw.Draw(c)
    if o["title"]: dr.text((10,9),o["title"],fill="black",font=_f(18))
    for i,(lab,_,_) in enumerate(VIEWS):
        t=Image.open(tiles[i]).convert("RGB").resize((S,S),Image.LANCZOS); x,y=(i%2)*(S+6),y0+(i//2)*(S+6); c.paste(t,(x,y)); dr.text((x+8,y+6),lab,fill=(40,40,40),font=_f(14)); os.remove(tiles[i])
    if dims: dr.text((10,2*S+6+TH+6),"overall "+dims,fill="black",font=_f(18))
    c.save(o["out"]); print(o["out"]); sys.exit(0)

o=args(sys.argv[sys.argv.index("--")+1:]); import mathutils
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)
bpy.ops.import_scene.gltf(filepath=os.path.abspath(o["model"]))
Rx=mathutils.Matrix.Rotation(math.radians(-90),4,"X")   # trimesh Z-up -> Blender Z-up (same as render_real.py)
for ob in bpy.context.scene.objects:
    if ob.parent is None: ob.matrix_world=Rx@ob.matrix_world
bpy.context.view_layer.update()
ms=[ob for ob in bpy.context.scene.objects if ob.type=="MESH"]
for ob in ms:
    k=ob.name.split("__")[0].lower() if "__" in ob.name else ""
    c=COL.get(k) or next((v for kk,v in COL.items() if k.startswith(kk)),None) or (.72,.74,.77); ob.color=c+(1,)
pts=[ob.matrix_world@mathutils.Vector(c) for ob in ms for c in ob.bound_box]
lo=mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); hi=mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
ctr=(lo+hi)/2; rad=max((hi-lo).length/2,1e-3)
sc=bpy.context.scene; r=sc.render; r.engine="BLENDER_WORKBENCH"; r.resolution_x=r.resolution_y=o["size"]; r.film_transparent=False
sh=sc.display.shading; sh.light="STUDIO"; sh.color_type="OBJECT"; sh.show_cavity=True; sh.cavity_type="BOTH"; sh.show_object_outline=True; sh.show_shadows=True
sh.background_type="WORLD"; w=sc.world or bpy.data.worlds.new("w"); sc.world=w; w.color=(0.9,0.91,0.93); sc.display.render_aa="8"
try: sc.view_settings.view_transform="Standard"
except Exception: pass
cam=bpy.data.objects.new("cam",bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera=cam; cam.data.lens=50
fov=cam.data.angle; dist=rad/math.sin(fov/2)*1.08
d=os.path.dirname(os.path.abspath(o["out"]))
for i,(lab,az,el) in enumerate(VIEWS):
    a,e=math.radians(az),math.radians(el)
    cam.location=ctr+mathutils.Vector((dist*math.cos(e)*math.sin(a),-dist*math.cos(e)*math.cos(a),dist*math.sin(e)))
    cam.rotation_euler=(ctr-cam.location).to_track_quat("-Z","Y").to_euler()
    r.filepath=os.path.join(d,f"_sk{i}.png"); bpy.ops.render.render(write_still=True)

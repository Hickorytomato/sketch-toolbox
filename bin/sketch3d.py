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
    o=dict(size=360,title=""); pos=[]; i=0
    while i<len(a):
        if a[i].startswith("--"): o[a[i][2:]]=a[i+1]; i+=2
        else: pos.append(a[i]); i+=1
    o["model"],o["out"]=pos[:2]; o["size"]=int(o["size"]); return o
VIEWS=[("front 3/4",-35,22),("back 3/4",145,22),("side",-90,8),("top",-20,80)]
if bpy is None:
    o=args(sys.argv[1:]); d=os.path.dirname(os.path.abspath(o["out"])); os.makedirs(d,exist_ok=True)
    tiles=[os.path.join(d,f"_sk{i}.png") for i in range(4)]
    ok=False
    if os.path.exists(BL):
        r=subprocess.run([BL,"-b","--factory-startup","-P",os.path.abspath(__file__),"--"]+sys.argv[1:],capture_output=True,text=True,timeout=300)
        ok=all(os.path.exists(t) for t in tiles)
        if not ok: sys.stderr.write(r.stdout[-1500:]+r.stderr[-1500:])
    from PIL import Image,ImageDraw
    S=o["size"]
    if not ok:   # fallback: matplotlib shaded mesh
        import trimesh,numpy as np,matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        m=trimesh.load(o["model"],force="mesh")
        if len(m.faces)>20000: m=m.simplify_quadric_decimation(face_count=20000)
        v=m.vertices-m.bounds.mean(0); L=np.array([.4,-.6,.7]); L/=np.linalg.norm(L)
        sh=np.clip(m.face_normals@L,0,1)*.7+.3
        for i,(lab,az,el) in enumerate(VIEWS):
            f=plt.figure(figsize=(S/100,S/100),dpi=100); ax=f.add_subplot(projection="3d"); ax.set_axis_off()
            ax.add_collection3d(Poly3DCollection(v[m.faces],facecolors=np.c_[sh*.75,sh*.78,sh*.82],edgecolor="none"))
            r=np.abs(v).max(); ax.set_xlim(-r,r); ax.set_ylim(-r,r); ax.set_zlim(-r,r); ax.view_init(el,az-90)
            f.savefig(tiles[i],facecolor="#eef0f2"); plt.close(f)
    c=Image.new("RGB",(2*S+6,2*S+6+(30 if o["title"] else 0)),"white"); y0=30 if o["title"] else 0; dr=ImageDraw.Draw(c)
    if o["title"]: dr.text((8,9),o["title"],fill="black")
    for i,(lab,_,_) in enumerate(VIEWS):
        t=Image.open(tiles[i]).convert("RGB").resize((S,S)); x,y=(i%2)*(S+6),y0+(i//2)*(S+6); c.paste(t,(x,y)); dr.text((x+6,y+6),lab,fill="black"); os.remove(tiles[i])
    c.save(o["out"]); print(o["out"]); sys.exit(0)

o=args(sys.argv[sys.argv.index("--")+1:]); import mathutils
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)
bpy.ops.import_scene.gltf(filepath=os.path.abspath(o["model"]))
Rx=mathutils.Matrix.Rotation(math.radians(-90),4,"X")   # trimesh Z-up -> Blender Z-up (same as render_real.py)
for ob in bpy.context.scene.objects:
    if ob.parent is None: ob.matrix_world=Rx@ob.matrix_world
bpy.context.view_layer.update()
COL={"raw_steel":(.55,.56,.58),"black_paint":(.28,.29,.31),"rust":(.55,.25,.1),"cedar":(.6,.35,.18),"concrete":(.6,.6,.58),"glow":(1,.45,.1),"fire":(1,.5,.1),
     "charcoal":(.1,.08,.07),"soil":(.25,.17,.1),"dark":(.15,.15,.16),"mesh_screen":(.2,.2,.2),"hdpe":(.88,.9,.92),"leather":(.4,.22,.12),"mannequin":(.8,.78,.74),
     "petg":(.1,.5,.58),"petg_teal":(.06,.5,.56),"petg_orange":(.95,.45,.1),"petg_black":(.26,.27,.29),"petg_white":(.9,.9,.87),"petg_yellow":(.95,.75,.1),
     "petg_blue":(.1,.25,.7),"petg_grey":(.45,.46,.47),"petg_red":(.8,.12,.1),"petg_green":(.2,.55,.2),"plywood":(.85,.7,.5),"wood":(.8,.62,.4),"pine":(.88,.74,.52)}
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

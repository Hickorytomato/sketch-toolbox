#!/usr/bin/env python3
"""explode.py VDIR [--size 720]  -> VDIR/explode/NN.png (one per assembly step) + explode.json   (v1.0.5 feature 6)
Blender WORKBENCH (fast, no path tracing) step-by-step exploded views from the model: parts already fitted are grey,
this step's parts are highlighted and pulled out along their direction from the assembly, with a dashed line back to
where they go and their BOM tag (A1, B2 ... same as the BOM, cut day and hand plan). Last image = everything assembled + tags.
Steps come from steps.json (spec 'steps' or the build order). Typical time: Blender start ~2-4 s + ~0.5-1.5 s per step at 720 px."""
import sys,os,json,math,subprocess,time
HERE=os.path.dirname(os.path.abspath(__file__)); BL=os.path.join(HERE,"..","tools","blender","blender")
try: import bpy
except ImportError: bpy=None
if bpy is None:
    a=sys.argv[1:]; V=os.path.abspath(a[0]); size=int(a[a.index("--size")+1]) if "--size" in a else 720
    OD=f"{V}/explode"; os.makedirs(OD,exist_ok=True)
    for f in os.listdir(OD): os.remove(os.path.join(OD,f))
    sys.path.insert(0,HERE); import rules
    d=json.load(open(f"{V}/parts.json")); TAG=rules.part_tags(d)
    t0=time.time()
    env=dict(os.environ,SKETCH_STEPS=f"{V}/steps.json",EXPLODE_TAGS=json.dumps(TAG))
    r=subprocess.run([BL,"-b","--factory-startup","-P",os.path.abspath(__file__),"--",V,str(size)],capture_output=True,text=True,timeout=600,env=env)
    J=f"{OD}/explode.json"
    if not os.path.exists(J): sys.stderr.write(r.stdout[-2000:]+r.stderr[-2000:]); print("explode: Blender render failed"); sys.exit(1)
    E=json.load(open(J))
    from PIL import Image,ImageDraw,ImageFont
    try: FT=ImageFont.truetype("DejaVuSans-Bold.ttf",max(14,size//34)); FS=ImageFont.truetype("DejaVuSans.ttf",max(12,size//48))
    except Exception: FT=FS=ImageFont.load_default()
    for st in E["steps"]:
        im=Image.open(st["png"]).convert("RGB"); W,H=im.size; dr=ImageDraw.Draw(im)
        for lb in st["labels"]:
            (x0,y0),(x1,y1)=[(p[0]*W,(1-p[1])*H) for p in (lb["from"],lb["to"])]
            if lb["moved"]:   # dashed line from the exploded part back to its place
                n=max(int(math.hypot(x1-x0,y1-y0)/9),1)
                for i in range(0,n,2): dr.line([(x0+(x1-x0)*i/n,y0+(y1-y0)*i/n),(x0+(x1-x0)*min(i+1,n)/n,y0+(y1-y0)*min(i+1,n)/n)],fill=(200,40,30),width=2)
            t=lb["tag"]; bb=dr.textbbox((0,0),t,font=FT); w_,h_=bb[2]-bb[0]+10,bb[3]-bb[1]+8
            dr.ellipse([x0-w_/2,y0-h_/2,x0+w_/2,y0+h_/2],fill=(255,255,255) if not lb["moved"] else (255,236,150),outline=(30,30,30),width=2); dr.text((x0-w_/2+5,y0-h_/2+2),t,fill=(0,0,0),font=FT)
        hdr=f'Step {st["n"]} of {len(E["steps"])}: {st["caption"]}'; dr.rectangle([0,0,W,int(size/16)],fill=(255,255,255)); dr.text((10,6),hdr,fill=(0,0,0),font=FT)
        if st["tags"]: dr.text((10,H-int(size/22)),"this step: "+", ".join(st["tags"])[:90],fill=(40,40,40),font=FS)
        im.save(st["png"])
    E["seconds"]=round(time.time()-t0,1); E["size"]=size; json.dump(E,open(J,"w"),indent=1)
    print(f'explode -> {OD}: {len(E["steps"])} step image(s) in {E["seconds"]} s ({size} px, Blender workbench)'); sys.exit(0)
# ------------------------------------------------------------------ inside Blender
import mathutils
argv=sys.argv[sys.argv.index("--")+1:]; V,size=argv[0],int(argv[1]); OD=f"{V}/explode"
sys.path.insert(0,HERE); import steps
TAG=json.loads(os.environ.get("EXPLODE_TAGS","{}"))
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)
bpy.ops.import_scene.gltf(filepath=f"{V}/model.glb")
Rx=mathutils.Matrix.Rotation(math.radians(-90),4,"X")
for ob in bpy.context.scene.objects:
    if ob.parent is None: ob.matrix_world=Rx@ob.matrix_world
bpy.context.view_layer.update()
ms=[ob for ob in bpy.context.scene.objects if ob.type=="MESH"]
def bbox(objs):
    pts=[ob.matrix_world@mathutils.Vector(c) for ob in objs for c in ob.bound_box]
    lo=mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); hi=mathutils.Vector([max(p[i] for p in pts) for i in range(3)]); return lo,hi
lo,hi=bbox(ms); ctr=(lo+hi)/2; rad=max((hi-lo).length/2,1e-3)
def pname(ob): return ob.name.split("__",1)[-1].split(".")[0]
def tag_of(n):
    if n in TAG: return TAG[n]
    best=max((k for k in TAG if n.startswith(k)),key=len,default=None); return TAG.get(best,"")
sc=bpy.context.scene; r=sc.render; r.engine="BLENDER_WORKBENCH"; r.resolution_x=r.resolution_y=size
sh=sc.display.shading; sh.light="STUDIO"; sh.color_type="OBJECT"; sh.show_cavity=True; sh.cavity_type="BOTH"; sh.show_object_outline=True; sh.show_shadows=False
w=sc.world or bpy.data.worlds.new("w"); sc.world=w; w.color=(0.95,0.95,0.96); sc.display.render_aa="8"
try: sc.view_settings.view_transform="Standard"
except Exception: pass
cam=bpy.data.objects.new("cam",bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera=cam; cam.data.lens=50
R=rad*1.6; fov=cam.data.angle; dist=R/math.sin(fov/2)
a,e=math.radians(-35),math.radians(24)
cam.location=ctr+mathutils.Vector((dist*math.cos(e)*math.sin(a),-dist*math.cos(e)*math.cos(a),dist*math.sin(e)))
cam.rotation_euler=(ctr-cam.location).to_track_quat("-Z","Y").to_euler(); bpy.context.view_layer.update()
from bpy_extras.object_utils import world_to_camera_view as w2c
home={ob.name:ob.matrix_world.copy() for ob in ms}
names=[ob.name for ob in ms]; G=steps.groups(names); byn={ob.name:ob for ob in ms}
if not G: G=[("Assembling the parts",names)]
out=[]; done=[]
def center(ob): lo_,hi_=bbox([ob]); return (lo_+hi_)/2
for k,(cap,ns) in enumerate(G+[("Finished: everything assembled",[])]):
    final=not ns
    for ob in ms: ob.matrix_world=home[ob.name]; ob.hide_render=not (ob.name in done or ob.name in ns or final)
    for ob in ms: ob.color=(0.74,0.75,0.77,1) if ob.name in done or final else (0.98,0.62,0.18,1)
    ref=[byn[n] for n in done] or [byn[n] for n in names]; rlo,rhi=bbox(ref); rc=(rlo+rhi)/2
    labels=[]
    for n in ns:
        ob=byn[n]; c=center(ob); v=c-rc
        if v.length<rad*0.05: v=mathutils.Vector((0,0,1))
        v.normalize(); olo,ohi=bbox([ob]); D=[byn[x] for x in done]
        def clear(off):
            for q in D:
                qlo,qhi=bbox([q])
                if all(olo[i]+off[i]<qhi[i]-1e-6 and qlo[i]<ohi[i]+off[i]-1e-6 for i in range(3)): return False
            return True
        cands=[v,mathutils.Vector((0,0,1)),mathutils.Vector((0,-1,0)),mathutils.Vector((-1,0,0)),mathutils.Vector((1,0,0)),mathutils.Vector((0,1,0))]
        off=next((c_*rad*0.55 for c_ in cands if clear(c_*rad*0.55)),v*rad*0.55)
        ob.matrix_world=mathutils.Matrix.Translation(off)@home[n]
        p0=w2c(sc,cam,c+off); p1=w2c(sc,cam,c); labels.append(dict(part=pname(ob),tag=tag_of(pname(ob)),moved=True,**{"from":[p0.x,p0.y],"to":[p1.x,p1.y]}))
    if final:
        for ob in ms:
            p=w2c(sc,cam,center(ob)); labels.append(dict(part=pname(ob),tag=tag_of(pname(ob)),moved=False,**{"from":[p.x,p.y],"to":[p.x,p.y]}))
    bpy.context.view_layer.update()
    f=os.path.join(OD,f"{k+1:02d}.png"); r.filepath=f; bpy.ops.render.render(write_still=True)
    out.append(dict(n=k+1,caption=cap,png=f,parts=[pname(byn[n]) for n in ns],tags=sorted({l["tag"] for l in labels if l["moved"] and l["tag"]}),labels=labels))
    done+=ns
json.dump(dict(steps=out),open(os.path.join(OD,"explode.json"),"w"),indent=1)

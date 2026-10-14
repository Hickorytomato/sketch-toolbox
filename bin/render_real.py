#!/usr/bin/env python3
"""render_real.py MODEL.glb OUTDIR [--fill 0.7 = subject fills 70% of frame (auto-framing; props named mannequin__/dark__ are ignored when framing unless --framewith all)] [--el 24] [--cutout = transparent hero_cutout.png with real shadow, for from_photo.py] [--look studio|dusk] [--finish raw_steel|black_paint|rust|cedar|concrete] [--size 540] [--frames 72] [--samples 12] [--nospin]
Photoreal Blender/Cycles render. Object names 'preset__name' pick materials (raw_steel, black_paint, rust, cedar, concrete, glow, fire, charcoal, soil, dark, mesh_screen).
--finish swaps the main finish (any metal/wood preset) for another. Outputs OUTDIR/hero.png and OUTDIR/spin.mp4 (<6 MB).
Falls back to turntable.py (clay look) if Blender fails."""
import sys,os,subprocess,shutil
HERE=os.path.dirname(os.path.abspath(__file__)); BL=os.path.join(HERE,"..","tools","blender","blender")
try: import bpy
except ImportError: bpy=None
def args(a):
    o=dict(look="studio",finish=None,size=540,frames=96,samples=12,nospin=False,cutout=False,replay=False,spinonly=False); pos=[]; i=0
    while i<len(a):
        if a[i] in("--nospin","--cutout","--replay","--spinonly"): o[a[i][2:]]=True; i+=1
        elif a[i].startswith("--"): o[a[i][2:]]=a[i+1]; i+=2
        else: pos.append(a[i]); i+=1
    o["model"],o["out"]=pos[:2]; o["size"],o["frames"],o["samples"]=int(o["size"]),int(o["frames"]),int(o["samples"]); return o

def encode(o):
    out=os.path.join(o["out"],"spin.mp4"); fr=os.path.join(o["out"],"_frames","%04d.png")
    n=len([f for f in os.listdir(os.path.dirname(fr)) if f.endswith(".png")]); lap=float(o.get("lap",7))  # seconds per lap; video = 2 laps
    vf=f"loop=1:{n}:0,minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:vsbmc=1"
    for crf in (20,24,28,32):
        subprocess.run(["ffmpeg","-y","-loglevel","error","-framerate",f"{n/lap:.4f}","-i",fr,"-vf",vf,"-c:v","libx264","-crf",str(crf),"-pix_fmt","yuv420p","-movflags","+faststart",out],check=True)
        if os.path.getsize(out)<6e6: break
    shutil.rmtree(os.path.join(o["out"],"_frames")); return out

if bpy is None:
    o=args(sys.argv[1:]); os.makedirs(o["out"],exist_ok=True)
    hp=os.path.join(o["out"],"hero_cutout.png" if o["cutout"] else "hero.png")
    if os.path.exists(hp) and not o["spinonly"]: os.remove(hp)
    try:
        r=subprocess.run([BL,"-b","--factory-startup","-P",os.path.abspath(__file__),"--"]+sys.argv[1:],capture_output=True,text=True,timeout=3600)
        if o["spinonly"]:
            if r.returncode or not os.path.isdir(os.path.join(o["out"],"_frames")): raise RuntimeError(r.stderr[-1500:])
            print(encode(o)); sys.exit(0)
        if not os.path.exists(hp): raise RuntimeError(r.stdout[-1500:]+r.stderr[-1500:])
        if not (o["nospin"] or o["cutout"]): print(encode(o))
        print(hp)
    except Exception as e:
        print("BLENDER FAILED, falling back to clay turntable:",str(e)[-500:],file=sys.stderr)
        py=os.path.join(HERE,"..",".venv","bin","python")
        subprocess.run([py,os.path.join(HERE,"turntable.py"),o["model"],os.path.join(o["out"],"spin.mp4")],check=True)
        shutil.copy(os.path.join(o["out"],"spin_frame.png"),os.path.join(o["out"],"hero.png")); print("fallback:",o["out"])
    sys.exit(0)

# ---------------- inside Blender ----------------
import math,mathutils
o=args(sys.argv[sys.argv.index("--")+1:])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.abspath(o["model"]))
objs=[ob for ob in bpy.context.scene.objects if ob.type=="MESH"]
Rx=mathutils.Matrix.Rotation(math.radians(-90),4,"X")   # trimesh Z-up -> Blender Z-up
for ob in bpy.context.scene.objects:
    if ob.parent is None: ob.matrix_world=Rx@ob.matrix_world
bpy.context.view_layer.update()
pts=[ob.matrix_world@mathutils.Vector(c) for ob in objs for c in ob.bound_box]
mn=mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx=mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
size=max(mx-mn); s=2.0/size; ctr=(mn+mx)/2
pivot=bpy.data.objects.new("pivot",None); bpy.context.scene.collection.objects.link(pivot)
for ob in bpy.context.scene.objects:
    if ob.parent is None and ob!=pivot:
        ob.matrix_world=mathutils.Matrix.Scale(s,4)@mathutils.Matrix.Translation((-ctr.x,-ctr.y,-mn.z))@ob.matrix_world; ob.parent=pivot
H=(mx.z-mn.z)*s

def mat(name):
    m=bpy.data.materials.new(name); m.use_nodes=True; nt=m.node_tree; b=nt.nodes["Principled BSDF"]; N=nt.nodes.new; L=nt.links.new
    def noise(scale,c1,c2,detail=8):
        tc=N("ShaderNodeTexCoord"); nz=N("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value=scale; nz.inputs["Detail"].default_value=detail
        L(tc.outputs["Object"],nz.inputs["Vector"]); cr=N("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color=c1+(1,); cr.color_ramp.elements[1].color=c2+(1,)
        L(nz.outputs["Fac"],cr.inputs["Fac"]); return cr
    bi=b.inputs; key=name
    if key=="raw_steel":
        L(noise(0.6,(0.30,0.30,0.32),(0.55,0.55,0.57)).outputs["Color"],bi["Base Color"]); bi["Metallic"].default_value=1; bi["Roughness"].default_value=0.42
    elif key=="black_paint":
        bi["Base Color"].default_value=(0.02,0.02,0.022,1); bi["Metallic"].default_value=0.2; bi["Roughness"].default_value=0.65
    elif key=="rust":
        cr=noise(0.4,(0.22,0.07,0.02),(0.58,0.24,0.07)); cr.color_ramp.elements.new(0.8).color=(0.12,0.05,0.03,1)
        L(cr.outputs["Color"],bi["Base Color"]); bi["Metallic"].default_value=0.15; bi["Roughness"].default_value=0.9
    elif key=="cedar":
        tc=N("ShaderNodeTexCoord"); w=N("ShaderNodeTexWave"); w.inputs["Scale"].default_value=0.35; w.wave_type="BANDS"; w.bands_direction="Y"; w.inputs["Distortion"].default_value=2.5; w.inputs["Detail Scale"].default_value=1.5; w.inputs["Detail"].default_value=4
        L(tc.outputs["Object"],w.inputs["Vector"]); cr=N("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color=(0.36,0.15,0.06,1); cr.color_ramp.elements[1].color=(0.52,0.25,0.11,1)
        L(w.outputs["Fac"],cr.inputs["Fac"]); L(cr.outputs["Color"],bi["Base Color"]); bi["Roughness"].default_value=0.6
    elif key=="concrete":
        L(noise(1.5,(0.33,0.33,0.32),(0.55,0.54,0.52)).outputs["Color"],bi["Base Color"]); bi["Roughness"].default_value=0.92
    elif key in("glow","fire"):
        em=N("ShaderNodeEmission"); em.inputs["Color"].default_value=(1,0.35,0.05,1) if key=="glow" else (1,0.5,0.1,1); em.inputs["Strength"].default_value=25 if key=="glow" else 12
        out=nt.nodes["Material Output"]
        if key=="fire":
            tr=N("ShaderNodeBsdfTransparent"); mx_=N("ShaderNodeMixShader"); lw=N("ShaderNodeLayerWeight"); lw.inputs[0].default_value=0.6
            L(lw.outputs["Facing"],mx_.inputs[0]); L(em.outputs[0],mx_.inputs[1]); L(tr.outputs[0],mx_.inputs[2]); L(mx_.outputs[0],out.inputs["Surface"])
        else: L(em.outputs[0],out.inputs["Surface"])
    elif key=="charcoal": bi["Base Color"].default_value=(0.04,0.03,0.025,1); bi["Roughness"].default_value=1; bi["Emission Color"].default_value=(1,0.2,0.02,1); bi["Emission Strength"].default_value=1.5
    elif key=="soil": L(noise(2,(0.05,0.03,0.02),(0.13,0.08,0.05)).outputs["Color"],bi["Base Color"]); bi["Roughness"].default_value=1
    elif key=="mesh_screen":
        bi["Base Color"].default_value=(0.06,0.06,0.06,1); bi["Metallic"].default_value=0.8; bi["Roughness"].default_value=0.5
    elif key=="ground_studio": bi["Base Color"].default_value=(0.35,0.35,0.36,1); bi["Roughness"].default_value=0.5
    elif key=="ground_dusk": L(noise(0.3,(0.04,0.06,0.025),(0.12,0.13,0.06)).outputs["Color"],bi["Base Color"]); bi["Roughness"].default_value=1
    elif key.startswith("petg"):   # printed PETG: slight gloss, faint layer lines
        PC={"petg":(0.05,0.30,0.36),"petg_teal":(0.03,0.32,0.36),"petg_orange":(0.85,0.25,0.03),"petg_black":(0.018,0.018,0.02),"petg_white":(0.75,0.75,0.72),
            "petg_yellow":(0.85,0.55,0.02),"petg_blue":(0.03,0.12,0.45),"petg_grey":(0.25,0.26,0.27),"petg_red":(0.6,0.04,0.03),"petg_green":(0.08,0.35,0.08)}
        c=PC.get(key,PC["petg"]); tc=N("ShaderNodeTexCoord"); w=N("ShaderNodeTexWave"); w.wave_type="BANDS"; w.bands_direction="Y"; w.inputs["Scale"].default_value=1.6
        L(tc.outputs["Object"],w.inputs["Vector"]); bump=N("ShaderNodeBump"); bump.inputs["Strength"].default_value=0.08; L(w.outputs["Fac"],bump.inputs["Height"]); L(bump.outputs["Normal"],bi["Normal"])
        bi["Base Color"].default_value=c+(1,); bi["Roughness"].default_value=0.26 if key!="petg_black" else 0.55; _set(bi,"Coat Weight",0.25 if key!="petg_black" else 0.05); _set(bi,"Coat Roughness",0.15); _set(bi,"Subsurface Weight",0.04)
    elif key=="hdpe":   # translucent milky bottle
        bi["Base Color"].default_value=(0.86,0.88,0.9,1); bi["Roughness"].default_value=0.32; _set(bi,"Transmission Weight",0.82); _set(bi,"IOR",1.5); bi["Alpha"].default_value=1
    elif key.startswith("liquid"):
        c={"liquid_blue":(0.15,0.45,0.9),"liquid_green":(0.2,0.75,0.3),"liquid_pink":(0.9,0.3,0.5)}.get(key,(0.15,0.45,0.9))
        bi["Base Color"].default_value=c+(1,); bi["Roughness"].default_value=0.05; _set(bi,"Transmission Weight",0.9); _set(bi,"IOR",1.33)
    elif key=="sprayer_white": bi["Base Color"].default_value=(0.8,0.8,0.78,1); bi["Roughness"].default_value=0.35
    elif key=="sprayer_dark": bi["Base Color"].default_value=(0.03,0.03,0.035,1); bi["Roughness"].default_value=0.4
    elif key=="rubber": bi["Base Color"].default_value=(0.6,0.6,0.6,1); bi["Roughness"].default_value=0.5; _set(bi,"Transmission Weight",0.5)
    elif key=="leather":
        L(noise(0.15,(0.09,0.045,0.02),(0.16,0.08,0.035)).outputs["Color"],bi["Base Color"]); bi["Roughness"].default_value=0.55
    elif key=="leather_stitch": bi["Base Color"].default_value=(0.55,0.42,0.25,1); bi["Roughness"].default_value=0.8
    elif key=="plastic":   # printed filament: satin dielectric, slight subsurface, not metal
        bi["Base Color"].default_value=(0.85,0.32,0.06,1); bi["Metallic"].default_value=0.0; bi["Roughness"].default_value=0.38
        _set(bi,"Subsurface Weight",0.08); _set(bi,"Specular IOR Level",0.5)
    elif key=="mannequin": bi["Base Color"].default_value=(0.30,0.29,0.28,1); bi["Roughness"].default_value=0.55; _set(bi,"Coat Weight",0.1)
    else: bi["Base Color"].default_value=(0.05,0.05,0.05,1)
    return m
def _set(bi,k,v):
    try: bi[k].default_value=v
    except Exception: pass
sc0=bpy.context.scene
FIN={"raw_steel","black_paint","rust","cedar","concrete","plastic"}; cache={}
for ob in objs:
    k=ob.name.split("__")[0]
    if o["finish"] and k in FIN: k=o["finish"]
    if k not in cache: cache[k]=mat(k)
    ob.data.materials.clear(); ob.data.materials.append(cache[k])
    for poly in ob.data.polygons: poly.use_smooth=True
    if k=="mesh_screen":
        wf=ob.modifiers.new("wf","WIREFRAME"); wf.thickness=0.25; wf.use_replace=True
    try: ob.data.set_sharp_from_angle(angle=math.radians(35))
    except Exception: pass
    if k=="fire" and not any(x.name=="fireglow" for x in sc0.objects):
        pl=bpy.data.lights.new("fireglow","POINT"); pl.energy=400 if o["look"]=="dusk" else 120; pl.color=(1,0.45,0.12); pl.shadow_soft_size=0.3
        po=bpy.data.objects.new("fireglow",pl); sc0.collection.objects.link(po); po.location=(0,0,H*0.75); po.parent=pivot

sc=bpy.context.scene; w=bpy.data.worlds.new("w"); sc.world=w; w.use_nodes=True; bg=w.node_tree.nodes["Background"]
bpy.ops.mesh.primitive_plane_add(size=60); g=bpy.context.active_object; g.data.materials.append(mat("ground_"+("dusk" if o["look"]=="dusk" else "studio")))
def area(loc,energy,size,color=(1,1,1)):
    l=bpy.data.lights.new("a","AREA"); l.energy=energy; l.size=size; l.color=color; ob=bpy.data.objects.new("a",l); sc.collection.objects.link(ob); ob.location=loc
    c=ob.constraints.new("TRACK_TO"); c.target=pivot; return ob
if o["look"]=="dusk":
    sky=w.node_tree.nodes.new("ShaderNodeTexSky"); sky.sky_type="NISHITA"; sky.sun_elevation=math.radians(4); sky.sun_rotation=math.radians(200); sky.sun_disc=False
    w.node_tree.links.new(sky.outputs[0],bg.inputs[0]); bg.inputs[1].default_value=0.18
    sun=bpy.data.lights.new("sun","SUN"); sun.energy=1.6; sun.color=(1,0.6,0.35); sun.angle=0.05; so=bpy.data.objects.new("sun",sun); sc.collection.objects.link(so)
    so.rotation_euler=(math.radians(84),0,math.radians(200)); area((-3,-3,2.5),120,3,(0.6,0.7,1))
else:
    bg.inputs[0].default_value=(0.8,0.82,0.85,1); bg.inputs[1].default_value=0.2
    area((3,-3,4),450,3); area((-4,-2,2),120,4,(0.85,0.9,1)); area((0,4,3),300,2)
cam=bpy.data.cameras.new("c"); cam.lens=50; co=bpy.data.objects.new("c",cam); sc.collection.objects.link(co); sc.camera=co
tgt=bpy.data.objects.new("t",None); sc.collection.objects.link(tgt); tgt.location=(0,0,H*0.42)
d=3.9; el=math.radians(float(o.get("el",24))); co.location=(0,-d*math.cos(el),H*0.42+d*math.sin(el)); co.constraints.new("TRACK_TO").target=tgt
FILL=float(o.get("fill",0.7)); fillobjs=[ob for ob in objs if not ob.name.split("__")[0] in ("mannequin","dark") or o.get("framewith")=="all"] or objs
def autoframe(angles):
    """move camera along its view ray so the subject's projected bbox fills FILL of the frame at every angle listed"""
    from bpy_extras.object_utils import world_to_camera_view
    global d
    vw=bpy.context.view_layer; r_=sc.render; r_.resolution_x=r_.resolution_y=o["size"]
    pts0=[(ob,[mathutils.Vector(c) for c in ob.bound_box]) for ob in fillobjs]
    for it in range(4):
        cx=[];cy=[];zc=[]
        for a in angles:
            pivot.rotation_euler=(0,0,a); vw.update()
            for ob,bb in pts0:
                for c in bb:
                    p=world_to_camera_view(sc,co,ob.matrix_world@c); cx.append(p.x); cy.append(p.y)
        ext=max(max(cx)-min(cx),max(cy)-min(cy)); midy=(max(cy)+min(cy))/2
        tgt.location.z+= (midy-0.5)*2*d*math.tan(cam.angle/2)*0.9
        d*=ext/FILL; co.location=(0,-d*math.cos(el),tgt.location.z+d*math.sin(el)); vw.update()
    pivot.rotation_euler=(0,0,0)
sc.render.resolution_x=sc.render.resolution_y=o["size"]
r=sc.render; r.engine="CYCLES"; sc.cycles.device="CPU"; sc.cycles.samples=o["samples"]; sc.cycles.use_denoising=True
sc.cycles.max_bounces=6; sc.cycles.transparent_max_bounces=8; r.resolution_x=r.resolution_y=o["size"]; r.film_transparent=False
sc.view_settings.view_transform="AgX"; sc.view_settings.look="AgX - Medium High Contrast"
r.image_settings.file_format="PNG"
r.use_persistent_data=True; sc.cycles.use_adaptive_sampling=True; sc.cycles.adaptive_threshold=0.05
sc.cycles.denoiser="OPENIMAGEDENOISE"
if o["replay"]:   # build replay: stills per assembly step (clay), finish, final light, then orbit frames
    import json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import steps
    rd=os.path.join(os.path.abspath(o["out"]),"_replay"); os.makedirs(rd,exist_ok=True)
    names=[ob.name for ob in objs]; byname={ob.name:ob for ob in objs}
    clay=bpy.data.materials.new("clay"); clay.use_nodes=True; cb=clay.node_tree.nodes["Principled BSDF"].inputs; cb["Base Color"].default_value=(0.55,0.56,0.58,1); cb["Roughness"].default_value=0.7
    orig={ob.name:ob.data.materials[0] for ob in objs}
    glow=[x for x in sc.objects if x.name=="fireglow"]
    for ob in objs: ob.hide_render=True; ob.data.materials[0]=clay
    for x in glow: x.hide_render=True
    sc.cycles.samples=o["samples"]; r.resolution_x=r.resolution_y=o["size"]; pivot.rotation_euler=(0,0,math.radians(-35))
    log=[]; k=0
    def shot(cap):
        global k
        f=os.path.join(rd,f"step{k:02d}.png"); r.filepath=f; bpy.ops.render.render(write_still=True); log.append([cap,f]); k+=1
    for cap,ns in steps.groups(names):
        for n in ns: byname[n].hide_render=False
        shot(cap)
    for ob in objs:
        if not steps.caption(ob.name) is None: ob.data.materials[0]=orig[ob.name]
    shot("Applying the finish")
    fs=steps.fire(names)
    for n in fs: byname[n].hide_render=False; byname[n].data.materials[0]=orig[n]
    for x in glow: x.hide_render=False
    if fs: shot("Lighting the fire")
    od=os.path.join(rd,"orbit"); os.makedirs(od,exist_ok=True); N=int(o.get("orbit",60))
    for i in range(N):
        pivot.rotation_euler=(0,0,math.radians(-35)+2*math.pi*i/N); r.filepath=os.path.join(od,f"{i:04d}.png"); bpy.ops.render.render(write_still=True)
    json.dump({"steps":log,"orbit":od,"n":N},open(os.path.join(rd,"steps.json"),"w")); raise SystemExit
# hero: more samples, larger, 3/4 angle
autoframe([math.radians(-35)])
pivot.rotation_euler=(0,0,math.radians(-35)); sc.cycles.samples=int(o.get("herosamples",max(32,o["samples"]*4))); r.resolution_x=r.resolution_y=int(o["size"]*1.5)
if o["cutout"]:
    g.is_shadow_catcher=True; r.film_transparent=True; r.image_settings.color_mode="RGBA"
    r.filepath=os.path.join(os.path.abspath(o["out"]),"hero_cutout.png"); bpy.ops.render.render(write_still=True); raise SystemExit
if not o["spinonly"]: r.filepath=os.path.join(os.path.abspath(o["out"]),"hero.png"); bpy.ops.render.render(write_still=True)
if not o["nospin"]:
    autoframe([2*math.pi*i/12 for i in range(12)])
    sc.cycles.samples=o["samples"]; r.resolution_x=r.resolution_y=o["size"]
    fd=os.path.join(os.path.abspath(o["out"]),"_frames"); os.makedirs(fd,exist_ok=True)
    for i in range(o["frames"]):
        pivot.rotation_euler=(0,0,2*math.pi*i/o["frames"]); r.filepath=os.path.join(fd,f"{i:04d}.png"); bpy.ops.render.render(write_still=True)

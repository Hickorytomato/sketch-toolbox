#!/usr/bin/env python3
"""build_replay.py MODEL.glb OUTDIR [--look studio|dusk] [--finish X] [--title "..."] [--size 640] [--samples 8] [--orbit 60]
Renders the build in assembly order (clay parts appear step by step with captions), then the finish, the final lighting,
and a slow orbit. Writes OUTDIR/replay.mp4 (<6 MB, <=720p). Steps/captions come from steps.py.
Falls back to matplotlib clay stills (no orbit render) if Blender fails."""
import sys,os,json,subprocess,shutil,tempfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
HERE=os.path.dirname(os.path.abspath(__file__)); BL=os.path.join(HERE,"..","tools","blender","blender")
a=sys.argv[1:]; glb,out=a[0],a[1]; os.makedirs(out,exist_ok=True)
def opt(k,d): return a[a.index(k)+1] if k in a else d
look,finish,title=opt("--look","studio"),opt("--finish",None),opt("--title",os.path.basename(os.path.dirname(os.path.abspath(glb))) or "Build")
size=min(720,int(opt("--size",640))); rd=os.path.join(out,"_replay"); shutil.rmtree(rd,ignore_errors=True)
cmd=[BL,"-b","--factory-startup","-P",os.path.join(HERE,"render_real.py"),"--",glb,out,"--replay","--look",look,"--size",str(size),"--samples",opt("--samples","8"),"--orbit",opt("--orbit","48")]
if finish: cmd+=["--finish",finish]
try:
    subprocess.run(cmd,capture_output=True,timeout=3600)
    meta=json.load(open(os.path.join(rd,"steps.json")))
    orbit=[os.path.join(meta["orbit"],f"{i:04d}.png") for i in range(meta["n"])]
except Exception as e:
    print("Blender replay failed, using clay fallback:",e,file=sys.stderr)
    import trimesh; sys.path.insert(0,HERE); import steps, render_views
    sc=trimesh.load(glb); names=list(sc.geometry.keys()); os.makedirs(rd,exist_ok=True); log=[]; shown=[]
    for i,(cap,ns) in enumerate(steps.groups(names)):
        shown+=ns; m=trimesh.util.concatenate([sc.geometry[n] for n in shown]); f=f"{rd}/step{i:02d}.png"
        render_views.render(m,25,-60,f,""); log.append([cap,f])
    meta={"steps":log}; orbit=[]
try: font=ImageFont.truetype("DejaVuSans-Bold.ttf",max(18,size//24)); small=ImageFont.truetype("DejaVuSans.ttf",max(14,size//36))
except: font=small=ImageFont.load_default()
def card(path,cap,sub):
    h=size//7; src=Image.open(path).convert("RGB").resize((size-h,size-h))
    im=Image.new("RGB",(size,size),(18,18,20)); im.paste(src,(h//2,0)); d=ImageDraw.Draw(im,"RGBA")
    d.text((size//24,size-h+h//6),cap,fill="white",font=font); d.text((size//24,size-h//2.3),sub,fill=(220,220,220),font=small)
    return np.asarray(im).astype(np.float32)
n=len(meta["steps"]); frames=[]
cards=[card(f,c,f"Step {i+1} of {n} · {title}") for i,(c,f) in enumerate(meta["steps"])]
FPS=24
for i,c in enumerate(cards):
    if i: frames+=[cards[i-1]*(1-t)+c*t for t in np.linspace(0,1,10)[1:]]
    frames+=[c]*int(FPS*(1.4 if i<n-1 else 1.8))
if orbit:
    oc=[card(f,"Done",title) for f in orbit]
    frames+=[cards[-1]*(1-t)+oc[0]*t for t in np.linspace(0,1,8)[1:]]
    # slow orbit: each orbit frame shown twice (60 frames -> 5 s)
    for f in oc: frames+=[f,f]
td=tempfile.mkdtemp()
for i,f in enumerate(frames): Image.fromarray(f.astype(np.uint8)).save(f"{td}/{i:05d}.png")
mp4=os.path.join(out,"replay.mp4")
for crf in (20,24,28,32):
    subprocess.run(["ffmpeg","-y","-loglevel","error","-framerate",str(FPS),"-i",f"{td}/%05d.png","-c:v","libx264","-crf",str(crf),"-pix_fmt","yuv420p","-movflags","+faststart",mp4],check=True)
    if os.path.getsize(mp4)<6e6: break
sd=os.path.join(out,"steps"); shutil.rmtree(sd,ignore_errors=True); os.makedirs(sd)
for i,(c,f) in enumerate(meta["steps"]): shutil.copy(f,os.path.join(sd,f"{i+1:02d}.png"))
json.dump([c for c,_ in meta["steps"]],open(os.path.join(sd,"captions.json"),"w"))   # used by fabdocs build-steps PDF
shutil.rmtree(td); shutil.rmtree(rd,ignore_errors=True); print(mp4)

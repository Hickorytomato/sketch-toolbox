#!/usr/bin/env python3
"""relief.py (v1.0.6): emboss / deboss images or text onto a printed surface WITHOUT a mesh boolean.
The heightmap is displaced straight into the surface grid of the part, so the mesh is watertight by construction and
memory stays small (the v1.0.4 vase died fusing a separate relief mesh). Today: round vases/cups/cylinders (outer wall).
  relief_vase(r, h, wall, floor, relief=[{text|image, angle, z, w, h, depth, invert, blur}], res=0.3) -> (trimesh, info)
    angle  deg around the axis where the art is centred (0 = +X, 90 = +Y = hero camera side)
    z, w, h  centre height, width along the surface (arc length), height - all mm
    depth  + emboss (raised), - deboss (sunk) mm.  res  grid spacing mm inside the art (0.3 = fine; coarse 2 mm elsewhere)
Printability (checked here, not by the 2 mm wall rule): raised/sunk strokes >= 2 x nozzle wide, |depth| >= 2 layers,
deboss leaves >= the 2 mm wall. Fails loudly with the reason; never silently thins."""
import math,os,numpy as np
NOZ=0.4; LAYER=0.2; MINWALL=2.0
def heightmap(rel,res):
    from PIL import Image,ImageDraw,ImageFont,ImageFilter
    W=max(8,int(round(rel["w"]/res))); H=max(8,int(round(rel["h"]/res)))
    if rel.get("image"):
        im=Image.open(rel["image"]).convert("L").resize((W,H),Image.LANCZOS); a=1-np.asarray(im,float)/255   # dark = raised
    else:
        im=Image.new("L",(W,H),0); dr=ImageDraw.Draw(im); txt=str(rel["text"]); fs=H
        while fs>4:
            ft=ImageFont.truetype(rel.get("font","DejaVuSans-Bold.ttf"),fs); bb=dr.textbbox((0,0),txt,font=ft)
            if bb[2]-bb[0]<=W*0.96 and bb[3]-bb[1]<=H*0.92: break
            fs=int(fs*0.92)
        dr.text(((W-(bb[2]-bb[0]))/2-bb[0],(H-(bb[3]-bb[1]))/2-bb[1]),txt,fill=255,font=ft); a=np.asarray(im,float)/255
    if rel.get("invert"): a=1-a
    b=max(0.0,float(rel.get("blur",0.25)))/res   # soft shoulders (no vertical cliffs: prints cleaner, no overhang)
    if b>0: a=np.asarray(Image.fromarray((a*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(b)),float)/255
    return np.clip(a,0,1)
def check_art(a,rel,res,wall):
    from scipy import ndimage
    errs=[]; d=float(rel["depth"]); ink=a>0.5
    if abs(d)<2*LAYER-1e-9: errs.append(f"relief depth {abs(d):.2f} mm is under 2 layers ({2*LAYER:.1f} mm): it will not show")
    if d<0 and wall+d<MINWALL-1e-9: errs.append(f"deboss {abs(d):.2f} mm leaves {wall+d:.2f} mm of wall: keep >= {MINWALL:g} mm (use depth >= {-(wall-MINWALL):.2f} or a thicker wall)")
    if ink.sum()==0: errs.append("the art is empty")
    else:
        r=max(1,int(round(NOZ/res)))   # opening with a 2xnozzle disk removes strokes the nozzle can't lay down
        yy,xx=np.mgrid[-r:r+1,-r:r+1]; k=(xx**2+yy**2)<=r*r
        lost=ink&~ndimage.binary_opening(ink,structure=k); f=lost.sum()/ink.sum()
        if f>0.15: errs.append(f"{100*f:.0f}% of the art is finer than {2*NOZ:.1f} mm (2 x nozzle): make the text/lines bigger or bolder")
    return errs
def relief_vase(r,h,wall,floor=2.0,relief=(),res=0.3,coarse=2.0):
    import trimesh
    from scipy.ndimage import map_coordinates
    R=float(r); Hh=float(h); Ri=R-float(wall); errs=[]; info=[]
    nt=int(min(2400,max(96,math.ceil(2*math.pi*R/res)))); th=np.linspace(0,2*math.pi,nt,endpoint=False)
    zs=set(np.round(np.linspace(0,Hh,int(math.ceil(Hh/coarse))+1),4))
    maps=[]
    for rel in relief:
        a=heightmap(rel,res); errs+=check_art(a,rel,res,wall)
        z0,z1=rel["z"]-rel["h"]/2,rel["z"]+rel["h"]/2
        if z0<floor+1 or z1>Hh-1: errs.append(f'relief z {z0:.1f}..{z1:.1f} mm must stay inside the wall ({floor+1:g}..{Hh-1:g} mm)')
        if rel["w"]>2*math.pi*R*0.95: errs.append("relief wider than the circumference")
        zs|=set(np.round(np.arange(z0,z1+res/2,res),4)); maps.append((rel,a,z0,z1))
        info.append(dict(angle=float(rel.get("angle",90)),z0=z0,z1=z1,w=rel["w"],depth=float(rel["depth"]),what=rel.get("text") or os.path.basename(str(rel.get("image")))))
    if errs: raise ValueError("; ".join(errs))
    zs=np.array(sorted(z for z in zs if 0<=z<=Hh)); nz=len(zs)
    T,Z=np.meshgrid(th,zs); Rad=np.full(T.shape,R)
    for rel,a,z0,z1 in maps:
        c=math.radians(float(rel.get("angle",90))); dth=(T-c+math.pi)%(2*math.pi)-math.pi; s=R*dth
        u=(s+rel["w"]/2)/rel["w"]; v=(Z-z0)/(z1-z0); inside=(u>=0)&(u<=1)&(v>=0)&(v<=1)
        rows,cols=a.shape; val=map_coordinates(a,[(1-v[inside])*(rows-1),u[inside]*(cols-1)],order=1,mode="nearest")
        Rad[inside]+=float(rel["depth"])*val
    V=[]; F=[]
    def ring(rad_row,z): base=len(V); V.extend(np.c_[rad_row*np.cos(th),rad_row*np.sin(th),np.full(nt,z)]); return base
    def band(a0,b0,flip=False):
        for i in range(nt):
            j=(i+1)%nt; q=[a0+i,a0+j,b0+j,b0+i]
            F.extend([[q[0],q[1],q[2]],[q[0],q[2],q[3]]] if not flip else [[q[0],q[2],q[1]],[q[0],q[3],q[2]]])
    OR=[ring(Rad[k],zs[k]) for k in range(nz)]
    zi=[floor]+[z for z in zs if z>floor+1e-6]; IR=[ring(np.full(nt,Ri),z) for z in zi]
    for k in range(nz-1): band(OR[k],OR[k+1])
    for k in range(len(IR)-1): band(IR[k],IR[k+1],flip=True)
    band(OR[-1],IR[-1])   # top rim (open top)
    cb=len(V); V.append([0,0,0]); ci=len(V); V.append([0,0,floor])
    for i in range(nt):
        j=(i+1)%nt; F.append([cb,OR[0]+j,OR[0]+i]); F.append([ci,IR[0]+i,IR[0]+j])
    m=trimesh.Trimesh(np.array(V),np.array(F),process=True)
    trimesh.repair.fix_normals(m)
    if not m.is_watertight or m.volume<=0: raise ValueError("relief mesh is not watertight (internal error)")
    return m,dict(bands=info,faces=len(m.faces),res=res,R=R)
if __name__=="__main__":
    import sys,time,json,resource
    t=time.time(); m,i=relief_vase(30,80,2.4,2.4,[dict(text="SKETCH",angle=90,z=40,w=60,h=18,depth=0.8)])
    print(json.dumps(i),f"{time.time()-t:.1f}s",m.is_watertight,f"maxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.0f} MB")

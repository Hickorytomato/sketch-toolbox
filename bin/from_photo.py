#!/usr/bin/env python3
"""from_photo.py composite PHOTO RENDER OUT.png [--x 0.5] [--y 0.85] [--scale 0.4] [--shadow 0.5] [--key auto]
Places a render on a user's photo. x,y = where the bottom-center of the image (incl. shadow) sits (0-1 of photo); scale = object width / photo width.
Best: render with render_real.py --cutout (transparent + real shadow). Otherwise background of the render is removed by flood-filling from the corners (works best with --look studio or a transparent PNG).
from_photo.py info PHOTO  -> size + suggested placement (lower third center)"""
import sys,numpy as np
from PIL import Image,ImageFilter,ImageDraw,ImageEnhance
def opt(n,d):
    return float(sys.argv[sys.argv.index(n)+1]) if n in sys.argv else d
def cutout(im,tol=38):
    im=im.convert("RGBA"); a=np.asarray(im).astype(int); h,w=a.shape[:2]
    if (a[...,3]<250).any():   # rendered with --cutout: partial alpha = shadow -> make it black, kill faint haze
        sh=a[...,3]<235; a[sh,:3]=0
        floor=np.median(np.concatenate([a[-20:,:40,3].ravel(),a[-20:,-40:,3].ravel()]))
        al=a[...,3].astype(float); al[sh]=np.clip((al[sh]-floor)/(235-floor),0,1)*200; a[...,3]=al; return Image.fromarray(a.astype(np.uint8),"RGBA")
    from scipy import ndimage
    ref=np.median(np.concatenate([a[:8,:,:3].reshape(-1,3),a[-8:,:,:3].reshape(-1,3)]),0)
    # background = pixels similar to the gradient row-wise (per row median of edges)
    rowref=np.stack([np.median(np.concatenate([a[y,:12,:3],a[y,-12:,:3]]),0) for y in range(h)])
    diff=np.abs(a[...,:3]-rowref[:,None,:]).sum(2)
    bg=diff<tol; lab,_=ndimage.label(bg); edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
    mask=~np.isin(lab,list(edge)); mask=ndimage.binary_opening(mask,iterations=2); mask=ndimage.binary_fill_holes(mask)
    al=Image.fromarray((mask*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)); im.putalpha(al); return im
cmd=sys.argv[1]
if cmd=="info":
    p=Image.open(sys.argv[2]); print(p.size,"suggest --x 0.5 --y 0.85 --scale 0.35"); sys.exit()
photo=Image.open(sys.argv[2]).convert("RGBA"); src=Image.open(sys.argv[3]); has_a=src.mode=="RGBA"; obj=cutout(src); out=sys.argv[4]
bb=obj.getchannel("A").point(lambda v:255 if v>25 else 0).getbbox(); obj=obj.crop(bb)
W=int(photo.width*opt("--scale",0.4)); obj=obj.resize((W,int(obj.height*W/obj.width)),Image.LANCZOS)
x=int(photo.width*opt("--x",0.5)-W/2); y=int(photo.height*opt("--y",0.85)-obj.height)
sh=Image.new("RGBA",photo.size,(0,0,0,0)); d=ImageDraw.Draw(sh); sw,shh=int(W*1.05),int(W*0.18)
d.ellipse([x+W/2-sw/2,y+obj.height-shh/2,x+W/2+sw/2,y+obj.height+shh/2],fill=(0,0,0,int(255*opt("--shadow",0.0 if has_a else 0.5))))
sh=sh.filter(ImageFilter.GaussianBlur(W/25))
# match brightness roughly to photo
lum=np.asarray(photo.convert("L")).mean()/128; obj_rgb=ImageEnhance.Brightness(obj).enhance(min(1.3,max(0.6,lum))); obj_rgb.putalpha(obj.getchannel("A"))
res=Image.alpha_composite(photo,sh); res.alpha_composite(obj_rgb,(x,y)); res.convert("RGB").save(out); print(out)

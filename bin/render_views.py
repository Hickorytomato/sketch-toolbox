#!/usr/bin/env python3
"""render_views.py MODEL(.stl/.glb) OUTDIR  -> front/side/top/iso PNGs + views.png grid"""
import sys, os, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
def load(p):
    m=trimesh.load(p,force="mesh"); e=(m.bounds[1]-m.bounds[0]).max()/25
    v,f=trimesh.remesh.subdivide_to_size(m.vertices,m.faces,e); return trimesh.Trimesh(v,f)
def render(m,elev,azim,out,title):
    f=plt.figure(figsize=(5,5),dpi=120); ax=f.add_subplot(111,projection="3d")
    tri=m.vertices[m.faces]; n=m.face_normals
    light=np.array([0.4,-0.6,0.7]); light/=np.linalg.norm(light)
    s=np.abs(n@light)*0.7+0.3
    col=np.c_[0.35*s,0.38*s,0.42*s,np.ones_like(s)]
    ax.add_collection3d(Poly3DCollection(tri,facecolors=col,edgecolor="none"))
    b=m.bounds; c=b.mean(0); r=(b[1]-b[0]).max()/2
    ax.set_xlim(c[0]-r,c[0]+r);ax.set_ylim(c[1]-r,c[1]+r);ax.set_zlim(c[2]-r,c[2]+r)
    ax.set_box_aspect((1,1,1)); ax.view_init(elev,azim); ax.set_axis_off(); ax.set_title(title)
    f.savefig(out,bbox_inches="tight"); plt.close(f)
if __name__=="__main__":
    m=load(sys.argv[1]); o=sys.argv[2]; os.makedirs(o,exist_ok=True)
    views=[("iso",25,-60),("front",0,-90),("side",0,0),("top",90,-90)]
    paths=[]
    for name,e,a in views:
        p=f"{o}/view_{name}.png"; render(m,e,a,p,name); paths.append(p)
    from PIL import Image
    ims=[Image.open(p).convert("RGB").resize((500,500)) for p in paths]
    g=Image.new("RGB",(1000,1000),"white")
    for i,im in enumerate(ims): g.paste(im,((i%2)*500,(i//2)*500))
    g.save(f"{o}/views.png"); print(f"{o}/views.png")

import sys, numpy as np, trimesh, imageio, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
src, out = sys.argv[1], sys.argv[2]
# per-part colours from 'preset__name' (same presets as render_real.py) so the fallback spin is not grey clay
PAL={"petg_teal":(.05,.5,.55),"petg_orange":(.95,.45,.1),"petg_black":(.15,.15,.17),"petg_white":(.9,.9,.86),"petg_yellow":(.95,.7,.1),"petg_blue":(.1,.25,.65),
     "hdpe":(.8,.85,.92),"liquid_blue":(.3,.55,.9),"leather":(.45,.26,.12),"mannequin":(.6,.58,.55),"sprayer_white":(.92,.92,.9),"sprayer_dark":(.12,.12,.14),
     "raw_steel":(.55,.58,.63),"black_paint":(.12,.12,.13),"rust":(.55,.25,.1),"cedar":(.6,.33,.16),"concrete":(.55,.55,.53),"dark":(.15,.15,.16)}
sc_ = trimesh.load(src); geoms = sc_.dump() if hasattr(sc_,"dump") else [sc_]
names = [n for n in (sc_.graph.nodes_geometry if hasattr(sc_,"graph") else ["x"])]
cols=[]; ms=[]
for n in names if hasattr(sc_,"graph") else ["x"]:
    if hasattr(sc_,"graph"):
        T_,g_ = sc_.graph[n]; g=sc_.geometry[g_].copy(); g.apply_transform(T_)
    else: g=sc_
    ms.append(g); cols.append(np.repeat([PAL.get(n.split("__")[0].rstrip("0123456789"),(.55,.58,.63))],len(g.faces),0))
m = trimesh.util.concatenate(ms); FC=np.concatenate(cols); m.fix_normals()
v0 = m.vertices - m.bounds.mean(0); f = m.faces
v0 = v0[:, [0,2,1]] if m.extents[1] > m.extents[2]*1.0 and False else v0
r = np.linalg.norm(v0,axis=1).max()
L = np.array([0.3,-0.6,0.75]); L/=np.linalg.norm(L)
frames=[]
for a in np.radians(np.arange(0,360,4)):
    ca,sa=np.cos(a),np.sin(a); Rz=np.array([[ca,-sa,0],[sa,ca,0],[0,0,1]])
    e=np.radians(22); ce,se=np.cos(e),np.sin(e); Rx=np.array([[1,0,0],[0,ce,-se],[0,se,ce]])
    v=v0@Rz.T@Rx.T                     # x right, y depth, z up
    tri=v[f]; n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]); n/=np.linalg.norm(n,axis=1,keepdims=True)+1e-12
    vis=n[:,1]<0                       # facing camera (camera at -y)
    shade=np.clip(0.3+0.7*np.abs(n@L),0,1)
    depth=tri[:,:,1].mean(1); order=np.argsort(-depth); order=order[vis[order]]
    fig=plt.figure(figsize=(6,6),dpi=100); ax=fig.add_axes([0,0,1,1]); ax.set_facecolor("#1e1e1e"); fig.patch.set_facecolor("#1e1e1e")
    c=(FC*shade[:,None]).clip(0,1)[order]
    ax.add_collection(PolyCollection(tri[order][:,:,[0,2]],facecolors=c,edgecolors=c,linewidths=0.3))
    ax.set_xlim(-r*1.1,r*1.1); ax.set_ylim(-r*1.1,r*1.1); ax.set_aspect("equal"); ax.axis("off")
    fig.canvas.draw(); frames.append(np.asarray(fig.canvas.buffer_rgba())[...,:3].copy()); plt.close(fig)
imageio.mimsave(out,frames,fps=24,codec="libx264",quality=7,macro_block_size=1)
imageio.imwrite(out.rsplit('.',1)[0]+"_frame.png",frames[5])

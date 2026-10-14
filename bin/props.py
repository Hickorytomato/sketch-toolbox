#!/usr/bin/env python3
"""props.py - believable context props for renders/concepts (trimesh, mm, Z up). Node names use render_real.py presets.
  bottle(x,y,z0,rot=0)      -> list[(name,mesh)]  32 oz trigger sprayer: translucent HDPE body, liquid, neck, ribbed cap,
                               shaped shroud + nozzle + curved trigger, dip tube. ~Ø88 x 245 body, ~310 overall.
  belt(cx,cy,r_in,z,w=38,t=5,span_deg=220,start_deg=None) -> [(name,mesh)] curved belt following a waist radius (default 150-180)
  mannequin(cx,cy,r_waist,z_belt) -> [(name,mesh)] neutral faceless hip/torso form (NOT a person), matte grey
  save(path, items, rotz_deg=180) -> GLB for render_real.py / concept_art.py
CLI demo: props.py OUT.glb  (bottle on a belt on a mannequin)"""
import numpy as np, trimesh, sys
from trimesh.creation import revolve, cylinder, extrude_polygon
from shapely.geometry import Polygon
def T(m,x=0,y=0,z=0): m=m.copy(); m.apply_translation([x,y,z]); return m
def _rev(prof,sec=72): return revolve(np.asarray(prof,float),sections=sec)
def _side(poly,width):
    """extrude a YZ-profile (y forward, z up) symmetric across X by width"""
    m=extrude_polygon(Polygon(poly),width); m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[0,1,0]))  # XY->YZ: x->-z
    m.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
    b=m.bounds; m.apply_translation([-(b[0][0]+b[1][0])/2,0,0]); return m
def _yz(poly,width):
    # build directly: vertices (x,y,z) from polygon (y,z)
    p=Polygon(poly); m=extrude_polygon(p,width)       # in XY plane, Z extrusion
    v=m.vertices.copy(); m.vertices=np.c_[v[:,2]-width/2,v[:,0],v[:,1]]; m.fix_normals(); return m
def bottle(x=0,y=0,z0=0,rot=0,d=88,h=245,fill=0.72,liquid="liquid_blue"):
    r=d/2; nr=14
    prof=[[0,0],[r-6,0],[r-1.5,1.5],[r,6],[r,h*0.70],[r-2,h*0.76],[r*0.80,h*0.86],[nr+6,h-22],[nr+1,h-14],[nr,h-12],[nr,h],[0,h]]
    body=_rev(prof)
    shell_in=[[0,2],[r-7,2],[r-2.6,3.5],[r-1.6,7]]
    lh=h*0.70*fill/0.70*0.70 if fill<1 else h*0.7
    lh=min(h*0.70,h*fill)
    liq=_rev([[0,2.2],[r-6.5,2.2],[r-1.8,6.5],[r-1.8,lh],[0,lh]])
    out=[("hdpe__bottle",body),("%s__liquid"%liquid,liq)]
    out.append(("rubber__diptube",T(cylinder(2.2,h-6,sections=12),r*0.45,0,(h-6)/2+4)))
    cap=_rev([[0,0],[17.5,0],[17.5,18],[15,20],[0,20]],48)
    ribs=[T(cylinder(1.2,16,sections=6),17.6*np.cos(a),17.6*np.sin(a),9) for a in np.linspace(0,2*np.pi,30,endpoint=False)]
    out.append(("sprayer_white__cap",T(trimesh.util.concatenate([cap]+ribs),0,0,h-4)))
    zb=h+15   # shroud: side profile in (y forward, z up)
    shroud=[(-22,zb),(-24,zb+30),(-18,zb+52),(-4,zb+60),(40,zb+60),(66,zb+52),(70,zb+44),(56,zb+36),(20,zb+30),(14,zb+12),(10,zb)]
    out.append(("sprayer_white__shroud",_yz(shroud,34)))
    out.append(("sprayer_dark__nozzle",T(_yz([(66,zb+40),(80,zb+40),(82,zb+54),(66,zb+56)],20),0,0,0)))
    trig=[(14,zb+30),(24,zb+28),(30,zb+8),(30,zb-18),(26,zb-34),(20,zb-36),(19,zb-20),(20,zb+2),(16,zb+18)]
    out.append(("sprayer_dark__trigger",_yz(trig,16)))
    out.append(("sprayer_white__collar",T(cylinder(12,16,sections=40),0,0,h+16)))
    R=trimesh.transformations.rotation_matrix(np.radians(rot),[0,0,1])
    res=[]
    for n,m in out:
        m=m.copy(); m.apply_transform(R); m.apply_translation([x,y,z0]); res.append((n,m))
    return res
def _sector(r0,r1,z0,z1,a0,a1,n=96):
    a=np.linspace(a0,a1,n); outer=np.c_[r1*np.cos(a),r1*np.sin(a)]; inner=np.c_[r0*np.cos(a[::-1]),r0*np.sin(a[::-1])]
    m=extrude_polygon(Polygon(np.r_[outer,inner]),z1-z0); m.apply_translation([0,0,z0]); return m
def belt(cx=0,cy=-165,r_in=165,z=40,w=38,t=5,span_deg=220,start_deg=None,buckle=True):
    """belt band around a waist circle centred (cx,cy); default arc centred on +Y (front of the circle faces +Y)"""
    a0=np.radians(90-span_deg/2 if start_deg is None else start_deg); a1=a0+np.radians(span_deg)
    m=_sector(r_in,r_in+t,z-w/2,z+w/2,a0,a1); m.apply_translation([cx,cy,0]); out=[("leather__belt",m)]
    # stitching grooves: thin raised lines
    for dz in(-w/2+3,w/2-3):
        s=_sector(r_in+t,r_in+t+0.4,z+dz-0.4,z+dz+0.4,a0,a1); s.apply_translation([cx,cy,0]); out.append(("leather_stitch__st%d"%dz,s))
    return out
def mannequin(cx=0,cy=-165,r_waist=165,z_belt=40):
    """neutral dress-form torso/hips, elliptic section (wider than deep), faceless; belt line at z_belt"""
    rw=r_waist-1.0
    prof=[[0,-300],[rw*0.60,-300],[rw*0.98,-250],[rw*1.10,-160],[rw*1.08,-60],[rw,0],[rw*0.95,80],[rw*0.98,170],[rw*1.05,250],[rw*0.95,310],[rw*0.62,350],[rw*0.25,366],[0,368]]
    m=_rev(prof,96); m.apply_translation([cx,cy,z_belt]); stand=T(cylinder(14,260,sections=24),cx,cy,z_belt-300-130)
    return [("mannequin__form",m),("dark__stand",stand)]
def save(path,items,rotz_deg=180):
    sc=trimesh.Scene(); R=trimesh.transformations.rotation_matrix(np.radians(rotz_deg),[0,0,1]); seen={}
    for n,m in items:
        k=n; i=1
        while k in seen: i+=1; k=f"{n}{i}"
        seen[k]=1; m=m.copy(); m.apply_transform(R); sc.add_geometry(m,node_name=k,geom_name=k)
    sc.export(path); return path
if __name__=="__main__":
    it=bottle(0,60,-60)+belt()+mannequin(); print(save(sys.argv[1] if len(sys.argv)>1 else "props_demo.glb",it))

#!/usr/bin/env python3
"""meshfuse.py IN.stl OUT.stl -> one fused solid: split into closed shells (joined only across 2-face edges), repair each, boolean-union.
Shared by kit.custom_stl (CAD copy) and ship.py (the print gate)."""
import sys,numpy as np,trimesh,manifold3d as mf
def tomf(m): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices,np.float32),tri_verts=np.asarray(m.faces,np.uint32)))
def totm(M): k=M.to_mesh(); return trimesh.Trimesh(k.vert_properties[:,:3],k.tri_verts,process=True)
def shells(m):
    m=m.copy(); m.merge_vertices()
    es=m.edges_sorted.reshape(-1,2); fi=np.repeat(np.arange(len(m.faces)),3); grp=trimesh.grouping.group_rows(es)
    pairs=np.array([fi[g] for g in grp if len(g)==2]) if len(grp) else np.zeros((0,2),int)
    comps=trimesh.graph.connected_components(pairs,nodes=np.arange(len(m.faces)),min_len=1)
    return [m.submesh([c],append=True) for c in comps if len(c)>=4]
def close(c):
    if not c.is_watertight: trimesh.repair.fill_holes(c); trimesh.repair.fix_normals(c)
    if not c.is_watertight:
        try:
            import pymeshfix; v,f=pymeshfix.clean_from_arrays(np.ascontiguousarray(c.vertices,np.float64),np.ascontiguousarray(c.faces,np.int32)); c=trimesh.Trimesh(v,f)
        except Exception: pass
    if c.is_watertight and c.volume<0: c.invert()
    return c
def fuse(m,name="part"):
    """-> ((bodies, n_shells), None) or (None, plain reason)"""
    parts=shells(m) if len(m.faces) else []; Ms=[]
    for c in parts:
        c=close(c)
        if not c.is_watertight: return None,f"a shell of {name} is not a closed surface (holes in the mesh) and could not be repaired"
        M=tomf(c)
        if M.status()!=mf.Error.NoError: return None,f"a shell of {name} is not a valid solid ({M.status()})"
        Ms.append(M)
    if not Ms: return None,f"{name} has no geometry"
    U=mf.Manifold.batch_boolean(Ms,mf.OpType.Add) if len(Ms)>1 else Ms[0]
    return ([totm(b) for b in U.decompose() if b.volume()>1e-3],len(Ms)),None
if __name__=="__main__":
    r,e=fuse(trimesh.load(sys.argv[1],force="mesh"))
    if e: print("[FAIL]",e); sys.exit(1)
    trimesh.util.concatenate(r[0]).export(sys.argv[2]); print(f"{r[1]} shells -> {len(r[0])} bodies")

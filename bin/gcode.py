#!/usr/bin/env python3
"""gcode.py NEST.json OUTDIR [machine ...]  -> <sheet>_<machine>.nc + preview PNG per sheet per machine (machines.json).
plasma/laser: kerf compensation (outer +kerf/2, holes/inner -kerf/2), lead-ins (outside for outers, from inside for holes),
inner features first then outer per part, nearest-neighbor part order, M3/M5 torch, G4 pierce delay, arcs as G2/G3 (I,J).
router: tool-radius compensation, depth passes to full thickness, spindle M3 S.  Units inches (G20), absolute (G90).
STARTING POINT ONLY: verify feeds, kerf, THC/height, M-codes for your controller in a simulator and dry run before cutting."""
import sys,os,json,math,matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
B=os.path.dirname(os.path.abspath(__file__)); n=json.load(open(sys.argv[1])); o=sys.argv[2]; os.makedirs(o,exist_ok=True)
M=json.load(open(f"{B}/machines.json")); wanted=sys.argv[3:] or [k for k,v in M.items() if isinstance(v,dict) and v.get("type") in("plasma","laser","router") and v.get("enabled")]
def f4(v): return f"{v:.4f}"
from shapely.geometry import Polygon as _SP0
def circle_ops(cx,cy,r,inside,lead,cw):
    """returns (start_xy, list of gcode lines for lead-in + full circle). inside=True: hole (lead from center side)."""
    sx,sy=cx+r,cy
    lx=cx+(r-lead if inside else r+lead); lx=max(cx+0.6*r,lx) if inside else lx
    g=["G2" if cw else "G3"]
    lines=[f"G1 X{f4(sx)} Y{f4(sy)}", f"{g[0]} X{f4(sx)} Y{f4(sy)} I{f4(cx-sx)} J0"]
    return (lx,cy),lines
def poly_offset(pts,d):
    from shapely.geometry import Polygon
    P=Polygon(pts).buffer(d,join_style=2); return list(P.exterior.coords)[:-1]
for mname in wanted:
    m=M[mname]; t=m["type"]
    for G in n["groups"]:
        th=G.get("thickness") or 0.25; mat=G.get("material","steel")
        warn=[]
        if t in("plasma","laser") and th>m.get("max_thickness",9): warn.append(f"{th}\" exceeds {mname} max {m['max_thickness']}\"")
        WOOD=("wood","plywood","baltic_birch","mdf","hardwood","pine","cedar"); mcls="wood" if mat in WOOD else "plastic" if mat in("acrylic","hdpe","plastic") else mat
        if t=="plasma" and mcls in("wood","plastic"): print(f"skip {mname} for {G['name']}: {mat} is not plasma-cuttable"); continue
        if t=="laser" and th>m.get("max_thickness",9): print(f"skip {mname} for {G['name']}: {th}\" is over its {m.get('max_thickness')}\" max"); continue
        if t=="router" and mcls not in m.get("materials",[]): 
            print(f"skip {mname} for {G['name']}: {mat} not a router material"); continue
        comp=(m["kerf"]/2 if t!="router" else m["tool_dia"]/2); lead=m.get("lead_in",m.get("tool_dia",0.25))
        L=[f"(Sketch {mname} program  sheet {G['name']} {G['sheet'][0]}x{G['sheet'][1]}  {th}in {mat})",
           "(STARTING POINT - VERIFY IN SIMULATOR AND DRY RUN BEFORE CUTTING)",f"(comp {comp:.4f} per side, feed {m['feed_ipm']} ipm)","G20 G90 G17 G40"]
        if t=="router": L+=[f"M3 S{m['rpm']}",f"G0 Z{m['safe_z']}"]
        segs=[]; pierces=[]; pos=(0,0)
        parts=sorted(G["parts"],key=lambda p:0); order=[]; rem=list(parts)
        def pc(p):
            g=p["geom"]["outer"]; return (g["circle"][0],g["circle"][1]) if "circle" in g else tuple(map(lambda v:sum(v)/len(v),zip(*g["poly"])))
        while rem:
            p=min(rem,key=lambda q:math.dist(pos,pc(q))); rem.remove(p); order.append(p); pos=pc(p)
        def cut(start,body,label):
            L.append(f"(-- {label})"); L.append(f"G0 X{f4(start[0])} Y{f4(start[1])}"); segs.append(("rapid",pos,start))
            if t=="router":
                passes=max(1,math.ceil(th/m["depth_per_pass"]))
                for k in range(1,passes+1):
                    L.append(f"G1 Z{f4(-min(th,k*m['depth_per_pass']))} F{m['plunge_ipm']}"); L.append(f"G1 F{m['feed_ipm']}"); L.extend(body)
                L.append(f"G0 Z{m['safe_z']}")
            else:
                L.extend(["M3",f"G4 P{m['pierce_delay_s']}",f"G1 F{m['feed_ipm']}"]+body+["M5"])
            pierces.append(start)
        tooSmall=[]; FLIP=[]
        def pocket(p,pk,LL=None):
            """contour-parallel pocket: offsets inward by 40% stepover until empty, ramp to depth in passes"""
            LL=L if LL is None else LL; r_=m["tool_dia"]/2; P_=_SP0(pk["poly"]).buffer(-r_,join_style=2); rings=[]
            while not P_.is_empty:
                for g_ in (P_.geoms if P_.geom_type=="MultiPolygon" else [P_]): rings.append(list(g_.exterior.coords))
                P_=P_.buffer(-0.8*r_,join_style=2)
            if not rings: tooSmall.append(f'{p["name"]} pocket narrower than the {m["tool_dia"]}" bit'); return
            dep=pk["depth"]; n_=max(1,math.ceil(dep/m["depth_per_pass"])); LL.append(f'(-- {p["name"]} pocket {dep:.3f} deep, {len(rings)} rings)')
            for k in range(1,n_+1):
                for rg in rings:
                    LL+= [f"G0 X{f4(rg[0][0])} Y{f4(rg[0][1])}",f"G1 Z{f4(-min(dep,k*m['depth_per_pass']))} F{m['plunge_ipm']}",f"G1 F{m['feed_ipm']}"]+[f"G1 X{f4(x)} Y{f4(y)}" for x,y in rg[1:]]+[f"G0 Z{m['safe_z']}"]
                    segs.append(("pocket",rg,None))
        for p in order:
            gm=p["geom"]
            for hx,hy,hr in gm["holes"]+gm["inner"]:
                r=hr-comp
                if t in("plasma","laser") and 2*hr<m.get("min_hole_ratio",1)*th: tooSmall.append(f'{p["name"]} hole {2*hr:.3f}" < {m.get("min_hole_ratio",1)}x thickness: drill instead')
                if r<=0.02: tooSmall.append(f'{p["name"]} hole {2*hr:.3f}" too small for {mname}'); continue
                st,body=circle_ops(hx,hy,r,True,lead,cw=False)   # holes CCW
                cut(st,body,f'{p["name"]} hole d{2*hr:.3f}'); segs.append(("circle",(hx,hy),r))
            from shapely.geometry import Polygon as _SP, LinearRing as _LR
            for ip in gm.get("inner_poly",[]):   # interior cutouts: offset inward, CCW
                P_=_SP(ip).buffer(-comp,join_style=2)
                if P_.is_empty: tooSmall.append(f'{p["name"]} cutout too small for {mname}'); continue
                q=list(P_.exterior.coords)[:-1]
                if not _LR(q).is_ccw: q=q[::-1]
                c0=P_.centroid; a=q[0]; st=(a[0]+(c0.x-a[0])*0.3,a[1]+(c0.y-a[1])*0.3)
                cut(st,[f"G1 X{f4(x)} Y{f4(y)}" for x,y in q]+[f"G1 X{f4(a[0])} Y{f4(a[1])}"],f'{p["name"]} cutout'); segs.append(("poly",q,None))
            for pk in gm.get("pockets",[]):
                if t!="router": tooSmall.append(f'{p["name"]} has a {pk["depth"]:.3f}" deep pocket/dado: not cuttable on {mname}, use router/table saw'); continue
                if pk.get("face","top")!="top": tooSmall.append(f'{p["name"]}: pocket on the BACK face, cut it in a second program after flipping (see {G["name"]}_{mname}_flip.nc)'); FLIP.append((p,pk)); continue
                pocket(p,pk)
            if "circle" in gm["outer"]:
                cx,cy,r=gm["outer"]["circle"]; st,body=circle_ops(cx,cy,r+comp,False,lead,cw=True)   # outer CW
                cut(st,body,f'{p["name"]} outer d{2*r:.3f}'); segs.append(("circle",(cx,cy),r+comp))
            else:
                pts=poly_offset(gm["outer"]["poly"],comp)
                from shapely.geometry import LinearRing
                if LinearRing(pts).is_ccw: pts=pts[::-1]   # outer contour CW
                a=pts[0]   # lead-in: approach first corner from outside along center->corner direction
                cxp,cyp=pc(p); vx,vy=a[0]-cxp,a[1]-cyp; vl=math.hypot(vx,vy) or 1; st=(a[0]+vx/vl*lead,a[1]+vy/vl*lead)
                body=[f"G1 X{f4(a[0])} Y{f4(a[1])}"]+[f"G1 X{f4(x)} Y{f4(y)}" for x,y in pts[1:]]+[f"G1 X{f4(a[0])} Y{f4(a[1])}"]
                cut(st,body,f'{p["name"]} outer'); segs.append(("poly",pts,None))
            pos=pierces[-1]
        L+=(["M5","G0 Z1"] if t=="router" else [])+["G0 X0 Y0","M30"]
        tooSmall=list(dict.fromkeys(tooSmall)); hdr=[f"(WARNING: {w})" for w in warn+tooSmall]
        nc=f"{o}/{G['name']}_{mname}.nc"; open(nc,"w").write("\n".join(L[:2]+hdr+L[2:])+"\n")
        if FLIP:   # back-face pockets: mirror X about sheet centre after flipping the sheet end-for-end along Y axis
            W0=G["sheet"][0]; LF=[f"(Sketch {mname} FLIP program {G['name']}: flip the sheet left-to-right, re-zero same corner)","(STARTING POINT - VERIFY BEFORE CUTTING)","G20 G90 G17 G40",f"M3 S{m['rpm']}",f"G0 Z{m['safe_z']}"]
            for p_,pk_ in FLIP: pocket(p_,dict(pk_,poly=[(W0-x,y) for x,y in pk_["poly"]]),LF)
            open(nc.replace(".nc","_flip.nc"),"w").write("\n".join(LF+["M5","G0 X0 Y0","M30"])+"\n")
        cutlen=0; pocklen=0
        fig,ax=plt.subplots(figsize=(10,10*G["sheet"][1]/G["sheet"][0])); W,H=G["sheet"]
        ax.add_patch(plt.Rectangle((0,0),W,H,fill=False,color="gray"))
        for s in segs:
            if s[0]=="rapid": ax.plot([s[1][0],s[2][0]],[s[1][1],s[2][1]],ls=":",color="gray",lw=0.8)
            elif s[0]=="circle": ax.add_patch(plt.Circle(s[1],s[2],fill=False,color="red",lw=1)); cutlen+=2*math.pi*s[2]
            elif s[0]=="pocket": ax.plot(*zip(*s[1]),color="orange",lw=0.5); pocklen+=sum(math.dist(s[1][i],s[1][i+1]) for i in range(len(s[1])-1))
            else:
                q=s[1]+[s[1][0]]; ax.plot(*zip(*q),color="red",lw=1); cutlen+=sum(math.dist(q[i],q[i+1]) for i in range(len(q)-1))
        for i,pp in enumerate(pierces): ax.plot(*pp,"o",color="orange",ms=3); ax.text(pp[0],pp[1],str(i+1),fontsize=6)
        mins=cutlen/m["feed_ipm"]+len(pierces)*m.get("pierce_delay_s",0)/60*(1 if t!="router" else 0)
        if t=="router": mins=mins*max(1,math.ceil(th/m["depth_per_pass"]))+pocklen/m["feed_ipm"]   # pocket rings already listed per pass
        ax.set_aspect("equal"); ax.set_xlim(-2,W+2); ax.set_ylim(-2,H+2)
        ax.set_title(f"{mname}: {G['name']}  cut {cutlen:.0f} in, {len(pierces)} pierces, ~{mins:.1f} min  (VERIFY BEFORE CUTTING)")
        fig.savefig(nc.replace(".nc","_preview.png"),dpi=80,bbox_inches="tight"); plt.close(fig)
        json.dump(dict(machine=mname,sheet=G["name"],cut_in=round(cutlen,1),pierces=len(pierces),est_min=round(mins,1),warnings=warn+tooSmall),open(nc.replace(".nc",".json"),"w"))
        print(nc,f"cut {cutlen:.0f}in pierces {len(pierces)} ~{mins:.1f}min",("WARN: "+"; ".join(warn+tooSmall)) if warn or tooSmall else "")

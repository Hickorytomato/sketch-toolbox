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
import sys as _s; _s.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import kerf as _kerf, rules as _rules
_PJ=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[1])))),"parts.json")
_PD=json.load(open(_PJ)) if os.path.exists(_PJ) else {}
BID=_PD.get("build_id","?"); HSPEC=_PD.get("hole_specs",[])
def _fit_hole(part,d):
    """bolt hole whose clearance is tighter than 2x the plasma tolerance (0.030): drill it to size"""
    for h in HSPEC:
        if part in h["parts"] and abs(h["d_in"]-d)<0.002 and (h.get("tapped") or (h.get("dia_in") and h["d_in"]-h["dia_in"]<0.06)): return True
    return False
for mname in wanted:
    m=M[mname]; t=m["type"]
    for G in n["groups"]:
        th=G.get("thickness") or 0.25; mat=G.get("material","steel")
        warn=[]
        if t in("plasma","laser") and th>m.get("max_thickness",9): warn.append(f"{th}\" exceeds {mname} max {m['max_thickness']}\"")
        WOOD=("wood","plywood","baltic_birch","mdf","hardwood","pine","cedar"); mcls="wood" if mat in WOOD else "plastic" if mat in("acrylic","hdpe","plastic") else mat
        if t=="plasma" and mcls in("wood","plastic"): print(f"skip {mname} for {G['name']}: {mat} is not plasma-cuttable"); continue
        if t=="laser" and th>m.get("max_thickness",9): print(f"skip {mname} for {G['name']}: {th}\" is over its {m.get('max_thickness')}\" max"); continue
        if t=="laser" and _rules.mcls(mat) in("banned_plastic","unknown","plastic"): print(f"skip {mname} for {G['name']}: {mat} is banned or unidentified for the laser (get the SDS)"); continue
        if t=="router" and mcls not in m.get("materials",[]): 
            print(f"skip {mname} for {G['name']}: {mat} not a router material"); continue
        if t=="router":   # cutouts narrower than the bit can't be routed at all: send that sheet to the laser/hand instead
            from shapely.geometry import Polygon as _Pg
            _narrow=[f["name"] for f in G.get("parts",[]) if isinstance(f,dict) and any(len(q)>2 and _Pg(q).buffer(-m["tool_dia"]/2+1e-4).is_empty for q in f.get("inner_poly",[]))]
            if _narrow: print(f"skip {mname} for {G['name']}: cutouts in {', '.join(_narrow)} are narrower than the {m['tool_dia']} in bit (use the laser or a smaller bit)"); continue
        KF,KSRC=_kerf.lookup(mname,m,mat,th); comp=KF/2; HOLES=[]; TABS={}
        DPP=m.get("depth_per_pass",0.125)
        if t=="router": DPP=min(DPP,(0.5 if mcls=="wood" and "ply" not in mat and mat!="mdf" else 1/3)*m["tool_dia"])   # DOC limit 0.5x bit softwood, 1/3 ply/MDF/hardwood
        lead=m.get("lead_in",m.get("tool_dia",0.25))
        L=[f"(Sketch {mname} program  sheet {G['name']} {G['sheet'][0]}x{G['sheet'][1]}  {th}in {mat})",
           "(STARTING POINT - VERIFY IN SIMULATOR AND DRY RUN BEFORE CUTTING)",f"(Build {BID})",f"(kerf {KF:.4f} from {KSRC})",f"(comp {comp:.4f} per side, feed {m['feed_ipm']} ipm)","G20 G90 G17 G40"]
        if t=="router": L+=[f"M3 S{m['rpm']}",f"G0 Z{m['safe_z']}"]
        segs=[]; pierces=[]; pos=(0,0)
        parts=sorted(G["parts"],key=lambda p:0); order=[]; rem=list(parts)
        def pc(p):
            g=p["geom"]["outer"]; return (g["circle"][0],g["circle"][1]) if "circle" in g else tuple(map(lambda v:sum(v)/len(v),zip(*g["poly"])))
        while rem:
            p=min(rem,key=lambda q:math.dist(pos,pc(q))); rem.remove(p); order.append(p); pos=pc(p)
        def cut(start,body,label,last=None):
            L.append(f"(-- {label})"); L.append(f"G0 X{f4(start[0])} Y{f4(start[1])}"); segs.append(("rapid",pos,start))
            if t=="router":
                passes=max(1,math.ceil(th/DPP-1e-9))
                for k in range(1,passes+1):
                    L.append(f"G1 Z{f4(-min(th,k*DPP))} F{m['plunge_ipm']}"); L.append(f"G1 F{m['feed_ipm']}"); L.extend(last if (last and k==passes) else body)
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
            dep=pk["depth"]; n_=max(1,math.ceil(dep/DPP-1e-9)); LL.append(f'(-- {p["name"]} pocket {dep:.3f} deep, {len(rings)} rings)')
            for k in range(1,n_+1):
                for rg in rings:
                    LL+= [f"G0 X{f4(rg[0][0])} Y{f4(rg[0][1])}",f"G1 Z{f4(-min(dep,k*DPP))} F{m['plunge_ipm']}",f"G1 F{m['feed_ipm']}"]+[f"G1 X{f4(x)} Y{f4(y)}" for x,y in rg[1:]]+[f"G0 Z{m['safe_z']}"]
                    segs.append(("pocket",rg,None))
        for p in order:
            gm=p["geom"]
            for hx,hy,hr in gm["holes"]+gm["inner"]:
                r=hr-comp; dd=2*hr
                lim={"plasma":1.5,"laser":0.5}.get(t,0)   # catalog #28 plasma < 1.5x t, #18 laser < 0.5x t -> DRILL
                if (t in("plasma","laser") and dd<lim*th-1e-9) or (t=="plasma" and _fit_hole(p["name"],dd)) or r<=0.02 or (t=="router" and dd<m["tool_dia"]-1e-9):
                    why=("fit-critical bolt hole: plasma holds ±0.030" if t=="plasma" and dd>=lim*th-1e-9 and r>0.02 else f"under {lim}x thickness" if t in("plasma","laser") else "smaller than the bit")
                    tooSmall.append(f'{p["name"]} hole {dd:.3f}" DRILL ({why}): not in this program, center-punch and drill'); HOLES.append(dict(part=p["name"],d=round(dd,4),x=hx,y=hy,action="drill",why=why)); continue
                st,body=circle_ops(hx,hy,r,True,lead,cw=False)   # holes CCW
                fd=m["feed_ipm"]*(0.6 if t=="plasma" and dd<1.0 else 1)   # catalog #83: holes < 1 in at ~60% speed
                if fd!=m["feed_ipm"]: body=[f"G1 F{fd:.0f}"]+body
                cut(st,body,f'{p["name"]} hole d{dd:.5f}'); segs.append(("circle",(hx,hy),r)); HOLES.append(dict(part=p["name"],d=round(dd,4),action="cut",feed=fd))
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
                cut(st,body,f'{p["name"]} outer d{2*r:.5f}'); segs.append(("circle",(cx,cy),r+comp))
            else:
                pts=poly_offset(gm["outer"]["poly"],comp)
                from shapely.geometry import LinearRing
                if LinearRing(pts).is_ccw: pts=pts[::-1]   # outer contour CW
                a=pts[0]   # lead-in: approach first corner from outside along center->corner direction
                cxp,cyp=pc(p); vx,vy=a[0]-cxp,a[1]-cyp; vl=math.hypot(vx,vy) or 1; st=(a[0]+vx/vl*lead,a[1]+vy/vl*lead)
                body=[f"G1 X{f4(a[0])} Y{f4(a[1])}"]+[f"G1 X{f4(x)} Y{f4(y)}" for x,y in pts[1:]]+[f"G1 X{f4(a[0])} Y{f4(a[1])}"]
                last=None
                if t=="router":   # holding tabs on the final pass: >= 3, every ~5 in, 3/16 in (~5 mm) + bit wide, t/2 high (catalog #41)
                    ring=pts+[pts[0]]; per=sum(math.dist(ring[i],ring[i+1]) for i in range(len(ring)-1)); nT=max(3,math.ceil(per/5)); tw=0.1875+m["tool_dia"]
                    cen=[per*(k+0.5)/nT for k in range(nT)]; zt=-th/2; zb=-th; last=[f"G1 X{f4(a[0])} Y{f4(a[1])}"]; acc=0
                    for i in range(len(ring)-1):
                        p0,p1=ring[i],ring[i+1]; sl=math.dist(p0,p1)
                        if sl<1e-9: continue
                        ev=[]
                        for c_ in cen:
                            for u,z in ((c_-tw/2,zt),(c_+tw/2,zb)):
                                if acc<u<=acc+sl: ev.append((u,z))
                        for u,z in sorted(ev):
                            f_=(u-acc)/sl; last+= [f"G1 X{f4(p0[0]+f_*(p1[0]-p0[0]))} Y{f4(p0[1]+f_*(p1[1]-p0[1]))}",f"G1 Z{f4(z)}"]
                        last.append(f"G1 X{f4(p1[0])} Y{f4(p1[1])}"); acc+=sl
                    TABS[p["name"]]=nT
                cut(st,body,f'{p["name"]} outer',last); segs.append(("poly",pts,None))
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
        if t=="router": mins=mins*max(1,math.ceil(th/DPP-1e-9))+pocklen/m["feed_ipm"]   # pocket rings already listed per pass
        ax.set_aspect("equal"); ax.set_xlim(-2,W+2); ax.set_ylim(-2,H+2)
        ax.set_title(f"{mname}: {G['name']}  cut {cutlen:.0f} in, {len(pierces)} pierces, ~{mins:.1f} min  (VERIFY BEFORE CUTTING)")
        fig.savefig(nc.replace(".nc","_preview.png"),dpi=80,bbox_inches="tight"); plt.close(fig)
        json.dump(dict(machine=mname,type=t,sheet=G["name"],sheet_size=list(G["sheet"]),comp=comp,kerf=KF,kerf_src=KSRC,thickness=th,material=mat,tool_dia=m.get("tool_dia"),parts=[pp_["name"] for pp_ in G["parts"]],
            holes=HOLES,tabs=TABS,doc=round(DPP,4),build_id=BID,cut_in=round(cutlen,1),pierces=len(pierces),est_min=round(mins,1),warnings=warn+tooSmall),open(nc.replace(".nc",".json"),"w"))
        print(nc,f"cut {cutlen:.0f}in pierces {len(pierces)} ~{mins:.1f}min",("WARN: "+"; ".join(warn+tooSmall)) if warn or tooSmall else "")

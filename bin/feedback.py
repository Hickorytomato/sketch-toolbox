#!/usr/bin/env python3
"""feedback.py PROJECT "slot tight" | "thread loose" | "dado too tight" | "gap fused" | "kerf 0.07"   (v1.0.5 feature 7: shop learning)
feedback.py PROJECT --coupon thread|pip_gap|slot|dado --pick N      (N = coupon step that fit, from coupons.pdf)
feedback.py PROJECT --coupon kerf_laser|kerf_plasma --measured M    (1.000 in square measured M -> kerf = 1 - M)
feedback.py PROJECT --coupon tol_router|tol_laser|tol_plasma|tol_printer --dia D1,D2,D3,D4 --spacing S1,S2,S3,S4   (v1.0.6 measured tolerance)
feedback.py --list | --undo KEY
Stores the correction per machine+material in bin/learned.json (kept by the installer). Future builds use it in place of
ASSUMED values (values you typed in the spec still win) and print 'SHOP CORRECTION APPLIED' in assumptions.txt, HOW_TO_USE and the gate."""
import sys,os,json,glob,re,subprocess
B=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,B); import learn
ROOT=os.environ.get("SKETCH_ROOT") or os.path.dirname(B)
a=sys.argv[1:]
if not a or a[0] in("-h","--help"): print(__doc__); sys.exit(0)
if a[0]=="--list": print(json.dumps(learn.load(),indent=1)); sys.exit(0)
if a[0]=="--undo":
    L=learn.load(); hit=[k for k,v in L.items() if a[1] in v]
    for k in hit: L[k].pop(a[1]); L[k].setdefault("_log",[]).append(dict(undo=a[1]))
    json.dump(L,open(learn.P,"w"),indent=1); print("removed",a[1],"from",hit or "nothing"); sys.exit(0)
P=a[0] if os.path.isdir(a[0]) else os.path.join(ROOT,a[0]); P=os.path.abspath(P)
vs=sorted([int(x.rsplit("v",1)[1]) for x in glob.glob(f"{P}/v*") if re.search(r"/v\d+$",x) and os.path.exists(f"{x}/parts.json")])
if not vs: print(f"no builds in {P}"); sys.exit(2)
V=f"{P}/v{vs[-1]}"; d=json.load(open(f"{V}/parts.json")); CJ=f"{V}/fab/coupons.json"; C={c["id"]:c for c in json.load(open(CJ))["coupons"]} if os.path.exists(CJ) else {}
KEY={"thread":"thread_clearance_mm","pip_gap":"pip_gap_mm","slot":"slot_clearance_mm","dado":"dado_clear_in"}
def save(c,key,val,why):
    k=learn.put(c["machine"],c["material"],key,val,why); print(f"[learned] {k}: {key} = {val}  ({why}). Next build of anything on {c['machine']} in {c['material']} uses it; rerun design.sh {os.path.basename(P)} --sketch then --final.")
if "--coupon" in a:
    cid=a[a.index("--coupon")+1]
    if cid not in C: print(f"no '{cid}' coupon in {V}/fab/coupons.json (have: {', '.join(C) or 'none'}). Run --final first."); sys.exit(2)
    c=C[cid]
    if cid.startswith("kerf_"):
        m=float(a[a.index("--measured")+1]); mn=c["machine"]
        r=subprocess.run([sys.executable,f"{B}/tools_setup.py","--kerf-test",mn,c["material"],str(c["thickness"]),"--drawn","1.0","--measured",str(m)],capture_output=True,text=True); print(r.stdout.strip() or r.stderr.strip()); sys.exit(r.returncode)
    if cid.startswith("tol_"):   # v1.0.6 measured tolerance: hole sizes + spacings off the tolerance coupon
        try: D=[float(x) for x in a[a.index("--dia")+1].split(",")]; S_=[float(x) for x in a[a.index("--spacing")+1].split(",")]
        except Exception: print(f'give the measurements: --dia D1,D2,D3,D4 --spacing S1,S2,S3,S4 ({c["unit"]})'); sys.exit(2)
        f=1/25.4 if c["unit"]=="mm" else 1.0; dd,sp=c["drawn_dia"],c["drawn_spacing"]
        if any(abs(x-sp)>0.1*sp for x in S_) or any(abs(x-dd)>0.3*dd for x in D):
            print(f"those numbers are far from the drawn {dd} / {sp} {c['unit']}: re-measure (centre to centre spacing, hole diameter)"); sys.exit(2)
        size=max(abs(x-dd) for x in D)*f; pos=max(abs(x-sp) for x in S_)/2*f
        why=f'tolerance coupon on {os.path.basename(P)} v{vs[-1]}: worst hole size error {size:.4f} in, worst position error {pos:.4f} in (x1.25 margin)'
        k=learn.put(c["machine"],"*","tol_pos_in",max(pos*1.25,0.001),why); learn.put(c["machine"],"*","tol_size_in",max(size*1.25,0.001),why)
        print(f"[learned] {k}: tol_pos_in={max(pos*1.25,0.001):.4f} tol_size_in={max(size*1.25,0.001):.4f} ({why}). The cross-machine bolt check uses these from the next --final."); sys.exit(0)
    n=int(a[a.index("--pick")+1])
    if not 1<=n<=len(c["steps"]): print(f"pick 1..{len(c['steps'])}"); sys.exit(2)
    save(c,KEY[cid],c["steps"][n-1],f"{cid} coupon step {n} from {os.path.basename(P)} v{vs[-1]}"); sys.exit(0)
txt=" ".join(a[1:]).lower()
m=re.search(r"kerf\s*([\d.]+)",txt)
if m:
    k=float(m.group(1)); g=[c for c in C.values() if c["id"].startswith("kerf_")]
    if not g: print("this build has no laser/plasma program; for a saw use: tools_setup.py --saw NAME --saw-kerf K"); sys.exit(2)
    c=g[0]; r=subprocess.run([sys.executable,f"{B}/tools_setup.py","--kerf",c["machine"],c["material"],str(c["thickness"]),str(k)],capture_output=True,text=True); print(r.stdout.strip()); sys.exit(r.returncode)
feat=next((f for f,ws in (("thread",("thread","cap","screw on","lid")),("pip_gap",("gap","fused","print in place","hinge")),("dado",("dado","groove","housing")),("slot",("slot","dovetail","slide","press","tab","fit"))) if any(w in txt for w in ws)),None)
sign=+1 if re.search(r"tight|fused|stuck|won.?t (go|fit|turn)|too small|binds",txt) else -1 if re.search(r"loose|wobbl|sloppy|falls? (out|off)|too big|rattl",txt) else 0
if not feat or not sign: print('say which feature and how: e.g. "slot tight", "thread loose", "dado too tight", "gap fused"'); sys.exit(2)
if feat not in C: print(f"this build has no {feat} feature/coupon (have: {', '.join(C) or 'none'})"); sys.exit(2)
c=C[feat]; step=0.0025 if c["unit"]=="in" else 0.1; cur=c["current"]; new=round(max(0.0,cur+sign*step),4)
if c["steps"] and not (c["steps"][0]-1e-9<=new<=c["steps"][-1]+1e-9):
    print(f'{new} is outside the range Sketch can ship for {feat} ({c["steps"][0]}..{c["steps"][-1]} {c["unit"]}): check the real cause (sheet thickness, bit, printer calibration) or set it in the spec yourself.'); sys.exit(2)
save(c,KEY[feat],new,f'"{txt}" on {os.path.basename(P)} v{vs[-1]} ({cur} -> {new}; one coupon step - print the coupon to dial it in exactly)')

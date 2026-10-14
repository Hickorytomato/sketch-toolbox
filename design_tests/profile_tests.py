#!/usr/bin/env python3
"""profile_tests.py: v1.0.6 output profiles. For every profile (and the unknown / unsupported-format fallbacks):
set the owner's machine with tools_setup-style machine_setup, re-package an already-built sample (mixed_table: laser+plasma+router,
print_panels: printer) into a scratch copy, and run the outputs gate. Then break tests: wrong units / Z in a THC program / a
hand-made file in the folder must FAIL. Uses SKETCH_PROFILE so the owner's profile.json is never touched."""
import os,sys,json,glob,shutil,subprocess,tempfile
ROOT=os.environ.get("SKETCH_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B=f"{ROOT}/bin"; PY=sys.executable
sys.path.insert(0,B); import outputs as O
ok=bad=0
def rep(g,m):
    global ok,bad; ok+=bool(g); bad+=not g; print(("ok   " if g else "BAD  ")+m)
def latest(p):
    vs=sorted(glob.glob(f"{ROOT}/design_tests/{p}/v*/fab/HOW_TO_USE.txt"),key=lambda x:int(x.split("/v")[-1].split("/")[0])); return os.path.dirname(os.path.dirname(vs[-1])) if vs else None
T=tempfile.mkdtemp(prefix="proftest_")
def setup(kind,model,sw="",units=None):
    pid,msg=O.match(kind,model,sw); pf=f"{T}/profile.json"
    json.dump({"machine_setup":{kind:dict(model=model,software=sw,profile=pid,msg=msg,**({"units":units} if units else {}))}},open(pf,"w")); return pf,pid,msg
def pack(sample,kind,pf):
    V=latest(sample); W=f"{T}/{sample}_{kind}"; shutil.rmtree(W,ignore_errors=True); shutil.copytree(V,W,symlinks=True)
    env=dict(os.environ,SKETCH_PROFILE=pf,SKETCH_ROOT=ROOT)
    r=subprocess.run([PY,f"{B}/package_machines.py",W,f"{W}/fab","--for",kind],capture_output=True,text=True,env=env)
    return W,r
def gate(W,pf):
    code=f"import sys,json;sys.path.insert(0,'{B}');import pro;R=[];d=json.load(open('{W}/parts.json'));pro.gate_outputs(d,'{W}/fab',lambda a,t,s,m:R.append((s,t,m)));print(json.dumps(R))"
    r=subprocess.run([PY,"-c",code],capture_output=True,text=True,env=dict(os.environ,SKETCH_PROFILE=pf)); 
    try: return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: return [("FAIL","crash",r.stderr[-300:])]
CASES=[("printer","Prusa MK4",""),("printer","Bambu Lab P1S",""),("printer","Bambu A1","OrcaSlicer"),("printer","Ender 3","Cura"),
       ("laser","OMTech 60W","LightBurn"),("laser","Glowforge Pro",""),("laser","xTool S1",""),("laser","Ortur LM3","LaserGRBL"),
       ("plasma","Langmuir Crossfire Pro","FireControl"),("plasma","homebuilt","Mach3"),("plasma","homebuilt","Mach4"),("plasma","homebuilt","LinuxCNC"),("plasma","Crossfire","SheetCAM"),
       ("router","Avid PRO4848","Mach4"),("router","homebuilt","Mach3"),("router","homebuilt","LinuxCNC"),("router","Shapeoko 4","Carbide Motion"),("router","Onefinity","gSender"),
       ("router","x","Fusion"),("router","x","VCarve"),("router","x","Carbide Create"),("router","X-Carve","Easel"),
       ("router","ShopBot Desktop",""),("laser","Trotec Speedy 300",""),("router","homebuilt","Planet CNC")]
seen=set()
for kind,model,sw in CASES:
    pf,pid,msg=setup(kind,model,sw); seen.add(pid)
    sample="print_panels" if kind=="printer" else "mixed_table"
    W,r=pack(sample,kind,pf)
    if r.returncode: rep(False,f"{kind} {model}/{sw}: package_machines crashed: {r.stderr[-200:]}"); continue
    R=gate(W,pf); st=[x[0] for x in R]
    o=O.selected(kind,json.load(open(pf)))
    rep(st and all(s=="PASS" for s in st),f"{kind} {model}/{sw or '-'} -> {o['label']} gate PASS: {R[-1][2][:110] if R else '?'}")
    H=open(f"{W}/fab/HOW_TO_USE.txt").read()
    if msg: rep(msg in H and pid is None,f"   plain fallback said in HOW_TO_USE: {msg[:90]}")
    D=glob.glob(f"{W}/fab/FOR_*_{o['label']}") if kind!="printer" else glob.glob(f"{W}/fab/FOR_3D_PRINTER")
    exts={f.rsplit('.',1)[-1] for f in glob.glob(f"{D[0]}/*")} if D else set()
    rep(D and exts-{"png","txt"} and exts-{"png","txt"}<=set(o["files"])|({o["gcode"].get("ext","nc")} if o.get("gcode") else set()),f"   folder {os.path.basename(D[0]) if D else '?'} has only {sorted(exts)}")
    if o.get("gcode") and kind!="printer":   # break tests on the posted program
        nc=[f for f in glob.glob(f"{D[0]}/*.{o['gcode'].get('ext','nc')}")][0]; t=open(nc).read()
        wrong="G21" if o["gcode"]["units"]=="in" else "G20"; open(nc,"w").write(t.replace("G20" if wrong=="G21" else "G21",wrong))
        R2=gate(W,pf); rep(any(s=="FAIL" and "has" in m_ for s,_,m_ in R2),f"   break: wrong units in {os.path.basename(nc)} -> FAIL")
        open(nc,"w").write(t)
        if o["gcode"].get("noz"):
            open(nc,"w").write(t.replace("M3\n","G0 Z0.15\nM3\n",1)); R2=gate(W,pf); rep(any(s=="FAIL" and "Z moves" in m_ for s,_,m_ in R2),"   break: Z move in THC program -> FAIL"); open(nc,"w").write(t)
    open(f"{D[0]}/handmade.sbp","w").write("SO,1,1\n"); R2=gate(W,pf); rep(any(s=="FAIL" and "handmade.sbp" in m_ for s,_,m_ in R2),"   break: a hand-made .sbp in the folder -> FAIL")
miss=set(O.P)-seen; rep(not miss,f"every output profile gate-tested ({len(O.P)}){': missing '+str(sorted(miss)) if miss else ''}")
# a stale package (folder made for another machine) must FAIL
pf,_,_=setup("laser","Glowforge Pro"); W,_=pack("mixed_table","laser",pf); pf2,_,_=setup("laser","OMTech","LightBurn")
R2=gate(W,pf2); rep(any(s=="FAIL" for s,_,_ in R2),"break: files made for Glowforge but laser now set to LightBurn -> FAIL")
shutil.rmtree(T,ignore_errors=True)
print(f"\nprofile_tests: {ok} ok, {bad} bad"); sys.exit(1 if bad else 0)

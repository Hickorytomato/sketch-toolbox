#!/usr/bin/env python3
"""photo_tests.py (v1.0.6 item 10): photo -> spec.json through bin/import_file.py.
PIL-made images (photo_in/make_images.py): dimensioned hand sketch, napkin (rotated/perspective/blurred, smudged number),
printed drawing with title block, a board with a tape measure. The vision reading is stored as photo_in/<n>.read.json
(what Sketch reads off clean.png). Checks: clean image keeps the dimensions (no crop to a drawn rectangle), original kept for
object photos, fractions parsed, read values src 'read', missing ones assumed AND asked, unclear ones asked, impossible
readings asked, then --sketch builds."""
import os,sys,json,subprocess,shutil,tempfile
ROOT=os.environ.get("SKETCH_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B=f"{ROOT}/bin"; PY=sys.executable
D=f"{ROOT}/design_tests/photo_in"; T=tempfile.mkdtemp(prefix="photo_"); ok=bad=0
def rep(g,m):
    global ok,bad; ok+=bool(g); bad+=not g; print(("ok   " if g else "BAD  ")+m)
def run(*a): return subprocess.run(list(a),capture_output=True,text=True,env=dict(os.environ,SKETCH_ROOT=ROOT))
run(PY,f"{D}/make_images.py") if False else subprocess.run([PY,"make_images.py"],cwd=D,capture_output=True)
from PIL import Image
EXP={"plate_sketch":dict(L=6,W=4,t=0.25,asks=1,assumed=[]),"napkin":dict(L=120,W=80,t=3,asks=2,assumed=[]),
     "printed_drawing":dict(L=300,W=200,t=18,asks=1,assumed=[]),"board_tape":dict(L=24,W=5.7,asks=3,assumed=["t"])}
for n,e in EXP.items():
    f=[x for x in os.listdir(D) if x.startswith(n+".") and not x.endswith(".json")][0]; P=f"{T}/{n}"
    r=run(PY,f"{B}/import_file.py",f"{D}/{f}",P); rep(r.returncode==0 and "READ WITH VISION" in r.stdout,f"{n}: image prepared for reading ({r.stdout.splitlines()[0][:90] if r.stdout else r.stderr[-120:]})")
    c=Image.open(f"{P}/source/read/clean.png"); o=Image.open(f"{D}/{f}")
    if n in("plate_sketch","napkin"): rep(c.width*c.height>0.6*o.width*o.height,f"{n}: clean.png keeps the whole sheet ({c.size} of {o.size}), dimensions not cropped off")
    rep(any(x.startswith("original.") for x in os.listdir(f"{P}/source/read")),f"{n}: original photo kept for reading (tape/ruler, colour)")
    r=run(PY,f"{B}/import_file.py","--from-read",f"{D}/{n}.read.json",P); S=json.load(open(f"{P}/spec.json")); v=S["values"]
    rep(all(abs(v[k]["v"]-e[k])<1e-6 and v[k]["src"]=="read" for k in ("L","W","t") if k in e),f"{n}: L/W/t read ({', '.join(f'{k}={v[k][chr(118)]}' for k in ('L','W','t') if k in v)})")
    rep(all(v[k]["src"]=="assumed" for k in e["assumed"]),f"{n}: missing values assumed: {e['assumed'] or 'none'}")
    asks=[l for l in r.stdout.splitlines() if l.startswith("[ask]")]
    rep(len(asks)==e["asks"] and len(S.get("questions",[]))==e["asks"],f"{n}: {len(asks)} question(s) asked + stored in spec (want {e['asks']})")
    rb=run(f"{B}/design.sh",P,"--sketch"); rep(rb.returncode==0 and os.path.exists(f"{P}/v1/sketch.png"),f"{n}: --sketch builds it")
# break: impossible reading + hole off the part must be asked, not silently built
bad_r={"units":"in","shape":"plate","values":{"L":{"v":"0"},"W":{"v":"3-1/2"},"t":{"v":"1/8"}},"holes":[{"x":19,"y":1,"d":0.25}]}
json.dump(bad_r,open(f"{T}/bad.json","w")); r=run(PY,f"{B}/import_file.py","--from-read",f"{T}/bad.json",f"{T}/bad"); S=json.load(open(f"{T}/bad/spec.json"))
rep(abs(S["values"]["W"]["v"]-3.5)<1e-9 and abs(S["values"]["t"]["v"]-0.125)<1e-9,"fractions '3-1/2' and '1/8' parsed")
rep(S["values"]["L"]["src"]=="assumed" and any("can't be right" in q for q in S["questions"]) and any("falls off" in q for q in S["questions"]),"L=0 and a hole off the part -> assumed + asked")
shutil.rmtree(T,ignore_errors=True); print(f"\nphoto tests: {ok} ok, {bad} bad"); sys.exit(1 if bad else 0)

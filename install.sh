#!/usr/bin/env bash
# Sketch toolbox installer v1.0.6 (fast first sketch: light deps first, heavy tools in the background). Idempotent. Root: $SKETCH_ROOT (default /workspace/sketch).
# Downloads the v1.0.5 release tarball, checks its sha256, installs scripts -> $ROOT/bin and tests -> $ROOT/design_tests,
# keeps your settings, removes scripts that are no longer in this version, sets up the light venv deps, then installs
# PrusaSlicer, Blender and the PDF/video libs in the background (bin/install_heavy.sh; SKETCH_INSTALL_WAIT=1 = wait for them).
set -euo pipefail
VER=1.0.6
URL="https://github.com/Hickorytomato/sketch-toolbox/releases/download/v$VER/sketch-toolbox-$VER.tar.gz"
SHA=f2f438abc670eb282ee4806a18b16b2fef457b9f15cc9427a0cbb09f72dc5999
ROOT=${SKETCH_ROOT:-/workspace/sketch}; mkdir -p "$ROOT/bin" "$ROOT/tools"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
# preflight: free disk space (Blender + PrusaSlicer + python deps ~3.5 GB on a first install)
NEED_MB=3500; { [ -x "$ROOT/tools/blender/blender" ] || ls "$ROOT"/tools/blender*/blender >/dev/null 2>&1; } && [ -e "$ROOT/tools/prusaslicer/AppRun" ] && NEED_MB=500
NEED_MB=${SKETCH_NEED_MB:-$NEED_MB}   # override for testing
for D in "$ROOT" "$TMP"; do
  FREE_MB=$(df -Pm "$D" | awk 'NR==2{print $4}')
  if [ -n "$FREE_MB" ] && [ "$FREE_MB" -lt "$NEED_MB" ]; then
    echo "Not enough disk space to install Sketch's toolbox: it needs about $((NEED_MB/1000)).$(( (NEED_MB%1000)/100 )) GB free on $(df -P "$D" | awk 'NR==2{print $6}'), but only $((FREE_MB/1000)).$(( (FREE_MB%1000)/100 )) GB is free. Free up $(( (NEED_MB-FREE_MB+99)/100/10 )).$(( (NEED_MB-FREE_MB+99)/100%10 )) GB and run it again."; exit 1
  fi
done
echo "downloading sketch-toolbox v$VER"
curl -fsSL -o "$TMP/tb.tar.gz" "$URL"
[ "$(sha256sum "$TMP/tb.tar.gz" | cut -d' ' -f1)" = "$SHA" ] || { echo "toolbox checksum mismatch, not installing"; exit 1; }
python3 - "$TMP/tb.tar.gz" "$ROOT" <<'PY'
import sys,tarfile,os,json
src,root=sys.argv[1],sys.argv[2]
USER=("prices.json","printers.json","machines.json","profile.json","taste.json","stock.json","ref_user.json","learned.json","price_links.json","price_cache.json")   # owner-edited settings (ref_user = shop-reference overrides, learned = feedback.py corrections, price_* = live prices)
saved={}
for f in USER:
    p=os.path.join(root,"bin",f)
    if os.path.exists(p): saved[f]=open(p).read()
t=tarfile.open(src,"r:gz")
new={os.path.basename(m.name) for m in t.getmembers() if m.name.startswith("bin/") and m.isfile()}
binp=os.path.join(root,"bin")
for f in os.listdir(binp):   # drop scripts from older versions
    if f.endswith((".py",".sh",".md")) and f not in new:
        os.remove(os.path.join(binp,f)); print("removed old",f)
t.extractall(root,**({"filter":"data"} if hasattr(tarfile,"data_filter") else {}))
def merge(user,new):   # owner's values always win; only brand-new default keys are added
    if isinstance(user,dict) and isinstance(new,dict):
        out=dict(user)
        for k,v in new.items(): out[k]=merge(user[k],v) if k in user else v
        return out
    return user
for f,txt in saved.items():
    p=os.path.join(binp,f)
    try:
        out=json.dumps(merge(json.loads(txt),json.load(open(p))),indent=1) if os.path.exists(p) else txt   # read the new defaults BEFORE truncating the file
        open(p,"w").write(out)
    except Exception: open(p,"w").write(txt)   # unparseable -> keep owner's file untouched
    print("kept your",f)
for d in (binp,os.path.join(root,"design_tests")):
    for f in os.listdir(d):
        if f.endswith((".py",".sh")): os.chmod(os.path.join(d,f),0o755)
print("scripts ->",binp)
PY
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || python3 -m venv "$ROOT/.venv"
# v1.0.6 FAST FIRST SKETCH: only what design.sh --sketch needs, now; the heavy parts (slicer, Blender renders, video, PDFs) in the background
"$PY" -c "import trimesh,matplotlib,PIL,scipy,ezdxf,shapely,cadquery,manifold3d,rtree,networkx,fast_simplification,pymeshfix" 2>/dev/null || \
  "$PY" -m pip install -q trimesh matplotlib pillow numpy scipy ezdxf shapely cadquery manifold3d rtree networkx fast_simplification pymeshfix
echo "python deps for --sketch ok"
echo "Sketch toolbox ready at $ROOT: design.sh <project> --sketch works now"
if [ "${SKETCH_INSTALL_WAIT:-0}" = 1 ]; then bash "$ROOT/bin/install_heavy.sh"
else
  nohup bash "$ROOT/bin/install_heavy.sh" > "$ROOT/install_heavy.log" 2>&1 < /dev/null &
  echo "heavy tools (PrusaSlicer, Blender, PDF/video libs) installing in the background (pid $!, log $ROOT/install_heavy.log). --show/--final wait for them."
fi

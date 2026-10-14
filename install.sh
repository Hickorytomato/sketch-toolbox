#!/usr/bin/env bash
# Sketch toolbox installer v1.0.5. Idempotent. Root: $SKETCH_ROOT (default /workspace/sketch).
# Downloads the v1.0.5 release tarball, checks its sha256, installs scripts -> $ROOT/bin and tests -> $ROOT/design_tests,
# keeps your settings, removes scripts that are no longer in this version, then sets up the venv, Blender and PrusaSlicer.
set -euo pipefail
VER=1.0.5
URL="https://github.com/Hickorytomato/sketch-toolbox/releases/download/v$VER/sketch-toolbox-$VER.tar.gz"
SHA=afa9d3bb680ba08dc60e6e33e228bb8d605db6012f9dc6271f9460f298a18b8c
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
    try: open(p,"w").write(json.dumps(merge(json.loads(txt),json.load(open(p))),indent=1) if os.path.exists(p) else txt)
    except Exception: open(p,"w").write(txt)   # unparseable -> keep owner's file untouched
    print("kept your",f)
for d in (binp,os.path.join(root,"design_tests")):
    for f in os.listdir(d):
        if f.endswith((".py",".sh")): os.chmod(os.path.join(d,f),0o755)
print("scripts ->",binp)
PY
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || python3 -m venv "$ROOT/.venv"
"$PY" -c "import trimesh,matplotlib,PIL,imageio,reportlab,scipy,ezdxf,shapely,cadquery,rectpack,manifold3d,rtree,networkx,cv2,svgelements,fast_simplification,pymeshfix" 2>/dev/null || \
  "$PY" -m pip install -q trimesh matplotlib pillow numpy imageio reportlab scipy ezdxf shapely cadquery rectpack manifold3d rtree networkx opencv-python-headless svgelements fast_simplification pymeshfix
echo "python deps ok"
BV=4.2.3; BD="$ROOT/tools/blender-$BV-linux-x64"
if [ ! -x "$ROOT/tools/blender/blender" ]; then
  if [ ! -x "$BD/blender" ]; then
    echo "downloading Blender $BV (~350 MB) from download.blender.org"
    curl -fsSL -o "$TMP/b.tar.xz" "https://download.blender.org/release/Blender4.2/blender-$BV-linux-x64.tar.xz"
    if curl -fsSL -o "$TMP/sums" "https://download.blender.org/release/Blender4.2/blender-$BV.sha256"; then
      want=$(grep "linux-x64.tar.xz" "$TMP/sums" | cut -d' ' -f1); got=$(sha256sum "$TMP/b.tar.xz" | cut -d' ' -f1)
      [ -z "$want" ] || [ "$want" = "$got" ] || { echo "Blender checksum mismatch"; exit 1; }
    fi
    python3 -c "import tarfile,sys;t=tarfile.open(sys.argv[1]);t.extractall(sys.argv[2],**({'filter':'tar'} if hasattr(tarfile,'tar_filter') else {}))" "$TMP/b.tar.xz" "$ROOT/tools"
  fi
  ln -sfn "blender-$BV-linux-x64" "$ROOT/tools/blender"
fi
"$ROOT/tools/blender/blender" -b --version 2>/dev/null | head -1 || echo "WARNING: Blender won't start; renders fall back to clay (turntable.py)"
# PrusaSlicer 2.8.1 (last release with a Linux AppImage) for desk-model slicing; sha256 pinned
PSU="https://github.com/prusa3d/PrusaSlicer/releases/download/version_2.8.1/PrusaSlicer-2.8.1%2Blinux-x64-newer-distros-GTK3-202409181416.AppImage"
PSH=565f2f4bd4dbb05904a459d54db1916b6932124709c1d17b5aacfe9f5f2f1b03
if [ ! -x "$ROOT/tools/prusaslicer/AppRun" ]; then
  echo "downloading PrusaSlicer 2.8.1 (~100 MB)"
  if curl -fsSL -o "$TMP/ps.AppImage" "$PSU" && [ "$(sha256sum "$TMP/ps.AppImage" | cut -d' ' -f1)" = "$PSH" ]; then
    chmod +x "$TMP/ps.AppImage"; (cd "$TMP" && ./ps.AppImage --appimage-extract >/dev/null) && rm -rf "$ROOT/tools/prusaslicer" && mv "$TMP/squashfs-root" "$ROOT/tools/prusaslicer"
  else echo "WARNING: PrusaSlicer download/checksum failed; 3D-print slicing disabled"; fi
fi
if [ -x "$ROOT/tools/prusaslicer/AppRun" ] && ! "$ROOT/tools/prusaslicer/AppRun" --help >/dev/null 2>&1; then
  sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y -q -o Dpkg::Options::=--force-confold libwebkit2gtk-4.1-0 >/dev/null 2>&1 \
    || echo "WARNING: PrusaSlicer needs libwebkit2gtk-4.1-0 (install with your package manager); slicing disabled until then"
fi
command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg missing (needed for MP4s). Install it with your package manager."
command -v pdftoppm >/dev/null || echo "WARNING: poppler-utils (pdftotext/pdftoppm) missing: PDF import disabled until installed."
echo "Sketch toolbox ready at $ROOT"

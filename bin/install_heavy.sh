#!/usr/bin/env bash
# install_heavy.sh: the slow part of the install (v1.0.6), run in the background by install.sh. Status in $ROOT/.heavy_install:
# "running <pid>" while it works, then "done" (or "failed: <why>"). design.sh --show/--final wait for "done"; --sketch never waits.
set -uo pipefail
B=$(cd "$(dirname "$0")" && pwd); ROOT=${SKETCH_ROOT:-$(dirname "$B")}; PY="$ROOT/.venv/bin/python"; TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ST="$ROOT/.heavy_install"; echo "running $$" > "$ST"
fail(){ echo "failed: $*" > "$ST"; echo "HEAVY INSTALL FAILED: $*"; exit 1; }
"$PY" -c "import imageio,reportlab,rectpack,cv2,svgelements" 2>/dev/null || "$PY" -m pip install -q imageio reportlab rectpack opencv-python-headless svgelements || fail "pip (imageio reportlab rectpack opencv svgelements)"
echo "python deps ok"
BV=4.2.3; BD="$ROOT/tools/blender-$BV-linux-x64"
if [ ! -x "$ROOT/tools/blender/blender" ]; then
  if [ ! -x "$BD/blender" ]; then
    echo "downloading Blender $BV (~350 MB) from download.blender.org"
    curl -fsSL -o "$TMP/b.tar.xz" "https://download.blender.org/release/Blender4.2/blender-$BV-linux-x64.tar.xz"
    if curl -fsSL -o "$TMP/sums" "https://download.blender.org/release/Blender4.2/blender-$BV.sha256"; then
      want=$(grep "linux-x64.tar.xz" "$TMP/sums" | cut -d' ' -f1); got=$(sha256sum "$TMP/b.tar.xz" | cut -d' ' -f1)
      [ -z "$want" ] || [ "$want" = "$got" ] || fail "Blender checksum mismatch"
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
echo done > "$ST"; echo "heavy tools ready"

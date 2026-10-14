#!/usr/bin/env bash
# design.sh <project_dir> [--sketch | --show | --final [--for printer,laser,plasma,router,hand]]      THREE GATED STAGES - never jump ahead unless the user asks.
#  STAGE 1  --sketch (default; --preview is an alias): spec.json -> NEW vN: model + sketch.png (4-angle rough 3D, Blender workbench)
#           + before/after strip + quick facts + assumptions. ~5-10 s. No concept art, spin, replay, slicing, drawings or files.
#           Iterate: spec.py set ... then --sketch again. Ask "ready for the next step?" when they like it.
#  STAGE 2  --show: on the LATEST sketched version (rebuilds a new vN only if spec.json changed): photoreal hero.png + spin.mp4
#           (hero first ~15 s; spin.mp4 = 2 slow laps, renders in background ~70 s; replay.mp4 only with WOW_REPLAY=1), wearer review. No concept art unless asked. No production files. Ask "ready for the build files?" when they approve the look.
#  STAGE 3  --final: on the latest version: dimensioned drawing, STL/3MF/G-code, STEP, DXF + nesting + plasma/laser/router G-code,
#           cope templates, hand-tool plan, drawings.pdf, BOM, quote, cut list, zip. (Reuses stage-2 hero/spin if present.)
#           + FOR_<machine>/ folders (package_machines.py): 3MF/G-code/STL for PrusaSlicer/Bambu/Orca/Cura, LightBurn SVG/DXF (cut/engrave/score
#           colors), SheetCAM/Fusion DXF + .nc for plasma/router, build_plan.pdf for hand tools (tools, cut list, drawings, steps, 1:1 templates)
#           and HOW_TO_USE.txt. Ask which machines/software first; default = machines.json enabled + hand. --for or SKETCH_FOR overrides.
#  ALL OUTPUTS ARE ESTIMATES - verify before cutting/printing.
set -e
B=$(cd "$(dirname "$0")" && pwd); R=${SKETCH_ROOT:-$(dirname "$B")}; export SKETCH_ROOT=$R; PY=$R/.venv/bin/python
P=$1; [ -d "$P" ] || P=$R/$1; P=$(cd "$P" && pwd); [ -f "$P/spec.json" ] || { echo "no spec.json in $P"; exit 2; }
MODE=${2:---sketch}; [ "$MODE" = "--preview" ] && MODE=--sketch
case "$MODE" in --sketch|--show|--final) ;; *) echo "unknown mode $MODE (use --sketch | --show | --final)"; exit 2;; esac
L=0; for d in "$P"/v*/; do x=$(basename "$d"); x=${x#v}; [[ "$x" =~ ^[0-9]+$ ]] && [ -f "$d/model.glb" ] && [ "$x" -gt "$L" ] && L=$x; done
NEW=1; if [ "$MODE" = --show ] || [ "$MODE" = --final ]; then
  [ "$L" -gt 0 ] && cmp -s "$P/spec.json" "$P/v$L/spec.json" && NEW=0
  [ "$L" = 0 ] && echo "[design] no sketch yet - run stage 1 first: design.sh $(basename $P) --sketch" && exit 5
fi
if [ $NEW = 1 ]; then n=1; while [ -d "$P/v$n" ]; do n=$((n+1)); done; else n=$L; fi
V=$P/v$n; mkdir -p "$V"; cp "$P/spec.json" "$V/spec.json"
log(){ echo "[design v$n ${MODE#--}] $*"; }
if [ $NEW = 1 ]; then
  [ "$MODE" != --sketch ] && log "spec.json changed since v$L -> rebuilding model as v$n"
  log "model from spec"; $PY $B/spec_build.py $V/spec.json $V > $V/build.log 2>&1 || { tail -5 $V/build.log; log "MODEL BUILD FAILED - fix spec.json (see $V/build.log); nothing else was generated"; exit 4; }; grep -v -i warn $V/build.log | tail -1
  echo '{"kind":"spec"}' > $V/params.json
fi
if [ "$MODE" = "--sketch" ]; then
  T0=$(date +%s.%N); log "quick 3D sketch (4 angles, workbench) - stage 1 of 3"
  $PY $B/sketch3d.py $V/model.glb $V/sketch.png --size ${SKETCH_SIZE:-360} --title "$(basename $P) v$n - rough 3D sketch (stage 1 of 3)" >/dev/null 2>$V/sketch.log || log "sketch render failed (see $V/sketch.log)"
  touch $V/.sketch
  $PY - "$P" "$n" <<'PYX'
import json,sys,os,glob
from PIL import Image,ImageDraw
P,n=sys.argv[1],int(sys.argv[2]); V=f"{P}/v{n}"; d=json.load(open(f"{V}/parts.json")); S=json.load(open(f"{V}/spec.json"))
import trimesh; m=trimesh.util.concatenate([trimesh.load(f) for f in glob.glob(f"{V}/stl/*.stl")]); e=m.extents; U=S.get("units","mm")   # unrotated parts
warn=[]
if d.get("print_parts"):
    B_=os.environ.get("SKETCH_ROOT","")+"/bin/printers.json"; pr=json.load(open(B_)) if os.path.exists(B_) else {}
    key=S["values"].get("printer",{}).get("v") or pr.get("active"); bed=pr.get("printers",{}).get(key,{}).get("bed")
    for pp in d["print_parts"]:
        ex=sorted(trimesh.load(f'{V}/{pp["stl"]}').extents)
        if bed and not (ex[2]<=max(bed[:2]) and ex[1]<=min(bed[:2]) and ex[0]<=bed[2]): warn.append(f'{pp["name"]} {ex[2]:.0f}x{ex[1]:.0f}x{ex[0]:.0f} mm does NOT fit the {key} bed {bed} -> final will split it (tell the user / offer to resize)')
pv=[x for x in range(n-1,0,-1) if os.path.exists(f"{P}/v{x}/sketch.png")]
if pv and os.path.exists(f"{V}/sketch.png"):   # before -> after strip so the user sees exactly what changed
    a,b=[Image.open(f).convert("RGB").crop((0,30,Image.open(f).width,30+Image.open(f).width//2)) for f in (f"{P}/v{pv[0]}/sketch.png",f"{V}/sketch.png")]; h=min(a.height,b.height)
    a,b=a.resize((a.width*h//a.height,h)),b.resize((b.width*h//b.height,h)); c=Image.new("RGB",(a.width+b.width+8,h+28),"white")
    c.paste(a,(0,28)); c.paste(b,(a.width+8,28)); dr=ImageDraw.Draw(c); dr.text((8,8),f"v{pv[0]} (before)",fill="black"); dr.text((a.width+16,8),f"v{n} (now)",fill="black"); c.save(f"{V}/before_after.png")
g=sum(p["volume_mm3"] for p in d.get("print_parts",[]))/1000*1.25*0.6
last=(S.get("history") or [{}])[-1].get("change","first build")
print(f'[sketch] v{n}: {d.get("title")} | overall {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} {U} | weight ~{d["total_weight_lb"]} lb'+(f' | ~{g:.0f} g filament (rough, pre-slice)' if g else '')+f' | change: {last}')
a=[f'{k}={v["v"]}' for k,v in S["values"].items() if v.get("src") not in("user","read")]
print("[assumptions] "+", ".join(a)); [print("[WARN] "+w) for w in warn]; print(f"[send] {V}/sketch.png"+(f" + {V}/before_after.png" if pv else ""))
print("[next] Stage 1 of 3 (rough 3D sketch). Ask your 2-3 questions, iterate with spec.py set + --sketch. When they like it, ask: 'Ready for the next step? I'll make a photoreal picture and spin video.' -> design.sh <project> --show")
PYX
  log "stage-1 time: $(echo "$(date +%s.%N) - $T0" | bc 2>/dev/null || python3 -c "import time;print(round(time.time()-$T0,1))") s (render+facts, after model)"
  exit 0
fi
export SKETCH_STEPS=$V/steps.json
if [ "$MODE" = "--show" ]; then
  log "photoreal hero (~15 s) - stage 2 of 3"; rm -f $V/spin.mp4 $V/.spin_done; $PY $B/render_real.py $V/model.glb $V --nospin --size 720 --herosamples 32 >/dev/null 2>&1 || log "hero render failed"
  log "spin.mp4 rendering in background (~70 s, 2 slow laps) -> $V/spin.mp4 (wait: until [ -f $V/.spin_done ]; do sleep 5; done)"
  ( $PY $B/render_real.py $V/model.glb $V --spinonly --size 540 --samples 8 --frames 48 --lap 7 >$V/spin.log 2>&1; touch $V/.spin_done ) </dev/null >/dev/null 2>&1 &
  [ -n "$WOW_WAIT" ] && wait
  if [ -n "$WOW_REPLAY" ]; then log "build replay (opt-in: WOW_REPLAY=1)"; $PY $B/build_replay.py $V/model.glb $V >/dev/null 2>&1 || log "replay failed"; fi
  WF=""; [ -f "$P/wearer.json" ] && WF="--facts $P/wearer.json"
  if [ -n "$WF" ] || grep -q '"wearer"' "$P/geom.json" 2>/dev/null; then log "wearer review"; set +e; $PY $B/review.py $P $V $WF | sed -n 3p; RV=${PIPESTATUS[0]}; set -e
    [ "$RV" = 3 ] && log "REVIEW: REVISION REQUIRED - fix the low scores (see $V/review.md), go back to --sketch, before showing the user"; fi
  touch $V/.show
  echo "[send] $V/hero.png NOW. Then spin.mp4 when $V/.spin_done exists (~70 s): $V/spin.mp4$( [ -f $V/replay.mp4 ] && echo " + $V/replay.mp4")"
  echo "[next] Stage 2 of 3 (the look). When they approve it, ask: 'Ready for the build files? I'll make the print/cut files, drawings, cut list and price estimate.' -> design.sh <project> --final"
  exit 0
fi
[ ! -f $V/hero.png ] && log "note: no stage-2 hero for v$n (look not shown yet) - building files anyway because --final was asked for"
log "drawing (dimensioned from spec)"; $PY $B/spec_drawing.py $V >/dev/null; cp $V/drawing.png $V/shop_drawing.png
F=$V/fab; mkdir -p $F/step; cp $V/step/*.step $V/assembly.step $V/model.stl $F/step/ 2>/dev/null || true
[ -f $V/hero.png ] && cp $V/hero.png $F/; cp $V/drawing.png $V/assumptions.txt $V/spec.json $F/; rm -f $F/drawing_2.png; [ -f $V/drawing_2.png ] && cp $V/drawing_2.png $F/; [ -f $V/replay.mp4 ] && cp $V/replay.mp4 $F/; [ -f $V/spin.mp4 ] && cp $V/spin.mp4 $F/
# split flats by material class -> nesting + G-code on the right machines
$PY - "$V" <<'PYX'
import json,sys
V=sys.argv[1]; d=json.load(open(f"{V}/parts.json"))
W=("plywood","baltic_birch","mdf","wood","hardwood","pine","cedar"); A=("acrylic",)
for cls,keep in (("metal",lambda m:m not in W+A),("wood",lambda m:m in W),("acrylic",lambda m:m in A)):
    fl=[f for f in d["flats"] if keep(f.get("material","steel"))]
    if fl: json.dump(dict(d,flats=fl),open(f"{V}/_flats_{cls}.json","w"))
PYX
for cls in metal wood acrylic; do
  J=$V/_flats_$cls.json; [ -f $J ] || continue
  case $cls in metal) MC=plasma; GM="plasma laser";; wood) MC=router; GM="router laser";; acrylic) MC=laser; GM="laser router";; esac
  EN=$($PY -c "import json,sys;M=json.load(open('$B/machines.json'));print(' '.join(m for m in sys.argv[1:] if M.get(m,{}).get('enabled')))" $GM)
  [ -n "$EN" ] && GM=$EN || { log "$cls flats: none of [$GM] enabled in machines.json -> DXF + drawings + hand-tool plan only"; GM=""; }
  log "$cls flats: DXF, true-shape nesting ($MC), G-code (${GM:-none})"
  $PY $B/export_dxf.py $J $F/dxf_$cls >/dev/null
  $PY $B/nest.py $J $F/nest_$cls --machine $MC | sed 's/^/      /'
  [ -n "$GM" ] && $PY $B/gcode.py $F/nest_$cls/nest.json $F/gcode_$cls $GM | sed 's/^/      /'
  rm -f $J
done
if $PY -c "import json,sys;d=json.load(open('$V/parts.json'));sys.exit(0 if any(j.get('type')=='cope' for j in d['joints']) else 1)"; then log "cope templates"; $PY $B/cope.py $V/parts.json $F/cope_templates.pdf >/dev/null; fi
if $PY -c "import json,sys;sys.exit(0 if json.load(open('$V/parts.json')).get('print_parts') else 1)"; then log "3D print: checks, split, slice, 3MF"; $PY $B/print3d.py $V $F/print | sed 's/^/      /'; fi
if [ "$($PY -c "import json;print(json.load(open('$V/parts.json')).get('domain'))")" = wood ]; then $PY $B/wood_plan.py $V $F/hand_tool_plan.txt >/dev/null; fi
log "drawings.pdf, BOM, quote, sanity"; $PY $B/fabdocs.py $V $F >/dev/null
FOR=""; [ "$3" = "--for" ] && FOR="--for $4"; [ -n "$SKETCH_FOR" ] && FOR="--for $SKETCH_FOR"
log "per-machine packages + HOW_TO_USE.txt ${FOR:-(machines.json enabled + hand)}"; $PY $B/package_machines.py $V $F $FOR | sed 's/^/      /'
cat > $F/README.txt <<TXT
START WITH HOW_TO_USE.txt: one FOR_<machine>/ folder per machine/program you use, and which file goes into which program.
Build package generated by Sketch from $(basename $P)/v$n (spec.json included; assumptions.txt lists every value Sketch guessed).
EVERYTHING HERE IS AN ESTIMATE AND NEEDS HUMAN VERIFICATION BEFORE CUTTING, WELDING OR PRINTING: check drawing.png/drawings.pdf,
simulate and dry-run all G-code (kerf, feeds, heights, M-codes are generic), check prints in your own slicer, treat prices/hours as rough.
TXT
cp $V/review.md $V/review.png $F/ 2>/dev/null || true
Z=$V/$(basename $P)_v${n}_fab.zip; rm -f "$Z"; (cd $F && $PY -c "import shutil,sys;shutil.make_archive(sys.argv[1][:-4],'zip','.')" "$Z")
$PY - "$V" <<'PYX'
import json,sys,os
V=sys.argv[1]; d=json.load(open(f"{V}/parts.json")); q=json.load(open(f"{V}/fab/quote.json"))
a=[f'{k}={v["v"]}{v.get("unit","")}' for k,v in d["spec_values"].items() if v["src"] not in("user","read")]
r=[f'{k}={v["v"]}{v.get("unit","")}' for k,v in d["spec_values"].items() if v["src"]=="read"]
if r: print("[read from drawing/file - confirm] "+", ".join(r))
print(f'[summary] {d.get("title")}: weight ~{d["total_weight_lb"]} lb, material ~${q["material_est"]}, quote ~${q["price_est"]} (estimates)')
pj=f"{V}/fab/print/print.json"
if os.path.exists(pj):
    for r in json.load(open(pj))["parts"]:
        for p in r["pieces"]: print(f'[print] {p["name"]}: {p.get("time")}, {p.get("grams")} g, ~${p.get("cost")} filament')
print("[assumptions to confirm] "+(", ".join(a) if a else "none"))
PYX
log "package: $Z ($(du -h "$Z" | cut -f1))"
echo "[next] Stage 3 of 3 done. Send drawing.png, offer the zip, say plainly every number and G-code is an estimate to check before cutting/printing."

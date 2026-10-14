#!/usr/bin/env bash
# v1.0.6 fast first sketch: --sketch must work while the heavy tools are still installing.
# Simulates the install in progress: .heavy_install says "running", Blender is hidden, and the heavy python libs
# (cv2, reportlab, imageio, rectpack, svgelements) raise ImportError. Then --final must wait and say so, not crash.
cd "$(dirname "$0")/.."; R=$(pwd); ok=0; bad=0
rep(){ if [ "$1" = 0 ]; then echo "ok   $2"; ok=$((ok+1)); else echo "BAD  $2"; bad=$((bad+1)); fi; }
T=$(mktemp -d); mkdir -p $T/stub; for m in cv2 reportlab imageio rectpack svgelements; do echo "raise ImportError('$m still installing')" > $T/stub/$m.py; done
HS=$R/.heavy_install; OLD=$(cat $HS 2>/dev/null || true); sleep 600 & SP=$!; echo "running $SP" > $HS
mkdir -p design_tests/_fast && cp design_tests/salt_shaker/spec.json design_tests/_fast/ && rm -rf design_tests/_fast/v*
S=$(date +%s%N); out=$(PYTHONPATH=$T/stub SKETCH_NO_BLENDER=1 bin/design.sh design_tests/_fast --sketch 2>&1); rc=$?; E=$(( ($(date +%s%N)-S)/1000000 ))
rep $rc "--sketch while heavy tools install: rc=$rc in ${E} ms"
[ -s design_tests/_fast/v1/sketch.png ]; rep $? "sketch.png written ($(stat -c%s design_tests/_fast/v1/sketch.png 2>/dev/null) bytes)"
.venv/bin/python -c "from PIL import Image;im=Image.open('design_tests/_fast/v1/sketch.png');assert im.width>=700,im.size" ; rep $? "sketch.png is full size (2x2 tiles + title + dimensions)"
echo "$out" | grep -q "waiting for them" ; [ $? != 0 ]; rep $? "--sketch did not wait on the heavy install"
out2=$(SKETCH_HEAVY_WAIT_S=6 bin/design.sh design_tests/_fast --final 2>&1); rc2=$?
[ $rc2 = 6 ] && echo "$out2" | grep -q "still installing"; rep $? "--final during the heavy install waits and then says so plainly (rc=$rc2)"
kill $SP 2>/dev/null; wait $SP 2>/dev/null
out3=$(SKETCH_HEAVY_WAIT_S=6 bin/design.sh design_tests/_fast --final 2>&1); rc3=$?
echo "$out3" | grep -q "installer stopped"; rep $? "installer died -> --final says so instead of hanging (rc=$rc3)"
if [ -n "$OLD" ]; then echo "$OLD" > $HS; else rm -f $HS; fi
rm -rf design_tests/_fast $T
echo "fast sketch tests: $ok ok, $bad bad"; [ $bad = 0 ]

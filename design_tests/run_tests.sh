#!/usr/bin/env bash
# 3 plain-sentence tests: stage 1 from the first ask (assumptions flagged), one mid-conversation change -> v2 sketch, then stage 3 files.
set -e; cd "$(dirname "$0")/.."; P=.venv/bin/python; B=${SKETCH_BIN:-bin}
t(){ bin=$B; $bin/design.sh design_tests/$1 --sketch; $P $bin/spec.py set design_tests/$1 "${@:2}"; $bin/design.sh design_tests/$1 --sketch; $bin/design.sh design_tests/$1 --final --for printer,laser,plasma,router,hand; }
t phone_holder phone_w=82 phone_t=14 filament=PETG     # "my phone is 82 mm wide in a 14 mm case, print it in PETG"
t plywood_shelf width=42 shelves=4                     # "make it 42 inches wide with 4 shelves"
t plant_stand H=24 ang=2x2x1/4                         # "make it 24 tall and beef it up to 2x2x1/4 angle"
t salt_shaker holes=6 neck_d=28                       # "give it 6 holes and a wider neck" (round/cone/shell/threads/hole pattern)
t belt_rig plate_h=64 dt_clear=0.35                   # "make the plate 64 tall, looser slide" (arc_plate, dovetail, cutters, path, ring, link)
echo "ALL TESTS PASSED"
echo "now: design_tests/ship_tests.sh (ship gate)"

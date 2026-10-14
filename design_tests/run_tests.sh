#!/usr/bin/env bash
# 3 plain-sentence tests: stage 1 from the first ask (assumptions flagged), one mid-conversation change -> v2 sketch, then stage 3 files.
set -e; cd "$(dirname "$0")/.."; P=.venv/bin/python; B=${SKETCH_BIN:-bin}
t(){ bin=$B; $bin/design.sh design_tests/$1 --sketch; $P $bin/spec.py set design_tests/$1 "${@:2}"; $bin/design.sh design_tests/$1 --sketch; $bin/design.sh design_tests/$1 --final --for printer,laser,plasma,router,hand; }
t phone_holder phone_w=82 phone_t=14 filament=PETG     # "my phone is 82 mm wide in a 14 mm case, print it in PETG"
t plywood_shelf width=42 shelves=4                     # "make it 42 inches wide with 4 shelves"
t plant_stand H=24 ang=2x2x1/4                         # "make it 24 tall and beef it up to 2x2x1/4 angle"
echo "ALL TESTS PASSED"

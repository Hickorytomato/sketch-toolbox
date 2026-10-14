#!/usr/bin/env bash
# Ship-gate tests (v1.0.3). Each must PASS or be BLOCKED exactly as listed. Run from the toolbox root after run_tests.sh.
cd "$(dirname "$0")/.."; P=.venv/bin/python; ok=0; bad=0
want(){ exp=$1; p=$2; bin/design.sh design_tests/$p --sketch >/dev/null 2>&1; out=$(bin/design.sh design_tests/$p --final 2>&1); rc=$?
  if [ $exp = pass ] && [ $rc = 0 ]; then echo "OK   $p ships"; ok=$((ok+1));
  elif [ $exp = block ] && [ $rc = 3 ] && echo "$out" | grep -q "$3"; then echo "OK   $p blocked: $(echo "$out" | grep -m1 "\[FAIL\]" | sed 's/^ *//' | cut -c1-150)"; ok=$((ok+1));
  else echo "BAD  $p (expected $exp, exit $rc)"; echo "$out" | grep -E "\[FAIL\]|Error" | head -5; bad=$((bad+1)); fi; }
want pass  vase_relief                       # relief overlaps the vase, petals 1.6 mm -> fused + thickened to 2 mm
want block vase_float  "floating piece"      # same + a bit 3 mm off the wall
want pass  hinge_pip_05                      # print_in_place, 0.5 mm gap
want block hinge_pip_03 "under the 0.5 mm"   # 0.3 mm gap fuses while printing
want block hinge_unflagged "floating piece"  # same hinge without the print_in_place flag
want pass  laser_tag                         # 1.3 mm slots / 1.5 mm holes: the 2 mm rule is print-only
want pass  salt_shaker; want pass belt_rig; want pass plywood_shelf   # existing samples still ship (tamper test reuses plywood_shelf)
$P design_tests/ship_tamper_test.py || bad=$((bad+1))
echo "ship tests: $ok ok, $bad bad"; [ $bad = 0 ]

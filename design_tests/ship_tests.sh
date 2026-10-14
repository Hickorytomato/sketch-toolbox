#!/usr/bin/env bash
# Ship-gate tests (v1.0.3 + v1.0.4 shop rules). Each must PASS or be BLOCKED exactly as listed. Run from the toolbox root after run_tests.sh.
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
want pass  lumber_shelf                      # v1.0.4: 2x4/2x8 shelf, actual sizes, buy list with saw kerf, screw length rule
want pass  steel_bracket                     # v1.0.4: welded plate bracket, weld schedule (side/filler/prep), 1/2 bolt holes from the table -> DRILL
want pass  bent_tab                          # v1.0.4: bent 10 ga tab, flat blank from BA (K estimate), hole-to-bend 2.5T+R
want pass  plant_stand                       # welded angle stand
want block ply_nominal "23/32"               # 3/4 plywood drawn at 0.750 nominal
$P design_tests/ship_tamper_test.py || bad=$((bad+1))
$P design_tests/rules_tests.py | tail -1; [ ${PIPESTATUS[0]} = 0 ] || bad=$((bad+1))   # every new FAIL rule: break blocks, clean ships
echo "ship tests: $ok ok, $bad bad"; [ $bad = 0 ]

# Sketch toolbox
Root $SKETCH_ROOT (default /workspace/sketch). Python: .venv/bin/python. Blender 4.2: tools/blender/blender. PrusaSlicer: tools/prusaslicer.
Chat can't open HTML: send sketch.png / hero.png / spin.mp4 (+ model.stl). EVERY number, price and G-code is an ESTIMATE.

## Flow: spec.json -> three gated stages (wait for the user's OK between them)
1. Onboarding: `tools_setup.py --have printer[,laser,router,plasma,saw,welder,hand] --printer <key> --filament PLA`
   -> machines.json, printers.json, profile.json. Printer only = printed parts in mm.
2. Write `<project>/spec.json` (examples: design_tests/*/spec.json): `values` {v, src user|assumed|read, unit, note}, `derived` "=expr",
   `parts` (kit kind, args, features, rot, at, group, repeat), `joints` (dado, rabbet, groove, lap, finger, mortise_tenon, miter, cope,
   bolted, screws, glue, welded), `dims`, optional `print`, `render_rot`, `steps`. Unstated values are "assumed" and listed back.
3. `design.sh <project> --sketch` (default, ~5 s): new vN + sketch.png (4-angle workbench), before_after.png, facts, assumptions, bed-fit WARN.
   `design.sh <project> --show`: hero.png (~15 s), spin.mp4 in background (2 slow laps, ~70 s; WOW_WAIT=1 waits), wearer review.
   WOW_REPLAY=1 adds replay.mp4 (captioned build replay).
   `design.sh <project> --final [--for printer,laser,plasma,router,hand]` (or SKETCH_FOR): drawing.png, fab/ + zip: STEP/STL, DXF,
   true-shape nesting, G-code per machine, print G-code + 3MF, cope templates, hand-tool plan, drawings/BOM/quote PDFs, sanity.txt,
   FOR_<machine>/ folders + HOW_TO_USE.txt. Store-bought materials (dowel, rod, pipe, hardware) go on the shopping list, not the slicer.
4. Changes: `spec.py set <project> k=v ...` (user value) | `assume` | `note` | `show`, then --sketch again. Never hand-edit model files.

## Scripts
spec_build.py + kit.py   spec -> CadQuery solids, model.glb (parts named preset__name), STEP, parts.json, steps.json
sketch3d.py              stage-1 workbench sketch          render_real.py  photoreal hero/spin (--look, --finish, --fill, --cutout)
props.py                 bottle(), belt(), mannequin(), save() for believable scenes (never depict real people)
review.py                wearer review (PROJECT/wearer.json or geom.json "wearer"); exit 3 = REVISION REQUIRED, fix before showing
spec_drawing.py          dimensioned hidden-line drawing     fabdocs.py  drawings.pdf, BOM, quote, build steps, sanity
export_dxf.py, nest.py, gcode.py   flats -> DXF -> nested sheets -> plasma/laser/router .nc (starting points only)
print3d.py               checks, orientation, split to bed with pins, PrusaSlicer G-code + 3MF, time/grams/cost (printers.json)
cope.py, wood_plan.py    pipe cope templates, hand-tool plan          package_machines.py  FOR_<machine>/ folders
import_file.py FILE PROJECT   STEP/IGES/STL/3MF/OBJ -> spec; DXF/SVG -> profile flat (--t, --domain); PDF/photo -> cleaned images:
                         read them with vision, write read.json, then `import_file.py --from-read read.json PROJECT`. Read values are src "read".
from_photo.py composite PHOTO RENDER OUT  (render with --cutout first)   taste.py show|add kept|rejected <cat> "<v>"|set units
build_replay.py, render_views.py, steps.py  build replay    turntable.py  clay fallback if Blender fails
Settings (kept on reinstall): prices.json, printers.json, machines.json, profile.json, stock.json, taste.json.

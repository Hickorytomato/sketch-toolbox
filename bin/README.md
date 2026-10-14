# Sketch toolbox
Root $SKETCH_ROOT (default /workspace/sketch). Python: .venv/bin/python. Blender 4.2: tools/blender/blender. PrusaSlicer: tools/prusaslicer.
Chat can't open HTML: send sketch.png / hero.png / spin.mp4 (+ model.stl). EVERY number, price and G-code is an ESTIMATE.

## Flow: spec.json -> three gated stages (wait for the user's OK between them)
1. Onboarding: `tools_setup.py --have printer[,laser,router,plasma,saw,welder,hand] --printer <key> --filament PLA`
   -> machines.json, printers.json, profile.json. Printer only = printed parts in mm.
2. Write `<project>/spec.json` (examples: design_tests/*/spec.json): `values` {v, src user|assumed|read, unit, note}, `derived` "=expr",
   `parts` (kit kind, args, features, rot, at, group, repeat, cut_from), `joints` (dado, rabbet, groove, lap, finger, mortise_tenon, miter, cope,
   bolted, screws, glue, welded), `dims`, optional `print`, `render_rot`, `steps`. Unstated values are "assumed" and listed back.
3. `design.sh <project> --sketch` (default, ~5 s): new vN + sketch.png (4-angle workbench), before_after.png, facts, assumptions, bed-fit WARN.
   `design.sh <project> --show`: hero.png (~15 s), spin.mp4 in background (2 slow laps, ~70 s; WOW_WAIT=1 waits), wearer review.
   WOW_REPLAY=1 adds replay.mp4 (captioned build replay).
   `design.sh <project> --final [--for printer,laser,plasma,router,hand]` (or SKETCH_FOR): drawing.png, fab/ + zip: STEP/STL, DXF,
   true-shape nesting, G-code per machine, print G-code + 3MF, cope templates, hand-tool plan, drawings/BOM/quote PDFs, sanity.txt,
   FOR_<machine>/ folders + HOW_TO_USE.txt. Store-bought materials (dowel, rod, pipe, hardware) go on the shopping list, not the slicer.
4. Changes: `spec.py set <project> k=v ...` (user value) | `assume` | `note` | `show`, then --sketch again. Never hand-edit model files.

## Kit kinds added in v1.0.1 (see kit.py docstrings; samples design_tests/salt_shaker, belt_rig)
round / cylinder / cone   revolved parts: segments [{h,r1,r2}] or profile [[r,z]], wall (hollow shell) + open/floor, threads
                          [{side external|internal, r (neck/root radius, same on both mates), z, pitch, turns, depth, clearance 0.4}],
                          holes [{face top|bottom, d, n, pcd, center, depth}], side_holes [{n,d,z,h}], knurl {n,depth}
prism (any 2D outline + rounded corners, any plane)   dovetail (rail; clear>0 = slot cutter)   path (stroke along polyline/spline: clips)
arc_plate (curved/rolled plate)   ring (torus eyelet, flat)   link (chain link)
cut_from: ["part",..] on ANY part = negative body subtracted from those parts (tunnels, windows, keyholes, dovetail slots).

## Scripts
spec_build.py + kit.py   spec -> CadQuery solids, model.glb (parts named preset__name), STEP, parts.json, steps.json
sketch3d.py              stage-1 workbench sketch          render_real.py  photoreal hero/spin (--look, --finish, --fill, --cutout)
props.py                 bottle(), belt(), mannequin(), save() for believable scenes (never depict real people)
review.py                wearer review (PROJECT/wearer.json or geom.json "wearer"); exit 3 = REVISION REQUIRED, fix before showing
spec_drawing.py          dimensioned hidden-line drawing     fabdocs.py  drawings.pdf, BOM, quote, build steps, sanity
export_dxf.py, nest.py, gcode.py   flats -> DXF -> nested sheets -> plasma/laser/router .nc (starting points only)
print3d.py               checks, orientation, split to bed with pins, bed packing (plate_<n> per bed, --per-part/--both), PrusaSlicer G-code + 3MF, time/grams/cost (printers.json)
cope.py, wood_plan.py    pipe cope templates, hand-tool plan          package_machines.py  FOR_<machine>/ folders
ship.py PROJECT           THE SHIP GATE (run by design.sh --final): fuse/1 body/2 mm print walls/flat base/bed/slicer, drawings vs model,
                         closed+kerfed cut files inside the sheet, BOM=model, shopping list, cost sources, hand plan -> vN/ship/ + manifest
                         + send_list.txt + zip.  ship.py --verify FILE: was this file shipped?  ship.py --check-print STL: gate one mesh.
meshfuse.py IN OUT       union overlapping shells into one solid (used by ship.py and kind custom_stl)
custom_stl (spec kind)   a mesh the bot generated itself (relief, ornament): {kind: custom_stl, args:{file: x.stl}, group: <body>} -> gated like every part.
                         Print-in-place moving parts: "assembly": "print_in_place", "bodies": [names] (gap >= 0.5 mm, printers.json pip_clearance_mm)
import_file.py FILE PROJECT   STEP/IGES/STL/3MF/OBJ -> spec; DXF/SVG -> profile flat (--t, --domain); PDF/photo -> cleaned images:
                         read them with vision, write read.json, then `import_file.py --from-read read.json PROJECT`. Read values are src "read".
from_photo.py composite PHOTO RENDER OUT  (render with --cutout first)   taste.py show|add kept|rejected <cat> "<v>"|set units
build_replay.py, render_views.py, steps.py  build replay    turntable.py  clay fallback if Blender fails
Settings (kept on reinstall): prices.json, printers.json, machines.json, profile.json, stock.json, taste.json.

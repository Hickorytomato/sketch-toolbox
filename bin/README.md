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

## Shop rules (v1.0.4: bin/ref/ + rules.py)
bin/ref/shop_reference.json (tap/clearance, lumber actual, ply 23/32, weld prep, filler, pipe OD, tolerances, hazards...),
bin/ref/kerf_table.json (Hypertherm PM45XP cut chart by material/thickness/amps; CO2/fiber laser kerf ranges) and
bin/ref/failure_modes.json (the 247-item research catalog) - every value with its source. Your overrides go in bin/ref_user.json
({"shop_reference":{...},"kerf_table":{...}}), merged over the defaults and KEPT by the installer.
Kerf, in this order: your test cut (`tools_setup.py --kerf-test plasma steel 0.25 --drawn 2 --measured 1.938`, or `--kerf m mat t k`)
> kerf table > machines.json default; every program and plan says which one it used. Saw kerf for cut lists: `tools_setup.py --saw "table saw" [--saw-kerf 0.125]`.
Generation: spec_build -> rules.enrich (build id, title block + process tolerances, finish per row, lumber actual, pipe NPS/sch/OD,
weld schedule side/filler/prep/WPS note, bolt holes from the clearance/tap table, bent_plate blanks, engineer/code flags, lumber buy plan with kerf);
gcode.py (table kerf, DRILL small/fit holes, 60% hole feed, router tabs + depth-per-pass limit); fabdocs (title block every sheet, hole callouts,
weld symbols from the model side, masking); wood_plan (shop plan for every build). ship.py runs rules.gate: every geometry/file/plan-text catalog
item is a check at the catalog's FAIL/WARN severity. `rules.py --coverage` lists checks / advice / skipped with reasons.
New kit kind: bent_plate (a,b,W,t,R,K,holes_a,holes_b,wb,relief_w,relief_d). Joints: bolted without d takes the table clearance (tapped:true -> tap drill);
screws/nails with through+into get the length rule checked. Dims may carry tol / fit / fit_class.

## Scripts
spec_build.py + kit.py   spec -> CadQuery solids, model.glb (parts named preset__name), STEP, parts.json, steps.json
sketch3d.py              stage-1 workbench sketch          render_real.py  photoreal hero/spin (--look, --finish, --fill, --cutout)
props.py                 bottle(), belt(), mannequin(), save() for believable scenes (never depict real people)
review.py                wearer review (PROJECT/wearer.json or geom.json "wearer"); exit 3 = REVISION REQUIRED, fix before showing
spec_drawing.py          dimensioned hidden-line drawing     fabdocs.py  drawings.pdf, BOM, quote, build steps, sanity
export_dxf.py, nest.py, gcode.py   flats -> DXF -> nested sheets -> plasma/laser/router .nc (starting points only)
print3d.py               checks, orientation, split to bed with pins, bed packing (plate_<n> per bed, --per-part/--both), PrusaSlicer G-code + 3MF, time/grams/cost (printers.json)
cope.py, wood_plan.py    pipe cope templates, shop plan (lumber buy list with kerf, weld schedule, tips)
rules.py, ref.py, kerf.py  shop rules (generation + ship gate), reference data + overrides, kerf lookup          package_machines.py  FOR_<machine>/ folders
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


## Pro outputs (v1.0.5) - all go through the ship gate and into send_list.txt (phone PNG + PDF)
- **Cut day** (`cutday.py`, saw/stock builds): 1D stock plan from stock lengths with your saw kerf, 2D guillotine sheet plan
  (RIP strips with the grain, then crosscuts, then trim rips), numbered cuts tagged with the BOM marks (A1, A2 ...), tick-off
  checklist, offcut list -> `cut_day.pdf`, `cut_day-N.png`, `offcuts.csv`.
- **Fit-test coupons** (`coupons.py`): thread rings (c-0.2/c/c+0.2 mm), print-in-place gap gauge, slot gauge, dado step gauge,
  laser/plasma kerf comb, saw-kerf card -> `coupons.pdf`, `coupons-N.png`, `coupons/*.stl|dxf`. Each says how to read it and
  the command to store the result.
- **Shop learning** (`feedback.py PROJECT --coupon thread --pick 3` or `feedback.py PROJECT "slot tight"`): stored per
  machine|material in `bin/learned.json` (kept on reinstall), used for ASSUMED values in later builds (values you typed win);
  every build says which corrections it applied (assumptions.txt, HOW_TO_USE.txt, gate). `feedback.py --list | --undo KEY`.
- **Customer quote** (`customer_quote.py`): materials (with sources), hardware, machine time (slicer / G-code x
  machines.json shop machine_rate_per_h), labor, margin, tax, lead time, valid-until, terms. Shop name/logo/address/drawn-by only
  from `tools_setup.py --shop name=... logo=... tax_pct=...`; none set = neutral quote. Always stamped ESTIMATE.
- **Live prices** (`prices_live.py`, off by default: `tools_setup.py --live-prices on`): reads the price from supplier product
  pages you list in `bin/price_links.json` (JSON-LD / itemprop / og:price), with store, link and 'as of' date; cache 7 days
  (`bin/price_cache.json`), robots.txt, 3 s between requests, 12 per build; failure = prices.json price, labelled. Home Depot /
  Lowe's / Menards search pages block automated reads, so they are given as search links only (never scraped, never faked).
- **Shop drawings**: every sheet has part, Rev letter (v1=A, v2=B ...), date, units, scale, tolerance block, drawn-by (profile
  shop.drawn_by or blank), "Sheet i of N"; a revision table auto-diffed against the previous version; weld callout sheet
  (W1.., AWS A2.4-style symbols from the model, WPS tail).
- **Exploded build steps** (`explode.py`): Blender workbench, one picture per assembly step, BOM-tagged parts, assembled into
  build_steps.pdf with a parts legend. About 1.4-1.9 s total (Blender start included) for 3-4 steps at 720 px on the box.

## v1.0.6
- **Whole stock bought** (buy.py): quote, shopping list and bom_quote.pdf price full boards/sticks, whole sheets and plate drops, with the offcut left over. Gate `buy`.
- **Sketch defaults flagged**: any rate/price that is still Sketch's default carries `[SKETCH DEFAULT - not your price yet]` and a red * on the quote, and a line in HOW_TO_USE. Set yours: `python3 bin/tools_setup.py --rates` (interactive) or `--rates labor_rate=65 margin_pct=20 price_per_ft.2x4=0.95 confirm=all`. Live prices stay link mode; links are exact product searches ("2 in. x 4 in. x 8 ft. lumber").
- **Exploded steps**: labels never overlap (leader lines when moved). Gate `explode`.
- **Measured tolerance**: `tol_<machine>` coupon for cross-machine bolted joints; `bin/feedback.py P --coupon tol_laser --dia D1,..,D4 --spacing S1,..,S4`; the cross-machine check then uses it.
- **Relief/emboss**: kit kind `relief_vase` (text and/or image heightmap displaced on the vase mesh, emboss + or deboss -). Sample design_tests/vase_emboss.
- **AWS A2.4 weld symbols**: fillet, V/bevel/square/U/J groove, both sides, size/length, angle, root, all-around, field weld, back weld, break arrow; text like "1/4 bevel groove 45 deg, root 1/8, field weld" or "CJP V-groove 60 deg, back weld". Sample design_tests/steel_groove.
- **Your exact machine + software**: `bin/tools_setup.py --machine router "Shapeoko 4" --software "Carbide Motion" [--units mm]` (or `--machines` to be asked). Output profiles (bin/outputs.py): PrusaSlicer, Bambu Studio, OrcaSlicer, Cura; LightBurn, Glowforge, xTool Creative Space, LaserGRBL; Langmuir FireControl, Mach3/Mach4/LinuxCNC (plasma + router), GRBL; Fusion, VCarve, SheetCAM, Carbide Create, Easel. Unknown software or a format Sketch can't write (ShopBot .sbp, Trotec/Epilog jobs, Ruida .rd...) -> said plainly, plain DXF/SVG/STL instead. Gate `outputs`; design_tests/profile_tests.py.
- **Load note**: anything that holds weight (shelf, stand, seat, bracket, rack, hook, or weight mentioned) gets "Not load-rated. Test it before trusting it with weight or people." in HOW_TO_USE and on every drawing sheet. Gate `load`.

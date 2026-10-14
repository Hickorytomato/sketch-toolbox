# sketch-toolbox

The toolbox behind **Sketch**, a maker's bot that bridges digital and physical: you describe a thing, Sketch
talks it through with a quick 3D sketch, shows a photoreal look, then produces the software that runs the
hardware: 3D-printer G-code/3MF, laser and plasma/router cut files, and printable hand-tool build plans,
plus drawings, cut and shopping lists and a ballpark cost.

This repo is only the scripts Sketch runs. Each copy of Sketch installs them on first run with `install.sh`
(pinned to a release tag and checked by sha256). Blender and PrusaSlicer are downloaded from their official sources.

- `bin/` the scripts (start with `bin/README.md` and `bin/design.sh`)
- `design_tests/` three sample projects; `design_tests/run_tests.sh` runs all three stages on them
- `install.sh` installer (`SKETCH_ROOT` defaults to `/workspace/sketch`; your prices/printers/machines/profile/taste/stock settings are kept on reinstall)

**All files, numbers and G-code are estimates. Test before trusting:** check dimensions, simulate or dry-run
G-code, and start with a cheap test piece before cutting or printing anything that matters.

MIT licensed. No keys or accounts needed.

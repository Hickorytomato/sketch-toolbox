#!/usr/bin/env python3
"""package_machines.py VDIR FABDIR [--for printer,laser,plasma,router,hand]
STAGE 3: re-package the build files per machine / program the owner actually uses, plus HOW_TO_USE.txt (which file goes into
which program). Default --for = machines enabled in bin/machines.json (+ hand, always).
  FOR_3D_PRINTER/  plate_<n>.3mf/.gcode (packed beds) + <part>.3mf (PrusaSlicer project WITH Sketch's settings; Bambu Studio & Orca open it, re-slice there), <part>.gcode
                   (PrusaSlicer, Marlin-flavor, for the configured printer only), <part>.stl (Cura / any slicer)
  FOR_LASER_LightBurn/  <part>.svg (true size, inches; layer colors: red=CUT, black fill=ENGRAVE, blue=SCORE) + .dxf (same layers/ACI colors)
                   + laser .nc if made
  FOR_PLASMA_SheetCAM_Fusion/, FOR_ROUTER_SheetCAM_Fusion/  per-part + nested-sheet DXF (inches, CUT/HOLES/POCKET layers) + .nc
  FOR_HAND_TOOLS/  build_plan.pdf = tools list + cut list + dimensioned drawings + build steps + 1:1 templates (+ cope templates)
"""
import sys,os,json,glob,shutil,subprocess
B=os.path.dirname(os.path.abspath(__file__))
a=sys.argv[1:]; V,F=a[0],a[1]; FOR=None
if "--for" in a: FOR=[x.strip() for x in a[a.index("--for")+1].split(",") if x.strip()]
M=json.load(open(f"{B}/machines.json")); d=json.load(open(f"{V}/parts.json"))
if not FOR: FOR=[k for k,v in M.items() if isinstance(v,dict) and v.get("enabled") and k in("printer","laser","plasma","router")]+["hand"]
[shutil.rmtree(x) for x in glob.glob(f"{F}/FOR_*")]
flats=d.get("flats",[]); prints=d.get("print_parts",[]); how=[]; made=[]
def cp(srcs,dst):
    os.makedirs(dst,exist_ok=True); n=0
    for s in srcs:
        for f in glob.glob(s): shutil.copy(f,dst); n+=1
    return n
# ---------- printer
if "printer" in FOR and prints:
    D=f"{F}/FOR_3D_PRINTER"; cp([f"{F}/print/*.3mf",f"{F}/print/*.gcode",f"{F}/print/*.stl",f"{F}/print/print_report.txt",f"{F}/print/print_preview.png",f"{F}/print/plate_*.png"],D); made.append(D)
    pr=M.get("printer",{})
    how+=["3D PRINTER  (FOR_3D_PRINTER/)",
     "  plate_<n>.*:   one file per print bed, parts already packed (plate_<n>.png shows the layout). <part>.stl = single parts (per-part .3mf/.gcode too when built with print3d.py --per-part or --both).",
     "  PrusaSlicer:   open <part>.3mf -> Sketch's settings (filament, layer, infill, supports, orientation) load with it. Check, then Slice.",
     "  Bambu Studio / OrcaSlicer: open <part>.3mf (geometry + orientation come in), pick YOUR printer + filament profile, Slice. Do not send the .gcode to a Bambu.",
     "  Cura:          open <part>.stl, set the material/infill listed in print_report.txt, Slice.",
     f"  <part>.gcode:  ready only for the configured printer ({pr.get('slicer','prusaslicer')}, {pr.get('bed_mm')} mm bed, {pr.get('nozzle')} mm nozzle). Any other printer: re-slice.",""]
# ---------- flats: laser svg/dxf, plasma/router dxf
def svg(f,path):
    xs=[p[0] for p in f["outer"]]; ys=[p[1] for p in f["outer"]]; x0,y0,W,H=min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys); m=0.1
    P=lambda pts:"M"+" L".join(f"{x-x0+m:.4f},{H-(y-y0)+m:.4f}" for x,y in pts)+" Z"
    o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W+2*m:.4f}in" height="{H+2*m:.4f}in" viewBox="0 0 {W+2*m:.4f} {H+2*m:.4f}">',
       '<g id="CUT" stroke="#FF0000" fill="none" stroke-width="0.005">',f'<path d="{P(f["outer"])}"/>']
    for ip in f.get("inner_poly",[]): o.append(f'<path d="{P(ip)}"/>')
    for x,y,r in f.get("holes",[]): o.append(f'<circle cx="{x-x0+m:.4f}" cy="{H-(y-y0)+m:.4f}" r="{r:.4f}"/>')
    o.append('</g><g id="ENGRAVE" fill="#000000" stroke="none">')
    for pk in f.get("pockets",[]):
        pts=pk.get("pts") if isinstance(pk,dict) else pk
        if pts: o.append(f'<path d="{P(pts)}"/>')
    o.append('</g><g id="SCORE" stroke="#0000FF" fill="none" stroke-width="0.005">')
    for ln in f.get("scores",[]): o.append(f'<path d="M{ln[0][0]-x0+m:.4f},{H-(ln[0][1]-y0)+m:.4f} L{ln[1][0]-x0+m:.4f},{H-(ln[1][1]-y0)+m:.4f}"/>')
    o.append('</g></svg>'); open(path,"w").write("\n".join(o))
dx=lambda: glob.glob(f"{F}/dxf_*/*.dxf")
if flats and "laser" in FOR:
    D=f"{F}/FOR_LASER_LightBurn"; os.makedirs(D,exist_ok=True); made.append(D)
    for f in flats: svg(f,f"{D}/{f['name']}.svg")
    import ezdxf
    for p in dx():
        doc=ezdxf.readfile(p)
        for nm,c in (("CUT",1),("HOLES",1),("POCKET",7),("ENGRAVE",7),("SCORE",5)):
            if nm in doc.layers: doc.layers.get(nm).color=c
        doc.saveas(f"{D}/{os.path.basename(p)}")
    cp([f"{F}/gcode_*/*_laser.nc",f"{F}/gcode_*/*_laser_preview.png"],D)
    how+=["LASER  (FOR_LASER_LightBurn/)",
     "  LightBurn: File > Import <part>.svg (true size in inches) or <part>.dxf. Layers come in by color: RED = Cut (holes + outline),",
     "  BLACK fill = Engrave, BLUE = Score. Set power/speed per layer for your material, check Preview, frame, then cut.",
     "  *_laser.nc: generic G-code for a G-code laser controller only (not LightBurn/Ruida). Simulate before running.",""]
for mc,name,cls in (("plasma","PLASMA",["metal"]),("router","ROUTER",["wood","acrylic"])):
    if mc in FOR and any(glob.glob(f"{F}/dxf_{c}/*.dxf") for c in cls):
        D=f"{F}/FOR_{name}_SheetCAM_Fusion"; made.append(D)
        cp(sum([[f"{F}/dxf_{c}/*.dxf",f"{F}/nest_{c}/sheet_*.dxf",f"{F}/nest_{c}/*.png",f"{F}/gcode_{c}/*_{mc}.nc",f"{F}/gcode_{c}/*_{mc}_preview.png"] for c in cls],[]),D)
        how+=[f"{name}  (FOR_{name}_SheetCAM_Fusion/)",
         "  SheetCAM / Fusion (Manufacture) / Mach / FireControl: import the DXFs (units = INCHES). Layers: CUT = outline, HOLES = holes,",
         "  POCKET = pocket/engrave. sheet_*.dxf = all parts already nested on your sheet. Let YOUR CAM add kerf/lead-ins and post for your machine.",
         f"  *_{mc}.nc: generic G-code straight from Sketch (kerf/feeds from machines.json). Use only after simulating and a dry run.",""]
# ---------- hand tools: one printable PDF
if "hand" in FOR:
    D=f"{F}/FOR_HAND_TOOLS"; os.makedirs(D,exist_ok=True); made.append(D)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    dom=d.get("domain"); tools={"metal":["Tape measure, square, soapstone/scribe","Metal-cutting saw or abrasive chop saw (miters)","Angle grinder: cut-off + flap disc",
          "Drill + bits for each hole size below","Welder (MIG/stick) + clamps, magnets","Safety: glasses, gloves, helmet, hearing protection"],
          "wood":["Tape measure, square, pencil","Circular/table/hand saw","Drill/driver + bits below","Clamps, wood glue, sandpaper","Safety glasses, hearing protection"]}.get(dom,
          ["3D printer (or print service)","Flush cutters, deburr tool","Drill + bits below (for screws)","Screwdriver"])
    hs=sorted({round(2*h[2],4) for f in flats for h in f.get("holes",[])}); U="in" if dom!="print" and not prints else "mm"
    if hs: tools.append("Hole sizes: "+", ".join(f'{x:g} {U}' for x in hs))
    with PdfPages(f"{D}/_cover.pdf") as pdf:
        fig=plt.figure(figsize=(8.5,11)); y=.95
        def t(s,sz=10,b=False):
            global y; fig.text(.07,y,s,fontsize=sz,weight="bold" if b else "normal",family="monospace" if not b else None); y-=.022*sz/10
        t(f"BUILD PLAN - {d.get('title')}",16,True); y-=.01; t("All numbers are estimates. Check every dimension against the drawings before cutting.",8)
        y-=.015; t("TOOLS",12,True); [t("  [ ] "+x) for x in tools]; y-=.015; t("CUT LIST",12,True)
        for c in d.get("cutlist",[]): t(f"  [ ] {c.get('mark','')} {c.get('part','')[:22]:22} x{c.get('qty',1):<3} {c.get('material','')[:18]:18} {c.get('length','')}  {c.get('notes','')}"[:100],8)
        if flats: t("  Plates: 1:1 templates at the back: "+", ".join(f["name"] for f in flats),8)
        for p in prints: t(f"  [ ] {p.get('name','')} - 3D printed part"[:100],8)
        y-=.015; t("CONTENTS",12,True); [t("  "+x) for x in ["This page: tools + cut list","Dimensioned drawings","Step-by-step build steps","1:1 templates (print at 100% / Actual size; check the 1 in / 25 mm box)"]]
        pdf.savefig(fig); plt.close(fig)
    # 1:1 tiled templates for flats (letter pages, 0.5 in margins, 0.25 in overlap)
    tp=[]
    if flats:
        sc=1 if U=="in" else 1/25.4
        with PdfPages(f"{D}/_templates.pdf") as pdf:
            for f in flats:
                xs=[p[0]*sc for p in f["outer"]]; ys=[p[1]*sc for p in f["outer"]]; x0,y0=min(xs),min(ys); W,H=max(xs)-x0,max(ys)-y0; pw,ph=7.5,10; nx,ny=int(W//(pw-.25))+1,int(H//(ph-.25))+1
                for j in range(ny):
                    for i in range(nx):
                        fig=plt.figure(figsize=(8.5,11)); ax=fig.add_axes([.5/8.5,.5/11,pw/8.5,ph/11]); ax.set_xlim(0,pw); ax.set_ylim(0,ph); ax.set_aspect("equal"); ax.axis("off")
                        ox,oy=x0+i*(pw-.25),y0+j*(ph-.25); ax.plot([p[0]*sc-ox for p in f["outer"]],[p[1]*sc-oy for p in f["outer"]],"k-",lw=.8)
                        for ip in f.get("inner_poly",[]): ax.plot([p[0]*sc-ox for p in ip],[p[1]*sc-oy for p in ip],"k-",lw=.8)
                        for x,yy,r in f.get("holes",[]):
                            ax.add_patch(plt.Circle((x*sc-ox,yy*sc-oy),r*sc,fill=False,lw=.6)); ax.plot([x*sc-ox-.1,x*sc-ox+.1],[yy*sc-oy]*2,"k-",[x*sc-ox]*2,[yy*sc-oy-.1,yy*sc-oy+.1],"k-",lw=.4)
                        ax.add_patch(plt.Rectangle((.1,.1),1,1,fill=False,lw=.5)); ax.text(.15,.55,"1 in" if U=="in" else "1 in\n(25.4mm)",fontsize=6)
                        ax.plot([0,pw,pw,0,0],[0,0,ph,ph,0],":",color="gray",lw=.4)
                        fig.text(.06,.97,f"1:1 TEMPLATE {f['name']}  page {j*nx+i+1}/{nx*ny} (col {i+1}, row {j+1}) - print at 100%, overlap 1/4 in, tape on dotted lines",fontsize=7)
                        pdf.savefig(fig); plt.close(fig)
        tp=[f"{D}/_templates.pdf"]
    parts=[f"{D}/_cover.pdf"]+[p for p in (f"{F}/drawings.pdf",f"{F}/build_steps.pdf") if os.path.exists(p)]+tp+([f"{F}/cope_templates.pdf"] if os.path.exists(f"{F}/cope_templates.pdf") else [])
    subprocess.run(["pdfunite"]+parts+[f"{D}/build_plan.pdf"],check=True); [os.remove(p) for p in (f"{D}/_cover.pdf",*tp)]
    cp([f"{F}/bom.csv",f"{F}/hand_tool_plan.txt"],D)
    how+=["HAND TOOLS  (FOR_HAND_TOOLS/)",
     "  build_plan.pdf: print it. Page 1 = tools checklist + cut list; then dimensioned drawings, step-by-step build, and 1:1 templates.",
     "  Print templates at 100% / 'Actual size' (NOT 'fit to page') and measure the 1 in box before tracing or punching holes.",""]
how+=["CAD  (step/): .step opens in Fusion, SolidWorks, Onshape, FreeCAD; model.stl in anything.","",
      "EVERYTHING IS AN ESTIMATE: simulate G-code, dry-run, check prints in your slicer, verify dimensions before cutting."]
open(f"{F}/HOW_TO_USE.txt","w").write(f"WHICH FILE GOES INTO WHICH PROGRAM - {d.get('title')}\nPackaged for: {', '.join(FOR)}\n\n"+"\n".join(how)+"\n")
for m_ in made: print("[machine]",m_)
print("[howto]",f"{F}/HOW_TO_USE.txt")

"""outputs.py - v1.0.6 output profiles: the owner's exact machine + software (tools_setup.py --machine) picks what Sketch writes.
Each profile lists the ONLY file types Sketch makes for it, the G-code flavor/units/extension when it takes G-code, and how to load it.
Unknown software, or a format Sketch can't write (ShopBot .sbp, Trotec/Epilog print-driver jobs, Ruida .rd, Glowforge-native...):
say so plainly and fall back to plain DXF/SVG/STL that any CAM opens. Never a hand-made imitation of a format we don't write."""
import os,re,json
B=os.path.dirname(os.path.abspath(__file__))
P={
 # 3D printers: slicers take 3MF/STL; G-code only for the PrusaSlicer-configured printer
 "prusaslicer":   dict(kind="printer",label="PrusaSlicer",files=["3mf","gcode","stl"],gcode=dict(flavor="marlin2",units="mm"),how="open <part>.3mf in PrusaSlicer (settings included), check, Slice; .gcode only fits the configured printer"),
 "bambu_studio":  dict(kind="printer",label="BambuStudio",files=["3mf","stl"],how="open <part>.3mf in Bambu Studio, pick YOUR printer + filament, Slice, send. Sketch does not write Bambu G-code"),
 "orcaslicer":    dict(kind="printer",label="OrcaSlicer",files=["3mf","stl"],how="open <part>.3mf in OrcaSlicer, pick your printer profile, Slice"),
 "cura":          dict(kind="printer",label="Cura",files=["stl"],how="open <part>.stl in Cura, set material/infill from print_report.txt, Slice"),
 # lasers
 "lightburn":     dict(kind="laser",label="LightBurn",files=["svg","dxf"],how="File > Import <part>.svg (true size) or .dxf; layers by color: red=cut, black=engrave, blue=score"),
 "glowforge":     dict(kind="laser",label="Glowforge",files=["svg"],how="upload <part>.svg at app.glowforge.com (true size in inches); set each color step to Cut/Engrave/Score"),
 "xtool_cs":      dict(kind="laser",label="xToolCreativeSpace",files=["svg","dxf"],how="xTool Creative Space: Import <part>.svg or .dxf, set Cut/Engrave/Score per color"),
 "lasergrbl":     dict(kind="laser",label="LaserGRBL",files=["nc","svg"],gcode=dict(flavor="grbl",units="mm",ext="nc"),how="LaserGRBL: File > Open <sheet>_laser.nc (GRBL, mm); or import the .svg"),
 # plasma
 "firecontrol":   dict(kind="plasma",label="FireControl",files=["nc","dxf"],gcode=dict(flavor="firecontrol",units="in",ext="nc",noz=True),how="Langmuir FireControl: File > Open <sheet>_plasma.nc (inches, no Z: torch height is your THC). Run the simulator first. Or SheetCAM/Fusion with the Langmuir post from the DXF"),
 "mach3_plasma":  dict(kind="plasma",label="Mach3",files=["tap","dxf"],gcode=dict(flavor="mach3",units="in",ext="tap",noz=True),how="Mach3: File > Load G-code <sheet>_plasma.tap; check THC settings; simulate, dry run"),
 "mach4_plasma":  dict(kind="plasma",label="Mach4",files=["tap","dxf"],gcode=dict(flavor="mach4",units="in",ext="tap",noz=True),how="Mach4: File > Load G-code <sheet>_plasma.tap; simulate, dry run"),
 "linuxcnc_plasma":dict(kind="plasma",label="LinuxCNC",files=["ngc","dxf"],gcode=dict(flavor="linuxcnc",units="in",ext="ngc",noz=True),how="LinuxCNC/QtPlasmaC: open <sheet>_plasma.ngc; preview, dry run"),
 # routers
 "mach3":         dict(kind="router",label="Mach3",files=["tap","dxf"],gcode=dict(flavor="mach3",units="in",ext="tap"),how="Mach3: File > Load G-code <sheet>_router.tap; zero X/Y at the sheet corner, Z at the top of the stock; simulate, air cut"),
 "mach4":         dict(kind="router",label="Mach4",files=["tap","dxf"],gcode=dict(flavor="mach4",units="in",ext="tap"),how="Mach4: File > Load G-code <sheet>_router.tap; zero as above; simulate, air cut"),
 "linuxcnc":      dict(kind="router",label="LinuxCNC",files=["ngc","dxf"],gcode=dict(flavor="linuxcnc",units="in",ext="ngc"),how="LinuxCNC (AXIS/Probe Basic): open <sheet>_router.ngc; check the preview, air cut"),
 "grbl":          dict(kind="router",label="GRBL",files=["nc","dxf"],gcode=dict(flavor="grbl",units="mm",ext="nc"),how="GRBL sender (Carbide Motion, gSender, UGS, CNCjs): load <sheet>_router.nc (mm); zero at the sheet corner, top of stock; air cut"),
 # CAM software: give geometry, let their CAM make toolpaths
 "fusion":        dict(kind="cam",label="Fusion",files=["dxf","step"],how="Fusion: insert the DXF (sketch) or open the .step, make toolpaths in Manufacture, post for your machine"),
 "vcarve":        dict(kind="cam",label="VCarve",files=["dxf","svg"],how="VCarve/Aspire: File > Import vectors <part>.dxf (inches), make toolpaths, save with your machine's post"),
 "sheetcam":      dict(kind="cam",label="SheetCAM",files=["dxf"],how="SheetCAM: File > Import drawing sheet_*.dxf (inches), layers CUT/HOLES/POCKET; post with your machine's post"),
 "carbide_create":dict(kind="cam",label="CarbideCreate",files=["svg","dxf"],how="Carbide Create: Import <part>.svg or .dxf, add toolpaths, save G-code"),
 "easel":         dict(kind="cam",label="Easel",files=["svg"],how="Easel: Import > SVG, set cut depths, carve"),
}
# names people type -> profile id (machine model or software)
ALIAS=[(r"bambu|\bx1c?\b|\bp1[ps]\b|\ba1\b",'bambu_studio'),(r"orca",'orcaslicer'),(r"prusa|\bmk[34]|\bxl\b|\bmini\b|core one",'prusaslicer'),(r"cura|ender|creality|anycubic|elegoo",'cura'),
 (r"lightburn|ruida|omtech|thunder|boss laser",'lightburn'),(r"glowforge",'glowforge'),(r"xtool|creative space",'xtool_cs'),(r"lasergrbl|ortur|atomstack|sculpfun",'lasergrbl'),
 (r"fire ?control|langmuir|crossfire|razorweld",'firecontrol'),(r"qtplasmac|plasmac",'linuxcnc_plasma'),
 (r"linuxcnc|probe basic",'linuxcnc'),(r"mach ?4",'mach4'),(r"mach ?3",'mach3'),(r"grbl|shapeoko|onefinity|carbide motion|gsender|\bugs\b|cncjs|x-?carve|longmill|sienci",'grbl'),
 (r"fusion",'fusion'),(r"vcarve|aspire|vectric",'vcarve'),(r"sheetcam",'sheetcam'),(r"carbide create",'carbide_create'),(r"easel",'easel')]
# formats Sketch does NOT write (said plainly, never faked)
UNSUP={r"shopbot|\.sbp|opensbp":"ShopBot .sbp (OpenSBP)",r"trotec|ruby":"Trotec Ruby job files",r"epilog":"Epilog print-driver jobs",r"\.rd\b|rdworks":"Ruida .rd files",
       r"\.lbrn":"LightBurn project files (.lbrn2)",r"\.gfx|glowforge native":"Glowforge-native files",r"hypertherm|phd":"Hypertherm EDGE/Phoenix programs",r"\.crv|vcarve project":"VCarve project files (.crv)",r"heidenhain|\.h\b|fanuc macro":"Heidenhain/Fanuc conversational programs"}
FALLBACK={"printer":["stl"],"laser":["svg","dxf"],"plasma":["dxf"],"router":["dxf","svg"]}
def profile():
    p=os.environ.get("SKETCH_PROFILE") or f"{B}/profile.json"
    return json.load(open(p)) if os.path.exists(p) else {}
def match(kind,model="",software=""):
    """-> (profile_id or None, message). Software beats model. An unsupported-format ask gets a plain answer + fallback."""
    t=f"{software} {model}".lower()
    for rx,fmt in UNSUP.items():
        if re.search(rx,t): return None,f"Sketch can't write {fmt}. Using plain {'/'.join(x.upper() for x in FALLBACK[kind])} instead: open those in your machine's own software/CAM."
    for src in (software,model):
        for rx,pid in ALIAS:
            if src and re.search(rx,src.lower()):
                if kind=="plasma" and pid in("mach3","mach4","linuxcnc"): pid=pid+"_plasma"
                if kind=="laser" and pid=="grbl": pid="lasergrbl"
                if P[pid]["kind"] in (kind,"cam"): return pid,""
    if not (model or software): return None,""
    return None,f'Sketch has no output profile for "{(software or model).strip()}". Using plain {"/".join(x.upper() for x in FALLBACK[kind])} instead (any CAM or machine software opens these). Sketch does not guess at other formats.'
def selected(kind,prof=None):
    """-> dict(id, label, files, gcode, how, model, software, msg) for this machine kind, or None if the owner never said."""
    s=(prof if prof is not None else profile()).get("machine_setup",{}).get(kind)
    if not s: return None
    pid=s.get("profile"); msg=s.get("msg","")
    if pid in P:
        o=dict(P[pid]); g=dict(o.get("gcode") or {})
        if g and s.get("units") in("in","mm"): g["units"]=s["units"]
        o.update(id=pid,gcode=g or None,model=s.get("model",""),software=s.get("software",""),msg=msg); return o
    return dict(id=None,label="Plain",kind=kind,files=FALLBACK[kind],gcode=None,how="plain files: "+", ".join(FALLBACK[kind]),model=s.get("model",""),software=s.get("software",""),msg=msg or f"no output profile: plain {'/'.join(FALLBACK[kind])}")
NUM=re.compile(r"([XYZIJRF])(-?\d+(?:\.\d*)?)")
def post(lines,o,kind):
    """Generic Sketch G-code (G20 inches) -> the profile's flavor/units. Same toolpath, only syntax/units change."""
    g=o["gcode"]; mm=g["units"]=="mm"; out=[f"(Sketch output profile: {o['label']} {g['flavor']}, units {'mm G21' if mm else 'inch G20'})"]+(["(moves converted to mm; sizes in the comments below are still inches)"] if mm else [])+(["(GRBL laser: set $32=1 laser mode before running)"] if g["flavor"]=="grbl" and kind=="laser" else [])
    for ln in lines:
        s=ln.rstrip("\n")
        if s.startswith("(") or not s.strip(): out.append(s); continue
        if mm: s=NUM.sub(lambda m:f"{m[1]}{float(m[2])*25.4:.3f}",s.replace("G20","G21"))
        if g.get("noz"): 
            s=re.sub(r"\s*Z-?\d+(?:\.\d*)?","",s)
            if re.fullmatch(r"\s*G[01]\s*(F\S+)?\s*",s) and "F" not in s: continue
            if re.fullmatch(r"\s*G0\s*",s): continue
        if g["flavor"]=="grbl":
            s=re.sub(r"\bG40\b\s*","",s); s=re.sub(r"\bM6\b|\bT\d+\b","",s)
            if kind=="laser": s=re.sub(r"\bM3\b","M4 S1000",s)   # GRBL laser mode: dynamic power
        if g["flavor"]=="linuxcnc" and s.strip()=="M30": s="M2"
        if s.strip(): out.append(s.strip())
    if g["flavor"] in("mach3","mach4"): out=["%"]+out+["%"]
    return out
def check_nc(txt,o,kind):
    """problems with a posted program vs its profile (for the gate)."""
    g=o["gcode"]; bad=[]; body=[l for l in txt.splitlines() if l.strip() and not l.startswith("(") and l!="%"]
    want,other=("G21","G20") if g["units"]=="mm" else ("G20","G21")
    if not any(want in l for l in body): bad.append(f"no {want}")
    if any(other in l for l in body): bad.append(f"has {other}")
    if f"Sketch output profile: {o['label']}" not in txt: bad.append("no profile header")
    if g.get("noz") and any(re.search(r"Z-?\d",l) for l in body): bad.append("Z moves in a THC/no-Z program")
    if g["flavor"]=="grbl" and any(re.search(r"\bG4[012]\b|\bM6\b",l) for l in body): bad.append("cutter comp/tool change in GRBL")
    if g["flavor"]=="linuxcnc" and body and body[-1]!="M2": bad.append("LinuxCNC program must end M2")
    if g["flavor"] in("mach3","mach4") and not (txt.startswith("%") and txt.rstrip().endswith("%")): bad.append("Mach program not wrapped in %")
    return bad

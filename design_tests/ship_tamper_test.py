#!/usr/bin/env python3
"""ship_tamper_test.py: breaks one thing of each kind in a shipped plywood_shelf build and checks the ship gate blocks every one."""
import json,os,shutil,subprocess,sys,glob,csv,hashlib,re
ROOT=os.environ.get("SKETCH_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__))); SRC=sorted(glob.glob(f"{ROOT}/design_tests/plywood_shelf/v*/ship"),key=lambda x:int(x.split("/v")[-1].split("/")[0]))[-1].rsplit("/",1)[0]
PY=sys.executable; SHIP=f"{ROOT}/bin/ship.py"
def regen(F):
    json.dump(dict(files={os.path.relpath(os.path.join(r,f),F):hashlib.sha256(open(os.path.join(r,f),'rb').read()).hexdigest() for r,_,fs in os.walk(F) for f in fs if f!='.gen.json'}),open(F+'/.gen.json','w'))
def J(p,fn):
    d=json.load(open(p)); fn(d); json.dump(d,open(p,"w"))
def bomdel(F):
    L=open(f"{F}/bom.csv").read().splitlines(); open(f"{F}/bom.csv","w").write("\n".join(L[:2]+L[3:])+"\n")
def bomadd(F): open(f"{F}/bom.csv","a").write("Z,Shelf bracket,steel,2,,,,\n")
def shopdel(F):
    L=[l for l in open(f"{F}/shopping_list.csv").read().splitlines() if "screw" not in l]; open(f"{F}/shopping_list.csv","w").write("\n".join(L)+"\n")
def dxfopen(F):
    import ezdxf; p=sorted(glob.glob(f"{F}/dxf_*/*.dxf"))[0]; d=ezdxf.readfile(p)
    for e in d.modelspace():
        if e.dxftype()=="LWPOLYLINE" and e.dxf.layer=="CUT":
            pts=[tuple(q[:2]) for q in e.get_points()][:-2]; e.set_points(pts); e.closed=False; break
    d.saveas(p)
def kerf(F):
    p=sorted(glob.glob(f"{F}/gcode_*/*.json"))[0]; J(p,lambda d:d.update(comp=0))
def outside(F):
    p=glob.glob(f"{F}/nest_*/nest.json")[0]
    def f(d):
        pr=d["groups"][0]["parts"][0]; pr["geom"]["outer"]["poly"]=[[x+100,y] for x,y in pr["geom"]["outer"]["poly"]]
    J(p,f)
def nestdrop(F):
    p=glob.glob(f"{F}/nest_*/nest.json")[0]; J(p,lambda d:d["groups"][0]["parts"].pop())
def handname(F):
    s=open(f"{F}/hand_tool_plan.txt").read().replace("   - shelf1 ","   - shelf9 ",1); open(f"{F}/hand_tool_plan.txt","w").write(s)
def handdim(F):
    s=open(f"{F}/hand_tool_plan.txt").read(); s=re.sub(r'(   - shelf1\s+)[0-9.]+"',r'\g<1>40.000"',s,count=1); open(f"{F}/hand_tool_plan.txt","w").write(s)
def dimval(V): J(f"{V}/drawing_dims.json",lambda d:d["dims"][0].update(value=40.0))
def dimtyped(V): J(f"{V}/drawing_dims.json",lambda d:d["dims"][0].update(expr=42))
def dimunits(V): J(f"{V}/drawing_dims.json",lambda d:d.update(units="mm"))
def dimgeom(V): J(f"{V}/drawing_dims.json",lambda d:(d["dims"][0].update(expr="=width-2",value=40.0)))
def png(F): open(f"{F}/drawing.png","ab").write(b"x")
def costsrc(F): J(f"{F}/quote.json",lambda d:d["sources"][0].update(source="typed in by bot"))
def costsum(F): J(f"{F}/quote.json",lambda d:d.update(material_est=d["material_est"]+25))
def edit_noregen(F): open(f"{F}/bom.csv","a").write("\n")
def extra(F): open(f"{F}/flower.stl","w").write("solid x\nendsolid x\n")
T=[("drawing value != spec",dimval,"V",True,"spec gives"),("drawing dim typed in",dimtyped,"V",True,"typed in"),("drawing vs geometry",dimgeom,"V",True,"does not match the model"),
   ("drawing units",dimunits,"V",True,"units differ"),("drawing.png edited",png,"F",True,"not the image"),
   ("DXF open contour",dxfopen,"F",True,"open contour"),("kerf not applied",kerf,"F",True,"offset not applied"),("part outside sheet",outside,"F",True,"sticks out"),
   ("nest count != BOM",nestdrop,"F",True,"nested"),("BOM row missing",bomdel,"F",True,"missing"),("BOM orphan row",bomadd,"F",True,"orphan"),
   ("shopping list missing HW",shopdel,"F",True,"shopping list"),("cost not from prices",costsrc,"F",True,"not from prices"),("cost total off",costsum,"F",True,"doesn't equal"),
   ("hand plan unknown part",handname,"F",True,"not a part"),("hand plan wrong size",handdim,"F",True,"model/drawing has"),
   ("file edited after build (no regen)",edit_noregen,"F",False,"changed after"),("extra file not from toolbox",extra,"F",False,"not made by the toolbox")]
ok=0
for name,fn,where,rg,key in T:
    P=f"{ROOT}/design_tests/_tamper"; shutil.rmtree(P,ignore_errors=True); os.makedirs(P); shutil.copytree(SRC,f"{P}/v1"); shutil.copy(f"{SRC}/../spec.json",P)
    shutil.rmtree(f"{P}/v1/ship",ignore_errors=True); V=f"{P}/v1"; F=f"{V}/fab"
    fn(V if where=="V" else F)
    if rg: regen(F)
    r=subprocess.run([PY,SHIP,P],capture_output=True,text=True,env=dict(os.environ,SKETCH_ROOT=ROOT)); out=r.stdout+r.stderr
    fl=[l for l in out.splitlines() if l.startswith("[FAIL]") and "SHIP BLOCKED" not in l]
    good=r.returncode==1 and any(key in l for l in fl) and not os.path.exists(f"{V}/ship")
    ok+=good; print(("BLOCKED " if good else "NOT BLOCKED ")+f"{name}: "+(fl[0][:170] if fl else out[-300:]))
# control: untouched copy ships
P=f"{ROOT}/design_tests/_tamper"; shutil.rmtree(P); os.makedirs(P); shutil.copytree(SRC,f"{P}/v1"); shutil.copy(f"{SRC}/../spec.json",P); shutil.rmtree(f"{P}/v1/ship",ignore_errors=True)
r=subprocess.run([PY,SHIP,P],capture_output=True,text=True,env=dict(os.environ,SKETCH_ROOT=ROOT)); print("control:",r.stdout.strip().splitlines()[-1][:120]); shutil.rmtree(P)
print(f"{ok}/{len(T)} tampers blocked")
sys.exit(0 if ok==len(T) else 1)

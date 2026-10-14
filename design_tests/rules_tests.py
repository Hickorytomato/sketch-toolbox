#!/usr/bin/env python3
"""rules_tests.py: every new FAIL check in bin/rules.py gets a deliberate break that BLOCKS and the clean build that ships.
Run after run_tests.sh / ship_tests.sh (needs the shipped samples). Also checks kerf lookups vary with thickness."""
import os,sys,json,glob,shutil,re,copy,tempfile,subprocess
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B=os.path.join(ROOT,"bin"); sys.path.insert(0,B)
import rules, kerf
def latest(p):
    vs=sorted(glob.glob(f"{ROOT}/design_tests/{p}/v*/ship/ship_manifest.json"),key=lambda x:int(x.split("/v")[-1].split("/")[0]))
    if not vs: sys.exit(f"no shipped build of {p}: run run_tests.sh + ship_tests.sh first")
    return os.path.dirname(os.path.dirname(vs[-1]))
M0=json.load(open(f"{B}/machines.json"))
def run(V,M=None):
    d=json.load(open(f"{V}/parts.json")); spec=json.load(open(f"{V}/spec.json")); R=[]
    def res(area,target,status,why,**k): R.append(dict(area=area,target=target,status=status,why=why,**k))
    rules.gate(dict(d=d,spec=spec,F=f"{V}/fab",V=V,U=d["params"].get("units","in"),M=M or M0,res=res)); return R
def J(p,f=None):
    o=json.load(open(p)); 
    if f: f(o); json.dump(o,open(p,"w"))
    return o
def pdf(path,lines):
    from reportlab.pdfgen import canvas
    c=canvas.Canvas(path); y=700
    for l in lines: c.drawString(50,y,l); y-=14
    c.showPage(); c.save()
def edit(p,a,b,cnt=1):
    s=open(p).read(); assert a in s,(p,a[:40]); open(p,"w").write(s.replace(a,b,cnt))
def gj(V,typ): return [g for g in glob.glob(f"{V}/fab/gcode_*/*.json") if json.load(open(g)).get("type")==typ and not g.endswith("_flip.json")][0]
T=[]   # (id, base sample, mutate(V)->optional M, why)
def t(i,base,why):
    def deco(f): T.append((i,base,f,why)); return f
    return deco
@t(52,"plywood_shelf","drawings.pdf with no title block")
def _(V): pdf(f"{V}/fab/drawings.pdf",["drawing"])
for i in (111,227):
    @t(i,"plywood_shelf","title block but no general tolerance")
    def _(V): pdf(f"{V}/fab/drawings.pdf",["Units: inches Scale: NTS do not scale Date: x Build: "+json.load(open(f"{V}/parts.json"))["build_id"]])
@t(228,"steel_bracket","plasma tolerance stated tighter than plasma holds")
def _(V): J(f"{V}/parts.json",lambda d:[x.update(tol="±0.005 in") for x in d["title_block"]["tolerance"] if "plasma" in x["applies"]])
@t(235,"plywood_shelf","one program switched to mm (G21)")
def _(V): nc=glob.glob(f"{V}/fab/gcode_*/*.nc")[0]; edit(nc,"G20 G90","G21 G90")
for i in (55,123):
    @t(i,"plywood_shelf","build id differs between files")
    def _(V): J(f"{V}/parts.json",lambda d:d.update(build_id="0000000000"))
for i in (57,224):
    @t(i,"plywood_shelf","a BOM row with no finish")
    def _(V): J(f"{V}/parts.json",lambda d:d["cutlist"][0].pop("finish"))
@t(54,"steel_bracket","hole with no callout")
def _(V): J(f"{V}/fab/doc_meta.json",lambda m:m["holes"].__setitem__("base",[]))
@t(126,"lumber_shelf","lumber modelled at nominal (row says 2x6, geometry is a 2x4)")
def _(V): J(f"{V}/parts.json",lambda d:[r.update(material="2x6") for r in d["cutlist"] if r.get("material")=="2x4"])
for i in (127,40,70):
    @t(i,"plywood_shelf","3/4 plywood drawn at 0.750")
    def _(V): J(f"{V}/parts.json",lambda d:[f.update(thickness=0.75) for f in d["flats"] if f["thickness"]>0.7])
@t(96,"plywood_shelf","dado 0.13 wider than the mating part")
def _(V): J(f"{V}/parts.json",lambda d:[f.update(thickness=0.6) for f in d["flats"] if f["name"].startswith("shelf")])
@t(125,"lumber_shelf","board too short for its parts + kerf")
def _(V): J(f"{V}/parts.json",lambda d:d["stock_plan"][0]["boards"][0].update(stock=50))
@t(137,"lumber_shelf","6 in screw breaks out of a 3.5 in leg")
def _(V): J(f"{V}/parts.json",lambda d:[j.update(size="#10 x 6 in yellow zinc construction screw") for j in d["jointrec"] if j.get("type")=="screws"])
@t(116,"lumber_shelf","hardware line with no length/material")
def _(V): J(f"{V}/parts.json",lambda d:d["fasteners"].append(dict(item="#10 screw",qty=4)))
@t(205,"steel_bracket","1/2 bolt hole drilled 0.45")
def _(V): J(f"{V}/parts.json",lambda d:d["hole_specs"][0].update(d_in=0.45))
@t(204,"steel_bracket","1/4-20 tapped hole at 0.250 instead of #7")
def _(V): J(f"{V}/parts.json",lambda d:d["hole_specs"].append(dict(parts=["base"],d_in=0.25,bolt="1/4-20 x 3/4 in grade 5 zinc",tapped=True,dia_in=0.25)))
@t(206,"steel_bracket","3/8-16 tapped into 3/8 aluminum (needs 2D)")
def _(V): J(f"{V}/parts.json",lambda d:(d["hole_specs"].append(dict(parts=["base"],d_in=0.3125,bolt="3/8-16 x 1 in grade 5 zinc",tapped=True,dia_in=0.375)),[f.update(material="aluminum 6061") for f in d["flats"] if f["name"]=="base"]))
@t(28,"steel_bracket","0.30 hole plasma-cut in 3/8 plate")
def _(V): J(gj(V,"plasma"),lambda g:g["holes"].append(dict(part="base",d=0.3,action="cut",feed=60)))
@t(93,"steel_bracket","plasma program for plywood")
def _(V): J(gj(V,"plasma"),lambda g:g.update(material="plywood"))
for i in (15,237):
    @t(i,"steel_bracket","PVC on the laser")
    def _(V): J(gj(V,"laser"),lambda g:g.update(material="PVC sheet"))
for i in (73,246):
    @t(i,"steel_bracket","unidentified plastic on the laser")
    def _(V): J(gj(V,"laser"),lambda g:g.update(material="mystery plastic"))
@t(18,"steel_bracket","0.1 laser hole in 3/8")
def _(V): J(gj(V,"laser"),lambda g:g["holes"].append(dict(part="base",d=0.1,action="cut")))
@t(75,"steel_bracket","part bigger than the laser bed")
def _(V): J(f"{V}/parts.json",lambda d:[f.update(w=200,h=200) for f in d["flats"] if f["name"]=="base"])
for i in (30,19):
    @t(i,"steel_bracket","two holes 0.03 apart")
    def _(V): J(f"{V}/parts.json",lambda d:[f["holes"].append([f["holes"][0][0]+0.55,f["holes"][0][1],0.258]) for f in d["flats"] if f["name"]=="base"])
for i in (86,22):
    @t(i,"bent_tab","hole cut at r + kerf/2 (comp sign flipped)")
    def _(V):
        nc=gj(V,"plasma")[:-5]+".nc"; s=open(nc).read(); g=json.load(open(nc[:-3]+".json"))
        m=re.search(r"\(-- (\S+ hole d([\d.]+))\)\n((?:.*\n){0,8}?G[23] .*?I)(-?[\d.]+)",s); r=float(m[2])/2+g["comp"]
        open(nc,"w").write(s[:m.start(4)]+f"{-r:.4f}"+s[m.end(4):])
@t(39,"plywood_shelf","0.1 hole routed with a 1/4 bit")
def _(V): J(gj(V,"router"),lambda g:g["holes"].append(dict(part="side_L",d=0.1,action="cut")))
for i in (38,98):
    @t(i,"plywood_shelf","stopped pocket with square corners")
    def _(V): J(f"{V}/parts.json",lambda d:[f["pockets"].append(dict(poly=[[3,3],[6,3],[6,5],[3,5],[3,3]],depth=0.25,face="top")) for f in d["flats"] if f["name"]=="side_L"])
@t(97,"plywood_shelf","no bit diameter in machines.json")
def _(V): M=copy.deepcopy(M0); M["router"]["tool_dia"]=None; return M
@t(16,"steel_bracket","same contour twice in the nest DXF")
def _(V):
    import ezdxf
    p=glob.glob(f"{V}/fab/nest_*/*.dxf")[0]; doc=ezdxf.readfile(p); ms=doc.modelspace()
    e=[x for x in ms if x.dxftype()=="LWPOLYLINE" and x.dxf.layer=="CUT"][0]; ms.add_lwpolyline(list(e.get_points()),close=True,dxfattribs={"layer":"CUT"}); doc.saveas(p)
@t(71,"plywood_shelf","open engrave fill")
def _(V): s_=glob.glob(f"{V}/fab/FOR_LASER*/side_L.svg")[0]; t_=open(s_).read(); i_=t_.index('<g id="ENGRAVE"'); j_=t_.index(" Z",i_); open(s_,"w").write(t_[:j_]+t_[j_+2:])
for i in (23,32):
    @t(i,"steel_bracket","parts nested closer than the kerf")
    def _(V): J(glob.glob(f"{V}/fab/nest_metal/nest.json")[0],lambda n:[g.update(spacing=0.01) for g in n["groups"]])
@t(191,"bent_tab","flange shorter than 4T")
def _(V): J(f"{V}/parts.json",lambda d:d["flats"][0]["bends"][0].update(flanges=[3,0.3]))
@t(192,"bent_tab","inside radius 0.03 on 10 ga")
def _(V): J(f"{V}/parts.json",lambda d:d["flats"][0]["bends"][0].update(R=0.03))
@t(193,"bent_tab","hole 0.1 from the bend")
def _(V): J(f"{V}/parts.json",lambda d:d["flats"][0]["holes"].__setitem__(0,[d["flats"][0]["bends"][0]["u1"]+0.25,1,0.14]))
@t(194,"bent_tab","partial bend with no relief")
def _(V): J(f"{V}/parts.json",lambda d:d["flats"][0]["bends"][0].update(partial=True,relief_w=0,relief_d=0))
@t(119,"bent_tab","no developed length on the drawing")
def _(V): J(f"{V}/fab/doc_meta.json",lambda m:m.update(blanks=[]))
@t(179,"bent_tab","rolled ring blank not π(ID+t)")
def _(V): J(f"{V}/parts.json",lambda d:d["flats"][0].update(roll=dict(id=4,way="flat")))
for i,od in ((120,None),(180,1.66)):
    @t(i,"plant_stand",f"pipe row {'without OD' if od is None else 'NPS 1-1/2 at 1.66 OD'}")
    def _(V,od=od): J(f"{V}/parts.json",lambda d:d["cutlist"].insert(0,dict(mark="P",part="Post",material='1-1/2" sch40 pipe',qty=1,length="10.000 in",finish="paint",names=[],notes=("NPS 1-1/2 sch 40 = 1.660 in OD" if od else ""),pipe=dict(nps="1-1/2",sched="40",od_in=od or 1.9))))
@t(188,"steel_bracket","weld with no side")
def _(V): J(f"{V}/parts.json",lambda d:d["welds"][0].pop("side"))
for i in (108,175):
    @t(i,"steel_bracket","weld symbol drawn on the other side")
    def _(V): J(f"{V}/fab/doc_meta.json",lambda m:m["welds"][0].update(side="other"))
@t(172,"steel_bracket","ER308L on mild steel")
def _(V): J(f"{V}/parts.json",lambda d:d["welds"][0].update(filler="ER308L"))
@t(166,"steel_bracket","weld with no joint prep")
def _(V): J(f"{V}/parts.json",lambda d:d["welds"][0].update(prep=""))
@t(168,"steel_bracket","CJP weld, plan without the WPS note")
def _(V): J(f"{V}/parts.json",lambda d:d["welds"][0].update(cjp=True)); [edit(p,"WPS","W.P.S.",99) for p in (f"{V}/fab/hand_tool_plan.txt",f"{V}/fab/HOW_TO_USE.txt") if "WPS" in open(p).read()]
for i in (173,238):
    @t(i,"steel_bracket","galvanized plate welded, no zinc warning")
    def _(V): J(f"{V}/parts.json",lambda d:[r.update(material="galvanized steel plate") for r in d["cutlist"] if r.get("mark")!="HW"])
for i in (124,159,189,244):
    @t(i,"steel_bracket","hoist beam bracket without the engineer flag")
    def _(V): J(f"{V}/spec.json",lambda s:s.update(ask="a bracket for a chain hoist"))
for i in (153,156):
    @t(i,"lumber_shelf","wall framing job with no code-table notes")
    def _(V): J(f"{V}/spec.json",lambda s:s.update(ask="wall framing with a header"))
CLEAN={  # clean twins for checks the stock samples don't exercise
 204:("steel_bracket",lambda V:J(f"{V}/parts.json",lambda d:d["hole_specs"].append(dict(parts=["base"],d_in=0.201,bolt="1/4-20 x 3/4 in grade 5 zinc",tapped=True,dia_in=0.25)))),
 206:("steel_bracket",lambda V:J(f"{V}/parts.json",lambda d:d["hole_specs"].append(dict(parts=["base"],d_in=0.201,bolt="1/4-20 x 3/4 in grade 5 zinc",tapped=True,dia_in=0.25)))),
 179:("bent_tab",lambda V:J(f"{V}/parts.json",lambda d:d["flats"][0].update(roll=dict(id=d["flats"][0]["w"]/3.14159265-d["flats"][0]["thickness"],way="flat")))),
 120:("plant_stand",lambda V:J(f"{V}/parts.json",lambda d:d["cutlist"].insert(0,dict(mark="P",part="Post",material='1-1/2" sch40 pipe',qty=1,length="10.000 in",finish="paint",names=[],notes="NPS 1-1/2 sch 40 = 1.900 in OD",pipe=dict(nps="1-1/2",sched="40",od_in=1.9))))),
 173:("steel_bracket",lambda V:(J(f"{V}/parts.json",lambda d:[r.update(material="galvanized steel plate") for r in d["cutlist"] if r.get("mark")!="HW"]),open(f"{V}/fab/hand_tool_plan.txt","a").write("\n".join(rules.safety(json.load(open(f"{V}/parts.json"))))+"\n"))),
 124:("steel_bracket",lambda V:(J(f"{V}/spec.json",lambda s:s.update(ask="a bracket for a chain hoist")),open(f"{V}/fab/hand_tool_plan.txt","a").write("!! ENGINEER/CODE: verify\n"))),
 153:("lumber_shelf",lambda V:(J(f"{V}/spec.json",lambda s:s.update(ask="wall framing with a header")),open(f"{V}/fab/hand_tool_plan.txt","a").write("\n".join(rules.FRAMING_NOTES.values())+"\n"))),
 168:("steel_bracket",lambda V:J(f"{V}/parts.json",lambda d:d["welds"][0].update(cjp=True))),
}
for a_,b_ in ((180,120),(238,173),(159,124),(189,124),(244,124),(156,153),(237,None),(246,None),(15,None),(73,None),(194,None)): 
    if b_: CLEAN[a_]=CLEAN[b_]
ok=bad=0; tmp=tempfile.mkdtemp()
def fresh(base):
    V=f"{tmp}/{base}"; shutil.rmtree(V,ignore_errors=True); shutil.copytree(latest(base),V,ignore=shutil.ignore_patterns("ship","*.zip","step","steps")); return V
base_fail={}
for base in sorted({b for _,b,_,_ in T}):
    R=run(fresh(base)); base_fail[base]=[r for r in R if r["status"]=="FAIL"]
    if base_fail[base]: print("BAD  clean",base,"has FAILs:",[r["target"]+" "+r["why"] for r in base_fail[base]][:3]); bad+=1
    else: print(f"OK   clean {base}: {sum(r['status']=='PASS' for r in R)} rule checks pass, 0 FAIL"); ok+=1
for i,base,f,why in T:
    V=fresh(base); M=f(V); R=run(V,M)
    hit=[r for r in R if r.get("id")==i and r["status"]=="FAIL"]
    if hit: print(f"OK   #{i:<3} blocks: {why} -> {hit[0]['why'][:110]}"); ok+=1
    else: print(f"BAD  #{i:<3} did not block: {why}  {[r['status']+' '+r['why'][:80] for r in R if r.get('id')==i]}"); bad+=1
for i,(base,f) in CLEAN.items():
    V=fresh(base); f(V); R=run(V); fl=[r for r in R if r.get("id")==i and r["status"]=="FAIL"]; ps=[r for r in R if r.get("id")==i and r["status"]=="PASS"]
    if not fl and ps: print(f"OK   #{i:<3} clean twin passes: {ps[0]['why'][:100]}"); ok+=1
    else: print(f"BAD  #{i:<3} clean twin: {[r['status']+' '+r['why'][:90] for r in R if r.get('id')==i]}"); bad+=1
# kerf by thickness: table + G-code offsets differ
k=[kerf.lookup("plasma",M0["plasma"],"steel",t_)[0] for t_ in (0.06,0.135,0.25,0.375,0.5)]
c1=json.load(open(gj(latest("bent_tab"),"plasma")))["comp"]; c2=json.load(open(gj(latest("steel_bracket"),"plasma")))["comp"]
if len(set(k))==5 and c1!=c2: print(f"OK   kerf by thickness: plasma steel {k}; G-code comp 10ga {c1:.4f} vs 3/8 {c2:.4f}"); ok+=1
else: print("BAD  kerf by thickness",k,c1,c2); bad+=1
lk=[kerf.lookup("laser",M0["laser"],m_,t_)[0] for m_,t_ in (("plywood",0.125),("plywood",0.25),("acrylic",0.125),("acrylic",0.25))]
if lk[0]!=lk[1] and lk[2]!=lk[3]: print(f"OK   laser kerf by thickness: ply 1/8 {lk[0]} vs 1/4 {lk[1]}, acrylic 1/8 {lk[2]} vs 1/4 {lk[3]}"); ok+=1
else: print("BAD  laser kerf",lk); bad+=1
shutil.rmtree(tmp,ignore_errors=True)
print(f"rules tests: {ok} ok, {bad} bad"); sys.exit(1 if bad else 0)

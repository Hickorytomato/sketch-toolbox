#!/usr/bin/env python3
"""review.py PROJECT_DIR [VDIR] [--facts wearer.json] -> VDIR/review.md + VDIR/review.png ; exit 3 = REVISION REQUIRED
Wearer/user-perspective design review. Run after design.sh, BEFORE showing the user. Scores 0-10 per category from the end
user's point of view (not the printer's): body fit/comfort, draw & return, weight + print time vs value, failure points
(flex parts must bend along layers), part count/assembly, maintenance. Facts come from PROJECT/geom.json["wearer"] (or
--facts JSON) plus VDIR/fab/print/print.json. Missing facts score 5 and are listed as 'unknown - measure it'.
Gate: overall < 7.0 or any category < 5 -> REVISION REQUIRED with the fixes to make; Sketch must revise and re-run.
Fact keys (wearer object, all optional): cup_axis_from_body_mm, cup_top_vs_belt_center_mm, body_contact ('curved...'|'flat'),
 carried_mass_g, flex_parts:[{name,orientation:'in-plane (along layers)'|'across layers',strain_pct}], prints_default,
 one_hand_draw (bool), sharp_edges (bool), washable (bool), use='worn'|'handheld'|'static'."""
import sys,os,json,re,glob
from PIL import Image,ImageDraw,ImageFont
a=sys.argv[1:]; facts_f=None
if "--facts" in a: i=a.index("--facts"); facts_f=a[i+1]; del a[i:i+2]
P=os.path.abspath(a[0]); V=a[1] if len(a)>1 else sorted(glob.glob(f"{P}/v[0-9]*"),key=lambda s:int(re.sub(r"\D","",os.path.basename(s))))[-1]
W=json.load(open(facts_f))if facts_f else json.load(open(f"{P}/geom.json")).get("wearer",{})
pj=f"{V}/fab/print/print.json"; hrs=grams=None; nprint=None
def tsec(t): return sum(int(n)*m for n,u in re.findall(r"(\d+)([dhms])",t) for m in [{"d":86400,"h":3600,"m":60,"s":1}[u]])
if os.path.exists(pj):
    pr=json.load(open(pj)); pcs=[pc for p in pr["parts"] for pc in p["pieces"]]
    hrs=sum(tsec(pc["time"]) for pc in pcs)/3600; grams=sum(float(pc["grams"]) for pc in pcs); nprint=len(pcs)
nprint=W.get("prints_default",nprint)
S={}; why={}; fix={}
def put(k,sc,w,f=None): S[k]=max(0,min(10,round(sc,1))); why[k]=w; fix[k]=f
# 1 body fit / comfort
off=W.get("cup_axis_from_body_mm"); bc=W.get("body_contact","")
if off is None: put("Body fit & comfort",5,"unknown - measure how far the load sits from the body")
else:
    sc=10-max(0,(off-55)/6)-(0 if "curved" in bc else 2.5)
    put("Body fit & comfort",sc,f"load axis {off:.0f} mm off the body; contact: {bc or 'flat'}",
        None if sc>=7 else "curve the back to the waist (R150-180) and pull the heavy item closer to the body")
# 2 draw & return
top=W.get("cup_top_vs_belt_center_mm"); bt=W.get("bottle_top_vs_belt_center_mm")
if top is None: put("Draw & return",5,"unknown - where does the hand meet the item?")
else:
    sc=10-max(0,(top-10)/8)-(0 if W.get("one_hand_draw",True) else 3)-(1 if bt and bt>230 else 0)
    put("Draw & return",sc,f"cup mouth {top:+.0f} mm vs belt centre, grip/trigger top {bt:+.0f} mm" if bt else f"cup mouth {top:+.0f} mm vs belt",
        None if sc>=7 else "drop the holster so the mouth is at/below belt line (hand hangs there naturally); flare the mouth")
# 3 weight + print time vs value
m=W.get("carried_mass_g")
if hrs is None: put("Weight & print time vs value",5,"no slice yet")
else:
    sc=10-max(0,(hrs-15)/3)   # ~15 h = two overnight prints is the value line for a worn rig-(max(0,(m-1500)/150) if m else 0)
    put("Weight & print time vs value",sc,f"{hrs:.1f} h printing, {grams:.0f} g filament"+(f", ~{m} g carried full" if m else ""),
        None if sc>=7 else "merge repeated mounts into one part, hollow/lighten, drop modules nobody uses daily")
# 4 failure points
fl=W.get("flex_parts")
if fl is None: put("Failure points",5,"unknown - list every part that bends and its layer orientation")
else:
    bad=[f for f in fl if "across" in f.get("orientation","")]; hi=[f for f in fl if f.get("strain_pct",0)>2.5]
    sc=10-4*len(bad)-2*len(hi)
    put("Failure points",sc,"; ".join(f"{f['name']}: {f['orientation']}, {f.get('strain_pct','?')}% strain" for f in fl) or "no flex parts",
        None if sc>=7 else "re-orient flex features so they bend IN the layer plane; keep strain < 2.5% PETG")
# 5 part count
if nprint is None: put("Part count & assembly",5,"unknown")
else:
    sc=10-max(0,nprint-5)*0.6
    put("Part count & assembly",sc,f"{nprint} prints by default",None if sc>=7 else "integrate repeated interfaces into one carrier part")
# 6 maintenance / hygiene (cleaning business: wet, chemicals)
sc=8 if W.get("washable",True) else 4
put("Wet use & cleaning",sc,"open drains + PETG (chemical resistant)" if sc>=7 else "traps liquid",None if sc>=7 else "add drains, avoid pockets")
ov=sum(S.values())/len(S); need=ov<7 or min(S.values())<5
lines=[f"# Wearer review - {os.path.basename(P)} {os.path.basename(V)}","",f"**Overall {ov:.1f}/10 -> {'REVISION REQUIRED' if need else 'PASS'}**",""]
for k in S: lines.append(f"- **{k}: {S[k]}/10** - {why[k]}"+(f"  \n  FIX: {fix[k]}" if fix[k] else ""))
open(f"{V}/review.md","w").write("\n".join(lines)+"\n"); print("\n".join(lines))
# scorecard PNG (chat-friendly)
F="/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"
try: f1,f2,f3=ImageFont.truetype(F,34),ImageFont.truetype(F,22),ImageFont.truetype(F,17)
except Exception: f1=f2=f3=ImageFont.load_default()
im=Image.new("RGB",(900,110+len(S)*78),(24,26,30)); d=ImageDraw.Draw(im)
d.text((30,24),f"Wearer review  {os.path.basename(V)}   {ov:.1f}/10",fill=(240,240,240),font=f1)
d.text((640,30),"REVISE" if need else "PASS",fill=(235,90,70) if need else (90,200,120),font=f1)
y=100
for k in S:
    c=(90,200,120) if S[k]>=7 else (235,180,60) if S[k]>=5 else (235,90,70)
    d.text((30,y),k,fill=(230,230,230),font=f2); d.rounded_rectangle((420,y+4,420+int(40*S[k]),y+26),6,fill=c); d.text((835,y),f"{S[k]:.0f}",fill=c,font=f2)
    d.text((30,y+32),why[k][:95],fill=(160,165,175),font=f3); y+=78
im.save(f"{V}/review.png"); sys.exit(3 if need else 0)

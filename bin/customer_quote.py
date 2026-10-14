#!/usr/bin/env python3
"""customer_quote.py VDIR OUTDIR -> customer_quote.pdf + customer_quote-<n>.png + customer_quote.json   (v1.0.5 feature 3)
A quote you can hand a customer. Line items: materials (prices.json / live prices / slicer, each with its source),
hardware, machine time (slicer hours + G-code minutes x machines.json shop machine_rate_per_h), labor (non-machine hours x
labor_rate), shop margin, tax (profile shop.tax_pct, else a blank field), lead time, valid-until date, terms.
Shop name/logo/address/drawn-by come ONLY from profile.json 'shop' (tools_setup.py --shop ...); none set -> neutral quote.
Always stamped ESTIMATE."""
import sys,os,json,glob,time,datetime,subprocess,textwrap,math
B=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,B); import ref
V,O=sys.argv[1],sys.argv[2]
d=json.load(open(f"{V}/parts.json")); Q=json.load(open(f"{O}/quote.json")); M=json.load(open(f"{B}/machines.json")); SH=M.get("shop",{})
PROF=ref.profile(); SHOP=PROF.get("shop",{}) or {}
LP=json.load(open(f"{O}/live_prices.json")) if os.path.exists(f"{O}/live_prices.json") else {}
RATE=SH.get("machine_rate_per_h",{}); LR=float(SH.get("labor_rate",75)); MG=float(SH.get("margin_pct",25))
L=[]   # (section, description, qty, unit, rate, amount, source)
for s in Q["sources"]:
    if s["line"]=="labor" or s["line"].startswith("filament ") and False: continue
    if s["line"]=="labor": continue
    if s["usd"]==0 and "slicer" in s["source"]: continue   # printed parts are priced by their filament lines
    lp=LP.get("lines",{}).get(s["line"])
    if lp and lp.get("usd") is not None: L.append(("Materials",s["line"],1,"lot",lp["usd"],lp["usd"],f'{lp["store"]} {lp["date"]} ({lp["url"]})'))
    else: L.append(("Materials",s["line"],1,"lot",s["usd"],s["usd"],s["source"]+(f' [no live price: {lp["why"]}]' if lp else "")))
hw={}
for r in d["cutlist"]:
    if r.get("mark")=="HW": hw.setdefault(r["material"],dict(r,qty=0))["qty"]+=r["qty"]
for r in hw.values():
    lp=LP.get("lines",{}).get(r["material"])
    if lp and lp.get("usd") is not None: L.append(("Hardware",r["material"],r["qty"],"ea",lp["usd"],round(lp["usd"]*r["qty"],2),f'{lp["store"]} {lp["date"]}'))
    else: L.append(("Hardware",r["material"],r["qty"],"ea",None,None,"not priced: add to prices.json or set a supplier link (price_links.json)"))
mach={}
if Q.get("printer_hours"): mach["printer"]=float(Q["printer_hours"])
PREF={"metal":("plasma","laser","router"),"wood":("router","laser"),"acrylic":("laser","router")}   # same primary machine as design.sh
by={}
for g in glob.glob(f"{O}/gcode_*/*.json"):
    j=json.load(open(g))
    if j.get("type") and j.get("est_min") is not None: by.setdefault(j.get("sheet"),[]).append((os.path.basename(os.path.dirname(g)).split("_",1)[1],j))
ALT=[]
for sh,js in by.items():
    cls=js[0][0]; order=PREF.get(cls,("plasma","laser","router")); js.sort(key=lambda q:order.index(q[1]["type"]) if q[1]["type"] in order else 9)
    t=js[0][1]["type"]; mach[t]=mach.get(t,0)+float(js[0][1]["est_min"])/60; ALT+=[f'{sh} on {q[1]["type"]}' for q in js[1:]]
# one machine per material group in the package: bill the primary program per sheet only (the alternates are options)
for t,h in sorted(mach.items()):
    r=float(RATE.get(t,0)); L.append(("Machine time",f"{t} time (from {'slicer' if t=='printer' else 'G-code estimate'})",round(h,3),"h",r,round(h*r,2),f'machines.json shop machine_rate_per_h[{t}] '+("(Sketch default)" if "_src" in RATE and "Sketch default" in RATE["_src"] else "")))
lh={k:v for k,v in Q.get("labor_hours",{}).items() if k!="cutting"}
for k,h in lh.items():
    if h: L.append(("Labor",k.replace("_"," "),round(h,2),"h",LR,round(h*LR,2),"machines.json shop labor_rate x hours (shop per-part rates)"))
sub=round(sum(x[5] for x in L if x[5] is not None),2); mg=round(sub*MG/100,2)
tax_pct=SHOP.get("tax_pct"); tax=round((sub+mg)*float(tax_pct)/100,2) if tax_pct is not None else None
total=round(sub+mg+(tax or 0),2)
hrs=sum(x[2] for x in L if x[3]=="h"); hpd=float(SH.get("shop_hours_per_day",6))
lead=SHOP.get("lead_time") or f"about {max(1,math.ceil(hrs/hpd))} working day(s) of shop time once approved + material lead time (Sketch estimate from {hrs:.1f} h at {hpd:g} h/day)"
today=datetime.date.today(); vd=int(SHOP.get("valid_days",30)); valid=today+datetime.timedelta(days=vd)
terms=SHOP.get("terms") or "This is an estimate. Final price is confirmed in writing before work starts. Materials are priced on the date shown and may change."
qn=f'Q-{d.get("build_id","x")}-{today.strftime("%y%m%d")}'
out=dict(quote_no=qn,date=str(today),valid_until=str(valid),valid_days=vd,build_id=d.get("build_id"),shop=SHOP,lines=[dict(section=a,desc=b,qty=c,unit=u,rate=r,amount=am,source=s) for a,b,c,u,r,am,s in L],
         alternates_not_billed=ALT,subtotal=sub,margin_pct=MG,margin=mg,tax_pct=tax_pct,tax=tax,total=total,lead_time=lead,terms=terms,estimate=True,unpriced=[x[1] for x in L if x[5] is None])
json.dump(out,open(f"{O}/customer_quote.json","w"),indent=1)
from reportlab.lib.pagesizes import letter; from reportlab.pdfgen import canvas; from reportlab.lib.units import inch; from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor,black
PW,PH=letter; c=canvas.Canvas(f"{O}/customer_quote.pdf",pagesize=letter); pg=[0]
def top():
    pg[0]+=1; y=PH-0.6*inch; x=0.5*inch
    if SHOP.get("logo") and os.path.exists(SHOP["logo"]):
        try: c.drawImage(ImageReader(SHOP["logo"]),x,y-0.55*inch,1.0*inch,0.7*inch,preserveAspectRatio=True,mask="auto"); x+=1.15*inch
        except Exception: pass
    c.setFont("Helvetica-Bold",16); c.drawString(x,y,SHOP.get("name") or "QUOTE"); c.setFont("Helvetica",9)
    yy=y-13
    for k in ("address","phone","email"):
        if SHOP.get(k): c.drawString(x,yy,str(SHOP[k])); yy-=11
    c.setFillColor(HexColor("#c0392b")); c.setFont("Helvetica-Bold",13); c.drawRightString(PW-0.5*inch,y,"ESTIMATE"); c.setFillColor(black)
    c.setFont("Helvetica",9)
    for i,t in enumerate((f"Quote {qn}",f"Date {today}",f"Valid until {valid} ({vd} days)",f"Page {pg[0]}")): c.drawRightString(PW-0.5*inch,y-14-11*i,t)
    return PH-1.55*inch
y=top(); c.setFont("Helvetica-Bold",10); c.drawString(0.5*inch,y,"For: ________________________________"); c.drawString(4.2*inch,y,"Project: "+(d.get("title") or "")[:45]); y-=22
c.setFont("Helvetica-Bold",9)
for x,t in ((0.5,"Item"),(4.5,"Qty"),(5.2,"Rate"),(6.3,"Amount")): c.drawString(x*inch,y,t)
y-=4; c.line(0.5*inch,y,PW-0.5*inch,y); y-=12; sec=None
for a,b,q,u,r,am,s in L:
    if y<1.9*inch: c.showPage(); y=top()
    if a!=sec: c.setFont("Helvetica-Bold",9.5); c.drawString(0.5*inch,y,a); y-=12; sec=a
    c.setFont("Helvetica",9); c.drawString(0.65*inch,y,b[:62]); c.drawString(4.5*inch,y,f"{q:g} {u}"); c.drawString(5.2*inch,y,"-" if r is None else f"${r:,.2f}"); c.drawRightString(7.2*inch,y,"not priced" if am is None else f"${am:,.2f}")
    c.setFont("Helvetica",6.5); c.drawString(0.65*inch,y-8,("source: "+s)[:120]); y-=20
y-=4; c.line(4.4*inch,y,PW-0.5*inch,y); y-=14
for t,v in (("Subtotal",sub),(f"Shop overhead & margin ({MG:g}%)",mg),(f"Tax ({tax_pct:g}%)" if tax_pct is not None else "Tax (rate not set: ________ )",tax),("TOTAL (estimate)",total)):
    c.setFont("Helvetica-Bold" if t.startswith("TOTAL") else "Helvetica",10 if t.startswith("TOTAL") else 9); c.drawString(4.4*inch,y,t); c.drawRightString(7.2*inch,y,"________" if v is None else f"${v:,.2f}"); y-=14
if out["unpriced"]: c.setFont("Helvetica-Oblique",8); c.drawString(0.5*inch,y,f'Not priced yet (not in the total): {", ".join(out["unpriced"])[:110]}'); y-=12
y-=8; c.setFont("Helvetica-Bold",9.5); c.drawString(0.5*inch,y,"Lead time"); c.setFont("Helvetica",9); y-=12
for tl in textwrap.wrap(lead,110): c.drawString(0.5*inch,y,tl); y-=11
y-=4; c.setFont("Helvetica-Bold",9.5); c.drawString(0.5*inch,y,"Terms"); c.setFont("Helvetica",9); y-=12
for tl in textwrap.wrap(terms,110): c.drawString(0.5*inch,y,tl); y-=11
c.setFont("Helvetica-Oblique",7.5); c.drawString(0.5*inch,0.55*inch,f'ESTIMATE generated by Sketch from build {d.get("build_id")}. Prices and hours are estimates; check before accepting. '+(f'Prepared by {SHOP["drawn_by"]}.' if SHOP.get("drawn_by") else ""))
c.drawString(0.5*inch,0.42*inch,"Accepted by: ______________________   Date: __________")
c.save(); subprocess.run(["pdftoppm","-png","-r","110",f"{O}/customer_quote.pdf",f"{O}/customer_quote"],check=False)
print(f"customer quote -> {O}/customer_quote.pdf: total ${total:,.2f} (estimate), {len(L)} lines, shop={'neutral' if not SHOP.get('name') else SHOP['name']}")

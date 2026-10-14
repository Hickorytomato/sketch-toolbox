#!/usr/bin/env python3
"""cope.py PARTS.json OUT.pdf -> printable 1:1 pipe cope (saddle) wrap templates for every joint in parts.json 'joints'.
Math: branch OD radius r meets header OD radius R at angle a (deg, between axes). Distance from header axis to the branch end
at wrap angle t:  z(t) = sqrt(R^2 - r^2 sin^2 t)/sin a + r cos t / tan a. Template height = z(t) - min z (cut back from long point).
Print at 100% (no 'fit to page'); check the 1-inch scale square. Wrap around the branch OD, align the seam line, trace, cut, grind."""
import sys,json,math
from reportlab.lib.pagesizes import letter,landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
d=json.load(open(sys.argv[1])); out=sys.argv[2]
J={}
for j in d.get("joints",[]): J.setdefault((j["branch_od"],j["header_od"],j["angle"]),[]).append(j)
c=canvas.Canvas(out,pagesize=landscape(letter)); PW,PH=landscape(letter)
if not J: c.drawString(72,PH-72,"No coped joints in this design."); c.save(); sys.exit()
for (bo,ho,ang),js in J.items():
    r,R,a=bo/2,ho/2,math.radians(ang)
    if r>R: r=R   # branch larger than header: full saddle at header size
    N=360; zs=[math.sqrt(max(R*R-(r*math.sin(2*math.pi*k/N))**2,0))/math.sin(a)+r*math.cos(2*math.pi*k/N)/math.tan(a) for k in range(N+1)]
    zmin=min(zs); hs=[z-zmin for z in zs]; C=math.pi*bo
    ends=sum(j.get("ends",1) for j in js); names=", ".join(j["branch"] for j in js)
    x0,y0=0.75*inch,1.6*inch; sc=inch
    if C*sc>PW-1.5*inch: raise SystemExit(f"OD {bo} wraps {C:.2f}in: wider than page; tile manually")
    c.setFont("Helvetica-Bold",14); c.drawString(x0,PH-0.7*inch,f'Cope template  branch {bo}" OD  ->  header {ho}" OD  at {ang} deg')
    c.setFont("Helvetica",9)
    c.drawString(x0,PH-0.95*inch,f"Wrap length = branch OD circumference {C:.3f}\". Cut {ends} ends: {names}. Print at 100% scale, verify the 1\" square.")
    c.drawString(x0,PH-1.12*inch,f"Max cut-back from long point: {max(hs):.3f}\". Cut on the line, keep the side toward the tube body. ESTIMATED TEMPLATE - test-fit on scrap first.")
    c.setLineWidth(0.5); c.rect(x0,y0,C*sc,max(hs)*sc+1.5*inch)   # wrap band
    c.setLineWidth(1.6); p=c.beginPath(); 
    for k,h in enumerate(hs):
        X=x0+C*sc*k/N; Y=y0+1.5*inch+ (max(hs)-h)*sc*0+ (h)*sc*0 + (max(hs)-h)*sc
        p.moveTo(X,Y) if k==0 else p.lineTo(X,Y)
    c.drawPath(p)
    for q,lab in((0,"0 (top)"),(0.25,"90"),(0.5,"180"),(0.75,"270"),(1,"360 seam")):
        X=x0+C*sc*q; c.setLineWidth(0.3); c.line(X,y0,X,y0+max(hs)*sc+1.5*inch); c.drawString(X+2,y0-12,lab)
    c.drawString(x0,y0+4,"tube body side (keep)"); c.setFont("Helvetica",8)
    c.rect(PW-1.75*inch,0.5*inch,inch,inch); c.drawString(PW-1.75*inch,0.38*inch,"1 inch scale check")
    c.showPage()
c.save(); print(out)

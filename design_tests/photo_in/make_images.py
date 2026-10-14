"""PIL-made test photos for import_file.py (v1.0.6 item 10)."""
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import random,math
F=lambda s,b=False:ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf"%("-Bold" if b else ""),s)
def arrow(d,a,b,txt,f,off=(0,-28)):
    d.line([a,b],fill=0,width=3)
    for p,q in ((a,b),(b,a)):
        ang=math.atan2(q[1]-p[1],q[0]-p[0])
        for s_ in (0.4,-0.4): d.line([p,(p[0]+18*math.cos(ang+s_),p[1]+18*math.sin(ang+s_))],fill=0,width=3)
    mx,my=(a[0]+b[0])/2+off[0],(a[1]+b[1])/2+off[1]; d.text((mx,my),txt,fill=0,font=f,anchor="mm")
# 1. clean dimensioned hand sketch: 6 x 4 in plate, 1/4 thick, two 1/2 holes 1 in from the ends
im=Image.new("L",(1400,1000),250); d=ImageDraw.Draw(im); f=F(40)
d.rectangle([200,250,1100,850],outline=0,width=5)
for cx in (350,950): d.ellipse([cx-38,550-38,cx+38,550+38],outline=0,width=4)
arrow(d,(200,170),(1100,170),'6"',f); arrow(d,(1200,250),(1200,850),'4"',f,(50,0))
arrow(d,(200,950),(350,950),'1"',F(34),(0,30)); d.text((380,620),'2x Ø1/2"',fill=0,font=F(34))
d.text((420,80),"BRACKET PLATE  1/4\" STEEL",fill=0,font=F(44,True)); d.text((780,500),'holes centered on 4" side',fill=0,font=F(26))
im.convert("RGB").save("plate_sketch.png")
# 2. napkin: beige, low contrast, rotated + perspective, blurry, 120 x 80 mm, 3 mm, one hole 20 mm, a smudged dimension
im=Image.new("RGB",(1300,1000),(214,200,170)); nap=Image.new("RGB",(900,700),(246,240,225)); d=ImageDraw.Draw(nap); f=F(36); ink=(70,70,110)
d.rectangle([120,180,780,600],outline=ink,width=4); d.ellipse([400,350,480,430],outline=ink,width=3)
d.line([(120,120),(780,120)],fill=ink,width=3); d.text((420,85),"120 mm",fill=ink,font=f,anchor="mm")
d.line([(830,180),(830,600)],fill=ink,width=3); d.text((845,390),"8?",fill=(150,140,150),font=f)   # smudged: 80? 85?
d.text((330,440),"Ø20",fill=ink,font=F(30)); d.text((140,630),"3mm acrylic",fill=ink,font=F(30))
nap=nap.rotate(9,expand=True,fillcolor=(214,200,170)); im.paste(nap,(150,90)); im=im.filter(ImageFilter.GaussianBlur(1.6))
w,h=im.size; im=im.transform((w,h),Image.PERSPECTIVE,(1,0.06,-30,0.02,1,-20,0.00004,0.00002),fillcolor=(214,200,170)); im.save("napkin.jpg",quality=70)
# 3. printed drawing with title block: shelf side 300 x 200 mm, 18 mm ply, holes, scale note
im=Image.new("RGB",(1700,1200),"white"); d=ImageDraw.Draw(im); f=F(30)
d.rectangle([20,20,1680,1180],outline=0,width=3); d.rectangle([1100,980,1680,1180],outline=0,width=2)
d.text((1120,995),"TITLE: SHELF SIDE",fill=0,font=F(30,True)); d.text((1120,1040),"MATL: 18 mm BIRCH PLY",fill=0,font=f); d.text((1120,1080),"UNITS: mm   SCALE 1:2",fill=0,font=f); d.text((1120,1120),"QTY 2",fill=0,font=f)
d.rectangle([250,250,1000,750],outline=0,width=4)
for x,y in ((325,325),(925,325),(325,675),(925,675)): d.ellipse([x-10,y-10,x+10,y+10],outline=0,width=3)
arrow(d,(250,180),(1000,180),"300",f); arrow(d,(1080,250),(1080,750),"200",f,(50,0)); arrow(d,(250,820),(325,820),"30",F(26),(0,28))
d.text((350,700),"4x Ø8 THRU",fill=0,font=F(26)); im.save("printed_drawing.png")
# 4. a real part with a tape measure: wooden board photo-ish, tape along the top showing 0..24 in
im=Image.new("RGB",(1600,900),(90,90,95)); d=ImageDraw.Draw(im)
d.rectangle([150,330,1450,640],fill=(196,154,102)); [d.line([(150,y),(1450,y+random.randint(-6,6))],fill=(170,128,80),width=2) for y in range(345,640,22)]
d.rectangle([150,250,1500,320],fill=(240,200,40)); px_in=1300/24
for i in range(0,25):
    x=150+i*px_in; d.line([(x,250),(x,290)],fill=0,width=3); d.text((x+3,292),str(i),fill=0,font=F(20))
    if i<24: d.line([(x+px_in/2,250),(x+px_in/2,272)],fill=0,width=2)
im=im.filter(ImageFilter.GaussianBlur(0.8)); im.save("board_tape.jpg",quality=80)
print("made 4 images")

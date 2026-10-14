#!/usr/bin/env python3
"""import_file.py FILE PROJECT [--units mm|in] [--domain print|metal|wood|laser] [--t T] [--material M] [--title "..."]
   import_file.py --from-read READ.json PROJECT
Turn existing files into a living spec (PROJECT/spec.json); then run design.sh PROJECT for renders, drawings, cut/print files, quote.
 3D CAD  STEP/STP/IGES/IGS/BREP (exact, OCCT) and STL/3MF/OBJ/PLY/GLB (mesh, sewn to a solid): overall L/W/H become spec values
         (src "read") and the body scales with them (sx="=L/L0"), so `spec.py set PROJECT L=200` resizes it.
 2D      DXF (ezdxf) / SVG (svgelements): closed outline + circles -> a flat 'profile' part (thickness/material assumed), ready to nest/cut.
 PDF     blueprint: pdftotext (dimension-looking text) + pdftoppm pages -> PROJECT/source/read/ for Sketch to READ WITH VISION.
 IMAGE   photo of a blueprint / napkin sketch / real object (PNG/JPG/WEBP): OpenCV finds the paper, de-skews the perspective, cleans to
         high-contrast -> PROJECT/source/read/clean.png (+ read_template.json). Sketch reads the dimensions itself, fills read.json
         (every read value src "read", note "read from drawing, confirm"; anything missing = assumed), then --from-read builds the spec.
READ.json: {"title","domain","units","shape":"plate|profile|box|parts", "values":{"L":{"v":120},...}, "holes":[{"x":..,"y":..,"d":..}],
            "outer":[[x,y],...], "parts":[...spec parts...], "dims":[...] }"""
import sys,os,json,re,shutil,subprocess,math
import numpy as np
B=os.path.dirname(os.path.abspath(__file__)); a=sys.argv[1:]
def opt(k,d=None): return a[a.index(k)+1] if k in a else d
prof=json.load(open(f"{B}/profile.json")) if os.path.exists(f"{B}/profile.json") else {}
READNOTE="read from drawing, confirm"
def V(v,src="read",unit="",note=""): return dict(v=v,src=src,unit=unit,note=note or (READNOTE if src=="read" else "Sketch assumption"))
def write(P,spec):
    os.makedirs(P,exist_ok=True); json.dump(spec,open(f"{P}/spec.json","w"),indent=1)
    rd=[k for k,v in spec["values"].items() if v.get("src")=="read"]; asm=[k for k,v in spec["values"].items() if v.get("src")=="assumed"]
    print(f"spec -> {P}/spec.json\n  read from file/drawing (confirm): "+", ".join(f'{k}={spec["values"][k]["v"]}' for k in rd)+
          "\n  assumed: "+(", ".join(f'{k}={spec["values"][k]["v"]}' for k in asm) or "none")+f"\nnext: bin/design.sh {P}")
if a[0]=="--from-read":
    r=json.load(open(a[1])); P=os.path.abspath(a[2]); U=r.get("units","in"); dom=r.get("domain",prof.get("default_domain","metal"))
    vals={}; ASK=list(r.get("unclear",[]))+list(r.get("questions",[]))
    def num(x):   # 3-1/2, 1 1/4", 2.5in, 64 mm, 1,5 -> float (None if not a number)
        if isinstance(x,(int,float)) or x is None: return x
        t=str(x).strip().replace('"',"").replace("in","").replace("mm","").replace("cm","").replace(",",".").strip()
        m=re.fullmatch(r"(\d+(?:\.\d+)?)?(?:[\s-]*(\d+)/(\d+))?",t)
        if not m or not (m[1] or m[2]): return x
        return (float(m[1]) if m[1] else 0)+(int(m[2])/int(m[3]) if m[2] else 0)
    for k,v in r.get("values",{}).items():
        v=v if isinstance(v,dict) else {"v":v}
        if v.get("v") is None: continue   # not on the drawing -> becomes an assumption below (never a 'read' None)
        x=num(v["v"])
        if isinstance(x,(int,float)) and x<=0: ASK.append(f"{k} reads as {v['v']}: that can't be right, what is it?"); continue
        vals[k]=V(x,v.get("src","read"),v.get("unit",U),v.get("note",""))
        if v.get("unclear"): ASK.append(f"{k}: I read {v['v']} {U} but it's unclear ({v['unclear']}). Is that right?")
    r["holes"]=[dict(h,**{k2:num(h.get(k2)) for k2 in ("x","y","d")}) for h in r.get("holes",[]) if all(h.get(k2) is not None for k2 in ("x","y","d"))]
    shape=r.get("shape","plate"); defaults={"in":dict(t=0.25,L=12,W=6,H=4),"mm":dict(t=3,L=100,W=50,H=30)}[U]
    if dom=="wood" and U=="in": defaults["t"]=0.75
    mat=r.get("material") or {"print":"PLA","wood":"plywood","laser":"acrylic"}.get(dom,"steel")
    need={"plate":["L","W","t"],"profile":["t"],"box":["L","W","H"]}.get(shape,[])
    for k in need:
        if k not in vals: vals[k]=V(defaults[k],"assumed",U,"not on the drawing - Sketch assumption")
    for k in need:
        if vals[k]["src"]=="assumed": ASK.append(f"{k} isn't on the drawing: I assumed {vals[k]['v']} {U}. What should it be?")
    if "L" in vals and "W" in vals:
        for i,h in enumerate(r.get("holes",[])):
            if not (0<h["x"]<vals["L"]["v"] and 0<h["y"]<vals["W"]["v"]) or h["d"]>=min(vals["L"]["v"],vals["W"]["v"]): ASK.append(f"hole {i+1} at ({h['x']}, {h['y']}) d{h['d']} falls off or fills the {vals['L']['v']} x {vals['W']['v']} part: which dimension did I misread?")
    if r.get("scale_from"): ASK.append(f"sizes scaled from {r['scale_from']} in the photo: measure one edge to confirm")
    holes=[{k2:(f"={h[k2]}" if False else h[k2]) for k2 in("x","y","d")} for h in r.get("holes",[])]
    for i,h in enumerate(r.get("holes",[])):   # each hole position/size becomes an editable read value
        for k2 in("x","y","d"): vals[f"h{i+1}_{k2}"]=V(h[k2],h.get("src_d" if k2=="d" else "src_pos",h.get("src","read")),U)
    hl=[{"x":f"=h{i+1}_x","y":f"=h{i+1}_y","d":f"=h{i+1}_d"} for i in range(len(r.get("holes",[])))]
    if shape=="plate":
        kind="pbox" if dom=="print" else ("panel" if dom in("wood","laser") else "plate")
        args={"L":"=L","W":"=W","H":"=t"} if kind=="pbox" else {"L":"=L","W":"=W","t":"=t"}
        parts=[{"name":"part","label":r.get("label","Plate"),"kind":kind,"material":mat,"args":args,"features":{"holes":hl},**({"group":"part"} if dom=="print" else {})}]
        dims=[{"label":"L","v":"=L","view":"top","axis":"h"},{"label":"W","v":"=W","view":"top","axis":"v"}]
    elif shape=="profile":
        parts=[{"name":"part","label":r.get("label","Profile"),"kind":"profile","material":mat,"args":{"outer":r["outer"],"t":"=t","holes":[[h["x"],h["y"],h["d"]] for h in r.get("holes",[])]}}]
        dims=[]
    elif shape=="box":
        parts=[{"name":"part","kind":"pbox","group":"part","material":mat,"args":{"L":"=L","W":"=W","H":"=H"},"features":{"holes":hl}}]
        dims=[{"label":"L","v":"=L","view":"front","axis":"h"},{"label":"H","v":"=H","view":"front","axis":"v"}]
    else: parts=r["parts"]; dims=[]
    if r.get("qty",1)>1 and shape in("plate","profile","box"):   # several identical parts: repeat, spaced apart for the render
        vals["qty"]=V(r["qty"],r.get("qty_src","read"))
        sp="=i*(L+1)" if "L" in vals else "=i*120"
        parts[0].update(repeat={"var":"i","n":"=qty"},name="part{i}",at=[sp,0,0]); parts[0].pop("group",None)
    write(P,dict(name=os.path.basename(P),title=r.get("title","Imported drawing"),domain=dom,units=U,ask=f"from drawing {r.get('source','')}",
                 values=vals,derived=r.get("derived",{}),parts=parts,joints=r.get("joints",[]),dims=r.get("dims",dims),source=r.get("source"),**({"questions":ASK} if ASK else {})))
    for q_ in ASK: print("[ask] "+q_)
    sys.exit()
F=os.path.abspath(a[0]); P=os.path.abspath(a[1]); ext=F.lower().rsplit(".",1)[-1]
src=f"{P}/source"; os.makedirs(src,exist_ok=True); dst=f"{src}/{os.path.basename(F)}"
if F!=dst: shutil.copy(F,dst)
title=opt("--title",os.path.splitext(os.path.basename(F))[0].replace("_"," ").title())
if ext in("step","stp","iges","igs","brep","stl","3mf","obj","ply","glb","gltf","off"):
    sys.path.insert(0,B); import kit
    dom=opt("--domain",prof.get("default_domain","print"))
    U=opt("--units","mm" if dom=="print" else prof.get("units","in"))   # cut/weld pipelines work in inches
    sh=kit.load_cad(dst); bb=sh.BoundingBox(); L0,W0,H0=bb.xlen,bb.ylen,bb.zlen
    fu=opt("--file-units","mm"); k=(1/25.4 if (fu=="mm" and U=="in") else 25.4 if (fu=="in" and U=="mm") else 1)
    dom=opt("--domain",prof.get("default_domain","print"))
    mat=opt("--material",{"print":"PLA","wood":"plywood","laser":"acrylic"}.get(dom,"steel"))
    note=f"measured from {os.path.basename(F)} (file units assumed {fu})"
    vals=dict(L=V(round(L0*k,3),"read",U,note),W=V(round(W0*k,3),"read",U,note),H=V(round(H0*k,3),"read",U,note))
    vals["filament" if dom=="print" else "material"]=V(mat,"assumed","","material not in the file")
    stock="print" if dom=="print" else "plate"
    part={"name":"body","label":title,"kind":"imported","material":"=filament" if dom=="print" else mat,
          "args":{"file":dst,"sx":f"=L/{L0}","sy":f"=W/{W0}","sz":f"=H/{H0}","stock":stock,"section":f"imported {os.path.basename(F)}"}}
    if dom=="print": part["group"]="body"
    thin=min(L0,W0,H0)
    def prism():
        try:
            sec=cq.Workplane("XY").add(sh.translate(cq.Vector(0,0,-bb.zmin))).section(H0/2).faces().vals()
            return abs(sum(f.Area() for f in sec)*H0-sh.Volume())<0.02*sh.Volume()
        except Exception: return False
    import cadquery as cq
    if dom!="print" and H0==thin and thin*k<=(1.0 if U=="in" else 25) and prism():   # flat plate-like part lying in XY: make it a cuttable flat
        part["args"]["stock"]="plate"; part["flat_t"]="=H"
    spec=dict(name=os.path.basename(P),title=title,domain=dom,units=U,ask=f"import {os.path.basename(F)}",values=vals,parts=[part],
              dims=[{"label":"L","v":"=L","view":"front","axis":"h"},{"label":"H","v":"=H","view":"front","axis":"v"},{"label":"W","v":"=W","view":"side","axis":"h"}],
              source=dst)
    write(P,spec)
elif ext in("dxf","svg"):
    from shapely.geometry import Polygon,LineString,Point
    from shapely.ops import polygonize,unary_union
    U=opt("--units","in" if prof.get("units")!="mm" else "mm"); lines=[]; circles=[]
    if ext=="dxf":
        import ezdxf
        from ezdxf import path as ezp
        doc=ezdxf.readfile(dst); msp=doc.modelspace()
        for e in msp:
            t=e.dxftype()
            if t=="CIRCLE": circles.append((e.dxf.center.x,e.dxf.center.y,2*e.dxf.radius)); continue
            try:
                pth=ezp.make_path(e); pts=[(v.x,v.y) for v in pth.flattening(0.01)]
                if len(pts)>1: lines.append(pts)
            except Exception: pass
        ins=doc.header.get("$INSUNITS",0); fu={1:"in",4:"mm",5:"cm",6:"m"}.get(ins,"in" if U=="in" else "mm")
    else:
        import svgelements as se
        svg=se.SVG.parse(dst)
        for el in svg.elements():
            if isinstance(el,se.Circle) and el.rx==el.ry: circles.append((float(el.cx),-float(el.cy),2*float(el.rx))); continue
            if isinstance(el,se.Shape):
                pth=se.Path(el); 
                for sub in pth.as_subpaths():
                    sp=se.Path(sub); n=max(8,int(sp.length()/1.0)) if sp.length() else 0
                    if n: lines.append([(float(p.x),-float(p.y)) for p in (sp.point(i/n) for i in range(n+1))])
        fu="px"   # svgelements resolves width/viewBox to CSS px (96/in)
    polys=list(polygonize(unary_union([LineString(l) for l in lines if len(l)>1]))) if lines else []
    if not polys and circles:   # round part
        c=max(circles,key=lambda c:c[2]); circles.remove(c); polys=[Point(c[0],c[1]).buffer(c[2]/2,resolution=64)]
    outer=Polygon(max(polys,key=lambda p:Polygon(p.exterior).area).exterior); inner=[Polygon(p.exterior) for p in polys if Polygon(p.exterior).area<outer.area-1e-9 and outer.contains(p.representative_point())]
    k={("px","mm"):25.4/96,("px","in"):1/96,("mm","in"):1/25.4,("in","mm"):25.4,("cm","in"):1/2.54,("cm","mm"):10}.get((fu,U),1)
    tol=0.002 if fu=="in" else 0.02*(96/25.4 if fu=="px" else 1)
    outer=outer.simplify(tol); inner=[q.simplify(tol) for q in inner]   # drop collinear sample points, keep arcs within tolerance
    x0,y0=outer.bounds[0],outer.bounds[1]; T=lambda x,y:(round((x-x0)*k,4),round((y-y0)*k,4))
    holes=[[*T(x,y),round(d*k,4)] for x,y,d in circles if outer.contains(Point(x,y))]
    inn=[[T(*p) for p in list(ip.exterior.coords)[:-1]] for ip in inner if not any(Point(ip.centroid).distance(Point(h[0]/k+x0,h[1]/k+y0))<1e-3 for h in holes)]
    W0=(outer.bounds[2]-x0)*k; H0=(outer.bounds[3]-y0)*k
    dom=opt("--domain",{"print":"laser"}.get(prof.get("default_domain"),prof.get("default_domain","metal")))
    mat=opt("--material",{"wood":"plywood","laser":"acrylic"}.get(dom,"steel"))
    t0=float(opt("--t",{"in":0.25 if dom!="wood" else 0.75,"mm":3}[U]))
    note=f"measured from {os.path.basename(F)} (file units {fu})"
    vals=dict(W=V(round(W0,4),"read",U,note),H=V(round(H0,4),"read",U,note),t=V(t0,"assumed",U,"thickness isn't in a 2D file"),material=V(mat,"assumed"))
    part={"name":"part","label":title,"kind":"profile","material":mat,"args":{"outer":[T(*p) for p in list(outer.exterior.coords)[:-1]],"holes":holes,"inner":inn,"t":"=t","sx":f"=W/{W0}","sy":f"=H/{H0}"}}
    write(P,dict(name=os.path.basename(P),title=title,domain=dom,units=U,ask=f"import {os.path.basename(F)}",values=vals,parts=[part],
                 dims=[{"label":"W","v":"=W","view":"top","axis":"h"},{"label":"H","v":"=H","view":"top","axis":"v"}],source=dst))
elif ext=="pdf" or ext in("png","jpg","jpeg","webp","bmp","tif","tiff"):
    rd=f"{src}/read"; os.makedirs(rd,exist_ok=True); text=""
    if ext=="pdf":
        text=subprocess.run(["pdftotext","-layout",dst,"-"],capture_output=True,text=True).stdout
        subprocess.run(["pdftoppm","-r","150","-png",dst,f"{rd}/page"],check=True)
        imgs=sorted(f"{rd}/{f}" for f in os.listdir(rd) if f.startswith("page"))
    else:
        import cv2
        im=cv2.imread(dst); g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY); h,w=g.shape
        # find the paper: largest 4-corner contour -> perspective warp
        e=cv2.Canny(cv2.GaussianBlur(g,(5,5),0),40,120); e=cv2.dilate(e,np.ones((5,5),np.uint8))
        cs,_=cv2.findContours(e,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE); warp=g; note="no paper edge found; used full image"
        for c in sorted(cs,key=cv2.contourArea,reverse=True)[:5]:
            ap=cv2.approxPolyDP(c,0.02*cv2.arcLength(c,True),True)
            if len(ap)==4 and cv2.contourArea(ap)>0.2*h*w:
                inkall=cv2.adaptiveThreshold(cv2.GaussianBlur(g,(3,3),0),255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,31,12)
                inkall=cv2.morphologyEx(inkall,cv2.MORPH_OPEN,np.ones((2,2),np.uint8)); qm=np.zeros_like(g); cv2.fillPoly(qm,[ap.reshape(-1,2)],255)
                inside=cv2.countNonZero(cv2.bitwise_and(inkall,cv2.dilate(qm,np.ones((15,15),np.uint8)))); tot=max(1,cv2.countNonZero(inkall))
                if inside<0.93*tot: note=f"a big rectangle ({100*inside/tot:.0f}% of the ink) is a drawn part, not the paper: kept the full image"; continue   # v1.0.6: never crop off the dimensions
                p=ap.reshape(4,2).astype(np.float32); s_=p.sum(1); d_=np.diff(p,axis=1).ravel()
                q=np.array([p[np.argmin(s_)],p[np.argmin(d_)],p[np.argmax(s_)],p[np.argmax(d_)]],np.float32)
                Wd=int(max(np.linalg.norm(q[0]-q[1]),np.linalg.norm(q[2]-q[3]))); Hd=int(max(np.linalg.norm(q[0]-q[3]),np.linalg.norm(q[1]-q[2])))
                M=cv2.getPerspectiveTransform(q,np.array([[0,0],[Wd,0],[Wd,Hd],[0,Hd]],np.float32)); warp=cv2.warpPerspective(g,M,(Wd,Hd)); note="paper found and de-skewed"; break
        # residual rotation from ink lines
        ink=cv2.threshold(warp,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]; ln=cv2.HoughLinesP(ink,1,np.pi/360,80,minLineLength=warp.shape[1]//8,maxLineGap=8)
        if ln is not None:
            ang=[math.degrees(math.atan2(l[3]-l[1],l[2]-l[0])) for l in ln.reshape(-1,4)]; ang=[x for x in ang if abs(x)<20]
            if ang:
                r_=float(np.median(ang)); Mr=cv2.getRotationMatrix2D((warp.shape[1]/2,warp.shape[0]/2),r_,1); warp=cv2.warpAffine(warp,Mr,(warp.shape[1],warp.shape[0]),borderValue=255); note+=f", rotated {r_:.1f} deg"
        clean=cv2.adaptiveThreshold(cv2.GaussianBlur(warp,(3,3),0),255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,12)
        cv2.imwrite(f"{rd}/clean.png",clean); cv2.imwrite(f"{rd}/deskewed.png",warp); shutil.copy(dst,f"{rd}/original.{ext}"); imgs=[f"{rd}/clean.png",f"{rd}/deskewed.png",f"{rd}/original.{ext}"]; print("image:",note)
        print("  photo of a real part (tape/ruler)? read original.* and scale from the tape; set scale_from in read.json")
    cand=sorted(set(re.findall(r'(?:Ø|R|⌀)?\s*\d+(?:[.,]\d+)?(?:\s*-\s*\d+/\d+|\s+\d+/\d+)?\s*(?:"|in\b|mm\b|cm\b)?',text)),key=len,reverse=True)
    cand=[c.strip() for c in cand if re.search(r"\d",c) and (len(c.strip())>1)][:60]
    tpl=dict(source=dst,title=title,domain=prof.get("default_domain","metal"),units=prof.get("units","in"),shape="plate|profile|box|parts",
             values={"L":{"v":None},"W":{"v":None},"t":{"v":None}},holes=[{"x":None,"y":None,"d":None}],unclear=[],scale_from=None,
             _rules="v: number or fraction text ('3-1/2', '1 1/4\"'). Leave null what isn't shown (-> assumed + asked). Add 'unclear':'why' to a value you're not sure of, and free questions to unclear[]. Photo of a part with a tape/ruler: set scale_from to what you scaled from.",
             _how="Open the images, read every dimension yourself, fill this in as read.json (leave out what isn't shown; it becomes an assumption), then: import_file.py --from-read read.json PROJECT")
    json.dump(tpl,open(f"{rd}/read_template.json","w"),indent=1); open(f"{rd}/text.txt","w").write(text)
    print("READ WITH VISION:",*imgs,sep="\n  "); print("dimension-like text found:",cand[:25] if cand else "none (scanned/handwritten: read the image)")
    print(f"template: {rd}/read_template.json  ->  import_file.py --from-read read.json {P}")
else: sys.exit(f"unsupported file type .{ext}")

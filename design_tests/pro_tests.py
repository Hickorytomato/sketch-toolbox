#!/usr/bin/env python3
"""pro_tests.py: v1.0.5 pro features on lumber_shelf, steel_bracket and salt_shaker (they must be shipped already: ship_tests.sh).
 1. every feature's gate check PASSes and its phone files are in send_list.txt
 2. break tests: each pro gate blocks a generator-level break (files re-hashed, so only the pro check can catch it)
 3. feedback loop: coupon pick -> learned.json -> next build applies it and says so (then undone)
 4. revision table: a spec change shows up in the next version's revision table
 5. live prices: local supplier page -> dated price on the quote; unreachable link -> build still ships with prices.json label"""
import json,os,shutil,subprocess,sys,glob,hashlib,re,threading,http.server,functools
ROOT=os.environ.get("SKETCH_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY=sys.executable; B=f"{ROOT}/bin"
ENV=dict(os.environ,SKETCH_ROOT=ROOT); ENV.pop("SKETCH_LIVE_PRICES",None)
ok=bad=0
def rep(good,msg):
    global ok,bad
    good=bool(good); ok+=good; bad+=not good; print(("ok   " if good else "BAD  ")+msg)
def latest(p):
    vs=sorted(glob.glob(f"{ROOT}/design_tests/{p}/v*/ship"),key=lambda x:int(x.split("/v")[-1].split("/")[0])); return vs[-1].rsplit("/",1)[0] if vs else None
def run(*a,env=ENV): return subprocess.run(list(a),capture_output=True,text=True,env=env)
def build(p,env=ENV):
    run(f"{B}/design.sh",f"design_tests/{p}","--sketch",env=env); r=run(f"{B}/design.sh",f"design_tests/{p}","--final",env=env); return r.returncode,r.stdout+r.stderr
WANT={"lumber_shelf":["cutday","coupon","prices","quote","revision","explode"],"steel_bracket":["cutday","coupon","prices","quote","revision","explode"],"salt_shaker":["coupon","prices","quote","revision","explode"],
      "mixed_table":["crossmachine","cutday","coupon","prices","quote","revision","explode"],"print_panels":["crossmachine","cutday","coupon","prices","quote","revision","explode"]}   # steering 2: mixed material / multi-machine
PHONE={"cutday":"CUT_DAY/cut_day-1.png","coupon":"COUPONS/coupons-1.png","quote":"QUOTE/customer_quote-1.png","explode":"BUILD_STEPS/step_01.png"}
# 1 ------------------------------------------------------------------
for p,areas in WANT.items():
    V=latest(p)
    if not V: rep(False,f"{p}: no shipped build (run ship_tests.sh first)"); continue
    r=run(PY,f"{B}/ship.py",f"{ROOT}/design_tests/{p}"); out=r.stdout
    for a in areas: rep(re.search(rf"^\[PASS\] {a} ",out,re.M) is not None,f"{p}: {a} gate PASS")
    sl=open(f"{V}/ship/send_list.txt").read() if os.path.exists(f"{V}/ship/send_list.txt") else ""
    for a in areas:
        if a in PHONE: rep(PHONE[a] in sl,f"{p}: {PHONE[a]} in send_list.txt")
    rep("DRAWINGS/drawings.pdf" in sl and "QUOTE/customer_quote.pdf" in sl,f"{p}: drawings + quote PDFs in send_list.txt")
# 2 ------------------------------------------------------------------
def regen(F):
    json.dump(dict(files={os.path.relpath(os.path.join(r,f),F):hashlib.sha256(open(os.path.join(r,f),'rb').read()).hexdigest() for r,_,fs in os.walk(F) for f in fs if f!='.gen.json'}),open(F+'/.gen.json','w'))
def J(p,fn):
    d=json.load(open(p)); fn(d); json.dump(d,open(p,"w"))
def cut_drop(F): J(f"{F}/cut_day.json",lambda d:d["cuts"].pop())
def cut_kerf(F): J(f"{F}/cut_day.json",lambda d:d["kerf"]["wood"].__setitem__(0,0.0))
def cut_overlap(F):
    def f(d): s=d["sheets"][0]["strips"][0]["parts"]; s[0]["x"]=s[1]["x"] if len(s)>1 else s[0]["x"]+999
    J(f"{F}/cut_day.json",f)
def cut_tag(F): J(f"{F}/cut_day.json",lambda d:d["tags"].update({k:"Z9" for k in list(d["tags"])[:1]}))
def cp_drop(F): J(f"{F}/coupons.json",lambda d:d["coupons"].clear())
def cp_steps(F): J(f"{F}/coupons.json",lambda d:d["coupons"][0].update(steps=[9,10,11]))
def q_total(F): J(f"{F}/customer_quote.json",lambda d:d.update(total=d["total"]+50))
def q_line(F): J(f"{F}/customer_quote.json",lambda d:d["lines"][0].update(amount=(d["lines"][0]["amount"] or 0)+5))
def q_shop(F): J(f"{F}/customer_quote.json",lambda d:d.update(shop={"name":"Somebody's Shop"}))
def pr_fake(F): J(f"{F}/customer_quote.json",lambda d:d["lines"][0].update(source="Home Depot 2026-10-01"))
def rv_letter(F): J(f"{F}/doc_meta.json",lambda d:d.update(rev="A"))
def rv_weld(F): J(f"{F}/doc_meta.json",lambda d:d["welds"].pop())
def ex_tag(F):
    V=os.path.dirname(F); J(f"{V}/explode/explode.json",lambda d:[l.update(tag="Q7") for s in d["steps"] for l in s["labels"]][:0])
def _stl(F,nm,fn):
    import trimesh; p=f"{os.path.dirname(F)}/stl/{nm}.stl"; m=trimesh.load(p,force="mesh"); m=fn(m); m.export(p)
def xm_move(F): _stl(F,"mount_FL",lambda m:(m.apply_translation([0.1,0,0]),m)[1])          # plate holes 0.1 in off the top's holes
def xm_nohole(F):
    import trimesh; _stl(F,"bracket_1",lambda m:trimesh.creation.box(bounds=m.bounds))      # printed bracket without its bolt holes
def xm_kerf(F): J(glob.glob(f"{F}/gcode_wood/*router.json")[0],lambda d:d.update(comp=0.0))  # router program without bit offset
def xm_bom(F):
    P=f"{os.path.dirname(F)}/parts.json"; J(P,lambda d:[r.update(names=[n for n in r.get("names",[]) if n!="bracket_2"]) for r in d["cutlist"]])
def ex_img(F): os.remove(sorted(glob.glob(f"{F}/build_steps/*.png"))[0])
BRK=[("cut day: a cut missing",cut_drop,"lumber_shelf","does not match the BOM"),("cut day: kerf not from settings",cut_kerf,"lumber_shelf","not the saw kerf"),
     ("cut day: parts overlap on sheet",cut_overlap,"steel_bracket","overlap"),("cut day: tags differ from BOM",cut_tag,"lumber_shelf","tags differ"),
     ("coupon missing for a tight fit",cp_drop,"salt_shaker","no test coupon"),("coupon steps don't bracket the value",cp_steps,"salt_shaker","bracket"),
     ("quote total wrong",q_total,"steel_bracket","total"),("quote line != BOM price",q_line,"lumber_shelf","differs from the priced BOM"),
     ("quote shop not from profile",q_shop,"salt_shaker","not the ones in your profile"),("fake dated store price",pr_fake,"lumber_shelf","dated store price"),
     ("revision letter wrong",rv_letter,"salt_shaker","revision letter"),("weld callouts != model",rv_weld,"steel_bracket","weld callout"),
     ("exploded tag not in BOM",ex_tag,"steel_bracket","not BOM tags"),("exploded image missing",ex_img,"lumber_shelf","step image"),
     ("cross-machine: plate holes off the top's holes",xm_move,"mixed_table","worst case needs"),("cross-machine: printed part has no bolt hole",xm_nohole,"print_panels","has no hole on the"),
     ("cross-machine: router offset not applied",xm_kerf,"mixed_table","is not half of the router"),("cross-machine: part missing from the combined BOM",xm_bom,"print_panels","combined BOM")]
for name,fn,p,key in BRK:
    V=latest(p); T=f"{ROOT}/design_tests/_protamper"; shutil.rmtree(T,ignore_errors=True); os.makedirs(T)
    n=V.rsplit("/v",1)[1]; shutil.copytree(V,f"{T}/v{n}",ignore=shutil.ignore_patterns("ship")); shutil.copy(f"{V}/../spec.json",T)
    for k in range(1,int(n)):   # keep the previous version for the revision diff
        if os.path.exists(f"{V}/../v{k}/spec.json"): os.makedirs(f"{T}/v{k}",exist_ok=True); [shutil.copy(f"{V}/../v{k}/{x}",f"{T}/v{k}/") for x in ("spec.json","parts.json") if os.path.exists(f"{V}/../v{k}/{x}")]
    F=f"{T}/v{n}/fab"; fn(F); regen(F)
    r=run(PY,f"{B}/ship.py",T); fl=[l for l in r.stdout.splitlines() if l.startswith("[FAIL]") and "SHIP BLOCKED" not in l]
    good=r.returncode==1 and any(key in l for l in fl) and not os.path.exists(f"{T}/v{n}/ship")
    rep(good,f"break blocks: {name}"+("" if good else f" -> {fl[:2] or r.stdout[-200:]}"))
    shutil.rmtree(T,ignore_errors=True)
# 2b mixed builds: exploded steps label material + machine, show bolts and welds --------------
for p,mach,weld in (("mixed_table",("router","plasma"),True),("print_panels",("3D print","router"),False)):
    V=latest(p)
    if not V: rep(False,f"{p}: no shipped build"); continue
    E=json.load(open(f"{V}/explode/explode.json")); pr=[l.get("proc","") for s_ in E["steps"] for l in s_["labels"]]
    for m_ in mach: rep(any(m_ in x for x in pr),f"{p}: exploded labels name the machine '{m_}'")
    rep(all(x and " - " in x for x in pr),f"{p}: every exploded part label says material - machine ({len(pr)} labels)")
    rep(any(s_.get("bolts") for s_ in E["steps"]),f"{p}: bolts drawn in the exploded steps ({max(len(s_.get('bolts',[])) for s_ in E['steps'])} max/step)")
    if weld: rep(any(s_.get("welds") for s_ in E["steps"]),f"{p}: welds listed on the step that makes them")
    sl=open(f"{V}/ship/send_list.txt").read(); fo=[l.split("/")[0] for l in sl.splitlines() if l.split("/")[0] in ("PRINTER","LASER","ROUTER","PLASMA")]
    rep(len(set(fo))>=2 and [k for i,k in enumerate(fo) if i==0 or fo[i-1]!=k]==list(dict.fromkeys(fo)),f"{p}: send_list groups files by machine ({' > '.join(dict.fromkeys(fo))})")
# 3 ------------------------------------------------------------------
LJ=f"{B}/learned.json"; bak=open(LJ).read() if os.path.exists(LJ) else None
try:
    r=run(PY,f"{B}/feedback.py",f"design_tests/salt_shaker","--coupon","thread","--pick","3"); rep(r.returncode==0 and "thread_clearance_mm" in r.stdout,"feedback: thread coupon pick 3 stored")
    rc,out=build("salt_shaker"); V=latest("salt_shaker")
    rep(rc==0 and "[PASS] learn" in out,"feedback: next salt_shaker build applies it and ships")
    rep("SHOP CORRECTION APPLIED" in open(f"{V}/fab/HOW_TO_USE.txt").read() and "SHOP CORRECTION APPLIED" in open(f"{V}/fab/assumptions.txt").read(),"feedback: build says which correction was applied")
    rep(abs(json.load(open(f"{V}/parts.json"))["params"]["clear"]-0.6)<1e-9,"feedback: thread clearance in the model is the learned 0.6 mm")
    r=run(PY,f"{B}/feedback.py",f"design_tests/lumber_shelf","slot tight"); rep(r.returncode!=0,"feedback: refuses a feature the build doesn't have")
finally:
    if bak is None:
        if os.path.exists(LJ): os.remove(LJ)
    else: open(LJ,"w").write(bak)
rc,out=build("salt_shaker"); rep(rc==0 and "[PASS] learn" not in out,"feedback: undone -> back to the spec value")
# 4 ------------------------------------------------------------------
SP=f"{ROOT}/design_tests/lumber_shelf/spec.json"; orig=open(SP).read()
try:
    s=json.loads(orig); k=next(k for k,v in s["values"].items() if isinstance(v.get("v"),(int,float)) and k in("H","height","shelf_h","W","width")) if any(k in s["values"] for k in ("H","height","shelf_h","W","width")) else next(k for k,v in s["values"].items() if isinstance(v.get("v"),(int,float)))
    s["values"][k]["v"]=s["values"][k]["v"]+2; open(SP,"w").write(json.dumps(s,indent=1))
    rc,out=build("lumber_shelf"); V=latest("lumber_shelf") if rc==0 else None
    M=json.load(open(f"{V}/fab/doc_meta.json")) if V else {}
    rep(rc==0 and any(c.startswith(f"{k} ") for c in M.get("revisions",[{}])[-1].get("changes",[])),f"revision table lists the change to {k}: {M.get('revisions',[{}])[-1].get('changes',[])[:3]}")
finally:
    open(SP,"w").write(orig)
build("lumber_shelf")
# 5 ------------------------------------------------------------------
SD=f"{ROOT}/design_tests/_shop"; os.makedirs(SD,exist_ok=True)
open(f"{SD}/2x4.html","w").write('<html><head><script type="application/ld+json">{"@type":"Product","offers":{"price":"4.98"}}</script></head></html>')
srv=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=SD)); port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
PL=f"{B}/price_links.json"; PC=f"{B}/price_cache.json"; bl=open(PL).read() if os.path.exists(PL) else None; bc=open(PC).read() if os.path.exists(PC) else None
try:
    json.dump({"2x4":{"url":f"http://127.0.0.1:{port}/2x4.html","unit":"stick:96","store":"Test Supplier"},"2x8":{"url":"http://10.255.255.1/nope","unit":"stick:96"}},open(PL,"w"))
    if os.path.exists(PC): os.remove(PC)
    rc,out=build("lumber_shelf",env=dict(ENV,SKETCH_LIVE_PRICES="1")); V=latest("lumber_shelf")
    q=json.load(open(f"{V}/fab/customer_quote.json")); lp=json.load(open(f"{V}/fab/live_prices.json"))
    live=[l for l in q["lines"] if "Test Supplier" in l["source"]]
    rep(rc==0 and live and all(re.search(r"\d{4}-\d\d-\d\d",l["source"]) for l in live),f"live prices: {len(live)} quote line(s) from the supplier page with an 'as of' date")
    rep(any("fetch failed" in (v.get("why") or "") for v in lp["lines"].values()) and rc==0,"live prices: unreachable link -> prices.json label, build still ships")
finally:
    srv.shutdown()
    for p_,b_ in ((PL,bl),(PC,bc)):
        if b_ is None:
            if os.path.exists(p_): os.remove(p_)
        else: open(p_,"w").write(b_)
    shutil.rmtree(SD,ignore_errors=True)
build("lumber_shelf")
print(f"pro tests: {ok} ok, {bad} bad"); sys.exit(1 if bad else 0)

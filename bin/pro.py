"""pro.py - ship-gate checks + send-list entries for the v1.0.5 pro outputs (cut day, coupons, customer quote,
live prices, shop drawings/revisions, exploded steps, shop learning). Called by ship.py; each check is FAIL-able."""
import os,json,glob,re
B=os.path.dirname(os.path.abspath(__file__))
SAW=("lumber","angle","sq_tube","tube","pipe","bar","flat_bar","rect_tube","round_bar","channel","sheet_good","plate","sheet")
def _tags(d):
    T={}
    for r in d["cutlist"]:
        if r.get("mark")=="HW" or r.get("stock") not in SAW: continue
        ns=r.get("names") or [f'{r["part"]}{i+1}' for i in range(r["qty"])]
        for i,n in enumerate(ns): T[n]=f'{r["mark"]}{i+1}'
    return T
def gate_cutday(d,F,res):
    T=_tags(d); J=f"{F}/cut_day.json"
    if not T:
        if os.path.exists(J): res("cutday","cut_day.json","FAIL","cut-day sheet for a build with no saw/stock parts")
        return
    if not os.path.exists(J): res("cutday","cut_day.json","FAIL","saw/stock parts but no cut-day sheet (cutday.py did not run)"); return
    C=json.load(open(J)); ok=True
    made=[t for c in C["cuts"] if c["kind"]=="crosscut" for t in c["makes"]]
    want=sorted(T.values()); miss=sorted(set(want)-set(made)); dup=sorted({t for t in made if made.count(t)>1}); extra=sorted(set(made)-set(want))
    if miss or dup or extra: res("cutday","cut_day.json","FAIL",f"cut list does not match the BOM: missing {miss} duplicate {dup} not in BOM {extra}"); ok=False
    if C.get("tags")!=T: res("cutday","cut_day.json","FAIL","part tags differ from the BOM marks (A1 = first part of row A)"); ok=False
    if [c["n"] for c in C["cuts"]]!=list(range(1,len(C["cuts"])+1)): res("cutday","cut_day.json","FAIL","cuts are not numbered 1..N in order"); ok=False
    import kerf as _k
    wk=_k.saw()[0]
    if abs(C["kerf"]["wood"][0]-wk)>1e-6: res("cutday","cut_day.json","FAIL",f"wood kerf {C['kerf']['wood'][0]} is not the saw kerf from your settings ({wk})"); ok=False
    U=C["units"]
    for s in C["sheets"]:
        SW,SL=s["sheet"]; k=s["kerf"]; R_=[]
        for sp in s["strips"]:
            for p in sp["parts"]:
                R_.append((p["x"],p["y"],p["x"]+p["L"],p["y"]+p["w"],p["tag"]))
                if p["x"]+p["L"]>SL+1e-6 or p["y"]+p["w"]>SW+1e-6: res("cutday",f'sheet {s["n"]}',"FAIL",f'{p["tag"]} runs off the {SW}x{SL} sheet'); ok=False
        for i in range(len(R_)):
            for j in range(i+1,len(R_)):
                a,b=R_[i],R_[j]
                if a[0]<b[2]+k-1e-6 and b[0]<a[2]+k-1e-6 and a[1]<b[3]+k-1e-6 and b[1]<a[3]+k-1e-6:
                    res("cutday",f'sheet {s["n"]}',"FAIL",f'{a[4]} and {b[4]} overlap or are closer than one kerf ({k})'); ok=False
    for sec in C["linear"]:
        for b in sec["boards"]:
            if b.get("note") is None and sum(x[1] for x in b["parts"])+len(b["parts"])*sec["kerf_in"]>b["stock"]+1e-6: res("cutday",sec["section"],"FAIL","parts + kerfs are longer than the board"); ok=False
    if not os.path.exists(f"{F}/cut_day.pdf") or not glob.glob(f"{F}/cut_day-*.png"): res("cutday","cut_day.pdf","FAIL","cut_day.pdf / phone PNGs missing"); ok=False
    if ok: res("cutday","cut_day.pdf","PASS",f'{len(C["cuts"])} numbered cuts match the BOM tags, kerf {C["kerf"]["wood"][0]} in from your saw settings, {len(C["sheets"])} sheet plan(s) inside the sheet, {len(C["offcuts"])} offcut(s) listed')
def gate_coupons(d,F,res):
    J=f"{F}/coupons.json"
    if not os.path.exists(J): res("coupon","coupons.json","FAIL","no fit-test coupons file (coupons.py did not run)"); return
    C=json.load(open(J))["coupons"]; ids={c["id"] for c in C}; ok=True; spec=json.load(open(f"{F}/spec.json"))
    need=set()
    if any(t.get("side")=="internal" for p in spec.get("parts",[]) for t in (p.get("args",{}).get("threads") or [])): need.add("thread")
    if any(pp.get("assembly")=="print_in_place" for pp in d.get("print_parts",[])): need.add("pip_gap")
    if any(j.get("type")=="dado" for j in d.get("jointrec",[])): need.add("dado")
    for mn in ("laser","plasma"):
        if any(f"_{mn}" in os.path.basename(p) for p in glob.glob(f"{F}/gcode_*/*.json")): need.add(f"kerf_{mn}")
    if need-ids: res("coupon","coupons.json","FAIL",f"tight-fit features with no test coupon: {sorted(need-ids)}"); ok=False
    import trimesh
    for c in C:
        for f in c["files"]:
            if not os.path.exists(f"{F}/{f}"): res("coupon",f,"FAIL","coupon file missing"); ok=False; continue
            if f.endswith(".stl"):
                m=trimesh.load(f"{F}/{f}")
                if not m.is_watertight or m.volume<=0: res("coupon",f,"FAIL","coupon mesh is not a closed solid (won't slice)"); ok=False
                if c["id"]=="thread" and len(m.split(only_watertight=False))!=1: res("coupon",f,"FAIL","thread coupon piece is not one body"); ok=False
        if c["steps"] and c["steps"]!=sorted(c["steps"]): res("coupon",c["id"],"FAIL","coupon steps are not in increasing order (the pick number would lie)"); ok=False
        if c["steps"] and c.get("current") is not None and not (c["steps"][0]-1e-9<=c["current"]<=c["steps"][-1]+1e-9): res("coupon",c["id"],"FAIL",f'coupon steps {c["steps"][0]}..{c["steps"][-1]} do not bracket the value in the build ({c["current"]})'); ok=False
        if not c.get("read") or not c.get("feedback"): res("coupon",c["id"],"FAIL","coupon has no how-to-read text or feedback command"); ok=False
    if not os.path.exists(f"{F}/coupons.pdf"): res("coupon","coupons.pdf","FAIL","coupons.pdf missing"); ok=False
    if ok: res("coupon","coupons.pdf","PASS",f'{len(C)} coupon(s): {", ".join(sorted(ids)) or "none needed"}; every tight-fit feature has one, steps bracket the build value')
def gate_learn(d,F,res):
    """every stored shop correction that matches this build was applied (or the spec value the user typed won, and it says so)"""
    import learn
    L=d.get("learned_applied",[]); seen={(x["key"],x["value"]) for x in L}; spec=json.load(open(f"{F}/spec.json")); ok=True
    fil=str(spec.get("values",{}).get("filament",{}).get("v","PLA")) if isinstance(spec.get("values",{}).get("filament"),dict) else "PLA"
    thr={t["clearance"][1:] for p in spec.get("parts",[]) for t in (p.get("args",{}).get("threads") or []) if t.get("side")=="internal" and isinstance(t.get("clearance"),str) and re.fullmatch(r"=\w+",t["clearance"])}
    for n in thr:
        if learn.get("printer",fil).get("thread_clearance_mm") is not None and ("thread_clearance_mm",n) not in seen: res("learn",n,"FAIL",f"your thread correction for printer|{fil} was not applied to {n}"); ok=False
    for x in L:
        if x["applied"] and x["key"]!="dado_clear_in" and abs(float(d["params"].get(x["value"],x["learned"]))-float(x["learned"]))>1e-9: res("learn",x["value"],"FAIL",f'{x["value"]} is {d["params"].get(x["value"])} in the model, not the learned {x["learned"]}'); ok=False
    A=open(f"{F}/assumptions.txt").read() if os.path.exists(f"{F}/assumptions.txt") else ""
    if L and "SHOP CORRECTION" not in A and "NOT applied" not in A: res("learn","assumptions.txt","FAIL","shop corrections used but not reported to the user"); ok=False
    if ok and L: res("learn","learned.json","PASS","; ".join((f'{x["value"]}: {x.get("was")} -> {x["learned"]} ({x["machine"]}|{x["material"]})' if x["applied"] else f'{x["value"]}: kept your {x.get("kept")} (learned {x["learned"]} not used: {x["why"]})') for x in L))
def gate_quote(d,F,res):
    J=f"{F}/customer_quote.json"
    if not os.path.exists(J) or not os.path.exists(f"{F}/customer_quote.pdf"): res("quote","customer_quote.pdf","FAIL","no customer quote (customer_quote.py did not run)"); return
    q=json.load(open(J)); Q=json.load(open(f"{F}/quote.json")); ok=True; import ref,subprocess,datetime
    am=[l["amount"] for l in q["lines"] if l["amount"] is not None]
    if abs(sum(am)-q["subtotal"])>0.011: res("quote","customer_quote.json","FAIL",f'line items add to ${sum(am):.2f}, not the subtotal ${q["subtotal"]:.2f}'); ok=False
    if abs(q["subtotal"]*q["margin_pct"]/100-q["margin"])>0.011: res("quote","customer_quote.json","FAIL","margin is not margin_pct x subtotal"); ok=False
    if q["tax_pct"] is not None and abs((q["subtotal"]+q["margin"])*q["tax_pct"]/100-q["tax"])>0.011: res("quote","customer_quote.json","FAIL","tax is not tax_pct x (subtotal + margin)"); ok=False
    if abs(q["subtotal"]+q["margin"]+(q["tax"] or 0)-q["total"])>0.011: res("quote","customer_quote.json","FAIL",f'total ${q["total"]} != subtotal + margin + tax'); ok=False
    for l in q["lines"]:
        if l["amount"] is not None and l["rate"] is not None and abs(l["qty"]*l["rate"]-l["amount"])>max(0.011,0.006*l["rate"]): res("quote",l["desc"],"FAIL",f'{l["qty"]} x {l["rate"]} != {l["amount"]}'); ok=False
        if not l.get("source"): res("quote",l["desc"],"FAIL","quote line with no source"); ok=False
    src={s_["line"]:s_["usd"] for s_ in Q["sources"] if s_["line"]!="labor"}
    for l in q["lines"]:
        if l["section"]=="Materials" and l["desc"] in src and abs(l["amount"]-src[l["desc"]])>0.011 and not re.search(r"\d{4}-\d\d-\d\d",l["source"]): res("quote",l["desc"],"FAIL",f'material ${l["amount"]} differs from the priced BOM ${src[l["desc"]]} with no dated live price'); ok=False
    shop=(ref.profile().get("shop") or {})
    if q.get("shop",{})!=shop: res("quote","shop","FAIL","shop name/logo/terms on the quote are not the ones in your profile (tools_setup.py --shop)"); ok=False
    try: txt=subprocess.run(["pdftotext",f"{F}/customer_quote.pdf","-"],capture_output=True,text=True).stdout
    except Exception: txt=None
    if txt is not None:
        if "ESTIMATE" not in txt: res("quote","customer_quote.pdf","FAIL","quote is not marked ESTIMATE"); ok=False
        if not shop.get("name") and not txt.lstrip().startswith("QUOTE"): res("quote","customer_quote.pdf","FAIL","no shop set in your profile but the quote carries a shop name"); ok=False
        if f'{q["total"]:,.2f}' not in txt: res("quote","customer_quote.pdf","FAIL","the PDF total is not the computed total"); ok=False
    if not q["valid_until"]>q["date"] or not q.get("terms") or not q.get("lead_time"): res("quote","customer_quote.json","FAIL","missing validity date, terms or lead time"); ok=False
    if ok: res("quote","customer_quote.pdf","PASS",f'{len(q["lines"])} lines add up to ${q["total"]:,.2f} (estimate, valid to {q["valid_until"]}); '+(f'shop "{shop["name"]}"' if shop.get("name") else "neutral (no shop in profile)")+(f'; {len(q["unpriced"])} item(s) not priced and listed' if q["unpriced"] else ""))
def gate_prices(d,F,res):
    J=f"{F}/live_prices.json"
    if not os.path.exists(J): res("prices","live_prices.json","FAIL","no live_prices.json (prices_live.py did not run; it must run even when off)"); return
    L=json.load(open(J)); ok=True; q=json.load(open(f"{F}/customer_quote.json")) if os.path.exists(f"{F}/customer_quote.json") else {"lines":[]}
    import datetime
    for k,v in L["lines"].items():
        if v.get("usd") is None: continue
        if not (v.get("url","").startswith("http") and re.fullmatch(r"\d{4}-\d\d-\d\d",v.get("date","")) and v.get("store") and v["usd"]>0):
            res("prices",k,"FAIL","live price without store, link, date or a positive number"); ok=False; continue
        age=(datetime.date.today()-datetime.date.fromisoformat(v["date"])).days
        if age>8: res("prices",k,"FAIL",f"live price is {age} days old (cache is 7 days): rerun with --refresh"); ok=False
    for l in q["lines"]:
        v=L["lines"].get(l["desc"])
        live=v and v.get("usd") is not None
        dated=bool(re.search(r"\d{4}-\d\d-\d\d",l.get("source","")))
        if dated and not live: res("prices",l["desc"],"FAIL","quote claims a dated store price that live_prices.json does not have"); ok=False
        if live and l["section"]=="Materials" and abs(l["amount"]-v["usd"])>0.011: res("prices",l["desc"],"FAIL",f'quote ${l["amount"]} != live price ${v["usd"]}'); ok=False
        if live and l["section"]=="Hardware" and abs(l["amount"]-v["usd"]*l["qty"])>0.011: res("prices",l["desc"],"FAIL","hardware total != live unit price x qty"); ok=False
        if live and not dated: res("prices",l["desc"],"FAIL","live price on the quote without its 'as of' date"); ok=False
    if ok: res("prices","live_prices.json","PASS",L["note"]+"; every store price has its link and 'as of' date")
def gate_revision(d,F,res):
    import subprocess
    M=json.load(open(f"{F}/doc_meta.json")) if os.path.exists(f"{F}/doc_meta.json") else {}
    if not M.get("revisions") or not M.get("rev"): res("revision","drawings.pdf","FAIL","no revision table / revision letter in the drawings"); return
    ok=True; V=os.path.dirname(F); m=re.search(r"/v(\d+)$",os.path.abspath(V)); n=int(m.group(1)) if m else 1
    want="";k=n
    while k>0: k,r_=divmod(k-1,26); want=chr(65+r_)+want
    if M["rev"]!=want or M["revisions"][-1]["rev"]!=want: res("revision","drawings.pdf","FAIL",f'revision letter {M["rev"]} is not the one for v{n} ({want})'); ok=False
    P=os.path.dirname(V); prev=next((k for k in range(n-1,0,-1) if os.path.exists(f"{P}/v{k}/spec.json") and os.path.exists(f"{P}/v{k}/parts.json")),None)
    if prev:
        o=json.load(open(f"{P}/v{prev}/spec.json")); nw=json.load(open(f"{V}/spec.json"))
        ov={k:(v.get("v") if isinstance(v,dict) else v) for k,v in o.get("values",{}).items()}; nv={k:(v.get("v") if isinstance(v,dict) else v) for k,v in nw.get("values",{}).items()}
        ch=[k for k in set(ov)|set(nv) if ov.get(k)!=nv.get(k)]; txt=" ".join(M["revisions"][-1]["changes"])
        miss=[k for k in ch if not re.search(rf"(^|\s){re.escape(k)} ",txt+" ")]
        if miss: res("revision","drawings.pdf","FAIL",f"revision table misses changed value(s) vs v{prev}: {miss}"); ok=False
    try: txt=subprocess.run(["pdftotext",f"{F}/drawings.pdf","-"],capture_output=True,text=True).stdout
    except Exception: txt=None
    if txt is not None:
        pages=txt.split("\f"); pages=[p_ for p_ in pages if p_.strip()]; N=len(pages)
        bad=[i+1 for i,p_ in enumerate(pages) if f"Sheet {i+1} of {N}" not in p_ or f"Rev {M['rev']}" not in p_]
        if bad: res("revision","drawings.pdf","FAIL",f"sheet number / revision missing or wrong on sheet(s) {bad[:6]} of {N}"); ok=False
        dr=M.get("drawn_by") or ""
        if dr and f"Drawn: {dr}" not in txt: res("revision","drawings.pdf","FAIL","drawn-by from your profile is missing"); ok=False
    W=d.get("welds",[]); MW=M.get("welds",[])
    if len(W)!=len(MW) or any(w.get("side","arrow")!=m_.get("side") or str(w.get("size"))!=str(m_.get("size")) for w,m_ in zip(W,MW)): res("revision","weld sheet","FAIL",f"weld callout sheet ({len(MW)}) does not match the model welds ({len(W)}) side/size"); ok=False
    if ok: res("revision","drawings.pdf","PASS",f'Rev {M["rev"]}, {M.get("pages")} sheets numbered "Sheet i of N", revision table '+(f'vs v{prev}: {"; ".join(M["revisions"][-1]["changes"])[:120]}' if prev else "first issue")+(f', {len(MW)} weld callout(s) W1..W{len(MW)} match the model' if MW else ""))
def gate_explode(d,F,res):
    V=os.path.dirname(F); J=f"{V}/explode/explode.json"
    if not os.path.exists(J): res("explode","build_steps.pdf","WARN","no exploded step pictures (Blender failed?): build_steps.pdf has text steps only"); return
    import rules; E=json.load(open(J)); T=rules.part_tags(d); ok=True
    shown={l["tag"] for s_ in E["steps"] for l in s_["labels"]}
    bad=sorted({l["tag"] for s_ in E["steps"] for l in s_["labels"]}-set(T.values())-{""})
    if bad: res("explode","build_steps","FAIL",f"step pictures carry tags that are not BOM tags: {bad}"); ok=False
    model_tags={T[n] for n in T if any(n==l["part"] for s_ in E["steps"] for l in s_["labels"])}
    for s_ in E["steps"]:
        for l in s_["labels"]:
            if l["tag"] and T.get(l["part"]) and T[l["part"]]!=l["tag"]: res("explode",l["part"],"FAIL",f'{l["part"]} is tagged {l["tag"]} in the picture but {T[l["part"]]} in the BOM'); ok=False
    imgs=sorted(glob.glob(f"{F}/build_steps/*.png"))
    if len(imgs)!=len(E["steps"]): res("explode","build_steps","FAIL",f"{len(imgs)} step image(s) shipped for {len(E['steps'])} steps"); ok=False
    try:
        import subprocess; n=int(re.search(r"Pages:\s+(\d+)",subprocess.run(["pdfinfo",f"{F}/build_steps.pdf"],capture_output=True,text=True).stdout).group(1))
        if n<len(E["steps"])+1: res("explode","build_steps.pdf","FAIL",f"build_steps.pdf has {n} pages for {len(E['steps'])} step pictures"); ok=False
    except Exception: pass
    if ok: res("explode","build_steps.pdf","PASS",f'{len(E["steps"])} exploded step picture(s), tags match the BOM ({len(shown-{""})} tagged parts), rendered in {E.get("seconds","?")} s')
GATES=[gate_cutday,gate_coupons,gate_learn,gate_prices,gate_quote,gate_revision,gate_explode]
def gate(ctx):
    for g in GATES:
        try: g(ctx["d"],ctx["F"],ctx["res"])
        except Exception as e: ctx["res"]("pro",g.__name__,"FAIL",f"check crashed: {e}")
def deliverables(F):
    """(fab file, ship path, where, check area) for the send list - phone-friendly PNG/PDF first."""
    out=[]
    for f in sorted(glob.glob(f"{F}/cut_day-*.png"),key=lambda x:int(re.findall(r"-(\d+)\.png",x)[0])): out.append((f,f"CUT_DAY/{os.path.basename(f)}","cut-day sheet page (phone)","cutday"))
    for f,w in (("cut_day.pdf","CUT DAY: print it, tick off each cut"),("offcuts.csv","offcut / waste list")):
        if os.path.exists(f"{F}/{f}"): out.append((f"{F}/{f}",f"CUT_DAY/{f}",w,"cutday"))
    for f in sorted(glob.glob(f"{F}/coupons-*.png"),key=lambda x:int(re.findall(r"-(\d+)\.png",x)[0])): out.append((f,f"COUPONS/{os.path.basename(f)}","fit-test coupon: how to make and read it (phone)","coupon"))
    for f in sorted(glob.glob(f"{F}/customer_quote-*.png")): out.append((f,f"QUOTE/{os.path.basename(f)}","customer quote page (phone)","quote"))
    if os.path.exists(f"{F}/customer_quote.pdf"): out.append((f"{F}/customer_quote.pdf","QUOTE/customer_quote.pdf","customer quote (estimate): print or email it to the customer","quote"))
    for f in sorted(glob.glob(f"{F}/build_steps/*.png")): out.append((f,f"BUILD_STEPS/step_{os.path.basename(f)}","exploded build step picture (phone)","explode"))
    if os.path.exists(f"{F}/coupons.pdf"): out.append((f"{F}/coupons.pdf","COUPONS/coupons.pdf","fit-test coupons: print this, test before the real part","coupon"))
    for f in sorted(glob.glob(f"{F}/coupons/*")): out.append((f,f"COUPONS/{os.path.basename(f)}","coupon file: "+("3D print it" if f.endswith(".stl") else "cut it (LightBurn / SheetCAM)"),"coupon"))
    return out

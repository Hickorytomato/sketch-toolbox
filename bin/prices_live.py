#!/usr/bin/env python3
"""prices_live.py VDIR OUTDIR [--refresh]  -> live_prices.json  (v1.0.5 feature 4, OPTIONAL, never blocks a build)
Current prices for BOM items, each with store, link, price and the date it was read ('price as of').
Off unless profile live_prices=true (tools_setup.py --live-prices on) or SKETCH_LIVE_PRICES=1.
Where prices come from:
  bin/price_links.json (yours, kept by the installer): {"2x4": {"url": "https://<supplier product page>", "unit": "stick:96"},
        "plate": {"url": "...", "unit": "lb"}, "1/2-13 x 1-1/2 in grade 5 zinc hex bolt": {"url": "...", "unit": "ea", "pack": 25}}
        unit = ft | lb | sqft | ea | stick:<length in> | sheet:<w>x<l> (price of one stick/sheet -> per ft/sqft); pack = items per package.
        Read from the page's structured data (JSON-LD offers.price, itemprop=price, og/product:price:amount). No number -> no price.
  Big-box search pages (Home Depot / Lowe's / Menards) block automated reads (403 / bot wall, tested 2026-10-14), so Sketch does
  NOT scrape them: it gives you a search link per item to check by hand, and you can paste a product link into price_links.json.
Polite: robots.txt honoured, >= 3 s between requests, <= 12 requests per build, 8 s timeout, cache 7 days (bin/price_cache.json).
Any failure -> that line keeps its prices.json price, labelled with why."""
import sys,os,json,re,time,urllib.request,urllib.parse,urllib.robotparser,datetime,html
B=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,B); import ref
V,O=sys.argv[1],sys.argv[2]; REFRESH="--refresh" in sys.argv
PROF=ref.profile(); ON=bool(PROF.get("live_prices")) or os.environ.get("SKETCH_LIVE_PRICES")=="1"
LINKS=json.load(open(f"{B}/price_links.json")) if os.path.exists(f"{B}/price_links.json") else {}
CP=f"{B}/price_cache.json"; CACHE=json.load(open(CP)) if os.path.exists(CP) else {}
TTL=7*86400; GAP=3.0; MAXREQ=12; UA="SketchToolbox/1.0.5 (maker price check; +https://github.com/Hickorytomato/sketch-toolbox)"
Q=json.load(open(f"{O}/quote.json")); d=json.load(open(f"{V}/parts.json"))
PR={}
for f in ("prices_default.json","prices.json"):
    if os.path.exists(f"{B}/{f}"):
        for k,v in json.load(open(f"{B}/{f}")).items():
            if isinstance(v,dict): PR.setdefault(k,{}).update(v)
def search_links(q):
    s=urllib.parse.quote_plus(q)
    return {"Home Depot":f"https://www.homedepot.com/s/{urllib.parse.quote(q)}","Lowe's":f"https://www.lowes.com/search?searchTerm={s}","Menards":f"https://www.menards.com/main/search.html?search={s}"}
nreq=[0]; last=[0.0]
def allowed(url):
    try:
        u=urllib.parse.urlparse(url); rp=urllib.robotparser.RobotFileParser(f"{u.scheme}://{u.netloc}/robots.txt"); rp.read(); return rp.can_fetch(UA,url)
    except Exception: return True   # no robots.txt reachable: the page fetch itself decides
def parse_price(t):
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',t,re.S|re.I):
        try: j=json.loads(m.group(1).strip())
        except Exception: continue
        st=[j]
        while st:
            x=st.pop()
            if isinstance(x,list): st+=x; continue
            if not isinstance(x,dict): continue
            of=x.get("offers")
            for o in (of if isinstance(of,list) else [of] if of else []):
                if isinstance(o,dict):
                    p=o.get("price") or o.get("lowPrice") or (o.get("priceSpecification") or {}).get("price")
                    if p not in(None,""):
                        try: return float(str(p).replace(",","").replace("$","")),"JSON-LD offers.price"
                        except ValueError: pass
            st+=[v for v in x.values() if isinstance(v,(dict,list))]
    for pat,lab in ((r'itemprop=["\']price["\'][^>]*content=["\']([\d.,]+)',"itemprop=price"),(r'content=["\']([\d.,]+)["\'][^>]*itemprop=["\']price',"itemprop=price"),
                    (r'property=["\'](?:og|product):price:amount["\'][^>]*content=["\']([\d.,]+)',"og:price:amount"),(r'content=["\']([\d.,]+)["\'][^>]*property=["\'](?:og|product):price:amount',"og:price:amount")):
        m=re.search(pat,t,re.I)
        if m: return float(m.group(1).replace(",","")),lab
    return None,"no structured price on the page"
def fetch(url):
    c=CACHE.get(url)
    if c and not REFRESH and time.time()-c["t"]<TTL: return c["price"],c["how"]+" (cached)",c["date"]
    if nreq[0]>=MAXREQ: return None,f"request budget ({MAXREQ}/build) used: rerun later",None
    if not allowed(url): return None,"robots.txt disallows it",None
    w=GAP-(time.time()-last[0])
    if w>0: time.sleep(w)
    nreq[0]+=1; last[0]=time.time()
    try:
        r=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html"}),timeout=8); t=r.read(3_000_000).decode("utf-8","replace")
    except Exception as e: return None,f"fetch failed ({type(e).__name__}: {str(e)[:60]})",None
    p,how=parse_price(t); dt=datetime.date.today().isoformat()
    if p is not None: CACHE[url]=dict(price=p,how=how,date=dt,t=time.time())
    return p,how,dt
def per_unit(p,spec):
    u=str(spec.get("unit","ea")); p=p/float(spec.get("pack",1))
    if u.startswith("stick:"): return p/(float(u.split(":")[1])/12),"ft"
    if u.startswith("sheet:"): w,l=[float(x) for x in u.split(":")[1].split("x")]; return p/(w*l/144),"sqft"
    return p,u
out=dict(enabled=ON,date=datetime.date.today().isoformat(),lines={},search={},note="")
items=[]
for s in Q["sources"]:
    m=re.search(r"price_per_(ft|lb|sqft)\[([^\]]+)\]",s["source"])
    if m: items.append((s["line"],m.group(2),m.group(1),s["usd"]))
for r in d["cutlist"]:
    if r.get("mark")=="HW": items.append((r["material"],r["material"],"ea",None))
seen=set()
for line,key,unit,usd in items:
    if line in seen: continue
    seen.add(line); out["search"][line]=search_links(key)
    if not ON: continue
    spec=LINKS.get(key) or LINKS.get(line)
    if not spec: out["lines"][line]=dict(usd=None,why=f"no supplier link for '{key}' in price_links.json (big-box search pages block automated reads)"); continue
    p,how,dt=fetch(spec["url"])
    if p is None: out["lines"][line]=dict(usd=None,why=how,url=spec["url"]); continue
    pu,uu=per_unit(p,spec); store=spec.get("store") or urllib.parse.urlparse(spec["url"]).netloc
    if unit=="ea": out["lines"][line]=dict(usd=round(pu,2),unit="ea",store=store,url=spec["url"],date=dt,how=how); continue
    old=PR.get(f"price_per_{unit}",{}).get(key)
    if uu!=unit or not old: out["lines"][line]=dict(usd=None,why=f"link unit {uu} does not match the BOM unit {unit} for {key}",url=spec["url"]); continue
    qty=usd/old; out["lines"][line]=dict(usd=round(pu*qty,2),qty=round(qty,3),unit=unit,per=round(pu,4),store=store,url=spec["url"],date=dt,how=how,was=usd)
if ON: json.dump(CACHE,open(CP,"w"),indent=1)
out["note"]=("live prices on: "+f'{sum(1 for v in out["lines"].values() if v.get("usd") is not None)} of {len(out["lines"])} item(s) priced live, {nreq[0]} request(s)') if ON else "live prices off (tools_setup.py --live-prices on): prices.json used, labelled; search links included"
json.dump(out,open(f"{O}/live_prices.json","w"),indent=1)
print("[prices]",out["note"])

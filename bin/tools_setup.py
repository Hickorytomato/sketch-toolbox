#!/usr/bin/env python3
"""tools_setup.py --have printer,laser,router,plasma,saw,welder,hand [--printer bambu_a1] [--filament PLA] [--units in|mm]
Records which tools the maker has (onboarding). Enables/disables machines in machines.json, sets printers.json 'active',
and writes profile.json {tools, default_domain, units}. Only a printer -> default_domain=print, units=mm, printer-friendly outputs.
  tools_setup.py --show
  tools_setup.py --saw "table saw" [--saw-kerf 0.125]      your saw (kerf for cut lists; blank kerf = sourced default)
  tools_setup.py --kerf-test plasma steel 0.25 --drawn 2.000 --measured 1.938
        cut a square drawn 2.000 with NO kerf comp, measure it: kerf = drawn - measured. Beats the table every time.
  tools_setup.py --kerf plasma steel 0.25 0.062             or enter a kerf you already know ('*' for any material/thickness)
  tools_setup.py --laser-source co2|fiber  --plasma-amps 45
  tools_setup.py --shop name="Your Shop" logo=/path/logo.png drawn_by="J. Smith" tax_pct=8.25 lead_time="2-3 weeks" valid_days=30 terms="..." address="..." phone=... email=...
        your shop details for the customer quote + title blocks (blank = neutral quote). machine_rate.plasma=45 labor_rate=75 margin_pct=25 go to machines.json shop
  tools_setup.py --shop-clear
  tools_setup.py --rates                 optional quick step: set your real rates and prices (asks one by one; Enter keeps, 'y' = mine as is)
  tools_setup.py --rates labor_rate=65 margin_pct=20 machine_rate.router=30 price_per_ft.2x4=0.95 price_per_sqft.plywood=1.9 [confirm=all]
        non-interactive form; confirm=all marks every current value as yours (no more 'Sketch default' flags)
  tools_setup.py --machine router "Shapeoko 4" [--software "Carbide Motion"] [--units mm]
        your exact machine + software (printer/laser/plasma/router). Picks the output profile (G-code flavor+units or file type).
        Unknown software or a format Sketch can't write -> it says so and uses plain DXF/SVG/STL. --machine router clear = forget.
  tools_setup.py --machines              asks for each enabled machine in turn (Enter = skip)
"""
import sys,os,json
B=os.path.dirname(os.path.abspath(__file__)); a=sys.argv[1:]
M=json.load(open(f"{B}/machines.json")); PR=json.load(open(f"{B}/printers.json")); pf=f"{B}/profile.json"
prof=json.load(open(pf)) if os.path.exists(pf) else {}
if not a or a[0] in("-h","--help"): print(__doc__); sys.exit(0)
def opt(k,d=None): return a[a.index(k)+1] if k in a else d
KEEP=("machine_setup","kerf_measured","saws","shop","live_prices","confirmed_rates","tolerance_measured")
def _save(): json.dump(M,open(f"{B}/machines.json","w"),indent=1); json.dump(prof,open(pf,"w"),indent=1)
def _k(mn,mat,t): import kerf; return f"{mn}|{kerf.mcls(mat) if mat!='*' else '*'}|{round(float(t),4) if t!='*' else '*'}"
def _confirm(k): c=prof.setdefault("confirmed_rates",[]); c.append(k) if k not in c else None
if "--machine" in a or "--machines" in a:
    import outputs as _o
    ms=prof.setdefault("machine_setup",{})
    def _set(kind,model,sw,units=None):
        if kind not in("printer","laser","plasma","router"): sys.exit(f"machine kind must be printer, laser, plasma or router (got {kind})")
        if model.lower()=="clear": ms.pop(kind,None); print(f"{kind}: forgotten (generic outputs)"); return
        pid,msg=_o.match(kind,model,sw); ms[kind]=dict(model=model,software=sw,profile=pid,msg=msg,**({"units":units} if units else {}))
        o=_o.selected(kind,prof); print(f"{kind}: {model}{' / '+sw if sw else ''} -> {o['label']} ({', '.join(o['files'])}"+(f"; G-code {o['gcode']['flavor']} {o['gcode']['units']}" if o.get('gcode') else "")+")")
        if msg: print("   "+msg)
    if "--machine" in a:
        i=a.index("--machine"); _set(a[i+1],a[i+2] if len(a)>i+2 and not a[i+2].startswith("--") else "",opt("--software",""),opt("--units"))
    else:
        for kind in("printer","laser","plasma","router"):
            if not M.get(kind,{}).get("enabled"): continue
            cur=ms.get(kind,{}); mdl=input(f"{kind}: exact make/model [{cur.get('model','skip')}]: ").strip() or cur.get("model","")
            if not mdl: continue
            sw=input(f"  software you send files with (LightBurn, Bambu Studio, FireControl, Mach4, LinuxCNC, VCarve...) [{cur.get('software','')}]: ").strip() or cur.get("software","")
            _set(kind,mdl,sw)
    _save(); print(json.dumps(ms,indent=1)); sys.exit(0)
if "--rates" in a:
    sys.path.insert(0,B); import defaults
    P=json.load(open(f"{B}/prices.json")); sh=M.setdefault("shop",{}); mr=sh.setdefault("machine_rate_per_h",{})
    KEYS=[("labor_rate",sh.get("labor_rate",75)),("margin_pct",sh.get("margin_pct",25))]+[(f"machine_rate.{m}",v) for m,v in mr.items() if not m.startswith("_") and M.get(m,{}).get("enabled",m=="printer")]
    PD=json.load(open(f"{B}/prices_default.json")) if os.path.exists(f"{B}/prices_default.json") else {}
    KEYS+=[(f"{s_}.{k}",v) for s_ in ("price_per_ft","price_per_sqft","price_per_lb","buy_each") for k,v in {**{k_:v_ for k_,v_ in PD.get(s_,{}).items() if not str(k_).startswith("_") and isinstance(v_,(int,float))},**P.get(s_,{})}.items()]
    CONF_ALL=lambda: [ (_confirm(k_), (P.setdefault(k_.split(".")[0],{}).setdefault(k_.split(".",1)[1],v_) if k_.startswith(("price_","buy_")) else None)) for k_,v_ in KEYS]
    def put(k,v):
        if k.startswith("machine_rate."): mr[k.split(".",1)[1]]=v
        elif k in("labor_rate","margin_pct","shop_hours_per_day"): sh[k]=v
        elif "." in k: s_,i=k.split(".",1); P.setdefault(s_,{})[i]=v
        else: sys.exit(f"unknown rate {k}")
        _confirm(k)
    kv=[x for x in a[a.index("--rates")+1:] if "=" in x and not x.startswith("--")]
    if kv:
        for x in kv:
            k,v=x.split("=",1)
            if k=="confirm" and v=="all": CONF_ALL(); continue
            try: put(k,float(v))
            except ValueError: sys.exit(f"{k} must be a number")
    elif sys.stdin.isatty():
        print("Set your real rates and prices (Enter = keep as Sketch default, y = this value is mine, or type a number):")
        for k,v in KEYS:
            r=input(f"  {k} [{v}{' - Sketch default' if defaults.is_default(k,v) else ''}]: ").strip()
            if r.lower()=="y": _confirm(k); (P.setdefault(k.split(".")[0],{}).setdefault(k.split(".",1)[1],v) if k.startswith(("price_","buy_")) else None)
            elif r:
                try: put(k,float(r))
                except ValueError: print("    not a number, kept")
    json.dump(P,open(f"{B}/prices.json","w"),indent=1); _save()
    left=[k for k,v in KEYS if defaults.is_default(k,(P.get(k.split(".")[0],{}).get(k.split(".",1)[1]) if k.startswith(("price_","buy_")) else mr.get(k.split(".",1)[1]) if k.startswith("machine_rate.") else sh.get(k,v)))]
    print(f"{len(KEYS)-len(left)} of {len(KEYS)} rates/prices are yours; still Sketch defaults: {', '.join(left) if left else 'none'}"); sys.exit(0)
if "--shop" in a or "--shop-clear" in a or "--live-prices" in a:
    if "--shop-clear" in a: prof.pop("shop",None)
    if "--live-prices" in a: prof["live_prices"]=opt("--live-prices")=="on"
    if "--shop" in a:
        sh=prof.setdefault("shop",{})
        for kv in a[a.index("--shop")+1:]:
            if kv.startswith("--") or "=" not in kv: break
            k,v=kv.split("=",1)
            try: v=float(v) if k in("tax_pct","valid_days","labor_rate","margin_pct") or k.startswith("machine_rate.") else v
            except ValueError: sys.exit(f"{k} must be a number")
            if k.startswith("machine_rate."): M["shop"].setdefault("machine_rate_per_h",{})[k.split(".",1)[1]]=v; _confirm(k)
            elif k in("labor_rate","margin_pct"): M["shop"][k]=v; _confirm(k)
            else: sh[k]=v
    _save()
elif "--saw" in a or "--kerf-test" in a or "--kerf" in a or "--laser-source" in a or "--plasma-amps" in a:
    km=prof.setdefault("kerf_measured",{})
    if "--saw" in a:
        prof.setdefault("saws",{})[opt("--saw")]={}
        if opt("--saw-kerf"): km[f"saw|{opt('--saw')}"]=float(opt("--saw-kerf"))
    if "--kerf-test" in a:
        i=a.index("--kerf-test"); mn,mat,t=a[i+1:i+4]; k=float(opt("--drawn"))-float(opt("--measured"))
        if not 0<k<0.5: sys.exit(f"kerf {k:.4f} in makes no sense: cut the square with no kerf comp and measure across flats")
        km[_k(mn,mat,t)]=round(k,4); print(f"measured kerf {mn} {mat} {t}: {k:.4f} in")
    if "--kerf" in a:
        i=a.index("--kerf"); mn,mat,t,k=a[i+1:i+5]; km[_k(mn,mat,t)]=float(k)
    if "--laser-source" in a: M["laser"]["source"]=opt("--laser-source")
    if "--plasma-amps" in a: M["plasma"]["amps"]=f'{opt("--plasma-amps")} A'
    _save()
elif "--show" not in a:
    have=[t.strip() for t in (opt("--have","") or "").split(",") if t.strip()]
    for m in("plasma","laser","router","printer"): M[m]["enabled"]=m in have
    if opt("--printer") in PR["printers"]: PR["active"]=opt("--printer"); M["printer"]["bed_mm"]=PR["printers"][PR["active"]]["bed"]
    if opt("--filament") in PR["filaments"]: M["printer"]["filament"]=opt("--filament")
    fab={"plasma","welder","laser","router","saw","hand"}&set(have)
    dom="print" if have and not fab else "metal" if {"plasma","welder"}&set(have) else "wood" if {"router","saw","hand"}&set(have) else "laser" if "laser" in have else "print"
    old={k:prof[k] for k in KEEP if k in prof}
    prof=dict(**old,tools=have,default_domain=dom,units=opt("--units","mm" if dom=="print" else "in"),printer=PR["active"],filament=M["printer"]["filament"])
    json.dump(M,open(f"{B}/machines.json","w"),indent=1); json.dump(PR,open(f"{B}/printers.json","w"),indent=1); json.dump(prof,open(pf,"w"),indent=1)
print(json.dumps(prof,indent=1)); print("enabled machines:",[k for k,v in M.items() if isinstance(v,dict) and v.get("enabled")])

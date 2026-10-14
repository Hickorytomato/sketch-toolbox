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
  tools_setup.py --shop-clear"""
import sys,os,json
B=os.path.dirname(os.path.abspath(__file__)); a=sys.argv[1:]
M=json.load(open(f"{B}/machines.json")); PR=json.load(open(f"{B}/printers.json")); pf=f"{B}/profile.json"
prof=json.load(open(pf)) if os.path.exists(pf) else {}
if not a or a[0] in("-h","--help"): print(__doc__); sys.exit(0)
def opt(k,d=None): return a[a.index(k)+1] if k in a else d
KEEP=("kerf_measured","saws","shop","live_prices")
def _save(): json.dump(M,open(f"{B}/machines.json","w"),indent=1); json.dump(prof,open(pf,"w"),indent=1)
def _k(mn,mat,t): import kerf; return f"{mn}|{kerf.mcls(mat) if mat!='*' else '*'}|{round(float(t),4) if t!='*' else '*'}"
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
            if k.startswith("machine_rate."): M["shop"].setdefault("machine_rate_per_h",{})[k.split(".",1)[1]]=v
            elif k in("labor_rate","margin_pct"): M["shop"][k]=v
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

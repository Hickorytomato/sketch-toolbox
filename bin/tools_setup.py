#!/usr/bin/env python3
"""tools_setup.py --have printer,laser,router,plasma,saw,welder,hand [--printer bambu_a1] [--filament PLA] [--units in|mm]
Records which tools the maker has (onboarding). Enables/disables machines in machines.json, sets printers.json 'active',
and writes profile.json {tools, default_domain, units}. Only a printer -> default_domain=print, units=mm, printer-friendly outputs.
  tools_setup.py --show"""
import sys,os,json
B=os.path.dirname(os.path.abspath(__file__)); a=sys.argv[1:]
M=json.load(open(f"{B}/machines.json")); PR=json.load(open(f"{B}/printers.json")); pf=f"{B}/profile.json"
prof=json.load(open(pf)) if os.path.exists(pf) else {}
def opt(k,d=None): return a[a.index(k)+1] if k in a else d
if "--show" not in a:
    have=[t.strip() for t in (opt("--have","") or "").split(",") if t.strip()]
    for m in("plasma","laser","router","printer"): M[m]["enabled"]=m in have
    if opt("--printer") in PR["printers"]: PR["active"]=opt("--printer"); M["printer"]["bed_mm"]=PR["printers"][PR["active"]]["bed"]
    if opt("--filament") in PR["filaments"]: M["printer"]["filament"]=opt("--filament")
    fab={"plasma","welder","laser","router","saw","hand"}&set(have)
    dom="print" if have and not fab else "metal" if {"plasma","welder"}&set(have) else "wood" if {"router","saw","hand"}&set(have) else "laser" if "laser" in have else "print"
    prof=dict(tools=have,default_domain=dom,units=opt("--units","mm" if dom=="print" else "in"),printer=PR["active"],filament=M["printer"]["filament"])
    json.dump(M,open(f"{B}/machines.json","w"),indent=1); json.dump(PR,open(f"{B}/printers.json","w"),indent=1); json.dump(prof,open(pf,"w"),indent=1)
print(json.dumps(prof,indent=1)); print("enabled machines:",[k for k,v in M.items() if isinstance(v,dict) and v.get("enabled")])

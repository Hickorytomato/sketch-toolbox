#!/usr/bin/env python3
"""taste.py add kept|rejected <category> "<value>" [note] | taste.py set units in|mm | taste.py show
categories: style, material, finish, lighting, other. Log lives at $SKETCH_ROOT/taste.json. Read 'show' before first guesses."""
import sys,json,os,datetime
F=os.path.join(os.environ.get("SKETCH_ROOT",os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),"taste.json")
d=json.load(open(F)) if os.path.exists(F) else {"units":"in","kept":[],"rejected":[]}
a=sys.argv[1:]
if not a or a[0]=="show":
    print(f"units: {d['units']}")
    for k in("kept","rejected"):
        print(k.upper()+":"); [print(f"  [{e['cat']}] {e['value']}"+(f" — {e['note']}" if e.get('note') else "")) for e in d[k][-30:]]
elif a[0]=="set" and a[1]=="units": d["units"]=a[2]
elif a[0]=="add": d[a[1]].append({"cat":a[2],"value":a[3],"note":a[4] if len(a)>4 else "","at":datetime.date.today().isoformat()})
else: sys.exit(__doc__)
json.dump(d,open(F,"w"),indent=1)

"""Build-replay steps. Captions come from $SKETCH_STEPS (steps.json written by spec_build); fire parts go last."""
import os, json
CAPTIONS=[]
FIRE=("flame","logs","fireglow")
if os.path.exists(os.environ.get("SKETCH_STEPS","")): CAPTIONS=[tuple(x) for x in json.load(open(os.environ["SKETCH_STEPS"]))]
def caption(name):
    n=name.split("__")[-1]
    if n.startswith(FIRE): return None
    best=max((p for p,_ in CAPTIONS if n.startswith(p)),key=len,default=None)
    return dict(CAPTIONS)[best] if best else "Adding the "+n.rstrip("0123456789-").replace("_"," ")
def groups(names):
    out={}
    for n in names:
        c=caption(n)
        if c: out.setdefault(c,[]).append(n)
    order=[c for _,c in CAPTIONS]
    return sorted(out.items(),key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order))
def fire(names): return [n for n in names if n.split("__")[-1].startswith(FIRE)]

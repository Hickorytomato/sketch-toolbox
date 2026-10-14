"""v1.0.6: one-line load note for anything that will carry weight."""
import re,json
NOTE="Not load-rated. Test it before trusting it with weight or people."
KW=r"\b(shel(f|ves)|stands?|seats?|stools?|benche?s?|chairs?|brackets?|racks?|hooks?|hangers?|ladders?|steps?|tables?|desks?|swings?|mounts?|weigh(t|s|ing)?|lbs?|pounds?|kg|load(-bearing)?|hold(s|ing)? up|support(s|ing)?|carr(y|ies))\b"
def text(spec):
    return " ".join([str(spec.get(k,"")) for k in ("ask","title","name","notes")]+[str(p.get("label",""))+" "+str(p.get("name","")) for p in spec.get("parts",[])]).lower()
def needed(spec):
    if spec.get("load_bearing") is not None: return bool(spec["load_bearing"])
    m=re.search(KW,text(spec)); return bool(m)
def why(spec):
    m=re.search(KW,text(spec)); return m[0] if m else ("spec load_bearing" if spec.get("load_bearing") else "")

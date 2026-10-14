#!/usr/bin/env python3
"""buy.py: whole stock you actually buy (v1.0.6). From cut_day.json (stock plan + sheet plan) and the priced BOM:
full boards / sticks at the stock length, full sheets of sheet goods, metal plate as a cut-to-size drop (suppliers sell plate
cut to size; whole 4x8 plate is not a hobby buy), each with what it is used for and the offcut. Unit rates come from the same
priced BOM rows (prices.json / prices_default.json / live price), so every $ keeps its source.
stock_buy(d, F) -> dict(lines=[...], total, covered=[cutlist marks priced here]).  CLI: buy.py VDIR OUTDIR -> OUTDIR/buy.json + buy.csv"""
import os,sys,json,math,csv
B=os.path.dirname(os.path.abspath(__file__))
def _fmt(v): return f"{v:.2f}".rstrip("0").rstrip(".")
def stock_buy(d,F):
    C=json.load(open(f"{F}/cut_day.json")) if os.path.exists(f"{F}/cut_day.json") else {"linear":[],"sheets":[]}
    U=d["params"].get("units","in"); toin=1 if U=="in" else 1/25.4
    LP=json.load(open(f"{F}/live_prices.json")).get("lines",{}) if os.path.exists(f"{F}/live_prices.json") else {}
    row={n:r for r in d["cutlist"] if r.get("mark")!="HW" for n in (r.get("names") or [])}
    def cost(r):   # live price for the row wins (dated), else the BOM price
        lp=LP.get(f'{r["part"]} ({r["material"]}) x{r["qty"]}')
        return (lp["usd"],f'{lp["store"]} {lp["date"]}') if lp and lp.get("usd") is not None else (r.get("cost_usd"),r.get("cost_src","?"))
    lines=[]; covered=set()
    # 1D: price per inch of each row = row cost / row length used; a board costs rate x stock length
    for sec in C.get("linear",[]):
        used={}
        for b in sec["boards"]:
            for n,L in b["parts"]: used[row[n]["mark"]]=used.get(row[n]["mark"],0)+L*toin if n in row else used.get("?",0)
        rate=[];src=[]
        for mk,L in used.items():
            r=next((x for x in d["cutlist"] if x.get("mark")==mk),None)
            if r is None or not L: continue
            c,s=cost(r)
            if c is not None: rate.append(c/L); src.append(s)
            covered.add(mk)
        rpi=sum(rate)/len(rate) if rate else None
        by={}
        for b in sec["boards"]: by.setdefault(round(b["stock"]*toin,3),[]).append(b)
        for st,bs in sorted(by.items()):
            used_in=sum(b["used_with_kerf"]*toin for b in bs); off=[round(b["offcut"]*toin,2) for b in bs]
            each=None if rpi is None else round(rpi*st,2)
            lines.append(dict(kind="board",item=f'{sec["section"]} x {_fmt(st/12)} ft ({_fmt(st)} in)',qty=len(bs),unit="ea",each=each,usd=None if each is None else round(each*len(bs),2),
                              used=f'{_fmt(used_in)} of {_fmt(st*len(bs))} in ({100*used_in/(st*len(bs)):.0f}%)',offcut=", ".join((f"{n} x {_fmt(o)} in" if n>1 else f"{_fmt(o)} in") for o,n in sorted(__import__("collections").Counter(off).items(),key=lambda q:-q[0])),
                              offcut_usd=None if rpi is None else round(rpi*sum(off),2),source=f'{"; ".join(sorted(set(src)))} x whole stock length ({sec.get("stock_len_src","stock.json")})'))
    # 2D: sheet goods = whole sheets; metal plate = cut-to-size drop covering the strips used (rounded up to 1 in)
    for sh in C.get("sheets",[]):
        SW,SL=[x*toin for x in sh["sheet"]]; k=sh.get("kerf",0)*toin
        ns=[p["name"] for st in sh["strips"] for p in st["parts"]]; area=sum(p["L"]*p["w"]*toin*toin for st in sh["strips"] for p in st["parts"])
        rate=[];src=[]
        for mk in {row[n]["mark"] for n in ns if n in row}:
            r=next(x for x in d["cutlist"] if x.get("mark")==mk); ar=sum(p["L"]*p["w"]*toin*toin for st in C["sheets"] for s_ in st["strips"] for p in s_["parts"] if p["name"] in (r.get("names") or []))
            c,s=cost(r)
            if c is not None and ar: rate.append(c/ar); src.append(s)
            covered.add(mk)
        rps=sum(rate)/len(rate) if rate else None
        metal=not ("plywood" in sh["material"] or any(w in sh["material"] for w in ("mdf","wood","birch","acrylic")))
        if metal:
            h=max(st["y"]*toin+st["width"]*toin for st in sh["strips"]); w=max(sum(p["L"]*toin for p in st["parts"])+k*len(st["parts"]) for st in sh["strips"])
            bw,bh=math.ceil(w),math.ceil(h); a=bw*bh; item=f'{sh["material"]} in plate, cut-to-size drop {bw} x {bh} in'; why="plate bought cut to size (Sketch default: most metal suppliers cut plate to order)"
        else:
            bw,bh=SW,SL; a=SW*SL; item=f'{sh["material"]} sheet {_fmt(SW)} x {_fmt(SL)} in'; why=sh.get("sheet_src","stock.json sheet_sizes")
        lines.append(dict(kind="sheet",item=item,qty=1,unit="ea",each=None if rps is None else round(rps*a,2),usd=None if rps is None else round(rps*a,2),
                          used=f'{_fmt(area)} of {_fmt(a)} sq in ({100*area/a:.0f}%)',offcut=f'{_fmt(a-area)} sq in (incl. kerf)'+("" if metal else f'; rip strip {_fmt(sh.get("rip_offcut",0)*toin)} x {_fmt(SL)} in'),
                          offcut_usd=None if rps is None else round(rps*(a-area),2),source=f'{"; ".join(sorted(set(src)))} x whole {"drop" if metal else "sheet"} area ({why})'))
    tot=round(sum(l["usd"] for l in lines if l["usd"] is not None),2)
    return dict(lines=lines,total=tot,covered=sorted(covered),unpriced=[l["item"] for l in lines if l["usd"] is None])
if __name__=="__main__":
    V,O=sys.argv[1],sys.argv[2]; d=json.load(open(f"{V}/parts.json")); R=stock_buy(d,O)
    json.dump(R,open(f"{O}/buy.json","w"),indent=1)
    with open(f"{O}/buy.csv","w",newline="") as fh:
        w=csv.writer(fh); w.writerow(["buy","qty","each","total","used","offcut","offcut value","price source"])
        for l in R["lines"]: w.writerow([l["item"],l["qty"],l["each"],l["usd"],l["used"],l["offcut"],l["offcut_usd"],l["source"]])
    print(f'stock to buy -> {O}/buy.json: {len(R["lines"])} line(s), ${R["total"]:.2f} whole stock')

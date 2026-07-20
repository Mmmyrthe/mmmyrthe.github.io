# -*- coding: utf-8 -*-
"""
Bouwt ../index.html uit _build/listings.json en _build/template.html.
Houdt _build/state.json bij (welke funda-id's eerder gezien zijn) voor 'nieuw'-detectie.
Gebruik:  python3 _build/render.py 2026-07-21
Argument = scandatum (YYYY-MM-DD). Zonder argument wordt de datum uit state niet gewijzigd.
"""
import json, statistics, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCAN_DATE = sys.argv[1] if len(sys.argv) > 1 else "onbekend"
# argv[2] = weergavetekst voor 'laatst bijgewerkt', bv. "21-07-2026 08:03". Anders afgeleid van datum.
def _nl_date(d):
    try:
        y, m, day = d.split("-"); return "%s-%s-%s" % (day, m, y)
    except Exception:
        return d
UPDATED = sys.argv[2] if len(sys.argv) > 2 else _nl_date(SCAN_DATE)

def rd(p, default):
    try:
        return json.load(open(os.path.join(HERE, p)))
    except FileNotFoundError:
        return default

listings = rd("listings.json", [])
state = rd("state.json", {})   # { funda_id: {"firstSeen": "YYYY-MM-DD"} }

def fid(url): return url.rstrip("/").split("/")[-1]

def label_pts(l):
    if l and l.startswith("A"): return 8
    return {"B":6,"C":4,"D":2,"E":1}.get(l, 0)

def score(w):
    s = 40
    tuin = w.get("tuin_m2")
    t = tuin if tuin is not None else max(0, w["perceel"] - 130)
    s += 20 if t>=300 else 16 if t>=200 else 10 if t>=150 else 4
    s += round((400000 - w["prijs"]) / 100000 * 12)
    sk = w["sk"]; s += 0 if sk<=3 else 5 if sk==4 else 8
    woon = w["woon"]; s += 10 if woon>=140 else 8 if woon>=120 else 4 if woon>=100 else 2
    s += label_pts(w.get("label"))
    s += 10 if w.get("zolder") else 0
    return min(100, s)

items = []
seen_now = set()
new_ids = []
for w in listings:
    i = fid(w["url"]); seen_now.add(i)
    first = state.get(i, {}).get("firstSeen")
    is_new = first is None
    if is_new:
        first = SCAN_DATE
        new_ids.append(i)
    tuin = w.get("tuin_m2")
    items.append({
        "id": i, "adres": w["adres"], "plaats": "Surhuisterveen",
        "prijs": w["prijs"], "woon": w["woon"], "perceel": w["perceel"], "sk": w["sk"],
        "label": w.get("label") or "–", "url": w["url"], "score": score(w),
        "tuin": w.get("tuin_note",""), "tuinTwijfel": tuin is not None and tuin < 150,
        "zolder": bool(w.get("zolder")), "voorbehoud": bool(w.get("voorbehoud")),
        "bouwjaar": w.get("bouwjaar",""), "foto": w.get("foto",""), "dist": 0, "rand": False,
        "firstSeen": first, "status": "nieuw" if is_new else "actueel",
    })

items.sort(key=lambda x: -x["score"])

# state bijwerken
newstate = {}
for it in items:
    newstate[it["id"]] = {"firstSeen": it["firstSeen"]}
json.dump(newstate, open(os.path.join(HERE, "state.json"), "w"), ensure_ascii=False, indent=1)

# index.html renderen
n = len(items)
med = int(statistics.median([x["prijs"] for x in items])) if items else 0
tmpl = open(os.path.join(HERE, "template.html")).read()
html = (tmpl.replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__N__", str(n))
            .replace("__UPDATED__", UPDATED)
            .replace("__MED__", format(med, ",").replace(",", ".")))
# 'nieuw'-tegel via echte firstSeen: template markeert status=='nieuw'
open(os.path.join(ROOT, "index.html"), "w").write(html)

summary = "%d nieuwe woning(en)" % len(new_ids) if new_ids else "geen nieuwe woningen"
print("Gerenderd: %d woningen, %s, mediaan € %s" % (n, summary, format(med, ",").replace(",", ".")))
for it in items:
    if it["id"] in new_ids:
        print("  NIEUW: %s · € %s · %d slk · score %d · %s" % (
            it["adres"], format(it["prijs"], ",").replace(",", "."), it["sk"], it["score"], it["url"]))

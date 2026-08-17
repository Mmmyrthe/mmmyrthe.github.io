# -*- coding: utf-8 -*-
"""
Bouwt ../index.html uit _build/listings.json en _build/template.html.
Houdt _build/state.json bij (welke woning-id's eerder gezien zijn) voor 'nieuw'-detectie.
Gebruik:  python3 _build/render.py 2026-07-21
Argument = scandatum (YYYY-MM-DD). Zonder argument wordt de datum uit state niet gewijzigd.

Sinds 2026-08-17: ondersteunt koop ÉN huur. Elk object in listings.json heeft
een veld "type": "koop" (default) of "huur". Voor huur: prijs = kale huur per
maand, perceel mag ontbreken, tuin is verplicht (scan filtert) maar kent geen
minimumgrootte.
"""
import json, statistics, sys, os, html

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
state = rd("state.json", {})   # { woning_id: {"firstSeen": "YYYY-MM-DD"} }
streets = [s.lower() for s in rd("streets.json", [])]  # voorkeursstraten (optioneel)

def fid(url): return url.rstrip("/").split("/")[-1]

def esc(v):
    """HTML-escaping van tekstvelden uit gescrapete bronnen — voorkomt dat een
    adres/tuin-tekst met opmaak ooit als HTML in de kaartjes belandt (XSS)."""
    return html.escape(str(v), quote=True) if v is not None else v

def label_pts(l):
    if l and l.startswith("A"): return 8
    return {"B":6,"C":4,"D":2,"E":1}.get(l, 0)

def score_koop(w):
    s = 40
    tuin = w.get("tuin_m2")
    t = tuin if tuin is not None else max(0, (w.get("perceel") or 0) - 130)
    s += 20 if t>=300 else 16 if t>=200 else 12 if t>=150 else 8 if t>=100 else 4
    s += round((400000 - w["prijs"]) / 100000 * 12)
    sk = w["sk"]; s += 0 if sk<=3 else 5 if sk==4 else 8
    woon = w["woon"]; s += 10 if woon>=140 else 8 if woon>=120 else 4 if woon>=100 else 2
    s += label_pts(w.get("label"))
    s += 10 if w.get("zolder") else 0
    return min(100, s)

def score_huur(w):
    s = 40
    tuin = w.get("tuin_m2")
    t = tuin if tuin is not None else 50   # tuin aanwezig (eis) maar niet gemeten
    s += 16 if t>=200 else 12 if t>=100 else 8 if t>=50 else 4
    s += max(0, round((1500 - w["prijs"]) / 1500 * 12))   # goedkoper = beter binnen budget
    sk = w["sk"]; s += 0 if sk<=3 else 5 if sk==4 else 8
    woon = w["woon"]; s += 10 if woon>=140 else 8 if woon>=120 else 4 if woon>=100 else 2
    s += label_pts(w.get("label"))
    s += 10 if w.get("zolder") else 0
    return min(100, s)

REQ_KOOP = ("url", "adres", "prijs", "woon", "perceel", "sk")
REQ_HUUR = ("url", "adres", "prijs", "woon", "sk")
items = []
seen_ids = set()
new_ids = []
skipped = []
for w in listings:
    typ = (w.get("type") or "koop").lower()
    required = REQ_HUUR if typ == "huur" else REQ_KOOP
    missing = [k for k in required if w.get(k) in (None, "")]
    if missing:
        skipped.append((w.get("adres") or w.get("url") or "?", missing))
        continue
    i = fid(w["url"])
    if i in seen_ids:            # zelfde woning via 2 bronnen — 1x tonen
        continue
    seen_ids.add(i)
    first = state.get(i, {}).get("firstSeen")
    is_new = first is None
    if is_new:
        first = SCAN_DATE
        new_ids.append(i)
    tuin = w.get("tuin_m2")
    voorkeur = any(s in w["adres"].lower() for s in streets)
    base = score_huur(w) if typ == "huur" else score_koop(w)
    items.append({
        "id": i, "type": typ, "adres": esc(w["adres"]), "plaats": "Surhuisterveen",
        "prijs": w["prijs"], "woon": w["woon"], "perceel": w.get("perceel") or 0, "sk": w["sk"],
        "label": esc(w.get("label")) or "–", "url": esc(w["url"]),
        "score": min(100, base + (5 if voorkeur else 0)), "voorkeur": voorkeur,
        "tuin": esc(w.get("tuin_note","")),
        "tuinTwijfel": typ == "koop" and tuin is not None and tuin < 80,
        "zolder": bool(w.get("zolder")), "voorbehoud": bool(w.get("voorbehoud")),
        "bouwjaar": esc(w.get("bouwjaar","")), "foto": esc(w.get("foto","")),
        "dist": 0, "rand": False,
        "firstSeen": first, "status": "nieuw" if is_new else "actueel",
    })

items.sort(key=lambda x: -x["score"])

# state bijwerken — bewaar ook ids die niet (meer) in listings staan maar wel
# een 'rejected'-notitie hebben, zodat afgewezen woningen niet opnieuw
# gedetailleerd worden bij een volgende scan
newstate = {}
for i, entry in state.items():
    if entry.get("rejected"):
        newstate[i] = entry
for it in items:
    newstate[it["id"]] = {"firstSeen": it["firstSeen"]}
json.dump(newstate, open(os.path.join(HERE, "state.json"), "w"), ensure_ascii=False, indent=1)

# index.html renderen
koop = [x for x in items if x["type"] == "koop"]
huur = [x for x in items if x["type"] == "huur"]
n = len(items)
med = int(statistics.median([x["prijs"] for x in koop])) if koop else 0
tmpl = open(os.path.join(HERE, "template.html")).read()
# "</" escapen zodat adres-/tuinteksten nooit de <script>-tag kunnen breken
data_js = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
# kleine tokens EERST vervangen, __DATA__ als laatste — zo kan woningtekst
# (adres/tuin) nooit per ongeluk een placeholder-token corrumperen
html_out = (tmpl.replace("__NKOOP__", str(len(koop)))
                .replace("__NHUUR__", str(len(huur)))
                .replace("__N__", str(n))
                .replace("__UPDATED__", UPDATED)
                .replace("__MED__", format(med, ",").replace(",", "."))
                .replace("__DATA__", data_js))
# 'nieuw'-tegel via echte firstSeen: template markeert status=='nieuw'
open(os.path.join(ROOT, "index.html"), "w").write(html_out)

summary = "%d nieuwe woning(en)" % len(new_ids) if new_ids else "geen nieuwe woningen"
print("Gerenderd: %d woningen (%d koop, %d huur), %s, mediaan koop € %s" % (
    n, len(koop), len(huur), summary, format(med, ",").replace(",", ".")))
for adres, missing in skipped:
    print("  OVERGESLAGEN (ontbrekende velden %s): %s" % (", ".join(missing), adres))
for it in items:
    if it["id"] in new_ids:
        eenheid = "/mnd" if it["type"] == "huur" else ""
        print("  NIEUW (%s): %s · € %s%s · %d slk · score %d · %s" % (
            it["type"], it["adres"], format(it["prijs"], ",").replace(",", "."), eenheid,
            it["sk"], it["score"], it["url"]))

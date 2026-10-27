"""Morning fetcher for The Daily Page.

Plain code, no AI. Each morning it:
  1. fetches today's material from a few public sources,
  2. crops each text by a fixed rule (sometimes whole, sometimes a run of words),
  3. writes found/YYYY-MM-DD.js, which the app loads.
Randomness is seeded by the date, so a re-run on the same day gives the same cards.
"""
import datetime, json, os, random, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from html import unescape

TZ_OFFSET = 13  # New Zealand daylight time; only used to name the day
TODAY = (datetime.datetime.utcnow() + datetime.timedelta(hours=TZ_OFFSET)).date()
rng = random.Random(TODAY.isoformat())
UA = {"User-Agent": "daily-page/1.0 (personal notebook prompt; github.com/caitkne/daily-page)"}

def get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def clean(s):
    s = unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()

# ---------- cropping: a fixed rule, like a paper viewfinder ----------
STOP = set("a an the and or but of to in on at for with by from as is are was were be been it its this that these those who which".split())
def crop(text):
    words = text.split()
    if len(words) <= 9 or rng.random() < 0.35:
        return text                                   # whole
    n = rng.randint(3, 9)
    for _ in range(20):
        i = rng.randint(0, len(words) - n)
        run = words[i:i + n]
        if run[0].lower().strip(",.;:") not in STOP and run[-1].lower().strip(",.;:") not in STOP:
            return " ".join(run).strip(",;:")
    return " ".join(words[:n])

cards = []
def add(text, source, kind, url=""):
    text = clean(text)
    if len(text) < 3:
        return
    cards.append({"text": crop(text), "whole": text, "source": source, "kind": kind, "url": url})

def safe(fn):
    try:
        before = len(cards); fn(); print(f"ok   {fn.__name__}: {len(cards) - before} cards")
    except Exception as e:
        print(f"FAIL {fn.__name__}: {e!r}", file=sys.stderr)

# ---------- daily sources ----------
NYT = {"NYT Style": "Style", "NYT Arts": "Arts", "NYT Travel": "Travel", "NYT Science": "Science"}
def nyt():
    for name, sec in NYT.items():
        root = ET.fromstring(get(f"https://rss.nytimes.com/services/xml/rss/nyt/{sec}.xml"))
        items = root.findall("./channel/item")
        for it in rng.sample(items, min(2, len(items))):
            text = it.findtext("title") if rng.random() < 0.5 else (it.findtext("description") or it.findtext("title"))
            add(text, name, "headline", it.findtext("link") or "")

VA_Q = ["doll", "dolls house", "toy", "game", "puppet", "sticker", "stationery", "sampler", "souvenir",
        "packaging", "badge", "paper doll", "pencil case", "toy theatre", "hair ornament", "notebook", "ribbon"]
def va():
    for q in rng.sample(VA_Q, 2):
        base = "https://api.vam.ac.uk/v2/objects/search?" + urllib.parse.urlencode({"q": q, "page_size": 50})
        info = json.loads(get(base))
        pages = max(1, min(int(info.get("info", {}).get("pages", 1)), 20))
        recs = json.loads(get(base + f"&page={rng.randint(1, pages)}")).get("records", [])
        if not recs: continue
        r = rng.choice(recs)
        parts = [r.get("_primaryTitle") or r.get("objectType"), r.get("_primaryDate"), r.get("_primaryPlace")]
        add(", ".join(p for p in parts if p), "V&A collection", "object",
            f"https://collections.vam.ac.uk/item/{r.get('systemNumber','')}/")

WELL_Q = ["charm", "amulet", "dream", "witchcraft", "talisman", "almanac", "fortune telling", "diary",
          "superstition", "doll", "nursery", "household remedy", "keepsake"]
def wellcome():
    for q in rng.sample(WELL_Q, 2):
        base = "https://api.wellcomecollection.org/catalogue/v2/works?" + urllib.parse.urlencode({"query": q, "pageSize": 50})
        info = json.loads(get(base))
        pages = max(1, min(int(info.get("totalPages", 1)), 20))
        res = json.loads(get(base + f"&page={rng.randint(1, pages)}")).get("results", [])
        if not res: continue
        w = rng.choice(res)
        add(w.get("title", ""), "Wellcome Collection", "object", f"https://wellcomecollection.org/works/{w.get('id','')}")

MET_Q = ["dollhouse", "doll", "toy", "sampler", "pattern book", "fan", "miniature", "valentine", "trade card", "paper doll"]
def met():
    q = rng.choice(MET_Q)
    ids = json.loads(get("https://collectionapi.metmuseum.org/public/collection/v1/search?" + urllib.parse.urlencode({"q": q}))).get("objectIDs") or []
    for oid in rng.sample(ids, min(2, len(ids))):
        o = json.loads(get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}"))
        parts = [o.get("title") or o.get("objectName"), o.get("objectDate"), o.get("medium")]
        add(", ".join(p for p in parts if p), "The Met", "object", o.get("objectURL", ""))

# ---------- festival synopses: collected once per edition into festivals.json, dealt one a day ----------
def festival():
    try:
        pool = json.load(open("festivals.json"))
    except FileNotFoundError:
        return
    if not pool: return
    f = pool[(TODAY.toordinal() * 7919) % len(pool)]     # walks the whole pool before repeating
    add(f["text"], f["festival"], "synopsis", f.get("url", ""))

for fn in (nyt, va, wellcome, met, festival):
    safe(fn)

rng.shuffle(cards)
out = {"date": TODAY.isoformat(), "made": datetime.datetime.utcnow().isoformat() + "Z", "cards": cards}
os.makedirs("found", exist_ok=True)
with open(f"found/{TODAY.isoformat()}.js", "w") as f:
    f.write("window.DAILY_FOUND = " + json.dumps(out, ensure_ascii=False, indent=1) + ";\n")
print(f"wrote found/{TODAY.isoformat()}.js with {len(cards)} cards")
if not cards:
    sys.exit(1)

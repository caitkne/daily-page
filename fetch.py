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
TODAY = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TZ_OFFSET)).date()
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
STOP = set("a an the and or but of to in on at for with by from as is are was were be been being it its this that these those who which whose she he they we you i her his their our your him them has have had will would can could should not no into over about than then so if when while because after before has said says".split())
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

AIC_Q = ["dollhouse", "doll", "toy", "sampler", "pattern book", "fan", "miniature", "valentine", "trade card", "paper doll"]
AIC_FIELDS = "id,title,artist_title,date_display,medium_display"
def aic_search(q, n=40):
    url = "https://api.artic.edu/api/v1/artworks/search?" + urllib.parse.urlencode(
        {"q": q, "limit": n, "page": rng.randint(1, 3), "fields": AIC_FIELDS})
    return json.loads(get(url, headers={"AIC-User-Agent": UA["User-Agent"]})).get("data", [])

def aic():
    """Art Institute of Chicago (the Met's API is gone)."""
    data = aic_search(rng.choice(AIC_Q))
    for o in rng.sample(data, min(2, len(data))):
        parts = [o.get("title"), o.get("date_display"), o.get("medium_display")]
        add(", ".join(p for p in parts if p), "Art Institute of Chicago", "object",
            f"https://www.artic.edu/artworks/{o.get('id')}")

# ---------- festival synopses: collected once per edition into festivals.json, dealt one a day ----------
def festival():
    try:
        pool = json.load(open("festivals.json"))
    except FileNotFoundError:
        return
    if not pool: return
    f = pool[(TODAY.toordinal() * 7919) % len(pool)]     # walks the whole pool before repeating
    add(f["text"], f["festival"], "synopsis", f.get("url", ""))

# ---------- fresh ways: real methods and materials, dealt alongside the deck ----------
ways = []
MEDIUM_Q = ["embroidery", "cut paper", "collage", "sampler", "paper doll", "stencil", "pricked", "quilt",
            "scrapbook", "silhouette", "beadwork", "papier-mache", "lacquer", "woodblock", "valentine", "toy"]
def medium():
    """A real object's medium line, verbatim: 'work in' this."""
    for q in rng.sample(MEDIUM_Q, 3):
        data = aic_search(q)
        rng.shuffle(data)
        for o in data:
            m = clean(o.get("medium_display") or "")
            if 12 <= len(m) <= 160 and ("," in m or " and " in m or " on " in m):
                who = ", ".join(p for p in [o.get("title"), o.get("artist_title"), o.get("date_display")] if p)
                ways.append({"name": "work in", "text": m[0].lower() + m[1:], "after": who + " (Art Institute of Chicago)",
                             "url": f"https://www.artic.edu/artworks/{o.get('id')}", "kind": "medium"})
                return

ARTIST_CATS = ["Fluxus", "Oulipo members", "Mail art", "Outsider artists", "Collagists", "Book artists",
               "Women performance artists", "Assemblage artists", "Textile artists", "Diarists",
               "Miniaturists", "Paper artists", "Conceptual art"]
def artist():
    """A working method from a real practitioner's Wikipedia summary."""
    for cat in rng.sample(ARTIST_CATS, 4):
        q = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
             "cmnamespace": 0, "cmlimit": 500, "format": "json"})
        members = json.loads(get(q)).get("query", {}).get("categorymembers", [])
        for m in rng.sample(members, min(6, len(members))):
            t = m["title"]
            sm = json.loads(get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t.replace(" ", "_"))))
            ex = clean(sm.get("extract", ""))
            desc = (sm.get("description") or "").lower()
            if sm.get("type") != "standard" or not ex or "list of" in t.lower():
                continue
            if not re.search(r"artist|poet|writer|novelist|composer|photographer|designer|illustrator|diarist|weaver|maker|sculptor|painter|filmmaker|performer", desc + " " + ex[:200].lower()):
                continue
            sents = re.split(r"(?<=[.!?])\s+", ex)
            text = " ".join(sents[:2])[:420]
            ways.append({"name": re.sub(r"\s*\(.*?\)", "", t).lower(), "text": text, "after": t + " (Wikipedia)",
                         "url": sm.get("content_urls", {}).get("desktop", {}).get("page", ""), "kind": "artist"})
            return


# ---------- images: a few never-seen pictures from open collections, one dealt a day ----------
images = []
SEEN_FILE = "found/seen-images.txt"
try:
    SEEN = set(open(SEEN_FILE).read().split())
except FileNotFoundError:
    SEEN = set()

IMG_Q = ["doll", "dolls house", "paper doll", "toy", "toy theatre", "puppet", "sticker", "scrapbook", "valentine",
         "trade card", "sampler", "embroidery", "ribbon", "hair ornament", "fan", "miniature", "pattern book",
         "lenticular", "souvenir", "packaging", "board game", "horse", "cat", "witch", "charm", "amulet",
         "ballet", "diary", "bedroom", "department store", "shop window", "railway", "train", "stationery"]

def add_image(url, title, source, link):
    if not url or url in SEEN or any(i["src"] == url for i in images):
        return False
    images.append({"src": url, "title": clean(title)[:200], "source": source, "url": link})
    return True

def img_aic():
    q = rng.choice(IMG_Q)
    url = "https://api.artic.edu/api/v1/artworks/search?" + urllib.parse.urlencode(
        {"q": q, "limit": 40, "page": rng.randint(1, 3), "fields": "id,title,artist_title,date_display,image_id",
         "query[term][is_public_domain]": "true"})
    data = [o for o in json.loads(get(url, headers={"AIC-User-Agent": UA["User-Agent"]})).get("data", []) if o.get("image_id")]
    for o in rng.sample(data, min(len(data), 6)):
        t = ", ".join(x for x in [o.get("title"), o.get("artist_title"), o.get("date_display")] if x)
        if add_image(f"https://www.artic.edu/iiif/2/{o['image_id']}/full/843,/0/default.jpg", t,
                     "Art Institute of Chicago", f"https://www.artic.edu/artworks/{o['id']}"):
            return

def img_va():
    q = rng.choice(IMG_Q)
    base = "https://api.vam.ac.uk/v2/objects/search?" + urllib.parse.urlencode({"q": q, "page_size": 50, "images_exist": 1})
    info = json.loads(get(base))
    pages = max(1, min(int(info.get("info", {}).get("pages", 1)), 20))
    recs = [r for r in json.loads(get(base + f"&page={rng.randint(1, pages)}")).get("records", []) if r.get("_primaryImageId")]
    for r in rng.sample(recs, min(len(recs), 6)):
        t = ", ".join(x for x in [r.get("_primaryTitle") or r.get("objectType"), r.get("_primaryDate"), r.get("_primaryPlace")] if x)
        if add_image(f"https://framemark.vam.ac.uk/collections/{r['_primaryImageId']}/full/!800,800/0/default.jpg", t,
                     "V&A collection", f"https://collections.vam.ac.uk/item/{r.get('systemNumber','')}/"):
            return

def img_wellcome():
    q = rng.choice(IMG_Q)
    base = "https://api.wellcomecollection.org/catalogue/v2/images?" + urllib.parse.urlencode({"query": q, "pageSize": 50})
    info = json.loads(get(base))
    pages = max(1, min(int(info.get("totalPages", 1)), 10))
    res = json.loads(get(base + f"&page={rng.randint(1, pages)}")).get("results", [])
    for im in rng.sample(res, min(len(res), 6)):
        thumb = (im.get("thumbnail") or {}).get("url", "")
        if not thumb.endswith("/info.json"):
            continue
        src = thumb[:-len("/info.json")] + "/full/!800,800/0/default.jpg"
        w = im.get("source") or {}
        if add_image(src, w.get("title", ""), "Wellcome Collection", f"https://wellcomecollection.org/works/{w.get('id','')}"):
            return

COMMONS_CATS = ["Paper dolls", "Dollhouses", "Lenticular printing", "Stickers", "Shop windows", "Toy packaging",
                "Department stores", "Blythe (doll)", "Sticker albums", "Toy catalogs",
                "Sewing patterns", "Embroidery samplers", "Plastic toys", "Dollhouse miniatures", "Rubber stamps",
                "Erasers", "Pencil cases", "Board games", "Trading cards", "Ballet shoes", "Rocking horses"]
def img_commons():
    for cat in rng.sample(COMMONS_CATS, 4):
        q = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "generator": "categorymembers", "gcmtitle": "Category:" + cat, "gcmtype": "file",
             "gcmlimit": 200, "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": 800, "format": "json"})
        pages = list((json.loads(get(q)).get("query") or {}).get("pages", {}).values())
        pages = [p for p in pages if p.get("imageinfo") and p["imageinfo"][0].get("mime") in ("image/jpeg", "image/png")]
        for p in rng.sample(pages, min(len(pages), 6)):
            ii = p["imageinfo"][0]
            title = re.sub(r"^File:|\.(jpe?g|png)$", "", p["title"], flags=re.I).replace("_", " ")
            if add_image(ii.get("thumburl") or ii["url"], title, "Wikimedia Commons · " + cat, ii.get("descriptionurl", "")):
                return


EBAY_Q = ["licca chan", "dream house doll", "blythe doll boxed", "sticker sheet", "sticker album", "deadstock stationery",
          "pencil case", "eraser collection", "lenticular", "dollar store toy", "rack toy", "playset", "folding dollhouse",
          "paper dolls", "barbie riding club", "horse figure", "babysitters club", "diary with lock", "charm bracelet",
          "witch figurine", "cat figurine", "department store bag", "souvenir", "train ticket", "hair accessories",
          "ballet shoes", "music box ballerina", "trading cards girls", "keychain", "pocket game"]
def img_ebay():
    """Vintage eBay listings (needs EBAY_CLIENT_ID / EBAY_CLIENT_SECRET repo secrets)."""
    cid, sec = os.environ.get("EBAY_CLIENT_ID"), os.environ.get("EBAY_CLIENT_SECRET")
    if not cid or not sec:
        print("skip img_ebay: no keys"); return
    import base64
    tok = json.loads(get("https://api.ebay.com/identity/v1/oauth2/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}).encode(),
        headers={"Authorization": "Basic " + base64.b64encode(f"{cid}:{sec}".encode()).decode(),
                 "Content-Type": "application/x-www-form-urlencoded"}))["access_token"]
    got = 0
    for q in rng.sample(EBAY_Q, 4):
        url = "https://api.ebay.com/buy/browse/v1/item_summary/search?" + urllib.parse.urlencode(
            {"q": "vintage " + q, "limit": 50, "offset": rng.choice([0, 50, 100])})
        items = json.loads(get(url, headers={"Authorization": "Bearer " + tok, "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"})).get("itemSummaries", [])
        items = [i for i in items if (i.get("image") or {}).get("imageUrl")]
        for it in rng.sample(items, min(len(items), 6)):
            src = it["image"]["imageUrl"].replace("s-l225", "s-l800")
            if add_image(src, it.get("title", ""), "eBay listing", it.get("itemWebUrl", "")):
                got += 1
                break
        if got >= 2:
            return


for fn in (nyt, va, wellcome, aic, festival):
    safe(fn)
for fn in (medium, artist, img_aic, img_va, img_wellcome, img_commons, img_commons, img_ebay):
    try:
        fn(); print(f"ok   {fn.__name__}")
    except Exception as e:
        print(f"FAIL {fn.__name__}: {e!r}", file=sys.stderr)

rng.shuffle(cards)
out = {"date": TODAY.isoformat(), "made": datetime.datetime.now(datetime.timezone.utc).isoformat(), "cards": cards, "ways": ways, "images": images}
os.makedirs("found", exist_ok=True)
with open(f"found/{TODAY.isoformat()}.js", "w") as f:
    f.write("window.DAILY_FOUND = " + json.dumps(out, ensure_ascii=False, indent=1) + ";\n")
with open(SEEN_FILE, "a") as f:
    f.writelines(i["src"] + "\n" for i in images)
print(f"wrote found/{TODAY.isoformat()}.js with {len(cards)} cards")
if not cards:
    sys.exit(1)

"""Collects festival synopses into festivals.json, once a month (or by hand).

Plain code, no AI: for each festival it reads the programme listing, follows each film link,
and keeps the film page's own short description, word for word.
"""
import html, json, re, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (daily-page; personal notebook prompt)"}
FESTIVALS = [
    {"festival": "Berlinale Generation", "lists": ["https://www.berlinale.de/en/2026/topics/generation-2026.html"],
     "link": r"/en/20\d\d/programme/20\d+\.html"},
    {"festival": "IFFR", "lists": ["https://iffr.com/en/iffr/2026/harbour"] + [f"https://iffr.com/en/iffr/2026/harbour/page/{n}" for n in range(2, 6)],
     "link": r"https://iffr\.com/en/iffr/20\d\d/films/[^\"#?]+"},
    {"festival": "Prismatic Ground", "lists": ["https://www.bam.org/film/2026/prismatic-ground"],
     "link": r"/film/20\d\d/(?!prismatic-ground)[a-z0-9-]+"},
    {"festival": "NZIFF", "lists": ["https://www.nziff.co.nz/2026/tamaki-makaurau-auckland/films/title/"],
     "link": r"/20\d\d/tamaki-makaurau-auckland/films/(?!title/)[a-z0-9-]+/?"},
    {"festival": "Fantasia", "lists": ["https://fantasiafestival.com/en/festival-2026/program"],
     "link": r"https://fantasiafestival\.com/en/festival-2026/(?:program|films?)/[a-z0-9-]+"},
]
PER_FESTIVAL = 120

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

BAD = ("cookie", "official website", "javascript", "©", "newsletter", "tickets")
def paragraphs(page):
    body = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", page)
    for m in re.finditer(r"(?is)<p[^>]*>(.*?)</p>", body):
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))).strip()
        if 60 <= len(t) <= 700 and not any(b in t.lower() for b in BAD):
            yield t

def description(page):
    d = meta(page)
    if d and not any(b in d.lower() for b in BAD):
        return d
    return next(paragraphs(page), "")

def meta(page):
    for pat in (r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
                r'<meta[^>]+content="([^"]+)"[^>]+property="og:description"',
                r'<meta[^>]+name="description"[^>]+content="([^"]+)"'):
        m = re.search(pat, page, re.I)
        if m:
            return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
    return ""

try:
    old = json.load(open("festivals.json"))
except Exception:
    old = []
old = [x for x in old if not any(b in x["text"].lower() for b in BAD)]
seen = {x["url"] for x in old}
pool = list(old)
for f in FESTIVALS:
    links = []
    for lst in f["lists"]:
        try:
            page = get(lst)
        except Exception as e:
            print(f"FAIL list {lst}: {e!r}"); continue
        for l in re.findall(r'href="([^"]+)"', page):
            if re.fullmatch(f["link"], l) or re.fullmatch(f["link"], urllib.parse.urlparse(l).path or ""):
                u = urllib.parse.urljoin(lst, l)
                if u not in links: links.append(u)
    if not links:
        print("  no film links matched; sample hrefs:", re.findall(r'href="([^"]+)"', page)[:60])
    new = 0
    for u in links[:PER_FESTIVAL]:
        if u in seen: continue
        try:
            d = description(get(u))
        except Exception as e:
            print(f"  fail {u}: {e!r}"); continue
        if len(d) >= 40 and "cookie" not in d.lower():
            pool.append({"festival": f["festival"], "text": d, "url": u}); seen.add(u); new += 1
        time.sleep(0.5)
    print(f"{f['festival']}: {len(links)} film links, {new} new synopses")
    for x in [p for p in pool if p["festival"] == f["festival"]][:3]:
        print("   e.g.", x["text"][:140])

json.dump(pool, open("festivals.json", "w"), ensure_ascii=False, indent=1)
print("total", len(pool))

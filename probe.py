"""One-off: look at festival pages from GitHub's side, to write parsers. Prints structure only."""
import re, urllib.request
URLS = [
 "https://www.berlinale.de/en/2026/topics/generation-2026.html",
 "https://iffr.com/en/iffr/2026/harbour",
 "https://www.bam.org/film/2026/prismatic-ground",
 "https://www.annecyfestival.com/en/the-festival/official-selection/short-films/short-films-official",
 "https://fantasiafestival.com/en/",
 "https://www.nziff.co.nz/",
]
UA = {"User-Agent": "Mozilla/5.0 (daily-page probe)"}
for u in URLS:
    print("=" * 20, u)
    try:
        h = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8", "replace")
    except Exception as e:
        print("FAIL", e); continue
    print("len", len(h), "| next_data", "__NEXT_DATA__" in h, "| ld+json", h.count("application/ld+json"))
    links = sorted(set(re.findall(r'href="([^"]+)"', h)))
    film = [l for l in links if re.search(r"film|programme|program|movie|event|selection", l, re.I)]
    print("links", len(links), "film-ish", len(film))
    for l in film[:40]: print("  ", l)
    for m in re.finditer(r'<(p|div)[^>]*class="([^"]*)"[^>]*>([^<]{60,300})<', h):
        print("  TEXT", m.group(2)[:50], "|", m.group(3).strip()[:160])
        if m.start() > 400000: break

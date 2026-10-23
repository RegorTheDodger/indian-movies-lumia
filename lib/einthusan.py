"""
Talking to einthusan.

All network access lives here. No HTML, no framework, so both the Flask app
and the Vercel function can use it, and so it can be tested on its own.
"""

import gzip
import http.client
import re
import ssl
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

HOST = "einthusan.tv"
CDN_HOST = "cdn2.einthusan.io"
COVER_BASE = "https://%s/etv/s3/moviecovers/" % CDN_HOST

CDN = "https://%s/etv/content/D{}.mp4" % CDN_HOST

LANGS = [
    ("tamil", "Tamil"),
    ("telugu", "Telugu"),
    ("hindi", "Hindi"),
    ("malayalam", "Malayalam"),
    ("kannada", "Kannada"),
    ("bengali", "Bengali"),
    ("marathi", "Marathi"),
    ("punjabi", "Punjabi"),
]
LANG_NAMES = dict(LANGS)
LANG_CODES = [c for c, _ in LANGS]

FETCH_TIMEOUT = 30
MAX_PAGES = 4
CACHE_TTL = 600

_pools = threading.local()
_cache = {}
_cache_lock = threading.Lock()


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------


def http_get(path, host=HOST, redirects=3):
    """GET over a pooled keep-alive socket.

    A TLS handshake to einthusan costs about half a second, so reusing the
    socket is what keeps a multi-page search at roughly one second instead of
    four. Connections are per-thread.
    """
    pool = getattr(_pools, "conns", None)
    if pool is None:
        pool = _pools.conns = []

    conn = None
    for candidate in pool:
        if candidate.sock is not None and candidate.host == host:
            conn = candidate
            break
    if conn is None:
        conn = http.client.HTTPSConnection(
            host, timeout=FETCH_TIMEOUT, context=ssl.create_default_context())
        pool.append(conn)

    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    try:
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()

        if resp.status in (301, 302, 303, 307, 308) and redirects > 0:
            location = resp.headers.get("Location", "")
            conn.close()
            if location.startswith("/"):
                return http_get(location, host, redirects - 1)
            parts = urllib.parse.urlsplit(location)
            if parts.scheme in ("http", "https"):
                tail = parts.path + (("?" + parts.query) if parts.query else "")
                return http_get(tail, parts.hostname, redirects - 1)

        if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
            raw = gzip.decompress(raw)
        if resp.will_close:
            conn.close()
        return raw.decode("utf-8", "replace")
    except Exception:
        conn.close()
        raise


def strip_tags(fragment):
    import html as html_mod
    return html_mod.unescape(re.sub(r"<[^>]*>", "", fragment)).strip()


def collapse(text):
    return re.sub(r"\s+", " ", text).strip()


def cached(key, producer):
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and now - entry[0] < CACHE_TTL:
            return entry[1]
    value = producer()
    if value is None:
        return None
    with _cache_lock:
        _cache[key] = (now, value)
    return value


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

_WATCH = re.compile(r"/movie/watch/([A-Za-z0-9]{4})")
_CONTENT = re.compile(r"/content/D([A-Za-z0-9]{4})\.mp4", re.I)
_BARE = re.compile(r"^[A-Za-z0-9]{4}$")
_COVER = re.compile(r"moviecovers/([A-Za-z0-9]+-[a-z0-9]+)\.jpg")


def parse_results_page(doc):
    """Pull (items, total_pages, total_count) out of a /movie/results/ page."""
    start = doc.find('<section id="UIMovieSummary">')
    if start == -1:
        return [], 0, 0
    tail = doc[start:]
    end = tail.find("<section id=", 10)
    body = tail[:end] if end != -1 else tail

    items = []
    for chunk in re.findall(r"<li>(.*?)</li>", body, re.S):
        mid = _WATCH.search(chunk)
        if not mid:
            continue

        heading = re.search(r"<h3[^>]*>(.*?)</h3>", chunk, re.S)
        title = collapse(strip_tags(heading.group(1))) if heading else ""
        if not title:
            continue

        meta = re.search(r"<p>\s*(\d{4})\s*<span>([^<]*)</span>", chunk)
        cover = _COVER.search(chunk)

        items.append({
            "id": mid.group(1),
            "title": title,
            "year": meta.group(1) if meta else "",
            "lang": collapse(strip_tags(meta.group(2))) if meta else "",
            "cover": COVER_BASE + cover.group(1) + ".jpg" if cover else None,
            "url": CDN.format(mid.group(1)),
        })

    pages_m = re.search(r"Page\s+\d+\s+of\s+(\d+)", doc)
    count_m = re.search(r"\(\s*(\d+)\s*results", doc)
    return (
        items,
        int(pages_m.group(1)) if pages_m else 0,
        int(count_m.group(1)) if count_m else 0,
    )


def fetch_prefix_page(term, lang, page, attempts=3):
    """Page is 1-based: page=0 returns an upsell page with no rows.

    Returns None when every attempt failed, which is deliberately distinct
    from "no matches" so a dropped request never looks like an empty result.
    """
    path = "/movie/results/?alpha={}&find=Alphabets&lang={}&page={}".format(
        urllib.parse.quote(term, safe=""), urllib.parse.quote(lang), page
    )
    for attempt in range(attempts):
        try:
            items, pages, count = parse_results_page(http_get(path))
            if items or pages:
                return items, pages, count
        except Exception:
            pass
        if attempt + 1 < attempts:
            time.sleep(0.4 * (attempt + 1))
    return None


def fetch_and_paginate(term, lang, max_pages=MAX_PAGES):
    head = fetch_prefix_page(term, lang, 1)
    if head is None:
        return None
    items, total_pages, total_count = head
    for page in range(2, min(total_pages, max_pages) + 1):
        got = fetch_prefix_page(term, lang, page)
        if got:
            items.extend(got[0])
    return items, total_pages, total_count


def exists(prefix, lang):
    """True only when this exact prefix matches something.

    search() falls back to a shorter prefix when nothing is found, which is
    right for a human but wrong for checking a suggestion: it would accept
    "Velaiyilla Pattathu" because "Velaiyilla" happens to match a film. This
    deliberately does no fallback.
    """
    got = fetch_and_paginate(prefix, lang, max_pages=1)
    return bool(got and got[0])


def lookup(prefix, lang, limit=1):
    """First matches for an exact prefix. No fallback, so it is safe for
    checking a guess: if this is empty, the catalogue really has nothing
    under that spelling."""
    got = fetch_and_paginate(prefix, lang, max_pages=1)
    return got[0][:limit] if got and got[0] else []


def resolve(titles, lang, per_title=1):
    """Turn guessed titles into real, playable records with cover art."""
    def one(title):
        try:
            return title, lookup(title, lang, per_title)
        except Exception:
            return title, []

    out, seen = [], set()
    with ThreadPoolExecutor(max_workers=6) as pool:
        for _title, items in pool.map(one, list(titles)[:20]):
            for item in items:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                out.append(item)
    return out


def shorter_prefix(term):
    """The part of a query before its first space or punctuation mark."""
    cleaned = term.strip()
    stop = re.search(r"[^A-Za-z0-9]", cleaned)
    if not stop:
        return None
    head = cleaned[:stop.start()].strip()
    return head or None


def search(term, lang):
    """(items, total_pages, total_count, used_prefix) or None on total failure."""
    def produce():
        got = fetch_and_paginate(term, lang)
        if got is None:
            return None
        if got[0]:
            return got[0], got[1], got[2], term

        alt = shorter_prefix(term)
        if alt and alt.lower() != term.strip().lower():
            retry = fetch_and_paginate(alt, lang)
            if retry and retry[0]:
                return retry[0], retry[1], retry[2], alt
        return [], got[1], got[2], term

    return cached(("search", term.lower(), lang), produce)


def search_all(term):
    """Every language at once, first page of each, plus a second page only
    where the prefix actually spilled over."""
    def produce():
        with ThreadPoolExecutor(max_workers=4) as pool:
            heads = list(pool.map(
                lambda code: (code, fetch_prefix_page(term, code, 1)), LANG_CODES))

        spill = [(c, g[1]) for c, g in heads if g is not None and g[1] >= 2]

        def tail(entry):
            code, pages = entry
            out = []
            for page in (2, 3):
                if page > min(pages, 3):
                    break
                got = fetch_prefix_page(term, code, page)
                if got:
                    out.extend(got[0])
            return code, out

        tails = []
        if spill:
            with ThreadPoolExecutor(max_workers=4) as pool:
                tails = list(pool.map(tail, spill))
        tail_items = dict(tails)

        merged, seen = [], set()
        for code, got in heads:
            if got is None:
                continue
            for item in list(got[0]) + tail_items.get(code, []):
                if item["id"] not in seen:
                    seen.add(item["id"])
                    merged.append(item)
        merged.sort(key=lambda i: (i["title"].lower(), i["id"]))
        return merged

    return cached(("searchall", term.lower()), produce)


# --------------------------------------------------------------------------
# link helpers
# --------------------------------------------------------------------------


def extract_id(raw):
    """The 4-character id from a watch url, a cdn url, or a bare id."""
    import html as html_mod
    text = html_mod.unescape(raw or "").strip().strip("<>\"'")
    if not text:
        return None
    for pattern in (_WATCH, _CONTENT):
        found = pattern.search(text)
        if found:
            return found.group(1)
    return text if _BARE.match(text) else None


def cdn_link(movie_id):
    return CDN.format(movie_id)

"""
HTML rendering for the Windows Phone 8.1 build.

Markup is constrained by IE11 rather than by taste:

  * posters are background-image boxes, because IE11 has no object-fit
  * the direct mp4 link is always visible, because IE11 cannot open <details>
  * inputs are type=text, because IE11 renders type=search inconsistently

Class names match static/legacy.css. static/legacy.js owns everything personal
(list, resume position, watch time), which is also why the server keeps no
accounts and no database.
"""

import html
import re
import urllib.parse

from . import einthusan as E

# IE11 has no object-fit, so the poster is a background-image on a fixed-ratio
# box instead. That puts the url inside a style attribute, where a quote or a
# bracket would break out of the CSS string, so covers are vetted first.
_COVER_OK = re.compile(r'^(?:https?:)?//[^\s"\'()\\<>]+$', re.I)

NAV = [
    ("/", "Home"),
    ("/search", "Search"),
    ("/watchlist", "My List"),
]


def esc(text):
    return html.escape(text or "", quote=True)


def safe_cover(url):
    """A cover url that is safe to drop inside url('...') in a style attribute,
    or None."""
    url = (url or "").strip()
    return url if _COVER_OK.match(url) else None


def page(title, body, top_lang="tamil"):
    current = title.lower()
    nav = "".join(
        '<a class="navlink%s" href="%s">%s</a>'
        % (" on" if (href == "/" and current == "home")
           or href.lstrip("/").lower() == current else "", href, esc(label))
        for href, label in NAV)

    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        # WP8.1 ships IE11; edge mode keeps it there instead of an emulated
        # document mode, which would break the CSS outright.
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light">'
        "<title>%s</title>"
        '<link rel="stylesheet" href="/static/legacy.css">'
        "</head><body>"
        '<div class="desktop"><div class="win">'
        # the whole page is a Windows 98 window: title bar, menu, toolbar,
        # content, status bar, with 2px bevels doing all the depth
        '<div class="titlebar" id="bar">'
        '<span class="tb-ico">&#128250;</span>'
        '<a class="mark" href="/"><b>Indian</b> Movies</a>'
        '<span class="tb-btns">'
        '<span class="tb-btn">&#95;</span>'
        '<span class="tb-btn">&#9633;</span>'
        '<span class="tb-btn">&#10005;</span>'
        "</span></div>"
        '<nav class="menu">%s</nav>'
        '<form class="navsearch" action="/search" method="get">'
        '<input type="text" name="q" placeholder="Search films..."'
        ' autocomplete="off" aria-label="Search films">'
        '<button class="tb-go" type="submit">Go</button>'
        "</form>"
        '<div class="content"><main class="page" data-lang="%s">%s</main></div>'
        '<div class="status"><span class="st">Ready</span>'
        '<span class="st-r">%s</span></div>'
        "</div></div>"
        '<script src="/static/legacy.js"></script>'
        "</body></html>"
        % (esc(title), nav, esc(top_lang), body,
           esc(E.LANG_NAMES.get(top_lang, top_lang)))
    )


# --------------------------------------------------------------------------
# pieces
# --------------------------------------------------------------------------


def lang_options(selected):
    return "".join('<option value="%s"%s>%s</option>'
                   % (code, " selected" if code == selected else "", esc(lbl))
                   for code, lbl in E.LANGS)


def search_bar(value="", lang="tamil", action="/search"):
    return (
        '<form class="search" action="%s" method="get">'
        '<span class="field"><input type="text" name="q" value="%s"'
        ' placeholder="Film title" autocomplete="off" aria-label="Film title" required>'
        '<select name="lang" aria-label="Language">%s</select></span>'
        '<button class="btn" type="submit">Search</button>'
        "</form>" % (esc(action), esc(value), lang_options(lang))
    )


def watch_href(item):
    """The bare id cannot render a player, so the card passes on what it
    already knows rather than paying for a lookup."""
    return "/watch/%s?%s" % (esc(item["id"]), urllib.parse.urlencode({
        "t": item["title"], "c": item.get("cover") or "",
        "y": item.get("year") or "", "l": item.get("lang") or "",
    }))


def card(item):
    href = watch_href(item)
    cover = safe_cover(item.get("cover"))
    poster = ('<span class="art" style="background-image:url(\'%s\')"></span>'
              % cover if cover else '<span class="nocover">No artwork</span>')
    meta = " &middot; ".join(esc(b) for b in (item.get("year"), item.get("lang")) if b)

    return (
        '<article class="card" data-id="%s" data-title="%s" data-cover="%s"'
        ' data-url="%s" data-year="%s">'
        '<a class="poster" href="%s">%s</a>%s'
        '<h3 class="ctitle"><a href="%s">%s</a></h3>'
        '<button class="wl" type="button" data-action="toggle"'
        ' aria-label="Add to my list"><span class="lbl">My List</span>'
        '<span class="on">In My List</span></button>'
        "</article>"
        % (esc(item["id"]), esc(item["title"]), esc(item.get("cover") or ""),
           esc(item["url"]), esc(item.get("year", "")), href, poster,
           ('<p class="cmeta">%s</p>' % meta) if meta else "", href,
           esc(item["title"]))
    )


def row(title, shelf, empty_text, note=""):
    head = '<h2 class="rowhead">%s</h2>' % esc(title)
    if note:
        head += '<p class="rownote">%s</p>' % esc(note)

    return (
        '<section class="row" data-row="%s">%s'
        '<div class="railwrap">'
        '<div class="rail" data-shelf="%s" tabindex="0"'
        ' aria-label="%s"></div>'
        '<button class="arrow left at-edge" data-scroll="-1" tabindex="-1"'
        ' aria-label="Scroll left">&#8249;</button>'
        '<button class="arrow right at-edge" data-scroll="1" tabindex="-1"'
        ' aria-label="Scroll right">&#8250;</button>'
        "</div>"
        '<p class="empty" data-empty="%s">%s</p>'
        "</section>"
        % (esc(shelf), head, esc(shelf), esc(title), esc(shelf), esc(empty_text))
    )


def static_row(title, inner, empty_shelf="", empty_text=""):
    note = ('<p class="empty" data-empty="%s">%s</p>' % (esc(empty_shelf), esc(empty_text))
            if empty_shelf else "")
    return ('<section class="row"><h2 class="rowhead">%s</h2>'
            '<div class="rail static">%s</div>%s</section>'
            % (esc(title), inner, note))


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------


def home_page(top_lang):
    return ("Home",
            '<section class="hero">'
            '<p class="eyebrow">%s</p>'
            '<h1 class="display">Every film,<br>one search away.</h1>'
            "%s"
            '<p class="lede">Direct mp4 files straight from the catalogue. '
            "Nothing to install, no account, nothing in the way.</p>"
            "</section>%s%s%s"
            % (esc(E.LANG_NAMES.get(top_lang, top_lang)),
               search_bar(lang=top_lang),
               row("Continue watching", "continue",
                   "Nothing part-watched yet. Start something and it lands here."),
               row("Recently played", "recent",
                   "Films you have started will be listed here."),
               row("My list", "watchlist",
                   "Nothing saved yet. Tap My List on any poster.")),
            top_lang)


def search_page(query, lang, items, total_pages, total_count, used_prefix,
                top_lang, suggestions=()):
    if not query:
        return ("Search",
                '<section class="hero"><h1 class="display">Search</h1>%s</section>'
                % search_bar(lang=lang), top_lang)

    if not items:
        guess = ""
        if suggestions:
            guess = ('<div class="chips" style="margin-top:26px">%s</div>'
                     % "".join(
                         '<a class="chip" href="/search?q=%s&amp;lang=%s">%s</a>'
                         % (urllib.parse.quote(t), urllib.parse.quote(lang), esc(t))
                         for t in suggestions))
        return ("Search",
                '<section class="hero">'
                '<h1 class="h1">No match for &ldquo;%s&rdquo;</h1>'
                '<p class="lede">Titles are indexed from their first letter, so '
                "search on the first word. Another language may have it.</p>%s%s"
                "</section>" % (esc(query), search_bar(query, lang), guess),
                top_lang)

    note = ""
    if used_prefix and used_prefix.strip().lower() != query.strip().lower():
        note = ('Nothing matched &ldquo;%s&rdquo; exactly, so these start with '
                '&ldquo;%s&rdquo;.' % (esc(query), esc(used_prefix)))
    elif total_count and total_count > len(items):
        note = "%d of %d matching." % (len(items), total_count)

    return ("Search",
            '<section class="hero"><p class="eyebrow">Results</p>'
            '<h1 class="display">%s</h1>%s%s</section>%s'
            % (esc(query), search_bar(query, lang),
               '<p class="lede">%s</p>' % note if note else "",
               static_row("Films", "".join(card(i) for i in items))),
            top_lang)


def watchlist_page(top_lang):
    return ("My List",
            '<section class="hero">'
            '<p class="eyebrow">Saved</p>'
            '<h1 class="display">My list</h1>'
            '<p class="lede">Kept in this browser. Clearing site data or '
            "switching device will empty it.</p>"
            '<p style="margin-top:26px">'
            '<button class="btn ghost" type="button" data-action="clear-watchlist">'
            "Clear list</button></p>"
            "</section>"
            '<div class="row"><div class="rail static" data-shelf="watchlist-full"></div>'
            '<p class="empty" data-empty="watchlist-full">Nothing saved yet.</p>'
            "</div>", top_lang)


def settings_page(top_lang):
    rows = "".join(
        '<label class="radio"><input type="radio" name="toplang" value="%s"%s>'
        "<span>%s</span></label>"
        % (code, " checked" if code == top_lang else "", esc(name))
        for code, name in E.LANGS)
    return ("Settings",
            '<section class="hero settings">'
            '<h1 class="display">Settings</h1>'
            "</section>"
            '<section class="panel"><h2>Default language</h2>'
            '<p class="lede" style="margin-top:0">Used for search and your '
            "library.</p>"
            '<form class="setlang" action="/settings" method="post">%s'
            '<button class="btn" type="submit">Save</button></form></section>'
            '<section class="panel"><h2>Stored data</h2>'
            '<p class="lede" style="margin-top:0">Your list, watch time and '
            "resume points live in this browser. No account, no server copy.</p>"
            '<button class="btn ghost" type="button" data-action="clear-all">'
            "Erase everything</button></section>" % rows,
            top_lang)


def watch_page(item, top_lang):
    meta = " &middot; ".join(esc(b) for b in (item.get("year"), item.get("lang")) if b)
    return (item["title"],
            '<article class="watch" data-id="%s" data-title="%s" data-cover="%s"'
            ' data-url="%s" data-year="%s">'
            '<div class="watchhead">'
            '<a class="back" href="/">&larr; Back</a>'
            '<h1 class="h1">%s</h1><p class="lede" style="margin-top:4px">%s</p>'
            '<p class="watchbar">'
            '<button class="wl" type="button" data-action="toggle">'
            '<span class="lbl">My List</span><span class="on">In My List</span>'
            "</button>"
            '<a class="btn ghost" href="%s" download>Download</a>'
            "</p></div>"
            '<div class="player"><video id="player" controls preload="metadata"'
            ' playsinline poster="%s"><source src="%s" type="video/mp4">'
            "Your browser cannot play this file. The direct link is below."
            "</video></div>"
            '<p class="resume" data-role="resume"></p>'
            # IE11 has no <details>/<summary>, so the link is simply always
            # visible rather than hiding behind a disclosure that cannot open.
            '<p class="directlab">Direct link</p>'
            '<p class="directlink"><code>%s</code></p>'
            "</article>"
            % (esc(item["id"]), esc(item["title"]), esc(item.get("cover") or ""),
               esc(item["url"]), esc(item.get("year", "")), esc(item["title"]),
               meta, esc(item["url"]), esc(item.get("cover") or ""),
               esc(item["url"]), esc(item["url"])),
            top_lang)


def convert_page(raw, movie_id, ok, ctype, error):
    if error:
        return ("Convert",
                '<section class="hero"><h1 class="display">Convert</h1>'
                '<p class="lede bad">%s</p>%s</section>'
                % (esc(error), search_bar()), "tamil")

    item = {"id": movie_id, "title": "id %s" % movie_id, "year": "", "lang": "",
            "cover": None, "url": E.cdn_link(movie_id)}

    if ok is None:
        badge = ""
    elif ok:
        badge = '<p class="lede good">Confirmed live (%s).</p>' % esc(ctype)
    else:
        badge = ('<p class="lede bad">No file at that address on the CDN. The id '
                 "may be wrong, or the film may be gone.</p>")

    return ("Convert",
            '<section class="hero"><h1 class="display">Convert a link</h1>'
            '<form class="search" action="/convert" method="get">'
            '<span class="field"><input type="text" name="u"'
            ' placeholder="einthusan link or 4-character id" autocomplete="off">'
            "</span>"
            '<button class="btn" type="submit">Convert</button></form>%s</section>'
            '<div class="row"><div class="rail static">%s</div></div>'
            % (badge, card(item)), "tamil")

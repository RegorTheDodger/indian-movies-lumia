"""
HTML rendering for the Windows Phone 8.1 build.

Markup is constrained by IE11 rather than by taste:

  * posters are background-image boxes, because IE11 has no object-fit
  * the direct mp4 link is always visible, because IE11 cannot open <details>
  * inputs are type=text, because IE11 renders type=search inconsistently

Class names match static/legacy.css. static/legacy.js owns the local copy of
personal data (list, resume position, watch time); signed-in users also sync
that data with the shared account database.
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
    ("/", "Home", "home"),
    ("/search", "Search", "search"),
    ("/watchlist", "My List", "list"),
    ("/settings", "Settings", "settings"),
]


def esc(text):
    return html.escape(text or "", quote=True)


ICON_HOME = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none"'
             ' stroke="currentColor" stroke-width="2" stroke-linejoin="round"'
             ' aria-hidden="true"><path d="m3 11 9-8 9 8v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>'
             '<path d="M9 21v-6h6v6"/></svg>')
ICON_SEARCH = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none"'
               ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
               ' aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
               '<path d="m20 20-3.5-3.5"/></svg>')
ICON_LIST = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none"'
             ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
             ' aria-hidden="true"><path d="M5 5h14M5 12h14M5 19h14"/></svg>')
ICON_SETTINGS = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none"'
                 ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
                 ' stroke-linejoin="round" aria-hidden="true"><path d="M9.6 3.2h4.8l.7 2.1a7.3 7.3 0 0 1 1.7 1l2.1-.6 2.4 4.1-1.5 1.6a7.4 7.4 0 0 1 0 2l1.5 1.6-2.4 4.1-2.1-.6a7.3 7.3 0 0 1-1.7 1l-.7 2.1H9.6l-.7-2.1a7.3 7.3 0 0 1-1.7-1l-2.1.6-2.4-4.1 1.5-1.6a7.4 7.4 0 0 1 0-2L2.7 9.8l2.4-4.1 2.1.6a7.3 7.3 0 0 1 1.7-1z"/><circle cx="12" cy="12.4" r="2.7"/></svg>')

NAV_ICONS = {
    "home": ICON_HOME,
    "search": ICON_SEARCH,
    "list": ICON_LIST,
    "settings": ICON_SETTINGS,
}


def safe_cover(url):
    """A cover url that is safe to drop inside url('...') in a style attribute,
    or None."""
    url = (url or "").strip()
    return url if _COVER_OK.match(url) else None


def page(title, body, top_lang="tamil"):
    current = title.lower()
    nav = "".join(
        '<a class="navlink%s" href="%s">%s<span>%s</span></a>'
        % (" on" if (href == "/" and current == "home")
           or href.lstrip("/").lower() == current else "",
           href, NAV_ICONS[key], esc(label))
        for href, label, key in NAV)

    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        # WP8.1 ships IE11; edge mode keeps it there instead of an emulated
        # document mode, which would break the CSS outright.
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="dark">'
        '<link rel="icon" href="/static/icon.svg" type="image/svg+xml">'
        "<title>%s</title>"
        '<link rel="stylesheet" href="/static/legacy.css">'
        "</head><body>"
        '<div class="phone-shell"><header class="phone-head" id="bar">'
        '<a class="brand" href="/"><span class="brand-mark">&#9654;</span>'
        '<span class="brand-name">Indian Movies</span></a>'
        '<span class="head-status">%s</span></header>'
        '<nav class="menu">%s</nav>'
        '<main class="page" data-lang="%s">%s</main>'
        '<footer class="phone-foot"><span>Indian Movies</span>'
        '<span class="st-r">%s</span></footer>'
        "</div>"
        '<script src="/static/legacy.js"></script>'
        "</body></html>"
        % (esc(title), esc(E.LANG_NAMES.get(top_lang, top_lang)), nav,
           esc(top_lang), body,
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
            "</section>%s%s"
            % (esc(E.LANG_NAMES.get(top_lang, top_lang)),
               search_bar(lang=top_lang),
               row("Continue watching", "continue",
                   "Nothing part-watched yet. Start something and it lands here."),
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
            '<section class="panel auth-panel" data-auth-panel><h2>Sync between devices</h2>'
            '<p class="lede" style="margin-top:0">Create an account or log in '
            "to sync your list and watch progress between Lumia and modern.</p>"
            '<p class="auth-status" data-auth-status role="status"></p>'
            '<div data-auth-guest>'
            '<form class="auth-form" data-auth-form="login" action="/auth/login" method="post">'
            '<input type="text" name="username" placeholder="Username" '
            'autocomplete="username" required>'
            '<input type="password" name="password" placeholder="Password" '
            'autocomplete="current-password" required>'
            '<button class="btn" type="submit">Log in</button></form>'
            '<form class="auth-form" data-auth-form="register" action="/auth/register" method="post">'
            '<input type="text" name="username" placeholder="New username" '
            'autocomplete="username" required>'
            '<input type="password" name="password" placeholder="New password (8+ characters)" '
            'autocomplete="new-password" required>'
            '<button class="btn ghost" type="submit">Create account</button></form>'
            '</div><div data-auth-user hidden>'
            '<p class="auth-welcome">Signed in as <b data-auth-name></b></p>'
            '<button class="btn ghost" type="button" data-auth-logout>Log out</button>'
            '</div>'
            '<form action="/auth/logout" method="post" hidden>'
            '<button class="btn ghost" type="submit">Log out</button></form>'
            '<p class="lede" style="margin-top:0">The browser syncs its local '
            "data after authentication.</p></section>"
            '<section class="panel"><h2>Stored data</h2>'
            '<p class="lede" style="margin-top:0">Erase this browser\'s local list, '
            "watch time and resume positions.</p>"
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

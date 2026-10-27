# Indian Movies — Windows Phone 8.1 build

The new site, rebuilt to run on the Lumia, wearing a Windows Phone 8.1
interface. A copy of `einthusan-web/`, with the browser-facing half replaced so that Internet
Explorer 11 can actually render and run it. The original is untouched and still
deploys to Vercel. This copy runs on the LAN and can also be hosted anywhere that
speaks WSGI, which is how the phone reaches it away from home.

| | what it is | port |
| --- | --- | --- |
| `einthusan-cdn/` | old, zero JavaScript, also for the Lumia | 8080 |
| `einthusan-web/` | the modern site, on Vercel | 8090 |
| **`einthusan-lumia/`** | **this build** | **8091** |
| `serve_library.py` | your Win98 movie library | 8000 |

## The look

Every page uses a Windows Phone 8.1-inspired dark Metro surface with a compact
brand header, a cyan active pivot link, large Segoe UI Light headings, flat
accent buttons, touch-sized fields, and horizontally scrolling movie rails.
The layout uses inline blocks and native overflow for the small Lumia screen.

## Why it needed rewriting

WP8.1 ships IE11, so almost everything the modern site is built on is simply
absent. None of the following is used anywhere in this build:

| missing in IE11 | what this does instead |
| --- | --- |
| `const` / `let`, arrows, template literals, classes | plain ES5, `var` and `function` |
| `fetch`, `Promise`, `async` | nothing is fetched — every page is server-rendered |
| `Object.assign`, `Array.from`, `.find()`, `.includes()`, `Set`, `WeakMap` | hand-rolled `extend`, loops, `indexOf` |
| `Element.closest()`, `NodeList.forEach`, `dataset` | a manual `upTo()` walk and `getAttribute()` |
| `classList.toggle(name, force)` | `setCls()` written by hand |
| `URLSearchParams` | `encodeURIComponent` |
| CSS custom properties | the palette is written out literally |
| CSS grid | inline-block and table-ish layout |
| `backdrop-filter` | solid and semi-transparent fills |
| `position: sticky` | `position: fixed` plus a body padding-top |
| `object-fit` | covers are `background-image` boxes at a fixed 2:3 |
| `clamp()`, `aspect-ratio`, `gap`, `:has()` | fixed sizes, a phone breakpoint, margins, a class mirrored in JS |
| `PointerEvent` | native scrolling — the rail is `overflow-x: auto` |
| `<details>` / `<summary>` | the direct mp4 link is just always visible |
| `::selection`, `:focus-within`, `border-radius` | none used; 1998 had square corners anyway |

Verified by `check.js` (78 assertions): the JavaScript is parsed as real ES5 by
acorn — and the check is proven to reject ES6 — and the CSS is scanned for every
property above. Nothing is taken on trust.

## Run it

```sh
cd einthusan-lumia
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py 8091          # http://<mac-ip>:8091
```

No API key: this build makes no model calls. Genres came from Groq and belonged
to the analytics page, which is not here.

## What it does

Search, a player, My List, Continue watching, and Settings.
The einthusan catalogue comes from the server; everything personal lives in
`localStorage` in the phone's browser.

- `iml:watchlist` — saved films
- `iml:progress` — resume positions
- `iml:watched` — accumulated watch time
- `iml:catalog` — titles and covers seen, so shelves can render offline

Resume works the same as the modern site: under 8 seconds is ignored, past 95%
counts as finished, and a jump longer than 6 seconds is treated as a seek rather
than watching.

## Notes for whoever touches this next

- **Do not add `vercel.json` or an `api/` directory.** This copy is deliberately
  not a Vercel project.
- **The `-ms-` prefixes matter.** `-ms-text-size-adjust`, `-ms-touch-action` and
  the `.rail` inline-block layout are what make the phone behave; removing them
  as "dead code" breaks it.
- **The cover url is vetted twice**, in `views.py` and in `legacy.js`. A cover
  ends up inside `url('...')` in a style attribute, so a quote or bracket in it
  would break out of the CSS string. Both regexes reject anything but a plain
  http(s) url.
- **`einthusan-lumia/` is a copy, not a fork.** If `lib/einthusan.py` changes
  upstream it has to be copied across by hand.

## Layout

```
app.py             local dev server
lib/einthusan.py   all network access, parsing, search   (unchanged)
lib/ai.py          unused here, kept so the package matches   (unchanged)
lib/webapp.py      routes
lib/views.py       HTML, IE11-shaped
static/legacy.css  IE11-safe stylesheet
static/legacy.js   ES5 client
```

## Hosting

It is a Flask app, so GitHub Pages cannot serve it — Pages is static files only
and every page here is built on the server. Host it on anything that runs Python.

`render.yaml` describes a Render web service: free plan, one gunicorn worker with
eight threads, `/healthz` as the check. Push, then point Render at the repo.
Set the Render `DATABASE_URL` environment variable to the same Neon connection
string used by the modern Vercel deployment. This is required for a Lumia login
to work with the same account and sync state as the modern site. Without it,
the app intentionally falls back to a local SQLite database, which is separate
from Vercel and is not suitable for cross-deployment accounts.

```
gunicorn app:app --workers 1 --threads 8 --timeout 120
```

One worker on purpose. The search pool holds one keep-alive connection per
language inside the process, so a second worker would double the outbound
connections for no gain on a single-user site.

On the free plan the instance sleeps after a while and the first visit then takes
half a minute to wake. That is the price of free; a paid instance stays warm.

/*
 * Client for Internet Explorer 11 (Windows Phone 8.1).
 *
 * There is no fetch, no Promise, no arrow function, no template literal, no
 * const/let, no Object.assign, no Set, no Array.from/find/findIndex, and no
 * Element.closest. None of those appear below. Everything here is ES5 and
 * feature-detected at the level of "does this method exist in IE11 at all".
 *
 * No XHR either: search and the watch page are rendered by the server, so the
 * only job here is the handful of things the server cannot own, which is
 * anything personal. That all lives in localStorage:
 *
 *   iml:watchlist  [{id, title, cover, url, year}]
 *   iml:progress   {id: {seconds, duration, at, meta}}
 *   iml:watched    {id: {title, cover, url, year, lang, seconds, finished, at}}
 *   iml:catalog    {id: {title, cover, url, year}}
 */

(function () {
  "use strict";

  var LS_LIST = "iml:watchlist";
  var LS_PROGRESS = "iml:progress";
  var LS_WATCHED = "iml:watched";
  var LS_CATALOG = "iml:catalog";
  var LS_REMOVED = "iml:removed";

  var DONE_AT = 0.95;      /* past this fraction a film counts as finished */
  var MIN_SECONDS = 8;     /* below this it is not worth remembering */
  var SEEK_LIMIT = 6;      /* a bigger jump is a seek, not watching */

  /* ------------------------------------------------------------ helpers */

  /* IE11 has no Element.closest, and classList.toggle ignores a force arg */
  function setCls(el, name, on) {
    var parts = (" " + el.className + " ").split(/\s+/);
    var out = [];
    var i, seen = false, p;
    for (i = 0; i < parts.length; i++) {
      p = parts[i];
      if (!p) continue;
      if (p === name) {
        seen = true;
        if (!on) continue;
      }
      out.push(p);
    }
    if (on && !seen) out.push(name);
    el.className = out.join(" ");
  }

  function hasCls(el, name) {
    return (" " + el.className + " ").indexOf(" " + name + " ") >= 0;
  }

  /* walk up until an element carries the attribute; closest() by hand */
  function upTo(el, attribute) {
    while (el && el.nodeType === 1) {
      if (el.getAttribute(attribute) !== null) return el;
      el = el.parentNode;
    }
    return null;
  }

  function attr(el, name) {
    return el.getAttribute(name) || "";
  }

  function each(list, fn) {
    for (var i = 0; i < list.length; i++) fn(list[i], i);
  }

  function isArray(v) {
    return Object.prototype.toString.call(v) === "[object Array]";
  }

  function escHtml(text) {
    return String(text === null || text === undefined ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function extend(target) {
    for (var i = 1; i < arguments.length; i++) {
      var src = arguments[i];
      if (!src) continue;
      for (var k in src) {
        if (Object.prototype.hasOwnProperty.call(src, k)) target[k] = src[k];
      }
    }
    return target;
  }

  /* the same vetting the server does, because covers also arrive from
     localStorage and end up inside url('...') in a style attribute */
  var COVER_OK = /^(?:https?:)?\/\/[^\s"'()\\<>]+$/i;
  function safeCover(url) {
    url = String(url || "").replace(/^\s+|\s+$/g, "");
    return COVER_OK.test(url) ? url : "";
  }

  function fmtSeconds(total) {
    var s = Math.floor(total || 0);
    var m = Math.floor(s / 60);
    return m + "m " + (s % 60) + "s";
  }

  /* -------------------------------------------------------------- store */

  function read(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function write(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      /* private mode, or quota */
    }
  }

  function getList() {
    var v = read(LS_LIST, []);
    return isArray(v) ? v : [];
  }
  function getProgress() { return read(LS_PROGRESS, {}) || {}; }
  function getWatched() { return read(LS_WATCHED, {}) || {}; }
  function getCatalog() { return read(LS_CATALOG, {}) || {}; }
  function getRemoved() { return read(LS_REMOVED, {}) || {}; }

  function setList(list) {
    write(LS_LIST, list);
    paint();
  }

  function remember(item) {
    if (!item || !item.id || !item.title) return;
    var cat = getCatalog();
    var prev = cat[item.id] || {};
    cat[item.id] = {
      id: item.id,
      title: item.title || prev.title || item.id,
      cover: item.cover || prev.cover || "",
      url: item.url || prev.url || "/watch/" + item.id,
      year: item.year || prev.year || ""
    };
    write(LS_CATALOG, cat);
  }

  function toggleList(item) {
    var list = getList();
    var removed = getRemoved();
    var at = -1;
    var i;
    for (i = 0; i < list.length; i++) {
      if (list[i] && list[i].id === item.id) { at = i; break; }
    }
    if (at >= 0) {
      list.splice(at, 1);
      removed[item.id] = new Date().getTime();
    } else {
      delete removed[item.id];
      list.unshift({
        id: item.id,
        title: item.title,
        cover: item.cover || "",
        url: item.url,
        year: item.year || "",
        at: new Date().getTime()
      });
    }
    write(LS_REMOVED, removed);
    setList(list);
  }

  /* ----------------------------------------------------------- progress */

  function setResume(id, seconds, duration, meta) {
    var p = getProgress();
    if (!duration || !isFinite(duration) || duration < 1) return;
    var frac = seconds / duration;
    if (seconds < MIN_SECONDS || frac >= DONE_AT) {
      delete p[id];
    } else {
      if (meta) remember(meta);
      p[id] = {
        /* IE11 has no Number.isFinite; the global is fine here */
        seconds: Math.floor(seconds),
        duration: Math.floor(duration),
        at: new Date().getTime(),
        meta: meta || (p[id] && p[id].meta) || null
      };
    }
    write(LS_PROGRESS, p);
  }

  function addWatchTime(id, delta, meta) {
    if (!delta || delta <= 0 || delta > SEEK_LIMIT) return;
    var w = getWatched();
    var prev = w[id] || {};
    if (meta) remember(meta);
    w[id] = extend({ seconds: 0, finished: false }, prev, meta || {},
                   { seconds: (prev.seconds || 0) + delta,
                     at: new Date().getTime() });
    write(LS_WATCHED, w);
  }

  function markFinished(id, meta) {
    var w = getWatched();
    var prev = w[id] || {};
    if (meta) remember(meta);
    w[id] = extend({ seconds: 0, finished: false }, prev, meta || {},
                   { finished: true, at: new Date().getTime() });
    write(LS_WATCHED, w);
    var p = getProgress();
    delete p[id];
    write(LS_PROGRESS, p);
  }

  function continueWatching() {
    var p = getProgress();
    var cat = getCatalog();
    var list = getList();
    var out = [];
    var id, i, meta;

    for (id in p) {
      if (!Object.prototype.hasOwnProperty.call(p, id)) continue;
      var entry = p[id];
      meta = extend({}, cat[id] || {}, entry.meta || {});
      if (!meta.id) meta.id = id;
      if (!meta.title) continue;
      if (!meta.url) meta.url = "/watch/" + id;
      meta.frac = entry.duration ? entry.seconds / entry.duration : 0;
      meta.at = entry.at || 0;
      meta.saved = false;
      for (i = 0; i < list.length; i++) {
        if (list[i] && list[i].id === id) { meta.saved = true; break; }
      }
      if (meta.frac > 0.01 && meta.frac < DONE_AT) out.push(meta);
    }

    out.sort(function (a, b) { return b.at - a.at; });
    return out.slice(0, 24);
  }

  /* ------------------------------------------------------------ markup */

  function watchHref(m) {
    /* no URLSearchParams in IE11 */
    return "/watch/" + encodeURIComponent(m.id) +
      "?t=" + encodeURIComponent(m.title || "") +
      "&c=" + encodeURIComponent(m.cover || "") +
      "&y=" + encodeURIComponent(m.year || "") +
      "&l=" + encodeURIComponent(m.lang || "");
  }

  function cardHtml(m) {
    var cover = safeCover(m.cover);
    var poster = cover
      ? '<span class="art" style="background-image:url(\'' + cover + '\')"></span>'
      : '<span class="nocover">No artwork</span>';

    var bar = "";
    if (typeof m.frac === "number" && m.frac > 0) {
      var pct = Math.round(m.frac * 100);
      bar = '<div class="pbar"><span class="pbar-track"><i style="width:' +
        pct + '%"></i></span><b>' + pct + "% watched</b></div>";
    }

    var meta = [];
    if (m.year) meta.push(m.year);
    if (m.lang) meta.push(m.lang);

    var href = watchHref(m);
    var wl = '<button class="wl' + (m.saved ? " on" : "") +
      '" type="button" data-action="toggle">' +
      '<span class="lbl">+ My List</span><span class="on">&#10003; Added</span>' +
      "</button>";

    return '<article class="card" data-id="' + escHtml(m.id) +
      '" data-title="' + escHtml(m.title) +
      '" data-cover="' + escHtml(m.cover || "") +
      '" data-url="' + escHtml(m.url || "") +
      '" data-year="' + escHtml(m.year || "") + '">' +
      '<a class="poster" href="' + href + '">' + poster + "</a>" + bar +
      (meta.length ? '<p class="cmeta">' + escHtml(meta.join(" \u00b7 ")) + "</p>" : "") +
      '<h3 class="ctitle"><a href="' + href + '">' + escHtml(m.title) + "</a></h3>" +
      wl + "</article>";
  }

  function fill(shelf, items, savedIds) {
    var host = document.querySelector('[data-shelf="' + shelf + '"]');
    var note = document.querySelector('[data-empty="' + shelf + '"]');
    if (!host) return;

    var html = "";
    for (var i = 0; i < items.length; i++) {
      var m = extend({}, items[i]);
      m.saved = wasSaved(savedIds, m.id);
      html += cardHtml(m);
    }
    host.innerHTML = html;
    if (note) note.style.display = items.length ? "none" : "";
  }

  function wasSaved(savedIds, id) {
    for (var i = 0; i < savedIds.length; i++) {
      if (savedIds[i] === id) return true;
    }
    return false;
  }

  function paint() {
    var list = getList();
    var savedIds = [];
    var i;

    for (i = 0; i < list.length; i++) {
      if (list[i] && list[i].id) {
        savedIds.push(list[i].id);
        remember(list[i]);
      }
    }

    /* every card the server rendered is a chance to learn about a film */
    each(document.querySelectorAll("[data-id][data-title]"), function (el) {
      remember({
        id: attr(el, "data-id"),
        title: attr(el, "data-title"),
        cover: attr(el, "data-cover"),
        url: attr(el, "data-url"),
        year: attr(el, "data-year")
      });
    });

    var saved = [];
    for (i = 0; i < list.length; i++) {
      if (list[i]) saved.push(extend({ saved: true }, list[i]));
    }
    fill("watchlist", saved, savedIds);
    fill("watchlist-full", saved, savedIds);
    fill("continue", continueWatching(), savedIds);
    /* reflect the state on every button, including the player page */
    each(document.querySelectorAll(".wl"), function (btn) {
      var host = upTo(btn, "data-id");
      if (host) setCls(btn, "on", wasSaved(savedIds, attr(host, "data-id")));
    });
  }

  /* ------------------------------------------------------------ player */

  function wirePlayer() {
    var video = document.getElementById("player");
    var wrap = document.querySelector(".watch");
    if (!video || !wrap) return;

    var id = attr(wrap, "data-id");
    var meta = {
      id: id,
      title: attr(wrap, "data-title"),
      cover: attr(wrap, "data-cover"),
      url: attr(wrap, "data-url"),
      year: attr(wrap, "data-year")
    };
    remember(meta);

    var note = wrap.querySelector('[data-role="resume"]');
    var resume = getProgress()[id];
    var pendingResume = 0;

    if (resume && resume.duration && resume.seconds > MIN_SECONDS) {
      pendingResume = Math.min(resume.seconds, resume.duration - 5);
      if (note) note.textContent = "Resume point saved: " + fmtSeconds(pendingResume) + ".";
    }

    /* seek once the film can actually be seeked */
    function onMeta() {
      if (pendingResume > 0) {
        try {
          video.currentTime = pendingResume;
          if (note) note.textContent = "Resumed at " + fmtSeconds(pendingResume) + ".";
        } catch (e) {
          /* some files refuse an early seek; leaving it at 0 is harmless */
        }
        pendingResume = 0;
      }
    }
    video.addEventListener("loadedmetadata", onMeta);
    video.addEventListener("canplay", onMeta);

    var lastTick = 0;
    var lastSave = 0;

    function tick() {
      var now = video.currentTime;
      var delta = now - lastTick;
      if (delta > 0 && delta <= SEEK_LIMIT) addWatchTime(id, delta, meta);
      lastTick = now;
      setResume(id, now, video.duration, meta);
    }

    video.addEventListener("timeupdate", function () {
      var t = new Date().getTime();
      if (t - lastSave < 4000) return;
      lastSave = t;
      tick();
    });

    video.addEventListener("seeking", function () { lastTick = video.currentTime; });
    video.addEventListener("play", function () { lastTick = video.currentTime; });
    video.addEventListener("pause", tick);
    video.addEventListener("ended", function () {
      markFinished(id, meta);
      paint();
      syncAccount();
    });

    /* last chance to record where they got to */
    window.addEventListener("beforeunload", tick);
    window.addEventListener("pagehide", tick);
  }

  /* -------------------------------------------------------------- rails */

  function syncArrows(rail) {
    var row = upTo(rail, "data-row") || rail.parentNode;
    if (!row) return;
    var left = row.querySelector(".arrow.left");
    var right = row.querySelector(".arrow.right");
    var max = rail.scrollWidth - rail.clientWidth;
    var overflowing = max > 4;
    if (left) left.hidden = !overflowing || rail.scrollLeft <= 4;
    if (right) right.hidden = !overflowing || rail.scrollLeft >= max - 4;
  }

  function wireRails() {
    each(document.querySelectorAll(".rail"), function (rail) {
      if (hasCls(rail, "static")) return;
      rail.addEventListener("scroll", function () { syncArrows(rail); });
      syncArrows(rail);
    });
  }

  /* ------------------------------------------------------------- wiring */

  document.addEventListener("click", function (event) {
    var target = event.target;

    var btn = upTo(target, "data-action");
    if (btn) {
      var action = attr(btn, "data-action");
      if (action === "toggle") {
        var card = upTo(btn, "data-id");
        if (card) {
          toggleList({
            id: attr(card, "data-id"),
            title: attr(card, "data-title"),
            cover: attr(card, "data-cover"),
            url: attr(card, "data-url"),
            year: attr(card, "data-year")
          });
        }
      } else if (action === "clear-watchlist") {
        var removed = getRemoved();
        var saved = getList();
        var si;
        for (si = 0; si < saved.length; si++) {
          if (saved[si] && saved[si].id) {
            removed[saved[si].id] = new Date().getTime();
          }
        }
        write(LS_REMOVED, removed);
        setList([]);
      } else if (action === "clear-all") {
        try {
          localStorage.removeItem(LS_LIST);
          localStorage.removeItem(LS_PROGRESS);
          localStorage.removeItem(LS_WATCHED);
          localStorage.removeItem(LS_CATALOG);
          localStorage.removeItem(LS_REMOVED);
        } catch (e) { /* nothing to do */ }
        paint();
      }
      syncAccount();
      return;
    }

    var arrow = upTo(target, "data-scroll");
    if (arrow) {
      var row = upTo(arrow, "data-row");
      var rail = row ? row.querySelector(".rail") : null;
      if (rail) {
        rail.scrollLeft = rail.scrollLeft +
          Number(attr(arrow, "data-scroll")) * rail.clientWidth * 0.85;
      }
    }
  });

  /* no :has() in IE11, so mirror :checked onto the label for the styling */
  function wireSettings() {
    var labels = document.querySelectorAll(".radio");
    if (!labels.length) return;

    function sync() {
      each(labels, function (label) {
        var input = label.querySelector("input");
        setCls(label, "on", !!(input && input.checked));
      });
    }
    each(labels, function (label) {
      label.addEventListener("click", function () {
        setTimeout(sync, 0);   /* let the radio take the click first */
      });
    });
    sync();
  }

  /* IE11-compatible account sync. Passwords are handled only by the server;
   * this client sends the existing local state after the session is present. */
  function syncAccount() {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/auth/me", true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4 || xhr.status !== 200) return;
      var account;
      try { account = JSON.parse(xhr.responseText); } catch (e) { return; }
      if (!account.authenticated) return;

      var state = {
        watchlist: getList(),
        progress: getProgress(),
        watched: getWatched(),
        catalog: getCatalog(),
        removed: getRemoved()
      };
      var send = new XMLHttpRequest();
      send.open("POST", "/api/sync", true);
      send.setRequestHeader("Content-Type", "application/json");
      send.onreadystatechange = function () {
        if (send.readyState !== 4 || send.status !== 200) return;
        var result;
        try { result = JSON.parse(send.responseText); } catch (e2) { return; }
        if (!result.state) return;
        write(LS_LIST, result.state.watchlist || []);
        write(LS_PROGRESS, result.state.progress || {});
        write(LS_WATCHED, result.state.watched || {});
        write(LS_CATALOG, result.state.catalog || {});
        write(LS_REMOVED, result.state.removed || {});
        paint();
      };
      send.send(JSON.stringify(state));
    };
    xhr.send();
  }

  function updateAuthUi(account, message) {
    var guest = document.querySelector("[data-auth-guest]");
    var signedIn = document.querySelector("[data-auth-user]");
    var name = document.querySelector("[data-auth-name]");
    var status = document.querySelector("[data-auth-status]");
    var loggedIn = !!(account && account.authenticated);
    if (guest) {
      guest.style.display = loggedIn ? "none" : "";
      if (loggedIn) guest.setAttribute("hidden", "hidden");
      else guest.removeAttribute("hidden");
    }
    if (signedIn) {
      signedIn.style.display = loggedIn ? "" : "none";
      if (loggedIn) signedIn.removeAttribute("hidden");
      else signedIn.setAttribute("hidden", "hidden");
    }
    if (name) name.innerHTML = loggedIn ? escHtml(account.user.display) : "";
    if (status) {
      status.innerHTML = escHtml(message || "");
      setCls(status, "good", !!message && loggedIn);
    }
  }

  function wireAuth() {
    var check = new XMLHttpRequest();
    check.open("GET", "/auth/me", true);
    check.onreadystatechange = function () {
      if (check.readyState !== 4 || check.status !== 200) return;
      try { updateAuthUi(JSON.parse(check.responseText)); } catch (e) {}
    };
    check.send();

    document.addEventListener("submit", function (event) {
      var form = upTo(event.target, "data-auth-form");
      if (!form) return;
      event.preventDefault();
      var xhr = new XMLHttpRequest();
      xhr.open("POST", attr(form, "action"), true);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4) return;
        var result;
        try { result = JSON.parse(xhr.responseText); } catch (e) { return; }
        if (xhr.status < 200 || xhr.status >= 300) {
          updateAuthUi({ authenticated: false }, result.error || "Could not sign in.");
          return;
        }
        form.reset();
        updateAuthUi(result, "Signed in. Your library is syncing.");
        syncAccount();
      };
      xhr.send(JSON.stringify({
        username: form.querySelector('[name="username"]').value,
        password: form.querySelector('[name="password"]').value
      }));
    });

    document.addEventListener("click", function (event) {
      var button = upTo(event.target, "data-auth-logout");
      if (!button) return;
      var xhr = new XMLHttpRequest();
      xhr.open("POST", "/auth/logout", true);
      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4) return;
        updateAuthUi({ authenticated: false }, "You are signed out.");
        paint();
      };
      xhr.send();
    });
  }

  function init() {
    paint();
    wireAuth();
    syncAccount();
    wirePlayer();
    wireRails();
    wireSettings();
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
  window.addEventListener("pageshow", paint);
}());

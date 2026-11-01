# -*- coding: utf-8 -*-
"""الخادم المحلي: واجهة ويب + API + مجدول الجمع + المترجم."""
import os
import io
import csv
import json
import time
import mimetypes
import threading
import traceback
import hmac
import secrets
import socket
import subprocess
import sys
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from . import config as C
from . import process as P
from .db import Store
from .collectors import Collector

STATIC = os.path.join(C.BASE_DIR, "static")
KEY_PATH = os.path.join(C.DATA_DIR, "access.key")


def get_key():
    env = (os.environ.get("RADAR_KEY") or "").strip()
    if len(env) >= 16:       # على الاستضافة السحابية: المفتاح يأتي من متغير بيئة فلا يضيع مع إعادة التشغيل
        return env
    try:
        with open(KEY_PATH, encoding="utf-8") as f:
            k = f.read().strip()
            if len(k) >= 16:
                return k
    except Exception:
        pass
    k = secrets.token_hex(12)
    os.makedirs(C.DATA_DIR, exist_ok=True)
    with open(KEY_PATH, "w", encoding="utf-8") as f:
        f.write(k)
    return k


def lan_ip():
    try:
        s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_.connect(("10.255.255.255", 1))
        ip = s_.getsockname()[0]
        s_.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

CAT_NAMES = {k: v[0] for k, v in C.CATEGORIES.items()}
CAT_NAMES[C.DEFAULT_CATEGORY[0]] = C.DEFAULT_CATEGORY[1]

MANIFEST = {
    "name": "أخباري — My News", "short_name": "أخباري", "description": "رصد كل ما يُنشر عن ليبيا بكل اللغات",
    "start_url": "/", "scope": "/", "display": "standalone", "dir": "rtl", "lang": "ar",
    "background_color": "#0a2463", "theme_color": "#1d56d8",
    "icons": [{"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
              {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}],
}

ADD_PAGE = """<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>أخباري</title>
<body style="font-family:Segoe UI,Tahoma,sans-serif;background:#0a2463;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center">
<div><img src="/icons/icon-128.png" width="72"><h2 id="m">جارٍ الاستلام…</h2><div id="d" style="opacity:.8;font-size:14px"></div></div>
<script>
var OK=/(^|\\.)(facebook\\.com|x\\.com|twitter\\.com|fb\\.com)$/;
function send(body){
 fetch('/api/ingest',{method:'POST',headers:{'Content-Type':'application/json','X-MyNews':'1'},body:JSON.stringify(body)})
 .then(function(r){return r.json()}).then(function(j){
  var m=document.getElementById('m'),d=document.getElementById('d');
  if(j.batch!==undefined){m.textContent='✓ أُضيف '+j.new+' منشور جديد';d.textContent='من أصل '+j.batch+' التُقطت ('+(j.batch-j.new)+' موجودة مسبقاً)'}
  else{m.textContent=j.new?'✓ أُضيف إلى أخباري':(j.ok?'موجود مسبقاً':'تعذّرت الإضافة');d.textContent=j.title||j.error||''}
  setTimeout(function(){window.close()},2200)})
 .catch(function(){document.getElementById('m').textContent='تعذّر الاتصال بأخباري — هل التطبيق يعمل؟'});
}
var q=new URLSearchParams(location.search);
if(q.get('batch')){
 window.addEventListener('message',function(e){
  try{var h=new URL(e.origin).hostname}catch(x){return}
  if(!OK.test(h)||!e.data||e.data.mynews!==1)return;
  document.getElementById('m').textContent='جارٍ الإضافة…';send({posts:e.data.posts,site:e.data.site});
 });
 if(window.opener)window.opener.postMessage({mynews:'ready'},'*');
}else{send({url:q.get('u')||'',title:q.get('t')||'',text:q.get('x')||''})}
</script></body></html>"""


def load_extra_feeds():
    try:
        with open(C.EXTRA_FEEDS_PATH, encoding="utf-8") as f:
            lst = json.load(f)
    except Exception:
        return []
    seen, out = set(), []
    for x in lst:       # إزالة التكرار (نفس الرابط أو نفس الاسم من المكتشف)
        k = (x.get("url") or "").rstrip("/").lower()
        k2 = (x.get("name") or "").strip().lower() if x.get("auto") else None
        if not k or k in seen or (k2 and k2 in seen):
            continue
        seen.add(k)
        if k2:
            seen.add(k2)
        out.append(x)
    return out


def save_extra_feeds(lst):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    with open(C.EXTRA_FEEDS_PATH, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=1)


class App:
    def __init__(self, store=None, collector=None, autostart=True):
        self.store = store or Store()
        self.extra = load_extra_feeds()
        self.collector = collector or Collector(self.store, self.extra)
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.pending_mode = None
        self.thread = None
        self.translator = None
        self.discoverer = None
        self.digester = None
        self.maintainer = None
        self.server = None
        if autostart:
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            from .translate import Translator
            self.translator = Translator(self.store, self.stop)
            self.translator.start()
            from .discover import Discoverer
            self.discoverer = Discoverer(self)
            self.discoverer.start()
            from .digest import Digester
            self.digester = Digester(self)
            self.digester.start()
            threading.Thread(target=self._fast_lane, daemon=True).start()
            threading.Thread(target=self._prestige_lane, daemon=True).start()
            from .maintain import Maintainer
            self.maintainer = Maintainer(self)
            self.maintainer.start()

    def _prestige_lane(self):
        """كل 40 دقيقة: المراجع الدولية (صحف ووكالات ومراكز أبحاث ومنظمات)."""
        if self.stop.wait(150):
            return
        while not self.stop.is_set():
            try:
                if not self.collector.status["running"]:
                    self.collector.run_prestige("lane")
            except Exception:
                traceback.print_exc()
            if self.stop.wait(2400):
                return

    def _fast_lane(self):
        """كل 3 دقائق: المصادر المباشرة المهمة فقط (جلب شرطي خفيف)."""
        if self.stop.wait(90):
            return
        while not self.stop.is_set():
            try:
                self.collector.run_direct()
            except Exception:
                traceback.print_exc()
            if self.stop.wait(180):
                return

    def _loop(self):
        n = 0
        empty = self.store.stats()["total"] == 0
        while not self.stop.is_set():
            mode = self.pending_mode or ("deep" if (n == 0 and empty) else ("full" if n % 6 == 0 else "fast"))
            self.pending_mode = None
            try:
                self.collector.run_cycle(mode)
            except Exception:
                traceback.print_exc()
            n += 1
            self.wake.wait(C.CYCLE_MINUTES * 60)
            self.wake.clear()

    def refresh(self, mode="full"):
        self.pending_mode = mode
        self.wake.set()

    def ingest(self, b):
        if isinstance(b.get("posts"), list):
            posts = b["posts"][:300]
            n_new = 0
            for p in posts:
                if not isinstance(p, dict):
                    continue
                site = b.get("site") or ""
                p = dict(p)
                p["site"] = site
                r = self._ingest_one(p)
                if r.get("new"):
                    n_new += 1
            return {"ok": True, "batch": len(posts), "new": n_new}
        return self._ingest_one(b)

    def _ingest_one(self, b):
        url = (b.get("url") or "").strip()
        text = P.strip_html((b.get("text") or "").strip())
        title = P.strip_html((b.get("title") or "").strip())
        host = P.domain_of(url)
        author = (b.get("author") or "").strip()[:60]
        if "facebook.com" in host or host.endswith("fb.com") or host.endswith("fb.watch") or b.get("site") == "fb":
            source = ("فيسبوك — " + author) if author else "فيسبوك"
        elif host in ("x.com", "twitter.com", "mobile.twitter.com") or host.endswith(".x.com") or b.get("site") == "x":
            source = ("إكس — " + author) if author else "إكس"
        elif "t.me" in host:
            source = "تلغرام"
        else:
            source = (b.get("source") or host or "إدخال يدوي")[:60]
        head = (text or title)[:220].strip()
        if not head:
            return {"ok": False, "error": "لا يوجد نص"}
        if not url.startswith("http"):
            url = ""
        lang = P.detect_lang(head)
        rel, matched = P.relevance(head, text)
        if b.get("site") and rel < 2:
            return {"ok": True, "new": False, "skipped": "غير ذي صلة بليبيا"}
        rec = {"title": head, "url": url, "summary": text[:1200], "source": source, "stype": "social", "via": "manual",
               "lang": lang, "published": int(time.time()), "rel": max(rel, 3), "matched": matched or ["إدخال يدوي"]}
        new = self.store.add_item(rec)
        return {"ok": True, "new": bool(new), "title": head[:80]}


def make_handler(app):
    store = app.store
    key = get_key()
    lan = C.HOST not in ("127.0.0.1", "localhost", "::1")
    PUBLIC = ("/icons/", "/favicon.ico")
    DENY = ("<!doctype html><meta charset=utf-8><body dir=rtl style='font-family:Segoe UI,Tahoma;background:#0a2463;color:#fff;"
            "text-align:center;padding:60px 20px'><h2>أخباري</h2><p>الوصول من هذا الجهاز يحتاج رابط الوصول السري.<br>افتح أخباري على الحاسوب "
            "← تبويب «الآيفون» وانسخ الرابط.</p>")

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None, cache="no-store"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False)
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            if self._setck:
                self.send_header("Set-Cookie", "mn_key=%s; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax%s" % (key, "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""))
            self.end_headers()
            self.wfile.write(body)

        _setck = False

        def _is_loop(self):
            return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

        def _host_ok(self):
            p = self.server.server_address[1]
            return (self.headers.get("Host") or "").lower() in ("127.0.0.1:%d" % p, "localhost:%d" % p)

        def _auth(self, q):
            """الجهاز نفسه: يكفي التحقق من Host (ضد DNS rebinding). الأجهزة الأخرى: رمز سري عبر الرابط أو الكوكي."""
            if self._is_loop():
                return self._host_ok()
            if not lan:
                return False
            given = q.get("k") or ""
            if not given:
                try:
                    ck = SimpleCookie(self.headers.get("Cookie") or "")
                    given = ck["mn_key"].value if "mn_key" in ck else ""
                except Exception:
                    given = ""
            ok = hmac.compare_digest(given.encode(), key.encode())
            if ok and q.get("k"):
                self._setck = True
            return ok

        def _key_q(self, q):
            return "?k=" + key if (not self._is_loop() and lan) else ""

        def _write_ok(self):
            # يمنع صفحات الإنترنت الأخرى من إرسال أوامر لتطبيقك
            return self.headers.get("X-MyNews") == "1"

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode("utf-8"))
            except Exception:
                return {}

        def _static(self, rel, cache="public, max-age=3600"):
            full = os.path.normpath(os.path.join(STATIC, rel))
            if not full.startswith(STATIC + os.sep) or not os.path.isfile(full):
                return self._send(404, {"error": "not found"})
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("image/svg+xml", "application/json"):
                ctype += "; charset=utf-8"
            with open(full, "rb") as f:
                return self._send(200, f.read(), ctype, cache=cache)

        def _index(self, q):
            with open(os.path.join(STATIC, "index.html"), "rb") as f:
                html = f.read().decode("utf-8").replace("__KEYQ__", self._key_q(q))
            return self._send(200, html, "text/html; charset=utf-8")

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            public = u.path == "/favicon.ico" or u.path.startswith("/icons/")
            if not public and not self._auth(q):
                return self._send(401 if not self._is_loop() else 403, DENY, "text/html; charset=utf-8")
            try:
                if u.path in ("/", "/index.html"):
                    return self._index(q)
                if u.path == "/add":
                    return self._send(200, ADD_PAGE, "text/html; charset=utf-8")
                if u.path == "/api/phone":
                    if not self._is_loop():
                        return self._send(403, {"error": "forbidden"})
                    p = self.server.server_address[1]
                    ip = lan_ip()
                    return self._send(200, {"lan": lan, "ip": ip, "port": p, "url": "http://%s:%d/?k=%s" % (ip, p, key)})
                if u.path == "/api/reader":
                    from . import reader as RD
                    return self._send(200, RD.read(store, q.get("url", ""), q.get("tr") == "1"))
                if u.path == "/api/ticker":
                    mins = max(5, min(int(q.get("minutes", 90)), 720))
                    res = store.stories({"hours": mins / 60.0, "known": "1", "min_rel": 2}, limit=25, sort="latest")["stories"]
                    out = [{"id": x["id"], "title": x["title"], "source_ar": x["source_ar"], "url": x["url"],
                            "published": x["last_known"] or x["last_pub"], "urgency": x["urgency"],
                            "n_domains": x["n_domains"], "category": x["category"]} for x in res]
                    out.sort(key=lambda x: -x["published"])
                    return self._send(200, {"now": int(time.time()), "items": out})
                if u.path == "/api/digests":
                    return self._send(200, {"now": int(time.time()), "digests": store.digests(min(int(q.get("limit", 24)), 96)),
                                            "next": app.digester.stats.get("next") if app.digester else None})
                if u.path == "/api/discovery":
                    d = app.discoverer
                    auto = [f for f in app.extra if f.get("auto")]
                    return self._send(200, {"stats": d.stats if d else {}, "auto": [{"name": f["name"], "url": f["url"], "site": f.get("site"), "added": f.get("added")} for f in auto][-60:], "count": len(auto)})
                if u.path == "/manifest.webmanifest":
                    m = dict(MANIFEST)
                    m["start_url"] = "/" + self._key_q(q)
                    return self._send(200, m, "application/manifest+json; charset=utf-8", cache="no-store")
                if u.path == "/favicon.ico":
                    return self._static("icons/mynews.ico")
                if u.path.startswith("/icons/"):
                    return self._static("icons/" + u.path[len("/icons/"):])
                if u.path == "/api/stories":
                    lim, off = min(int(q.get("limit", 40)), 200), int(q.get("offset", 0))
                    if q.get("sort") == "top":
                        from .digest import score
                        res = store.stories(q, limit=400, offset=0, sort="latest")
                        now_ = int(time.time())
                        pins = {r["value"] for r in store.rules() if r.get("kind") == "pin_source"}

                        def _sc(x):
                            b = 4 if pins and any((it.get("domain") in pins or it.get("source") in pins) for it in x.get("items", [])) else 0
                            return score(x, now_) + b
                        res["stories"].sort(key=_sc, reverse=True)
                        res["stories"] = res["stories"][off:off + lim]
                    else:
                        res = store.stories(q, limit=lim, offset=off, sort=q.get("sort", "latest"))
                    wl = [P.norm_text(w) for w in store.watches()]
                    if wl:
                        for s in res["stories"]:
                            t = P.norm_text(s["title"] + " " + s.get("title_orig", "") + " " + (s["summary"] or ""))
                            s["watch_hits"] = [w for w in wl if w in t]
                    return self._send(200, res)
                if u.path == "/api/stats":
                    return self._send(200, store.stats())
                if u.path == "/api/health":
                    return self._send(200, store.health())
                if u.path == "/api/status":
                    st = dict(app.collector.status)
                    st["now"] = int(time.time())
                    st["cycle_minutes"] = C.CYCLE_MINUTES
                    st["translation"] = store.translation_status()
                    if app.translator:
                        st["translator"] = app.translator.stats
                    if app.maintainer:
                        st["maint"] = app.maintainer.stats
                    return self._send(200, st)
                if u.path == "/api/meta":
                    return self._send(200, {"categories": CAT_NAMES, "name": C.APP_NAME, "name_en": C.APP_NAME_EN, "version": C.APP_VERSION,
                                            "langs": [l[0] for l in C.LANGS], "watches": store.watches(), "port": C.PORT})
                if u.path == "/api/alerts":
                    return self._send(200, store.alerts(int(q.get("since", 0)), int(q.get("min_urgency", 6))))
                if u.path == "/api/tracked":
                    return self._send(200, {"tracked": json.loads(store.meta_get("tracked", "[]"))})
                if u.path == "/api/feeds":
                    return self._send(200, {"builtin": C.DIRECT_FEEDS, "pages": C.AUTODISCOVER_PAGES,
                                            "telegram": C.TELEGRAM_CHANNELS, "mine": app.extra})
                if u.path == "/api/rules":
                    return self._send(200, {"rules": store.rules(), "saved": store.saved()})
                if u.path == "/api/opml":
                    from xml.sax.saxutils import quoteattr
                    rows = [(f["name"], f["url"]) for f in C.DIRECT_FEEDS] + [(f["name"], f["url"]) for f in app.extra]
                    body = ('<?xml version="1.0" encoding="UTF-8"?><opml version="2.0"><head><title>My News</title></head><body>'
                            + "".join("<outline type=\"rss\" text=%s xmlUrl=%s/>" % (quoteattr(n), quoteattr(x)) for n, x in rows)
                            + "</body></opml>")
                    return self._send(200, body, "text/x-opml; charset=utf-8", {"Content-Disposition": 'attachment; filename="mynews.opml"'})
                if u.path == "/api/export":
                    return self._export(q)
                return self._send(404, {"error": "not found"})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": str(e)})

        def _export(self, q):
            hours = float(q.get("hours", 24))
            fmt = q.get("fmt", "md")
            items = store.export_since(hours)
            if fmt == "json":
                return self._send(200, items, extra={"Content-Disposition": 'attachment; filename="mynews.json"'})
            if fmt == "csv":
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(["published", "lang", "category", "source", "domain", "title", "title_ar", "url", "urgency"])
                for it in items:
                    w.writerow([time.strftime("%Y-%m-%d %H:%M", time.gmtime(it["published"])), it["lang"], it["category"],
                                it["source"], it["domain"], it["title"], it.get("title_ar") or "", it["url"], it["urgency"]])
                return self._send(200, "﻿" + buf.getvalue(), "text/csv; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="mynews.csv"'})
            st = store.stories({"hours": hours}, limit=200, sort="sources")
            lines = ["# موجز أخباري — آخر %g ساعة" % hours, "", "عدد القصص: %d" % st["total"], ""]
            byc = {}
            for s in st["stories"]:
                byc.setdefault(s["category"], []).append(s)
            for cid, lst in byc.items():
                lines.append("## " + CAT_NAMES.get(cid, cid))
                for s in lst:
                    flag = "🔴 " if s["urgency"] >= 6 else ""
                    lines.append("- %s**%s** — %s (%d مصدر)" % (flag, s["title"], s["source_ar"], s["n_domains"]))
                    lines.append("  %s" % s["url"])
                lines.append("")
            return self._send(200, "\n".join(lines), "text/markdown; charset=utf-8",
                              {"Content-Disposition": 'attachment; filename="mynews_brief.md"'})

        def do_POST(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if not self._auth(q) or not self._write_ok():
                return self._send(403, {"error": "forbidden"})
            b = self._body()
            try:
                if u.path == "/api/digest/make":
                    did = app.digester.make() if app.digester else None
                    return self._send(200, {"ok": bool(did), "id": did})
                if u.path == "/api/refresh":
                    app.refresh(q.get("mode", "full"))
                    return self._send(200, {"ok": True})
                if u.path == "/api/ingest":
                    return self._send(200, app.ingest(b))
                if u.path in ("/api/shutdown", "/api/lan") and not self._is_loop():
                    return self._send(403, {"error": "هذا الأمر من الحاسوب نفسه فقط"})
                if u.path == "/api/lan":
                    st_ = C.load_settings()
                    st_["lan"] = bool(b.get("enable"))
                    os.makedirs(C.DATA_DIR, exist_ok=True)
                    with open(C.SETTINGS_PATH, "w", encoding="utf-8") as f:
                        json.dump(st_, f)
                    get_key()
                    self._send(200, {"ok": True, "restarting": True}, extra={"Connection": "close"})
                    self.close_connection = True
                    env = dict(os.environ, RADAR_WAIT="1")
                    env.pop("RADAR_HOST", None)
                    kw = {"creationflags": 0x00000008 | 0x00000200} if os.name == "nt" else {"start_new_session": True}
                    subprocess.Popen([sys.executable, "-m", "radar", "--no-browser"], cwd=os.path.dirname(C.BASE_DIR), env=env,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
                    app.stop.set()
                    app.wake.set()
                    threading.Timer(0.8, lambda: os._exit(0)).start()
                    return
                if u.path == "/api/shutdown":
                    self._send(200, {"ok": True}, extra={"Connection": "close"})
                    self.close_connection = True
                    app.stop.set()
                    app.wake.set()
                    threading.Timer(0.8, lambda: os._exit(0)).start()
                    return
                if u.path == "/api/tracked":
                    lst = json.loads(store.meta_get("tracked", "[]"))
                    url = (b.get("url") or "").strip()
                    if not url.startswith("http"):
                        return self._send(400, {"error": "رابط غير صالح"})
                    h = P.domain_of(url)
                    kind = "fb" if "facebook.com" in h or "fb.com" in h else ("x" if h in ("x.com", "twitter.com") else "web")
                    if not any(t["url"] == url for t in lst):
                        lst.append({"url": url, "name": (b.get("name") or url)[:80], "kind": kind, "last": 0})
                    store.meta_set("tracked", json.dumps(lst, ensure_ascii=False))
                    return self._send(200, {"tracked": lst})
                if u.path == "/api/tracked/visit":
                    lst = json.loads(store.meta_get("tracked", "[]"))
                    for t in lst:
                        if t["url"] == b.get("url"):
                            t["last"] = int(time.time())
                    store.meta_set("tracked", json.dumps(lst, ensure_ascii=False))
                    return self._send(200, {"tracked": lst})
                if u.path == "/api/watches":
                    store.add_watch(b.get("term", ""))
                    return self._send(200, {"watches": store.watches()})
                if u.path == "/api/maintain":
                    if app.maintainer:
                        app.maintainer.trigger()
                    return self._send(200, {"ok": True})
                if u.path == "/api/rules":
                    kind, val = b.get("kind"), (b.get("value") or "").strip()[:120]
                    if kind not in ("mute_word", "mute_source", "pin_source") or not val:
                        return self._send(400, {"error": "قاعدة غير صالحة"})
                    rs = store.rules()
                    if not any(r["kind"] == kind and r["value"] == val for r in rs):
                        rs.append({"kind": kind, "value": val})
                    store.meta_set("rules", json.dumps(rs, ensure_ascii=False))
                    return self._send(200, {"rules": rs})
                if u.path == "/api/saved":
                    qv = (b.get("q") or "").strip()[:150]
                    sv = store.saved()
                    if qv and qv not in sv:
                        sv.append(qv)
                    store.meta_set("saved", json.dumps(sv[-30:], ensure_ascii=False))
                    return self._send(200, {"saved": store.saved()})
                if u.path == "/api/opml":
                    import xml.etree.ElementTree as ET
                    try:
                        root = ET.fromstring((b.get("xml") or "").encode("utf-8"))
                    except Exception:
                        return self._send(400, {"error": "ملف OPML غير صالح"})
                    have = {f["url"] for f in app.extra} | {f["url"] for f in C.DIRECT_FEEDS}
                    added = 0
                    for o in root.iter("outline"):
                        x = (o.get("xmlUrl") or "").strip()
                        if x.startswith("http") and x not in have and added < 300:
                            have.add(x)
                            app.extra.append({"name": (o.get("text") or o.get("title") or x)[:80], "url": x, "lang": "und",
                                              "type": "news", "all": False, "autodiscover": False})
                            added += 1
                    save_extra_feeds(app.extra)
                    app.collector.extra_feeds = app.extra
                    if added:
                        app.refresh("fast")
                    return self._send(200, {"ok": True, "added": added})
                if u.path == "/api/feeds":
                    url = (b.get("url") or "").strip()
                    if not url.startswith("http"):
                        return self._send(400, {"error": "رابط غير صالح"})
                    if any(h in url for h in ("facebook.com", "fb.com", "twitter.com", "x.com/", "instagram.com")):
                        return self._send(400, {"error": "فيسبوك وإكس لا يوفّران RSS — أضف المنشور يدوياً من الآيفون أو أضف موقع الصفحة"})
                    f = {"name": (b.get("name") or url)[:80], "url": url, "lang": b.get("lang") or "und",
                         "type": b.get("type") or "news", "all": bool(b.get("all", False)), "autodiscover": bool(b.get("autodiscover", False))}
                    app.extra.append(f)
                    save_extra_feeds(app.extra)
                    app.collector.extra_feeds = app.extra
                    app.refresh("fast")
                    return self._send(200, {"ok": True, "mine": app.extra})
                return self._send(404, {"error": "not found"})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": str(e)})

        def do_DELETE(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if not self._auth(q) or not self._write_ok():
                return self._send(403, {"error": "forbidden"})
            if u.path == "/api/watches":
                store.del_watch(q.get("term", ""))
                return self._send(200, {"watches": store.watches()})
            if u.path == "/api/tracked":
                lst = [t for t in json.loads(store.meta_get("tracked", "[]")) if t["url"] != q.get("url")]
                store.meta_set("tracked", json.dumps(lst, ensure_ascii=False))
                return self._send(200, {"tracked": lst})
            if u.path == "/api/rules":
                rs = [r for r in store.rules() if not (r["kind"] == q.get("kind") and r["value"] == q.get("value"))]
                store.meta_set("rules", json.dumps(rs, ensure_ascii=False))
                return self._send(200, {"rules": rs})
            if u.path == "/api/saved":
                sv = [x for x in store.saved() if x != q.get("q")]
                store.meta_set("saved", json.dumps(sv, ensure_ascii=False))
                return self._send(200, {"saved": sv})
            if u.path == "/api/feeds":
                app.extra[:] = [f for f in app.extra if f["url"] != q.get("url")]
                save_extra_feeds(app.extra)
                return self._send(200, {"mine": app.extra})
            return self._send(404, {"error": "not found"})

    return H


class _Srv(ThreadingHTTPServer):
    allow_reuse_address = False       # على ويندوز يسمح SO_REUSEADDR بنسختين على نفس المنفذ
    daemon_threads = True
    request_queue_size = 128          # الافتراضي 5 فقط فيرفض الاتصال عند الانشغال


def port_free(host, port):
    try:
        t = _Srv((host, port), BaseHTTPRequestHandler)
        t.server_close()
        return True
    except OSError:
        return False


def serve(app=None, host=None, port=None):
    host, port = host or C.HOST, port or C.PORT
    if not port_free(host, port):
        print("\n  %s يعمل بالفعل على المنفذ %d. افتح http://localhost:%d\n" % (C.APP_NAME, port, port))
        return
    app = app or App()
    srv = _Srv((host, port), make_handler(app))
    app.server = srv
    print("\n  %s  —  http://%s:%d\n  (Ctrl+C للإيقاف)\n" % (C.APP_NAME, host if host != "0.0.0.0" else "localhost", port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop.set()
        app.wake.set()
        srv.server_close()

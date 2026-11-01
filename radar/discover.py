# -*- coding: utf-8 -*-
"""المُكتشِف: كل ساعة يفحص المواقع التي ظهر منها أخبار ليبية ولم تكن في مصادرنا، ويضيف لها RSS تلقائياً."""
import json
import time
import threading
from urllib.parse import urlparse

from . import config as C
from . import collectors as K

SKIP = ("google.", "bing.com", "msn.com", "yahoo.", "facebook.com", "fb.com", "x.com", "twitter.com", "t.co", "youtube.com",
        "youtu.be", "reddit.com", "wikipedia.org", "linkedin.com", "instagram.com", "flipboard.com", "newsbreak.com",
        "dailyhunt.com", "apple.news", "smartnews.com", "ground.news", "allsides.com", "tiktok.com", "telegram.", "t.me",
        "whatsapp.com", "pinterest.", "tumblr.com", "medium.com", "blogspot.", "wordpress.com")
MAX_AUTO = 400
EVERY = 1800


def host(u):
    try:
        h = urlparse(u if "//" in u else "//" + u).netloc.lower()
    except Exception:
        return ""
    return h[4:] if h.startswith("www.") else h


class Discoverer(threading.Thread):
    def __init__(self, app, first_delay=45):
        super().__init__(daemon=True)
        self.app = app
        self.first_delay = first_delay
        self.stats = {"runs": 0, "last_run": None, "last_found": [], "checked": 0, "auto_total": 0, "running": False, "next_run": None}

    def run(self):
        app = self.app
        self.stats["next_run"] = int(time.time()) + self.first_delay
        if app.stop.wait(self.first_delay):
            return
        while not app.stop.is_set():
            try:
                self.run_once()
            except Exception as e:
                K.log("المكتشف: خطأ %s" % str(e)[:150])
            self.stats["next_run"] = int(time.time()) + EVERY
            if app.stop.wait(EVERY):
                return

    def known_hosts(self):
        k = set()
        for f in list(C.DIRECT_FEEDS) + list(C.AUTODISCOVER_PAGES) + list(self.app.extra):
            k.add(host(f.get("url", "")))
        for d in list(C.LIBYAN_SITES) + list(C.MIXED_SITES):
            k.add(host(d))
        return k

    def candidates(self):
        store = self.app.store
        cutoff = int(time.time()) - 7 * 86400
        with store.lock:
            rows = store.db.execute("SELECT domain, source, lang, extra FROM items WHERE rel>=3 AND fetched>=? LIMIT 8000", (cutoff,)).fetchall()
        cnt, meta = {}, {}
        for r in rows:
            d = ""
            if r["extra"]:
                try:
                    d = host(json.loads(r["extra"]).get("src_url", ""))
                except Exception:
                    d = ""
            if not d:
                d = host(r["domain"] or "")
            if not d or "." not in d or any(s in d for s in SKIP):
                continue
            cnt[d] = cnt.get(d, 0) + 1
            meta.setdefault(d, (r["source"], r["lang"]))
        return sorted(((n, d) for d, n in cnt.items() if n >= 2), reverse=True), meta

    def feed_hosts(self):
        return {host(f.get("url", "")) for f in list(C.DIRECT_FEEDS) + list(C.AUTODISCOVER_PAGES) + list(self.app.extra)} | \
               {f.get("site") for f in self.app.extra if f.get("site")}

    def check_candidates(self, limit=40):
        """مواقع ليبية معروفة: نبحث عن RSS لها؛ وإن لم يوجد نضيفها لاستعلامات جوجل site:."""
        from concurrent.futures import ThreadPoolExecutor
        app, store = self.app, self.app.store
        done = json.loads(store.meta_get("cand_done", "{}"))
        if store.meta_get("cand_ver") != "2":      # الإصدار 2: يجرّب واجهة ووردبريس أيضاً، فنعيد فحص ما فشل سابقاً
            done = {k: v for k, v in done.items() if v.get("ok")}
            store.meta_set("cand_ver", "2")
        now = int(time.time())
        have = self.feed_hosts()
        todo = []
        for dom, name, lang, allf in getattr(C, "CANDIDATE_SITES", []):
            h = host(dom)
            if ("/" not in dom and h in have) or done.get(dom, {}).get("ok") or now - done.get(dom, {}).get("t", 0) < 7 * 86400:
                continue
            todo.append((dom, name, lang, allf))
        todo = todo[:limit]
        if not todo:
            return 0

        def probe(c):
            dom, name, lang, allf = c
            url = "https://" + dom + ("" if "/" in dom else "/")
            try:
                feed, _wp = K.probe_site(url)
                return c, feed
            except Exception:
                return c, None

        added = 0
        sites = json.loads(store.meta_get("extra_sites", "[]"))
        with ThreadPoolExecutor(max_workers=8) as ex:
            for c, feed in ex.map(probe, todo):
                dom, name, lang, allf = c
                if feed:
                    app.extra.append({"name": name, "url": feed, "lang": lang, "type": "official" if ".gov." in dom or "un.org" in dom else "news",
                                      "all": bool(allf), "auto": True, "added": now, "site": host(dom)})
                    done[dom] = {"ok": True, "t": now}
                    added += 1
                else:
                    done[dom] = {"ok": False, "t": now}
                    d0 = dom.split("/")[0]
                    if d0 not in sites and d0 not in C.LIBYAN_SITES:
                        sites.append(d0)
        store.meta_set("cand_done", json.dumps(done))
        store.meta_set("extra_sites", json.dumps(sites))
        app.collector.extra_sites = sites
        app.collector.extra_feeds = app.extra
        K.log("المكتشف: مرشّحون %d فُحصوا، RSS وُجد لـ%d" % (len(todo), added))
        return added

    def run_once(self, limit=30):
        app, store = self.app, self.app.store
        st = self.stats
        st["running"] = True
        try:
            try:
                st["cand_added"] = self.check_candidates()
            except Exception as e:
                K.log("المكتشف: خطأ المرشّحين %s" % str(e)[:100])
            known = self.known_hosts()
            failed = json.loads(store.meta_get("disc_failed", "{}"))
            now = int(time.time())
            cands, meta = self.candidates()
            todo = [d for n, d in cands if d not in known and now - failed.get(d, 0) > 7 * 86400][:limit]
            auto = [f for f in app.extra if f.get("auto")]
            found = []
            room = max(0, MAX_AUTO - len(auto))
            todo = todo[:max(room, 0) + 10]

            def probe(d):
                try:
                    return d, K.probe_site("https://" + d + "/")[0]
                except Exception:
                    return d, None
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=8) as ex:
                for d, feed in ex.map(probe, todo):
                    st["checked"] += 1
                    if feed and len(auto) + len(found) < MAX_AUTO:
                        name, lang = meta.get(d, (d, "und"))
                        found.append({"name": (name or d)[:60], "url": feed, "lang": lang or "und", "type": "news",
                                      "all": False, "auto": True, "added": now, "site": d})
                    elif not feed:
                        failed[d] = now
            if found:
                app.extra.extend(found)
                app.collector.extra_feeds = app.extra
            # تقليم المصادر التلقائية الميتة
            dead = set()
            with store.lock:
                for f in app.extra:
                    if f.get("auto"):
                        h = store.db.execute("SELECT fails,total_new,runs,last_yield FROM health WHERE name=?", ("RSS/" + f["name"],)).fetchone()
                        if not h:
                            continue
                        age = now - (f.get("added") or now)
                        if h["runs"] >= 8 and h["fails"] >= h["runs"] - 1 and not h["total_new"]:
                            dead.add(f["url"])      # لم يعمل قط
                        elif h["runs"] >= 60 and not h["total_new"] and age > 2 * 86400:
                            dead.add(f["url"])      # يعمل لكنه لم ينتج خبراً ليبياً واحداً
                        elif h["runs"] >= 60 and h["total_new"] and (h["last_yield"] or 0) and now - h["last_yield"] > 21 * 86400:
                            dead.add(f["url"])      # كان يُنتج ثم صمت ثلاثة أسابيع
            if dead:
                app.extra[:] = [f for f in app.extra if f["url"] not in dead]
            if found or dead or st.get("cand_added"):
                from .server import save_extra_feeds
                save_extra_feeds(app.extra)
            store.meta_set("disc_failed", json.dumps(failed))
            st.update(runs=st["runs"] + 1, last_run=now, last_found=[f["name"] for f in found],
                      auto_total=len([f for f in app.extra if f.get("auto")]))
            K.log("المكتشف: فُحص %d موقعاً، أُضيف %d مصدراً، حُذف %d" % (len(todo), len(found), len(dead)))
            if found or st.get("cand_added"):
                app.refresh("fast")
        finally:
            st["running"] = False

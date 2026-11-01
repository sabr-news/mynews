# -*- coding: utf-8 -*-
"""الموجز الساعي: أهم 10 أخبار/أحداث عند رأس كل ساعة."""
import time
import threading
from datetime import datetime

from . import config as C
from . import collectors as K

N_ITEMS = 10


def score(s, now):
    age_h = max(0.0, (now - (s.get("last_known") or s["last_pub"])) / 3600.0)
    sc = s["urgency"] * 3 + min(s["n_domains"], 12) * 2.5 + min(s["n_items"], 10) * 0.5
    sc += {"confirmed": 4, "official": 4, "likely": 2}.get(s["trust"], 0)
    sc -= age_h * 1.2
    if s.get("stype") == "social":
        sc -= 3
    if not s.get("last_known"):
        sc -= 2
    return sc


def build(store, hours=1.0):
    """يرجع (items, window_h). يوسّع النافذة إن قلّت الأخبار."""
    now = int(time.time())
    for w in (hours, 3, 6, 12, 24):
        st = store.stories({"hours": w, "known": "1", "min_rel": 2}, limit=200, sort="latest")["stories"]
        if len(st) >= N_ITEMS or w == 24:
            break
    st.sort(key=lambda s: score(s, now), reverse=True)
    top = st[:N_ITEMS]
    # ترجمة فورية لعناوين لم تُترجم بعد حتى يخرج الموجز بالعربية
    from .translate import to_arabic
    items = []
    for s in top:
        title = s["title"]
        if s["pending_translation"]:
            try:
                t = to_arabic(s["title_orig"])
                if t:
                    title = t
            except Exception:
                pass
        items.append({"title": title, "source_ar": s["source_ar"], "url": s["url"], "category": s["category"],
                      "n_domains": s["n_domains"], "urgency": s["urgency"],
                      "published": s.get("last_known") or s["last_pub"],
                      "summary": (s["summary"] or "")[:200] if s["lang"] == "ar" else ""})
    return items, w


class Digester(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.stats = {"last": None, "next": None}

    def make(self, label=None):
        items, w = build(self.app.store)
        if not items:
            return None
        now = datetime.now()
        label = label or now.strftime("%H:00")
        did = self.app.store.add_digest(label, w, items)
        self.stats["last"] = int(time.time())
        K.log("الموجز: صدر موجز %s (%d خبراً، نافذة %gس)" % (label, len(items), w))
        return did

    def run(self):
        app = self.app
        if app.stop.wait(150):
            return
        try:
            if not app.store.digests(1):
                self.make("موجز أول")
        except Exception as e:
            K.log("الموجز: خطأ %s" % e)
        while not app.stop.is_set():
            now = time.time()
            nxt = (int(now // 3600) + 1) * 3600
            self.stats["next"] = nxt
            if app.stop.wait(max(1, nxt - now - 40)):   # قبل رأس الساعة بـ40 ثانية: حدّث المصادر
                return
            try:
                app.refresh("fast")
                time.sleep(25)
                t0 = time.time()
                while app.collector.status.get("running") and time.time() - t0 < 60:
                    time.sleep(2)
                left = nxt - time.time()
                if left > 0:
                    time.sleep(left)
                self.make()
            except Exception as e:
                K.log("الموجز: خطأ %s" % str(e)[:120])
            app.stop.wait(5)

# -*- coding: utf-8 -*-
"""تصدير لقطة JSON ثابتة من قاعدة البيانات لتعمل الواجهة بلا خادم (GitHub Pages)."""
import os
import json
import time

from . import config as C
from .digest import score

MAX_STORIES = 2500
HOURS = 168


def _slim(s, now):
    items = []
    for it in s["items"][:6]:
        items.append({"title": it["title"], "url": it["url"], "source": it["source"], "source_ar": it["source_ar"],
                      "domain": it["domain"], "lang": it["lang"], "published": it["published"], "pub_known": it["pub_known"],
                      "stype": it["stype"], "auth": it["auth"], "paywall": it["paywall"]})
    d = dict(s)
    d["items"] = items
    d["summary"] = (s.get("summary") or "")[:240]
    d["score"] = round(score(s, now), 2)
    d.pop("matched", None)
    return d


def export(store, extra, out_dir):
    from .server import CAT_NAMES
    os.makedirs(out_dir, exist_ok=True)
    now = int(time.time())
    res = store.stories({"min_rel": 2, "hours": HOURS, "no_rules": 1}, limit=MAX_STORIES, offset=0, sort="latest")
    stories = [_slim(s, now) for s in res["stories"]]
    w = lambda name, obj: json.dump(obj, open(os.path.join(out_dir, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    w("stories.json", {"generated": now, "total": res["total"], "stories": stories})
    w("stats.json", store.stats())
    w("meta.json", {"categories": CAT_NAMES, "name": C.APP_NAME, "name_en": C.APP_NAME_EN, "version": C.APP_VERSION + "-web",
                    "langs": [l[0] for l in C.LANGS], "watches": [], "generated": now})
    w("health.json", store.health())
    w("feeds.json", {"builtin": C.DIRECT_FEEDS, "pages": C.AUTODISCOVER_PAGES, "telegram": C.TELEGRAM_CHANNELS, "mine": extra})

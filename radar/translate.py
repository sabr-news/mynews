# -*- coding: utf-8 -*-
"""ترجمة مجانية للعناوين وأسماء المصادر إلى العربية، مع تخزين دائم حتى لا تتكرر.
تستخدم نقطة جوجل المجانية غير الرسمية (قد تتأخر أو تتوقف)، ثم MyMemory كاحتياط. لا حساب ولا مفتاح ولا دفع."""
import json
import time
import threading
import urllib.parse

from . import names as N
from .collectors import http_get, decode, log

LANG_FOR_MM = {"zh": "zh-CN", "zh-CN": "zh-CN", "he": "he", "uk": "uk", "ja": "ja", "ko": "ko"}


def parse_gtx(text):
    d = json.loads(text)
    segs = d[0] or []
    out = "".join(s[0] for s in segs if s and s[0])
    return out.strip()


_GATE = threading.Lock()
_STATE = {"last": 0.0, "cool": 0.0, "n": 0}
PRIORITY = [0]          # >0: قارئ المقالات يترجم الآن، فيتوقف المترجم الخلفي


def gtx(text, sl="auto", tl="ar", prio=False):
    url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=%s&tl=%s&dt=t&q=%s" % (sl, tl, urllib.parse.quote(text, safe=""))
    with _GATE:
        now = time.time()
        if now < _STATE["cool"]:
            if not prio:
                raise RuntimeError("HTTP 429 (تهدئة)")
            time.sleep(min(35, _STATE["cool"] - now))
        elif not prio and PRIORITY[0]:
            raise RuntimeError("مشغول بالقارئ")
        wait = 1.1 - (time.time() - _STATE["last"])
        if wait > 0:
            time.sleep(wait)
        try:
            raw, cs = http_get(url, retries=0, timeout=15)
        except Exception as e:
            if "429" in str(e):
                _STATE["n"] = min(_STATE["n"] + 1, 6)
                _STATE["cool"] = time.time() + min(1200, 45 * 2 ** (_STATE["n"] - 1))
            raise
        finally:
            _STATE["last"] = time.time()
    _STATE["n"] = 0
    return parse_gtx(decode(raw, cs))


def mymemory(text, sl):
    if not sl or sl in ("und", "ar"):
        return None
    sl = LANG_FOR_MM.get(sl, sl)
    url = "https://api.mymemory.translated.net/get?q=%s&langpair=%s|ar" % (urllib.parse.quote(text, safe=""), sl)
    raw, cs = http_get(url, retries=0, timeout=15)
    d = json.loads(decode(raw, cs))
    t = (d.get("responseData") or {}).get("translatedText") or ""
    if d.get("responseStatus") not in (200, "200") or "MYMEMORY WARNING" in t.upper():
        return None
    return t.strip() or None


def to_arabic(text, lang="auto"):
    text = (text or "").strip()
    if not text:
        return None
    try:
        t = gtx(text[:480], "auto")
        if t and t != text:
            return t
    except Exception as e:
        if "تهدئة" not in str(e) and "مشغول" not in str(e):
            log("  ترجمة جوجل فشلت: %s" % str(e)[:80])
    try:
        return mymemory(text[:450], lang)
    except Exception:
        return None


class Translator(threading.Thread):
    def __init__(self, store, stop_event):
        super().__init__(daemon=True)
        self.store = store
        self.stop_event = stop_event
        self.failed = {}
        self.name_failed = {}
        self.stats = {"translated": 0, "names": 0, "errors": 0}
        self._reset = time.time()

    def run(self):
        backoff = 0
        while not self.stop_event.is_set():
            did = 0
            try:
                if PRIORITY[0]:
                    self.stop_event.wait(3)
                    continue
                if time.time() - self._reset > 3600:   # أعد المحاولة بما فشل سابقاً
                    self.failed.clear()
                    self.name_failed.clear()
                    self._reset = time.time()
                cooling = time.time() < _STATE["cool"]   # جوجل في تهدئة: نكمل ببطء عبر MyMemory بدل التوقف
                for it in self.store.pending_translations(3 if cooling else 10, exclude={k for k, v in self.failed.items() if v >= 3}):
                    t = to_arabic(it["title"], it["lang"])
                    if t and N.has_arabic(t):
                        self.store.set_title_ar(it["id"], t)
                        self.stats["translated"] += 1
                        did += 1
                        backoff = 0
                    else:
                        self.failed[it["id"]] = self.failed.get(it["id"], 0) + 1
                        self.stats["errors"] += 1
                        backoff = min(backoff + 1, 6)
                    time.sleep((2.0 if cooling else 0.3) + 0.5 * backoff)
                    if self.stop_event.is_set():
                        return
                    if PRIORITY[0]:
                        break
                for src in self.store.pending_names(8, exclude={k for k, v in self.name_failed.items() if v >= 2}):
                    t = to_arabic(src)
                    if t and N.has_arabic(t):
                        self.store.set_name(src, t)
                        self.stats["names"] += 1
                        did += 1
                    else:
                        self.name_failed[src] = self.name_failed.get(src, 0) + 1
                    time.sleep(0.3)
            except Exception as e:
                log("مترجم: خطأ %s" % str(e)[:120])
                time.sleep(10)
            self.stop_event.wait(2 if did else 8)

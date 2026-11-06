# -*- coding: utf-8 -*-
"""الجامعات: كل جامع يرجع قائمة سجلات خام، ويُسجَّل نجاحه/فشله في لوحة الصحة."""
import re
import json
import time
import ssl
import gzip
import zlib
import html
import threading
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config as C
from . import process as P

_CTX = ssl.create_default_context()


_LOGLOCK = threading.Lock()


def log(msg):
    """سطر واحد لكل رسالة، مع قفل حتى لا تتداخل أسطر الخيوط المتعددة."""
    try:
        import os
        line = time.strftime("%H:%M:%S ") + str(msg).replace("\r", " ").replace("\n", " ⏎ ") + "\n"
        with _LOGLOCK:
            os.makedirs(C.DATA_DIR, exist_ok=True)
            lp = os.path.join(C.DATA_DIR, "radar.log")
            try:
                if os.path.getsize(lp) > 4 * 1024 * 1024:     # تدوير السجل
                    os.replace(lp, lp + ".1")
            except OSError:
                pass
            with open(lp, "ab") as f:
                f.write(line.encode("utf-8"))
    except Exception:
        pass


# ---------------------------------------------------------------- HTTP
_GG = {"lock": threading.Lock(), "last": 0.0, "block": 0.0}


def _google_gate(url):
    """جوجل نيوز يحدّ الطلبات: نسلسل الطلبات بفارق 0.45 ث ونهدّئ دقيقة بعد أي 429."""
    if "news.google.com/rss" not in url:
        return
    with _GG["lock"]:
        now = time.time()
        if now < _GG["block"]:
            time.sleep(min(70, _GG["block"] - now))
        wait = 0.45 - (time.time() - _GG["last"])
        if wait > 0:
            time.sleep(wait)
        _GG["last"] = time.time()


def http_get(url, timeout=None, headers=None, retries=2, cond=None, out=None):
    h = {"User-Agent": C.USER_AGENT, "Accept": "*/*", "Accept-Encoding": "gzip, deflate",
         "Accept-Language": "en,ar;q=0.8"}
    if headers:
        h.update(headers)
    if cond:
        if cond.get("etag"):
            h["If-None-Match"] = cond["etag"]
        if cond.get("lm"):
            h["If-Modified-Since"] = cond["lm"]
    last = None
    url = urllib.parse.quote(url, safe=":/?&=%#+@,;~!$'()*[]")
    for attempt in range(retries + 1):
        _google_gate(url)
        try:
            req = urllib.request.Request(url, headers=h)
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=timeout or C.HTTP_TIMEOUT, context=_CTX) as r:
                chunks, size = [], 0
                while True:
                    ch = r.read(65536)
                    if not ch:
                        break
                    chunks.append(ch)
                    size += len(ch)
                    if size > 8 * 1024 * 1024:
                        break
                    if time.time() - t0 > 45:
                        raise RuntimeError("بطيء جداً (تجاوز 45 ثانية)")
                raw = b"".join(chunks)
                enc = (r.headers.get("Content-Encoding") or "").lower()
                if enc == "gzip":
                    raw = gzip.decompress(raw)
                elif enc == "deflate":
                    raw = zlib.decompress(raw)
                ctype = r.headers.get("Content-Type", "")
                m = re.search(r"charset=([\w-]+)", ctype)
                if out is not None:
                    out["etag"] = r.headers.get("ETag")
                    out["lm"] = r.headers.get("Last-Modified")
                return raw, (m.group(1) if m else None)
        except urllib.error.HTTPError as e:
            if e.code == 304 and cond:
                return None, None
            last = "HTTP %s" % e.code
            if e.code == 403 and not (headers or {}).get("User-Agent"):
                for ua in C.ALT_UAS:   # بعض المواقع تحجب المتصفحات الآلية وتسمح لقارئات RSS
                    try:
                        return http_get(url, timeout=timeout, headers={"User-Agent": ua}, retries=0, cond=cond, out=out)
                    except Exception:
                        pass
            if e.code in (404, 403, 401, 410):
                break
            if e.code == 429:
                if "news.google.com" in url:
                    _GG["block"] = time.time() + 60 + attempt * 30
                else:
                    time.sleep(6 + attempt * 6)
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, str(e)[:120])
        time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(last or "فشل غير معروف")


def decode(raw, charset=None):
    for enc in ([charset] if charset else []) + ["utf-8", "windows-1256", "latin-1"]:
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


# ---------------------------------------------------------------- التواريخ
def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        return int(parsedate_to_datetime(s).timestamp())
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S", "%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = datetime.strptime(s.replace("Z", "+0000") if "%z" in fmt else s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return int(d.timestamp())
        except Exception:
            continue
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


# ---------------------------------------------------------------- RSS / Atom
def _strip_ns(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_feed(text):
    """يرجع قائمة dict(title,url,summary,published). يدعم RSS 2.0 وAtom وRDF."""
    text = text.lstrip("﻿ \t\r\n")
    # إزالة الحروف غير الصالحة في XML
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError:
        text = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError:
            # ملف مقطوع أو معطوب: نستخرج العناصر المكتملة فقط بدل رفض الخلاصة كلها
            good = []
            for m in re.finditer(r"<(item|entry)\b.*?</\1>", text, re.S):
                try:
                    ET.fromstring(m.group(0).encode("utf-8"))
                    good.append(m.group(0))
                except ET.ParseError:
                    continue
            if not good:
                raise
            root = ET.fromstring(("<rss><channel>" + "".join(good) + "</channel></rss>").encode("utf-8"))
    out = []
    for el in root.iter():
        t = _strip_ns(el.tag)
        if t not in ("item", "entry"):
            continue
        rec = {"title": "", "url": "", "summary": "", "published": None}
        for ch in el:
            ct = _strip_ns(ch.tag)
            val = (ch.text or "").strip()
            if ct == "title":
                rec["title"] = P.strip_html(html.unescape(val))
            elif ct == "link":
                href = ch.attrib.get("href")
                if href and (ch.attrib.get("rel") in (None, "alternate")):
                    rec["url"] = rec["url"] or href.strip()
                elif val and not rec["url"]:
                    rec["url"] = val
            elif ct in ("description", "summary", "content", "encoded") and not rec["summary"]:
                rec["summary"] = P.strip_html(html.unescape(val))[:1200]
            elif ct in ("pubDate", "published", "updated", "date", "issued") and not rec["published"]:
                rec["published"] = parse_date(val)
            elif ct == "guid" and not rec["url"] and val.startswith("http"):
                rec["url"] = val
            elif ct == "source" and ch.attrib.get("url"):
                rec["src_url"] = ch.attrib["url"]
                rec["src_name"] = val
            elif ct == "Source" and val and not rec.get("source_name"):   # بينغ: <News:Source>
                rec["source_name"] = val
        u = rec["url"]
        if "bing.com/news/apiclick" in u:                                  # الرابط الحقيقي للناشر داخل رابط التحويل
            m = re.search(r"[?&]url=([^&]+)", u)
            if m:
                rec["url"] = urllib.parse.unquote(m.group(1))
        if rec["title"]:
            out.append(rec)
    return out


def autodiscover_feed(page_url):
    raw, cs = http_get(page_url)
    text = decode(raw, cs)
    for m in re.finditer(r"<link[^>]+>", text, re.I):
        tag = m.group(0)
        if re.search(r"type=[\"']application/(rss|atom)\+xml", tag, re.I):
            h = re.search(r"href=[\"']([^\"']+)", tag, re.I)
            if h:
                return urllib.parse.urljoin(page_url, html.unescape(h.group(1)))
    for guess in ("feed/", "feed", "rss", "rss.xml", "atom.xml", "index.xml"):
        try:
            u = urllib.parse.urljoin(page_url, guess)
            raw, cs = http_get(u, retries=0, timeout=10)
            if b"<rss" in raw[:2000] or b"<feed" in raw[:2000] or b"<rdf" in raw[:2000].lower():
                return u
        except Exception:
            continue
    return None


def parse_wp(text):
    """واجهة ووردبريس المفتوحة /wp-json/wp/v2/posts: تعمل حتى لو لا يوجد RSS."""
    data = json.loads(text)
    out = []
    if not isinstance(data, list):
        raise RuntimeError("ليست واجهة ووردبريس")
    for p in data:
        if not isinstance(p, dict) or not p.get("link"):
            continue
        t = p.get("title") or {}
        e = p.get("excerpt") or {}
        title = P.strip_html(html.unescape(t.get("rendered", "") if isinstance(t, dict) else str(t)))
        d = p.get("date_gmt") or p.get("date")
        pub = parse_date(d + "Z") if d and not str(d).endswith("Z") and "+" not in str(d) else parse_date(d or "")
        if title:
            out.append({"title": title, "url": p["link"], "published": pub,
                        "summary": P.strip_html(html.unescape(e.get("rendered", "") if isinstance(e, dict) else ""))[:1200]})
    return out


def probe_site(url):
    """يرجع (رابط المصدر، wp?) لأول وسيلة تعمل: RSS مكتشف، ثم واجهة ووردبريس."""
    try:
        feed = autodiscover_feed(url)
        if feed:
            raw, cs = http_get(feed, retries=0, timeout=15)
            if parse_feed(decode(raw, cs)):
                return feed, False
    except Exception:
        pass
    try:
        base = urllib.parse.urljoin(url, "/wp-json/wp/v2/posts?per_page=20&_fields=link,title,date_gmt,excerpt")
        raw, cs = http_get(base, retries=0, timeout=15)
        if parse_wp(decode(raw, cs)):
            return base, True
    except Exception:
        pass
    return None, False


# ---------------------------------------------------------------- Google News
def _gnews_url(q, hl, ceid, when="1d"):
    gl = ceid.split(":")[0]
    qq = q + (" when:%s" % when if when else "")
    return "https://news.google.com/rss/search?q=%s&hl=%s&gl=%s&ceid=%s" % (urllib.parse.quote(qq), hl, gl, urllib.parse.quote(ceid))


def google_news_jobs(mode="fast"):
    """قائمة مهام: (اسم_للصحة، رابط، لغة_تلميح، وصف).
    fast: أهم الاستعلامات لكل لغة (كل دورة) | full: كل الاستعلامات + إصدارات البلدان | deep: مثل full لكن آخر 7 أيام."""
    when = "7d" if mode == "deep" else ("1d" if mode == "full" else "6h")
    jobs = []
    for code, hl, ceid, _gd, queries in C.LANGS:
        for q in (queries if mode != "fast" else queries[:4]):
            jobs.append(("GoogleNews/%s" % code, _gnews_url(q, hl, ceid, when), code, q))
    if mode == "fast":
        return jobs
    # إصدارات إضافية للعربية والإنجليزية بأهم الاستعلامات
    for ed in C.AR_EDITIONS:
        for q in C.LANGS[0][4][:6]:
            jobs.append(("GoogleNews/ar-%s" % ed.split(":")[0], _gnews_url(q, "ar", ed, when), "ar", q))
    for ed in C.EN_EDITIONS:
        for q in C.LANGS[1][4][:5]:
            jobs.append(("GoogleNews/en-%s" % ed.split(":")[0], _gnews_url(q, "en", ed, when), "en", q))
    return jobs


def site_jobs(mode="fast", extra=()):
    when = "7d" if mode == "deep" else ("2d" if mode == "full" else "1d")
    jobs = []
    for dom in dict.fromkeys(list(C.LIBYAN_SITES) + list(extra)):
        lg = "ar" if dom.split(".")[-1] in ("ly", "tv", "net", "co") and "herald" not in dom and "review" not in dom and "update" not in dom and "observer" not in dom else "en"
        if dom in C.AR_COM_SITES:
            lg = "ar"
        jobs.append(("GoogleSite/%s" % dom, _gnews_url("site:" + dom, "ar" if lg == "ar" else "en", "LY:ar" if lg == "ar" else "US:en", when), lg, "site:" + dom, dom not in C.MIXED_SITES))
    return jobs


_PR_LANG = {"en": ("(Libya OR Libyan)", "en", "US:en"), "ar": ("ليبيا", "ar", "LY:ar"), "fr": ("(Libye OR libyen)", "fr", "FR:fr"),
            "it": ("(Libia OR libico)", "it", "IT:it"), "de": ("(Libyen OR libysch)", "de", "DE:de"), "es": ("(Libia OR libio)", "es", "ES:es"),
            "ru": ("Ливия", "ru", "RU:ru")}


def prestige_jobs(mode="lane"):
    """استعلام لكل مرجع دولي: ما نشره عن ليبيا (العنوان والرابط يكفيان ولو كان المقال مغلقاً)."""
    when = {"deep": "14d", "full": "5d"}.get(mode, "3d")
    jobs = []
    for dom, name, kind, lg in C.PRESTIGE:
        terms, hl, ceid = _PR_LANG.get(lg, _PR_LANG["en"])
        jobs.append(("Prestige/%s" % dom, _gnews_url("site:%s %s" % (dom, terms), hl, ceid, when), lg, "site:" + dom, dom))
    return jobs


def bing_news_jobs():
    jobs = []
    for code, hl, ceid, _gd, queries in C.LANGS[:8]:
        mkt = {"ar": "ar-XA", "en": "en-US", "fr": "fr-FR", "it": "it-IT", "es": "es-ES", "de": "de-DE", "tr": "tr-TR", "ru": "ru-RU"}.get(code)
        if not mkt:
            continue
        for q in queries[:3]:
            jobs.append(("BingNews/%s" % code, "https://www.bing.com/news/search?q=%s&format=RSS&mkt=%s" % (urllib.parse.quote(q), mkt), code, q))
    return jobs


def _gnews_split_source(rec):
    """عناوين جوجل تنتهي بـ « - اسم المصدر»؛ ننتزع المصدر ورابطه الأصلي إن وُجد."""
    title = rec["title"]
    src = rec.get("src_name") or ""
    if not src and " - " in title:
        title, src = title.rsplit(" - ", 1)
    elif src and title.endswith(" - " + src):
        title = title[: -(len(src) + 3)]
    rec["title"] = title.strip()
    rec["source_name"] = src.strip()
    # الملخص في جوجل غالباً تكرار للعنوان + المصدر؛ نتجاهله إذا كان مطابقاً
    s = rec.get("summary") or ""
    if s.startswith(title[:30]):
        rec["summary"] = ""
    return rec


# ---------------------------------------------------------------- GDELT
def gdelt_jobs():
    jobs = []
    base = "https://api.gdeltproject.org/api/v2/doc/doc?mode=artlist&format=json&maxrecords=250&sort=datedesc&timespan=%s&query=%s"
    spans = "24h"
    jobs.append(("GDELT/all", base % (spans, urllib.parse.quote('(libya OR libyan OR ليبيا OR libye OR libia OR ливия OR libië OR libyen)')), "und", "all"))
    jobs.append(("GDELT/sourcecountry-LY", base % (spans, urllib.parse.quote("sourcecountry:LY")), "und", "LY"))
    for code, hl, ceid, gd, queries in C.LANGS:
        if True:        # GDELT يحجب غالباً: نكتفي بالاستعلامين الشاملين أعلاه
            continue
        q = "(%s) sourcelang:%s" % (" OR ".join('"%s"' % x if " " in x else x for x in queries[:6]), gd)
        jobs.append(("GDELT/%s" % code, base % (spans, urllib.parse.quote(q)), code, ",".join(queries[:3])))
    return jobs


def parse_gdelt(text):
    try:
        data = json.loads(text)
    except Exception:
        # GDELT يرجع أحياناً رسالة نصية عند تجاوز الحد
        raise RuntimeError("GDELT: " + text[:100].replace("\n", " "))
    out = []
    lang_map = {"Arabic": "ar", "English": "en", "French": "fr", "Italian": "it", "Spanish": "es", "German": "de",
                "Turkish": "tr", "Russian": "ru", "Chinese": "zh", "Persian": "fa", "Portuguese": "pt", "Dutch": "nl",
                "Greek": "el", "Hebrew": "he", "Japanese": "ja", "Korean": "ko", "Ukrainian": "uk", "Polish": "pl", "Swedish": "sv"}
    for a in data.get("articles", []) or []:
        out.append({"title": P.strip_html(a.get("title", "")), "url": a.get("url", ""), "summary": "",
                    "published": parse_date(a.get("seendate", "")),
                    "lang": lang_map.get(a.get("language", ""), ""), "source_name": a.get("domain", "")})
    return out


# ---------------------------------------------------------------- تلغرام (واجهة الويب العامة)
def parse_telegram_web(text):
    out = []
    for blk in re.split(r'<div class="tgme_widget_message_wrap', text)[1:]:
        m_text = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
        m_link = re.search(r'<a class="tgme_widget_message_date" href="([^"]+)"', blk)
        m_time = re.search(r'<time[^>]+datetime="([^"]+)"', blk)
        if not m_text or not m_link:
            continue
        body = P.strip_html(html.unescape(re.sub(r"<br\s*/?>", " ", m_text.group(1))))
        if not body:
            continue
        title = body[:160] + ("…" if len(body) > 160 else "")
        out.append({"title": title, "url": m_link.group(1), "summary": body[:1200],
                    "published": parse_date(m_time.group(1)) if m_time else None})
    return out


# ---------------------------------------------------------------- Bluesky (بحث عام مجاني)
def parse_bluesky(text):
    import json as _j
    out = []
    for p in (_j.loads(text).get("posts") or []):
        rec = p.get("record") or {}
        body = (rec.get("text") or "").strip()
        if not body:
            continue
        au = p.get("author") or {}
        handle = au.get("handle", "")
        rkey = (p.get("uri") or "").rsplit("/", 1)[-1]
        out.append({"title": body[:160] + ("…" if len(body) > 160 else ""), "summary": body[:1200],
                    "url": "https://bsky.app/profile/%s/post/%s" % (handle, rkey),
                    "published": parse_date(rec.get("createdAt") or ""), "source_name": "بلواسكاي — " + (au.get("displayName") or handle)})
    return out


BSKY_QUERIES = ["ليبيا", "Libya", "طرابلس", "بنغازي", "Libye", "Libia"]


# ---------------------------------------------------------------- المنسق
class Collector:
    def __init__(self, store, extra_feeds=None):
        self.store = store
        self.extra_feeds = extra_feeds or []
        try:
            self.extra_sites = json.loads(store.meta_get("extra_sites", "[]"))
        except Exception:
            self.extra_sites = []
        self._gdelt_gap = threading.Lock()
        self._last_gdelt = 0.0
        self.status = {"running": False, "cycle": 0, "last_start": None, "last_end": None, "last_new": 0, "progress": ""}
        self._feed_cache = {}  # رابط صفحة -> رابط RSS المكتشف
        self._cond = {}        # رابط -> {etag, lm} للجلب الشرطي
        self._direct_lock = threading.Lock()
        self._prestige_lock = threading.Lock()
        self._force = False      # الصيانة تضع True لتجريب حتى الخامل والمتعثّر مرة كل دورة صيانة

    def _due(self, name, protected=False):
        """هل حان وقت جلب هذا المصدر؟ الخامل يُفحص أقل، والمتعثّر يتراجع أُسّياً، دون أن نفقد شيئاً."""
        if self._force:
            return True
        try:
            h = self.store.health_map().get(name)
            if not h:
                return True
            delay, why = self.store.source_delay(h)
            if protected and why == "dormant":
                return True      # مصدر أضافه المستخدم بنفسه: لا نخفّف فحصه
            return not delay or time.time() - (h.get("last_run") or 0) >= delay
        except Exception:
            return True

    # ---- معالجة سجل خام -> قاعدة البيانات
    def _ingest(self, recs, source, stype, via, lang_hint, trusted, accept_all=False, min_rel=0, auth=None):
        new = 0
        maxage = int(time.time()) - C.MAX_AGE_DAYS * 86400
        for r in recs:
            title = (r.get("title") or "").strip()
            if not title:
                continue
            pub = r.get("published")
            if pub and pub < maxage:
                continue
            if re.match(r"^\s*(log ?in|sign ?in|تسجيل الدخول)\b", title, re.I):
                continue      # صفحات دخول/توثيق التقطها البحث بالموقع
            summary = r.get("summary") or ""
            rel, matched = P.relevance(title, summary, trusted=trusted)
            if accept_all and rel < 2:
                rel = 2   # مصدر ليبي بالكامل: يُعرض دائماً
            if min_rel and rel < min_rel:
                continue
            if rel <= 0:
                continue
            lang = P.detect_lang(title + " " + summary[:200], r.get("lang") or lang_hint)
            src_name = r.get("source_name") or source
            rec = {"title": title, "url": r.get("url") or "", "summary": summary, "source": src_name, "stype": stype,
                   "via": via, "lang": lang, "published": pub, "rel": rel, "matched": matched}
            ex = {}
            if r.get("src_url"):
                ex["src_url"] = r["src_url"]
            kind, adom = C.prestige_kind(auth or P.domain_of(r.get("src_url") or r.get("url") or ""))
            if kind:
                ex["auth"] = kind
                ex["adom"] = adom
                if adom in C.PAYWALL:
                    ex["paywall"] = 1
            if ex:
                rec["extra"] = ex
            try:
                if self.store.add_item(rec):
                    new += 1
            except Exception as e:      # عنصر معطوب لا يُسقط بقية الخلاصة
                log("  تعذّر حفظ عنصر: %s" % str(e)[:80])
        return new

    # ---- مهام جلب بسيطة
    def _run_feed_job(self, health_name, kind, url, lang, stype, source, trusted, accept_all, via, gnews=False, gdelt=False, prestige=None):
        t0 = time.time()
        if not self._due(health_name):
            return 0
        log("بدأ " + health_name + " " + via[:40])
        try:
            if gdelt:
                if time.time() < getattr(self, "_gdelt_block", 0):
                    return 0     # GDELT حاجب مؤقتاً: لا نزعجه ولا نسجّله فشلاً
                with self._gdelt_gap:  # GDELT: طلب واحد كل ~5 ثوانٍ
                    wait = 6.5 - (time.time() - self._last_gdelt)
                    if wait > 0:
                        time.sleep(wait)
                    self._last_gdelt = time.time()
                    raw, cs = http_get(url, retries=0)
                recs = parse_gdelt(decode(raw, cs))
            else:
                raw, cs = http_get(url)
                recs = parse_feed(decode(raw, cs))
                if gnews:
                    recs = [_gnews_split_source(r) for r in recs]
            log("  جلب %s: %d عنصر (%.1f ث)، يعالج…" % (health_name, len(recs), time.time() - t0))
            n = self._ingest(recs, source, stype, via, lang, trusted, accept_all, min_rel=3 if prestige else 0, auth=prestige)
            self.store.record_health(health_name, kind, True, len(recs), n)
            log("  انتهى %s: جديد %d (%.1f ث)" % (health_name, n, time.time() - t0))
            return n
        except Exception as e:
            if gdelt and "429" in str(e):
                self._gdelt_block = time.time() + 7200
            log("  فشل %s: %s (%.1f ث)" % (health_name, str(e)[:120], time.time() - t0))
            self.store.record_health(health_name, kind, False, err=str(e))
            return 0

    def _telegram(self, ch):
        name = "Telegram/%s" % ch["channel"]
        if not self._due(name, True):
            return 0
        try:
            raw, cs = http_get("https://t.me/s/%s" % ch["channel"])
            recs = parse_telegram_web(decode(raw, cs))
            n = self._ingest(recs, ch.get("name") or ch["channel"], "social", "telegram", ch.get("lang", "ar"), False, accept_all=ch.get("all", False))
            self.store.record_health(name, "telegram", True, len(recs), n)
            return n
        except Exception as e:
            self.store.record_health(name, "telegram", False, err=str(e))
            return 0

    def _bsky(self, q):
        name = "Bluesky/%s" % q
        try:
            raw, cs = http_get("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=%s&sort=latest&limit=50" % urllib.parse.quote(q), retries=0, timeout=20)
            recs = parse_bluesky(decode(raw, cs))
            n = self._ingest(recs, "بلواسكاي", "social", "bluesky", "und", False)
            self.store.record_health(name, "bluesky", True, len(recs), n)
            return n
        except Exception as e:
            self.store.record_health(name, "bluesky", False, err=str(e))
            return 0

    def _direct(self, f):
        name = "RSS/%s" % f["name"]
        if not self._due(name, bool(f.get("mine"))):
            return 0
        try:
            url = f["url"]
            if f.get("autodiscover"):
                if url not in self._feed_cache:
                    found = autodiscover_feed(url)
                    if not found:
                        raise RuntimeError("لم يُعثر على RSS في الصفحة")
                    self._feed_cache[url] = found
                url = self._feed_cache[url]
            out = {}
            raw, cs = http_get(url, cond=self._cond.get(url), out=out)
            if raw is None:      # 304: لا جديد منذ آخر جلب
                self.store.record_health(name, "rss", True, 0, 0)
                return 0
            if out.get("etag") or out.get("lm"):
                self._cond[url] = {"etag": out.get("etag"), "lm": out.get("lm")}
            if "t.me/s/" in url:
                recs = parse_telegram_web(decode(raw, cs))
            elif "/wp-json/" in url:
                recs = parse_wp(decode(raw, cs))
            else:
                recs = parse_feed(decode(raw, cs))
            n = self._ingest(recs, f["name"], f.get("type", "news"), "telegram" if "t.me/s/" in url else "rss",
                             f.get("lang", "und"), False, accept_all=f.get("all", False))
            self.store.record_health(name, "rss", True, len(recs), n)
            return n
        except Exception as e:
            self.store.record_health(name, "rss", False, err=str(e))
            return 0

    def run_prestige(self, mode="lane", workers=6):
        """جلب المراجع الدولية فقط (كل ~40 دقيقة، وضمن الدورات الشاملة)."""
        if not self._prestige_lock.acquire(False):
            return 0
        try:
            n = 0
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(self._run_feed_job, hn, "prestige", url, lg, "news", "Google News", False, False, "prestige:" + q, True, False, dom.split("/")[0])
                        for hn, url, lg, q, dom in prestige_jobs(mode)]
                for f in futs:
                    n += f.result() or 0
            return n
        finally:
            self._prestige_lock.release()

    # ---- مسار سريع: المصادر المباشرة المهمة فقط (كل بضع دقائق، بجلب شرطي)
    def run_direct(self, workers=8):
        if self.status["running"] or not self._direct_lock.acquire(False):
            return 0
        try:
            feeds = [dict(f) for f in C.DIRECT_FEEDS if "search.rss" not in f["url"]] + [dict(f, autodiscover=True) for f in C.AUTODISCOVER_PAGES]
            feeds += [dict(f, mine=not f.get("auto")) for f in self.extra_feeds if f.get("all") or f.get("type") == "official"][:50]
            n = 0
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for r in ex.map(self._direct, feeds):
                    n += r or 0
            return n
        finally:
            self._direct_lock.release()

    # ---- دورة كاملة
    def run_cycle(self, mode="fast", workers=10):
        if self.status["running"]:
            return
        st = self.status
        st.update(running=True, last_start=int(time.time()), cycle=st["cycle"] + 1, last_new=0, progress="يبدأ… (%s)" % mode, mode=mode)
        total_new = 0
        try:
            tasks = []
            ex = ThreadPoolExecutor(max_workers=workers)
            # 1) مصادر مباشرة (الأسرع والأكثر قيمة)
            feeds = [dict(f) for f in C.DIRECT_FEEDS] + [dict(f, autodiscover=True) for f in C.AUTODISCOVER_PAGES] + [dict(f, mine=not f.get("auto")) for f in self.extra_feeds]
            for f in feeds:
                tasks.append(ex.submit(self._direct, f))
            for ch in C.TELEGRAM_CHANNELS:
                tasks.append(ex.submit(self._telegram, ch))
            # 2) جوجل نيوز وبينغ (متعددة اللغات)
            for hn, url, lg, q in google_news_jobs(mode):
                tasks.append(ex.submit(self._run_feed_job, hn, "googlenews", url, lg, "news", "Google News", True, False, "gnews:" + q, True))
            for hn, url, lg, q, pure in site_jobs(mode, self.extra_sites):
                tasks.append(ex.submit(self._run_feed_job, hn, "googlesite", url, lg, "news", "Google News", True, pure, "site:" + q, True))
            if mode != "fast":
                for hn, url, lg, q in bing_news_jobs():
                    tasks.append(ex.submit(self._run_feed_job, hn, "bing", url, lg, "news", "Bing News", True, False, "bing:" + q))
                # 3) GDELT (سلسلي بسبب حد الطلبات)
                for hn, url, lg, q in gdelt_jobs():
                    tasks.append(ex.submit(self._run_feed_job, hn, "gdelt", url, lg, "news", "GDELT", True, False, "gdelt:" + q, False, True))
            if mode != "fast":
                for hn, url, lg, q, dom in prestige_jobs(mode):
                    tasks.append(ex.submit(self._run_feed_job, hn, "prestige", url, lg, "news", "Google News", False, False, "prestige:" + q, True, False, dom.split("/")[0]))
            done = 0
            for fut in as_completed(tasks):
                total_new += fut.result() or 0
                done += 1
                if done % 5 == 0 or done == len(tasks):
                    st["progress"] = "%d/%d" % (done, len(tasks))
                    st["last_new"] = total_new
            ex.shutdown(wait=True)
        finally:
            st.update(running=False, last_end=int(time.time()), last_new=total_new, progress="اكتملت")
            self.store.meta_set("last_cycle_end", int(time.time()))
            self.store.housekeeping()
        return total_new

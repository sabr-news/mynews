# -*- coding: utf-8 -*-
"""قارئ المقالات داخل التطبيق: يجلب الصفحة، يفك رابط جوجل نيوز، يستخرج نص المقال، ويترجمه عند الطلب."""
import re
import html
import json
import time
import urllib.parse
import urllib.request

from . import config as C
from . import process as P
from . import collectors as K

_CACHE = {}
_DROP = re.compile(r"<(script|style|noscript|svg|iframe|form|header|footer|nav|aside|button|select|template)\b.*?</\1>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BLOCK = re.compile(r"<(p|h2|h3|blockquote)\b[^>]*>(.*?)</\1>", re.S | re.I)
_JUNK = re.compile(r"(cookie|ملفات تعريف الارتباط|اشترك في|subscribe to|all rights reserved|جميع الحقوق|read more|اقرأ أيضا|اقرأ أيضاً|follow us|تابعونا|advertisement|إعلان)", re.I)


def meta(page, *names):
    for n in names:
        m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)["\']' % re.escape(n), page, re.I) or \
            re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % re.escape(n), page, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def resolve_gnews(url):
    """يفك روابط news.google.com/rss/articles/... إلى رابط الناشر الأصلي (أفضل جهد)."""
    p = urllib.parse.urlparse(url)
    if p.netloc != "news.google.com":
        return url
    m = re.search(r"/(?:rss/)?(?:articles|read)/([^/?]+)", p.path)
    if not m:
        return url
    gid = m.group(1)
    try:
        raw, cs = K.http_get("https://news.google.com/rss/articles/%s?hl=en-US&gl=US&ceid=US:en" % gid, retries=0, timeout=20)
        page = K.decode(raw, cs)
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if not (sg and ts):
            ext = re.search(r'data-n-au="([^"]+)"', page)
            return html.unescape(ext.group(1)) if ext else url
        inner = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]'
                 % (gid, ts.group(1), sg.group(1)))
        freq = json.dumps([[["Fbv4je", inner, None, "generic"]]])
        body = urllib.parse.urlencode({"f.req": freq}).encode()
        req = urllib.request.Request("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "User-Agent": C.USER_AGENT})
        with urllib.request.urlopen(req, timeout=20, context=K._CTX) as r:
            txt = r.read().decode("utf-8", "replace")
        mm = re.search(r'garturlres\\",\\"(https?:[^"\\]+)', txt)
        if mm:
            return mm.group(1).replace("\\u003d", "=").replace("\\u0026", "&")
    except Exception as e:
        K.log("القارئ: فك رابط جوجل فشل: %s" % str(e)[:100])
    return url


def extract(page):
    title = meta(page, "og:title", "twitter:title") or (re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I) or [None, ""])[1]
    title = P.strip_html(html.unescape(title))
    image = meta(page, "og:image", "twitter:image")
    desc = meta(page, "og:description", "description")
    site = meta(page, "og:site_name")
    body = _COMMENT.sub("", _DROP.sub(" ", page))
    art = re.search(r"<article\b.*?</article>", body, re.S | re.I)
    scope = art.group(0) if art and len(P.strip_html(art.group(0))) > 400 else body
    paras, seen = [], set()
    for tag, inner in _BLOCK.findall(scope):
        t = P.strip_html(html.unescape(inner))
        t = re.sub(r"\s+", " ", t).strip()
        if tag.lower() == "p" or tag.lower() == "blockquote":
            if len(t) < 45 or _JUNK.search(t) and len(t) < 160:
                continue
        elif len(t) < 8 or len(t) > 140:
            continue
        if t in seen:
            continue
        seen.add(t)
        paras.append({"t": "h" if tag.lower() in ("h2", "h3") else "p", "x": t})
        if len(paras) >= 70:
            break
    # عنوان فرعي في آخر القائمة لا فائدة منه
    while paras and paras[-1]["t"] == "h":
        paras.pop()
    return {"title": title, "image": image, "desc": desc, "site": site, "paras": paras}


def translate_paras(paras):
    """يترجم الفقرات على دفعات (نقطة جوجل المجانية)."""
    from .translate import gtx
    out, batch, idx = [dict(p) for p in paras], [], []

    def flush():
        if not batch:
            return
        try:
            res = gtx("\n".join(batch), "auto", prio=True).split("\n")
            if len(res) == len(batch):
                for i, r in zip(idx, res):
                    out[i]["x"] = r.strip() or out[i]["x"]
            else:  # اختلف عدد الأسطر: ترجم فرادى
                for i, b in zip(idx, batch):
                    out[i]["x"] = gtx(b, "auto", prio=True).strip() or b
        except Exception as e:
            K.log("القارئ: فشلت الترجمة %s" % str(e)[:80])
        batch.clear()
        idx.clear()

    size = 0
    for i, p in enumerate(paras):
        if size + len(p["x"]) > 1800:
            flush()
            size = 0
        batch.append(p["x"][:1500].replace("\n", " "))
        idx.append(i)
        size += len(p["x"])
    flush()
    return out


def read(store, url, translate=False):
    with store.lock:
        known = store.db.execute("SELECT lang FROM items WHERE url=? LIMIT 1", (url,)).fetchone()
    if not known or not url.startswith("http"):
        return {"ok": False, "error": "رابط غير معروف"}
    key = url
    c = _CACHE.get(key)
    if c and time.time() - c["at"] < 1800:
        res = c["res"]
    else:
        final = resolve_gnews(url)
        res = {"ok": True, "final": final, "lang": known["lang"]}
        try:
            raw, cs = K.http_get(final, retries=1, timeout=25)
            page = K.decode(raw, cs)
            ex = extract(page)
            res.update(ex)
            if len(ex["paras"]) < 2:
                if ex["desc"]:
                    res["paras"] = [{"t": "p", "x": ex["desc"]}]
                res["partial"] = True
            res["lang"] = P.detect_lang(" ".join(p["x"] for p in res["paras"][:6]) or ex["title"], known["lang"])
        except Exception as e:
            res.update(ok=False, error="تعذّر جلب الصفحة: %s" % str(e)[:100])
        if len(_CACHE) > 80:
            _CACHE.clear()
        _CACHE[key] = {"at": time.time(), "res": res}
    if translate and res.get("ok") and res.get("lang") != "ar" and res.get("paras"):
        tk = key + "|ar"
        t = _CACHE.get(tk)
        if not t:
            r2 = dict(res)
            from . import translate as TR
            TR.PRIORITY[0] += 1
            try:
                r2["paras"] = translate_paras(res["paras"])
                r2["title_ar"] = None
                try:
                    from .translate import gtx
                    r2["title"] = gtx(res.get("title") or "", "auto", prio=True) or res.get("title")
                except Exception:
                    pass
            finally:
                TR.PRIORITY[0] -= 1
            r2["translated"] = any(a["x"] != b["x"] for a, b in zip(r2["paras"], res["paras"]))
            if not r2["translated"]:
                return dict(res, tr_failed=True)
            t = _CACHE[tk] = {"at": time.time(), "res": r2}
        return t["res"]
    return res

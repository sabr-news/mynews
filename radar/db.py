# -*- coding: utf-8 -*-
"""التخزين: SQLite + بحث نصي كامل (FTS5) + تجميع الأخبار المتشابهة في «قصص»."""
import os
import re
import json
import time
import sqlite3
import threading
from collections import defaultdict

from . import config as C
from . import process as P


class Store:
    def __init__(self, path=None):
        self.path = path or C.DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self._schema()
        # اتصال قراءة مستقل: في وضع WAL لا تنتظر القراءة (الأخبار والإحصاءات) كتابة الجامعات
        self.rlock = threading.RLock()
        self.rdb = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.rdb.row_factory = sqlite3.Row
        self.rdb.execute("PRAGMA busy_timeout=8000")
        self.rdb.execute("PRAGMA query_only=1")
        self.rdb.execute("PRAGMA cache_size=-32000")
        # فهرس الذاكرة للتشابه: item_id -> (cluster, tokens, ts)
        self.recent = {}
        self.inv = defaultdict(set)
        self._load_recent()

    # ------------------------------------------------------------------ schema
    def _schema(self):
        d = self.db
        d.executescript("""
        CREATE TABLE IF NOT EXISTS items(
            id TEXT PRIMARY KEY,
            url TEXT, domain TEXT, source TEXT, stype TEXT, via TEXT,
            lang TEXT, title TEXT, summary TEXT,
            published INTEGER, fetched INTEGER,
            category TEXT, urgency INTEGER DEFAULT 0, rel INTEGER DEFAULT 0,
            matched TEXT, cluster_id TEXT, extra TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_pub ON items(published DESC);
        CREATE INDEX IF NOT EXISTS ix_fetched ON items(fetched DESC);
        CREATE INDEX IF NOT EXISTS ix_cluster ON items(cluster_id);
        CREATE INDEX IF NOT EXISTS ix_lang ON items(lang);
        CREATE INDEX IF NOT EXISTS ix_cat ON items(category);
        CREATE TABLE IF NOT EXISTS health(
            name TEXT PRIMARY KEY, kind TEXT, last_run INTEGER, last_ok INTEGER, last_err TEXT,
            last_count INTEGER DEFAULT 0, last_new INTEGER DEFAULT 0, total_new INTEGER DEFAULT 0,
            runs INTEGER DEFAULT 0, fails INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS watches(id INTEGER PRIMARY KEY AUTOINCREMENT, term TEXT UNIQUE, created INTEGER);
        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
        """)
        try:  # عمود العنوان العربي وجدول أسماء المصادر
            d.execute("ALTER TABLE items ADD COLUMN title_ar TEXT")
        except sqlite3.OperationalError:
            pass
        for col in ("last_yield INTEGER", "err_streak INTEGER DEFAULT 0"):
            try:
                d.execute("ALTER TABLE health ADD COLUMN " + col)
                if col.startswith("last_yield"):     # فترة سماح: المصادر التي أنتجت سابقاً تُعدّ نشطة من الآن
                    d.execute("UPDATE health SET last_yield=last_run WHERE total_new>0")
            except sqlite3.OperationalError:
                pass
        d.execute("CREATE TABLE IF NOT EXISTS names(src TEXT PRIMARY KEY, ar TEXT)")
        d.execute("UPDATE items SET title_ar=title WHERE lang='ar' AND title_ar IS NULL")
        try:
            d.execute("ALTER TABLE items ADD COLUMN pub_known INTEGER DEFAULT 1")
            # عناصر قديمة وقت نشرها = وقت الجلب تقريباً: وقت النشر غير موثوق
            d.execute("UPDATE items SET pub_known=0 WHERE ABS(published-fetched)<=5")
        except Exception:
            pass
        d.execute("DELETE FROM health WHERE name LIKE 'Bluesky/%'")
        d.execute("CREATE TABLE IF NOT EXISTS digests(id INTEGER PRIMARY KEY AUTOINCREMENT, created INTEGER, label TEXT, window_h REAL, items TEXT)")
        try:  # ترحيلات خفيفة وآمنة للتكرار
            d.execute("UPDATE items SET rel=2 WHERE rel=1 AND via IN ('rss','telegram')")
            d.execute("DELETE FROM items WHERE matched='[\"sabha\"]'")
            d.execute("DELETE FROM health WHERE name IN ('RSS/Crisis Group - Libya','RSS/ReliefWeb - Libya','RSS/Libya Observer','RSS/الوسط','RSS/ليبيا الأحرار','RSS/UNSMIL','RSS/بوابة أفريقيا الإخبارية')")
            # أخبار موقع الوسط الدولية التي قُبلت سابقاً دون كيان ليبي
            d.execute("DELETE FROM items WHERE via LIKE 'site:site:alwasat%' AND matched='[]'")
            d.execute("DELETE FROM items WHERE via LIKE 'site:alwasat%' AND matched='[]'")
        except sqlite3.Error:
            pass
        try:
            d.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title, summary, tokenize='unicode61 remove_diacritics 2')")
            self.has_fts = True
        except sqlite3.OperationalError:
            self.has_fts = False

    def _load_recent(self):
        cutoff = int(time.time()) - C.DEDUP_WINDOW_HOURS * 3600
        for r in self.db.execute("SELECT id, cluster_id, title, published FROM items WHERE published>=?", (cutoff,)):
            self._index(r["id"], r["cluster_id"], P.title_tokens(r["title"]), r["published"])

    def _index(self, iid, cid, toks, ts):
        self.recent[iid] = (cid, toks, ts)
        for t in toks:
            self.inv[t].add(iid)

    def _prune_index(self):
        cutoff = int(time.time()) - C.DEDUP_WINDOW_HOURS * 3600
        old = [i for i, (_, _, ts) in self.recent.items() if ts < cutoff]
        for i in old:
            _, toks, _ = self.recent.pop(i)
            for t in toks:
                s = self.inv.get(t)
                if s:
                    s.discard(i)
                    if not s:
                        self.inv.pop(t, None)

    def _find_cluster(self, toks):
        if len(toks) < 2:
            return None
        votes = defaultdict(int)
        for t in toks:
            for iid in self.inv.get(t, ()):
                votes[iid] += 1
        best, bs = None, 0.0
        for iid, v in votes.items():
            if v < 3 and not (v == 2 and len(toks) <= 4):
                continue
            cid, otoks, _ = self.recent[iid]
            sc = P.jaccard(toks, otoks)
            if sc > bs:
                best, bs = cid, sc
        return best if bs >= C.TITLE_SIM_THRESHOLD else None

    # ------------------------------------------------------------------ write
    def add_item(self, rec):
        """rec: url,title,summary,source,stype,via,lang,published,extra ... يرجع True إذا كان جديداً."""
        now = int(time.time())
        iid = P.item_id(rec.get("url"), rec["title"])
        with self.lock:
            if self.db.execute("SELECT 1 FROM items WHERE id=?", (iid,)).fetchone():
                ex = rec.get("extra") or {}
                if ex.get("auth"):     # وُجد من قبل بلا وسم المرجع الدولي: نضيف الوسم
                    old = self.db.execute("SELECT extra FROM items WHERE id=?", (iid,)).fetchone()[0]
                    try:
                        cur = json.loads(old) if old else {}
                    except Exception:
                        cur = {}
                    if not cur.get("auth"):
                        cur.update(ex)
                        self.db.execute("UPDATE items SET extra=? WHERE id=?", (json.dumps(cur, ensure_ascii=False), iid))
                return False
            known = 1 if rec.get("published") else 0
            pub = int(rec.get("published") or now)
            if pub > now + 3600:
                pub = now
                known = 0
            toks = P.title_tokens(rec["title"])
            cid = self._find_cluster(toks) or iid
            cat = P.categorize(rec["title"], rec.get("summary"))
            urg = P.urgency(rec["title"], rec.get("summary"))
            self.db.execute(
                "INSERT INTO items(id,url,domain,source,stype,via,lang,title,summary,published,fetched,category,urgency,rel,matched,cluster_id,extra,title_ar,pub_known)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (iid, rec.get("url"), P.domain_of(rec.get("url") or ""), rec.get("source"), rec.get("stype", "news"),
                 rec.get("via", ""), rec.get("lang", "und"), rec["title"], rec.get("summary", ""), pub, now, cat, urg,
                 rec.get("rel", 0), json.dumps(rec.get("matched", []), ensure_ascii=False), cid,
                 json.dumps(rec.get("extra", {}), ensure_ascii=False) if rec.get("extra") else None,
                 rec["title"] if rec.get("lang") == "ar" else None, known))
            if self.has_fts:
                rid = self.db.execute("SELECT rowid FROM items WHERE id=?", (iid,)).fetchone()[0]
                self.db.execute("INSERT OR REPLACE INTO fts(rowid,title,summary) VALUES(?,?,?)",
                                (rid, P.norm_text(rec["title"]), P.norm_text(rec.get("summary", ""))[:2000]))
            self._index(iid, cid, toks, pub)
            return True

    def record_health(self, name, kind, ok, count=0, new=0, err=None):
        now = int(time.time())
        with self.lock:
            r = self.db.execute("SELECT * FROM health WHERE name=?", (name,)).fetchone()
            if r is None:
                self.db.execute("INSERT INTO health(name,kind,last_run,last_ok,last_err,last_count,last_new,total_new,runs,fails,last_yield,err_streak)"
                                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (name, kind, now, now if ok else None, None if ok else (err or "")[:300], count, new, new, 1,
                                 0 if ok else 1, now if new else None, 0 if ok else 1))
            else:
                self.db.execute(
                    "UPDATE health SET kind=?,last_run=?,last_ok=CASE WHEN ? THEN ? ELSE last_ok END,last_err=?,last_count=?,last_new=?,"
                    "total_new=total_new+?,runs=runs+1,fails=fails+?,last_yield=CASE WHEN ?>0 THEN ? ELSE last_yield END,"
                    "err_streak=CASE WHEN ? THEN 0 ELSE COALESCE(err_streak,0)+1 END WHERE name=?",
                    (kind, now, 1 if ok else 0, now, None if ok else (err or "")[:300], count, new, new, 0 if ok else 1,
                     new, now, 1 if ok else 0, name))

    # ------------------------------------------------------------------ watches / meta
    def watches(self):
        with self.lock:
            return [r["term"] for r in self.db.execute("SELECT term FROM watches ORDER BY id")]

    def add_watch(self, term):
        term = (term or "").strip()
        if not term:
            return
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO watches(term,created) VALUES(?,?)", (term, int(time.time())))

    def del_watch(self, term):
        with self.lock:
            self.db.execute("DELETE FROM watches WHERE term=?", (term,))

    def meta_get(self, k, default=None):
        with self.lock:
            r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
            return r["v"] if r else default

    def meta_set(self, k, v):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", (k, str(v)))

    # ------------------------------------------------------------------ ترجمة وأسماء
    def name_ar(self, src):
        from . import names as N
        import re as _re
        if src and src.startswith("http"):
            src = _re.sub(r"^https?://(www\.)?", "", src).rstrip("/")
        v = N.lookup(src)
        if v:
            return v
        if not any(ord(c) > 0x2FF and not ('\u0600' <= c <= '\u06FF') for c in src or ""):
            return N.display(src)  # كتابة نطقية للأسماء اللاتينية
        with self.rlock:
            r = self.rdb.execute("SELECT ar FROM names WHERE src=?", (src,)).fetchone()
        return r["ar"] if r else src

    def pending_translations(self, limit=10, exclude=()):
        cutoff = int(time.time()) - 7 * 86400
        with self.lock:
            rows = self.db.execute(
                "SELECT i.id id, i.title title, i.lang lang FROM items i WHERE i.title_ar IS NULL AND i.lang!='ar' AND i.rel>=2 AND i.published>=?"
                " AND NOT EXISTS (SELECT 1 FROM items a WHERE a.cluster_id=i.cluster_id AND a.id!=i.id AND (a.lang='ar' OR a.title_ar IS NOT NULL))"
                " GROUP BY i.cluster_id ORDER BY MAX(i.published) DESC LIMIT ?", (cutoff, limit + len(exclude))).fetchall()
        out = [dict(r) for r in rows if r["id"] not in exclude]
        return out[:limit]

    def set_title_ar(self, iid, text):
        with self.lock:
            self.db.execute("UPDATE items SET title_ar=? WHERE id=?", (text, iid))

    def pending_names(self, limit=8, exclude=()):
        from . import names as N
        cutoff = int(time.time()) - 3 * 86400
        with self.lock:
            srcs = [r[0] for r in self.db.execute("SELECT DISTINCT source FROM items WHERE rel>=2 AND published>=? AND source IS NOT NULL", (cutoff,))]
            have = {r[0] for r in self.db.execute("SELECT src FROM names")}
        out = [s for s in srcs if s not in have and s not in exclude and not N.lookup(s) and not s.startswith('http')
               and any(ord(c) > 0x2FF and not ('\u0600' <= c <= '\u06FF') for c in s)]
        return out[:limit]

    def set_name(self, src, ar):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO names(src,ar) VALUES(?,?)", (src, ar))

    def translation_status(self):
        with self.lock:
            left = self.db.execute("SELECT COUNT(*) FROM items i WHERE i.title_ar IS NULL AND i.lang!='ar' AND i.rel>=2 AND i.published>=?"
                                   " AND NOT EXISTS (SELECT 1 FROM items a WHERE a.cluster_id=i.cluster_id AND a.id!=i.id AND (a.lang='ar' OR a.title_ar IS NOT NULL))",
                                   (int(time.time()) - 7 * 86400,)).fetchone()[0]
        return {"pending": left}

    # ------------------------------------------------------------------ read
    # الروابط من جوجل/بينغ كلها بنطاق واحد، فنعدّ اسم الصحيفة بدلاً منه
    SRC = "CASE WHEN i.domain IN ('news.google.com','bing.com','www.bing.com') THEN i.source ELSE i.domain END"

    def rules(self):
        try:
            return json.loads(self.meta_get("rules", "[]"))
        except Exception:
            return []

    def saved(self):
        try:
            return json.loads(self.meta_get("saved", "[]"))
        except Exception:
            return []

    _AR_PRE = ("", "ال", "لل", "بال", "وال", "فال", "كال", "و", "ب", "ل", "ف", "ك", "ول", "وب")

    @staticmethod
    def _term(w):
        """كلمة عربية: نطابقها مع السوابق (ال، وال، بال، لل، و، ب، ل…) حتى يجد «نفط» ما فيه «النفط» و«للنفط»."""
        w = w.replace('"', "")
        if re.fullmatch(r"[\u0600-\u06FF]{3,}", w):
            base = w
            for p in ("وال", "بال", "فال", "كال", "لل", "ال"):
                if w.startswith(p) and len(w) - len(p) >= 3:
                    base = w[len(p):]
                    break
            forms = {p + base for p in Store._AR_PRE} | {w}
            return "(" + " OR ".join('"%s"*' % f for f in sorted(forms)) + ")"
        return '"%s"*' % w

    @staticmethod
    def parse_query(q):
        """صيغة البحث: كلمات = AND، OR/أو، NOT/-كلمة للاستبعاد، "عبارة حرفية"."""
        q = q.replace('«', '"').replace('»', '"')
        toks = re.findall(r'"[^"]+"|\S+', q)
        pos, neg, negnext = [], [], False
        for t in toks:
            u = t.upper()
            if u == "AND":
                continue
            if u in ("OR", "أو") and not t.startswith('"'):
                if pos and pos[-1] != "OR":
                    pos.append("OR")
                continue
            if u == "NOT":
                negnext = True
                continue
            isneg = negnext or (t[:1] in "-!" and len(t) > 1)
            negnext = False
            if t[:1] in "-!" and len(t) > 1:
                t = t[1:]
            phrase = t.startswith('"') and t.endswith('"') and len(t) > 2
            words = [w for w in P.norm_text(t.strip('"')).split() if w]
            if not words:
                continue
            ex = ('"%s"' % " ".join(words).replace('"', "")) if phrase else " ".join(Store._term(w) for w in words)
            (neg if isneg else pos).append(ex)
        while pos and pos[-1] == "OR":
            pos.pop()
        out = []
        for i, x in enumerate(pos):
            if i and x != "OR" and pos[i - 1] != "OR":
                out.append("AND")
            out.append(x)
        return " ".join(out), neg

    def _where(self, f):
        w, args = [], []
        w.append("i.rel>=?")
        args.append(int(f.get("min_rel", 2)))
        if f.get("lang"):
            langs = [x for x in f["lang"].split(",") if x]
            w.append("i.lang IN (%s)" % ",".join("?" * len(langs)))
            args += langs
        if f.get("cat"):
            cats = [x for x in f["cat"].split(",") if x]
            w.append("i.category IN (%s)" % ",".join("?" * len(cats)))
            args += cats
        if f.get("stype"):
            st = [x for x in f["stype"].split(",") if x]
            w.append("i.stype IN (%s)" % ",".join("?" * len(st)))
            args += st
        if f.get("domain"):
            w.append("i.domain=?")
            args.append(f["domain"])
        if f.get("hours") and float(f["hours"]) > 0:
            w.append("i.published>=?")
            args.append(int(time.time()) - int(float(f["hours"]) * 3600))
        if f.get("auth") in ("1", 1, True):
            w.append("i.extra LIKE '%\"auth\"%'")
        if f.get("known") in ("1", 1, True):
            w.append("i.pub_known=1")
        if f.get("since_fetched"):
            w.append("i.fetched>?")
            args.append(int(f["since_fetched"]))
        if f.get("min_urgency"):
            w.append("i.urgency>=?")
            args.append(int(f["min_urgency"]))
        q = (f.get("q") or "").strip()
        rules = [] if f.get("no_rules") else self.rules()
        mute_w = [P.norm_text(r["value"]) for r in rules if r.get("kind") == "mute_word" and P.norm_text(r["value"])]
        mute_s = [r["value"] for r in rules if r.get("kind") == "mute_source"]
        pos, neg = self.parse_query(q) if q else ("", [])
        neg = neg + ['"%s"' % m.replace('"', "") for m in mute_w]
        if self.has_fts:
            if pos:
                w.append("i.rowid IN (SELECT rowid FROM fts WHERE fts MATCH ?)")
                args.append(pos)
            if neg:
                w.append("i.rowid NOT IN (SELECT rowid FROM fts WHERE fts MATCH ?)")
                args.append(" OR ".join(neg))
        elif q:
            for t in re.findall(r"[^\s\"-]+", q):
                w.append("(i.title LIKE ? OR i.summary LIKE ?)")
                args += ["%" + t + "%"] * 2
        if mute_s:
            w.append("i.domain NOT IN (%s) AND i.source NOT IN (%s)" % (",".join("?" * len(mute_s)), ",".join("?" * len(mute_s))))
            args += mute_s + mute_s
        return (" AND ".join(w) or "1=1"), args

    @staticmethod
    def _ex(x):
        try:
            return json.loads(x["extra"]) if x["extra"] else {}
        except Exception:
            return {}

    def _row(self, r):
        d = dict(r)
        d["matched"] = json.loads(d["matched"]) if d.get("matched") else []
        ex = self._ex(d)
        d["_auth"], d["_paywall"] = ex.get("auth"), ex.get("paywall")
        d.pop("extra", None)
        return d

    def stories(self, f, limit=40, offset=0, sort="latest"):
        where, args = self._where(f)
        order = {
            "latest": "last_pub DESC",
            "urgent": "urg DESC, nd DESC, last_pub DESC",
            "sources": "nd DESC, n DESC, last_pub DESC",
        }.get(sort, "last_pub DESC")
        sql = ("SELECT i.cluster_id cid, COUNT(*) n, COUNT(DISTINCT " + self.SRC + ") nd, MAX(i.urgency) urg, MAX(i.published) last_pub,"
               " MIN(i.published) first_pub, MAX(i.fetched) last_fetched, MIN(i.fetched) first_fetched, MIN(CASE WHEN i.pub_known=1 THEN i.published END) first_known, MAX(CASE WHEN i.pub_known=1 THEN i.published END) last_known, GROUP_CONCAT(DISTINCT i.lang) langs"
               " FROM items i WHERE " + where + " GROUP BY i.cluster_id ORDER BY " + order + " LIMIT ? OFFSET ?")
        with self.rlock:
            rows = self.rdb.execute(sql, args + [limit, offset]).fetchall()
            total = self.rdb.execute("SELECT COUNT(DISTINCT i.cluster_id) FROM items i WHERE " + where, args).fetchone()[0]
            out = []
            for r in rows:
                its = self.rdb.execute("SELECT * FROM items WHERE cluster_id=? ORDER BY published ASC", (r["cid"],)).fetchall()
                its = [self._row(x) for x in its]
                # الممثل: يُفضَّل الأصل العربي، ثم ما تُرجم، ثم الأعلى صلة، ثم الأقدم
                rep = sorted(its, key=lambda x: (x["lang"] != "ar", x["title_ar"] is None, -x["rel"], x["published"]))[0]
                stypes = {x["stype"] for x in its}
                pending = rep["title_ar"] is None
                out.append({
                    "id": r["cid"], "title": rep["title_ar"] or rep["title"], "title_orig": rep["title"],
                    "pending_translation": pending, "translated": (rep["lang"] != "ar" and not pending),
                    "summary": rep["summary"], "url": rep["url"],
                    "source": rep["source"], "source_ar": self.name_ar(rep["source"]),
                    "domain": rep["domain"], "lang": rep["lang"], "category": rep["category"],
                    "urgency": r["urg"], "n_items": r["n"], "n_domains": r["nd"],
                    "first_pub": r["first_pub"], "last_pub": r["last_pub"], "last_fetched": r["last_fetched"],
                    "first_fetched": r["first_fetched"], "first_known": r["first_known"], "last_known": r["last_known"],
                    "langs": (r["langs"] or "").split(","),
                    "trust": P.source_trust_label("official" if "official" in stypes else (rep["stype"]), r["nd"]),
                    "stype": rep["stype"], "matched": rep["matched"],
                    "items": [{"title": x["title_ar"] or x["title"], "url": x["url"], "source": x["source"],
                               "source_ar": self.name_ar(x["source"]), "domain": x["domain"], "lang": x["lang"],
                               "published": x["published"], "pub_known": x["pub_known"], "fetched": x["fetched"], "stype": x["stype"],
                               "auth": x.get("_auth"), "paywall": x.get("_paywall")} for x in its[:12]],
                    "auth": next((x.get("_auth") for x in its if x.get("_auth")), None),
                    "auth_src": next((self.name_ar(x["source"]) for x in its if x.get("_auth")), None),
                    "paywall": any(x.get("_paywall") for x in its if x.get("_auth")),
                })
        return {"total": total, "stories": out}

    def stats(self):
        now = int(time.time())
        with self.rlock:
            q = lambda s, a=(): [dict(r) for r in self.rdb.execute(s, a)]
            total = self.rdb.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            d24 = self.rdb.execute("SELECT COUNT(*) FROM items WHERE rel>=2 AND published>=?", (now - 86400,)).fetchone()[0]
            s24 = self.rdb.execute("SELECT COUNT(DISTINCT cluster_id) FROM items WHERE rel>=2 AND published>=?", (now - 86400,)).fetchone()[0]
            langs = q("SELECT lang, COUNT(*) n FROM items WHERE rel>=2 AND published>=? GROUP BY lang ORDER BY n DESC", (now - 7 * 86400,))
            cats = q("SELECT category, COUNT(*) n FROM items WHERE rel>=2 AND published>=? GROUP BY category ORDER BY n DESC", (now - 7 * 86400,))
            stypes = q("SELECT stype, COUNT(*) n FROM items WHERE rel>=2 AND published>=? GROUP BY stype ORDER BY n DESC", (now - 7 * 86400,))
            doms = q("SELECT (CASE WHEN domain IN ('news.google.com','bing.com','www.bing.com') THEN source ELSE domain END) domain, COUNT(*) n FROM items WHERE rel>=2 AND published>=? GROUP BY 1 ORDER BY n DESC LIMIT 15", (now - 86400,))
            hours = q("SELECT (published/3600) h, COUNT(*) n FROM items WHERE rel>=2 AND published>=? GROUP BY h ORDER BY h", (now - 48 * 3600,))
            ents = defaultdict(int)
            for r in self.rdb.execute("SELECT matched FROM items WHERE rel>=2 AND published>=? AND matched IS NOT NULL", (now - 86400,)):
                try:
                    for m in json.loads(r["matched"]):
                        ents[m] += 1
                except Exception:
                    pass
            top_ents = sorted(ents.items(), key=lambda x: -x[1])[:20]
            last_item = self.rdb.execute("SELECT MAX(fetched) FROM items").fetchone()[0]
        return {"total": total, "last24h": d24, "stories24h": s24, "langs": langs, "categories": cats, "stypes": stypes,
                "domains": doms, "hours": hours, "entities": [{"term": k, "n": v} for k, v in top_ents],
                "last_fetch": last_item, "now": now}

    @staticmethod
    def source_delay(h, now=None):
        """كم ثانية ينبغي تأجيل جلب هذا المصدر؟ (0 = اجلبه الآن). تراجع أُسّي للمتعثّر، وتخفيف للخامل الذي لا ينتج جديداً."""
        now = now or int(time.time())
        streak = h.get("err_streak") or 0
        if streak >= 3:
            return min(86400, 600 * 2 ** min(streak - 2, 8)), "err"
        runs, tn, ly = h.get("runs") or 0, h.get("total_new") or 0, h.get("last_yield")
        if runs >= 40 and tn == 0:
            return 12 * 3600, "dormant"
        if runs >= 40 and ly:
            quiet = now - ly
            if quiet > 14 * 86400:
                return 24 * 3600, "dormant"
            if quiet > 3 * 86400:
                return 6 * 3600, "dormant"
        return 0, "ok"

    def health_map(self, max_age=45):
        c = getattr(self, "_hm", None)
        if c and time.time() - c[0] < max_age:
            return c[1]
        with self.rlock:
            m = {r["name"]: dict(r) for r in self.rdb.execute("SELECT * FROM health")}
        self._hm = (time.time(), m)
        return m

    def health(self):
        now = int(time.time())
        with self.rlock:
            rows = [dict(r) for r in self.rdb.execute("SELECT * FROM health ORDER BY kind, name")]
        for r in rows:
            r["state"] = self.source_delay(r, now)[1]
        return rows

    def alerts(self, since_fetched, min_urgency=6):
        """أخبار جديدة (بعد وقت الجلب) تستحق التنبيه: عاجلة، أو تطابق كلمات المراقبة."""
        watches = [P.norm_text(w) for w in self.watches()]
        with self.lock:
            rows = self.db.execute("SELECT * FROM items WHERE fetched>? ORDER BY fetched DESC LIMIT 600", (int(since_fetched),)).fetchall()
        out = []
        for r in rows:
            d = self._row(r)
            text = P.norm_text(d["title"] + " " + (d["summary"] or ""))
            hit = [w for w in watches if w and w in text]
            if d["urgency"] >= min_urgency or hit:
                d["watch_hits"] = hit
                out.append(d)
        return out[:50]

    def export_since(self, hours=24):
        cutoff = int(time.time()) - int(hours * 3600)
        with self.lock:
            return [self._row(r) for r in self.db.execute("SELECT * FROM items WHERE published>=? ORDER BY published DESC", (cutoff,))]

    # ------------------------------------------------------------------ الموجز الساعي
    def add_digest(self, label, window_h, items):
        with self.lock:
            cur = self.db.execute("INSERT INTO digests(created,label,window_h,items) VALUES(?,?,?,?)",
                                  (int(time.time()), label, window_h, json.dumps(items, ensure_ascii=False)))
            self.db.execute("DELETE FROM digests WHERE id NOT IN (SELECT id FROM digests ORDER BY id DESC LIMIT 96)")
            return cur.lastrowid

    def digests(self, limit=24):
        with self.lock:
            rows = self.db.execute("SELECT * FROM digests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r["id"], "created": r["created"], "label": r["label"], "window_h": r["window_h"],
                 "items": json.loads(r["items"])} for r in rows]

    def backfill_auth(self, days=21):
        """يضع وسم «مرجع دولي» على أخبار قديمة مصدرها نطاق مرجعي (رابط مباشر أو src_url)."""
        n = 0
        cutoff = int(time.time()) - days * 86400
        with self.lock:
            rows = self.db.execute("SELECT id, url, extra FROM items WHERE rel>=3 AND fetched>=? AND (extra IS NULL OR extra NOT LIKE '%\"auth\"%')", (cutoff,)).fetchall()
            for r in rows:
                try:
                    ex = json.loads(r["extra"]) if r["extra"] else {}
                except Exception:
                    ex = {}
                kind, adom = C.prestige_kind(P.domain_of(ex.get("src_url") or r["url"] or ""))
                if kind:
                    ex.update(auth=kind, adom=adom)
                    if adom in C.PAYWALL:
                        ex["paywall"] = 1
                    self.db.execute("UPDATE items SET extra=? WHERE id=?", (json.dumps(ex, ensure_ascii=False), r["id"]))
                    n += 1
            self.db.commit()
        return n

    def rebuild_fts(self):
        """يعيد بناء الفهرس من الجدول الأصلي (يصلح عدم التطابق بعد الحذف)."""
        if not self.has_fts:
            return 0
        with self.lock:
            self.db.execute("DELETE FROM fts")
            rows = self.db.execute("SELECT rowid, title, summary FROM items").fetchall()
            self.db.executemany("INSERT INTO fts(rowid,title,summary) VALUES(?,?,?)",
                                [(r[0], P.norm_text(r[1] or ""), P.norm_text(r[2] or "")[:2000]) for r in rows])
            self.db.commit()
        return len(rows)

    def recategorize(self, days=45):
        n = 0
        cutoff = int(time.time()) - days * 86400
        with self.lock:
            rows = self.db.execute("SELECT id,title,summary,category FROM items WHERE published>=?", (cutoff,)).fetchall()
            for r in rows:
                c = P.categorize(r["title"], r["summary"])
                if c != r["category"]:
                    self.db.execute("UPDATE items SET category=? WHERE id=?", (c, r["id"]))
                    n += 1
            self.db.commit()
        return n

    def housekeeping(self, keep_days=365):
        if self.meta_get("cat_fix2") != "1":
            try:
                self.recategorize()
                self.meta_set("cat_fix2", "1")
            except Exception:
                pass
        if self.meta_get("urg_fix1") != "1":
            try:
                cut = int(time.time()) - 30 * 86400
                with self.lock:
                    rows = self.db.execute("SELECT id,title,summary,urgency FROM items WHERE published>=?", (cut,)).fetchall()
                    for r in rows:
                        u = P.urgency(r["title"], r["summary"])
                        if u != r["urgency"]:
                            self.db.execute("UPDATE items SET urgency=? WHERE id=?", (u, r["id"]))
                self.meta_set("urg_fix1", "1")
            except Exception:
                pass
        if self.meta_get("fts_fix1") != "1":
            try:
                n = self.rebuild_fts()
                self.meta_set("fts_fix1", "1")
                print("fts rebuilt", n)
            except Exception:
                pass
        if time.time() - getattr(self, "_bf_t", 0) > 3600:
            self._bf_t = time.time()
            try:
                self.backfill_auth()
            except Exception:
                pass
        try:   # تنظيف بيانات خاطئة قديمة: روابط تحويل بينغ (بلا ناشر حقيقي) وصفحات دخول
            with self.lock:
                cond = "url LIKE '%bing.com/news/apiclick%' OR source='ReliefWeb API Documentation' OR title LIKE 'تسجيل الدخول -%'"
                ids = [r[0] for r in self.db.execute("SELECT rowid FROM items WHERE " + cond)]
                if ids:
                    if self.has_fts:
                        self.db.executemany("DELETE FROM fts WHERE rowid=?", [(i,) for i in ids])
                    self.db.execute("DELETE FROM items WHERE " + cond)
                self.db.commit()
        except Exception:
            pass
        try:   # صفوف صحة لمصادر لم تعد تُشغَّل منذ يومين
            with self.lock:
                self.db.execute("DELETE FROM health WHERE last_run<?", (int(time.time()) - 2 * 86400,))
                self.db.commit()
        except Exception:
            pass
        self._prune_index()

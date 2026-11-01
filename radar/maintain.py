# -*- coding: utf-8 -*-
"""الصيانة الذاتية: كل 3 ساعات يصلح التطبيق نفسه ويحدّث كل شيء، وتظهر للمستخدم شاشة تقدّم."""
import os
import time
import json
import sqlite3
import threading
import traceback

from . import config as C
from . import collectors as K

EVERY = 3 * 3600
STEPS = ["تنظيف الذاكرة المؤقتة وإعادة المصادر المتعثرة", "نسخة احتياطية وفحص قاعدة البيانات", "فحص المسارات الخلفية وإصلاحها",
         "تحديث المصادر واكتشاف الجديد", "جلب شامل لكل المصادر والمراجع الدولية", "وسم المراجع الدولية وإحصاء النتائج"]


class Maintainer(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.now_evt = threading.Event()
        last = 0
        try:
            last = int(app.store.meta_get("maint_last_end", "0") or 0)
        except Exception:
            pass
        rep = {}
        try:
            rep = json.loads(app.store.meta_get("maint_report", "{}"))
        except Exception:
            pass
        nxt = max((last or int(time.time())) + EVERY, int(time.time()) + 900)
        self.stats = {"running": False, "step": "", "idx": 0, "total": len(STEPS), "steps": STEPS, "detail": "",
                      "last_end": last or None, "next_run": nxt, "report": rep, "started": None}

    def trigger(self):
        self.now_evt.set()

    def run(self):
        while not self.app.stop.is_set():
            wait = self.stats["next_run"] - time.time()
            if self.now_evt.wait(min(30, max(1, wait))):
                self.now_evt.clear()
                self.run_once()
            elif wait <= 0:
                self.run_once()

    # ------------------------------------------------------------
    def _step(self, i, detail=""):
        self.stats.update(idx=i + 1, step=STEPS[i], detail=detail)

    def run_once(self):
        app, store, col = self.app, self.app.store, self.app.collector
        st = self.stats
        if st["running"]:
            return
        t0 = int(time.time())
        rep = {"started": t0, "fixed": [], "warnings": []}
        st.update(running=True, started=t0, idx=0, step=STEPS[0], detail="")
        n_before = store.stats()["total"]
        try:
            # 1) ذاكرة مؤقتة
            self._step(0)
            col._cond.clear()
            col._feed_cache.clear()
            col._gdelt_block = 0
            with store.lock:
                store.db.execute("DELETE FROM health WHERE last_run<?", (t0 - 2 * 86400,))
                store.db.commit()
            rep["fixed"].append("أُعيد ضبط الذاكرة المؤقتة وحاجز GDELT")

            # 2) قاعدة البيانات
            self._step(1, "نسخة احتياطية")
            try:
                bdir = os.path.join(C.DATA_DIR, "backup")
                os.makedirs(bdir, exist_ok=True)
                path = os.path.join(bdir, "radar-%s.db" % time.strftime("%Y%m%d-%H%M"))
                with store.lock:
                    dst = sqlite3.connect(path)
                    store.db.backup(dst)
                    dst.close()
                files = sorted(f for f in os.listdir(bdir) if f.startswith("radar-") and f.endswith(".db"))
                for old in files[:-3]:
                    try:
                        os.remove(os.path.join(bdir, old))
                    except Exception:
                        pass
                rep["fixed"].append("نسخة احتياطية جديدة (تُحفظ آخر 3)")
            except Exception as e:
                rep["warnings"].append("تعذّر النسخ الاحتياطي: %s" % str(e)[:80])
            self._step(1, "فحص السلامة")
            try:
                with store.lock:
                    ok = store.db.execute("PRAGMA quick_check").fetchone()[0]
                    store.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    store.db.execute("PRAGMA optimize")
                rep["db"] = "سليمة" if ok == "ok" else "تحذير: " + str(ok)[:80]
                if ok != "ok":
                    rep["warnings"].append("فحص قاعدة البيانات: " + str(ok)[:80])
            except Exception as e:
                rep["warnings"].append("فحص قاعدة البيانات: %s" % str(e)[:80])

            # 3) الخيوط الخلفية
            self._step(2)
            from .translate import Translator
            if app.translator is not None and not app.translator.is_alive():
                app.translator = Translator(store, app.stop)
                app.translator.start()
                rep["fixed"].append("أُعيد تشغيل المترجم")
            for attr in ("discoverer", "digester"):
                th = getattr(app, attr, None)
                if th is not None and not th.is_alive():
                    try:
                        cls = type(th)
                        nt = cls(app)
                        nt.start()
                        setattr(app, attr, nt)
                        rep["fixed"].append("أُعيد تشغيل " + attr)
                    except Exception:
                        pass
            if app.thread is not None and not app.thread.is_alive():
                app.thread = threading.Thread(target=app._loop, daemon=True)
                app.thread.start()
                rep["fixed"].append("أُعيد تشغيل حلقة الجمع")

            # 4) المصادر
            self._step(3, "فحص مواقع جديدة وحذف الميّت")
            d = app.discoverer
            if d is not None and not d.stats.get("running"):
                try:
                    d.run_once(limit=25)
                except Exception as e:
                    rep["warnings"].append("الاكتشاف: %s" % str(e)[:80])

            # 5) جلب (سريع للمصادر + شامل للمراجع الدولية)
            self._step(4, "بانتظار الدورة الجارية…")
            t_wait = time.time()
            while col.status["running"] and time.time() - t_wait < 150:
                self._step(4, "انتظار الدورة الجارية: " + str(col.status.get("progress", "")))
                time.sleep(3)
            col._force = True      # في الصيانة نجرّب كل شيء حتى الخامل والمتعثّر
            jobs = []
            if not col.status["running"]:
                jobs.append(threading.Thread(target=lambda: col.run_cycle("fast"), daemon=True))
            jobs.append(threading.Thread(target=lambda: col.run_prestige("full"), daemon=True))
            jobs.append(threading.Thread(target=lambda: col.run_direct(), daemon=True))
            for j in jobs:
                j.start()
            t_run = time.time()
            while any(j.is_alive() for j in jobs) and time.time() - t_run < 600:
                self._step(4, "جارٍ الجلب… " + str(col.status.get("progress", "")))
                time.sleep(2)

            col._force = False
            # 6) المراجع
            self._step(5)
            tagged = store.backfill_auth(60)
            n_after = store.stats()["total"]
            h = store.health()
            bad = [x for x in h if x["last_err"] and x["kind"] != "gdelt"]
            rep["dormant"] = len([x for x in h if x.get("state") == "dormant"])
            rep["backoff"] = len([x for x in h if x.get("state") == "err"])
            rep.update(new_items=max(0, n_after - n_before), sources=len(h), sources_ok=len([x for x in h if not x["last_err"]]),
                       sources_bad=len(bad), tagged=tagged)
            with store.lock:
                rep["prestige_24h"] = store.db.execute("SELECT COUNT(DISTINCT cluster_id) FROM items WHERE extra LIKE '%\"auth\"%' AND rel>=3 AND fetched>=?", (t0 - 86400,)).fetchone()[0]
        except Exception as e:
            traceback.print_exc()
            rep["warnings"].append("خطأ غير متوقع: %s" % str(e)[:120])
        finally:
            col._force = False
            end = int(time.time())
            rep["ended"] = end
            rep["seconds"] = end - t0
            try:
                store.meta_set("maint_last_end", end)
                store.meta_set("maint_report", json.dumps(rep, ensure_ascii=False))
            except Exception:
                pass
            st.update(running=False, last_end=end, next_run=end + EVERY, report=rep, step="", detail="")
            K.log("الصيانة الذاتية: انتهت في %d ث" % rep["seconds"])

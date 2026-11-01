# -*- coding: utf-8 -*-
import argparse
import threading
import webbrowser
import time

from . import config as C


def main(argv=None):
    ap = argparse.ArgumentParser(prog="radar", description="رادار ليبيا — منظومة رصد الأخبار الليبية")
    ap.add_argument("--port", type=int, default=C.PORT)
    ap.add_argument("--host", default=C.HOST, help="استخدم 0.0.0.0 للوصول من أجهزة أخرى في الشبكة")
    ap.add_argument("--no-browser", action="store_true", help="لا تفتح المتصفح تلقائياً")
    ap.add_argument("--demo", action="store_true", help="املأ قاعدة بيانات تجريبية (بدون إنترنت)")
    ap.add_argument("--once", action="store_true", help="نفّذ دورة جمع واحدة كاملة ثم اخرج")
    ap.add_argument("--selftest", action="store_true", help="اختبار ذاتي للمحلّلات والمعالجة بدون إنترنت")
    a = ap.parse_args(argv)
    import os as _os
    if _os.environ.get("RADAR_WAIT"):
        time.sleep(2.5)   # إعادة تشغيل ذاتية: انتظر خروج النسخة السابقة
    try:  # لعرض العربية في طرفية ويندوز
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if a.selftest:
        from .selftest import run
        return run()

    from .db import Store
    from .server import App, serve
    if a.demo:
        import os
        C.DATA_DIR = os.path.join(os.path.dirname(C.BASE_DIR), "data_demo")
        C.DB_PATH = os.path.join(C.DATA_DIR, "radar.db")
        C.EXTRA_FEEDS_PATH = os.path.join(C.DATA_DIR, "my_feeds.json")
        from .demo import seed
        store = Store(C.DB_PATH)
        seed(store)
        app = App(store=store, autostart=False)
    elif a.once:
        from .collectors import Collector
        store = Store()
        n = Collector(store).run_cycle("deep")
        print("تم. أخبار جديدة:", n)
        return 0
    else:
        from .server import port_free
        if not port_free(a.host, a.port):
            print("أخباري يعمل بالفعل على المنفذ %d" % a.port)
            return 0
        app = App()
    if not a.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open("http://localhost:%d" % a.port)).start()
    serve(app, a.host, a.port)
    return 0

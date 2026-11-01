# -*- coding: utf-8 -*-
"""تشغيل دورة جمع واحدة داخل GitHub Actions ثم تصدير لقطة ثابتة للواجهة (بلا خادم)."""
import os
import sys
import json
import time
import shutil
import threading
from types import SimpleNamespace
from datetime import datetime, timezone

from . import config as C
from . import collectors as K


def main(out_dir):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    seed = os.path.join(os.path.dirname(C.BASE_DIR), "seed", "my_feeds.json")
    if not os.path.exists(C.EXTRA_FEEDS_PATH) and os.path.exists(seed):
        shutil.copy(seed, C.EXTRA_FEEDS_PATH)
    from .db import Store
    from .server import load_extra_feeds
    store = Store()
    extra = load_extra_feeds()
    col = K.Collector(store, extra)
    now = datetime.now(timezone.utc)
    first = store.stats()["total"] < 200
    mode = "deep" if first else ("full" if now.minute < 20 else "fast")
    t0 = time.time()
    K.log("CI: بدأ (%s)" % mode)
    col.run_cycle(mode, workers=12)
    if mode == "fast":
        col.run_prestige("lane")
    col.run_direct()
    # الاكتشاف كل ساعتين تقريباً
    if now.hour % 2 == 0 and now.minute < 20:
        try:
            from .discover import Discoverer
            app = SimpleNamespace(store=store, extra=extra, collector=col, stop=threading.Event(), refresh=lambda m: None)
            Discoverer(app).run_once(limit=30)
        except Exception as e:
            K.log("CI: الاكتشاف فشل: %s" % str(e)[:100])
    store.housekeeping(keep_days=21)
    from .export import export
    export(store, extra, out_dir)
    K.log("CI: انتهى في %d ث" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "site/data")

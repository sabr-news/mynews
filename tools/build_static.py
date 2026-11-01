# -*- coding: utf-8 -*-
"""يبني مجلد site/ : نسخة ثابتة من الواجهة + أيقونات + manifest.  الاستعمال: python tools/build_static.py site"""
import os, re, sys, json, shutil
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = sys.argv[1] if len(sys.argv) > 1 else "site"
os.makedirs(out, exist_ok=True)
html = open(os.path.join(root, "radar", "static", "index.html"), encoding="utf-8").read()
html = html.replace("__KEYQ__", "")
html = html.replace('"/manifest.webmanifest', '"manifest.webmanifest').replace('"/favicon.ico"', '"icons/icon-32.png"')
html = re.sub(r'(src|href)="/icons/', r'\1="icons/', html)
html = html.replace('openReader(a.href,(title||"").trim(),site)', 'window.open(a.href,"_blank","noopener")')
html = html.replace("<head>", "<head>\n<script src=\"static-api.js\"></script>", 1)
open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)
shutil.copy(os.path.join(root, "tools", "static-api.js"), os.path.join(out, "static-api.js"))
shutil.copytree(os.path.join(root, "radar", "static", "icons"), os.path.join(out, "icons"), dirs_exist_ok=True)
man = {"name": "أخباري", "short_name": "أخباري", "start_url": "./", "scope": "./", "display": "standalone", "dir": "rtl", "lang": "ar",
       "background_color": "#000000", "theme_color": "#000000",
       "icons": [{"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"}]}
json.dump(man, open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False)
open(os.path.join(out, ".nojekyll"), "w").write("")
print("built", out)

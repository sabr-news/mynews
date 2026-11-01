# -*- coding: utf-8 -*-
"""اختبار ذاتي بدون إنترنت للمحلّلات والتصفية والتجميع والبحث."""
import os
import tempfile
from . import process as P
from . import collectors as K
from .db import Store

RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
<item><title>اشتباكات في الزاوية &amp; طرابلس</title><link>https://a.example/1?utm_source=x</link><description>&lt;p&gt;وصف &lt;b&gt;الخبر&lt;/b&gt;&lt;/p&gt;</description><pubDate>Fri, 23 Oct 2026 10:00:00 +0000</pubDate></item>
<item><title>Second - Reuters</title><link>https://b.example/2</link><source url="https://reuters.com">Reuters</source></item>
</channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom entry Libya</title><link rel="alternate" href="https://c.example/3"/><updated>2026-10-23T09:00:00Z</updated><summary>s</summary></entry></feed>"""
GDELT = '{"articles":[{"url":"https://d.example/4","title":"Libya oil output","seendate":"20261023T090000Z","language":"English","domain":"d.example"}]}'
TG = '''<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message_text js-message_text" dir="auto">عاجل: اشتباكات في طرابلس<br/>تفاصيل</div><a class="tgme_widget_message_date" href="https://t.me/x/55"><time datetime="2026-10-23T08:00:00+00:00"></time></a></div>'''

fails = []


def ok(cond, name):
    print(("  ✓ " if cond else "  ✗ ") + name)
    if not cond:
        fails.append(name)


def run():
    print("— المحلّلات")
    r = K.parse_feed(RSS)
    ok(len(r) == 2 and r[0]["title"] == "اشتباكات في الزاوية & طرابلس", "RSS: العنوان والكيانات HTML")
    ok(r[0]["summary"] == "وصف الخبر" and r[0]["published"], "RSS: الملخص والتاريخ")
    g = K._gnews_split_source(dict(r[1]))
    ok(g["title"] == "Second" and g["source_name"] == "Reuters", "جوجل: فصل اسم المصدر")
    a = K.parse_feed(ATOM)
    ok(a and a[0]["url"] == "https://c.example/3" and a[0]["published"], "Atom")
    gd = K.parse_gdelt(GDELT)
    ok(gd and gd[0]["lang"] == "en" and gd[0]["published"], "GDELT")
    tg = K.parse_telegram_web(TG)
    ok(tg and "اشتباكات" in tg[0]["title"] and tg[0]["published"], "تلغرام")

    print("— الصلة بليبيا")
    pos = [("اشتباكات في بنغازي", ""), ("Haftar meets envoy", ""), ("Libye: pétrole", ""), ("利比亚局势", ""),
           ("Ливия: переговоры", ""), ("وقف إنتاج حقل الشرارة", ""), ("الدبيبة والمنفي يلتقيان", ""),
           ("اجتماع في طرابلس حول النفط والحكومة", "")]
    neg = [("Tripoli, Lebanon: protests", ""), ("طرابلس لبنان: احتجاجات", ""), ("سرت الشائعات في المدينة", ""),
           ("The football match ended", ""), ("الزاوية الحادة في الهندسة", "")]
    for t, s in pos:
        ok(P.relevance(t, s)[0] > 0, "يقبل: " + t)
    for t, s in neg:
        ok(P.relevance(t, s)[0] == 0, "يرفض: " + t)
    ok(P.relevance("خبر عام", "", trusted=True)[0] == 1, "trusted يقبل")
    ok(P.relevance("Tripoli Lebanon news", "", trusted=True)[0] == 0, "trusted لا يتجاوز الضجيج")

    print("— اللغة والتصنيف")
    for t, lg in [("اشتباكات في بنغازي", "ar"), ("The government said in a statement", "en"), ("Le gouvernement est en train de", "fr"),
                  ("Il governo ha detto che per", "it"), ("Ливия объявила", "ru"), ("利比亚", "zh"), ("リビア", "ja")]:
        ok(P.detect_lang(t, "") == lg, "لغة %s ← %s" % (lg, t))
    ok(P.categorize("المؤسسة الوطنية للنفط ترفع إنتاج النفط", "") == "economy", "تصنيف اقتصاد")
    ok(P.categorize("اشتباكات مسلحة وقتلى", "") == "security", "تصنيف أمن")
    ok(P.categorize("Migrants boat shipwreck off coast", "") == "migration", "تصنيف هجرة")
    ok(P.urgency("عاجل: انفجار في طرابلس", "") >= 6, "عاجل")
    ok(P.urgency("لقاء ودي", "") == 0, "غير عاجل")
    ok(P.canon_url("https://www.X.com/a/?utm_source=1&id=5#f") == "https://x.com/a?id=5", "تطبيع الرابط")

    print("— التخزين والتجميع والبحث")
    tmp = tempfile.mkdtemp()
    s = Store(os.path.join(tmp, "t.db"))
    from .demo import seed
    n = seed(s)
    ok(n >= 25, "بذر %d عنصراً" % n)
    st = s.stories({}, limit=100)
    ok(st["total"] < n, "التجميع قلّل العدد: %d قصة من %d" % (st["total"], n))
    z = [x for x in st["stories"] if "الزاوية" in x["title"] or "Zawiya" in x["title"]]
    ok(z and z[0]["n_items"] >= 2, "تجميع الزاوية العربي (%s)" % (z[0]["n_items"] if z else 0))
    ex = [x for x in st["stories"] if "Mitiga" in x["title"]]
    ok(ex and ex[0]["n_items"] >= 2 and ex[0]["urgency"] >= 6, "تجميع الإنجليزي + عاجل")
    ok(len(s.stories({"min_urgency": 6})["stories"]) >= 1, "فلتر العاجل")
    dem = [x for x in st["stories"] if "الدبيبة" in x["title"] and "السفير" in x["title"]]
    ok(len(dem) == 1, "لا يدمج أخباراً مختلفة بالخطأ")
    boat = s.stories({"q": "مهاجرين"})
    ok(boat["total"] >= 1, "بحث عربي")
    ok(s.stories({"q": "Haftar"})["total"] >= 1, "بحث إنجليزي")
    ok(s.stories({"q": "الكهرباء", "min_rel": "0"})["total"] >= 1, "بحث بالبادئة/الألف واللام")
    ok(s.stories({"lang": "it"})["total"] >= 2, "فلتر اللغة")
    ok(s.stories({"cat": "economy"})["total"] >= 2, "فلتر التصنيف")
    s.add_watch("Haftar")
    ok(len(s.alerts(0)) >= 1, "التنبيهات")
    ok(not s.add_item({"title": "اشتباكات مسلحة في الزاوية الليبية وسقوط جرحى", "url": "https://example.com/dup", "summary": "", "source": "x", "lang": "ar", "rel": 3}) or True, "إضافة مكررة لا تفشل")
    print("\nالنتيجة:", "كل الاختبارات نجحت ✓" if not fails else "فشل %d: %s" % (len(fails), fails))
    return 1 if fails else 0

# -*- coding: utf-8 -*-
"""بيانات تجريبية لتجربة الواجهة بدون إنترنت. (أخبار وهمية لأغراض العرض فقط)"""
import time
import hashlib
from . import process as P

_NOW = lambda: int(time.time())

DEMO = [
    # (title, summary, source, stype, lang_hint, minutes_ago)
    ("اشتباكات مسلحة في الزاوية الليبية وسقوط جرحى", "اندلعت اشتباكات بين مجموعتين مسلحتين غرب طرابلس الليبية.", "ليبيا الأحرار", "news", "ar", 12),
    ("اشتباكات مسلحة بمدينة الزاوية الليبية وإصابة عدد من المدنيين", "", "الوسط", "news", "ar", 25),
    ("Clashes erupt in Zawiya, Libya, wounding civilians", "Armed groups clashed west of Tripoli, Libya.", "Libya Herald", "news", "en", 20),
    ("Libya: clashes in Zawiya leave several wounded", "", "Reuters", "news", "en", 31),
    ("Affrontements armés à Zawiya en Libye", "", "Le Monde", "news", "fr", 40),
    ("المؤسسة الوطنية للنفط: ارتفاع إنتاج النفط إلى 1.4 مليون برميل يومياً", "", "المؤسسة الوطنية للنفط", "official", "ar", 90),
    ("Libya's NOC says crude output rises to 1.4 million barrels per day", "", "Libya Review", "news", "en", 95),
    ("Libia, il petrolio supera 1,4 milioni di barili al giorno", "", "ANSA", "news", "it", 120),
    ("البعثة الأممية تدعو الأطراف الليبية إلى استئناف الحوار حول القاعدة الدستورية", "", "UNSMIL", "official", "ar", 150),
    ("UN envoy urges Libyan parties to resume dialogue on electoral law", "", "UN News", "official", "en", 160),
    ("Haftar receives Russian delegation in Benghazi", "Talks covered military cooperation.", "Libya Observer", "news", "en", 200),
    ("Хафтар принял российскую делегацию в Бенгази", "", "РИА Новости", "news", "ru", 210),
    ("Libya'da göçmen teknesi battı: çok sayıda kayıp", "Akdeniz'de Libya açıklarında göçmen teknesi alabora oldu.", "Anadolu Ajansı", "news", "tr", 250),
    ("Shipwreck off Libyan coast: dozens of migrants missing", "IOM says a boat sank off the Libyan coast.", "InfoMigrants", "news", "en", 255),
    ("غرق قارب مهاجرين قبالة السواحل الليبية وفقدان العشرات", "", "العربي الجديد", "news", "ar", 262),
    ("انقطاع الكهرباء في طرابلس لساعات طويلة والشركة العامة للكهرباء تعتذر", "", "أخبار ليبيا 24", "news", "ar", 300),
    ("المصرف المركزي الليبي يعلن تعديل سعر الصرف الرسمي للدينار", "", "بوابة الوسط", "news", "ar", 340),
    ("Libya central bank adjusts official dinar exchange rate", "", "Libya Update", "news", "en", 350),
    ("Libyen: Ölproduktion wieder aufgenommen nach Blockade von Sharara-Feld", "", "Deutsche Welle", "news", "de", 400),
    ("利比亚东部班加西举行经济论坛", "", "新华社", "news", "zh", 420),
    ("Dbeibah meets Turkish ambassador to discuss bilateral agreements", "", "Libya Observer", "news", "en", 460),
    ("الدبيبة يلتقي السفير التركي لبحث الاتفاقيات الثنائية", "", "الوسط", "news", "ar", 470),
    ("ليبيا: فيضانات وسيول في درنة وتحذيرات من الأرصاد", "", "ليبيا الأحرار", "news", "ar", 520),
    ("Libia, il Parlamento di Tobruk approva il bilancio", "", "Agenzia Nova", "news", "it", 600),
    ("لقطة من تلغرام: أنباء عن إغلاق ميناء الحريقة", "مصدر غير مؤكد على قناة عامة.", "قناة محلية", "social", "ar", 35),
    ("Libye: la Cour pénale internationale évoque de nouveaux mandats d'arrêt", "", "RFI", "news", "fr", 700),
    ("ليبيا: منتخب ليبيا يفوز على نظيره في تصفيات كأس أمم أفريقيا", "", "ليبيا الأحرار", "news", "ar", 800),
    ("Libya internet outage hits Tripoli and Misrata", "Telecom company blames cable damage.", "NetBlocks", "analysis", "en", 900),
    ("عاجل: انفجار قرب مطار معيتيقة في طرابلس وتعليق الرحلات", "تفاصيل أولية عن الانفجار.", "ليبيا الأحرار", "news", "ar", 6),
    ("Breaking: explosion near Mitiga airport in Tripoli, flights suspended", "", "Libya Observer", "news", "en", 9),
    ("Explosion near Mitiga airport Tripoli, flights halted", "", "Reuters", "news", "en", 14),
    # ضجيج يجب أن يُرفض في الاستيعاب الحقيقي (للتجربة فقط في selftest)
]


def seed(store):
    n = 0
    for title, summ, src, st, lg, mins in DEMO:
        rel, matched = P.relevance(title, summ, trusted=True)
        rec = {"title": title, "url": "https://example.com/demo/" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:10], "summary": summ,
               "source": src, "stype": st, "via": "demo", "lang": P.detect_lang(title + " " + summ, lg),
               "published": _NOW() - mins * 60, "rel": max(rel, 1), "matched": matched}
        if store.add_item(rec):
            n += 1
    store.record_health("RSS/Libya Herald (تجريبي)", "rss", True, 12, 3)
    store.record_health("GoogleNews/ar (تجريبي)", "googlenews", True, 40, 9)
    store.record_health("GDELT/all (تجريبي)", "gdelt", False, err="وضع تجريبي: لا اتصال")
    return n

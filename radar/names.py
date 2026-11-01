# -*- coding: utf-8 -*-
"""أسماء المصادر بالعربية. ما لم يرد هنا يُترجم تلقائياً ويُخزَّن."""
import re

_AR = re.compile(r"[؀-ۿ]")

SOURCE_AR = {
    "reuters": "رويترز", "bbc": "بي بي سي", "bbc news": "بي بي سي", "bbc news عربي": "بي بي سي عربي", "bbc arabic": "بي بي سي عربي",
    "cnn": "سي إن إن", "al jazeera": "الجزيرة", "al jazeera english": "الجزيرة", "aljazeera": "الجزيرة", "aljazeera.net": "الجزيرة",
    "the guardian": "الغارديان", "the new york times": "نيويورك تايمز", "new york times": "نيويورك تايمز",
    "the washington post": "واشنطن بوست", "washington post": "واشنطن بوست", "bloomberg": "بلومبرغ", "bloomberg.com": "بلومبرغ",
    "financial times": "فاينانشال تايمز", "the economist": "ذي إيكونوميست", "afp": "وكالة الصحافة الفرنسية",
    "agence france-presse": "وكالة الصحافة الفرنسية", "associated press": "أسوشيتد برس", "ap news": "أسوشيتد برس", "ap": "أسوشيتد برس",
    "anadolu ajansı": "وكالة الأناضول", "anadolu agency": "وكالة الأناضول", "aa": "وكالة الأناضول", "xinhua": "شينخوا",
    "xinhua news agency": "شينخوا", "新华社": "شينخوا", "ria novosti": "ريا نوفوستي", "риа новости": "ريا نوفوستي", "tass": "تاس",
    "тасс": "تاس", "sputnik": "سبوتنيك", "rt": "روسيا اليوم", "rt arabic": "روسيا اليوم", "euronews": "يورونيوز",
    "france 24": "فرانس 24", "rfi": "إذاعة فرنسا الدولية", "le monde": "لوموند", "le figaro": "لو فيغارو", "libération": "ليبراسيون",
    "ansa": "أنسا", "ansa.it": "أنسا", "agenzia nova": "وكالة نوفا", "la repubblica": "لا ريبوبليكا", "corriere della sera": "كورييري ديلا سيرا",
    "dw": "دويتشه فيله", "deutsche welle": "دويتشه فيله", "der spiegel": "دير شبيغل", "middle east eye": "ميدل إيست آي",
    "middle east monitor": "ميدل إيست مونيتور", "al-monitor": "المونيتور", "the times of israel": "تايمز أوف إسرائيل",
    "ynetnews": "واي نت", "haaretz": "هآرتس", "the jerusalem post": "جيروزاليم بوست", "arab news": "عرب نيوز",
    "asharq al-awsat": "الشرق الأوسط", "al arabiya": "العربية", "al arabiya english": "العربية", "sky news arabia": "سكاي نيوز عربية",
    "sky news": "سكاي نيوز", "al-ahram": "الأهرام", "ahram online": "الأهرام", "daily news egypt": "ديلي نيوز مصر",
    "the africa report": "ذا أفريكا ريبورت", "africanews": "أفريكا نيوز", "allafrica.com": "أول أفريكا", "allafrica": "أول أفريكا",
    "infomigrants": "إنفو مايغرانتس", "iom": "المنظمة الدولية للهجرة", "un news": "أخبار الأمم المتحدة", "un news - middle east": "أخبار الأمم المتحدة",
    "unsmil": "بعثة الأمم المتحدة في ليبيا", "unsmil.unmissions.org": "بعثة الأمم المتحدة في ليبيا", "reliefweb": "ريليف ويب",
    "libya herald": "ليبيا هيرالد", "libyaherald.com": "ليبيا هيرالد", "libya observer": "ليبيا أوبزرفر", "libyaobserver.ly": "ليبيا أوبزرفر",
    "libya review": "ليبيا ريفيو", "libyareview.com": "ليبيا ريفيو", "libya update": "ليبيا أبديت", "libyaupdate.com": "ليبيا أبديت",
    "libya update news": "ليبيا أبديت", "libya business news": "ليبيا بيزنس نيوز", "libyaakhbar.com": "ليبيا أخبار", "libya24.tv": "ليبيا 24",
    "alwasat.ly": "بوابة الوسط", "alwasat": "بوابة الوسط", "lana.gov.ly": "وكالة الأنباء الليبية", "lana": "وكالة الأنباء الليبية",
    "noc.ly": "المؤسسة الوطنية للنفط", "cbl.gov.ly": "مصرف ليبيا المركزي", "almarsad.co": "المرصد", "libyaalahrar.net": "ليبيا الأحرار",
    "218tv.net": "قناة 218", "alwatan.ly": "الوطن الليبية", "reddit": "ريديت", "reddit.com": "ريديت", "mastodon": "ماستودون",
    "bing news": "بينغ نيوز", "google news": "أخبار جوجل", "gdelt": "غديلت", "wikinews": "ويكي نيوز", "facebook": "فيسبوك", "x": "إكس",
    "netblocks": "نت بلوكس", "crisis group": "مجموعة الأزمات الدولية", "international crisis group": "مجموعة الأزمات الدولية",
    "atlantic council": "المجلس الأطلسي", "chatham house": "تشاتام هاوس", "carnegie endowment": "مؤسسة كارنيغي",
    "yeni şafak": "يني شفق", "hürriyet": "حرييت", "daily sabah": "ديلي صباح", "trt haber": "تي آر تي", "trt world": "تي آر تي وورلد",
    "ekathimerini": "كاثيميريني", "kathimerini": "كاثيميريني", "to vima": "تو فيما", "το βήμα": "تو فيما",
}


def has_arabic(s):
    return bool(_AR.search(s or ""))


def key(name):
    return (name or "").strip().lower()


def lookup(name):
    """يرجع الاسم العربي من الخريطة أو None."""
    if has_arabic(name):
        return name
    k = key(name)
    if k in SOURCE_AR:
        return SOURCE_AR[k]
    if k.startswith("www."):
        k2 = k[4:]
        if k2 in SOURCE_AR:
            return SOURCE_AR[k2]
    if k.startswith("reddit"):
        return "ريديت" + (" — " + name.split(" ", 1)[1] if " " in name else "")
    if k.startswith("mastodon"):
        return "ماستودون " + name.split(" ", 1)[1] if " " in name else "ماستودون"
    return None


# ---------- كتابة عربية تقريبية للأسماء اللاتينية غير المعروفة ----------
_DIG = [("sch", "ش"), ("sh", "ش"), ("ch", "تش"), ("th", "ث"), ("ph", "ف"), ("kh", "خ"), ("gh", "غ"), ("ck", "ك"), ("qu", "كو"),
        ("ou", "و"), ("oo", "و"), ("ee", "ي"), ("ea", "ي"), ("ç", "ش"), ("ş", "ش"), ("ğ", "غ"), ("ı", "ي"), ("ö", "ō"), ("ü", "ū")]
_LET = dict(a="ا", b="ب", c="ك", d="د", e="ي", f="ف", g="ج", h="ه", i="ي", j="ج", k="ك", l="ل", m="م", n="ن", o="و", p="ب",
            q="ق", r="ر", s="س", t="ت", u="و", v="ف", w="و", x="كس", y="ي", z="ز")
_TLD = re.compile(r"\.(com|net|org|gr|tr|info|ma|ly|it|fr|de|es|ru|uk|co|tv|pro|kz|az|cy|mx|my|sn|eu|news)(\.[a-z]{2})?$", re.I)
_WORDS = {"dw": "دي دبليو", "bbc": "بي بي سي", "cnn": "سي إن إن", "afp": "فرانس برس", "ap": "أسوشيتد برس", "rfi": "إذاعة فرنسا الدولية", "news": "نيوز", "the": "", "times": "تايمز", "daily": "ديلي", "post": "بوست", "press": "برس", "gazete": "غازيتي",
          "gazetesi": "غازيتيسي", "haber": "هابر", "haberler": "هابرلر", "journal": "جورنال", "info": "إنفو", "africa": "أفريقيا",
          "libya": "ليبيا", "observer": "أوبزرفر", "today": "اليوم", "egypt": "مصر", "world": "وورلد", "business": "بيزنس",
          "standard": "ستاندرد", "radio": "راديو", "tv": "تي في", "agency": "وكالة", "agence": "وكالة", "presse": "الصحافة",
          "de": "دي", "la": "لا", "le": "لو", "el": "إل", "il": "إل", "al": "ال"}


def translit(name):
    """كتابة عربية تقريبية (نطقية) لاسم لاتيني؛ تُستعمل حين لا يوجد اسم عربي معروف."""
    s = _TLD.sub("", (name or "").strip())
    out = []
    for w in re.split(r"[\s\-_.+/]+", s):
        if not w:
            continue
        lw = w.lower()
        if lw in _WORDS:
            if _WORDS[lw]:
                out.append(_WORDS[lw])
            continue
        r, i = "", 0
        while i < len(lw):
            for d, a in _DIG:
                if lw.startswith(d, i):
                    r += a
                    i += len(d)
                    break
            else:
                c = lw[i]
                if i == 0 and c in "aeiou":
                    r += "ا" if c in "ao" else "إ"
                elif i + 1 < len(lw) and lw[i + 1] == c and c not in "aeiou":
                    pass
                else:
                    r += _LET.get(c, c if c.isdigit() else "")
                i += 1
        out.append(r)
    return " ".join(x for x in out if x) or name


def display(name):
    """الاسم العربي للعرض: معروف، أو عربي أصلاً، أو كتابة نطقية."""
    v = lookup(name)
    if v:
        return v
    if re.search(r"[A-Za-zçşğıöüÇŞĞİÖÜ]", name or ""):
        return translit(name)
    return name


# ---- أسماء إضافية للمراجع الدولية والمنصات المتكررة
SOURCE_AR.update({
    "middle east online": "ميدل إيست أونلاين", "qatar news agency": "وكالة الأنباء القطرية", "qna": "وكالة الأنباء القطرية",
    "daily sabah": "ديلي صباح", "hurriyet daily news": "حرييت ديلي نيوز", "hürriyet daily news": "حرييت ديلي نيوز", "xinhuanet": "شينخوا",
    "xinhuanet.com": "شينخوا", "the libya observer": "ليبيا أوبزرفر", "the libya herald": "ليبيا هيرالد", "wall street journal": "وول ستريت جورنال",
    "the wall street journal": "وول ستريت جورنال", "wsj": "وول ستريت جورنال", "the national": "ذا ناشيونال", "the national news": "ذا ناشيونال",
    "foreign policy": "فورين بوليسي", "foreign affairs": "فورين أفيرز", "chatham house": "تشاتام هاوس", "international crisis group": "مجموعة الأزمات الدولية",
    "crisis group": "مجموعة الأزمات الدولية", "carnegie endowment for international peace": "كارنيغي", "brookings": "بروكنغز",
    "brookings institution": "بروكنغز", "atlantic council": "المجلس الأطلسي", "council on foreign relations": "مجلس العلاقات الخارجية",
    "csis": "CSIS", "rand": "راند", "rand corporation": "راند", "the washington institute": "معهد واشنطن", "washington institute": "معهد واشنطن",
    "human rights watch": "هيومن رايتس ووتش", "hrw": "هيومن رايتس ووتش", "amnesty international": "منظمة العفو الدولية", "ohchr": "مفوضية حقوق الإنسان",
    "unhcr": "مفوضية اللاجئين", "international committee of the red cross": "الصليب الأحمر", "icrc": "الصليب الأحمر", "world bank": "البنك الدولي",
    "international monetary fund": "صندوق النقد الدولي", "imf": "صندوق النقد الدولي", "european council": "المجلس الأوروبي", "politico europe": "بوليتيكو أوروبا",
    "politico": "بوليتيكو", "time": "تايم", "the times": "ذا تايمز", "the telegraph": "ديلي تلغراف", "ansa english": "أنسا", "agenzia ansa": "أنسا",
    "il sole 24 ore": "إل سولي 24 أوري", "frankfurter allgemeine": "فرانكفورتر ألغماينه", "faz": "فرانكفورتر ألغماينه", "el país": "إل باييس",
    "el pais": "إل باييس", "jeune afrique": "جون أفريك", "trt world": "تي آر تي وورلد", "trt": "تي آر تي", "tass news agency": "تاس",
    "the times of india": "تايمز أوف إنديا", "uanews": "يو إيه نيوز", "ua.news": "يو إيه نيوز", "fakti.bg": "فاكتي", "haberler.com": "هابرلر",
    "us muslims": "يو إس مسلمز",
})
for _d, _n, _k, _l in __import__("radar.config", fromlist=["PRESTIGE"]).PRESTIGE:
    SOURCE_AR.setdefault(_d, _n)

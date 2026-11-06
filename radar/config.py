# -*- coding: utf-8 -*-
"""
إعدادات «رادار ليبيا» — كل شيء هنا قابل للتعديل دون لمس بقية الكود.
"""
import os

APP_NAME = "أخباري"
APP_NAME_EN = "My News"
APP_VERSION = "2.2"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("RADAR_DATA", os.path.join(os.path.dirname(BASE_DIR), "data"))
DB_PATH = os.path.join(DATA_DIR, "radar.db")
EXTRA_FEEDS_PATH = os.path.join(DATA_DIR, "my_feeds.json")   # مصادر يضيفها المستخدم من الواجهة

SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")


def load_settings():
    try:
        import json as _j
        with open(SETTINGS_PATH, encoding="utf-8") as _f:
            return _j.load(_f)
    except Exception:
        return {}


HOST = os.environ.get("RADAR_HOST") or ("0.0.0.0" if load_settings().get("lan") else "127.0.0.1")
PORT = int(os.environ.get("RADAR_PORT") or os.environ.get("PORT") or "8765")

# كل كم دقيقة تُجمع الأخبار (الجامع العام GDELT محدود بطلب كل ~5 ثوانٍ فنراعي ذلك)
CYCLE_MINUTES = int(os.environ.get("RADAR_CYCLE_MIN", "10"))
HTTP_TIMEOUT = 25
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
ALT_UAS = ["Feedly/1.0 (+http://www.feedly.com/fetcher.html; like FeedFetcher-Google)", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"]

# ---------------------------------------------------------------------------
# قاموس الكيانات الليبية (متعدد اللغات).  strong = يكفي وحده لاعتبار الخبر ليبياً
# weak = غامض (مثل «طرابلس» قد تكون في لبنان) فيحتاج قرينة إضافية.
# ---------------------------------------------------------------------------
STRONG_TERMS = [
    # الدولة
    "ليبيا", "ليبي", "ليبية", "الليبي", "الليبية", "الليبيين", "الليبيون",
    "libya", "libyan", "libyans", "libye", "libyen", "libyenne", "libia", "libico", "libica",
    "libyen", "libyer", "libië", "libie", "libië", "libia", "líbia", "libië",
    "ливия", "ливии", "ливийск", "лівія", "libya'", "lıbya", "libya’",
    "利比亚", "リビア", "리비아", "לוב", "לוּב", "लीबिया", "লিবিয়া", "لیبی", "لیبیا",
    "libja", "libya", "libië", "λιβύη", "λιβύης",
    # مدن ومناطق (غير ملتبسة نسبياً)
    "بنغازي", "benghazi", "bengasi", "bengazi", "бенгази", "班加西", "ベンガジ",
    "مصراتة", "misrata", "misurata", "мисурата", "misrata",
    "sirte", "syrte", "сирт",
    "طبرق", "tobruk", "tobrouk", "тобрук",
    "سبها", "sabha libya", "sebha", "себха",
    "zawiya libya", "zawiyah libya", "الزاوية الليبية",
    "زليتن", "zliten", "zlitan",
    "درنة", "derna", "darnah", "дерна",
    "khoms libya", "al-khums", "مدينة الخمس",
    "غريان", "gharyan",
    "ترهونة", "tarhuna", "tarhouna",
    "البيضاء الليبية", "al-bayda libya",
    "أجدابيا", "ajdabiya", "agedabia",
    "kufra", "al-kufra", "واحة الكفرة",
    "غدامس", "ghadames", "ghadamis",
    "ghat libya",
    "فزان", "fezzan", "fezzân",
    "برقة", "cyrenaica", "cyrénaïque", "cirenaica",
    "طرابلس الليبية", "tripoli libya", "tripoli, libya", "tripolitania", "tripolitaine", "tripolitania",
    "الجفرة", "jufra", "al-jufra",
    "الجبل الغربي", "nafusa", "nafusa mountains",
    "مرزق", "murzuq", "murzuk",
    "أوباري", "ubari",
    "رأس لانوف", "ras lanuf", "ras lanouf",
    "السدرة", "es sider", "es-sider",
    "حقل الشرارة", "sharara oil", "el sharara", "al-sharara",
    "حقل الفيل", "el feel", "elephant oil field",
    "مليتة", "mellitah", "mellita",
    "الزويتينة", "zueitina",
    "البريقة", "brega", "marsa el brega",
    "المؤسسة الوطنية للنفط", "libya national oil corporation", "noc libya",
    "مصرف ليبيا المركزي", "central bank of libya", "banque centrale de libye",
    "المجلس الرئاسي الليبي", "libyan presidential council", "gnu libya",
    "حكومة الوحدة الوطنية", "government of national unity", "gnu tripoli",
    "حكومة الاستقرار", "government of national stability", "gns libya",
    "بعثة الأمم المتحدة للدعم في ليبيا", "unsmil", "un support mission in libya",
    "الجيش الوطني الليبي", "libyan national army", "libyan arab armed forces", "lnA libya",
    "القيادة العامة للقوات المسلحة", "ghat libya",
    "مجلس النواب الليبي", "libyan house of representatives", "hor libya",
    "المجلس الأعلى للدولة", "high council of state libya", "hcs libya",
    "ليبيا الأحرار", "libya observer", "libya herald", "libya review", "libya update", "libya akhbar",
    "الدبيبة", "dbeibah", "dbeibeh", "dbeiba", "dabaiba", "dbeibah", "дбейба",
    "حفتر", "haftar", "haftâr", "хафтар", "哈夫塔尔",
    "محمد المنفي", "menfi libya", "mohamed al-menfi", "mohamed menfi",
    "عقيلة صالح", "aguila saleh", "aguila saleh issa", "aguila salah",
    "خالد المشري", "khaled al-mishri", "khaled mishri", "khalid al-mishri",
    "باتيلي", "bathily libya", "abdoulaye bathily",
    "تيتيه", "stephanie williams libya", "hanna tetteh", "tetteh libya",
    "سيف الإسلام القذافي", "saif al-islam gaddafi", "saif al-islam kadhafi", "saif al islam",
    "القذافي", "gaddafi", "kadhafi", "qaddafi", "qadhafi", "gheddafi", "каддафи", "卡扎菲", "gadafi",
    "صدام حفتر", "saddam haftar",
    "الزنتان", "zintan", "zintani",
    "جهاز الردع الخاص", "radaa libya", "rada force", "deterrence apparatus libya",
    "جهاز الردع", "special deterrence force",
    "جهاز الأمن الداخلي", "libya internal security agency",
    "قوات الجيش الوطني", "operation dignity", "operation volcano of anger",
    "مهاجرون ليبيا", "migrants libya", "libya migrants", "libyan coast guard", "libyan coastguard",
    "خفر السواحل الليبي", "garde-côtes libyens", "guardia costiera libica",
    "مجلس الأمن ليبيا", "libya sanctions", "libya arms embargo", "irini", "operation irini",
    "الحدود الليبية", "libya border", "libyan border", "libya-tunisia", "libya-egypt border",
    "رأس جدير", "ras jedir", "ras ajdir", "ras jdir",
    "امساعد", "emsaed", "musaid",
    "mitiga", "معيتيقة", "mitiga airport",
    "mattei libya", "eni libya", "wintershall libya", "waha oil", "الواحة للنفط",
    "agoco", "arabian gulf oil company", "zallaf", "harouge", "الهروج",
    "الخليج العربي للنفط", "سرت للنفط", "sirte oil",
    "libyan dinar", "الدينار الليبي", "dinar libyen", "dinaro libico",
    "libya election", "انتخابات ليبيا", "élections libye", "elezioni libia", "libya elections",
]

# مواقع ملتبسة: لا تكفي وحدها (قد تكون في بلد آخر أو كلمة عادية)
GEO_WEAK_TERMS = [
    "طرابلس", "tripoli", "tripolis", "триполи", "trablus", "trípoli",
    "سرت", "الزاوية", "الخمس", "الكفرة", "sirt", "zawiya", "khoms",
    "البيضاء", "bayda", "al-bayda",
    "الجنوب الليبي", "southern libya",
    "الدبيبة", "المنفي", "المشري", "الردع", "الشرارة", "الفيل",
]
# سياق يرفع الثقة عند اقترانه بموقع ملتبس
CONTEXT_TERMS = [
    "نفط", "oil", "pétrole", "petrolio", "حفتر", "haftar", "الدبيبة", "dbeibah", "حكومة", "government",
    "اشتباكات", "clashes", "مهاجرين", "migrants", "المصرف المركزي", "central bank", "الأمم المتحدة", "united nations", "un ",
    "فاغنر", "wagner", "africa corps", "الجيش", "army", "بعثة", "mission", "مجلس", "council", "libya", "ليبيا",
]

# نصوص تُستبعد (ضجيج شائع): مثلاً طرابلس لبنان
NOISE_HINTS = [
    "tripoli lebanon", "tripoli, lebanon", "طرابلس لبنان", "طرابلس - لبنان", "طرابلس اللبنانية",
    "tripoli liban", "tripoli, liban", "north lebanon", "شمال لبنان",
    "tripoli greece", "tripoli peloponnese",
]

# ---------------------------------------------------------------------------
# التصنيفات (قواعد كلمات مفتاحية متعددة اللغات). المفتاح: (id, اسم عربي)
# ---------------------------------------------------------------------------
CATEGORIES = {
    "security": ("أمن وعسكري", [
        "اشتباك", "اشتباكات", "قصف", "هجوم", "اغتيال", "اختطاف", "خطف", "ميليشيا", "مسلح", "مسلحة", "تفجير", "انفجار",
        "قتلى", "جرحى", "طائرة مسيرة", "مسيّرة", "جيش", "قوات", "عسكري", "أمني", "داعش", "إرهاب",
        "clash", "clashes", "shelling", "attack", "assassinat", "abduct", "kidnap", "militia", "armed group", "explosion",
        "killed", "wounded", "drone", "troops", "military", "security forces", "isis", "terror",
        "affrontements", "tirs", "armée", "milice", "scontri", "esplosione", "esercito", "milizia", "morti", "feriti",
        "çatışma", "saldırı", "ölü", "yaralı", "askeri", "бой", "столкновен", "обстрел", "взрыв", "военн", "боевик",
    ]),
    "politics": ("سياسة", [
        "حكومة", "مجلس النواب", "المجلس الأعلى", "المجلس الرئاسي", "انتخابات", "حوار", "مبادرة", "دستور", "رئيس", "وزير",
        "برلمان", "توافق", "تسوية", "الأمم المتحدة", "بعثة", "مبعوث", "قاعدة دستورية", "استفتاء", "مجلس الأمن", "المجلس", "الإخوان", "تعيين", "تكليف", "استقالة",
        "government", "parliament", "house of representatives", "high council", "presidential council", "election",
        "dialogue", "roadmap", "constitution", "minister", "president", "un envoy", "unsmil", "negotiation", "talks",
        "gouvernement", "parlement", "élections", "constitution", "ministre", "governo", "parlamento", "elezioni",
        "hükümet", "meclis", "seçim", "правительств", "парламент", "выбор", "переговор",
    ]),
    "economy": ("نفط واقتصاد", [
        "نفط", "نفطي", "غاز", "إنتاج النفط", "برميل", "المؤسسة الوطنية للنفط", "المصرف المركزي", "الدينار", "سعر الصرف",
        "الدولار", "ميزانية", "اقتصاد", "سيولة", "مصارف", "بنوك", "تضخم", "استثمار", "ميناء", "حقل", "خط أنابيب", "المحافظ", "العملة", "احتياطيات", "الاحتياطي", "المتقاعدين", "المرتبات", "رواتب", "الجمارك", "ضرائب",
        "oil", "crude", "gas", "barrel", "production", "national oil corporation", "noc", "central bank", "dinar", "exchange rate",
        "budget", "economy", "liquidity", "bank", "inflation", "investment", "port", "oilfield", "pipeline", "refinery",
        "pétrole", "gaz", "banque centrale", "économie", "petrolio", "gas", "banca centrale", "economia",
        "petrol", "doğalgaz", "merkez bankası", "нефть", "газ", "экономик", "банк",
    ]),
    "migration": ("هجرة ولاجئون", [
        "مهاجر", "مهاجرين", "هجرة", "لاجئ", "لاجئين", "قارب", "غرق", "قوارب", "خفر السواحل", "ترحيل", "اتجار بالبشر",
        "migrant", "migrants", "migration", "refugee", "asylum", "boat", "shipwreck", "coast guard", "deport", "smuggling", "trafficking",
        "migrants", "réfugiés", "naufrage", "migranti", "sbarchi", "naufragio",
        "göçmen", "mülteci", "мигрант", "беженц",
    ]),
    "humanitarian": ("إنساني وصحة وكوارث", [
        "إنساني", "فيضان", "سيول", "إعصار", "زلزال", "كارثة", "صحة", "مستشفى", "وباء", "لقاح", "نازحين", "مفقودين", "إغاثة",
        "humanitarian", "flood", "storm", "earthquake", "disaster", "health", "hospital", "outbreak", "displaced", "aid", "relief", "daniel",
        "humanitaire", "inondation", "umanitario", "alluvione", "sel", "insani", "наводнен", "гуманитар",
    ]),
    "justice": ("قضاء وحقوق إنسان", [
        "نيابة", "محكمة", "قضاء", "حكم", "اعتقال", "سجن", "تعذيب", "حقوق الإنسان", "احتجاز", "اختفاء قسري", "جنائية دولية",
        "prosecutor", "court", "judge", "verdict", "arrest", "detention", "prison", "torture", "human rights", "icc", "enforced disappearance",
        "tribunal", "arrestation", "tribunale", "arresto", "mahkeme", "tutuklama", "суд", "арест",
    ]),
    "diplomacy": ("علاقات خارجية", [
        "سفير", "سفارة", "زيارة", "اتفاقية", "مذكرة تفاهم", "تركيا", "مصر", "روسيا", "إيطاليا", "الاتحاد الأوروبي", "الإمارات", "قطر", "الجزائر", "تونس",
        "ambassador", "embassy", "visit", "agreement", "memorandum", "turkey", "egypt", "russia", "italy", "european union", "uae", "qatar", "algeria", "tunisia",
        "ambassadeur", "accord", "ambasciatore", "accordo", "büyükelçi", "anlaşma", "посол", "соглашени",
        "ترسيم", "الحدود البحرية", "المذكرة", "memorandum", "mutabakat", "maritime", "μνημόνιο", "τουρκολιβυκό", "μνημονιο", "ΟΗΕ", "greece", "اليونان", "قبرص", "yunanistan", "حلف", "تحالف",
    ]),
    "society": ("مجتمع وخدمات", [
        "كهرباء", "انقطاع", "وقود", "غاز الطهي", "مياه", "تعليم", "جامعة", "مدرسة", "طرق", "أسعار", "رواتب", "مواطنين", "بلدية", "طقس", "أمطار",
        "electricity", "blackout", "power cut", "fuel", "water", "education", "university", "school", "roads", "prices", "salaries", "municipal", "weather",
        "électricité", "carburant", "elettricità", "carburante", "elektrik", "yakıt", "электричеств", "топлив",
    ]),
    "sports_culture": ("رياضة وثقافة", [
        "كرة القدم", "الدوري", "منتخب", "نادي", "مباراة", "ثقافة", "فن", "مهرجان", "آثار", "سياحة", "تراث",
        "football", "league", "national team", "club", "match", "culture", "festival", "archaeolog", "tourism", "heritage", "unesco",
        "calcio", "partita", "futbol", "maç", "футбол", "матч",
    ]),
    "tech": ("تقنية واتصالات", [
        "إنترنت", "اتصالات", "الألياف", "تقنية", "ذكاء اصطناعي", "هاتف", "سيبراني", "اختراق",
        "internet", "telecom", "fiber", "technology", "cyber", "hack", "starlink", "mobile network",
    ]),
}
DEFAULT_CATEGORY = ("other", "أخرى")

# كلمات رفع الأولوية للعاجل (تُجمع مع عدد المصادر التي تؤكد الخبر)
URGENT_TERMS = [
    "عاجل", "عاجلاً", "اشتباكات", "اشتباك", "انفجار", "اغتيال", "قتلى", "غرق", "هجوم", "إغلاق حقل", "إغلاق ميناء",
    "قصف", "اختطاف", "حريق", "فيضانات", "انقلاب", "طوارئ", "حظر التجول", "إطلاق نار", "مسيرة",
    "breaking", "urgent", "clashes", "explosion", "assassination", "killed", "shipwreck", "attack", "shelling", "kidnapped",
    "force majeure", "oil blockade", "shut down oilfield", "state of emergency", "curfew", "gunfire", "drone strike", "coup",
    "affrontements", "explosion", "attentat", "naufrage", "scontri", "esplosione", "naufragio",
    "çatışma", "patlama", "saldırı", "срочно", "столкновения", "взрыв", "нападение",
]

# ---------------------------------------------------------------------------
# الجامعات العامة: لغات واستعلامات. كل استعلام يُطبَّق على كل لغة ذات صلة.
# ---------------------------------------------------------------------------
# (رمز اللغة، hl لجوجل، gl/ceid، اسم GDELT للغة، استعلامات بتلك اللغة)
LANGS = [
    ("ar", "ar", "LY:ar", "arabic", ["ليبيا", "طرابلس ليبيا", "بنغازي", "الدبيبة", "حفتر", "المؤسسة الوطنية للنفط", "المصرف المركزي الليبي",
                                     "مجلس النواب الليبي", "المجلس الأعلى للدولة", "البعثة الأممية ليبيا", "المهاجرين ليبيا", "الجيش الوطني الليبي",
                                     "مصراتة", "سبها", "الزاوية", "سرت", "طبرق", "درنة", "الجنوب الليبي", "الدينار الليبي"]),
    ("en", "en", "US:en", "english", ["Libya", "Libyan", "Tripoli Libya", "Benghazi", "Dbeibah", "Haftar", "Libya oil", "Libya central bank",
                                      "Libya UN mission", "Libya migrants", "Libyan National Army", "Misrata", "Sabha", "Libya election", "Libya Gaddafi"]),
    ("fr", "fr", "FR:fr", "french", ["Libye", "Libyen", "Tripoli Libye", "Benghazi", "Dbeibah", "Haftar", "pétrole Libye", "migrants Libye"]),
    ("it", "it", "IT:it", "italian", ["Libia", "libico", "Tripoli Libia", "Bengasi", "Dbeibah", "Haftar", "migranti Libia", "petrolio Libia"]),
    ("es", "es", "ES:es", "spanish", ["Libia", "libio", "Trípoli Libia", "Bengasi", "Dbeiba", "Hafter"]),
    ("de", "de", "DE:de", "german", ["Libyen", "libysch", "Tripolis Libyen", "Bengasi", "Dbeiba", "Haftar", "Migranten Libyen"]),
    ("tr", "tr", "TR:tr", "turkish", ["Libya", "Trablus Libya", "Bingazi", "Dibeybe", "Hafter", "Libya petrol"]),
    ("ru", "ru", "RU:ru", "russian", ["Ливия", "ливийский", "Триполи Ливия", "Бенгази", "Дбейба", "Хафтар", "нефть Ливия"]),
    ("zh-CN", "zh-CN", "CN:zh-Hans", "chinese", ["利比亚", "的黎波里 利比亚", "班加西", "哈夫塔尔"]),
    ("fa", "fa", "IR:fa", "persian", ["لیبی", "طرابلس لیبی"]),
    ("pt", "pt-BR", "BR:pt-419", "portuguese", ["Líbia", "Trípoli Líbia", "Haftar"]),
    ("nl", "nl", "NL:nl", "dutch", ["Libië", "Haftar", "Tripoli Libië"]),
    ("el", "el", "GR:el", "greek", ["Λιβύη", "Χαφτάρ"]),
    ("he", "iw", "IL:he", "hebrew", ["לוב", "חפטר"]),
    ("ja", "ja", "JP:ja", "japanese", ["リビア"]),
    ("ko", "ko", "KR:ko", "korean", ["리비아"]),
    ("hi", "hi", "IN:hi", "", ["लीबिया"]),
    ("uk", "uk", "UA:uk", "ukrainian", ["Лівія"]),
    ("pl", "pl", "PL:pl", "polish", ["Libia"]),
    ("sv", "sv", "SE:sv", "swedish", ["Libyen"]),
]

# إصدارات عربية إضافية (حسب البلد) لأن نتائج جوجل تختلف بين بلد وآخر
AR_EDITIONS = ["EG:ar", "SA:ar", "AE:ar", "TN:ar", "DZ:ar", "MA:ar", "QA:ar", "JO:ar", "LB:ar", "IQ:ar"]
EN_EDITIONS = ["GB:en", "AU:en", "CA:en", "IN:en", "ZA:en", "NG:en", "EG:en"]

# ---------------------------------------------------------------------------
# مصادر مباشرة (RSS/Atom). الجامع يبلّغ عن حالة كل مصدر، وما لا يعمل يظهر في لوحة الصحة.
# يمكنك إضافة المزيد من الواجهة دون تعديل هذا الملف.
# type: news | official | social | analysis | ngo
# ---------------------------------------------------------------------------
DIRECT_FEEDS = [
    {"name": "Libya Herald", "url": "https://libyaherald.com/feed/", "lang": "en", "type": "news", "all": True},
    {"name": "Libya Update", "url": "https://libyaupdate.com/feed/", "lang": "en", "type": "news", "all": True},
    {"name": "Libya Review", "url": "https://libyareview.com/feed/", "lang": "en", "type": "news", "all": True},
    {"name": "أخبار ليبيا 24", "url": "https://libya24.tv/feed/", "lang": "ar", "type": "news", "all": True},
    {"name": "العربي الجديد - ليبيا", "url": "https://www.alaraby.co.uk/rss.xml", "lang": "ar", "type": "news", "all": False},
    {"name": "UN News - Middle East", "url": "https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml", "lang": "en", "type": "official", "all": False},
    {"name": "UN News - Arabic", "url": "https://news.un.org/feed/subscribe/ar/news/region/middle-east/feed/rss.xml", "lang": "ar", "type": "official", "all": False},
    {"name": "Reddit r/Libya", "url": "https://www.reddit.com/r/Libya/.rss", "lang": "en", "type": "social", "all": True},
    {"name": "Reddit بحث ليبيا", "url": "https://www.reddit.com/search.rss?q=libya&sort=new&t=day", "lang": "en", "type": "social", "all": False},
    {"name": "Mastodon #libya", "url": "https://mastodon.social/tags/libya.rss", "lang": "en", "type": "social", "all": True},
    {"name": "Mastodon #ليبيا", "url": "https://mastodon.social/tags/ليبيا.rss", "lang": "ar", "type": "social", "all": True},
    {"name": "Mastodon #Libye", "url": "https://mastodon.social/tags/libye.rss", "lang": "fr", "type": "social", "all": True},
    {"name": "Wikinews Libya", "url": "https://en.wikinews.org/w/index.php?title=Special:NewPages&feed=atom&namespace=0&days=7", "lang": "en", "type": "news", "all": False},
]

# قنوات تلغرام العامة: تُقرأ من واجهة الويب العامة t.me/s/<channel> دون حساب ولا تسجيل.
# أضف أسماء القنوات التي تعرفها (بدون @). ما لا يوجد يُسجَّل فشله في لوحة الصحة فقط.
TELEGRAM_CHANNELS = [
    # أمثلة — عدّلها بحسب القنوات الليبية التي تتابعها:
    # {"name": "اسم القناة", "channel": "channel_username", "lang": "ar"},
]

# صفحات الويب العامة التي ليس لها RSS: يمكن إضافتها هنا بصيغة (اسم، رابط الصفحة، لغة).
# سيحاول النظام اكتشاف RSS تلقائياً من رأس الصفحة (autodiscovery).
AUTODISCOVER_PAGES = [
    {"name": "المؤسسة الوطنية للنفط", "url": "https://noc.ly/", "lang": "ar", "type": "official", "all": True},
    {"name": "مصرف ليبيا المركزي", "url": "https://cbl.gov.ly/", "lang": "ar", "type": "official", "all": True},
]

# عمر الخبر الأقصى المقبول عند الجمع (أيام) — لمنع إغراق قاعدة البيانات بأرشيف قديم
MAX_AGE_DAYS = 14
# نافذة إزالة التكرار بين العناوين المتشابهة (ساعات)
DEDUP_WINDOW_HOURS = 72
# عتبة تشابه العناوين لاعتبارهما خبراً واحداً
TITLE_SIM_THRESHOLD = 0.5


# مواقع ليبية (كلها عن ليبيا): تُجلب أحدث أخبارها عبر بحث site: في جوجل نيوز،
# فلا تضيع حتى لو تعطل RSS الخاص بها أو لم يكن موجوداً. أضف مواقعك هنا.
LIBYAN_SITES = [
    "alwasat.ly", "mcg24.com", "roayahnews.com", "alaraby.co.uk", "fassatoday.com", "addresslibya.com", "libyaobserver.ly", "libyaalahrar.net", "libyaherald.com", "libyareview.com", "libyaupdate.com",
    "libya24.tv", "libyaakhbar.com", "almarsad.co", "218tv.net", "alwatan.ly", "libyaschannel.com", "libyanexpress.com",
    "ean.ly", "lana.gov.ly", "cbl.gov.ly", "noc.ly", "unsmil.unmissions.org", "libyaoutlook.com", "aljazeera.net/where/libya",
    "almotamar.ly", "alayam.ly", "fawasel.com", "libyaobserver.ly", "libyaalmostakbal.com", "ain-libya.com", "libyanow.com",
]

# مواقع تنشر أخباراً دولية أيضاً: لا تُقبل كل أخبارها، بل ما فيه كيان ليبي فقط
AR_COM_SITES = {"mcg24.com", "roayahnews.com", "alaraby.co.uk"}
MIXED_SITES = ["alaraby.co.uk", "alwasat.ly", "218tv.net", "aljazeera.net/where/libya", "alayam.ly", "fawasel.com"]


# مرشّحون: مواقع ليبية يتحقق منها المكتشف تلقائياً (يبحث عن RSS؛ وإن لم يجد يضيفها لاستعلامات جوجل site:)
# (النطاق، الاسم، اللغة، هل كل ما فيه عن ليبيا؟)
CANDIDATE_SITES = [
    ("libyaalsalam.net", "ليبيا السلام", "ar", True), ("elkhabar.ly", "الخبر", "ar", True), ("brnieq.ly", "برنيق", "ar", True),
    ("brnieq.com", "برنيق", "ar", True), ("newlibya.net", "ليبيا الجديدة", "ar", True), ("febp.ly", "فبراير", "ar", True),
    ("febpress.ly", "فبراير", "ar", True), ("akhbarlibya24.net", "أخبار ليبيا 24", "ar", True), ("libyaalahrar.tv", "ليبيا الأحرار", "ar", True),
    ("libyaakhbar.com", "ليبيا أخبار", "ar", True), ("libya-news.com", "أخبار ليبيا", "ar", True), ("lana.gov.ly", "وكالة الأنباء الليبية", "ar", True),
    ("lana-news.ly", "وكالة الأنباء الليبية", "ar", True), ("libyaobserver.ly", "ليبيا أوبزرفر", "en", True), ("eanlibya.com", "عين ليبيا", "ar", True),
    ("almarsad.co", "المرصد", "ar", True), ("tanasuh.tv", "التناصح", "ar", True), ("libyanexpress.com", "ليبيان إكسبرس", "en", True),
    ("libyaherald.com", "ليبيا هيرالد", "en", True), ("fawaselmedia.com", "فواصل", "ar", True), ("ewanlibya.ly", "إيوان ليبيا", "ar", True),
    ("libya-al-mostakbal.org", "ليبيا المستقبل", "ar", True), ("tripolipost.com", "طرابلس بوست", "ar", True), ("qurynanew.com", "قورينا الجديدة", "ar", True),
    ("almasartv.ly", "المسار", "ar", True), ("allibiya.tv", "الليبية", "ar", True), ("presssolidarity.net", "وكالة التضامن", "ar", True),
    ("afrigatenews.net", "أفريجيت", "ar", False), ("libyaoutlook.com", "ليبيا أوتلوك", "en", True), ("libyaschannel.com", "قناة ليبيا", "ar", True),
    ("alwatan.ly", "الوطن", "ar", True), ("libyanow.com", "ليبيا ناو", "ar", True), ("ain-libya.com", "عين ليبيا", "ar", True),
    ("libyaalmostakbal.com", "ليبيا المستقبل", "ar", True), ("almotamar.ly", "المؤتمر", "ar", True), ("alayam.ly", "الأيام", "ar", True),
    ("hnec.ly", "المفوضية العليا للانتخابات", "ar", True), ("mofa.gov.ly", "وزارة الخارجية الليبية", "ar", True), ("moi.gov.ly", "وزارة الداخلية", "ar", True),
    ("gnu.gov.ly", "حكومة الوحدة الوطنية", "ar", True), ("pm.gov.ly", "رئاسة الوزراء", "ar", True), ("health.gov.ly", "وزارة الصحة", "ar", True),
    ("libyaobserver.ly/ar", "ليبيا أوبزرفر", "ar", True), ("alwasat.ly", "بوابة الوسط", "ar", False), ("218tv.net", "218", "ar", False),
    ("libyaupdate.com", "ليبيا أبديت", "en", True), ("libyareview.com", "ليبيا ريفيو", "en", True), ("libya24.tv", "ليبيا 24", "ar", True),
    ("crisisgroup.org/middle-east-north-africa/north-africa/libya", "مجموعة الأزمات", "en", True),
    ("unsmil.unmissions.org", "بعثة الأمم المتحدة", "ar", True), ("libya.un.org", "الأمم المتحدة في ليبيا", "en", True),
    ("reliefweb.int/country/lby", "ريليف ويب", "en", True), ("acleddata.com", "أكليد", "en", False),
]

CANDIDATE_SITES += [
    # قنوات يوتيوب (لكل قناة RSS مجاني؛ ما لا يصحّ منها يُسجَّل فشلاً ولا يضر)
    ("youtube.com/@218tv", "قناة 218", "ar", True), ("youtube.com/@LibyaAlAhrarTV", "ليبيا الأحرار", "ar", True),
    ("youtube.com/@libyapanorama", "ليبيا بانوراما", "ar", True), ("youtube.com/@AlnabaaTV", "قناة النبأ", "ar", True),
    ("youtube.com/@AljazeeraChannel", "الجزيرة (يوتيوب)", "ar", False), ("youtube.com/@AlArabiya", "العربية (يوتيوب)", "ar", False),
    ("youtube.com/@skynewsarabia", "سكاي نيوز عربية (يوتيوب)", "ar", False), ("youtube.com/@bbcnewsarabic", "بي بي سي عربي (يوتيوب)", "ar", False),
    ("youtube.com/@FRANCE24Arabic", "فرانس 24 (يوتيوب)", "ar", False), ("youtube.com/@TRTArabi", "تي آر تي عربي (يوتيوب)", "ar", False),
    ("youtube.com/@DWArabic", "دويتشه فيله عربية (يوتيوب)", "ar", False),
]


# ---------------------------------------------------------------------------
# المراجع الدولية: صحف ووكالات ومراكز أبحاث ومنظمات ذات أثر. يُلتقط منها ما يذكر ليبيا فقط (العنوان يكفي ولو كان المقال مغلقاً).
# (النطاق، الاسم بالعربية، النوع، لغة البحث)
PRESTIGE = [
    # وكالات
    ("reuters.com", "رويترز", "agency", "en"), ("apnews.com", "أسوشيتد برس", "agency", "en"), ("aa.com.tr", "الأناضول", "agency", "en"),
    ("xinhuanet.com", "شينخوا", "agency", "en"), ("tass.com", "تاس", "agency", "en"), ("ansa.it", "أنسا", "agency", "it"),
    ("efe.com", "إيفي", "agency", "es"), ("afp.com", "وكالة الصحافة الفرنسية", "agency", "fr"),
    # صحف ومنصات عالمية
    ("bbc.com", "بي بي سي", "press", "en"), ("bbc.co.uk", "بي بي سي", "press", "en"), ("nytimes.com", "نيويورك تايمز", "press", "en"),
    ("washingtonpost.com", "واشنطن بوست", "press", "en"), ("theguardian.com", "الغارديان", "press", "en"), ("ft.com", "فايننشال تايمز", "press", "en"),
    ("economist.com", "الإيكونوميست", "press", "en"), ("wsj.com", "وول ستريت جورنال", "press", "en"), ("bloomberg.com", "بلومبرغ", "press", "en"),
    ("cnn.com", "سي إن إن", "press", "en"), ("news.sky.com", "سكاي نيوز", "press", "en"), ("time.com", "تايم", "press", "en"),
    ("aljazeera.com", "الجزيرة (إنجليزي)", "press", "en"), ("aljazeera.net", "الجزيرة", "press", "ar"), ("middleeasteye.net", "ميدل إيست آي", "press", "en"),
    ("al-monitor.com", "المونيتور", "press", "en"), ("thenationalnews.com", "ذا ناشيونال", "press", "en"), ("arabnews.com", "عرب نيوز", "press", "en"),
    ("english.alarabiya.net", "العربية (إنجليزي)", "press", "en"), ("alarabiya.net", "العربية", "press", "ar"), ("france24.com", "فرانس 24", "press", "en"),
    ("rfi.fr", "إذاعة فرنسا الدولية", "press", "fr"), ("lemonde.fr", "لوموند", "press", "fr"), ("lefigaro.fr", "لوفيغارو", "press", "fr"),
    ("jeuneafrique.com", "جون أفريك", "press", "fr"), ("corriere.it", "كورييري ديلا سيرا", "press", "it"), ("repubblica.it", "لا ريبوبليكا", "press", "it"),
    ("ilsole24ore.com", "إل سولي 24 أوري", "press", "it"), ("spiegel.de", "دير شبيغل", "press", "de"), ("faz.net", "فرانكفورتر ألغماينه", "press", "de"),
    ("dw.com", "دويتشه فيله", "press", "en"), ("elpais.com", "إل باييس", "press", "es"), ("politico.eu", "بوليتيكو أوروبا", "press", "en"),
    ("euronews.com", "يورونيوز", "press", "en"), ("africanews.com", "أفريكا نيوز", "press", "en"), ("theafricareport.com", "ذا أفريكا ريبورت", "press", "en"),
    ("trtworld.com", "تي آر تي وورلد", "press", "en"), ("dailysabah.com", "ديلي صباح", "press", "en"), ("hurriyetdailynews.com", "حرييت ديلي نيوز", "press", "en"),
    ("foreignpolicy.com", "فورين بوليسي", "press", "en"), ("foreignaffairs.com", "فورين أفيرز", "press", "en"), ("rt.com", "آر تي", "press", "en"),
    ("kommersant.ru", "كوميرسانت", "press", "ru"), ("lenta.ru", "لينتا", "press", "ru"),
    # مراكز أبحاث
    ("crisisgroup.org", "مجموعة الأزمات الدولية", "thinktank", "en"), ("chathamhouse.org", "تشاتام هاوس", "thinktank", "en"),
    ("carnegieendowment.org", "كارنيغي", "thinktank", "en"), ("brookings.edu", "بروكنغز", "thinktank", "en"), ("atlanticcouncil.org", "المجلس الأطلسي", "thinktank", "en"),
    ("washingtoninstitute.org", "معهد واشنطن", "thinktank", "en"), ("cfr.org", "مجلس العلاقات الخارجية", "thinktank", "en"), ("csis.org", "CSIS", "thinktank", "en"),
    ("rand.org", "راند", "thinktank", "en"), ("ecfr.eu", "المجلس الأوروبي للعلاقات الخارجية", "thinktank", "en"), ("iiss.org", "IISS", "thinktank", "en"),
    ("merip.org", "ميريب", "thinktank", "en"), ("acleddata.com", "أكليد", "thinktank", "en"), ("smallarmssurvey.org", "مسح الأسلحة الصغيرة", "thinktank", "en"),
    ("globalinitiative.net", "المبادرة العالمية ضد الجريمة", "thinktank", "en"), ("ispionline.it", "ISPI", "thinktank", "en"), ("swp-berlin.org", "SWP", "thinktank", "en"),
    # منظمات وجهات رسمية
    ("un.org", "الأمم المتحدة", "intl", "en"), ("news.un.org", "أخبار الأمم المتحدة", "intl", "en"), ("unsmil.unmissions.org", "بعثة الأمم المتحدة في ليبيا", "intl", "en"),
    ("ohchr.org", "مفوضية حقوق الإنسان", "intl", "en"), ("unhcr.org", "مفوضية اللاجئين", "intl", "en"), ("iom.int", "المنظمة الدولية للهجرة", "intl", "en"),
    ("wfp.org", "برنامج الأغذية العالمي", "intl", "en"), ("icrc.org", "الصليب الأحمر", "intl", "en"), ("reliefweb.int", "ريليف ويب", "intl", "en"),
    ("worldbank.org", "البنك الدولي", "intl", "en"), ("imf.org", "صندوق النقد الدولي", "intl", "en"), ("icc-cpi.int", "المحكمة الجنائية الدولية", "intl", "en"),
    ("consilium.europa.eu", "المجلس الأوروبي", "intl", "en"), ("eeas.europa.eu", "الخدمة الأوروبية للعمل الخارجي", "intl", "en"), ("ec.europa.eu", "المفوضية الأوروبية", "intl", "en"),
    ("hrw.org", "هيومن رايتس ووتش", "intl", "en"), ("amnesty.org", "منظمة العفو الدولية", "intl", "en"), ("state.gov", "الخارجية الأمريكية", "intl", "en"),
    ("gov.uk", "الحكومة البريطانية", "intl", "en"), ("africom.mil", "أفريكوم", "intl", "en"), ("au.int", "الاتحاد الأفريقي", "intl", "en"), ("nato.int", "الناتو", "intl", "en"),
]
PAYWALL = {"nytimes.com", "washingtonpost.com", "ft.com", "economist.com", "wsj.com", "bloomberg.com", "foreignaffairs.com",
           "lemonde.fr", "lefigaro.fr", "jeuneafrique.com", "corriere.it", "repubblica.it", "ilsole24ore.com", "spiegel.de", "faz.net",
           "elpais.com", "theafricareport.com", "al-monitor.com", "iiss.org", "foreignpolicy.com", "time.com", "kommersant.ru"}
PRESTIGE_KIND_AR = {"agency": "وكالة", "press": "صحيفة/منصة", "thinktank": "مركز أبحاث", "intl": "منظمة/جهة رسمية"}
PRESTIGE += [
    # عربية: صحف ومنصات عالمية بالعربية
    ("bbc.com/arabic", "بي بي سي عربي", "press", "ar"), ("skynewsarabia.com", "سكاي نيوز عربية", "press", "ar"), ("arabic.cnn.com", "سي إن إن بالعربية", "press", "ar"),
    ("independentarabia.com", "إندبندنت عربية", "press", "ar"), ("alhurra.com", "الحرة", "press", "ar"), ("arabic.rt.com", "روسيا اليوم", "press", "ar"),
    ("arabic.euronews.com", "يورونيوز عربي", "press", "ar"), ("aawsat.com", "الشرق الأوسط", "press", "ar"), ("alquds.co.uk", "القدس العربي", "press", "ar"),
    ("arabi21.com", "عربي21", "press", "ar"), ("alaraby.co.uk", "العربي الجديد", "press", "ar"), ("dw.com/ar", "دويتشه فيله عربية", "press", "ar"),
    ("france24.com/ar", "فرانس 24 عربي", "press", "ar"), ("aa.com.tr/ar", "الأناضول عربي", "agency", "ar"), ("trtarabi.com", "تي آر تي عربي", "press", "ar"),
    ("swissinfo.ch/ara", "سويس إنفو", "press", "ar"), ("rfi.fr/ar", "إذاعة فرنسا الدولية عربي", "press", "ar"),
]
_PRESTIGE_MAP = {}
for _d, _n, _k, _l in PRESTIGE:
    _PRESTIGE_MAP.setdefault(_d.split("/")[0], _k)


def _hostof(h):
    h = (h or "").lower()
    return h[4:] if h.startswith("www.") else h


def prestige_kind(host):
    """يرجع (نوع المرجع، النطاق المطابق) أو (None, None)؛ يطابق النطاق والنطاقات الفرعية."""
    h = _hostof(host)
    while h:
        if h in _PRESTIGE_MAP:
            return _PRESTIGE_MAP[h], h
        if "." not in h:
            break
        h = h.split(".", 1)[1]
    return None, None


# كلمات إضافية للتصنيف (تُدمج في CATEGORIES) لتقليل «أخرى»
_CAT_EXTRA = {
    "politics": ["الدبيبة", "حفتر", "المنفي", "تكالة", "المشري", "عقيلة صالح", "أسامة حماد", "صدام حفتر", "سيف الإسلام", "المجلس الأعلى للدولة", "الحكومة", "رئيس الوزراء", "القائد العام", "النائب العام", "حفتر", "dbeibah", "haftar", "menfi", "tetteh", "تيتيه"],
    "economy": ["منتدى الأعمال", "الغرفة التجارية", "شراكة", "أوبك", "opec", "صندوق التنمية", "مشروع", "فندق", "قرض", "الإقراض", "الإسكان", "التحويلات", "مصفاة", "الطاقة", "الكهرباء المشاريع", "تجارة", "الصادرات", "الواردات", "المنطقة الحرة", "الأعمال", "شركة", "سوق", "business forum", "trade", "forum d'affaires", "forum economico"],
    "society": ["الأرصاد", "الجوية", "رعدية", "نقابة", "المعلمين", "الدراسة", "الحرس البلدي", "طريق", "الدائري", "تأهيل", "كوادر", "المحلات", "الطقس", "سيول", "حوادث", "حادث مروري", "حريق", "الإنسولين", "الإمداد الطبي", "الدواء", "أدوية", "علاج", "المرضى", "المستشفى"],
    "sports_culture": ["بطولة", "الميدالية", "ذهبية", "بطل", "يفوز", "يحرز", "القرآن", "مسابقة", "تكريم", "الفائزين", "ملاكمة", "رياضي", "رياضة", "معرض", "كتاب", "فنان", "مسرح"],
    "security": ["ألغام", "مخلفات الحرب", "مخلفات الحروب", "الجغبوب", "اختطاف", "عقوبات", "sanctions", "ملاحقة", "ضبط", "القبض"],
    "tech": ["روبوت", "تطبيق", "تطبيقات", "رقمي", "الرقمنة", "منصة إلكترونية", "robot", "app", "digital"],
    "migration": ["كريت", "crete", "ترحيل", "المهاجرين", "قوارب الموت"],
    "diplomacy": ["وفد", "بكين", "الصين", "الأردن", "التعاون", "شراكة استراتيجية", "المذكرة", "الوطن الأزرق", "الاتفاق التركي", "الاتفاقية البحرية", "خارجية", "الخارجية", "حلف الناتو", "قمة", "اجتماع وزراء"],
    "humanitarian": ["ألغام", "الأمم المتحدة للطفولة", "يونيسف", "الهلال الأحمر", "مفقودين", "الإنسولين", "سوء التغذية", "مجاعة"],
}
for _k, _w in _CAT_EXTRA.items():
    if _k in CATEGORIES:
        CATEGORIES[_k][1].extend(w for w in _w if w not in CATEGORIES[_k][1])

CANDIDATE_SITES += [
    # جهات رسمية ليبية
    ("mof.gov.ly", "وزارة المالية", "ar", True), ("mop.gov.ly", "وزارة التخطيط", "ar", True), ("mol.gov.ly", "وزارة العمل", "ar", True),
    ("moe.gov.ly", "وزارة التربية والتعليم", "ar", True), ("mohe.gov.ly", "وزارة التعليم العالي", "ar", True), ("mod.gov.ly", "وزارة الدفاع", "ar", True),
    ("noc.ly", "المؤسسة الوطنية للنفط", "ar", True), ("cbl.gov.ly", "مصرف ليبيا المركزي", "ar", True), ("lia.ly", "المؤسسة الليبية للاستثمار", "en", True),
    ("gecol.ly", "الشركة العامة للكهرباء", "ar", True), ("libyanjustice.ly", "وزارة العدل", "ar", True), ("mocs.gov.ly", "وزارة الحكم المحلي", "ar", True),
    ("hcs.ly", "المجلس الأعلى للدولة", "ar", True), ("parliament.ly", "مجلس النواب", "ar", True), ("presidencycouncil.ly", "المجلس الرئاسي", "ar", True),
    ("nccl.ly", "المركز الوطني لمكافحة الأمراض", "ar", True), ("ncdc.org.ly", "المركز الوطني لمكافحة الأمراض", "ar", True),
    ("libyaobserver.ly/ar", "ليبيا أوبزرفر", "ar", True),
    # صحف ومواقع ليبية إضافية
    ("alwatanlibya.com", "الوطن ليبيا", "ar", True), ("almanaralink.com", "المنارة", "ar", True), ("alraedlibya.com", "الرائد", "ar", True),
    ("libyaalyoum.com", "ليبيا اليوم", "ar", True), ("alnabaa.ly", "النبأ", "ar", True), ("libyanspider.com", "العنكبوت الليبي", "en", True),
    ("libyaprospect.com", "ليبيا بروسبكت", "en", True), ("libyanewsnow.com", "ليبيا نيوز ناو", "en", True), ("alhadathlibya.com", "الحدث ليبيا", "ar", True),
    ("almawqif.ly", "الموقف", "ar", True), ("alrawabet.com", "الروابط", "ar", True), ("tripolitoday.com", "طرابلس اليوم", "ar", True),
    ("libyaalyom.com", "ليبيا اليوم", "ar", True), ("benghazitoday.com", "بنغازي اليوم", "ar", True), ("libyanewsagency.com", "وكالة أنباء ليبيا", "ar", True),
    ("sabha24.com", "سبها 24", "ar", True), ("fezzanlibya.com", "فزان", "ar", True), ("alkhabar24.ly", "الخبر 24", "ar", True),
    ("libyaalawsat.com", "ليبيا الأوسط", "ar", True), ("alsaaa24.com", "الساعة 24", "ar", True), ("nabaa.ly", "النبأ", "ar", True),
]

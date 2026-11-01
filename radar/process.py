# -*- coding: utf-8 -*-
"""المعالجة: تطبيع النص، الصلة بليبيا، اللغة، التصنيف، العاجل، التشابه بين العناوين."""
import re
import hashlib
import unicodedata
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from . import config as C

_AR_DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_NONWORD = re.compile(r"[^\w؀-ۿЀ-ӿ一-鿿぀-ヿ가-힯֐-׿]+", re.UNICODE)

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "ref",
            "ocid", "cmpid", "mc_cid", "mc_eid", "igshid", "mkt_tok", "_ga", "ito", "xtor", "ncid"}


def strip_html(s):
    if not s:
        return ""
    s = _TAG.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&#8217;", "’").replace("&#8211;", "–"))
    return _WS.sub(" ", s).strip()


def norm_text(s):
    """تطبيع للمقارنة: حروف صغيرة، إزالة التشكيل وتوحيد الألف والياء والتاء المربوطة."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = _AR_DIAC.sub("", s)
    s = (s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
          .replace("ؤ", "و").replace("ئ", "ي"))
    return s


def canon_url(url):
    try:
        u = urlparse(url.strip())
        q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k.lower() not in TRACKING]
        host = u.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = u.path.rstrip("/") or "/"
        return urlunparse((u.scheme.lower() or "https", host, path, "", urlencode(q), ""))
    except Exception:
        return url


def domain_of(url):
    try:
        h = urlparse(url).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def item_id(url, title):
    key = canon_url(url) if url else norm_text(title)
    return hashlib.sha1(key.encode("utf-8", "ignore")).hexdigest()[:20]


# ---------------- اللغة ----------------
def detect_lang(text, hint=""):
    t = text or ""
    counts = {"ar": 0, "fa_ar": 0, "ru": 0, "zh": 0, "ja": 0, "ko": 0, "he": 0, "el": 0, "hi": 0, "lat": 0}
    for ch in t:
        o = ord(ch)
        if 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F:
            counts["ar"] += 1
        elif 0x0400 <= o <= 0x04FF:
            counts["ru"] += 1
        elif 0x4E00 <= o <= 0x9FFF:
            counts["zh"] += 1
        elif 0x3040 <= o <= 0x30FF:
            counts["ja"] += 1
        elif 0xAC00 <= o <= 0xD7AF:
            counts["ko"] += 1
        elif 0x0590 <= o <= 0x05FF:
            counts["he"] += 1
        elif 0x0370 <= o <= 0x03FF:
            counts["el"] += 1
        elif 0x0900 <= o <= 0x097F:
            counts["hi"] += 1
        elif ch.isalpha():
            counts["lat"] += 1
    top = max(counts, key=counts.get)
    if counts[top] == 0:
        return hint or "und"
    if top == "ar":
        if any(c in t for c in "پچژگ"):
            return "fa"
        if hint in ("fa", "ur"):
            return hint
        return "ar"
    if top == "ja":
        return "ja"
    if top == "zh":
        return "ja" if counts["ja"] else "zh"
    if top == "ru":
        return "uk" if hint == "uk" or any(c in t for c in "іїєґ") else "ru"
    if top in ("ko", "he", "el", "hi"):
        return top
    # لاتيني: نعتمد التلميح، وإلا نخمن بكلمات شائعة
    if hint and hint not in ("ar", "ru", "zh", "und"):
        return hint.split("-")[0]
    low = " " + norm_text(t) + " "
    marks = {
        "fr": [" le ", " la ", " les ", " des ", " du ", " et ", " en ", " une ", " est ", " pour "],
        "it": [" il ", " della ", " che ", " per ", " con ", " una ", " nel ", " di "],
        "es": [" el ", " los ", " las ", " del ", " una ", " por ", " con ", " para "],
        "de": [" der ", " die ", " das ", " und ", " nicht ", " mit ", " für ", " ein "],
        "tr": [" ve ", " bir ", " için ", " ile ", " bu ", " da ", " de "],
        "pt": [" os ", " as ", " uma ", " não ", " com ", " para ", " do "],
        "en": [" the ", " and ", " of ", " to ", " in ", " is ", " for ", " on "],
    }
    best, bs = "en", 0
    for lg, ws in marks.items():
        sc = sum(low.count(w) for w in ws)
        if sc > bs:
            best, bs = lg, sc
    return best


# ---------------- الصلة بليبيا ----------------
def _build_matchers():
    def compile_terms(terms):
        out = []
        for t in terms:
            n = norm_text(t).strip()
            if n:
                out.append(n)
        # الأطول أولاً
        out = sorted(set(out), key=len, reverse=True)
        return out
    return compile_terms(C.STRONG_TERMS), compile_terms(C.GEO_WEAK_TERMS), compile_terms(C.CONTEXT_TERMS), compile_terms(C.NOISE_HINTS)


_STRONG, _GEO, _CTX, _NOISE = _build_matchers()
_CJK = re.compile(r"[぀-ヿ一-鿿가-힯֐-׿ऀ-ॿ]")


_PCACHE = {}


def _has(text, term):
    """مطابقة كلمة مع حدود (للغات ذات المسافات)، أو احتواء مباشر للغات بلا مسافات.
    الأنماط تُبنى مرة واحدة وتُحفظ (ذاكرة re المدمجة لا تتسع لقاموسنا فكانت تعيد البناء كل مرة)."""
    pat = _PCACHE.get(term)
    if pat is None:
        if _CJK.search(term):
            pat = False
        elif term.startswith("ال"):
            pat = re.compile(r"(?<![\w\u0600-\u06FF])[وبلفك]?" + re.escape(term) + r"(?![\w\u0600-\u06FF])")
        else:
            pat = re.compile(r"(?<![\w\u0600-\u06FF])(?:[وبلفك]?(?:ال)?)?" + re.escape(term) + r"(?![\w\u0600-\u06FF])")
        _PCACHE[term] = pat
    if pat is False:
        return term in text
    return pat.search(text) is not None


def relevance(title, summary, trusted=False):
    """يرجع (score, matched_terms). score>0 يعني ذا صلة. trusted=الجامع نفسه مطابق لكلمة قوية."""
    text = norm_text((title or "") + " \n " + (summary or ""))
    if any(n in text for n in _NOISE):
        # ضجيج صريح (طرابلس لبنان...) ما لم تظهر كلمة ليبيا القوية بوضوح
        if not any(_has(text, s) for s in ("ليبيا", "libya", "libye", "libia", "ливия")):
            return 0, []
    hits = []
    for s in _STRONG:
        if _has(text, s):
            hits.append(s)
            if len(hits) >= 6:
                break
    if hits:
        return 3 + min(len(hits), 5), hits
    geo = [g for g in _GEO if _has(text, g)]
    ctx = [c for c in _CTX if _has(text, c)]
    if geo and len(ctx) >= 2:
        return 2, geo[:2] + ctx[:2]
    if trusted:
        return 1, []
    return 0, []


# ---------------- التصنيف ----------------
_CAT_NORM = {}


def _norm_cats():
    for cid, (_name, words) in C.CATEGORIES.items():
        _CAT_NORM[cid] = [norm_text(w) for w in words]


_norm_cats()


def categorize(title, summary):
    text = norm_text((title or "") + " " + (summary or ""))
    title_n = norm_text(title or "")
    scores = {}
    for cid, words in _CAT_NORM.items():
        sc = 0
        for w in words:
            if _has(text, w):
                sc += 2 if _has(title_n, w) else 1
        if sc:
            scores[cid] = sc
    if not scores:
        return C.DEFAULT_CATEGORY[0]
    return max(scores, key=scores.get)


def all_categories(title, summary, limit=3):
    text = norm_text((title or "") + " " + (summary or ""))
    out = []
    for cid, words in _CAT_NORM.items():
        sc = sum(1 for w in words if _has(text, w))
        if sc:
            out.append((sc, cid))
    out.sort(reverse=True)
    return [c for _, c in out[:limit]]


_URG = sorted({norm_text(t) for t in C.URGENT_TERMS}, key=len, reverse=True)


_BRK = re.compile(r"(?:^|[\s#|:\-\[\(«\"])(?:عاجل|عاجلا|breaking|urgent|flash|alerte|ultima ora|son dakika|срочно)(?![\w\u0600-\u06FF])", re.I)


def urgency(title, summary):
    t = norm_text(title or "")
    s = norm_text(summary or "")
    sc = 6 if (_BRK.search(t) and "غير عاجل" not in t) else 0     # كلمة «عاجل» صريحة في العنوان = خبر عاجل
    for w in _URG:
        if _has(t, w):
            sc += 3
        elif _has(s, w):
            sc += 1
    return min(sc, 12)


# ---------------- تشابه العناوين ----------------
_STOP = set(norm_text(w) for w in [
    "في", "من", "على", "الى", "إلى", "عن", "مع", "ان", "أن", "هذا", "هذه", "التي", "الذي", "بعد", "قبل", "ضد", "حول", "بين",
    "the", "and", "for", "with", "from", "after", "over", "that", "this", "has", "have", "are", "was", "were", "will", "its",
    "des", "les", "une", "pour", "dans", "sur", "che", "per", "con", "una", "del", "los", "las", "und", "der", "die", "das",
])


def title_tokens(title):
    t = norm_text(title)
    # إزالة لاحقة اسم المصدر مثل « - الجزيرة» أو « | Reuters»
    t = re.split(r"\s[-–—|]\s", t)[0] if re.search(r"\s[-–—|]\s", t) else t
    toks = []
    for w in _NONWORD.sub(" ", t).split():
        if len(w) <= 1 or w in _STOP:
            continue
        # تجذير عربي خفيف: إزالة «ال» وحرف العطف «و» الملتصق
        if re.match(r"^[\u0600-\u06FF]+$", w):
            if w.startswith("ال") and len(w) > 4:
                w = w[2:]
            elif w.startswith("و") and len(w) > 4:
                w = w[1:]
                if w.startswith("ال") and len(w) > 4:
                    w = w[2:]
            elif w.startswith("ب") and len(w) > 4:
                w = w[1:]
        if len(w) > 1 and w not in _STOP:
            toks.append(w)
    # للغات CJK: أزواج أحرف
    if len(toks) <= 2 and _CJK.search(t):
        chars = [c for c in t if _CJK.match(c)]
        toks += ["".join(chars[i:i + 2]) for i in range(len(chars) - 1)]
    return set(toks)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / float(min(len(a), len(b)) * 0.5 + max(len(a), len(b)) * 0.5)


def source_trust_label(stype, n_domains):
    """درجة الثقة المبدئية: رسمي/وكالة + عدد المصادر المستقلة."""
    if n_domains >= 3:
        return "confirmed"
    if n_domains == 2:
        return "likely"
    if stype in ("official",):
        return "official"
    if stype == "social":
        return "unverified"
    return "single"

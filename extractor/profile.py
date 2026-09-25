"""
profile.py - the business profile of one folder (section 15).

    py profile.py "C:\\Users\\Laurent\\new model\\documents.db"

It reads the spans that extract_db.py stored (status 'verified' or
'format_warning' only) and turns them into ONE profile of the business
the folder is about. Pure code, deterministic. Every value carries its
sources (extraction id, file, page, chunk, exact text), and every value
is the exact text of a source span or the normalization of that text
(the invariant of 15.9, checked by check_invariant()).

The steps, in order:
  1. each file gets a document type (length-weighted mean of its chunks'
     doc-type probabilities) and a date (its latest DOC_DATE);
  2. organisation names are grouped into clusters (15.3);
  3. the business is the cluster with the best score (15.4);
  4. each file is 'by the business', 'by another' or 'unknown' (15.5);
  5. the country is voted, and every span used is normalized again with
     that country (14.1);
  6. each field is chosen by its rule (15.6), revenue paired with its
     year (15.7);
  7. coverage = REQUIRED fields found / 11 (15.8).
Writes the tables profile and profile_summary, and profile.json next to
the database, then prints a readable table.
"""
import argparse
import datetime
import importlib.util
import json
import pathlib
import re
import sqlite3
import sys
import sysconfig
import unicodedata

import config
import normalize as N

HERE = pathlib.Path(__file__).resolve().parent


def _standard_profile():
    """Python's standard library has a module called 'profile' too, and
    cProfile (which PyTorch may import) needs it. Because this file has
    the same name, it would be found first: so we load the standard one
    from the standard library folder and hand cProfile what it uses."""
    path = pathlib.Path(sysconfig.get_paths()["stdlib"]) / "profile.py"
    spec = importlib.util.spec_from_file_location("_standard_profile", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_std = _standard_profile()
run, runctx, Profile, _Utils = _std.run, _std.runctx, _std.Profile, \
    _std._Utils

REQUIRED = ["business_name", "address", "activity", "services",
            "legal_form", "reg_id", "contact", "founded", "staff",
            "revenue", "clients"]
DOC_WEIGHT = {"registration": 5, "brochure": 3, "financials": 3,
              "terms": 3, "price_list": 2, "staff_list": 2, "invoice": 1,
              "quote": 1, "contract": 1, "letter": 1, "other": 0.5}
NO_S_BY_BUSINESS = {"brochure", "price_list", "staff_list", "financials",
                    "terms"}
CLIENT_DOCS = {"invoice", "quote", "contract", "letter", "brochure"}
CURRENCY_COUNTRY = {"JPY": "JP", "KRW": "KR", "INR": "IN", "RUB": "RU",
                    "CNY": "CN", "TWD": "TW", "HKD": "HK", "SGD": "SG",
                    "SAR": "SA", "AED": "AE", "EGP": "EG", "MAD": "MA",
                    "KZT": "KZ", "BYN": "BY", "GBP": "GB", "USD": "US",
                    "CAD": "CA", "AUD": "AU", "NGN": "NG", "MXN": "MX",
                    "ARS": "AR", "COP": "CO", "CLP": "CL", "CHF": "CH",
                    "XOF": "SN"}
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]")


# =====================================================================
#  reading the database
# =====================================================================
class Span:
    """One stored extraction, with where it comes from."""

    def __init__(self, row, chunk, file_path):
        (self.id, self.chunk_id, self.label, self.start, self.end,
         self.text, self.score, self.status, normalized, self.reason) = row
        self.norm = json.loads(normalized) if normalized else {}
        self.file_id, self.page, self.ordinal, self.kind, chunk_text = chunk
        self.file = file_path
        self.lang = None

    def source(self):
        return {"extraction": self.id, "file": self.file,
                "page": self.page, "chunk": self.chunk_id,
                "text": self.text}


def latest_model(db):
    row = db.execute("SELECT model FROM chunk_meta ORDER BY created DESC "
                     "LIMIT 1").fetchone()
    return row[0] if row else None


def load(db, model):
    files = {fid: path for fid, path in
             db.execute("SELECT id, path FROM files")}
    chunks = {r[0]: r[1:] for r in db.execute(
        "SELECT id, file_id, page, ordinal, kind, text FROM chunks")}
    meta = {}
    for cid, lang, probs in db.execute(
            "SELECT chunk_id, language, doc_type_probs FROM chunk_meta "
            "WHERE model = ?", (model,)):
        meta[cid] = (lang, json.loads(probs) if probs else None)
    spans = []
    for row in db.execute(
            "SELECT id, chunk_id, label, start_char, end_char, text, score, "
            "status, normalized, reason FROM extractions WHERE model = ? "
            "AND status IN ('verified', 'format_warning') "
            "ORDER BY chunk_id, start_char", (model,)):
        chunk = chunks.get(row[1])
        if chunk is None:
            continue
        sp = Span(row, chunk, files.get(chunk[0], "?"))
        sp.lang = (meta.get(row[1]) or (None, None))[0]
        spans.append(sp)
    return files, chunks, meta, spans


# =====================================================================
#  1. files: type and date
# =====================================================================
def file_types(files, chunks, meta):
    """Arg-max of the length-weighted mean doc-type probability."""
    sums = {}
    for cid, (fid, page, ordinal, kind, text) in chunks.items():
        probs = (meta.get(cid) or (None, None))[1]
        if not probs:
            continue
        w = len(text or "")
        acc = sums.setdefault(fid, [0.0] * len(config.DOC_TYPES))
        for k, p in enumerate(probs):
            acc[k] += p * w
    out = {}
    for fid in files:
        acc = sums.get(fid)
        out[fid] = config.DOC_TYPES[max(range(len(acc)),
                                        key=lambda k: acc[k])] \
            if acc else "other"
    return out


def date_key(norm):
    """(year, month, day) of a normalized date, for sorting."""
    if not norm or not norm.get("ok") or norm.get("kind") != "date":
        return None
    return (norm.get("year") or 0, norm.get("month") or 0,
            norm.get("day") or 0)


def file_dates(spans):
    out = {}
    for sp in spans:
        if sp.label == "DOC_DATE":
            k = date_key(sp.norm)
            if k and (sp.file_id not in out or k > out[sp.file_id]):
                out[sp.file_id] = k
    return out


# =====================================================================
#  2. name clusters (15.3)
# =====================================================================
def legal_form_keys():
    """Every legal form of Appendix G, simplified like a name key,
    longest first."""
    path = HERE / "gen" / "data" / "locales.json"
    keys = set()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for loc in data["locales"].values():
            for form in loc.get("legal_forms", []):
                for text in list(form.get("forms", [])) + \
                        list(form.get("long", []) or []):
                    k = _simplify(text)
                    if k:
                        keys.add(k)
    return sorted(keys, key=len, reverse=True)


def _simplify(text):
    """NFKC, casefold, punctuation and symbols removed, spaces
    collapsed."""
    t = unicodedata.normalize("NFKC", text or "").casefold()
    t = "".join(" " if unicodedata.category(ch)[0] in "PS" else ch
                for ch in t)
    return re.sub(r"\s+", " ", t).strip()


_FORMS = None


def name_key(name):
    """The cluster key of a name (15.3)."""
    global _FORMS
    if _FORMS is None:
        _FORMS = legal_form_keys()
    t = _simplify(name)
    for form in _FORMS:
        if CJK.search(form):
            t = t.replace(form, " ")
        else:
            t = re.sub(r"(?<!\w)%s(?!\w)" % re.escape(form), " ", t)
    if CJK.search(t):
        t = re.sub(r"\s+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def strip_legal_form(name):
    """The name without its legal form, as written (for the trading name
    when there is no other one). Returns the longest part of the text
    that is left - always a piece of the original text."""
    if not name:
        return name
    form = N.parse_legal_form(name)
    if not form:
        return name
    parts = re.split(r"[,«»\"“”()（）]", name)
    best = name
    for part in parts:
        part = part.strip(" -–")
        if part and name_key(part) == name_key(name) and len(part) < \
                len(best):
            best = part
    return best


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def same_organisation(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    minimum = 2 if CJK.search(shorter) else 4
    if len(shorter) >= minimum and shorter in longer:
        return True
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and len(ta & tb) / len(ta | tb) >= 0.8:
        return True
    return False


def clusters(spans):
    """-> {span id: cluster id} for S_NAME and C_NAME spans."""
    names = [sp for sp in spans if sp.label in ("S_NAME", "C_NAME")]
    keys = sorted({name_key(sp.text) for sp in names} - {""})
    uf = UnionFind()
    for k in keys:
        uf.find(k)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if same_organisation(a, b):
                uf.union(a, b)
    # a document has ONE subject (rule R5): every S_NAME of one file is
    # the same organisation (this joins a trading name that shares no
    # word with the legal name, e.g. a brochure naming both)
    first_in_file = {}
    for sp in names:
        k = name_key(sp.text)
        if sp.label == "S_NAME" and k:
            if sp.file_id in first_in_file:
                uf.union(first_in_file[sp.file_id], k)
            else:
                first_in_file[sp.file_id] = k
    # two subjects that share a registration number, a phone, an e-mail
    # or a web site are one organisation (a sole trader's own name on
    # one invoice, his trade name on the next)
    owner = {}
    for sp in spans:
        if sp.label in ("S_REG_ID", "S_PHONE", "S_EMAIL", "S_URL") and \
                sp.file_id in first_in_file:
            key = identifier_key(sp)
            if key:
                here = uf.find(first_in_file[sp.file_id])
                if key in owner:
                    uf.union(owner[key], here)
                else:
                    owner[key] = here
    return {sp.id: uf.find(name_key(sp.text)) for sp in names
            if name_key(sp.text)}


def identifier_key(sp):
    """A comparable form of an identifier of the subject, or None."""
    if sp.label == "S_REG_ID":
        k = N.compact_id(sp.text)
        return ("id", k) if len(k) >= 6 else None
    if sp.label == "S_PHONE":
        digits = re.sub(r"\D", "", N.ascii_digits(sp.text)[0])
        return ("phone", digits[-9:]) if len(digits) >= 8 else None
    if sp.label == "S_EMAIL":
        n = N.normalize("S_EMAIL", sp.text)
        return ("email", n["value"]) if n.get("ok") else None
    if sp.label == "S_URL":
        n = N.normalize("S_URL", sp.text)
        return ("url", n["host"]) if n.get("ok") else None
    return None


# =====================================================================
#  3-4. the business, and who wrote each file
# =====================================================================
def top_cluster(counts):
    return max(sorted(counts), key=lambda c: counts[c]) if counts else None


def choose_business(spans, cluster_of, ftype):
    s_count, c_files = {}, {}
    for sp in spans:
        cl = cluster_of.get(sp.id)
        if cl is None:
            continue
        if sp.label == "S_NAME":
            s_count.setdefault(sp.file_id, {}).setdefault(cl, 0)
            s_count[sp.file_id][cl] += 1
        else:
            c_files.setdefault(cl, set()).add(sp.file_id)
    score, present = {}, {}
    for fid, per in s_count.items():
        for cl in per:
            score[cl] = score.get(cl, 0) + DOC_WEIGHT.get(ftype.get(fid),
                                                          0.5)
            present.setdefault(cl, set()).add(fid)
    for cl, fids in c_files.items():
        for fid in fids:
            if ftype.get(fid) not in ("invoice", "quote", "letter"):
                continue
            top = top_cluster(s_count.get(fid, {}))
            if top != cl:
                score[cl] = score.get(cl, 0) + 0.5
                present.setdefault(cl, set()).add(fid)
    if not score:
        return None, s_count
    best = max(sorted(score), key=lambda c: (score[c],
                                             len(present.get(c, ()))))
    return best, s_count


def authorship(files, ftype, s_count, business, spans=(), cluster_of=None):
    """-> {file id: 'business' | 'other' | 'unknown'}. A file with no
    S_NAME is also by the business when it shows one of the business's
    identifiers (registration number, phone, e-mail, web site)."""
    own_ids = set()
    for sp in spans:
        top = top_cluster(s_count.get(sp.file_id, {}))
        if top is not None and top == business:
            k = identifier_key(sp)
            if k:
                own_ids.add(k)
    ids_of_file = {}
    for sp in spans:
        k = identifier_key(sp)
        if k:
            ids_of_file.setdefault(sp.file_id, set()).add(k)
    out = {}
    for fid in files:
        top = top_cluster(s_count.get(fid, {}))
        if top is not None and top == business:
            out[fid] = "business"
        elif top is None and ftype.get(fid) in NO_S_BY_BUSINESS:
            out[fid] = "business"
        elif top is None and ids_of_file.get(fid, set()) & own_ids:
            out[fid] = "business"
        elif top is not None:
            out[fid] = "other"
        else:
            out[fid] = "unknown"
    return out


# =====================================================================
#  5. the country
# =====================================================================
def country_names():
    """{lower-case country name in any language: country code}."""
    names = {}
    for key in ["ar", "zh", "zh-Hant", "en", "fr", "ru", "es", "it", "hi",
                "ja", "ko"]:
        path = HERE / "gen" / "data" / key / "lexicon.json"
        if not path.exists():
            continue
        lex = json.loads(path.read_text(encoding="utf-8"))
        for code, name in (lex.get("country_names") or {}).items():
            if isinstance(name, str) and len(name) >= 3:
                names[unicodedata.normalize("NFKC", name).casefold()] = code
    return names


def main_country(lang):
    path = HERE / "gen" / "data" / "locales.json"
    if not lang or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    code = data.get("language", {}).get("main_locale", {}).get(lang)
    loc = data["locales"].get(code or "")
    return loc["country"] if loc else None


def language_countries():
    """{language: [countries of its locales]} from locales.json."""
    path = HERE / "gen" / "data" / "locales.json"
    out = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for loc in data["locales"].values():
            out.setdefault(loc["lang"], []).append(loc["country"])
    return out


def vote_country(spans):
    """Votes of 15.6: registration-ID type 3, phone country code 2,
    country name in the address 2, currency 1, language 0.5. A piece of
    evidence votes only when it points to one country: a number that
    fits the formats of several countries does not vote."""
    votes, seen = {}, set()
    names = country_names()
    langs = {}
    for sp in spans:
        if sp.lang:
            langs[sp.lang] = langs.get(sp.lang, 0) + 1
    lang = max(sorted(langs), key=lambda k: langs[k]) if langs else None
    candidates = sorted(set(language_countries().get(lang, [])))

    def add(countries, weight, what):
        countries = sorted(set(c for c in countries if c))
        if len(countries) == 1 and what not in seen:
            seen.add(what)
            votes[countries[0]] = votes.get(countries[0], 0) + weight
    for sp in spans:
        if sp.label in ("S_REG_ID", "C_REG_ID"):
            fits = []
            for country in candidates:
                n = N.normalize(sp.label, sp.text, sp.lang, country)
                if n.get("ok") and n.get("type") not in (None, "unknown"):
                    fits.append((country, n.get("checksum")))
            valid = [c for c, chk in fits if chk == "valid"]
            add(valid or [c for c, _ in fits], 3, ("id", N.compact_id(
                sp.text)))
        elif sp.label == "S_PHONE":
            n = N.normalize("S_PHONE", sp.text, sp.lang)
            if n.get("ok"):
                add([n.get("country")], 2, ("phone", n["e164"]))
            else:
                fits = [c for c in candidates if N.normalize(
                    "S_PHONE", sp.text, sp.lang, c).get("valid")]
                add(fits, 2, ("phone", sp.text))
        elif sp.label == "S_ADDRESS":
            low = unicodedata.normalize("NFKC", sp.text).casefold()
            for name, code in names.items():
                # a whole word: "Cartagena de Indias" is not India
                if CJK.search(name):
                    hit = name in low
                else:
                    hit = re.search(r"(?<!\w)%s(?!\w)" % re.escape(name),
                                    low) is not None
                if hit:
                    add([code], 2, ("address", code))
                    break
        elif N.KIND_OF_LABEL.get(sp.label) == "amount":
            n = N.normalize(sp.label, sp.text, sp.lang)
            cur = n.get("currency")
            if cur == "USD" and not re.search(r"USD|US\$|U\$S", sp.text):
                cur = None                 # a bare "$" is not the US
            add([CURRENCY_COUNTRY.get(cur)], 1, ("currency", cur))
    if lang:
        add([main_country(lang)], 0.5, ("language", lang))
    if not votes:
        return None, 0.0, votes
    top = max(sorted(votes), key=lambda c: votes[c])
    return top, votes[top] / sum(votes.values()), votes


# =====================================================================
#  6. fields
# =====================================================================
def renormalize(sp, country):
    """The span's value with the voted country (14.1, point 2)."""
    n = N.normalize(sp.label, sp.text, sp.lang, country)
    if n.get("ok") or not sp.norm:
        sp.norm = n
    return sp.norm


def text_key(text):
    """Same address / same activity: NFKC, casefold, letters and digits
    only (digits of every script as ASCII, accents ignored)."""
    t = N.ascii_digits(text or "")[0].casefold()
    t = "".join(ch for ch in unicodedata.normalize("NFKD", t)
                if not unicodedata.combining(ch))
    return "".join(ch for ch in t if ch.isalnum())


def value_key(sp):
    """What makes two spans 'the same value' for a field."""
    n = sp.norm or {}
    kind = n.get("kind")
    if n.get("ok"):
        if kind == "amount":
            return ("amount", n.get("value"), n.get("currency"))
        if kind == "date":
            return ("date", n.get("year"), n.get("month"), n.get("day"))
        if kind == "year":
            return ("year", n.get("year"))
        if kind == "count":
            return ("count", n.get("value"), n.get("qualifier"))
        if kind == "phone":
            return ("phone", n.get("e164"))
        if kind == "email":
            return ("email", n.get("value"))
        if kind == "url":
            return ("url", n.get("host"))
        if kind == "reg_id":
            return ("reg_id", n.get("compact"))
        if kind == "legal_form":
            return ("legal_form", n.get("code"))
        if kind == "activity_code":
            return ("code", n.get("code"))
    return ("text", text_key(sp.text))


class Candidate:
    def __init__(self, key):
        self.key = key
        self.spans = []

    def files(self):
        return {sp.file_id for sp in self.spans}

    def date(self, fdate):
        dates = [fdate.get(f) for f in self.files() if fdate.get(f)]
        return max(dates) if dates else (0, 0, 0)

    def representative(self):
        """The most frequent exact text among the candidate's spans."""
        counts = {}
        for sp in self.spans:
            counts[sp.text] = counts.get(sp.text, 0) + 1
        return max(sorted(counts), key=lambda t: counts[t])

    def value(self):
        text = self.representative()
        sp = next(s for s in self.spans if s.text == text)
        out = {"text": text}
        if sp.norm and sp.norm.get("ok") and sp.norm.get("kind") != "text":
            out["normalized"] = {k: v for k, v in sp.norm.items()
                                 if k not in ("ok",)}
        return out

    def sources(self):
        return [sp.source() for sp in self.spans]


def group(spans):
    cands = {}
    for sp in spans:
        cands.setdefault(value_key(sp), Candidate(value_key(sp))).spans.append(
            sp)
    return list(cands.values())


def pick(spans, order, fdate, ftype):
    """Chooses among candidates. order: a list of criteria among
    'registration', 'recent', 'frequent', 'files'. -> (best, others,
    status)."""
    cands = group(spans)
    if not cands:
        return None, [], "not_found"

    def crit(c):
        out = []
        for o in order:
            if o == "registration":
                out.append(int(any(ftype.get(f) == "registration"
                                   for f in c.files())))
            elif o == "recent":
                out.append(c.date(fdate))
            elif o == "frequent":
                out.append(len(c.spans))
            elif o == "files":
                out.append(len(c.files()))
        return tuple(out)
    cands.sort(key=lambda c: (crit(c), str(c.key)), reverse=True)
    best = cands[0]
    status = "found"
    if len(cands) > 1 and crit(cands[1]) == crit(best):
        status = "conflict"
    return best, cands[1:], status


def field_record(name, best, others, status, weak=False, extra=None):
    rec = {"field": name, "status": status, "weak": weak,
           "value": best.value() if best else None,
           "sources": best.sources() if best else [],
           "alternatives": [{"value": c.value(), "sources": c.sources()}
                            for c in others[:10]]}
    if extra:
        rec.update(extra)
    return rec


def spans_for(label_set, spans, author, business_is_c=None):
    """Spans of these labels from files by the business; if there are
    none, from files of unknown authorship (weak)."""
    main = [sp for sp in spans if sp.label in label_set and
            author.get(sp.file_id) == "business"]
    if business_is_c:
        main += [sp for sp in spans if sp.label in business_is_c and
                 getattr(sp, "_c_is_business", False)]
    if main:
        return main, False
    weak = [sp for sp in spans if sp.label in label_set and
            author.get(sp.file_id) == "unknown"]
    return weak, bool(weak)


# ---------------------------------------------------------------------
#  15.7 revenue with its year
# ---------------------------------------------------------------------
def pair_revenue(rev_spans, year_spans, chunks):
    """-> list of (revenue span, year span or None)."""
    out = []
    by_chunk = {}
    for y in year_spans:
        by_chunk.setdefault(y.chunk_id, []).append(y)
    for r in rev_spans:
        text = chunks[r.chunk_id][4] or ""
        years = sorted(by_chunk.get(r.chunk_id, []), key=lambda y: y.start)
        line_start = text.rfind("\n", 0, r.start) + 1
        line_end = text.find("\n", r.end)
        line_end = len(text) if line_end < 0 else line_end
        same_line = [y for y in years if line_start <= y.start < line_end]
        chosen = None
        # 1. on the same line, immediately before the amount
        before = [y for y in same_line if y.end <= r.start and
                  not re.search(r"\d", text[y.end:r.start])]
        if before:
            chosen = before[-1]
        # 2. anywhere on the same line
        elif same_line:
            chosen = min(same_line, key=lambda y: abs(y.start - r.start))
        else:
            # 3. k years on one line, k amounts on a later line
            chosen = _pair_by_order(r, years, rev_spans, text)
            # 4. the nearest year within 80 characters
            if chosen is None:
                near = [y for y in years if min(abs(y.start - r.end),
                                                abs(r.start - y.end)) <= 80]
                if near:
                    chosen = min(near, key=lambda y: min(
                        abs(y.start - r.end), abs(r.start - y.end)))
        out.append((r, chosen))
    return out


def _pair_by_order(r, years, all_rev, text):
    def line_of(pos):
        return text.count("\n", 0, pos)
    rev_line = [x for x in all_rev if x.chunk_id == r.chunk_id and
                line_of(x.start) == line_of(r.start)]
    rev_line.sort(key=lambda x: x.start)
    lines = {}
    for y in years:
        lines.setdefault(line_of(y.start), []).append(y)
    for ln, ys in sorted(lines.items()):
        if ln < line_of(r.start) and len(ys) == len(rev_line):
            ys.sort(key=lambda y: y.start)
            return ys[rev_line.index(r)]
    return None


# =====================================================================
#  the profile
# =====================================================================
def build(db, model=None, log=print):
    model = model or latest_model(db)
    if model is None:
        return None
    files, chunks, meta, spans = load(db, model)
    ftype = file_types(files, chunks, meta)
    fdate = file_dates(spans)
    cluster_of = clusters(spans)
    business, s_count = choose_business(spans, cluster_of, ftype)
    author = authorship(files, ftype, s_count, business, spans,
                        cluster_of)
    # C spans in files by others (or with no S at all, like a letter
    # from a bank or a tax office) where the C is the business
    for sp in spans:
        if sp.label.startswith("C_") and author.get(sp.file_id) in (
                "other", "unknown"):
            names = [x for x in spans if x.file_id == sp.file_id and
                     x.label == "C_NAME"]
            sp._c_is_business = any(cluster_of.get(x.id) == business
                                    for x in names)
    # the country is voted from the business's own facts only (never a
    # client's or a supplier's number)
    own = [sp for sp in spans if (author.get(sp.file_id) == "business" and
                                  not sp.label.startswith("C_")) or
           getattr(sp, "_c_is_business", False)]
    country, confidence, votes = vote_country(own or spans)
    for sp in spans:
        renormalize(sp, country)
    fields = {}
    # ---- names (15.4)
    names = [sp for sp in spans if sp.label in ("S_NAME", "C_NAME") and
             cluster_of.get(sp.id) == business]
    with_form = [sp for sp in names if N.parse_legal_form(sp.text)]
    legal, legal_others, legal_status = pick(
        with_form or names, ["registration", "frequent", "recent"], fdate,
        ftype)
    trading_pool = [sp for sp in names if not N.parse_legal_form(sp.text)
                    and ftype.get(sp.file_id) in ("brochure", "terms",
                                                  "price_list")]
    trading, trading_others, trading_status = pick(
        trading_pool, ["frequent", "recent"], fdate, ftype)
    rec = field_record("business_name", legal, legal_others,
                       legal_status if legal else "not_found")
    if legal:
        rec["legal_name"] = legal.value()["text"]
        rec["trading_name"] = trading.value()["text"] if trading else \
            strip_legal_form(legal.value()["text"])
        rec["trading_name_derived"] = trading is None
        rec["trading_sources"] = trading.sources() if trading else \
            legal.sources()
    fields["business_name"] = rec
    # ---- the other fields
    rules = [
        ("address", {"S_ADDRESS"}, {"C_ADDRESS"}, ["recent", "files"]),
        ("manager", {"S_PERSON"}, None, ["recent", "frequent"]),
        ("capital", {"CAPITAL"}, None, ["registration", "recent",
                                        "frequent"]),
        ("founded", {"FOUNDED"}, None, ["registration", "recent",
                                        "frequent"]),
        ("activity_code", {"ACTIVITY_CODE"}, None,
         ["registration", "recent", "frequent"]),
        ("activity", {"ACTIVITY"}, None, ["frequent", "recent"]),
        ("hours", {"HOURS"}, None, ["frequent", "recent"]),
        ("staff", {"STAFF"}, None, ["recent", "frequent"]),
    ]
    for name, labels, c_labels, order in rules:
        pool, weak = spans_for(labels, spans, author, c_labels)
        best, others, status = pick(pool, order, fdate, ftype)
        fields[name] = field_record(name, best, others, status, weak)
    # ---- legal form: the LEGAL_FORM span, else parsed from the name
    pool, weak = spans_for({"LEGAL_FORM"}, spans, author)
    best, others, status = pick(pool, ["registration", "recent",
                                       "frequent"], fdate, ftype)
    if best:
        fields["legal_form"] = field_record("legal_form", best, others,
                                            status, weak)
    elif legal and N.parse_legal_form(legal.value()["text"], country):
        form = N.parse_legal_form(legal.value()["text"], country)
        fields["legal_form"] = {
            "field": "legal_form", "status": "found", "weak": False,
            "value": {"text": legal.value()["text"], "normalized": {
                k: v for k, v in form.items() if k != "ok"}},
            "sources": legal.sources(), "alternatives": [],
            "parsed_from_name": True}
    else:
        fields["legal_form"] = field_record("legal_form", None, [],
                                            "not_found")
    # ---- lists: registration numbers, phones, e-mails, web sites
    for name, labels, c_labels in (("reg_id", {"S_REG_ID"}, {"C_REG_ID"}),
                                   ("phones", {"S_PHONE"}, None),
                                   ("emails", {"S_EMAIL"}, None),
                                   ("websites", {"S_URL"}, None),
                                   ("certifications", {"CERT"}, None)):
        pool, weak = spans_for(labels, spans, author, c_labels)
        cands = sorted(group(pool), key=lambda c: (-len(c.spans),
                                                   str(c.key)))
        doubtful = []
        if name == "reg_id":
            # a number that fits no format of the country, or fails its
            # check digit (an OCR slip, a typo) is only an alternative
            good = [c for c in cands if (c.spans[0].norm or {}).get("ok")
                    and (c.spans[0].norm or {}).get("type") != "unknown"]
            if good:
                doubtful = [c for c in cands if c not in good]
                cands = good
        fields[name] = {"field": name, "status": "found" if cands else
                        "not_found", "weak": weak,
                        "value": [c.value() for c in cands],
                        "sources": [s for c in cands for s in c.sources()],
                        "alternatives": [{"value": c.value(),
                                          "sources": c.sources()}
                                         for c in doubtful]}
    phones, emails = fields["phones"], fields["emails"]
    fields["contact"] = {
        "field": "contact",
        "status": "found" if phones["value"] or emails["value"]
        else "not_found", "weak": phones["weak"] and emails["weak"],
        "value": {"phones": phones["value"], "emails": emails["value"]},
        "sources": phones["sources"] + emails["sources"],
        "alternatives": []}
    # ---- revenue (15.7)
    fields["revenue"] = revenue_field(spans, author, chunks, fdate)
    # ---- services
    fields["services"] = services_field(spans, author, chunks)
    # ---- clients
    fields["clients"] = clients_field(spans, author, ftype, cluster_of,
                                      business)
    fields["country"] = {"field": "country", "status": "found" if country
                         else "not_found", "weak": False,
                         "value": {"text": country,
                                   "confidence": round(confidence, 3),
                                   "votes": votes},
                         "sources": [], "alternatives": []}
    found = sum(1 for f in REQUIRED if fields[f]["status"] == "found")
    to_ask = [f for f in REQUIRED if fields[f]["status"] != "found"]
    summary = {"business_name": (fields["business_name"].get("legal_name")
                                 if fields["business_name"]["value"]
                                 else None),
               "country": country, "coverage": round(found / len(REQUIRED),
                                                     4),
               "found": found, "required": len(REQUIRED), "to_ask": to_ask,
               "model": model,
               "computed": datetime.datetime.now(datetime.timezone.utc)
               .isoformat(timespec="seconds")}
    return {"summary": summary, "fields": fields,
            "files": {files[f]: {"type": ftype.get(f),
                                 "date": fdate.get(f),
                                 "author": author.get(f)} for f in files}}


def revenue_field(spans, author, chunks, fdate):
    revs, weak = spans_for({"REVENUE"}, spans, author)
    years = [sp for sp in spans if sp.label == "REVENUE_YEAR" and
             author.get(sp.file_id) in ("business", "unknown")]
    by_year = {}
    for r, y in pair_revenue(revs, years, chunks):
        yv = y.norm.get("year") if y is not None and y.norm.get("ok") \
            else None
        by_year.setdefault(yv, []).append((r, y))
    per_year = []
    for yv in sorted([k for k in by_year if k is not None], reverse=True):
        best, others, status = pick([r for r, _ in by_year[yv]],
                                    ["recent", "frequent"], fdate, {})
        year_span = next(y for r, y in by_year[yv] if r in best.spans)
        per_year.append({"year": yv, "status": status,
                         "value": best.value(),
                         "year_text": year_span.text,
                         "sources": best.sources() + [year_span.source()],
                         "alternatives": [{"value": c.value(),
                                           "sources": c.sources()}
                                          for c in others[:5]]})
    unknown = by_year.get(None, [])
    if not per_year:
        return {"field": "revenue", "status": "not_found", "weak": weak,
                "value": None, "sources": [s for r, _ in unknown
                                           for s in [r.source()]],
                "alternatives": [], "by_year": [],
                "unknown_year": [r.value() if hasattr(r, "value") else
                                 {"text": r.text} for r, _ in unknown]}
    head = per_year[0]
    return {"field": "revenue", "status": head["status"], "weak": weak,
            "value": dict(head["value"], year=head["year"],
                          year_text=head["year_text"]),
            "sources": head["sources"], "alternatives": [],
            "by_year": per_year,
            "unknown_year": [{"text": r.text} for r, _ in unknown]}


def services_field(spans, author, chunks):
    """Distinct services with counts and the summed LINE_TOTAL of the
    same line; top 30."""
    pool, weak = spans_for({"SERVICE"}, spans, author)
    totals = [sp for sp in spans if sp.label == "LINE_TOTAL" and
              author.get(sp.file_id) in ("business", "unknown")]
    cands = group(pool)
    out = []
    for c in cands:
        amount = 0.0
        for sp in c.spans:
            text = chunks[sp.chunk_id][4] or ""
            line_end = text.find("\n", sp.end)
            line_end = len(text) if line_end < 0 else line_end
            for t in totals:
                if t.chunk_id == sp.chunk_id and sp.end <= t.start < \
                        line_end and t.norm.get("ok"):
                    amount += t.norm.get("value") or 0.0
                    break
        out.append((len(c.spans), amount, c))
    out.sort(key=lambda x: (-x[0], -x[1], str(x[2].key)))
    return {"field": "services", "status": "found" if out else "not_found",
            "weak": weak,
            "value": [dict(c.value(), count=n, line_total=round(a, 2))
                      for n, a, c in out[:30]],
            "sources": [s for _, _, c in out[:30] for s in c.sources()],
            "alternatives": []}


def clients_field(spans, author, ftype, cluster_of, business):
    orgs = {}
    for sp in spans:
        if sp.label != "C_NAME" or author.get(sp.file_id) != "business":
            continue
        if ftype.get(sp.file_id) not in CLIENT_DOCS:
            continue
        cl = cluster_of.get(sp.id)
        if cl is None or cl == business:
            continue
        orgs.setdefault(cl, []).append(sp)
    totals = {}
    for sp in spans:
        if sp.label == "DOC_TOTAL" and sp.norm.get("ok"):
            totals.setdefault(sp.file_id, sp.norm.get("value") or 0.0)
    organisations = []
    for cl, sps in sorted(orgs.items()):
        cand = Candidate(("client", cl))
        cand.spans = sps
        inv_files = {sp.file_id for sp in sps
                     if ftype.get(sp.file_id) == "invoice"}
        organisations.append(dict(cand.value(), invoices=len(inv_files),
                                  total=round(sum(totals.get(f, 0.0)
                                                  for f in inv_files), 2),
                                  sources=cand.sources()))
    with_c = {sp.file_id for sp in spans if sp.label == "C_NAME"}
    private = sum(1 for f, a in author.items()
                  if a == "business" and ftype.get(f) == "invoice" and
                  f not in with_c)
    found = bool(organisations) or private >= 3
    return {"field": "clients", "status": "found" if found else
            "not_found", "weak": False,
            "value": {"organisations": organisations,
                      "private_customer_documents": private},
            "sources": [s for o in organisations for s in o["sources"]],
            "alternatives": []}


# =====================================================================
#  15.9 - the invariant
# =====================================================================
def check_invariant(profile, db):
    """Every value shown is the exact text of one of its sources, or the
    normalization of that text. -> list of problems (empty = OK)."""
    rows = {r[0]: r[1] for r in db.execute("SELECT id, text FROM "
                                           "extractions")}
    problems = []

    def check_value(field, value, sources):
        if value is None:
            return
        texts = {rows.get(s["extraction"]) for s in sources}
        text = value.get("text")
        if text is None:
            return
        if text in texts:
            return
        # the trading name may be the legal name minus its legal form
        if any(t and strip_legal_form(t) == text for t in texts):
            return
        problems.append((field, text))

    for name, f in profile["fields"].items():
        if name in ("country", "contact"):
            continue
        v = f.get("value")
        if isinstance(v, list):
            for item in v:
                check_value(name, item, f["sources"])
        elif isinstance(v, dict) and name == "clients":
            for org in v["organisations"]:
                check_value(name, org, org["sources"])
        elif isinstance(v, dict):
            check_value(name, v, f["sources"])
        if name == "business_name" and f.get("value"):
            check_value(name, {"text": f.get("legal_name")}, f["sources"])
            check_value(name, {"text": f.get("trading_name")},
                        f.get("trading_sources", []))
    return problems


# =====================================================================
#  writing
# =====================================================================
def write(db, profile, db_path=None):
    db.execute("CREATE TABLE IF NOT EXISTS profile (field TEXT PRIMARY KEY, "
               "value TEXT, status TEXT, alternatives TEXT, sources TEXT, "
               "computed TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS profile_summary (id INTEGER "
               "PRIMARY KEY CHECK (id = 1), business_name TEXT, country "
               "TEXT, coverage REAL, found INTEGER, required INTEGER, "
               "to_ask TEXT, model TEXT, computed TEXT)")
    s = profile["summary"]
    with db:
        db.execute("DELETE FROM profile")
        for name, f in profile["fields"].items():
            db.execute("INSERT INTO profile VALUES (?, ?, ?, ?, ?, ?)",
                       (name, json.dumps(f.get("value"), ensure_ascii=False),
                        f["status"], json.dumps(f.get("alternatives"),
                                                ensure_ascii=False),
                        json.dumps(f.get("sources"), ensure_ascii=False),
                        s["computed"]))
        db.execute("DELETE FROM profile_summary")
        db.execute("INSERT INTO profile_summary VALUES (1, ?, ?, ?, ?, ?, "
                   "?, ?, ?)", (s["business_name"], s["country"],
                                s["coverage"], s["found"], s["required"],
                                json.dumps(s["to_ask"]), s["model"],
                                s["computed"]))
    if db_path:
        out = pathlib.Path(db_path).with_name("profile.json")
        out.write_text(json.dumps(profile, ensure_ascii=False, indent=1),
                       encoding="utf-8")


def show(profile):
    s = profile["summary"]
    print("Business: %s   country: %s   coverage: %.0f%% (%d/%d)" % (
        s["business_name"], s["country"], 100 * s["coverage"], s["found"],
        s["required"]))
    print("%-16s %-10s %-45s %s" % ("field", "status", "value", "sources"))
    for name, f in profile["fields"].items():
        v = f.get("value")
        if isinstance(v, list):
            text = "; ".join(x.get("text", "") for x in v[:3]) + \
                (" (+%d)" % (len(v) - 3) if len(v) > 3 else "")
        elif isinstance(v, dict):
            text = v.get("text") if "text" in v else json.dumps(
                v, ensure_ascii=False)
        else:
            text = "" if v is None else str(v)
        src = sorted({"%s p.%s" % (x["file"], x["page"])
                      for x in f.get("sources", [])})
        print("%-16s %-10s %-45s %s" % (name, f["status"] + (
            " (weak)" if f.get("weak") else ""), str(text)[:45],
            ", ".join(src[:3]) + (" ..." if len(src) > 3 else "")))


def main():
    ap = argparse.ArgumentParser(description="Build the business profile")
    ap.add_argument("db", help="path of documents.db")
    ap.add_argument("--model", help="model id (default: the latest)")
    args = ap.parse_args()
    db = sqlite3.connect(args.db)
    profile = build(db, args.model)
    if profile is None:
        print("No extractions in this database - run extract_db.py first.")
        return 1
    write(db, profile, args.db)
    show(profile)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

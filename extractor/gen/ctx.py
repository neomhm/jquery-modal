"""
ctx.py - everything a layout needs to write ONE document.

A layout never writes a labelled value by hand. It asks the context:
    ctx.name(org)          -> the name, labelled S_NAME or C_NAME
    ctx.money(v, "DOC_TOTAL")
    ctx.say("founded")     -> a sentence template with its slots filled
The context knows who the subject (S) and the counterparty (C) of the
document are (rule R5), so the same organisation is labelled S_NAME in
its own invoice and C_NAME in a supplier's invoice, and a bank or a
private person is never labelled at all (R7, R9).
"""
import datetime
import re
import unicodedata

from gen import data as D
from gen import formats as F
from gen import holdout as H
from gen import ids as I
from gen import names as N
from gen.doc import Doc
from gen.text import AText

SLOT_RE = re.compile(r"\{([^{}]*)\}")
KO_PARTICLES = {"은/는": ("은", "는"), "이/가": ("이", "가"),
                "을/를": ("을", "를"), "과/와": ("과", "와"),
                "으로/로": ("으로", "로")}
# Korean reading of the last digit / letter, for particles after
# numbers and Latin names: True = ends in a consonant (batchim)
KO_DIGIT_BATCHIM = {"0": True, "1": True, "2": False, "3": True, "4": False,
                    "5": False, "6": True, "7": True, "8": True, "9": False}
KO_DIGIT_RIEUL = {"1", "7", "8"}


# keywords that only exist in some countries (a Japanese invoice mixed
# with English never says "HST"; a Mexican one never says "NIF")
ONLY_IN = {}
for _words, _countries in [
        (["GST", "GST No.", "GST Number", "GST Reg. No."],
         ["IN", "AU", "CA", "SG", "NG"]),
        (["HST", "GST/HST", "PST", "GST/HST No.", "TPS", "TVQ", "TVH",
          "No TPS", "No TVQ"], ["CA"]),
        (["CGST", "SGST", "IGST", "GSTIN", "HSN/SAC", "HSN Code"], ["IN"]),
        (["Sales Tax", "Sales Tax No."], ["US"]),
        (["N° TVA intracommunautaire", "N° de TVA intracommunautaire",
          "TVA intracom."], ["FR", "BE"]),
        (["IVA trasladado", "RFC", "Clave ProdServ"], ["MX"]),
        (["Impuesto al Valor Agregado"], ["MX", "AR", "CO", "CL"]),
        (["Impuesto sobre el Valor Añadido", "NIF", "CIF", "NIF-IVA",
          "N.º de IVA intracomunitario", "NIF intracomunitario"], ["ES"]),
        (["CUIT"], ["AR"]), (["NIT"], ["CO"]), (["RUT", "R.U.T."],
                                                ["CL", "CO"]),
        (["消费税", "消费税（GST）", "消费税注册号", "GST注册号码"], ["SG"]),
        (["增值税", "增值税额", "增值税纳税人识别号", "统一社会信用代码",
          "统一社会信用代码/纳税人识别号"], ["CN"]),
        (["營業稅", "營業稅額", "加值型營業稅", "營業稅 Tax", "統一編號", "統編",
          "營業人統一編號", "扣繳單位統一編號", "統一編號 Tax ID No."], ["TW"]),
        (["商業登記號碼", "稅務檔案號碼", "利得稅檔案號碼"], ["HK"]),
        (["ИНН"], ["RU"]), (["БИН", "БИН/ИИН"], ["KZ"]),
        (["УНП", "Учётный номер плательщика"], ["BY"]),
        (["رقم التسجيل الضريبي (TRN)"], ["AE"]),
        (["التعريف الجبائي"], ["MA"]),
        (["رقم البطاقة الضريبية", "رقم الملف الضريبي"], ["EG"])]:
    for _w in _words:
        ONLY_IN[_w] = set(_countries)
NOT_IN = {w: {"US", "CA", "AU", "IN"} for w in
          ["VAT", "VAT No.", "VAT Number", "VAT Reg. No.",
           "VAT Registration No."]}
NOT_IN.update({w: {"CA"} for w in ["TVA", "T.V.A.", "N° de TVA",
                                   "Numéro de TVA", "N° TVA",
                                   "N° d'identification TVA"]})


def country_ok(word, country):
    if word in ONLY_IN and country not in ONLY_IN[word]:
        return False
    return not (word in NOT_IN and country in NOT_IN[word])


class CannotFill(Exception):
    """A template needs a fact this document does not have."""


def _batchim(ch):
    """(has final consonant, final is ㄹ) for the last character."""
    if "가" <= ch <= "힣":
        t = (ord(ch) - 0xAC00) % 28
        return t != 0, t == 8
    if ch.isdigit():
        return KO_DIGIT_BATCHIM[ch], ch in KO_DIGIT_RIEUL
    if ch.isalpha() and ch.isascii():
        return ch.lower() in "lmnr", ch.lower() in "lr"
    return False, False


class DocCtx:

    def __init__(self, rng, biz, S, C, doc_type, kind, layout, rules,
                 date=None, old=False, audience=None):
        self.rng = rng
        self.biz = biz
        self.S = S
        self.C = C
        self.loc = biz.loc
        self.key = self.loc["data"]
        self.lang = self.loc["lang"]
        self.country = self.loc["country"]
        self.lex = D.lexicon(self.key)
        self.sent = D.sentences(self.key)
        self.titles_ = D.titles(self.key)
        self.rules = rules
        self.old = old                  # an old document (outdated values)
        self.doc = Doc(doc_type, kind, layout)
        self.doc.date = date
        self.audience = audience        # clients named in a brochure
        loc = self.loc
        # digits of the document (section 10.7)
        r = rng.random()
        self.digits = None
        for script, share in (loc.get("digits") or {}).items():
            if r < share:
                self.digits = script
                break
            r -= share
        self.fmt = F.Fmt(rng, loc, self.lex, self.digits)
        settings = D.language_settings()
        self.english = rng.random() < settings["english_mix"].get(self.lang,
                                                                   0)
        self.en = D.lexicon("en") if self.lang != "en" else None
        self.bi_lex = None
        if rng.random() < loc.get("bilingual", 0.05):
            if self.lang != "en":
                self.bi_lex = D.lexicon("en")
            elif self.country == "CA":
                self.bi_lex = D.lexicon("fr")
        self.no_accents = rng.random() < settings["accents_dropped"].get(
            self.lang, 0)
        self.caps = self.lang in ("en", "fr", "es", "it", "ru") and \
            rng.random() < 0.10
        self._kw = {}
        self._used_clients = []
        self._staff_n = None
        self._counts = {}
        # which name of the subject this document uses
        self.s_legal = True
        if S is not None and S.trading != S.legal:
            formal = doc_type in ("invoice", "quote", "registration",
                                  "contract", "financials", "terms")
            self.s_legal = rng.random() < (0.7 if formal else 0.3)

    # -----------------------------------------------------------------
    #  words
    # -----------------------------------------------------------------
    def kw(self, concept, fresh=False):
        """A keyword of the lexicon; the same variant all through the
        document (unless fresh). Mixed with English in some documents,
        bilingual in others ("Facture / Invoice")."""
        if concept in self._kw and not fresh:
            return self._kw[concept]
        def fit(words):
            return [w for w in words if country_ok(w, self.country)]

        variants = fit((self.lex.get("kw") or {}).get(concept) or []) or \
            (self.lex.get("kw") or {}).get(concept) or [concept]
        word = self.rng.choice(variants)
        if self.english and self.en and self.rng.random() < 0.5:
            en = fit((self.en.get("kw") or {}).get(concept) or [])
            if en:
                word = self.rng.choice(en)
        elif self.bi_lex and self.rng.random() < 0.8:
            other = fit((self.bi_lex.get("kw") or {}).get(concept) or [])
            if other:
                word = "%s / %s" % (word, self.rng.choice(other))
        self._kw[concept] = word
        return word

    def colon(self):
        """The colon used after a label in this language."""
        if self.lang in ("zh", "ja"):
            return self.rng.choice(["：", "：", ":"])
        if self.lang == "fr":
            return " :"
        return ":"

    def label(self, concept, sep=None):
        """'Label: ' ready to be followed by a value."""
        word = self.kw(concept)
        if sep is None:
            sep = self.colon() + ("" if self.lang in ("zh", "ja") and
                                  self.rng.random() < 0.7 else " ")
        return word + sep

    def unit(self, code):
        words = (self.lex.get("units") or {}).get(code) or [code]
        return words[0]

    def title(self, section, key, fallback=None):
        items = (self.titles_.get(section) or {}).get(key)
        if not items:
            return fallback or key
        t = self.rng.choice(items)
        if self.bi_lex and self.rng.random() < 0.5:
            other = (D.titles("en" if self.lang != "en" else "fr")
                     .get(section) or {}).get(key)
            if other:
                t = "%s / %s" % (t, self.rng.choice(other))
        return t

    def lst(self, name):
        return self.lex.get(name) or []

    def join_list(self, items):
        lj = self.lex.get("list_join") or {"sep": ", ", "last": " and "}
        out = AText()
        for k, item in enumerate(items):
            if k:
                out.add(lj["last"] if k == len(items) - 1 else lj["sep"])
            out.add(item)
        return out

    # -----------------------------------------------------------------
    #  roles
    # -----------------------------------------------------------------
    def role(self, org):
        """'S', 'C' or None for an organisation in THIS document."""
        if org is None or isinstance(org, dict):
            return None                 # private persons are never C_
        if self.S is not None and org is self.S:
            return "S"
        if self.C is not None and org is self.C:
            return "C"
        return None

    # -----------------------------------------------------------------
    #  labelled values
    # -----------------------------------------------------------------
    def name(self, org, legal=None, role=None):
        """The organisation's name, labelled by its role."""
        if isinstance(org, dict):                      # a private person
            return AText(org["full"])
        role = role or self.role(org)
        if legal is None:
            legal = self.s_legal if role == "S" else True
        text = org.legal if legal else org.trading
        if role == "S" and self.caps:
            text = text.upper()
        label = {"S": "S_NAME", "C": "C_NAME"}.get(role)
        return AText(text, label)

    def other_org_name(self, org):
        """Another organisation mentioned in passing: always O."""
        return AText(org.legal)

    def current_address(self, org):
        if org is self.biz and getattr(self.biz, "outdated", None) and \
                self.biz.outdated["field"] == "address":
            if self.doc.date and self.doc.date < self.biz.move_date:
                return self.biz.old_address
            if self.old:
                return self.biz.old_address
        return org.address if not isinstance(org, dict) else org["address"]

    def addr(self, org, multiline=False, role=None):
        role = role or self.role(org)
        a = self.current_address(org)
        text = "\n".join(a["lines"]) if multiline else a["one"]
        label = {"S": "S_ADDRESS", "C": "C_ADDRESS"}.get(role)
        return AText(text, label)

    def phone(self, org, which=0, style=None):
        role = self.role(org)
        phones = org.phones if not isinstance(org, dict) else []
        if not phones:
            raise CannotFill("phone")
        text, truth = self.fmt.phone(phones[min(which, len(phones) - 1)],
                                     style)
        return AText(text, "S_PHONE" if role == "S" else None, truth)

    def fax(self, org):
        if not getattr(org, "fax", None):
            raise CannotFill("fax")
        text, _ = self.fmt.phone(org.fax)
        return AText(text, trap="T6")

    def email(self, org):
        if not getattr(org, "email", None):
            raise CannotFill("email")
        role = self.role(org)
        return AText(org.email, "S_EMAIL" if role == "S" else None,
                     {"kind": "email", "value": org.email.lower()})

    def url(self, org, social=None):
        if social is None:
            social = bool(org.social) and (not org.website or
                                           self.rng.random() < 0.3)
        role = self.role(org)
        if social and org.social:
            text = org.social
        elif org.website:
            text = N.show_url(self.rng, org.website)
        else:
            raise CannotFill("url")
        host = re.sub(r"^https?://", "", text).split("/")[0]
        host = host[4:] if host.startswith("www.") else host
        return AText(text, "S_URL" if role == "S" else None,
                     {"kind": "url", "host": host.lower()})

    def person(self, org, short=None):
        if getattr(org, "manager", None) is None:
            raise CannotFill("person")
        m = org.manager
        if short is None:
            short = self.rng.random() < 0.25
        text = m["short"] if short else m["full"]
        role = self.role(org)
        return AText(text, "S_PERSON" if role == "S" else None)

    def reg_id(self, org, which=None, keyword=True, types=None):
        """'SIRET 123 456 782 00010': keyword O, number labelled."""
        ids = [r for r in getattr(org, "reg_ids", [])
               if types is None or r["type"] in types]
        if not ids:
            raise CannotFill("reg_id")
        if which is not None:
            r = ids[which % len(ids)]
        else:
            # several numbers in one template: a different type each time
            used = getattr(self, "_used_reg", set())
            fresh = [x for x in ids if (id(org), x["type"]) not in used]
            r = self.rng.choice(fresh or ids)
            used.add((id(org), r["type"]))
            self._used_reg = used
        role = self.role(org)
        label = {"S": "S_REG_ID", "C": "C_REG_ID"}.get(role)
        out = AText()
        if keyword:
            out.add(self.rng.choice(r["labels"]))
            out.add(self.colon() + " " if self.rng.random() < 0.4 else " ")
        shown = I.show(self.rng, r["type"], r["compact"])
        # the truth is what normalize() reads from the text: its letters
        # and digits, upper-case ("315095703 RT0001" -> "315095703RT0001")
        compact = re.sub(r"[^0-9A-Za-z]", "", unicodedata.normalize(
            "NFKC", shown)).upper()
        out.add(shown, label, {"kind": "reg_id", "compact": compact,
                               "type": r["type"]})
        return out

    def legal_form(self, org, long=None):
        if org.cls == "sole_trader" and org.form["attach"] and \
                org.form["code"] not in ("RU_IP", "KZ_IP", "BY_IP"):
            pass
        form = org.form
        text = org.form_text
        if long is None:
            long = form.get("long") and self.rng.random() < 0.25
        if long and form.get("long"):
            text = self.rng.choice(form["long"])
        role = self.role(org)
        return AText(text, "LEGAL_FORM" if role == "S" else None,
                     {"kind": "legal_form", "code": form["code"]})

    def capital(self, org, prose=None):
        if not getattr(org, "capital", None):
            raise CannotFill("capital")
        if prose is None:
            prose = self.rng.random() < 0.3
        text, truth = (self.fmt.money_prose(org.capital) if prose else
                       self.fmt.money(org.capital, decimals=0
                                      if self.rng.random() < 0.7 else None))
        return AText(text, "CAPITAL" if self.role(org) == "S" else None,
                     truth)

    def founded(self, org, kind="year"):
        if getattr(org, "founded", None) is None:
            raise CannotFill("founded")
        text, truth = self.fmt.founded(org.founded, kind)
        return AText(text, "FOUNDED" if self.role(org) == "S" else None,
                     truth)

    def staff_value(self, org):
        if org is self.biz and self.old and getattr(org, "old_staff", None):
            return org.old_staff
        return org.staff

    def staff(self, org, qualifier=None):
        n = self.staff_value(org)
        if not n:
            raise CannotFill("staff")
        text, truth = self.fmt.staff(n, qualifier)
        self._staff_n = truth["max"] or truth["value"]
        return AText(text, "STAFF" if self.role(org) == "S" else None, truth)

    def revenue(self, org, year):
        value = org.revenue[year]
        text, truth = self.fmt.money_prose(value)
        return AText(text, "REVENUE" if self.role(org) == "S" else None,
                     truth)

    def revenue_full(self, org, year, style="doc"):
        text, truth = self.fmt.money(org.revenue[year], style,
                                     decimals=0 if self.rng.random() < 0.6
                                     else None)
        return AText(text, "REVENUE" if self.role(org) == "S" else None,
                     truth)

    def rev_year(self, org, year):
        text, truth = self.fmt.rev_year(year)
        return AText(text, "REVENUE_YEAR" if self.role(org) == "S" else None,
                     truth)

    def activity(self, org):
        phrases = (org.act.get("phrases") or {}).get(self.key)
        if not phrases:
            raise CannotFill("activity")
        return AText(self.rng.choice(phrases),
                     "ACTIVITY" if self.role(org) == "S" else None)

    def act_code(self, org, keyword=True):
        if not getattr(org, "act_code", None):
            raise CannotFill("activity_code")
        out = AText()
        if keyword:
            labels = (self.loc.get("activity_code") or {}).get("labels") or \
                ["Code"]
            out.add(self.rng.choice(labels))
            out.add(self.colon() + " " if self.rng.random() < 0.4 else " ")
        code = org.act_code
        system = org.act_system
        shown = code
        if system == "NAF" and self.rng.random() < 0.4:
            shown = code.replace(".", "")
        out.add(shown, "ACTIVITY_CODE" if self.role(org) == "S" else None,
                {"kind": "activity_code", "system": system,
                 "code": code.replace(".", "").upper()})
        return out

    def service(self, name, org=None):
        org = org or self.S
        return AText(name, "SERVICE" if self.role(org) == "S" else None)

    def hours(self, org, style="compact"):
        if not getattr(org, "hours", None):
            raise CannotFill("hours")
        text, _ = self.fmt.hours(org.hours, style)
        return AText(text, "HOURS" if self.role(org) == "S" else None)

    def cert(self, name, org=None):
        org = org or self.S
        return AText(name, "CERT" if self.role(org) == "S" else None)

    def doc_date(self, d=None, style=None):
        """The issue date. A fact type (R6): it belongs to S, so in a
        document with no S (a letter from a bank or a tax office) the
        date is O."""
        d = d or self.doc.date
        text, truth = self.fmt.date(d, style)
        if self.S is None:
            return AText(text)
        return AText(text, "DOC_DATE", truth)

    def date_o(self, d, style=None):
        text, _ = self.fmt.date(d, style)
        return text

    def money(self, value, label=None, style="doc", decimals=None):
        text, truth = self.fmt.money(value, style, decimals)
        return AText(text, label, truth if label else None)

    def raw_money(self, value, label=None):
        text, truth = self.fmt.raw_number(value)
        return AText(text, label, truth if label else None)

    # -----------------------------------------------------------------
    #  templates
    # -----------------------------------------------------------------
    def can_fill(self, text):
        for m in SLOT_RE.finditer(text):
            name = m.group(1)
            if name in KO_PARTICLES:
                continue
            if not self.slot_available(name):
                return False
        return True

    def slot_available(self, name):
        S, biz = self.S, self.biz
        is_biz = S is biz and S is not None
        pres = biz.presence if is_biz else {}

        def ok(fact):
            return (not is_biz) or pres.get(fact, True)

        if name in ("S_NAME", "S_NAME:legal"):
            return S is not None
        if name.startswith("S_") or name in (
                "LEGAL_FORM", "CAPITAL", "STAFF", "REVENUE", "REVENUE_YEAR",
                "REVENUE_PREV", "REVENUE_YEAR_PREV", "ACTIVITY",
                "ACTIVITY_CODE", "SERVICE", "SERVICE_LIST", "HOURS",
                "HOURS:prose", "CERT", "CERT_LIST") or \
                name.startswith("FOUNDED"):
            if S is None:
                return False
        if name == "S_ADDRESS":
            return True
        if name == "S_PHONE":
            return bool(S.phones) and ok("phone")
        if name == "S_EMAIL":
            return bool(S.email) and ok("email")
        if name == "S_URL":
            return bool(S.website or S.social) and ok("website")
        if name == "S_PERSON":
            return ok("manager")
        if name == "S_REG_ID":
            return bool(S.reg_ids) and ok("reg_id")
        if name == "LEGAL_FORM":
            return ok("legal_form") and S.cls != "sole_trader" or \
                (S.cls == "sole_trader" and ok("legal_form"))
        if name == "CAPITAL":
            return bool(getattr(S, "capital", None)) and ok("capital")
        if name.startswith("FOUNDED"):
            return getattr(S, "founded", None) is not None and ok("founded")
        if name == "STAFF":
            return bool(getattr(S, "staff", 0)) and ok("staff")
        if name in ("REVENUE", "REVENUE_YEAR"):
            return bool(getattr(S, "revenue", None)) and ok("revenue")
        if name in ("REVENUE_PREV", "REVENUE_YEAR_PREV"):
            return len(getattr(S, "revenue", {}) or {}) >= 2 and \
                ok("revenue")
        if name == "ACTIVITY":
            return bool((S.act.get("phrases") or {}).get(self.key)) and \
                ok("activity")
        if name == "ACTIVITY_CODE":
            return bool(getattr(S, "act_code", None)) and ok("activity_code")
        if name in ("SERVICE", "SERVICE_LIST"):
            return bool(getattr(S, "services", None))
        if name.startswith("HOURS"):
            return bool(getattr(S, "hours", None)) and ok("hours")
        if name in ("CERT", "CERT_LIST"):
            return bool(getattr(S, "certs", None)) and ok("certs")
        if name in ("C_NAME", "C_ADDRESS", "C_REG_ID"):
            if self.C is not None and not isinstance(self.C, dict):
                if name == "C_REG_ID":
                    return bool(self.C.reg_ids)
                return True
            if name == "C_NAME" and self.C is None:
                return len(self._client_pool()) > len(self._used_clients)
            return False
        if name == "C_NAME_LIST":
            return self.C is None and len(self._client_pool()) >= 2
        if name == "DOC_DATE":
            return self.doc.date is not None
        if name in ("person", "position"):
            return True
        return True

    def _client_pool(self):
        return [c for c in (self.audience if self.audience is not None
                            else self.biz.clients)]

    def next_client(self):
        pool = [c for c in self._client_pool()
                if c not in self._used_clients]
        if not pool:
            raise CannotFill("C_NAME")
        c = self.rng.choice(pool)
        self._used_clients.append(c)
        return c

    def fill(self, text, tid=None):
        """Fills a template's slots. Raises CannotFill."""
        out = AText()
        pos = 0
        self._used_reg = set()
        for m in SLOT_RE.finditer(text):
            literal = text[pos:m.start()]
            if literal.startswith(".") and out.text.endswith("."):
                literal = literal[1:]           # "Inc." + "." -> "Inc."
            out.add(literal)
            name = m.group(1)
            if name in KO_PARTICLES:
                out.add(self._particle(out.text, name))
            elif name in ("year", "client_founded") and \
                    self.lang in ("zh", "ja", "ko"):
                value = self.plain(name)
                follow = text[m.end():m.end() + 1]
                suffix = "년" if self.lang == "ko" else "年"
                out.add(value if follow == suffix else value + suffix)
            else:
                out.add(self.slot(name))
            pos = m.end()
        literal = text[pos:]
        if literal.startswith(".") and out.text.endswith("."):
            literal = literal[1:]
        out.add(literal)
        if tid:
            self.doc.templates.append(tid)
        return out

    def _particle(self, before, name):
        with_c, without_c = KO_PARTICLES[name]
        ch = before.rstrip()[-1:] or " "
        k = len(before.rstrip())
        while ch in ")）」』\"'»" and k > 1:
            k -= 1
            ch = before.rstrip()[k - 1]
        final, rieul = _batchim(ch)
        tail = before.rstrip()[:k].lower()
        if tail.endswith(("kg", "g")) and ch.lower() == "g":
            final, rieul = True, False           # 그램: ends in ㅁ
        elif tail.endswith(("ml", "l", "m", "cm", "km")):
            final, rieul = False, False          # 리터 / 미터
        if name == "으로/로":
            return without_c if (not final or rieul) else with_c
        return with_c if final else without_c

    def say(self, category, trap=None, need=None):
        """A holdout-aware sentence of a category ('founded', 'traps' ...).
        Returns an AText, or None when no template fits."""
        items = self.sent.get(category) or []
        if trap:
            items = [t for t in items if t.get("trap") == trap]
        pool = []
        for t in items:
            if t.get("countries") and self.country not in t["countries"]:
                continue                  # a TW-only or HK-only template
            group = H.group_of(self.key, t["id"])
            if group not in self.rules["allowed"]:
                continue
            if need and not any("{%s}" % n in t["text"] for n in need):
                continue
            if not self.can_fill(t["text"]):
                continue
            pool.append((t, group))
        if not pool:
            return None
        prefer = self.rules.get("prefer")
        if prefer and self.rng.random() < self.rules.get("p_prefer", 0.5):
            held = [p for p in pool if p[1] == prefer]
            if held:
                pool = held
        t, group = self.rng.choice(pool)
        try:
            at = self.fill(t["text"], t["id"])
        except CannotFill:
            return None
        if trap or t.get("trap"):
            at.mark_trap(trap or t["trap"])
        return at

    def phrase(self, *path, tid_prefix=None, **_):
        """A non-held-out template: phrase('letters', 'move', 'body')."""
        node = self.sent
        for key in path:
            node = (node or {}).get(key) if isinstance(node, dict) else None
        if not node:
            return None
        pool = [(k, t) for k, t in enumerate(node) if self.can_fill(
            t["text"] if isinstance(t, dict) else t)]
        if not pool:
            return None
        k, t = self.rng.choice(pool)
        text = t["text"] if isinstance(t, dict) else t
        tid = t.get("id") if isinstance(t, dict) else \
            "%s.%s.%02d" % (".".join(path), self.lang, k + 1)
        try:
            return self.fill(text, tid)
        except CannotFill:
            return None

    # -----------------------------------------------------------------
    #  one slot
    # -----------------------------------------------------------------
    def slot(self, name):
        S, rng, fmt = self.S, self.rng, self.fmt
        if name == "S_NAME":
            return self.name(S)
        if name == "S_NAME:legal":
            return self.name(S, legal=True)
        if name == "S_ADDRESS":
            return self.addr(S)
        if name == "S_PHONE":
            return self.phone(S)
        if name == "S_EMAIL":
            return self.email(S)
        if name == "S_URL":
            return self.url(S)
        if name == "S_PERSON":
            return self.person(S)
        if name == "S_REG_ID":
            return self.reg_id(S)
        if name == "C_NAME":
            if self.C is not None and not isinstance(self.C, dict):
                return self.name(self.C)
            c = self.next_client()
            return AText(c.legal, "C_NAME")
        if name == "C_NAME_LIST":
            k = min(len(self._client_pool()) - len(self._used_clients),
                    rng.randint(2, 4))
            if k < 2:
                raise CannotFill("C_NAME_LIST")
            names = [AText(self.next_client().legal, "C_NAME")
                     for _ in range(k)]
            return self.join_list(names)
        if name == "C_ADDRESS":
            return self.addr(self.C)
        if name == "C_REG_ID":
            return self.reg_id(self.C)
        if name == "LEGAL_FORM":
            return self.legal_form(S)
        if name == "CAPITAL":
            return self.capital(S)
        if name == "FOUNDED":
            return self.founded(S, "year")
        if name == "FOUNDED:date":
            return self.founded(S, "date")
        if name == "FOUNDED:month":
            return self.founded(S, "month")
        if name == "STAFF":
            return self.staff(S)
        if name == "staff_noun":
            forms = self.lex.get("staff_noun") or {"other": ""}
            n = self._staff_n or self.staff_value(S) or 2
            return AText(F.plural_form(forms, self.lang, n))
        if name in ("REVENUE", "REVENUE_YEAR", "REVENUE_PREV",
                    "REVENUE_YEAR_PREV"):
            years = sorted(S.revenue)
            y = years[-1] if not name.endswith("PREV") else years[-2]
            if name.startswith("REVENUE_YEAR"):
                return self.rev_year(S, y)
            return self.revenue(S, y)
        if name == "ACTIVITY":
            return self.activity(S)
        if name == "ACTIVITY_CODE":
            return self.act_code(S)
        if name == "SERVICE":
            return self.service(rng.choice(S.services)["name"])
        if name == "SERVICE_LIST":
            k = min(len(S.services), rng.randint(2, 5))
            items = rng.sample(S.services, k)
            return self.join_list([self.service(s["name"]) for s in items])
        if name == "HOURS":
            return self.hours(S, "compact")
        if name == "HOURS:prose":
            return self.hours(S, "prose")
        if name == "CERT":
            return self.cert(rng.choice(S.certs))
        if name == "CERT_LIST":
            k = min(len(S.certs), rng.randint(2, 3))
            if k < 1:
                raise CannotFill("CERT_LIST")
            return self.join_list([self.cert(c) for c in
                                   rng.sample(S.certs, k)])
        if name == "DOC_DATE":
            if self.doc.date is None:
                raise CannotFill("DOC_DATE")
            return self.doc_date()
        return AText(self.plain(name))

    def plain(self, name):
        """The O slots."""
        rng, fmt, lex = self.rng, self.fmt, self.lex
        org = self.S or self.biz
        if name == "city":
            return (self.current_address(org) or {}).get("city") or \
                self.biz.address["city"]
        if name == "country":
            return (lex.get("country_names") or {}).get(self.country, "")
        if name in ("year", "client_founded"):
            founded = getattr(org, "founded", None)
            while True:
                y = rng.randint(1985, 2026) if name == "year" else \
                    rng.randint(1920, 2020)
                if not founded or y != founded.year:
                    break
            return fmt.int_text(y)
        if name in ("date_start", "date_end") and "fy" in self._counts:
            # the accounting period of a financial statement: the fiscal
            # year shown (April-March in India and Japan, else calendar)
            fy = self._counts["fy"]
            if self.loc.get("fiscal") == "india" or self.lang == "ja":
                d = datetime.date(fy - 1, 4, 1) if name == "date_start" \
                    else datetime.date(fy, 3, 31)
                if self.lang == "ja":
                    d = datetime.date(fy, 4, 1) if name == "date_start" \
                        else datetime.date(fy + 1, 3, 31)
            else:
                d = datetime.date(fy, 1, 1) if name == "date_start" \
                    else datetime.date(fy, 12, 31)
            return fmt.date(d, "numeric" if fmt.date_style in
                            ("hijri",) else None)[0]
        if name in ("date", "date_start", "date_end"):
            base = self.doc.date or datetime.date(2025, rng.randint(1, 12),
                                                  rng.randint(1, 28))
            delta = {"date": rng.randint(3, 60),
                     "date_start": rng.randint(-20, 30),
                     "date_end": rng.randint(31, 90)}[name]
            d = base + datetime.timedelta(days=delta)
            if name == "date_end" and "date_start" in self._counts:
                d = self._counts["date_start"] + datetime.timedelta(
                    days=rng.randint(7, 40))
            if name == "date_start":
                self._counts["date_start"] = d
            return fmt.date(d, "numeric" if fmt.date_style in
                            ("hijri",) else None)[0]
        if name == "weekday":
            return rng.choice(lex["weekdays"]["full"])
        if name == "time":
            return "%d:%02d" % (rng.randint(8, 18), rng.choice([0, 15, 30,
                                                                45]))
        if name == "n_days":
            return fmt.int_text(rng.choice([7, 10, 14, 15, 30, 30, 45, 60]))
        if name.startswith("n_"):
            kind = name[2:]
            ranges = {"years": (5, 45), "clients": (50, 5000),
                      "shops": (2, 15), "vehicles": (3, 60),
                      "products": (50, 5000), "projects": (20, 2000),
                      "countries": (3, 40)}
            lo, hi = ranges.get(kind, (2, 50))
            n = rng.randint(lo, hi)
            if n > 100:
                n = int(round(n, -1 if n < 1000 else -2))
            forms = (lex.get("counted") or {}).get(kind) or {"other": "{n}"}
            return F.plural_form(forms, self.lang, n).replace(
                "{n}", fmt.num(n))
        if name in ("partner", "supplier", "competitor", "other_org"):
            pool = self.biz.suppliers if name == "supplier" else \
                self.biz.suppliers + [c for c in self.biz.clients
                                      if c not in self._used_clients]
            if name == "other_org":
                public = (lex.get("orgs") or {}).get("public_bodies") or []
                if public and rng.random() < 0.5:
                    return rng.choice(public).format(
                        city=self.biz.address["city"],
                        family=self.biz.manager["family"])
            if pool:
                return rng.choice(pool).legal
            return rng.choice(lex.get("brand_words") or ["Nova"])
        if name == "bank":
            banks = ((lex.get("orgs") or {}).get("banks") or {}).get(
                self.country) or ["Bank"]
            return rng.choice(banks)
        if name == "other_address":
            return N.address(rng, self.loc, lex)["one"]
        if name == "person":
            p = N.person(rng, self.loc)
            return p["full"]
        if name == "position":
            return rng.choice(lex.get("positions") or ["Assistant"])
        if name == "manager_title":
            return getattr(org, "manager_title", None) or \
                rng.choice(lex.get("manager_titles") or ["Director"])
        if name == "amount":
            base = 1000 * self.loc["usd_rate"] * rng.uniform(5, 3000)
            return fmt.money_prose(base)[0]
        if name == "percent":
            return fmt.percent(rng.choice([2, 3, 5, 8, 10, 12, 15, 20]))
        if name == "quantity":
            return fmt.int_text(rng.randint(2, 500))
        if name == "invoice_no":
            return self.doc_number("invoice")
        if name == "order_no":
            return self.doc_number("order")
        if name == "currency":
            words = (lex.get("currency_names") or {}).get(
                self.loc["currency"]) or [self.loc["currency"]]
            return words[-1] if len(words) == 2 else words[0]
        if name in ("p", "n"):
            return str(self._counts.get(name, 1))
        return ""

    def doc_number(self, kind):
        rng = self.rng
        year = (self.doc.date or datetime.date(2025, 1, 1)).year
        n = rng.randint(1, 2400)
        style = rng.random()
        prefix = {"invoice": ["INV", "F", "FA", "FAC", ""],
                  "quote": ["Q", "D", "DEV", "EST", ""],
                  "order": ["PO", "BC", "CMD", ""],
                  "receipt": ["R", "REC", ""],
                  "credit": ["CN", "AV", "AVO", ""]}.get(kind, [""])
        p = rng.choice(prefix)
        if style < 0.4:
            return "%s%s%d-%04d" % (p, "-" if p else "", year, n)
        if style < 0.7:
            return "%s%05d" % (p, n)
        return "%d%04d" % (year % 100, n)

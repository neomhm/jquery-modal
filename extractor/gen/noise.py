"""
noise.py - the mess of real files (section 10.7), applied to annotated
text so that every span stays on its characters.

    hard_wrap        PDF prose cut at 60-110 characters, mid-sentence,
                     with a hyphen at 5 % of the cuts (fr es it en ru)
    extra_spaces     doubled spaces and tabs between words
    ocr_noise        1-2 % character swaps (0/O, 1/l, rn/m, é/e ...)
    drop_accents     é -> e (fr es it)
    convert_digits   Arabic-Indic, Devanagari or full-width digits
    side_by_side     two blocks merged line by line, like pdfplumber
                     reads a two-column page
"""
import re
import unicodedata

from gen.text import AText

# spans whose text must stay exactly parseable: never cut or spaced
STRICT = {"S_PHONE", "S_EMAIL", "S_URL", "S_REG_ID", "C_REG_ID", "CAPITAL",
          "REVENUE", "REVENUE_YEAR", "DOC_DATE", "DOC_TOTAL", "LINE_TOTAL",
          "PRICE", "FOUNDED", "STAFF", "ACTIVITY_CODE", "LEGAL_FORM"}


def _in_strict(at, pos):
    for sp in at.spans:
        if sp["s"] <= pos < sp["e"] and sp["label"] in STRICT:
            return True
        if sp["s"] < pos < sp["e"] and sp["label"] in STRICT:
            return True
    return False


def hard_wrap(at, rng, lang, width=None):
    """Cut long lines at spaces. A cut inside a text span keeps the span
    whole (the newline is inside it); strict spans are never cut."""
    width = width or rng.randint(60, 110)
    hyphen_langs = ("fr", "es", "it", "en", "ru")
    pos = 0
    line_start = 0
    text = at.text
    while pos < len(at.text):
        text = at.text
        nl = text.find("\n", line_start)
        line_end = len(text) if nl < 0 else nl
        if line_end - line_start <= width:
            if nl < 0:
                break
            line_start = nl + 1
            pos = line_start
            continue
        # find a cut point: last space before width
        cut = text.rfind(" ", line_start, line_start + width)
        while cut > line_start and _in_strict(at, cut):
            cut = text.rfind(" ", line_start, cut)
        if cut <= line_start:
            nxt = text.find(" ", line_start + width, line_end)
            while nxt > 0 and _in_strict(at, nxt):
                nxt = text.find(" ", nxt + 1, line_end)
            if nxt < 0:
                line_start = line_end + 1
                pos = line_start
                continue
            cut = nxt
        # sometimes hyphenate the next long word instead (5 %)
        if lang in hyphen_langs and rng.random() < 0.05:
            m = re.match(r"[^\W\d_]{7,}", text[cut + 1:])
            if m and not _in_strict(at, cut + 1):
                word = m.group(0)
                k = rng.randint(3, len(word) - 3)
                at.insert(cut + 1 + k, "-\n")
                line_start = cut + 1 + k + 2
                pos = line_start
                continue
        at.replace(cut, cut + 1, "\n")
        line_start = cut + 1
        pos = line_start
    return at


def extra_spaces(at, rng, rate=0.08):
    positions = [m.start() for m in re.finditer(r"(?<=\S) (?=\S)", at.text)]
    for pos in reversed(positions):
        if rng.random() < rate and not _in_strict(at, pos):
            at.replace(pos, pos + 1, rng.choice(["  ", "   ", "\t", " \t"]))
    return at


OCR_SWAPS = [("0", "O"), ("O", "0"), ("1", "l"), ("l", "1"), ("rn", "m"),
             ("m", "rn"), ("é", "e"), ("è", "e"), ("5", "S"), ("8", "B"),
             ("cl", "d"), ("I", "l")]


def ocr_noise(at, rng, rate=None):
    rate = rate or rng.uniform(0.01, 0.02)
    text = at.text
    n = max(1, int(len(text) * rate))
    for _ in range(n):
        old, new = rng.choice(OCR_SWAPS)
        hits = [m.start() for m in re.finditer(re.escape(old), at.text)]
        if not hits:
            continue
        pos = rng.choice(hits)
        # a swap must not straddle a span edge
        sp = at.span_at(pos)
        end = pos + len(old)
        if sp and end > sp["e"]:
            continue
        other = at.span_at(end - 1)
        if other is not sp:
            continue
        at.replace(pos, end, new)
    return at


def drop_accents(at):
    def strip(ch):
        if ch.isascii():
            return ch
        base = unicodedata.normalize("NFD", ch)
        plain = "".join(c for c in base if unicodedata.category(c) != "Mn")
        return plain if len(plain) == 1 else ch
    return at.map_chars(strip)


ARAB = "٠١٢٣٤٥٦٧٨٩"
DEVA = "०१२३४५६७८९"
FULL = "０１２３４５６７８９"


def convert_digits(at, mode):
    """Rewrites digits in another script, character by character. Digits
    inside e-mails, URLs and Latin letter-digit codes (IBAN, GSTIN) stay
    ASCII, like in real documents."""
    if not mode:
        return at
    table = {"arab": ARAB, "deva": DEVA, "full": FULL}[mode]
    text = at.text
    keep = [False] * len(text)
    for sp in at.spans:
        if sp["label"] in ("S_EMAIL", "S_URL"):
            for i in range(sp["s"], sp["e"]):
                keep[i] = True
    # e-mails, URLs, and codes mixing letters and digits (INV-2025-001,
    # GSTIN, IBAN): one token of letters, digits, '-' and '/'. 'Rs.1,000'
    # or 'Amount:1' are not codes - their digits are converted.
    for m in re.finditer(r"\S+@\S+|https?://\S+|www\.\S+|"
                         r"\b[A-Z]{2}\d{2}(?: ?[0-9A-Z]{4}){2,7}"
                         r"(?: ?[0-9A-Z]{1,3})?\b|"          # IBAN
                         r"[A-Za-z0-9\-/]*[A-Za-z][A-Za-z0-9\-/]*", text):
        if re.search(r"\d", m.group(0)):
            for i in range(m.start(), m.end()):
                keep[i] = True
    chars = list(text)
    for i, ch in enumerate(chars):
        if keep[i]:
            continue
        if "0" <= ch <= "9":
            chars[i] = table[ord(ch) - 48]
        elif mode == "full" and ch in ",." and 0 < i < len(chars) - 1 and \
                text[i - 1].isdigit() and text[i + 1].isdigit():
            chars[i] = "，" if ch == "," else "．"
    at.text = "".join(chars)                    # same length: spans stay
    return at


def side_by_side(left, right, rng):
    """Two blocks read by pdfplumber as one: line i of the left block,
    4-20 spaces, line i of the right block. Spans that ran over a line
    break are cut into one span per line."""
    lines_l = left.lines()
    lines_r = right.lines()
    width = max((len(x.text) for x in lines_l), default=0)
    out = AText()
    for i in range(max(len(lines_l), len(lines_r))):
        if i:
            out.add("\n")
        a = lines_l[i] if i < len(lines_l) else AText()
        b = lines_r[i] if i < len(lines_r) else AText()
        out.add(a)
        if b.text:
            gap = width - len(a.text) + rng.randint(4, 20)
            out.add(" " * max(4, gap))
            out.add(b)
    return out

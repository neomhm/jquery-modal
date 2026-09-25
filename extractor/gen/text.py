"""
text.py - "annotated text": a string that remembers its labelled spans.

Every labelled value in the synthetic data is CREATED, never searched for
(section 10.1): when a layout writes a company name, it writes it through
AText.add(value, "S_NAME", truth), so the span's exact position and its
normalized truth are known. Every later change to the text (line wraps,
extra spaces, OCR noise, digit scripts ...) goes through the methods
below, which move the spans along with the characters.

A span is a small dict:
    {"s": start, "e": end, "label": "S_NAME", "truth": {...} or None,
     "norm": True}      # norm: may the normalizer be tested on it?
A trap is a character range that shows a trap of section 10.6:
    {"s": start, "e": end, "trap": "T6"}
"""
import copy


class AText:

    def __init__(self, text="", label=None, truth=None, norm=True,
                 trap=None, cond=None):
        self.text = ""
        self.spans = []
        self.traps = []
        if text:
            self.add(text, label, truth, norm=norm, trap=trap, cond=cond)

    # ---------------------------------------------------------------
    #  building
    # ---------------------------------------------------------------
    def add(self, piece, label=None, truth=None, norm=True, trap=None,
            cond=None):
        """Append plain text, or a labelled value when label is given.
        piece may also be another AText (its spans move along)."""
        if isinstance(piece, AText):
            self.extend(piece)
            if trap and piece.text:
                self.traps.append({"s": len(self.text) - len(piece.text),
                                   "e": len(self.text), "trap": trap})
            return self
        if not piece:
            return self
        start = len(self.text)
        self.text += piece
        if label:
            span = {"s": start, "e": start + len(piece), "label": label,
                    "truth": truth, "norm": norm}
            if cond:
                span["cond"] = cond
            self.spans.append(span)
        if trap:
            self.traps.append({"s": start, "e": start + len(piece),
                               "trap": trap})
        return self

    def extend(self, other):
        shift = len(self.text)
        self.text += other.text
        for sp in other.spans:
            sp2 = dict(sp)
            sp2["s"] += shift
            sp2["e"] += shift
            self.spans.append(sp2)
        for tr in other.traps:
            self.traps.append({"s": tr["s"] + shift, "e": tr["e"] + shift,
                               "trap": tr["trap"]})
        return self

    def mark_trap(self, trap, start=0, end=None):
        """Mark a range (default: everything so far) as showing a trap."""
        end = len(self.text) if end is None else end
        if end > start:
            self.traps.append({"s": start, "e": end, "trap": trap})
        return self

    def copy(self):
        return copy.deepcopy(self)

    def __len__(self):
        return len(self.text)

    def __repr__(self):
        return "AText(%r, %d spans)" % (self.text[:60], len(self.spans))

    @staticmethod
    def join(parts, sep):
        """Join AText or str parts with a plain separator."""
        out = AText()
        for k, part in enumerate(parts):
            if k:
                out.add(sep)
            out.add(part)
        return out

    # ---------------------------------------------------------------
    #  editing (every edit keeps spans and traps on their characters)
    # ---------------------------------------------------------------
    def span_at(self, pos):
        """The span that contains character pos (or None)."""
        for sp in self.spans:
            if sp["s"] <= pos < sp["e"]:
                return sp
        return None

    def inside_span(self, pos):
        """True if an insertion at pos would fall strictly inside a span."""
        for sp in self.spans:
            if sp["s"] < pos < sp["e"]:
                return sp
        return None

    def replace(self, start, end, new):
        """Replace text[start:end] by new. A span that contains the whole
        range keeps it (and grows or shrinks). A span that only partly
        overlaps the range is dropped (callers avoid this)."""
        delta = len(new) - (end - start)
        self.text = self.text[:start] + new + self.text[end:]
        kept = []
        for sp in self.spans:
            if sp["e"] <= start:
                kept.append(sp)
            elif sp["s"] >= end and not (sp["s"] == start == end):
                sp["s"] += delta
                sp["e"] += delta
                kept.append(sp)
            elif sp["s"] <= start and end <= sp["e"]:
                if sp["s"] == start == end:          # insertion at the start
                    sp["s"] += delta
                    sp["e"] += delta
                else:
                    sp["e"] += delta
                kept.append(sp)
            # else: partial overlap -> dropped
        self.spans = [sp for sp in kept if sp["e"] > sp["s"]]
        traps = []
        for tr in self.traps:
            if tr["e"] <= start:
                traps.append(tr)
            elif tr["s"] >= end:
                tr["s"] += delta
                tr["e"] += delta
                traps.append(tr)
            else:
                tr["e"] = max(tr["s"] + 1, tr["e"] + delta)
                traps.append(tr)
        self.traps = traps
        return self

    def insert(self, pos, new):
        return self.replace(pos, pos, new)

    def map_chars(self, fn, start=0, end=None, skip=None):
        """Apply fn to every character of text[start:end] (fn returns the
        replacement string, usually one character). skip(pos) -> True
        leaves that character alone. Works right to left so positions
        stay valid while lengths change."""
        end = len(self.text) if end is None else end
        for pos in range(end - 1, start - 1, -1):
            if skip and skip(pos):
                continue
            ch = self.text[pos]
            new = fn(ch)
            if new != ch:
                self.replace(pos, pos + 1, new)
        return self

    def lines(self):
        """Split into one AText per line. A span that runs over a line
        break is cut into one fragment per line (its truth is dropped,
        since a fragment is no longer the whole value)."""
        out = []
        pos = 0
        for line in self.text.split("\n"):
            a, b = pos, pos + len(line)
            piece = AText()
            piece.text = line
            for sp in self.spans:
                s, e = max(sp["s"], a), min(sp["e"], b)
                if e > s:
                    frag = dict(sp)
                    frag["s"], frag["e"] = s - a, e - a
                    whole = sp["s"] >= a and sp["e"] <= b
                    if not whole:
                        frag["truth"] = None
                        frag["norm"] = False
                        # trim the fragment of outer whitespace
                        t = line[frag["s"]:frag["e"]]
                        frag["s"] += len(t) - len(t.lstrip())
                        frag["e"] -= len(t) - len(t.rstrip())
                    if frag["e"] > frag["s"]:
                        piece.spans.append(frag)
            for tr in self.traps:
                s, e = max(tr["s"], a), min(tr["e"], b)
                if e > s or (tr["s"] == tr["e"] and a <= tr["s"] <= b):
                    piece.traps.append({"s": s - a, "e": max(e, s) - a,
                                        "trap": tr["trap"]})
            out.append(piece)
            pos = b + 1
        return out

    def check(self):
        """Assert the invariants of a well-formed annotated text."""
        last = -1
        for sp in sorted(self.spans, key=lambda x: x["s"]):
            assert 0 <= sp["s"] < sp["e"] <= len(self.text), sp
            assert sp["s"] >= last, ("overlapping spans", sp, self.text)
            value = self.text[sp["s"]:sp["e"]]
            assert value == value.strip(), ("span with outer space", value)
            last = sp["e"]
        return True

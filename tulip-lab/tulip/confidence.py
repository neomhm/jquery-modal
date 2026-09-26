"""
confidence.py - how sure Tulip is of each column she mapped (Tulip 1.1,
item C). No retraining: it works with every model file.

For an imported sheet, every field the winning program assigns
(`out.price = amount(col('C'))`) gets a band - sure, check or unsure -
with the sheet columns it reads and a score between 0 and 1. The score
is made of three things the candidate loop already has:

  1. the model's own probability of the line that maps the field
     (teacher-forced on the winning program), and of the lines every
     field depends on (target, header, sections, keep, unpivot);
  2. the agreement among the 8 candidate programs (the greedy one and
     the 7 sampled ones, seeded as in the loop, so they are the very
     programs the loop would try): the share that assign the field with
     the same expression;
  3. the runtime's checks: the share of the field's cells it could not
     read.

The band's two thresholds are calibrated per model on held-out tasks
(calibrate.py; build.py does it for a new model) so that "sure" is right
at least 99% of the time. A model with no calibration never says "sure".

    signals = confidence.signals(winner, candidates, res, line_p)
    rows = confidence.columns(target, prog, signals, letters_map, bands)
"""
import ast
import hashlib
import json
import math
import pathlib

import contract
import tulipscript as ts

BANDS = ("sure", "check", "unsure")
# the version of score(): thresholds calibrated for another version of
# the score are not used
SCORE_VERSION = 2
# the share of "sure" columns that must be right (work order, item C)
SURE_PRECISION = 0.99


# ---------------------------------------------------------------------
#  the thresholds of a model
# ---------------------------------------------------------------------
def side_file(model_path):
    """tulip-1.0.0.pt -> tulip-1.0.0.confidence.json (next to it)."""
    return pathlib.Path(model_path).with_suffix(".confidence.json")


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_bands(model_path, meta=None):
    """The model's calibrated thresholds {"sure", "check", ...}, or None.
    <model>.confidence.json (calibrate.py, for a model file built before
    Tulip 1.1) is used when it names this very file (its sha256); else
    the model file's own calibration (build.py writes it)."""
    try:
        path = side_file(model_path)
        if path.exists():
            bands = json.loads(path.read_text(encoding="utf-8"))
            if bands.get("model_sha256") == file_sha256(model_path) and \
                    bands.get("score_version") == SCORE_VERSION and \
                    "sure" in bands:
                return bands
    except (OSError, ValueError, TypeError):
        pass
    return bands_from_meta(meta)


def bands_from_meta(meta):
    """The calibration build.py wrote into a model file's meta, when it
    is for this version of the score."""
    bands = (meta or {}).get("confidence")
    if bands and "sure" in bands and \
            bands.get("score_version") == SCORE_VERSION:
        return bands
    return None


# ---------------------------------------------------------------------
#  1. the model's probability of each line of the winning program
# ---------------------------------------------------------------------
def statement_spans(text):
    """-> [(first char, end char, field or None)] for each statement of a
    program that parses (field is None for target, header, sections,
    keep and unpivot)."""
    tree = ast.parse(text)
    starts = [0]
    for line in text.split("\n"):
        starts.append(starts[-1] + len(line) + 1)
    spans = []
    for stmt in tree.body:
        a = starts[stmt.lineno - 1] + stmt.col_offset
        b = starts[stmt.end_lineno - 1] + stmt.end_col_offset
        field = None
        if isinstance(stmt, ast.Assign) and isinstance(
                stmt.targets[0], ast.Attribute):
            field = stmt.targets[0].attr
        spans.append((a, b, field))
    return spans


def token_logprobs(model, prompt_ids, program_ids):
    """log p(token) of each program token, the program fed after the
    prompt (teacher forcing, temperature 1). Only the program's scores
    are computed, not the preview's."""
    import torch
    if not program_ids:
        return []
    device = model.embed.weight.device
    ids = torch.tensor([list(prompt_ids) + list(program_ids)],
                       device=device)
    with torch.no_grad():
        h = model.hidden(ids)[0, len(prompt_ids) - 1:-1]
        logits = (h @ model.embed.weight.t()).float()
        logp = torch.log_softmax(logits, -1)
        picked = logp.gather(1, torch.tensor(program_ids, device=device)
                             .view(-1, 1)).view(-1)
    return picked.tolist()


def line_probabilities(tokenizer, text, logprobs=None, model=None,
                       prompt_ids=None):
    """-> {"fields": {field: (joint p, min p)}, "structure": (joint p,
    min p)} for the program text. Each token belongs to the statement of
    its first character that is not a line break."""
    enc = tokenizer.encode(text, add_special_tokens=False)
    if logprobs is None:
        logprobs = token_logprobs(model, prompt_ids, enc.ids)
    spans = statement_spans(text)
    per = {}
    for (a, b), lp in zip(enc.offsets, logprobs):
        piece = text[a:b]
        at = a + (len(piece) - len(piece.lstrip("\n")))
        if at >= b:
            at = a                     # a token of line breaks only
        owner = "structure"
        for s, e, field in spans:
            if s <= at < e or (at >= e and at < e + 1):
                owner = field or "structure"
                break
        per.setdefault(owner, []).append(lp)
    out = {"fields": {}, "structure": (1.0, 1.0)}
    for owner, lps in per.items():
        joint = math.exp(sum(lps))
        low = math.exp(min(lps))
        if owner == "structure":
            out["structure"] = (joint, low)
        else:
            out["fields"][owner] = (joint, low)
    return out


# ---------------------------------------------------------------------
#  2. agreement among the candidates
# ---------------------------------------------------------------------
def expressions(text):
    """A program text -> (target, {field: expression}); a refusal gives
    ("refuse:<reason>", {}), a text that does not parse (None, {})."""
    try:
        prog = ts.parse(text)
    except Exception:
        return None, {}
    if prog.refusal:
        return "refuse:" + prog.refusal, {}
    return prog.target, dict((f, ast.unparse(e)) for f, e in prog.outs)


def agreement(winner, candidates):
    """-> {field: share of the candidates (winner included) with the
    winner's target that assign the field with the same expression}."""
    target, mine = expressions(winner)
    others = [expressions(c) for c in candidates]
    n = max(1, len(others))
    return dict((f, sum(1 for t, ex in others
                        if t == target and ex.get(f) == e) / float(n))
                for f, e in mine.items())


# ---------------------------------------------------------------------
#  3. the runtime's checks
# ---------------------------------------------------------------------
def unreadable_shares(res):
    """-> {field: share of its filled cells that could not be read} from
    the runtime's warnings (parse_failures:<field>:<count>)."""
    filled = {}
    for record in res.rows:
        for f, v in record.items():
            if v is not None:
                filled[f] = filled.get(f, 0) + 1
    out = {}
    for w in res.warnings:
        parts = w.split(":")
        if len(parts) == 3 and parts[0] == "parse_failures":
            count = int(parts[2])
            out[parts[1]] = count / float(count + filled.get(parts[1], 0))
    return out


# ---------------------------------------------------------------------
#  the score and the band
# ---------------------------------------------------------------------
def signals(winner, candidates, res, lines=None):
    """-> {field: {line_p, line_min_p, structure_p, agreement,
    unreadable, filled}} for each field the winner assigns.
    lines: line_probabilities() of the winner (None: no model)."""
    agree = agreement(winner, candidates)
    bad = unreadable_shares(res)
    n_rows = max(1, len(res.rows))
    out = {}
    for field in agree:
        joint, low = (lines or {}).get("fields", {}).get(field,
                                                         (None, None))
        s_joint, s_low = (lines or {}).get("structure", (None, None))
        out[field] = {
            "line_p": joint, "line_min_p": low, "structure_p": s_joint,
            "structure_min_p": s_low, "agreement": agree[field],
            "unreadable": bad.get(field, 0.0),
            "filled": sum(1 for r in res.rows if r.get(field) is not None)
            / float(n_rows)}
    return out


def score(sig):
    """One number between 0 and 1 from a field's signals (version 2): the
    candidates' agreement on the field, times the weakest token of its
    line, times the share of its cells that were read. Without the
    model's probabilities (a stand-in writer in the tests) the agreement
    and the runtime's checks alone.

    Version 1 also took the weakest token of the program's structure
    (target, header, keep...): on the pilot model's first 200 held-out
    tasks it was low for every column - mostly the header row's digit -
    and did not tell right columns from wrong ones, so version 2 leaves
    it out (it is still recorded in the signals)."""
    p = 1.0
    if sig.get("line_min_p") is not None:
        p = min(p, sig["line_min_p"])
    return round(p * sig["agreement"] * (1.0 - sig["unreadable"]), 6)


def band(value, bands):
    """A score -> sure / check / unsure by the model's calibrated
    thresholds. Without a calibration, never "sure"."""
    if not bands:
        return "check" if value >= 0.5 else "unsure"
    if value >= bands["sure"]:
        return "sure"
    return "check" if value >= bands["check"] else "unsure"


def letters_of(expr, prog=None):
    """The sheet columns an expression reads (col, header_of, format_of),
    in the order they appear. unpivot's col('name') and col('value') read
    the unpivoted columns; col('section') the section rows."""
    out = []
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id in ("col", "header_of", "format_of") \
                and sub.args and isinstance(sub.args[0], ast.Constant):
            name = sub.args[0].value
            if name in ("name", "value") and prog is not None and \
                    prog.unpivot:
                found = list(prog.unpivot)
            elif name == "section":
                found = ["section rows"]
            else:
                found = [name] if name in ts.LETTERS else []
            out += [x for x in found if x not in out]
    return out


def field_rights(task, result, sheet):
    """{field: right} for each field the winning program fills, against a
    generated task's truth: the field is right when the target is the
    task's answer and, on every sheet row that both the import and the
    truth imported (at least one), its columns hold the truth's values.
    Rows the import added or missed are the rows' fault, not the
    column's; they do not count here."""
    import helpers as H
    fields = []
    for col in (result.get("confidence") or {}).get("columns", []):
        if col["field"] not in fields:
            fields.append(col["field"])
    target = result["target"]
    if target != task["answer"]:
        return dict((f, False) for f in fields)
    prog = ts.parse(task["program"])
    truth = ts.run(prog, sheet, H.HELPERS, task["locale"], task["targets"],
                   H.TOTALS)
    t_rows, _, t_numbers = contract.convert(target, truth.rows, None,
                                            truth.row_numbers)
    mine, theirs = {}, {}
    for row, n in zip(result["rows"], result["row_numbers"]):
        mine.setdefault(n, []).append(row)
    for row, n in zip(t_rows, t_numbers):
        theirs.setdefault(n, []).append(row)
    shared = sorted(set(mine) & set(theirs))
    out = {}
    for f in fields:
        cols = [c["name"] for c in contract.columns(target)
                if (c.get("tulip") or {}).get("field", c["name"]) == f]
        out[f] = bool(shared) and all(
            [r.get(c) for r in mine[n]] == [r.get(c) for r in theirs[n]]
            for n in shared for c in cols)
    return out


def columns(target, prog, sig, original=lambda letter: letter,
            bands=None):
    """-> [{column, field, sheet_columns, band, score, signals}], one per
    column of tables.schema.json that the program fills, in the schema's
    order (opening hours: opens, closes and closed share the band of
    Tulip's hours field)."""
    exprs = dict(prog.outs)
    out = []
    for col in contract.columns(target):
        field = (col.get("tulip") or {}).get("field", col["name"])
        if field not in exprs or field not in sig:
            continue
        s = score(sig[field])
        out.append({"column": col["name"], "field": field,
                    "sheet_columns": [original(x) for x in
                                      letters_of(exprs[field], prog)],
                    "band": band(s, bands), "score": s,
                    "signals": dict((k, None if v is None else
                                     round(v, 6))
                                    for k, v in sig[field].items())})
    return out


# ---------------------------------------------------------------------
#  calibration: thresholds from held-out columns
# ---------------------------------------------------------------------
def wilson_low(right, n, z=1.6449):
    """The one-sided 95% lower bound of a share right/n."""
    if n == 0:
        return 0.0
    p = right / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d


def isotonic(pairs):
    """[(score, right)] -> [(lowest score, highest score, share right)]:
    the non-decreasing step function closest to the data (pool adjacent
    violators), lowest scores first. Equal scores stay in one step."""
    steps = []                         # [lo, hi, right, n]
    for s, ok in sorted(pairs):
        if steps and steps[-1][1] == s:
            steps[-1][2] += 1 if ok else 0
            steps[-1][3] += 1
        else:
            steps.append([s, s, 1 if ok else 0, 1])
        while len(steps) > 1 and steps[-2][2] * steps[-1][3] > \
                steps[-1][2] * steps[-2][3]:
            lo, _, r, n = steps.pop(-2)
            steps[-1][0] = lo
            steps[-1][2] += r
            steps[-1][3] += n
    return [(lo, hi, r / float(n)) for lo, hi, r, n in steps]


def calibrate(pairs, sure=SURE_PRECISION, check=0.8, min_n=30,
              rule="low95"):
    """pairs: [(score, right)] of held-out columns -> the bands'
    thresholds, or None when no threshold gives "sure" enough columns.
      sure   the lowest score from which the columns at or above it are
             right at least `sure` of the time - with rule "low95", the
             one-sided 95% lower bound of that share (so the rate on new
             columns is very likely at least `sure`), with rule "rate"
             the share itself; at least min_n columns.
      check  the lowest score from which a column's own chance of being
             right (the isotonic fit of right against score) is at least
             `check`; below it, "unsure"."""
    pairs = sorted(pairs, key=lambda p: -p[0])
    t_sure, right = None, 0
    for i, (s, ok) in enumerate(pairs):
        right += 1 if ok else 0
        n = i + 1
        if (i + 1 == len(pairs) or pairs[i + 1][0] != s) and n >= min_n:
            rate = wilson_low(right, n) if rule == "low95" else \
                right / float(n)
            if rate >= sure:
                t_sure = s
    if t_sure is None:
        return None
    t_check = t_sure
    for lo, _, share in reversed(isotonic(pairs)):
        if lo >= t_sure:
            continue
        if share < check:
            break
        t_check = lo
    return {"sure": t_sure, "check": t_check}


def measure(pairs, bands):
    """-> {band: {"columns": n, "right": k, "rate": k/n, "low95": ...}}"""
    out = dict((b, [0, 0]) for b in BANDS)
    for s, ok in pairs:
        cell = out[band(s, bands)]
        cell[0] += 1
        cell[1] += 1 if ok else 0
    return dict((b, {"columns": n, "right": k,
                     "rate": round(k / float(n), 4) if n else None,
                     "low95": round(wilson_low(k, n), 4) if n else None})
                for b, (n, k) in out.items())

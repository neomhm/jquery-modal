"""
tulip.py - the Tulip API (section 15.1): give it a sheet, get the rows.

    from tulip import Tulip
    tulip = Tulip("tulip-1.1.0.pt")
    results = tulip.import_file("tarifs.xlsx", ["products", "services"],
                                "fr-FR")

For each sheet:
  1. sheets.compact() removes the empty columns; sheets.preview() writes
     the text the model reads.
  2. The model writes a program (greedy). A refusal is final. A program
     that passes every check of tulipscript.run() is the import.
  3. Otherwise 7 more programs are sampled (temperature 0.7, top-p 0.95,
     the random generator seeded from the sha1 of the preview, so the
     result is always the same) and the first that passes is taken.
  4. If none passes: refused when 4 or more of the 8 candidates refused
     (with their most common reason), otherwise needs_review.
Every candidate is first tried on the first 500 data rows; one rejected
there never runs on the whole sheet. An exception while parsing or
running a candidate only rejects that candidate.

The rows are in the declared format of tables.schema.json (contract.py):
a day is "monday".."sunday", opening hours are one row per range with
opens / closes / closed, a VAT rate is a percent, dates are ISO 8601.
"rows" and "sources" use the schema's column names; "contract" is the
schema's version.

"confidence" (import_sheet / import_file, not the evaluation's loop)
gives each column the program fills a band - sure, check or unsure -
with the sheet columns it reads (confidence.py): from the model's
probability of the line that maps it, the agreement of the 8 candidate
programs (the 7 sampled ones are then always written, with the loop's
seed, so the import itself does not change) and the runtime's checks.
The thresholds are the model's calibration (calibrate.py): in the model
file, or in <model>.confidence.json next to it; without one, no column
is ever "sure".

Every data row read and not imported is in "skipped" as (row, reason):
unreadable:<fields>, empty_required, totals_row or removed_by_keep.
targets must be 1 to 4 known names (ValueError otherwise). import_file()
never raises for a bad file: it answers needs_review with reason
unreadable_file:<exception type>.

The model's output is only ever PARSED by tulipscript.parse() and run by
tulipscript.run() - never exec, eval or compile.
"""
import collections
import hashlib
import sys
import threading
import time

import torch
from tokenizers import Tokenizer

import blocks
import confidence as C
import config
import contract
import helpers as H
import model as M
import sheets
import tok as TK
import tulipscript as ts

# The PLAN offers at most 4 targets per call, and the model was trained
# on previews offering 1 to 4 (section 10.3).
MAX_TARGETS = 4


def check_targets(targets):
    """-> the targets as a list, or ValueError with a clear message when
    they are missing, empty, not a list of names, unknown, repeated or
    more than MAX_TARGETS."""
    if targets is None:
        raise ValueError("targets are required: give 1 to %d of %s"
                         % (MAX_TARGETS, ", ".join(config.TARGETS)))
    if isinstance(targets, str) or not isinstance(targets, (list, tuple)):
        raise ValueError("targets must be a list of target names, e.g. "
                         "['products', 'services'], not %r" % (targets,))
    targets = list(targets)
    if not targets:
        raise ValueError("targets is empty: give 1 to %d of %s"
                         % (MAX_TARGETS, ", ".join(config.TARGETS)))
    bad = [t for t in targets if t not in config.TARGETS]
    if bad:
        raise ValueError("unknown target(s): %s (choose from %s)" % (
            ", ".join(repr(t) for t in bad), ", ".join(config.TARGETS)))
    if len(set(targets)) != len(targets):
        raise ValueError("a target is repeated: %s" % ", ".join(targets))
    if len(targets) > MAX_TARGETS:
        raise ValueError("%d targets given; at most %d per call (the model "
                         "was trained on 1 to %d)" % (len(targets),
                                                      MAX_TARGETS,
                                                      MAX_TARGETS))
    return targets


def empty_result(file, sheet, status, reason, problems=()):
    """A result with every key of section 15.1 (plus hidden, seconds),
    for a sheet or a file that never reached the model."""
    return {"file": file, "sheet": sheet, "status": status,
            "target": None, "reason": reason, "program": None,
            "candidates_tried": 0, "rows": [], "sources": [],
            "row_numbers": [], "skipped": [], "problems": list(problems),
            "warnings": [], "hidden": False, "seconds": 0.0,
            "contract": contract.version(), "confidence": None}


def unreadable_file(path, exc):
    """The one result for a file sheets.load() could not read (a corrupt
    .xlsx, a binary .csv, a file that cannot be opened): needs_review,
    because the owner has to open or re-save it; the model never saw
    it. The sheet name is "" - nothing inside the file was read."""
    name = type(exc).__name__
    if name == "ScannedPDF":            # pdftable.py: no text, no OCR
        return empty_result(str(path), "", "needs_review", "scanned_pdf",
                            ["scanned_pdf: the PDF has no text (scanned "
                             "pages need OCR, which Tulip does not do)"])
    if name == "Error":                 # csv.Error: say whose Error
        name = type(exc).__module__.strip("_").split(".")[0] + ".Error"
    return empty_result(str(path), "", "needs_review",
                        "unreadable_file:" + name,
                        ["unreadable_file:%s:%s" % (name, str(exc)[:200])])


def shifted(out, rows, columns):
    """A result of a table that lies `rows` rows down and `columns`
    columns right in its sheet -> the sheet's own row numbers and
    letters (blocks.py)."""
    if not rows and not columns:
        return out

    def letter(x):
        if x in ts.LETTERS and ts.LETTERS.index(x) + columns < \
                len(ts.LETTERS):
            return ts.LETTERS[ts.LETTERS.index(x) + columns]
        return x
    out["row_numbers"] = [n + rows for n in out["row_numbers"]]
    out["sources"] = [dict((f, [(r + rows, letter(c)) for r, c in srcs])
                           for f, srcs in record.items())
                      for record in out["sources"]]
    out["skipped"] = [(n + rows, why) for n, why in out["skipped"]]
    for col in (out.get("confidence") or {}).get("columns", []):
        col["sheet_columns"] = [letter(x) for x in col["sheet_columns"]]
    return out


def skipped_rows(res, sheet, totals):
    """Every data row the program read and did not import, as
    [(row, reason)] sorted by row (section 7.1: "every skipped row is
    listed with its row number and reason"). Row numbers are the sheet's
    own (compact() removes columns, never rows).
      unreadable:<fields>  a required cell is filled but unreadable
      empty_required       the required cells are empty (a notes line)
      totals_row           removed by keep() and it is a totals row
      removed_by_keep      removed by keep() (and not importable)
    Blank rows, repeated header rows and section-title rows are not data
    rows and are not listed."""
    out = list(res.skipped)
    out += [(n, "empty_required") for n in res.empty]
    for n in res.dropped:
        cells = sheet.rows[n - 1] if 0 < n <= len(sheet.rows) else []
        out.append((n, "totals_row" if ts.is_totals_row(cells, totals)
                    else "removed_by_keep"))
    seen, unique = set(), []
    for item in sorted(out, key=lambda x: (x[0], str(x[1]))):
        if item not in seen:            # unpivot repeats a row per column
            seen.add(item)
            unique.append(item)
    return unique


class Tulip:
    def __init__(self, path, device="cpu", threads=None):
        """Loads the model file on the CPU by default. `threads` calls
        torch.set_num_threads(threads), which is PROCESS-WIDE: it changes
        every model in this process."""
        if threads:
            torch.set_num_threads(int(threads))
        self.device = torch.device(device)
        self.model, tokenizer_json, self.meta = M.load(path, self.device)
        self.tokenizer = Tokenizer.from_str(tokenizer_json)
        self.sampling = dict(config.SAMPLING)
        self.sampling.update(self.meta.get("sampling") or {})
        # the totals words of all ten languages, stored in the model file
        self.totals = tuple(self.meta.get("totals") or H.TOTALS)
        self.model_id = self.meta.get("model_id") or str(path)
        self.max_len = self.model.config.max_len
        self._lock = threading.Lock()
        self.bands = C.load_bands(path, self.meta)

    @classmethod
    def from_model(cls, net, tokenizer, meta=None):
        """A Tulip around a model already in memory (training and
        evaluation use this; no file needed)."""
        self = cls.__new__(cls)
        self.device = next(net.parameters()).device
        self.model, self.tokenizer, self.meta = net, tokenizer, meta or {}
        self.sampling = dict(config.SAMPLING)
        self.totals = tuple(H.TOTALS)
        self.model_id = self.meta.get("model_id") or "in-memory"
        self.max_len = net.config.max_len
        self._lock = threading.Lock()
        self.bands = C.bands_from_meta(self.meta)
        return self

    # ----------------------------------------------------------- writing
    def prompt(self, preview):
        return TK.encode(self.tokenizer, preview) + [TK.PROGRAM]

    def fits(self, preview):
        """Room for the preview and a program (section 8: 4,096)."""
        return len(self.prompt(preview)) + 64 <= self.max_len

    def write(self, preview, n_sampled=7):
        """-> [greedy program, sampled programs...] (texts)."""
        with self._lock:
            return self._write(preview, n_sampled)

    def _write(self, preview, n_sampled=7, greedy_only=False,
               sampled_only=False):
        """-> [greedy, sampled...]; sampled_only: [None, sampled...] (the
        greedy program is not written again; the sampled ones do not
        depend on it)."""
        prompt = self.prompt(preview)
        room = self.max_len - len(prompt) - 1
        max_new = max(1, min(self.sampling["max_new_tokens"], room))
        if sampled_only:
            programs = [None]
        else:
            out = self.model.generate(prompt, TK.END, max_new=max_new, n=1,
                                      temperature=0.0)
            programs = [TK.decode(self.tokenizer, out[0])]
        if greedy_only or n_sampled <= 0:
            return programs
        seed = int(hashlib.sha1(preview.encode("utf-8")).hexdigest()[:15],
                   16)
        gen = torch.Generator(device=self.device)
        gen.manual_seed(seed)
        outs = self.model.generate(prompt, TK.END, max_new=max_new,
                                   n=n_sampled,
                                   temperature=self.sampling["temperature"],
                                   top_p=self.sampling["top_p"],
                                   generator=gen)
        programs += [TK.decode(self.tokenizer, o) for o in outs]
        return programs

    # ----------------------------------------------------------- checking
    def check(self, text, sheet, targets, locale):
        """One candidate -> (Result or None, program or None, reason)."""
        try:
            prog = ts.parse(text)
        except ts.TulipError as e:
            return None, None, "parse:" + e.code
        except Exception as e:                       # never crash
            return None, None, "exception:" + type(e).__name__
        if prog.refusal:
            return None, prog, "refuse:" + prog.refusal
        try:
            trial_rows = self.sampling["trial_rows"]
            head = (prog.header or 0) + trial_rows
            if len(sheet.rows) > head:
                trial = sheets.Sheet(sheet.name, sheet.rows[:head],
                                     sheet.formats[:head]
                                     if sheet.formats else None)
                res = ts.run(prog, trial, H.HELPERS, locale, targets,
                             self.totals)
                if res.problems:
                    return res, prog, "trial:" + res.problems[0]
            res = ts.run(prog, sheet, H.HELPERS, locale, targets,
                         self.totals)
        except Exception as e:
            return None, prog, "exception:" + type(e).__name__
        if res.problems or res.status not in ("imported",
                                              "imported_with_warnings"):
            return res, prog, (res.problems or ["rejected"])[0]
        return res, prog, None

    # ----------------------------------------------------------- the loop
    def import_sheet(self, sheet, targets, locale, confidence=True):
        """ValueError when targets are missing, empty, unknown or more
        than 4 (check_targets)."""
        targets = check_targets(targets)
        with self._lock:
            return self._import_sheet(sheet, targets, locale,
                                      confidence=confidence)

    def _import_sheet(self, sheet, targets, locale, n_sampled=None,
                      greedy=None, confidence=False):
        """greedy: the greedy program when it was already written (the
        evaluation writes it once for pass@1 and for the loop).
        confidence: also give each mapped column its band (the 7 sampled
        programs are then written even when the greedy one passed).
        A table cut from a sheet by blocks.split() is read from its own
        R1; its rows and cells are given back in the sheet's own
        numbers and letters."""
        out = self._import_one(sheet, targets, locale, n_sampled, greedy,
                               confidence)
        return shifted(out, getattr(sheet, "row_offset", 0),
                       getattr(sheet, "column_offset", 0))

    def _import_one(self, sheet, targets, locale, n_sampled=None,
                    greedy=None, confidence=False):
        started = time.time()
        small, letters = sheets.compact(sheet)
        out = {"file": getattr(sheet, "file", "") or "",
               "sheet": sheet.name, "status": "needs_review",
               "target": None, "reason": None, "program": None,
               "candidates_tried": 0, "rows": [], "sources": [],
               "row_numbers": [], "skipped": [], "problems": [],
               "warnings": [], "hidden": bool(getattr(sheet, "hidden",
                                                      False)),
               "contract": contract.version(), "confidence": None}
        if not small.rows:
            out.update(status="refused", reason="not_a_table",
                       problems=["empty_sheet"])
            out["seconds"] = round(time.time() - started, 3)
            return out
        preview = sheets.preview(small, targets, locale)
        if not self.fits(preview):
            out.update(reason="too_long", problems=["too_long"])
            out["seconds"] = round(time.time() - started, 3)
            return out
        n_sampled = self.sampling["n_sampled"] if n_sampled is None \
            else n_sampled
        # 1. the greedy candidate
        if greedy is None:
            greedy = self._write(preview, 0, greedy_only=True)[0]
        res, prog, why = self.check(greedy, small, targets, locale)
        out["candidates_tried"] = 1
        if prog is not None and prog.refusal:            # final
            out.update(status="refused", reason=prog.refusal,
                       program=ts.canonical(greedy))
            out["seconds"] = round(time.time() - started, 3)
            return out
        seen = {"preview": preview, "n_sampled": n_sampled,
                "candidates": [greedy], "confidence": confidence}
        if why is None:
            return self._done(out, res, prog, greedy, small, letters,
                              started, seen)
        reasons = [why]
        refusals = []
        # 2. seven sampled candidates, one shared cache of the preview
        programs = self._write(preview, n_sampled, sampled_only=True)[1:]
        seen["candidates"] += programs
        for text in programs:
            out["candidates_tried"] += 1
            res, prog, why = self.check(text, small, targets, locale)
            if prog is not None and prog.refusal:
                refusals.append(prog.refusal)
                continue
            if why is None:
                return self._done(out, res, prog, text, small, letters,
                                  started, seen)
            reasons.append(why)
        # 3. nothing passed
        if len(refusals) >= 4:
            reason = collections.Counter(refusals).most_common(1)[0][0]
            out.update(status="refused", reason=reason)
        else:
            out.update(status="needs_review",
                       reason="no_candidate_passed")
        out["problems"] = sorted(set(reasons))[:10]
        out["program"] = greedy
        out["seconds"] = round(time.time() - started, 3)
        return out

    def _done(self, out, res, prog, text, small, letters, started,
              seen=None):
        """Report with the ORIGINAL column letters (section 8), the rows
        in the declared format of tables.schema.json (contract.py: day
        names, opens / closes, VAT in percent...). A value that is not in
        its declared format is a bug somewhere: the sheet goes to review
        and nothing is written. seen: what the loop wrote (the preview,
        the candidates), for the confidence bands."""
        def original(src):
            row, col = src
            if col in ts.LETTERS and ts.LETTERS.index(col) < len(letters):
                col = letters[ts.LETTERS.index(col)]
            return (row, col)
        sources = [dict((f, [original(s) for s in srcs])
                        for f, srcs in record.items())
                   for record in res.sources]
        rows, sources, numbers = contract.convert(prog.target, res.rows,
                                                  sources, res.row_numbers)
        wrong = contract.check_rows(prog.target, rows)
        if wrong:
            out.update(status="needs_review", reason="contract_format",
                       target=prog.target, program=ts.canonical(text),
                       problems=["contract:" + w for w in wrong[:10]])
            out["seconds"] = round(time.time() - started, 3)
            return out
        out.update(status=res.status, target=prog.target,
                   program=ts.canonical(text), rows=rows, sources=sources,
                   row_numbers=numbers,
                   skipped=skipped_rows(res, small, self.totals),
                   warnings=res.warnings, problems=res.problems)
        if seen and seen.get("confidence"):
            out["confidence"] = self._confidence(res, prog, text, seen,
                                                 original)
        out["seconds"] = round(time.time() - started, 3)
        return out

    def _confidence(self, res, prog, text, seen, original):
        """{"calibrated", "columns": [{column, field, sheet_columns,
        band, score, signals}]} for the winning program (confidence.py).
        The candidates are the greedy program and the 7 sampled ones:
        when the greedy program won, the sampled ones are written now,
        with the loop's seed - the very programs the loop would have
        tried."""
        candidates = list(seen["candidates"])
        if len(candidates) == 1 and seen["n_sampled"] > 0:
            candidates += self._write(seen["preview"], seen["n_sampled"],
                                      sampled_only=True)[1:]
        lines = self._line_probabilities(seen["preview"], text)
        signals = C.signals(text, candidates, res, lines)
        bands = getattr(self, "bands", None)
        return {"calibrated": bool(bands),
                "candidates": len(candidates),
                "columns": C.columns(prog.target, prog, signals,
                                     lambda x: original((0, x))[1], bands)}

    def _line_probabilities(self, preview, text):
        """The model's probability of each line of the program (None
        without a model)."""
        model = getattr(self, "model", None)
        if model is None:
            return None
        return C.line_probabilities(self.tokenizer, text, model=model,
                                    prompt_ids=self.prompt(preview))

    def import_file(self, path, targets, locale, confidence=True):
        """-> one result per sheet of the file (a CSV has one).

        ValueError when targets are missing, empty, unknown or more than
        4. Otherwise it never raises: a file that cannot be read (a
        corrupt .xlsx, a binary .csv) gives ONE result, needs_review with
        reason unreadable_file:<exception type>, and an exception on one
        sheet gives that sheet needs_review with reason
        exception:<type> - one bad file never stops a folder import."""
        targets = check_targets(targets)
        try:
            loaded = sheets.load(path, locale)
        except Exception as e:
            return [unreadable_file(path, e)]
        results = []
        for sheet in (part for whole in loaded
                      for part in blocks.split(whole)):
            if not sheet.file:
                sheet.file = str(path)
            results.append(self.import_sheet_safely(sheet, targets, locale,
                                                    confidence))
        return results

    def import_sheet_safely(self, sheet, targets, locale, confidence=True):
        """import_sheet() for targets already checked, with any exception
        turned into needs_review (reason exception:<type>) for that sheet
        alone."""
        try:
            with self._lock:
                return self._import_sheet(sheet, targets, locale,
                                          confidence=confidence)
        except Exception as e:
            out = empty_result(str(getattr(sheet, "file", "") or ""),
                               getattr(sheet, "name", ""), "needs_review",
                               "exception:" + type(e).__name__,
                               ["exception:%s:%s" % (type(e).__name__,
                                                     str(e)[:200])])
            out["hidden"] = bool(getattr(sheet, "hidden", False))
            return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Import one file with Tulip")
    ap.add_argument("file")
    ap.add_argument("--model", required=True)
    ap.add_argument("--targets", required=True,
                    help="1 to %d of: %s (comma-separated)" % (
                        MAX_TARGETS, ", ".join(config.TARGETS)))
    ap.add_argument("--locale", required=True)
    args = ap.parse_args()
    try:
        targets = check_targets([x.strip() for x in args.targets.split(",")
                                 if x.strip()])
    except ValueError as e:
        ap.error(str(e))
    t = Tulip(args.model)
    for r in t.import_file(args.file, targets, args.locale):
        print(json.dumps(r, ensure_ascii=False, default=str, indent=1))

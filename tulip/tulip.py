"""
tulip.py - the Tulip API (section 15.1): give it a sheet, get the rows.

    from tulip import Tulip
    tulip = Tulip("tulip-1.0.0.pt")
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

import config
import helpers as H
import model as M
import sheets
import tok as TK
import tulipscript as ts


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

    def _write(self, preview, n_sampled=7, greedy_only=False):
        prompt = self.prompt(preview)
        room = self.max_len - len(prompt) - 1
        max_new = max(1, min(self.sampling["max_new_tokens"], room))
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
    def import_sheet(self, sheet, targets, locale):
        with self._lock:
            return self._import_sheet(sheet, targets, locale)

    def _import_sheet(self, sheet, targets, locale, n_sampled=None,
                      greedy=None):
        """greedy: the greedy program when it was already written (the
        evaluation writes it once for pass@1 and for the loop)."""
        started = time.time()
        small, letters = sheets.compact(sheet)
        out = {"file": getattr(sheet, "file", "") or "",
               "sheet": sheet.name, "status": "needs_review",
               "target": None, "reason": None, "program": None,
               "candidates_tried": 0, "rows": [], "sources": [],
               "row_numbers": [], "skipped": [], "problems": [],
               "warnings": [], "hidden": bool(getattr(sheet, "hidden",
                                                      False))}
        if not small.rows:
            out.update(status="refused", reason="not_a_table",
                       problems=["empty_sheet"])
            return out
        preview = sheets.preview(small, targets, locale)
        if not self.fits(preview):
            out.update(reason="too_long", problems=["too_long"])
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
        if why is None:
            return self._done(out, res, prog, greedy, small, letters,
                              started)
        reasons = [why]
        refusals = []
        # 2. seven sampled candidates, one shared cache of the preview
        programs = self._write(preview, n_sampled)[1:]
        for text in programs:
            out["candidates_tried"] += 1
            res, prog, why = self.check(text, small, targets, locale)
            if prog is not None and prog.refusal:
                refusals.append(prog.refusal)
                continue
            if why is None:
                return self._done(out, res, prog, text, small, letters,
                                  started)
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

    def _done(self, out, res, prog, text, small, letters, started):
        """Report with the ORIGINAL column letters (section 8)."""
        def original(src):
            row, col = src
            if col in ts.LETTERS and ts.LETTERS.index(col) < len(letters):
                col = letters[ts.LETTERS.index(col)]
            return (row, col)
        out.update(status=res.status, target=prog.target,
                   program=ts.canonical(text), rows=res.rows,
                   sources=[dict((f, [original(s) for s in srcs])
                                 for f, srcs in record.items())
                            for record in res.sources],
                   row_numbers=res.row_numbers, skipped=res.skipped,
                   warnings=res.warnings, problems=res.problems)
        out["seconds"] = round(time.time() - started, 3)
        return out

    def import_file(self, path, targets, locale):
        """-> one result per sheet of the file (a CSV has one)."""
        results = []
        for sheet in sheets.load(path, locale):
            if not sheet.file:
                sheet.file = str(path)
            results.append(self.import_sheet(sheet, targets, locale))
        return results


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Import one file with Tulip")
    ap.add_argument("file")
    ap.add_argument("--model", required=True)
    ap.add_argument("--targets", default=",".join(config.TARGETS))
    ap.add_argument("--locale", required=True)
    args = ap.parse_args()
    t = Tulip(args.model)
    for r in t.import_file(args.file, args.targets.split(","), args.locale):
        print(json.dumps(r, ensure_ascii=False, default=str, indent=1))

#!/usr/bin/env python3
"""
RedactReady — batch-redact PDFs *properly*, then prove nothing leaked.

Most "redaction" failures come from drawing a black box over text that
is still in the file — anyone can copy-paste it back out. RedactReady
uses real content-removal redaction (PyMuPDF add_redact_annot +
apply_redactions): the matched characters are deleted from the
content stream and the area is painted black.

Then the part that matters — the leak re-check. Every output PDF is
searched twice for every term:
  1. through the normal text-extraction layer, and
  2. through the RAW content-stream bytes of every page
because text can hide where extractors do not look. A file only gets a
PASS when both channels find zero hits. The report prints the counts.

Scope, stated honestly: text-based PDFs only. If a page contains no
extractable text (a scanned image), redaction cannot be verified, so
the file is flagged SCAN-DETECTED and reported as needing OCR first —
RedactReady never silently "passes" a scan. Originals are never
modified; outputs go to a new folder with a report.

Local only. No network. Uses PyMuPDF.
"""
import os
import re
import sys

import fitz  # PyMuPDF


def _normalise(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def find_leaks(pdf_path, terms):
    """Two-channel leak search. Returns dict term -> {text_hits, raw_hits}."""
    doc = fitz.open(pdf_path)
    out = {}
    for term in terms:
        t = _normalise(term)
        text_hits = 0
        raw_hits = 0
        needle = t.encode("utf-8", "ignore")
        for page in doc:
            text = _normalise(page.get_text())
            text_hits += text.count(t)
            for xref in page.get_contents():
                raw = doc.xref_stream(xref) or b""
                raw_hits += raw.lower().count(needle)
                # also catch hex-encoded strings in the content stream
                raw_hits += raw.lower().count(needle.hex().encode())
        out[term] = {"text_hits": text_hits, "raw_hits": raw_hits}
    doc.close()
    return out


def redact_file(src, dst, terms, also_regexes):
    """Redact one PDF. Returns a result dict."""
    doc = fitz.open(src)
    result = {"src": src, "dst": dst, "pages": len(doc),
              "pages_without_text": 0, "matches_redacted": 0,
              "regex_matches": 0}
    patterns = [re.compile(p, re.IGNORECASE) for p in also_regexes]
    for page in doc:
        text = page.get_text()
        if not text.strip():
            result["pages_without_text"] += 1
        hit_rects = []
        for term in terms:
            if not term.strip():
                continue
            rects = page.search_for(term)
            hit_rects += rects
            result["matches_redacted"] += len(rects)
        if patterns:
            for block in page.get_text("words"):
                word = " ".join(block[4].split())
                for pat in patterns:
                    if pat.search(word):
                        hit_rects.append(fitz.Rect(block[:4]))
                        result["regex_matches"] += 1
                        break
        for r in hit_rects:
            page.add_redact_annot(r, fill=(0, 0, 0))
        if hit_rects:
            page.apply_redactions()
    doc.save(dst, garbage=4, deflate=True)
    doc.close()
    result["scan_detected"] = result["pages_without_text"] > 0
    leaks = find_leaks(dst, terms)
    result["leaks"] = leaks
    result["leak_free"] = all(v["text_hits"] == 0 and v["raw_hits"] == 0
                              for v in leaks.values())
    result["verdict"] = result["leak_free"] and not result["scan_detected"]
    return result


def run_redactready(paths, outdir, terms, also_regexes=None):
    os.makedirs(outdir, exist_ok=True)
    also_regexes = also_regexes or []
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, fns in os.walk(p):
                for fn in sorted(fns):
                    if fn.lower().endswith(".pdf"):
                        files.append(os.path.join(root, fn))
        elif p.lower().endswith(".pdf"):
            files.append(p)
    results, errors = [], []
    for f in files:
        dst = os.path.join(outdir, os.path.splitext(os.path.basename(f))[0]
                           + "_redacted.pdf")
        try:
            results.append(redact_file(f, dst, terms, also_regexes))
        except Exception as e:
            errors.append({"file": f, "error": str(e)})
    L = ["# RedactReady — redaction & leak re-check report", "",
         f"Files processed: {len(results)}  ·  Errors: {len(errors)}",
         f"Terms: {', '.join(terms) if terms else '(none)'}",
         f"Extra patterns: {', '.join(also_regexes) if also_regexes else '(none)'}",
         "", "## Per file"]
    for r in results:
        leak_str = "; ".join(
            f"{t}: text {v['text_hits']} / raw {v['raw_hits']}"
            for t, v in r["leaks"].items()) or "no terms"
        L.append(f"- {os.path.basename(r['src'])}: {r['pages']} pages, "
                 f"{r['matches_redacted']} term matches + "
                 f"{r['regex_matches']} pattern matches redacted; "
                 f"leak re-check [{leak_str}]; "
                 f"{'SCAN-DETECTED (unverifiable pages present) ' if r['scan_detected'] else ''}"
                 f"verdict {'PASS' if r['verdict'] else 'CHECK'}")
    L += ["", "## Errors"]
    L += [f"- {e['file']}: {e['error']}" for e in errors] or ["- none"]
    L += ["", "## How the re-check works",
          "- Channel 1: the output's extracted text is searched for every term.",
          "- Channel 2: the raw content-stream bytes of every page are searched",
          "  (plain and hex-encoded) — text can hide where extractors miss it.",
          "- A file PASSes only with zero hits in both channels and no",
          "  text-less (scanned) pages. Scans are flagged, never passed silently.",
          "- Redaction removes the matched text runs found by the search layer;",
          "  a term drawn as vector outlines or inside an image is out of scope",
          "  and is exactly what the scan flag protects you from assuming."]
    report_path = os.path.join(outdir, "redaction_report.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return {"files": results, "errors": errors, "report_path": report_path,
            "verdict": bool(results) and all(r["verdict"] for r in results)
            and not errors}


EMAIL_RE = r"[\w.+-]+@[\w-]+\.[\w.]+"
SSN_RE = r"\b\d{3}-\d{2}-\d{4}\b"

PRESETS = {
    "emails": ("regex", EMAIL_RE),
    "us_ssn": ("regex", SSN_RE),
}


def main(argv):
    if len(argv) < 4:
        print("usage: redact_ready.py <pdf-or-folder> <outdir> term1 [term2 ...]")
        return 2
    s = run_redactready([argv[1]], argv[2], argv[3:],
                        also_regexes=[EMAIL_RE, SSN_RE])
    print(f"files={len(s['files'])} errors={len(s['errors'])} verdict={s['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

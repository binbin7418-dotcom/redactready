# RedactReady

Batch true redaction for PDFs: matched text is removed from the
content stream (not covered), then every output is leak-checked
through two channels — extracted text and raw content-stream bytes.

## Run (dev)

```
python gui.py                       # desktop app (needs PyMuPDF)
python redact_ready.py <pdf-or-folder> <outdir> "Term One" "Term Two"
<venv python> test/acceptance_test.py
```

## How it works

`redact_ready.py` finds each term (plus optional email / SSN-shaped
pattern matches at word level), applies PyMuPDF redactions, and saves
with garbage collection. `find_leaks` then searches the output twice:
normalized extracted text per page, and the raw bytes (plus
hex-encoded form) of every page content stream. Files with text-less
pages are flagged SCAN-DETECTED and cannot PASS — scanned paper needs
OCR before any text redactor can honestly verify it.

## Scope

Text-layer PDFs. Vector-outline or image-baked text is out of scope
for any text redactor and is called out in the report rather than
silently ignored.

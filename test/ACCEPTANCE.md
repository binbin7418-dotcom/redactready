# RedactReady — Acceptance

Seeded test (product-factory venv python: PyMuPDF):
`test/acceptance_test.py` — full output: `test/acceptance_results.txt`

**Result: 9/9 checks passed.**

Seeds: (1) a text PDF containing a name ×2, a case ID, an email and
an SSN-shaped number plus public control text; (2) an image-only PDF;
(3) a fake-redaction control — text covered by a drawn black
rectangle, not removed.

Verified:
- The checker CATCHES the fake redaction in the control (text hit ≥ 1)
- Term matches redacted ≥ 3; pattern matches (email + SSN) = 2
- Output leak re-check: 0 hits in the text channel AND 0 in the raw
  content-stream channel for both terms
- Control text survives untouched; case ID absent from output text
- Text document verdict PASS
- Image-only PDF flagged SCAN-DETECTED and NOT passed
- Original file untouched (SHA-256 before/after identical)
- GUI + engine compile clean (`py_compile`)

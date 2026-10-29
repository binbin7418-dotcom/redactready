#!/usr/bin/env python3
"""RedactReady seeded acceptance test (run with the product-factory
venv python, which provides PyMuPDF).

Seeds a PDF containing known secrets: a person name (x2), a case id,
an e-mail address (pattern), an SSN-shaped number (pattern) — plus an
innocent control term that must survive untouched, and a second PDF
that is image-only (no text layer) which MUST be flagged as a scan,
never passed. A fake-redaction control: text under a black rectangle
in a third PDF must still be FOUND by the raw-channel search (proving
the checker catches drawn-over text).
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fitz

from redact_ready import run_redactready, find_leaks, EMAIL_RE, SSN_RE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CHECKS = []
NAME = "Jonathan Meyer"
CASE = "CV-2026-4482"


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


os.makedirs(OUT, exist_ok=True)
p1 = os.path.join(OUT, "seed_doc.pdf")
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), f"Party: {NAME}, case {CASE}.", fontsize=11)
page.insert_text((72, 100), f"Contact {NAME} at jonathan.meyer@example.com", fontsize=11)
page.insert_text((72, 128), "SSN on file: 123-45-6789. Hearing in Springfield.", fontsize=11)
page.insert_text((72, 156), "Public control text stays visible.", fontsize=11)
doc.save(p1)
doc.close()
hash_before = hashlib.sha256(open(p1, "rb").read()).hexdigest()

p2 = os.path.join(OUT, "seed_scan.pdf")
doc = fitz.open()
page = doc.new_page()
pix = fitz.Pixmap(fitz.Colorspace(fitz.CS_RGB), fitz.IRect(0, 0, 200, 60))
pix.clear_with(200)
page.insert_image(page.rect, pixmap=pix)
doc.save(p2)
doc.close()

p3 = os.path.join(OUT, "seed_fake.pdf")
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), f"Hidden name: {NAME}", fontsize=11)
r = page.search_for(NAME)[0]
page.draw_rect(r, color=(0, 0, 0), fill=(0, 0, 0))  # drawn OVER, not removed
doc.save(p3)
doc.close()

leaks_fake = find_leaks(p3, [NAME])
check("checker catches drawn-over (fake) redaction",
      leaks_fake[NAME]["text_hits"] >= 1 or leaks_fake[NAME]["raw_hits"] >= 1,
      f"{leaks_fake[NAME]}")

s = run_redactready([p1, p2], os.path.join(OUT, "redacted"),
                    [NAME, CASE], also_regexes=[EMAIL_RE, SSN_RE])
by_name = {os.path.basename(r["src"]): r for r in s["files"]}
r1, r2 = by_name["seed_doc.pdf"], by_name["seed_scan.pdf"]

check("term matches found & redacted", r1["matches_redacted"] >= 3,
      f"{r1['matches_redacted']}")
check("pattern matches redacted (email+ssn)", r1["regex_matches"] >= 2,
      f"{r1['regex_matches']}")
check("zero leaks both channels", r1["leak_free"], f"{r1['leaks']}")
out_text = fitz.open(r1["dst"])[0].get_text()
check("control text survives", "Public control text stays visible." in out_text)
check("case id gone from text", CASE not in out_text)
check("doc 1 verdict PASS", r1["verdict"])
check("scan PDF flagged, not passed", r2["scan_detected"] and not r2["verdict"])
check("original untouched",
      hashlib.sha256(open(p1, "rb").read()).hexdigest() == hash_before)

passed = sum(1 for _, ok, _ in CHECKS if ok)
print(f"\n{passed}/{len(CHECKS)} checks passed")
sys.exit(0 if passed == len(CHECKS) else 1)

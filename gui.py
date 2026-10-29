#!/usr/bin/env python3
"""RedactReady desktop shell (tkinter).
Pick PDFs + terms -> truly redacted copies + leak re-check report."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redact_ready import run_redactready, EMAIL_RE, SSN_RE


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RedactReady — True PDF Redaction with Leak Re-Check")
        self.geometry("700x620")
        self.paths = []
        self.emails = tk.BooleanVar(value=True)
        self.ssn = tk.BooleanVar(value=False)
        tk.Label(self, text="PDF files:").pack(anchor="w", padx=12, pady=(12, 2))
        row = tk.Frame(self)
        row.pack(fill="x", padx=12)
        tk.Button(row, text="Add files…", command=self.pick_files).pack(side="left")
        tk.Button(row, text="Add folder…", command=self.pick_folder).pack(side="left", padx=6)
        tk.Button(row, text="Clear", command=self.clear).pack(side="left")
        self.count_lbl = tk.Label(self, text="0 files selected")
        self.count_lbl.pack(anchor="w", padx=12, pady=(4, 0))
        tk.Label(self, text="Terms to redact (one per line — names, case numbers, IDs):").pack(
            anchor="w", padx=12, pady=(10, 2))
        self.terms_box = tk.Text(self, height=6)
        self.terms_box.pack(fill="x", padx=12)
        tk.Checkbutton(self, text="Also redact e-mail addresses (pattern)",
                       variable=self.emails).pack(anchor="w", padx=12, pady=(6, 0))
        tk.Checkbutton(self, text="Also redact US SSN-shaped numbers (###-##-####)",
                       variable=self.ssn).pack(anchor="w", padx=12)
        self.btn = tk.Button(self, text="Redact & Leak-Check", command=self.run, height=2)
        self.btn.pack(pady=12)
        self.log = scrolledtext.ScrolledText(self, wrap="word")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.write("RedactReady removes the matched text from the PDF itself (not just\n"
                   "a black box on top), then searches the output twice — extracted\n"
                   "text and raw content streams — and only PASSes files with zero\n"
                   "leaks. Scanned pages are flagged, never silently passed.\n")

    def write(self, s):
        self.log.insert("end", s)
        self.log.see("end")

    def _refresh(self):
        self.count_lbl.config(text=f"{len(self.paths)} file(s)/folder(s) selected")

    def pick_files(self):
        self.paths += list(filedialog.askopenfilenames(
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]))
        self._refresh()

    def pick_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.paths.append(p)
        self._refresh()

    def clear(self):
        self.paths = []
        self._refresh()

    def run(self):
        terms = [t.strip() for t in self.terms_box.get("1.0", "end").splitlines()
                 if t.strip()]
        if not self.paths:
            messagebox.showerror("RedactReady", "Add at least one PDF first.")
            return
        if not terms and not (self.emails.get() or self.ssn.get()):
            messagebox.showerror("RedactReady", "Enter at least one term or pattern.")
            return
        self._terms = terms
        self.btn.config(state="disabled")
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        try:
            regexes = []
            if self.emails.get():
                regexes.append(EMAIL_RE)
            if self.ssn.get():
                regexes.append(SSN_RE)
            outdir = os.path.join(os.path.expanduser("~"), "RedactReady_output")
            s = run_redactready(self.paths, outdir, self._terms, regexes)
            self.write(f"\nDone. {len(s['files'])} file(s), errors: {len(s['errors'])}.\n")
            for r in s["files"]:
                self.write(f"- {os.path.basename(r['src'])}: {r['matches_redacted']} redacted, "
                           f"leak-free: {r['leak_free']}, scan detected: {r['scan_detected']}\n")
            self.write(f"Verdict: {'PASS' if s['verdict'] else 'CHECK REPORT'}\n"
                       f"Output folder: {outdir}\nReport: {s['report_path']}\n")
        except Exception as e:
            self.write(f"\nError: {e}\n")
        finally:
            self.btn.config(state="normal")


if __name__ == "__main__":
    App().mainloop()

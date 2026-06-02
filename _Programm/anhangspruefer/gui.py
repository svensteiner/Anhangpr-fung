"""
Graphical User Interface für den Anhangsprüfer.

Die GUI ist als Notebook (Tabs) aufgebaut. Jeder Tab entspricht einem
der zwei klar getrennten Ziele des Tools:

    Tab 1 - Compliance-Prüfung (UGB)
            -> anhangspruefer.compliance.*

    Tab 2 - Vorjahresvergleich
            -> anhangspruefer.vorjahresvergleich.*

Die geteilten Header / Disclaimer / Statusleisten sitzen außerhalb des
Notebooks. Die ziel-spezifische Logik kapselt jeweils ein eigener Frame
(`ComplianceTab`, `VorjahresvergleichTab`).
"""

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Add parent directory to path for imports when running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from anhangspruefer import __version__, DISCLAIMER
from anhangspruefer.compliance.engine import ReviewEngine
from anhangspruefer.compliance.reporting.markdown_report import MarkdownReportGenerator
from anhangspruefer.compliance.knowledge.checklist_loader import ChecklistLoader
from anhangspruefer.vorjahresvergleich import (
    compare_anhaenge,
    generate_report as generate_yoy_report,
    generate_excel as generate_yoy_excel,
)
from anhangspruefer.utils.logging_config import setup_logging


# =============================================================================
# Tab 1: Compliance-Prüfung (Ziel 1)
# =============================================================================
class ComplianceTab(ttk.Frame):
    """UI für die UGB-Compliance-Prüfung gegen eine Checkliste."""

    def __init__(self, parent, status_setter):
        super().__init__(parent, padding=10)
        self._set_status = status_setter

        self.anhang_path = tk.StringVar()
        self.checklist_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "output"))
        self.last_report_path: Path | None = None

        self._build()

    def _build(self):
        intro = ttk.Label(
            self,
            text="Ziel 1: Strukturierte Prüfung des Anhangs gegen UGB-Angabepflichten (§§ 236-243).",
            font=("Segoe UI", 9, "italic"),
            foreground="#444",
        )
        intro.pack(fill=tk.X, pady=(0, 8))

        # File selection
        files = ttk.LabelFrame(self, text="Dateien", padding=10)
        files.pack(fill=tk.X, pady=(0, 10))

        self._file_row(files, "Anhang (PDF):", self.anhang_path,
                       self._select_anhang, ftypes=[("PDF Dateien", "*.pdf")])
        self._file_row(files, "Checkliste (optional):", self.checklist_path,
                       self._select_checklist, ftypes=[("JSON Dateien", "*.json")])
        self._dir_row(files, "Ausgabeordner:", self.output_dir, self._select_output_dir)

        # Actions
        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, pady=(0, 10))
        self.run_button = ttk.Button(actions, text="▶ Prüfung starten", command=self._run)
        self.run_button.pack(side=tk.LEFT, padx=(0, 10))
        self.open_button = ttk.Button(actions, text="📄 Protokoll öffnen",
                                       command=self._open_report, state=tk.DISABLED)
        self.open_button.pack(side=tk.LEFT)

        # Progress
        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.pack(fill=tk.X, pady=(0, 6))
        self.progress_label = ttk.Label(self, text="Bereit")
        self.progress_label.pack(fill=tk.X, pady=(0, 8))

        # Results
        results = ttk.LabelFrame(self, text="Ergebnisse", padding=10)
        results.pack(fill=tk.BOTH, expand=True)
        self.results = scrolledtext.ScrolledText(results, wrap=tk.WORD,
                                                  font=("Consolas", 10), height=12)
        self.results.pack(fill=tk.BOTH, expand=True)
        self.results.insert(tk.END,
            "Wählen Sie eine Anhang-Datei aus und klicken Sie auf 'Prüfung starten'.\n")
        self.results.config(state=tk.DISABLED)

    # ---- helpers --------------------------------------------------------
    def _file_row(self, parent, label, var, cmd, ftypes):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, width=60).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row, text="Durchsuchen...", command=cmd).pack(side=tk.LEFT)

    def _dir_row(self, parent, label, var, cmd):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X)
        ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, width=60).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row, text="Durchsuchen...", command=cmd).pack(side=tk.LEFT)

    def _select_anhang(self):
        f = filedialog.askopenfilename(title="Anhang auswählen",
                                        filetypes=[("PDF", "*.pdf"), ("Alle", "*.*")])
        if f:
            self.anhang_path.set(f)

    def _select_checklist(self):
        f = filedialog.askopenfilename(title="Checkliste auswählen",
                                        filetypes=[("JSON", "*.json"), ("Alle", "*.*")])
        if f:
            self.checklist_path.set(f)

    def _select_output_dir(self):
        d = filedialog.askdirectory(title="Ausgabeordner auswählen")
        if d:
            self.output_dir.set(d)

    def _open_report(self):
        if self.last_report_path and self.last_report_path.exists():
            os.startfile(str(self.last_report_path))
        else:
            messagebox.showwarning("Kein Protokoll", "Es wurde noch kein Protokoll erstellt.")

    def _log(self, msg):
        self.results.config(state=tk.NORMAL)
        self.results.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.results.see(tk.END)
        self.results.config(state=tk.DISABLED)
        self.update_idletasks()

    def _set_progress(self, value, msg=""):
        self.progress["value"] = value
        if msg:
            self.progress_label.config(text=msg)
        self._set_status(msg or "Compliance-Prüfung läuft...")
        self.update_idletasks()

    # ---- run ------------------------------------------------------------
    def _run(self):
        if not self.anhang_path.get():
            messagebox.showerror("Fehler", "Bitte wählen Sie eine Anhang-Datei aus.")
            return
        anhang = Path(self.anhang_path.get())
        if not anhang.exists():
            messagebox.showerror("Fehler", f"Datei nicht gefunden:\n{anhang}")
            return

        self.run_button.config(state=tk.DISABLED)
        self.open_button.config(state=tk.DISABLED)
        self.results.config(state=tk.NORMAL)
        self.results.delete(1.0, tk.END)
        self.results.config(state=tk.DISABLED)

        threading.Thread(target=self._thread, daemon=True).start()

    def _thread(self):
        try:
            anhang = Path(self.anhang_path.get())
            output = Path(self.output_dir.get())
            output.mkdir(parents=True, exist_ok=True)

            self._set_progress(5, "Initialisiere...")
            self._log("=" * 50)
            self._log("COMPLIANCE-PRÜFUNG GESTARTET")
            self._log("=" * 50)
            self._log(f"Anhang: {anhang.name}")

            setup_logging(log_level="WARNING", console_output=False)
            engine = ReviewEngine()
            self._log("✓ Engine geladen")

            loader = ChecklistLoader()
            if self.checklist_path.get() and Path(self.checklist_path.get()).exists():
                checklist = loader.load_from_json(Path(self.checklist_path.get()))
                self._log(f"✓ Eigene Checkliste: {Path(self.checklist_path.get()).name}")
            else:
                checklist = loader.load_default_checklist()
                self._log("✓ Standard-Checkliste")
            self._log(f"  → {len(checklist.items)} Prüfungspunkte")

            self._set_progress(30, "Analysiere Anhang...")
            result = engine.review(
                notes_path=anhang,
                checklist_path=Path(self.checklist_path.get()) if self.checklist_path.get() else None,
            )
            self._log("✓ Analyse fertig")

            self._set_progress(80, "Erstelle Protokoll...")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            md = output / f"pruefungsprotokoll_{ts}.md"
            html = output / f"pruefungsprotokoll_{ts}.html"
            gen = MarkdownReportGenerator(checklist=checklist)
            gen.generate(result, md)
            gen.generate_word_compatible(result, html)

            stats = result.summary_statistics
            total = stats.get("total_items", 0)
            self._log("")
            self._log(f"Geprüfte Punkte: {total}")
            for status, count in stats.get("status_counts", {}).items():
                pct = count / total * 100 if total else 0
                self._log(f"  • {status}: {count} ({pct:.0f}%)")

            self._log("")
            self._log(f"Markdown:  {md.name}")
            self._log(f"HTML/Word: {html.name}")
            self._set_progress(100, "Fertig")
            self.last_report_path = html

            self.after(0, lambda: self.open_button.config(state=tk.NORMAL))
            self.after(0, lambda: messagebox.showinfo(
                "Compliance-Prüfung abgeschlossen",
                f"Protokoll erstellt:\n{html}\n\nValidierung durch Prüfer erforderlich!"))
        except Exception as e:
            self._log(f"✗ FEHLER: {e}")
            self._set_progress(0, "Fehler")
            self.after(0, lambda: messagebox.showerror("Fehler", str(e)))
        finally:
            self.after(0, lambda: self.run_button.config(state=tk.NORMAL))


# =============================================================================
# Tab 2: Vorjahresvergleich (Ziel 2)
# =============================================================================
class VorjahresvergleichTab(ttk.Frame):
    """UI für den 2025↔2024 Vorjahreszahlen-Abgleich."""

    def __init__(self, parent, status_setter):
        super().__init__(parent, padding=10)
        self._set_status = status_setter

        self.current_pdf = tk.StringVar()
        self.prior_pdf = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "output"))
        self.last_report_path: Path | None = None

        self._build()

    def _build(self):
        intro = ttk.Label(
            self,
            text=("Ziel 2: Prüft, ob die Vorjahreszahlen im aktuellen Anhang (z.B. 2025) "
                  "mit den Berichtsjahreszahlen aus dem Vorjahres-Anhang (z.B. 2024) übereinstimmen."),
            font=("Segoe UI", 9, "italic"),
            foreground="#444",
            wraplength=820,
        )
        intro.pack(fill=tk.X, pady=(0, 8))

        files = ttk.LabelFrame(self, text="Dateien", padding=10)
        files.pack(fill=tk.X, pady=(0, 10))

        self._file_row(files, "Aktueller Anhang (PDF):", self.current_pdf,
                       lambda: self._pick(self.current_pdf, "Aktuellen Anhang auswählen"))
        self._file_row(files, "Vorjahres-Anhang (PDF):", self.prior_pdf,
                       lambda: self._pick(self.prior_pdf, "Vorjahres-Anhang auswählen"))
        self._dir_row(files, "Ausgabeordner:", self.output_dir, self._select_output_dir)

        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, pady=(0, 10))
        self.run_button = ttk.Button(actions, text="▶ Vergleich starten", command=self._run)
        self.run_button.pack(side=tk.LEFT, padx=(0, 10))
        self.open_button = ttk.Button(actions, text="📄 Bericht öffnen",
                                       command=self._open_report, state=tk.DISABLED)
        self.open_button.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.pack(fill=tk.X, pady=(0, 6))
        self.progress_label = ttk.Label(self, text="Bereit")
        self.progress_label.pack(fill=tk.X, pady=(0, 8))

        results = ttk.LabelFrame(self, text="Ergebnisse", padding=10)
        results.pack(fill=tk.BOTH, expand=True)
        self.results = scrolledtext.ScrolledText(results, wrap=tk.WORD,
                                                  font=("Consolas", 10), height=12)
        self.results.pack(fill=tk.BOTH, expand=True)
        self.results.insert(tk.END,
            "Wählen Sie zwei Anhang-PDFs (aktuell und vorjahr) und klicken Sie auf 'Vergleich starten'.\n")
        self.results.config(state=tk.DISABLED)

    def _file_row(self, parent, label, var, cmd):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, width=60).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row, text="Durchsuchen...", command=cmd).pack(side=tk.LEFT)

    def _dir_row(self, parent, label, var, cmd):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X)
        ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, width=60).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row, text="Durchsuchen...", command=cmd).pack(side=tk.LEFT)

    def _pick(self, var, title):
        f = filedialog.askopenfilename(title=title,
                                        filetypes=[("PDF", "*.pdf"), ("Alle", "*.*")])
        if f:
            var.set(f)

    def _select_output_dir(self):
        d = filedialog.askdirectory(title="Ausgabeordner auswählen")
        if d:
            self.output_dir.set(d)

    def _open_report(self):
        if self.last_report_path and self.last_report_path.exists():
            os.startfile(str(self.last_report_path))
        else:
            messagebox.showwarning("Kein Bericht", "Es wurde noch kein Bericht erstellt.")

    def _log(self, msg):
        self.results.config(state=tk.NORMAL)
        self.results.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.results.see(tk.END)
        self.results.config(state=tk.DISABLED)
        self.update_idletasks()

    def _set_progress(self, value, msg=""):
        self.progress["value"] = value
        if msg:
            self.progress_label.config(text=msg)
        self._set_status(msg or "Vorjahresvergleich läuft...")
        self.update_idletasks()

    def _run(self):
        if not self.current_pdf.get() or not self.prior_pdf.get():
            messagebox.showerror("Fehler", "Bitte beide Anhang-PDFs auswählen.")
            return
        cur, pri = Path(self.current_pdf.get()), Path(self.prior_pdf.get())
        if not cur.exists() or not pri.exists():
            messagebox.showerror("Fehler", "Eine der Dateien wurde nicht gefunden.")
            return

        self.run_button.config(state=tk.DISABLED)
        self.open_button.config(state=tk.DISABLED)
        self.results.config(state=tk.NORMAL)
        self.results.delete(1.0, tk.END)
        self.results.config(state=tk.DISABLED)

        threading.Thread(target=self._thread, daemon=True).start()

    def _thread(self):
        try:
            cur = Path(self.current_pdf.get())
            pri = Path(self.prior_pdf.get())
            output = Path(self.output_dir.get())
            output.mkdir(parents=True, exist_ok=True)

            self._set_progress(10, "Extrahiere Label/Zahl-Paare...")
            self._log("=" * 50)
            self._log("VORJAHRESVERGLEICH GESTARTET")
            self._log("=" * 50)
            self._log(f"Aktuell: {cur.name}")
            self._log(f"Vorjahr: {pri.name}")

            self._set_progress(40, "Vergleiche...")
            result = compare_anhaenge(cur, pri)

            self._set_progress(80, "Erstelle Bericht...")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            md = output / f"vorjahresvergleich_{ts}.md"
            xlsx = output / f"vorjahresvergleich_{ts}.xlsx"
            generate_yoy_report(result, md)
            generate_yoy_excel(result, xlsx)

            stats = result.stats
            self._log("")
            self._log(f"OK              : {stats.get('OK', 0)}")
            self._log(f"ABWEICHUNG      : {stats.get('ABWEICHUNG', 0)}")
            self._log(f"Nur aktuell     : {stats.get('NUR_AKTUELL', 0)}")
            self._log(f"Nur vorjahr     : {stats.get('NUR_VORJAHR', 0)}")
            self._log(f"Wert fehlt      : {stats.get('FEHLENDER_WERT', 0)}")
            self._log(f"Gesamt          : {stats.get('GESAMT', 0)}")
            self._log("")
            self._log(f"Markdown: {md.name}")
            self._log(f"Excel   : {xlsx.name}")

            self._set_progress(100, "Fertig")
            self.last_report_path = xlsx
            self.after(0, lambda: self.open_button.config(state=tk.NORMAL))
            self.after(0, lambda: messagebox.showinfo(
                "Vorjahresvergleich abgeschlossen",
                f"Berichte erstellt:\n• {md.name}\n• {xlsx.name}\n\nManuelle Validierung erforderlich!"))
        except Exception as e:
            self._log(f"✗ FEHLER: {e}")
            self._set_progress(0, "Fehler")
            self.after(0, lambda: messagebox.showerror("Fehler", str(e)))
        finally:
            self.after(0, lambda: self.run_button.config(state=tk.NORMAL))


# =============================================================================
# Hauptfenster
# =============================================================================
class AnhangsprueferGUI:
    """Top-level Fenster mit Notebook für die zwei Ziele."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Anhangsprüfer v{__version__}")
        self.root.geometry("950x760")
        self.root.minsize(880, 660)

        ttk.Style().theme_use("clam")

        self._build_menu()
        self._build_header()
        self._build_notebook()
        self._build_status_bar()

        self.root.after(100, self._show_disclaimer)

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        help_menu.add_command(label="Haftungsausschluss", command=self._show_disclaimer)
        help_menu.add_command(label="Über Anhangsprüfer", command=self._show_about)

    def _build_header(self):
        header = ttk.Frame(self.root, padding=(10, 10, 10, 0))
        header.pack(fill=tk.X)
        ttk.Label(header, text="Anhangsprüfer",
                  font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text="Prüfungsunterstützung für den UGB-Anhang",
                  font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(10, 0), pady=(8, 0))

        warn = ttk.Frame(self.root)
        warn.pack(fill=tk.X, padx=10, pady=(5, 5))
        tk.Label(
            warn,
            text="⚠ HINWEIS: Dieses Tool ersetzt nicht die fachliche Beurteilung durch einen Wirtschaftsprüfer!",
            font=("Segoe UI", 9, "bold"),
            foreground="#856404",
            background="#fff3cd",
            padx=10, pady=5,
        ).pack(fill=tk.X)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))

        self.compliance_tab = ComplianceTab(self.notebook, self._set_status)
        self.vorjahres_tab = VorjahresvergleichTab(self.notebook, self._set_status)

        self.notebook.add(self.compliance_tab, text="  1. Compliance-Prüfung (UGB)  ")
        self.notebook.add(self.vorjahres_tab, text="  2. Vorjahresvergleich  ")

    def _build_status_bar(self):
        self.status_label = ttk.Label(
            self.root,
            text=f"Anhangsprüfer v{__version__} | Nur zur Prüfungsunterstützung",
            relief=tk.SUNKEN,
            padding=(5, 2),
        )
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)

    def _set_status(self, msg: str):
        self.status_label.config(text=f"Anhangsprüfer v{__version__} | {msg}")

    def _show_disclaimer(self):
        messagebox.showwarning(
            "Wichtiger Hinweis",
            "HAFTUNGSAUSSCHLUSS\n\n"
            "Dieses Tool dient ausschließlich der Prüfungsunterstützung und ersetzt\n"
            "NICHT die fachliche Beurteilung durch einen qualifizierten Wirtschaftsprüfer.\n\n"
            "Alle automatisch generierten Bewertungen sind vorläufige Arbeitsergebnisse,\n"
            "die einer manuellen Überprüfung durch den verantwortlichen Prüfer bedürfen.\n\n"
            "Es handelt sich NICHT um eine UGB-konforme Prüfung."
        )

    def _show_about(self):
        messagebox.showinfo(
            "Über Anhangsprüfer",
            f"Anhangsprüfer v{__version__}\n\n"
            "Zwei klar getrennte Ziele:\n"
            "  1. Compliance-Prüfung gegen UGB-Angabepflichten (§§ 236-243)\n"
            "  2. Vorjahresvergleich zwischen aktuellem und vorjährigem Anhang\n\n"
            "Alle Bewertungen sind vorläufig und erfordern Prüfervalidierung."
        )


def main():
    root = tk.Tk()
    try:
        if hasattr(sys, "_MEIPASS"):
            icon_path = Path(sys._MEIPASS) / "icon.ico"
        else:
            icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
    except Exception:
        pass
    AnhangsprueferGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

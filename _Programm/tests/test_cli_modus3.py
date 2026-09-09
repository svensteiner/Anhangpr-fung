# -*- coding: utf-8 -*-
"""CLI und run_review.py dürfen die alte Engine nicht mehr still nutzen."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROG = ROOT / "_Programm"


def test_old_review_engine_cannot_run():
    from anhangspruefer.compliance.engine import ReviewEngine

    with pytest.raises(RuntimeError, match="abgeschaltet"):
        ReviewEngine().review("anhang.pdf")


def test_run_review_is_disabled():
    text = (PROG / "run_review.py").read_text(encoding="utf-8")
    assert "ReviewEngine" not in text
    assert "Starten.bat" in text
    proc = subprocess.run(
        [sys.executable, str(PROG / "run_review.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "unbekannt" in proc.stdout.lower()
    assert "starten.bat" in proc.stdout.lower()


def test_run_gui_is_disabled():
    text = (PROG / "run_gui.py").read_text(encoding="utf-8")
    assert "Starten.bat" in text
    proc = subprocess.run(
        [sys.executable, str(PROG / "run_gui.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    out = (proc.stdout + proc.stderr).lower()
    assert "starten.bat" in out
    assert "unbekannt" in out


def test_gui_module_is_disabled():
    text = (PROG / "anhangspruefer" / "gui.py").read_text(encoding="utf-8")
    assert "ReviewEngine" not in text
    assert "tkinter" not in text
    assert "Starten.bat" in text
    proc = subprocess.run(
        [sys.executable, str(PROG / "anhangspruefer" / "gui.py")],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(PROG),
    )
    assert proc.returncode == 2
    out = (proc.stdout + proc.stderr).lower()
    assert "starten.bat" in out
    assert "unbekannt" in out


def test_cli_review_requires_company_profile():
    proc = subprocess.run(
        [sys.executable, "-m", "anhangspruefer", "review", "anhang.pdf"],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(PROG),
    )
    assert proc.returncode != 0
    blob = (proc.stderr + proc.stdout).lower()
    assert "rechtsform" in blob or "required" in blob


def test_cli_help_names_pdf_or_word():
    proc = subprocess.run(
        [sys.executable, "-m", "anhangspruefer", "review", "-h"],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(PROG),
    )
    assert proc.returncode == 0
    assert "Word" in proc.stdout or "word" in proc.stdout.lower()
    assert "--rechtsform" in proc.stdout
    assert "--groessenklasse" in proc.stdout

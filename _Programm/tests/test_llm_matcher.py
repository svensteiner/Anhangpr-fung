"""Tests für die lokale KI-Zuordnung (llm_matcher) – ohne Netzwerk/Ollama.

Ein Fake-LLM ersetzt Mistral; geprüft werden Vertraulichkeits-Guard,
Kandidatenauswahl, Antwort-Parsing und die Verfeinerung der Findings.
"""

from datetime import datetime

import pytest

from anhangspruefer.models.checklist import Checklist, ChecklistItem
from anhangspruefer.models.enums import ComplianceStatus
from anhangspruefer.models.finding import Finding, ReviewResult
from anhangspruefer.compliance.knowledge.llm_matcher import (
    LocalLLM,
    _parse_assessment,
    build_prompt,
    refine_findings,
    select_candidates,
)


# --- Vertraulichkeit: nur localhost erlaubt ---------------------------------
def test_localllm_rejects_non_localhost():
    with pytest.raises(ValueError):
        LocalLLM(base_url="http://api.example.com:11434")
    with pytest.raises(ValueError):
        LocalLLM(base_url="https://ollama.some-cloud.io")


def test_localllm_accepts_localhost():
    LocalLLM(base_url="http://127.0.0.1:11434")
    LocalLLM(base_url="http://localhost:11434")


def test_localllm_rejects_userinfo_bypass():
    # Council-Befund: 'http://127.0.0.1:11434@fremd' würde per startswith durchrutschen
    with pytest.raises(ValueError):
        LocalLLM(base_url="http://127.0.0.1:11434@evil.example.com")
    with pytest.raises(ValueError):
        LocalLLM(base_url="http://user:pass@127.0.0.1:11434")
    with pytest.raises(ValueError):
        LocalLLM(base_url="https://127.0.0.1:11434")   # nur http erlaubt


# --- Kandidatenauswahl -------------------------------------------------------
def _item(desc, kws=(), iid="K1", cat="Verbindlichkeiten"):
    return ChecklistItem(item_id=iid, category=cat, description=desc,
                         search_keywords=list(kws))


def test_select_candidates_prefers_specific_paragraphs():
    paras = [
        ("Die Gewinn- und Verlustrechnung wurde nach dem Gesamtkostenverfahren erstellt.", 5),
        ("Von den Verbindlichkeiten haben EUR 0,00 eine Restlaufzeit von mehr als fünf Jahren.", 4),
        ("Der Lagebericht steht im Einklang mit dem Jahresabschluss.", 9),
    ]
    item = _item("Angabe des Gesamtbetrags der Verbindlichkeiten mit einer Restlaufzeit von mehr als fünf Jahren",
                 kws=["Verbindlichkeiten", "Restlaufzeit"])
    cands = select_candidates(item, paras, k=2)
    assert cands and "Restlaufzeit von mehr als fünf Jahren" in cands[0][0]


def test_select_candidates_k017_regression():
    """KPMG-Komposita + Bindestrich-Schreibweise: der Absatz mit der ECHTEN
    Angabe muss vor dem Absatz rangieren, der nur 'Firmenwert' erwähnt."""
    latente = ("Zwischen den Wertansätzen bestehen Steuerlatenzen für den Aktivposten "
               "Leasing KFZ, des Geschäfts-(Firmen-)wertes und der Rückstellung für "
               "Jubiläumsgelder in erheblicher Höhe zum Bilanzstichtag.", 4)
    abschreibung = ("Die planmäßigen Abschreibungen wurden linear der voraussichtlichen "
                    "Nutzungsdauer entsprechend vorgenommen, für den Geschäfts-(Firmen-)wert "
                    "gesondert über zehn Jahre.", 2)
    item = _item("Erläuterung der gewählten Abschreibungsdauer sowie die Abschreibungsmethode "
                 "für jeden Geschäfts- oder Firmenwert gesondert",
                 kws=["Abschreibungsdauer", "Abschreibungsmethode", "Firmenwert"])
    cands = select_candidates(item, [latente, abschreibung], k=2)
    assert cands[0][1] == 2          # Abschreibungs-Absatz zuerst (S.2)


def test_norm_compact_matches_hyphenated_compounds():
    from anhangspruefer.compliance.knowledge.llm_matcher import _norm_compact
    assert "firmenwert" in _norm_compact("des Geschäfts-(Firmen-)wertes")


def test_best_sentence_skips_page_header_and_picks_relevant():
    from anhangspruefer.compliance.knowledge.llm_matcher import _best_sentence
    para = ("HANKOOK Tire Austria GmbH Anhang. Folgende Nutzungsdauern wurden den "
            "planmäßigen Abschreibungen zugrunde gelegt: Geschäfts-(Firmen-)wert zehn Jahre. "
            "Der Firmenwert wird linear abgeschrieben.")
    item = _item("Erläuterung der Abschreibungsdauer und Abschreibungsmethode für den Firmenwert",
                 kws=["Abschreibungsdauer", "Abschreibungsmethode", "Firmenwert", "Nutzungsdauer"])
    s = _best_sentence(para, item)
    assert "HANKOOK Tire Austria GmbH Anhang" not in s     # Seitenkopf vermieden
    assert ("Nutzungsdauer" in s) or ("Abschreibung" in s)  # relevante Stelle


def test_split_sentences_keeps_abbreviations_together():
    from anhangspruefer.compliance.knowledge.llm_matcher import _split_sentences
    text = ("Gemäß § 237 Abs. 1 Z 7 UGB wird berichtet. Die Angabe erfolgt gesondert.")
    parts = _split_sentences(text)
    # 'Abs. 1' und 'Z 7' dürfen den Satz NICHT zerreißen -> genau 2 Sätze
    assert len(parts) == 2
    assert "Abs. 1 Z 7 UGB wird berichtet" in parts[0]


def test_split_sentences_does_not_break_before_number():
    from anhangspruefer.compliance.knowledge.llm_matcher import _split_sentences
    text = "Die Aufwendungen betragen EUR 29.500,00. Der Betrag ist geprüft."
    parts = _split_sentences(text)
    assert len(parts) == 2 and parts[0].endswith("29.500,00.")


def test_generic_words_do_not_match():
    # "Angabe"/"Erläuterung" allein dürfen keinen Kandidaten erzeugen
    paras = [("Erläuterung: Diese Angabe betrifft etwas völlig anderes.", 1)]
    item = _item("Angabe der Restlaufzeiten", kws=["Angabe", "Erläuterung"])
    assert select_candidates(item, paras) == []


# --- Antwort-Parsing ---------------------------------------------------------
def test_parse_assessment_valid_and_bounds():
    a = _parse_assessment({"erfuellt": "ja", "absatz": 2, "begruendung": "ok"}, 3)
    assert a.erfuellt == "ja" and a.absatz_index == 1
    # Absatz außerhalb der Kandidatenliste -> "ja" wird zu "unklar" abgestuft
    b = _parse_assessment({"erfuellt": "ja", "absatz": 9, "begruendung": ""}, 3)
    assert b.erfuellt == "unklar" and b.absatz_index is None
    assert _parse_assessment({"erfuellt": "vielleicht"}, 3) is None
    assert _parse_assessment(None, 3) is None


# --- Verfeinerung mit Fake-LLM ----------------------------------------------
class FakeLLM:
    """Gibt vorbereitete Antworten zurück; niemals Netzwerk."""
    model = "fake"

    def __init__(self, answers):
        self.answers = list(answers)

    def is_available(self):
        return True

    def generate_json(self, prompt, num_predict=120):
        return self.answers.pop(0) if self.answers else None


def _setup():
    cl = Checklist(name="t", version="")
    cl.add_item(_item("Angabe der Restlaufzeit der Verbindlichkeiten",
                      kws=["Verbindlichkeiten", "Restlaufzeit"], iid="K1"))
    cl.add_item(_item("Angabe der Haftungsverhältnisse",
                      kws=["Haftungsverhältnisse"], iid="K2", cat="Eventualverbindlichkeiten"))
    cl.add_item(_item("Umgründungsangabe", kws=["Verschmelzung"], iid="K3", cat="Umgründung"))
    res = ReviewResult(document_name="d", checklist_name="t", review_timestamp=datetime(2026, 1, 1))
    for iid in ("K1", "K2", "K3"):
        res.add_finding(Finding(checklist_item_id=iid,
                                status=ComplianceStatus.PARTIALLY_COMPLIANT, ugb_references=[]))
    res.findings[2].status = ComplianceStatus.NOT_APPLICABLE   # Relevanz-Filter
    paras = [
        ("Von den Verbindlichkeiten haben EUR 0,00 eine Restlaufzeit von mehr als fünf Jahren.", 4),
        ("Im Geschäftsjahr sind keine Haftungsverhältnisse auszuweisen.", 5),
    ]
    return cl, res, paras


def test_refine_findings_updates_status_and_evidence():
    cl, res, paras = _setup()
    llm = FakeLLM([
        {"erfuellt": "ja", "absatz": 1, "begruendung": "Betrag 0,00 angegeben"},
        {"erfuellt": "nein", "absatz": None,
         "fehlt_konkret": "Angabe der Haftungsverhältnisse nicht enthalten",
         "begruendung": "nicht gefunden"},
    ])
    summary = refine_findings(res, cl, paras, llm=llm)

    st = {f.checklist_item_id: f for f in res.findings}
    assert st["K1"].status == ComplianceStatus.COMPLIANT
    assert st["K1"].evidence and st["K1"].evidence[0].page_number == 4
    assert st["K1"].technical_reasoning.startswith("KI:")
    assert st["K2"].status == ComplianceStatus.NOT_COMPLIANT
    # KONKRETE Fehlt-Aussage wird übernommen
    assert st["K2"].missing_elements == ["Angabe der Haftungsverhältnisse nicht enthalten"]
    assert st["K3"].status == ComplianceStatus.NOT_APPLICABLE     # unberührt
    assert summary["verfeinert"] == 2 and summary["ki"] == "fake"


def test_refine_nein_without_fehlt_konkret_falls_back_to_prueffrage():
    cl, res, paras = _setup()
    llm = FakeLLM([
        {"erfuellt": "nein", "absatz": None, "fehlt_konkret": "x",
         "begruendung": ""},
        {"erfuellt": "nein", "absatz": None, "fehlt_konkret": None,
         "begruendung": "nichts"},
    ])
    refine_findings(res, cl, paras, llm=llm)
    st = {f.checklist_item_id: f for f in res.findings}
    # Fallback: Prüffrage als konkrete Fehlt-Benennung
    assert st["K2"].missing_elements == ["Angabe der Haftungsverhältnisse"]


def test_refine_findings_keeps_result_on_model_error():
    cl, res, paras = _setup()
    llm = FakeLLM([None, {"erfuellt": "quatsch"}])   # beide Antworten unbrauchbar
    refine_findings(res, cl, paras, llm=llm)
    st = {f.checklist_item_id: f.status for f in res.findings}
    assert st["K1"] == ComplianceStatus.PARTIALLY_COMPLIANT   # Fallback bleibt
    assert st["K2"] == ComplianceStatus.PARTIALLY_COMPLIANT


def test_refine_findings_uses_answer_cache():
    # Etappe 1: eine Antwort kommt vom Modell und landet im Cache
    cl, res, paras = _setup()
    cache = {}
    llm = FakeLLM([{"erfuellt": "ja", "absatz": 1, "begruendung": "x"}])
    refine_findings(res, cl, paras, llm=llm, answer_cache=cache, max_seconds=0.0)
    # max_seconds=0 stoppt nach der 0. Modellanfrage NICHT für Cache-Treffer,
    # aber die erste Anfrage wird noch gestellt? -> Budget wird VOR der Anfrage
    # geprüft, daher hier: nichts verfeinert, Cache leer.
    assert cache == {}

    # Etappe 2: Cache vorbefüllt -> Punkte werden OHNE Modellanfrage verfeinert
    cl2, res2, paras2 = _setup()
    cache2 = {
        "K1": {"erfuellt": "ja", "absatz": 1, "begruendung": "aus Cache"},
        "K2": {"erfuellt": "nein", "absatz": None,
               "fehlt_konkret": "Haftungsangabe fehlt", "begruendung": "aus Cache"},
    }
    llm2 = FakeLLM([])          # darf NICHT gefragt werden
    summary = refine_findings(res2, cl2, paras2, llm=llm2, answer_cache=cache2,
                              max_seconds=0.0)
    st = {f.checklist_item_id: f.status for f in res2.findings}
    assert summary["verfeinert"] == 2
    assert st["K1"] == ComplianceStatus.COMPLIANT
    assert st["K2"] == ComplianceStatus.NOT_COMPLIANT


def test_cached_nein_without_fehlt_konkret_is_reasked():
    # Alt-Format-Cache ("nein" ohne fehlt_konkret) -> Modell wird neu gefragt
    cl, res, paras = _setup()
    cache = {"K1": {"erfuellt": "nein", "absatz": None, "begruendung": "alt"}}
    llm = FakeLLM([{"erfuellt": "nein", "absatz": None,
                    "fehlt_konkret": "Restlaufzeitangabe fehlt", "begruendung": "neu"}])
    refine_findings(res, cl, paras, llm=llm, answer_cache=cache)
    assert cache["K1"]["fehlt_konkret"] == "Restlaufzeitangabe fehlt"   # ersetzt


def test_apply_heuristic_fundstellen_offen_and_fehlt():
    from datetime import datetime
    from anhangspruefer.models.checklist import Checklist, ChecklistItem
    from anhangspruefer.models.finding import Finding, ReviewResult
    from anhangspruefer.models.enums import ComplianceStatus
    from anhangspruefer.compliance.knowledge.llm_matcher import apply_heuristic_fundstellen

    cl = Checklist(name="t", version="")
    cl.add_item(ChecklistItem(item_id="K1", category="Vorräte",
                description="Angabe der Vorratsbewertung", search_keywords=["Vorratsbewertung"]))
    cl.add_item(ChecklistItem(item_id="K2", category="Umgründung",
                description="Angabe zur Verschmelzungsbilanzierung", search_keywords=["Verschmelzungsbilanzierung"]))
    cl.add_item(ChecklistItem(item_id="K3", category="X", description="n.a. Punkt"))
    res = ReviewResult(document_name="d", checklist_name="t", review_timestamp=datetime(2026, 1, 1))
    for iid in ("K1", "K2", "K3"):
        res.add_finding(Finding(checklist_item_id=iid, status=ComplianceStatus.PARTIALLY_COMPLIANT, ugb_references=[]))
    res.findings[2].status = ComplianceStatus.NOT_APPLICABLE      # K3 = n.a.

    paras = [("Die Vorratsbewertung erfolgt zu Anschaffungskosten.", 2)]
    apply_heuristic_fundstellen(res, cl, paras)
    st = {f.checklist_item_id: f for f in res.findings}
    # Kandidat vorhanden -> Offen + korrekte Fundstelle (kein geratenes Ja)
    assert st["K1"].status == ComplianceStatus.NOT_ASSESSABLE
    assert st["K1"].evidence and st["K1"].evidence[0].page_number == 2
    assert "Vorratsbewertung" in st["K1"].evidence[0].quote
    # spezifischer Begriff fehlt belegbar -> Fehlt (konkret)
    assert st["K2"].status == ComplianceStatus.NOT_COMPLIANT and st["K2"].missing_elements
    # n.a. bleibt unberührt
    assert st["K3"].status == ComplianceStatus.NOT_APPLICABLE


def test_build_prompt_contains_rules_and_candidates():
    item = _item("Angabe X", kws=["Restlaufzeit"])
    p = build_prompt(item, [("Textabsatz eins", 4)])
    assert "Negativaussage" in p and "[1] Textabsatz eins" in p and "Angabe X" in p

"""
Lokale KI-Zuordnung: Anhang-Textstellen <-> KPMG-Prüfpunkte (Modus 3).

Der Stichwort-Matcher findet nur grobe Kandidaten (generische Wörter wie
"Angabe"/"Erläuterung" treffen fast jeden Absatz). Diese Schicht lässt ein
LOKALES Sprachmodell (Ollama + Mistral, http://127.0.0.1:11434) je Prüfpunkt
entscheiden, ob und WO die geforderte Angabe im Anhang steht.

VERTRAULICHKEIT (hart erzwungen):
    Mandantendaten sind geheim. Der Client verbindet sich AUSSCHLIESSLICH zu
    localhost — jede andere Adresse wird mit ValueError abgelehnt. Es findet
    kein Datenversand an Cloud-Dienste statt; ist Ollama nicht verfügbar,
    bleibt einfach das bisherige (Stichwort-)Ergebnis stehen.

Ablauf je (relevantem) Prüfpunkt:
    1. Kandidaten-Absätze per Stichwort-Überlappung vorauswählen (billig).
    2. Mistral prüft mit strenger JSON-Antwort: erfüllt ja/nein/unklar +
       Absatznummer + Kurzbegründung. Negativaussagen ("keine ...", "EUR 0,00")
       zählen ausdrücklich als Angabe.
    3. Finding aktualisieren: Status, Fundstelle (Absatz + Seite), Begründung.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from ...models.checklist import Checklist, ChecklistItem
from ...models.enums import ComplianceStatus
from ...models.finding import EvidenceItem, ReviewResult
from ...utils.logging_config import get_logger

logger = get_logger("llm_matcher")

_ALLOWED_HOSTS = ("http://127.0.0.1:", "http://localhost:")

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "mistral"

# deutsche Stoppwörter + generische Checklisten-Wörter (tragen nichts zur
# Kandidatenauswahl bei, weil sie fast jeden Prüfpunkt/Absatz treffen)
_STOP = {
    "angabe", "angaben", "erläuterung", "erlaeuterung", "aufgliederung",
    "beschreibung", "hinweis", "sowie", "oder", "und", "der", "die", "das",
    "des", "dem", "den", "eine", "einer", "eines", "einem", "einen", "bei",
    "für", "fuer", "von", "mit", "aus", "ist", "sind", "wird", "werden",
    "wurde", "wurden", "nach", "über", "ueber", "auf", "als", "auch", "wenn",
    "falls", "gemäß", "gemaess", "ugb", "afrac", "kfs", "sich", "zur", "zum",
    "nicht", "durch", "diese", "dieser", "dieses", "ihre", "ihres", "deren",
}


def _keywords(item: ChecklistItem) -> set[str]:
    """Aussagekräftige Wörter aus Prüffrage + Stichwörtern (klein, >3 Zeichen)."""
    text = item.description + " " + " ".join(item.search_keywords)
    words = re.findall(r"[a-zäöüß]{4,}", text.lower())
    return {w for w in words if w not in _STOP}


# ---------------------------------------------------------------------------
# Absatz-Extraktion mit Seitenzahlen (auch Tabellenzeilen behalten –
# Fundstellen stehen oft in Zahlenzeilen wie "... EUR 0,00 ...")
# ---------------------------------------------------------------------------
def extract_paragraphs(pdf_path: Path) -> list[tuple[str, int]]:
    import pdfplumber

    out: list[tuple[str, int]] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text(x_tolerance=2) or ""
                buf: list[str] = []

                def flush() -> None:
                    if buf:
                        para = re.sub(r"\s+", " ", " ".join(buf)).strip()
                        if len(para) >= 30:
                            out.append((para, page_num))
                        buf.clear()

                for raw in text.split("\n"):
                    ln = raw.strip()
                    if not ln:
                        flush()
                        continue
                    # nummerierte Überschriften trennen Absätze
                    if re.match(r"^\d+(?:\.\d+)*\.?\s+\S", ln) and buf:
                        flush()
                    buf.append(ln)
                flush()
    except Exception:
        logger.exception("Absatz-Extraktion fehlgeschlagen: %s", pdf_path)
    return out


def _norm_compact(text: str) -> str:
    """Nur Buchstaben, klein: 'Geschäfts-(Firmen-)wert' -> 'geschäftsfirmenwert'.

    Damit matchen Bindestrich-/Klammer-Schreibweisen des Anhangs die
    Checklisten-Stichwörter (z.B. 'Firmenwert')."""
    return re.sub(r"[^a-zäöüß]", "", text.lower())


def _kw_hit(kw: str, low: str, compact: str) -> bool:
    """Stichwort-Treffer inkl. Wortstamm: KPMG-Komposita wie
    'Abschreibungsdauer' treffen auch 'Abschreibungen ... Nutzungsdauer'."""
    if kw in low or kw in compact:
        return True
    if len(kw) >= 8 and kw[:7] in low:      # Stamm-Präfix (abschreibungsdauer -> abschre…)
        return True
    return False


# Satzende nur vor Großbuchstabe (nicht vor Zahlen: 'EUR 29.500. (Vorjahr' etc.).
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])")
# Abkürzungen, nach denen NICHT getrennt werden darf (dt. Rechnungslegung).
_ABBR = {"abs", "z", "lit", "nr", "ca", "vgl", "bzw", "inkl", "exkl",
         "mio", "mrd", "rz", "ggf", "evtl", "sog", "tz", "art", "ziff", "s", "u", "d",
         "i", "m", "b", "v", "o", "g"}
_TRAILING_ABBR_RE = re.compile(r"([A-Za-zäöüß]+)\.\s*$")


def _split_sentences(text: str) -> list[str]:
    """Satztrennung, die an Abkürzungen ('Abs. 1', 'z. B.') NICHT bricht.

    Es zählt nur das UNMITTELBAR vor dem Satzpunkt stehende Wort – eine echte
    Satzgrenze wie 'EUR 29.500,00.' (endet auf Ziffern) wird korrekt getrennt."""
    parts = _SENT_SPLIT_RE.split(text)
    merged: list[str] = []
    for p in parts:
        if merged:
            m = _TRAILING_ABBR_RE.search(merged[-1])
            if m and m.group(1).lower() in _ABBR:
                merged[-1] = merged[-1] + " " + p
                continue
        merged.append(p)
    return merged


def _best_sentence(paragraph: str, item: ChecklistItem, max_len: int = 220) -> str:
    """Passendste Satzstelle des Absatzes zum Prüfpunkt.

    Statt des Absatzanfangs (oft Seitenkopf 'HANKOOK … Anhang') wird der Satz
    mit der höchsten Stichwort-Überlappung zur Prüffrage gezeigt – so passt die
    Fundstelle inhaltlich zur geprüften Angabe."""
    kws = _keywords(item)
    sentences = [s.strip() for s in _split_sentences(paragraph) if len(s.strip()) >= 15]
    if not sentences:
        return paragraph[:max_len]

    # SPEZIFISCHE Begriffe (lange Komposita der Prüffrage) entscheiden zuerst:
    # Enthält irgendein Satz einen davon, kommen NUR diese Sätze in Frage.
    # Sonst gewinnen generische Wörter ("Angabe", "Erläuterung") und es wird der
    # falsche Satz des richtigen Absatzes zitiert.
    spezifisch = [w for w in kws if len(w) >= 10]

    def trifft_spezifisch(s: str) -> bool:
        low, compact = s.lower(), _norm_compact(s)
        return any(_kw_hit(w, low, compact) for w in spezifisch)

    kandidaten = [s for s in sentences if trifft_spezifisch(s)] if spezifisch else []
    if not kandidaten:
        kandidaten = sentences

    def score(s: str) -> float:
        low, compact = s.lower(), _norm_compact(s)
        return sum((2.0 if len(w) >= 10 else 1.0) for w in kws if _kw_hit(w, low, compact))

    best = max(kandidaten, key=score)
    if score(best) == 0:                 # kein Treffer -> erster sinnvoller Satz
        best = kandidaten[0]
    return _zitat_fenster(best, spezifisch, max_len)


def _zitat_fenster(satz: str, spezifisch: list[str], max_len: int) -> str:
    """Kürzt lange Sätze auf ein FENSTER um den Fachbegriff.

    Stures Abschneiden am Satzanfang verliert den entscheidenden Begriff, wenn
    er weiter hinten steht – die Fundstelle wirkt dann unpassend, obwohl der
    Satz korrekt ist.
    """
    if len(satz) <= max_len:
        return satz

    low = satz.lower()
    pos = -1
    for w in spezifisch:
        p = low.find(w)
        if p < 0 and len(w) >= 8:
            p = low.find(w[:7])          # Wortstamm (wie _kw_hit)
        if p >= 0 and (pos < 0 or p < pos):
            pos = p
    if pos < 0:
        return satz[:max_len]

    start = max(0, pos - max_len // 3)
    # an Wortgrenze beginnen, damit das Zitat lesbar bleibt
    if start > 0:
        leer = satz.find(" ", start)
        start = leer + 1 if 0 <= leer < start + 30 else start
    ausschnitt = satz[start:start + max_len]
    return ("…" if start > 0 else "") + ausschnitt.strip() + ("…" if start + max_len < len(satz) else "")


def select_candidates(
    item: ChecklistItem, paragraphs: list[tuple[str, int]], k: int = 3
) -> list[tuple[str, int]]:
    """Top-k Absätze nach gewichteter Stichwort-Überlappung (billige Vorauswahl).

    Lange, spezifische Begriffe (Komposita) zählen doppelt — ein Absatz, der
    'Abschreibungsdauer/-methode' abdeckt, schlägt einen, der nur beiläufig
    'Firmenwert' erwähnt."""
    kws = _keywords(item)
    scored: list[tuple[float, int]] = []
    for idx, (text, _page) in enumerate(paragraphs):
        low = text.lower()
        compact = _norm_compact(text)
        hits = sum((2.0 if len(w) >= 10 else 1.0)
                   for w in kws if _kw_hit(w, low, compact))
        if hits:
            scored.append((hits + min(len(text), 800) / 8000.0, idx))
    scored.sort(reverse=True)
    return [paragraphs[i] for _s, i in scored[:k]]


# ---------------------------------------------------------------------------
# Lokaler Ollama-Client (nur localhost!)
# ---------------------------------------------------------------------------
class LocalLLM:
    """Minimaler Client für die lokale Ollama-API. Verweigert Nicht-localhost."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL,
                 timeout: int = 300):
        # Vertraulichkeits-Guard: URL echt PARSEN (nicht startswith – sonst per
        # 'http://127.0.0.1:11434@fremd.example' umgehbar). Host MUSS localhost
        # sein, keine userinfo, Schema http.
        from urllib.parse import urlsplit
        sp = urlsplit(base_url.rstrip("/"))
        if (sp.scheme != "http"
                or sp.hostname not in ("127.0.0.1", "localhost", "::1")
                or sp.username or sp.password):
            raise ValueError(
                "Vertraulichkeit: LocalLLM erlaubt ausschließlich http://localhost "
                f"bzw. 127.0.0.1 (erhalten: {base_url!r}). Kein Datenversand nach außen."
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/api/tags", timeout=3) as r:
                names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
            return any(n == self.model or n.startswith(self.model + ":") for n in names)
        except Exception:
            return False

    def generate_json(self, prompt: str, num_predict: int = 120) -> Optional[dict]:
        body = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": num_predict},
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/api/generate", body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = json.loads(r.read()).get("response", "")
            return json.loads(resp)
        except Exception:
            logger.exception("Ollama-Aufruf fehlgeschlagen")
            return None


# ---------------------------------------------------------------------------
# Prompt + Bewertung
# ---------------------------------------------------------------------------
_PROMPT = """Du bist Assistent eines Wirtschaftsprüfers (Österreich, UGB). Aufgabe: Prüfe, ob einer der Absätze die geforderte Anhangangabe enthält.

WICHTIGE REGELN:
- Eine Angabe gilt auch dann als ENTHALTEN, wenn der Betrag 0,00 ist oder als Negativaussage formuliert wird ("keine ...", "EUR 0,00").
- Wähle NUR einen Absatz, der die geforderte Angabe SELBST enthält – NICHT einen, der lediglich dieselben Begriffe in anderem Zusammenhang erwähnt.
- Wenn kein Absatz die Angabe enthält: "nein".
- Wenn die Absätze zur Beurteilung nicht ausreichen: "unklar".

BEISPIEL:
Prüfpunkt: Angabe der Haftungsverhältnisse.
Absatz [1]: "Im Geschäftsjahr sind keine Haftungsverhältnisse auszuweisen."
Richtige Antwort: {{"erfuellt": "ja", "absatz": 1, "fehlt_konkret": null, "begruendung": "Negativaussage ist eine Angabe"}}

BEISPIEL 2 (Angabe fehlt):
Prüfpunkt: Angabe des Gesamtbetrags der Verbindlichkeiten mit Restlaufzeit über fünf Jahren.
Absätze enthalten dazu nichts.
Richtige Antwort: {{"erfuellt": "nein", "absatz": null, "fehlt_konkret": "Gesamtbetrag der Verbindlichkeiten mit Restlaufzeit über 5 Jahren nicht angegeben", "begruendung": "keine entsprechende Textstelle"}}

PRÜFPUNKT (KPMG): {frage} ({ugb})

KANDIDATEN-ABSÄTZE:
{absaetze}

Antworte NUR mit JSON: {{"erfuellt": "ja"|"nein"|"unklar", "absatz": <Nummer oder null>, "fehlt_konkret": <bei "nein": WAS KONKRET fehlt, sachlich in max 20 Worten; sonst null>, "begruendung": "<max 15 Worte>"}}"""


@dataclass
class LLMAssessment:
    erfuellt: str                    # "ja" | "nein" | "unklar"
    absatz_index: Optional[int]      # 0-basiert in der Kandidatenliste
    begruendung: str
    fehlt_konkret: str = ""          # bei "nein": WAS konkret fehlt


def build_prompt(item: ChecklistItem, candidates: list[tuple[str, int]]) -> str:
    absaetze = "\n".join(
        f"[{i}] {text[:400]}" for i, (text, _p) in enumerate(candidates, start=1))
    return _PROMPT.format(
        frage=item.description.strip(),
        ugb="; ".join(item.ugb_references) or "UGB",
        absaetze=absaetze or "[1] (keine Kandidaten gefunden)",
    )


def _parse_assessment(data: Optional[dict], n_candidates: int) -> Optional[LLMAssessment]:
    if not isinstance(data, dict):
        return None
    erf = str(data.get("erfuellt", "")).strip().lower()
    if erf not in ("ja", "nein", "unklar"):
        return None
    idx = data.get("absatz")
    absatz_index: Optional[int] = None
    if isinstance(idx, (int, float)) and 1 <= int(idx) <= n_candidates:
        absatz_index = int(idx) - 1
    if erf == "ja" and absatz_index is None:
        erf = "unklar"   # "ja" ohne belastbare Fundstelle ist nicht belastbar
    fehlt = data.get("fehlt_konkret")
    fehlt = str(fehlt).strip()[:250] if fehlt not in (None, "", "null") else ""
    return LLMAssessment(erf, absatz_index, str(data.get("begruendung", ""))[:200], fehlt)


_STATUS_MAP = {
    "ja": ComplianceStatus.COMPLIANT,
    "nein": ComplianceStatus.NOT_COMPLIANT,
    "unklar": ComplianceStatus.NOT_ASSESSABLE,
}


def apply_heuristic_fundstellen(
    result: ReviewResult,
    checklist: Checklist,
    paragraphs: list[tuple[str, int]],
) -> dict:
    """Ohne LLM: je relevantem Prüfpunkt die beste FUNDSTELLE (Heuristik) setzen
    und ein EHRLICHES Verdikt vergeben.

    Council-Linie (Stichwort-Matcher ist als Auswähler gut fürs Zitat, aber der
    LLM ist als Ja/Nein-Entscheider unzuverlässig): daher KEIN geratenes „Ja".
      - Kandidat vorhanden  -> Offen (NOT_ASSESSABLE) + Fundstelle; der Prüfer
        bestätigt „Ja" per Dropdown.
      - Kein Kandidat UND die spezifischen (langen) Pflicht-Begriffe kommen
        NIRGENDS im Anhang vor -> Fehlt (bewiesene Abwesenheit), konkret benannt.
      - sonst -> Offen.
    NICHT ANWENDBAR (Relevanzfilter) bleibt unberührt.
    """
    by_id = {it.item_id: it for it in checklist.items}
    full = " ".join(t for t, _ in paragraphs)
    doc_low, doc_compact = full.lower(), _norm_compact(full)
    offen = fehlt = 0

    for f in result.findings:
        if f.status == ComplianceStatus.NOT_APPLICABLE:
            continue
        item = by_id.get(f.checklist_item_id)
        if item is None:
            continue

        cands = select_candidates(item, paragraphs, k=1)
        if cands:
            text, page = cands[0]
            zitat = _best_sentence(text, item)
            # Trifft KEIN spezifischer Begriff der Prüffrage das Zitat, ist die
            # Fundstelle geraten -> lieber keine Fundstelle als eine irreführende.
            spez = [w for w in _keywords(item) if len(w) >= 10]
            trifft = (not spez) or any(
                _kw_hit(w, zitat.lower(), _norm_compact(zitat)) for w in spez)
            f.status = ComplianceStatus.NOT_ASSESSABLE          # -> "Offen"
            f.technical_reasoning = ""
            f.missing_elements = []
            f.evidence = [EvidenceItem(
                section_id="heuristik", section_title="Anhang",
                quote=zitat, page_number=page,
                relevance_score=1.0, is_supporting=False,
            )] if trifft else []
            offen += 1
            continue

        # kein Kandidat: nur dann "Fehlt", wenn spezifische Begriffe belegbar fehlen
        spec = [w for w in _keywords(item) if len(w) >= 10]
        proven_absent = bool(spec) and not any(_kw_hit(w, doc_low, doc_compact) for w in spec)
        if proven_absent:
            f.status = ComplianceStatus.NOT_COMPLIANT           # -> "Fehlt"
            f.evidence = []
            f.missing_elements = [item.description.strip()[:200]]
            f.technical_reasoning = ""
            fehlt += 1
        else:
            f.status = ComplianceStatus.NOT_ASSESSABLE          # -> "Offen"
            f.evidence = []
            f.missing_elements = []
            offen += 1

    result._update_statistics()
    return {"offen": offen, "fehlt": fehlt}


_BINAER_PROMPT = """Du bist Assistent eines Wirtschaftsprüfers (Österreich, UGB).

FRAGE: Enthält der folgende Textabschnitt aus dem Anhang die unten geforderte Angabe?

REGELN:
- Eine Angabe gilt auch als ENTHALTEN, wenn der Betrag 0,00 ist oder sie als Negativaussage formuliert ist ("keine ...", "EUR 0,00").
- Antworte "ja" NUR, wenn der Abschnitt die Angabe SELBST macht – nicht, wenn er nur ähnliche Begriffe erwähnt.
- Bei "ja" MUSST du einen wörtlichen Satzteil aus dem Abschnitt als Beleg zitieren (exakt abschreiben).
- Reicht der Abschnitt zur Beurteilung nicht: "unklar".

GEFORDERTE ANGABE ({ugb}):
{frage}

TEXTABSCHNITT AUS DEM ANHANG:
{absatz}

Antworte NUR mit JSON:
{{"enthalten": "ja"|"nein"|"unklar", "beleg": "<wörtliches Zitat aus dem Abschnitt, sonst null>", "fehlt_konkret": "<bei nein: was genau fehlt, max 15 Worte, sonst null>"}}"""


def build_binaer_prompt(item: ChecklistItem, absatz: str) -> str:
    """Prompt für die BINÄRE Ja/Nein-Frage zu GENAU EINEM Absatz.

    Kein Auswählen aus mehreren Kandidaten -> der beim Auswählen belegte
    Positions-Bias des lokalen Modells kann strukturell nicht auftreten.
    """
    return _BINAER_PROMPT.format(
        frage=item.description.strip(),
        ugb="; ".join(item.ugb_references) or "UGB",
        absatz=absatz[:1200],
    )


def _beleg_ist_echt(beleg: str, absatz: str) -> bool:
    """Halluzinationsschutz: das Zitat muss wirklich im Abschnitt stehen."""
    b = _norm_compact(beleg or "")
    return len(b) >= 15 and b in _norm_compact(absatz)


def refine_binaer(
    result: ReviewResult,
    checklist: Checklist,
    paragraphs: list[tuple[str, int]],
    llm: Optional[LocalLLM] = None,
    max_seconds: Optional[float] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    answer_cache: Optional[dict] = None,
) -> dict:
    """Entscheidet offene Prüfpunkte mit dem LOKALEN Modell (Ja/Nein je Absatz).

    Voraussetzung: `apply_heuristic_fundstellen()` lief bereits – die Fundstelle
    stammt IMMER aus der Heuristik (nachweislich ~91-95 % treffsicher), das
    Modell bewertet sie nur.

    Sicherungen gegen den bekannten Ja-Bias:
      * "ja" nur mit wörtlichem Beleg, der im Absatz nachweisbar ist,
      * und der Beleg muss einen spezifischen Fachbegriff der Prüffrage enthalten.
    Andernfalls bleibt der Punkt "Offen". Fällt das Modell aus, bleibt ebenfalls
    alles beim Heuristik-Ergebnis – die Prüfung kippt nie.
    """
    llm = llm or LocalLLM()
    if not llm.is_available():
        logger.info("Lokales Modell nicht verfügbar – Heuristik-Ergebnis bleibt.")
        return {"ja": 0, "fehlt": 0, "offen": 0, "ki": None, "verbleibend": 0}

    by_id = {it.item_id: it for it in checklist.items}
    todo = [f for f in result.findings
            if f.status not in (ComplianceStatus.NOT_APPLICABLE,)]
    t0 = time.time()
    zahl = {"ja": 0, "fehlt": 0, "offen": 0}
    erledigt = 0

    for f in todo:
        item = by_id.get(f.checklist_item_id)
        if item is None:
            continue
        cands = select_candidates(item, paragraphs, k=1)
        if not cands:
            zahl["offen"] += 1
            continue
        absatz, page = cands[0]

        raw = answer_cache.get(item.item_id) if answer_cache is not None else None
        if raw is None:
            if max_seconds is not None and time.time() - t0 > max_seconds:
                break
            raw = llm.generate_json(build_binaer_prompt(item, absatz), num_predict=180)
            if answer_cache is not None and raw is not None:
                answer_cache[item.item_id] = raw
        if not isinstance(raw, dict):
            zahl["offen"] += 1
            continue

        antwort = str(raw.get("enthalten", "")).strip().lower()
        beleg = str(raw.get("beleg") or "")
        spez = [w for w in _keywords(item) if len(w) >= 10]

        if antwort == "ja":
            beleg_ok = _beleg_ist_echt(beleg, absatz)
            begriff_ok = (not spez) or any(
                _kw_hit(w, beleg.lower(), _norm_compact(beleg)) for w in spez)
            if beleg_ok and begriff_ok:
                f.status = ComplianceStatus.COMPLIANT               # -> "Ja"
                f.technical_reasoning = ""
                f.evidence = [EvidenceItem(
                    section_id="ki", section_title="Anhang", quote=beleg[:300],
                    page_number=page, relevance_score=1.0, is_supporting=True)]
                zahl["ja"] += 1
            else:
                zahl["offen"] += 1                                   # bleibt Offen
        elif antwort == "nein":
            f.status = ComplianceStatus.NOT_COMPLIANT               # -> "Fehlt"
            f.missing_elements = [str(raw.get("fehlt_konkret") or "").strip()
                                  or item.description.strip()[:200]]
            f.evidence = []
            f.technical_reasoning = ""
            zahl["fehlt"] += 1
        else:
            zahl["offen"] += 1

        erledigt += 1
        if progress:
            progress(erledigt, len(todo))

    result._update_statistics()
    return {**zahl, "ki": llm.model, "verbleibend": len(todo) - erledigt}


def refine_findings(
    result: ReviewResult,
    checklist: Checklist,
    paragraphs: list[tuple[str, int]],
    llm: Optional[LocalLLM] = None,
    max_seconds: Optional[float] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    answer_cache: Optional[dict] = None,
) -> dict:
    """Verfeinert alle ANWENDBAREN Findings mit dem lokalen Modell.

    NICHT ANWENDBAR bleibt unberührt (Relevanz-Filter hat Vorrang). Bei
    Zeitüberschreitung/Fehlern behalten die restlichen Findings ihr
    bisheriges (Stichwort-)Ergebnis — die Prüfung kippt nie.

    answer_cache (optional): dict item_id -> Roh-Antwort (JSON-dict) des
    Modells. Bereits beantwortete Punkte werden nicht erneut angefragt; neue
    Antworten werden eingetragen. Damit ist ein langer Lauf in Etappen
    wiederaufnehmbar.
    """
    llm = llm or LocalLLM()
    if not llm.is_available():
        logger.info("Lokale KI nicht verfügbar – Stichwort-Ergebnis bleibt bestehen.")
        return {"verfeinert": 0, "uebersprungen": len(result.findings), "ki": None}

    by_id = {it.item_id: it for it in checklist.items}
    todo = [f for f in result.findings if f.status != ComplianceStatus.NOT_APPLICABLE]
    t0 = time.time()
    done = 0

    for f in todo:
        item = by_id.get(f.checklist_item_id)
        if item is None:
            continue
        candidates = select_candidates(item, paragraphs)

        raw = None
        if answer_cache is not None and item.item_id in answer_cache:
            raw = answer_cache[item.item_id]
            # Alt-Format: "nein" ohne konkrete Fehlt-Angabe -> neu fragen,
            # damit die klare "was fehlt konkret"-Aussage vorhanden ist.
            if (isinstance(raw, dict)
                    and str(raw.get("erfuellt", "")).lower() == "nein"
                    and not str(raw.get("fehlt_konkret") or "").strip()):
                raw = None
        if raw is None:
            if max_seconds is not None and time.time() - t0 > max_seconds:
                logger.info("Zeitbudget erreicht: %d/%d Prüfpunkte verfeinert.", done, len(todo))
                break
            raw = llm.generate_json(build_prompt(item, candidates))
            if answer_cache is not None and raw is not None:
                answer_cache[item.item_id] = raw

        assessment = _parse_assessment(raw, len(candidates))
        if assessment is None:
            continue   # Modellfehler -> Stichwort-Ergebnis behalten

        f.status = _STATUS_MAP[assessment.erfuellt]
        f.technical_reasoning = f"KI: {assessment.begruendung}".strip().rstrip(".") + "."
        f.missing_elements = []
        if assessment.erfuellt == "nein":
            # konkrete Benennung, WAS fehlt (Fallback: die Prüffrage selbst)
            f.missing_elements = [assessment.fehlt_konkret
                                  or item.description.strip()[:200]]
        f.evidence = []
        if assessment.absatz_index is not None:
            text, page = candidates[assessment.absatz_index]
            f.add_evidence(EvidenceItem(
                section_id="llm", section_title="Anhang",
                quote=_best_sentence(text, item), page_number=page,
                relevance_score=1.0, is_supporting=(assessment.erfuellt == "ja"),
            ))
        done += 1
        if progress:
            progress(done, len(todo))

    result._update_statistics()
    return {"verfeinert": done, "uebersprungen": len(todo) - done, "ki": llm.model}

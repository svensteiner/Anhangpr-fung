"""
Concrete Example: Source-Governed Knowledge Workflow

This module demonstrates the complete source management workflow:
1. Storing a statutory source (UGB § 238)
2. Storing an interpretative source (IWP commentary excerpt)
3. Linking both to the Anteilsbesitz rule
4. Generating proper citations

This is NOT production code - it is documentation-as-code.
"""

from datetime import date
from pathlib import Path

from .classification import SourceAuthority, StoragePermission
from .metadata import SourceMetadata, create_source_metadata
from .storage import SourceStorageManager, STORAGE_ROOT
from .registry import SourceRegistry, SourceReference, link_source_to_rule
from .citation import CitationGenerator, format_source_block_for_protocol


# =============================================================================
# EXAMPLE 1: STATUTORY LAW SOURCE (§ 238 UGB)
# =============================================================================

STATUTORY_SOURCE_CONTENT = """
§ 238 UGB - Inhalt des Anhangs

(1) In den Anhang sind außer den nach anderen Bestimmungen vorgeschriebenen
Angaben folgende Angaben aufzunehmen:

[...]

2. Name und Sitz der Unternehmen, an denen die Gesellschaft mindestens
   mit einem Fünftel beteiligt ist, unter Angabe des Anteils am Kapital
   sowie des Eigenkapitals und des Ergebnisses des letzten Geschäftsjahrs
   dieser Unternehmen, für das ein Jahresabschluss vorliegt;

[...]

(2) Die in Abs. 1 Z 2 vorgeschriebenen Angaben brauchen nicht gemacht
zu werden, soweit sie für die Darstellung der Vermögens-, Finanz- und
Ertragslage der Gesellschaft von untergeordneter Bedeutung sind.
"""

STATUTORY_SOURCE_METADATA = {
    "source_id": "UGB_238_2024",
    "authority": SourceAuthority.STATUTORY_LAW,
    "title": "§ 238 UGB - Inhalt des Anhangs",
    "legal_reference": "§ 238 Abs 1 Z 2, Abs 2 UGB",
    "bgbl_reference": "BGBl. Nr. 1/2005 idF BGBl. I Nr. 120/2023",
    "effective_date": date(2005, 1, 1),
    "retrieval_date": date(2024, 3, 15),
    "retrieval_url": "https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer=10001702",
    "retrieval_method": "manual",
    "content_summary": "Gesetzliche Grundlage für Anhangangaben zu Anteilsbesitz. "
                       "Definiert Mindestbeteiligungsquote (20%) und Pflichtangaben "
                       "(Name, Sitz, Anteil, Eigenkapital, Ergebnis).",
    "storage_permission": StoragePermission.FULL_TEXT,
    "storage_legal_basis": "Amtliche Werke sind gemeinfrei (§ 7 UrhG)",
    "copyright_status": "public_domain",
    "verified_by": "Abgleich mit RIS-Datenbank",
    "verification_date": date(2024, 3, 15),
    "verification_method": "Direkter Abruf aus RIS",
}


# =============================================================================
# EXAMPLE 2: INTERPRETATIVE SOURCE (IWP Commentary Excerpt)
# =============================================================================

# NOTE: This is a SUMMARY, not the actual copyrighted text
# Actual IWP content may NOT be stored in full

INTERPRETATIVE_SOURCE_SUMMARY = """
[ZUSAMMENFASSUNG - nicht wörtliches Zitat]

Das IWP vertritt die Auffassung, dass bei der Anwendung der
Wesentlichkeitsgrenze des § 238 Abs 2 UGB ein strenger Maßstab
anzulegen ist. Die Ausnahme sollte nur in Fällen angewendet werden,
in denen die Beteiligung sowohl quantitativ als auch qualitativ
für die Vermögens-, Finanz- und Ertragslage ohne Bedeutung ist.

Bei Beteiligungen über 25% ist regelmäßig von Wesentlichkeit auszugehen,
da hier typischerweise eine Sperrminorität besteht.
"""

INTERPRETATIVE_SOURCE_METADATA = {
    "source_id": "IWP_FG_ANHANG_2022_RZ145",
    "authority": SourceAuthority.CHAMBER_PUBLICATION,
    "title": "Fachgutachten zur Anhangberichterstattung",
    "publisher": "IWP (Institut Österreichischer Wirtschaftsprüfer)",
    "publication_date": date(2022, 6, 1),
    "retrieval_date": date(2024, 3, 15),
    "retrieval_method": "manual",
    "content_summary": "Interpretationshilfe zur Wesentlichkeitsbeurteilung bei "
                       "Anteilsbesitz-Angaben. Vertritt strengen Maßstab bei "
                       "Anwendung der Ausnahme des § 238 Abs 2 UGB.",
    "excerpt_pages": "Rz. 145-148",
    "storage_permission": StoragePermission.SUMMARY_ONLY,
    "storage_legal_basis": "Zitatrecht (§ 42f UrhG) für fachliche Auseinandersetzung",
    "copyright_status": "fair_use",
    "content_type": "summary",
}


# =============================================================================
# EXPECTED SOURCE LINKING TO RULE
# =============================================================================

EXPECTED_SOURCE_LINKS = [
    # Link 1: Statutory basis
    {
        "source_id": "UGB_238_2024",
        "authority": SourceAuthority.STATUTORY_LAW,
        "reference_type": "legal_basis",
        "rule_id": "UGB_238_1_Z2_ANTEILSBESITZ",
        "rule_component": "applicability",
        "specific_location": "§ 238 Abs 1 Z 2 UGB",
        "interpretation_confidence": "definitive",
        "interpretation_caveat": None,
    },

    # Link 2: Threshold definition (also statutory)
    {
        "source_id": "UGB_238_2024",
        "authority": SourceAuthority.STATUTORY_LAW,
        "reference_type": "threshold",
        "rule_id": "UGB_238_1_Z2_ANTEILSBESITZ",
        "rule_component": "threshold_20_percent",
        "specific_location": "§ 238 Abs 1 Z 2 UGB ('mindestens einem Fünftel')",
        "interpretation_confidence": "definitive",
        "interpretation_caveat": None,
    },

    # Link 3: Required elements (statutory)
    {
        "source_id": "UGB_238_2024",
        "authority": SourceAuthority.STATUTORY_LAW,
        "reference_type": "legal_basis",
        "rule_id": "UGB_238_1_Z2_ANTEILSBESITZ",
        "rule_component": "required_elements",
        "specific_location": "§ 238 Abs 1 Z 2 UGB",
        "interpretation_confidence": "definitive",
        "interpretation_caveat": None,
    },

    # Link 4: Materiality interpretation (IWP)
    {
        "source_id": "IWP_FG_ANHANG_2022_RZ145",
        "authority": SourceAuthority.CHAMBER_PUBLICATION,
        "reference_type": "interpretation",
        "rule_id": "UGB_238_1_Z2_ANTEILSBESITZ",
        "rule_component": "materiality_exception",
        "specific_location": "Rz. 145-148",
        "interpretation_confidence": "consensus",
        "interpretation_caveat": "Berufsständische Auffassung, nicht rechtsverbindlich",
    },
]


# =============================================================================
# EXPECTED CITATION OUTPUT
# =============================================================================

EXPECTED_CITATIONS = {
    "statutory_citation": "Gemäß § 238 Abs 1 Z 2 UGB",

    "interpretative_citation": (
        "Nach IWP, Fachgutachten zur Anhangberichterstattung (2022), Rz. 145-148 "
        "[berufsständische Auffassung]"
    ),

    "combined_for_rule": """
#### Quellenangaben

**Rechtliche Grundlage:**
- Gemäß § 238 Abs 1 Z 2 UGB

**Interpretationsquellen:**
- Nach IWP, Fachgutachten zur Anhangberichterstattung (2022), Rz. 145-148 [berufsständische Auffassung]

---
_Dieses Tool ersetzt nicht die rechtliche oder fachliche Beratung. Alle Aussagen sind als Prüfungsunterstützung zu verstehen._
""",
}


# =============================================================================
# DEMONSTRATION FUNCTION
# =============================================================================

def demonstrate_source_workflow(storage_root: Path = STORAGE_ROOT) -> dict:
    """
    Demonstrate the complete source-governed workflow.

    Returns a dictionary documenting each step.
    """
    results = {
        "steps": [],
        "success": True,
        "errors": [],
    }

    # Initialize storage
    storage = SourceStorageManager(storage_root)
    registry = SourceRegistry(storage_root)
    citation_gen = CitationGenerator()

    # Step 1: Store statutory source
    try:
        statutory_meta = create_source_metadata(**STATUTORY_SOURCE_METADATA)
        success, msg, path = storage.store_source(statutory_meta, STATUTORY_SOURCE_CONTENT)
        results["steps"].append({
            "step": "1. Store statutory source",
            "success": success,
            "message": msg,
            "path": str(path) if path else None,
        })
    except ValueError as e:
        results["steps"].append({
            "step": "1. Store statutory source",
            "success": False,
            "error": str(e),
        })
        results["errors"].append(str(e))

    # Step 2: Store interpretative source (summary only!)
    try:
        interp_meta = create_source_metadata(**INTERPRETATIVE_SOURCE_METADATA)
        success, msg, path = storage.store_source(interp_meta, INTERPRETATIVE_SOURCE_SUMMARY)
        results["steps"].append({
            "step": "2. Store interpretative source (summary)",
            "success": success,
            "message": msg,
            "path": str(path) if path else None,
        })
    except ValueError as e:
        results["steps"].append({
            "step": "2. Store interpretative source",
            "success": False,
            "error": str(e),
        })
        results["errors"].append(str(e))

    # Step 3: Link sources to rule
    for link_data in EXPECTED_SOURCE_LINKS:
        try:
            ref = link_source_to_rule(
                storage_root=storage_root,
                **link_data
            )
            results["steps"].append({
                "step": f"3. Link {link_data['source_id']} to rule",
                "success": True,
                "reference_type": link_data["reference_type"],
                "rule_component": link_data["rule_component"],
            })
        except Exception as e:
            results["steps"].append({
                "step": f"3. Link {link_data['source_id']} to rule",
                "success": False,
                "error": str(e),
            })
            results["errors"].append(str(e))

    # Step 4: Generate citations
    rule_id = "UGB_238_1_Z2_ANTEILSBESITZ"
    refs = registry.get_sources_for_rule(rule_id)

    # Build metadata lookup
    metadata_lookup = {}
    for ref in refs:
        meta = storage.get_source_metadata(ref.source_id)
        if meta:
            metadata_lookup[ref.source_id] = meta

    citation_block = format_source_block_for_protocol(rule_id, refs, metadata_lookup)
    results["steps"].append({
        "step": "4. Generate citation block",
        "success": True,
        "output": citation_block,
    })

    # Step 5: Validate rule sourcing
    is_valid, issues = registry.validate_rule_sourcing(rule_id)
    results["steps"].append({
        "step": "5. Validate rule sourcing",
        "success": is_valid,
        "issues": issues,
    })

    # Step 6: Generate audit trail
    audit_trail = registry.generate_audit_trail(rule_id)
    results["steps"].append({
        "step": "6. Generate audit trail",
        "success": True,
        "output": audit_trail,
    })

    results["success"] = len(results["errors"]) == 0
    return results


# =============================================================================
# WHAT THE SYSTEM PREVENTS
# =============================================================================

PREVENTED_ACTIONS = """
## Was das System VERHINDERT

### 1. Speicherung urheberrechtlich geschützter Volltexte
```python
# DIES WÜRDE FEHLSCHLAGEN:
commentary_full_text = "..." # 5000 Wörter aus Doralt-Kommentar
storage.store_source(metadata, commentary_full_text)
# -> ValueError: Maximale Wortanzahl überschritten: 5000 > 100
```

### 2. Verwendung unverifizierter Quellen
```python
# DIES WÜRDE FEHLSCHLAGEN:
metadata = create_source_metadata(
    source_id="FORUM_POST_2023",
    authority=SourceAuthority.UNVERIFIED,
    title="Forum-Beitrag",
    ...
)
# -> ValueError: UNVERIFIED sources may not be stored
```

### 3. Zitate ohne Quellenangabe
```python
# Das System erzwingt Quellenangaben für alle Regeln
is_valid, issues = registry.validate_rule_sourcing("MY_RULE")
# -> (False, ["Keine Quellen dokumentiert"])
```

### 4. Autoritative Aussagen zu nicht-autoritativen Quellen
```python
# Die Zitierfunktion fügt automatisch Caveats hinzu:
format_citation(iwp_metadata, include_caveat=True)
# -> "Nach IWP, ... [berufsständische Auffassung]"
```

### 5. Interpretation ohne Kennzeichnung
```python
# Tool-eigene Ableitungen werden IMMER markiert:
format_citation(tool_derived_metadata)
# -> "Tool-interne Ableitung: ... [NICHT AUTORITATIV - ersetzt nicht fachliche Beurteilung]"
```
"""


# =============================================================================
# INTEGRATION NOTES
# =============================================================================

INTEGRATION_NOTES = """
## Integration in bestehende Architektur

### 1. Bei Regel-Definition
Jede neue Regel MUSS vor Aktivierung:
- Mindestens eine STATUTORY_LAW-Quelle verlinken
- Alle Interpretationen mit Quellen belegen
- validate_rule_sourcing() bestehen

### 2. Bei Report-Generierung
Der MarkdownReportGenerator MUSS:
- format_source_block_for_protocol() für jede bewertete Regel aufrufen
- Quellenangaben im Protokoll ausgeben
- Caveats entsprechend der Quellen-Autorität hinzufügen

### 3. Bei Updates
Wenn eine Quelle aktualisiert wird:
- Neue source_id mit Versionsnummer
- Alte Quelle als superseded_by markieren
- Alle verlinkten Regeln prüfen

### 4. Bei Audits
Das System ermöglicht:
- Vollständige Rückverfolgbarkeit jeder Tool-Aussage
- Nachvollziehbare Quellenhistorie
- Integritätsprüfung gespeicherter Inhalte
"""

"""
Source Registry and Rule Linking.

Manages the bidirectional relationship between sources and rules:
- Which sources support which rules
- Which rules cite which sources
- Traceability for audit purposes
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Literal
from pathlib import Path
import json

from .classification import SourceAuthority, CitationRequirement


@dataclass
class SourceReference:
    """
    A reference from a rule to a source.

    This creates an explicit, auditable link between tool logic
    and its supporting documentation.
    """

    # What is being cited
    source_id: str
    # Reference to SourceMetadata.source_id

    authority: SourceAuthority
    # Authority level of the source

    # How it is being used
    reference_type: Literal[
        "legal_basis",      # Source provides legal foundation
        "interpretation",   # Source provides interpretative guidance
        "example",          # Source provides illustrative example
        "threshold",        # Source defines numeric thresholds
        "terminology",      # Source defines terms used
        "exclusion",        # Source defines what is NOT required
    ]

    # Where in the rule it is used
    rule_id: str
    # ID of the rule using this source

    rule_component: str
    # Which part of the rule: "applicability", "required_elements", "thresholds", etc.

    # Citation details
    specific_location: Optional[str] = None
    # Page, paragraph, or section reference
    # Example: "§ 238 Abs 1 Z 2" or "Rz. 145"

    quote_excerpt: Optional[str] = None
    # Brief excerpt if permitted (< 50 words for most sources)

    # Confidence and limitations
    interpretation_confidence: Literal["definitive", "consensus", "disputed", "tool_derived"] = "tool_derived"
    # How certain is this interpretation?

    interpretation_caveat: Optional[str] = None
    # Any limitations or caveats

    # Tracking
    linked_date: date = field(default_factory=date.today)
    linked_by: Optional[str] = None


class SourceRegistry:
    """
    Central registry managing source-to-rule relationships.

    Provides:
    - Forward lookup: rule_id -> list of sources
    - Reverse lookup: source_id -> list of rules
    - Audit trail of all citations
    """

    def __init__(self, storage_root: Path):
        self.storage_root = storage_root
        self.registry_file = storage_root / "metadata" / "source_rule_links.json"
        self._links: dict[str, list[SourceReference]] = {}
        self._load()

    def _load(self) -> None:
        """Load existing links from file."""
        if self.registry_file.exists():
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            for rule_id, refs in data.get("links", {}).items():
                self._links[rule_id] = [
                    self._dict_to_reference(r) for r in refs
                ]

    def _save(self) -> None:
        """Persist links to file."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "last_updated": date.today().isoformat(),
            "links": {
                rule_id: [self._reference_to_dict(r) for r in refs]
                for rule_id, refs in self._links.items()
            }
        }
        self.registry_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def _reference_to_dict(self, ref: SourceReference) -> dict:
        """Convert reference to dictionary."""
        return {
            "source_id": ref.source_id,
            "authority": ref.authority.value,
            "reference_type": ref.reference_type,
            "rule_id": ref.rule_id,
            "rule_component": ref.rule_component,
            "specific_location": ref.specific_location,
            "quote_excerpt": ref.quote_excerpt,
            "interpretation_confidence": ref.interpretation_confidence,
            "interpretation_caveat": ref.interpretation_caveat,
            "linked_date": ref.linked_date.isoformat(),
            "linked_by": ref.linked_by,
        }

    def _dict_to_reference(self, data: dict) -> SourceReference:
        """Convert dictionary to reference."""
        return SourceReference(
            source_id=data["source_id"],
            authority=SourceAuthority(data["authority"]),
            reference_type=data["reference_type"],
            rule_id=data["rule_id"],
            rule_component=data["rule_component"],
            specific_location=data.get("specific_location"),
            quote_excerpt=data.get("quote_excerpt"),
            interpretation_confidence=data.get("interpretation_confidence", "tool_derived"),
            interpretation_caveat=data.get("interpretation_caveat"),
            linked_date=date.fromisoformat(data["linked_date"]) if data.get("linked_date") else date.today(),
            linked_by=data.get("linked_by"),
        )

    def add_link(self, reference: SourceReference) -> None:
        """Add a source-to-rule link."""
        if reference.rule_id not in self._links:
            self._links[reference.rule_id] = []

        # Check for duplicates
        existing = [r for r in self._links[reference.rule_id]
                    if r.source_id == reference.source_id
                    and r.rule_component == reference.rule_component]
        if existing:
            # Update existing
            self._links[reference.rule_id] = [
                r for r in self._links[reference.rule_id]
                if not (r.source_id == reference.source_id
                        and r.rule_component == reference.rule_component)
            ]

        self._links[reference.rule_id].append(reference)
        self._save()

    def get_sources_for_rule(self, rule_id: str) -> list[SourceReference]:
        """Get all sources supporting a rule."""
        return self._links.get(rule_id, [])

    def get_rules_for_source(self, source_id: str) -> list[SourceReference]:
        """Get all rules citing a source."""
        results = []
        for rule_id, refs in self._links.items():
            for ref in refs:
                if ref.source_id == source_id:
                    results.append(ref)
        return results

    def get_legal_basis_sources(self, rule_id: str) -> list[SourceReference]:
        """Get only the legal basis sources for a rule."""
        return [
            r for r in self._links.get(rule_id, [])
            if r.reference_type == "legal_basis"
        ]

    def get_interpretation_sources(self, rule_id: str) -> list[SourceReference]:
        """Get interpretative sources (not legal basis) for a rule."""
        return [
            r for r in self._links.get(rule_id, [])
            if r.reference_type in ("interpretation", "example", "terminology")
        ]

    def validate_rule_sourcing(self, rule_id: str) -> tuple[bool, list[str]]:
        """
        Validate that a rule has adequate source documentation.

        Returns: (is_adequate, list_of_issues)
        """
        issues = []
        refs = self._links.get(rule_id, [])

        if not refs:
            issues.append("Keine Quellen dokumentiert")
            return False, issues

        # Check for legal basis
        legal_basis = [r for r in refs if r.reference_type == "legal_basis"]
        if not legal_basis:
            issues.append("Keine rechtliche Grundlage dokumentiert")

        # Check authority levels
        has_statutory = any(r.authority == SourceAuthority.STATUTORY_LAW for r in refs)
        has_only_tool_derived = all(r.authority == SourceAuthority.TOOL_DERIVED for r in refs)

        if has_only_tool_derived:
            issues.append("Nur tool-interne Ableitungen, keine externen Quellen")

        # Check for high-authority sources
        high_authority = [r for r in refs if r.authority in (
            SourceAuthority.STATUTORY_LAW,
            SourceAuthority.OFFICIAL_GUIDANCE,
            SourceAuthority.CHAMBER_PUBLICATION,
        )]
        if not high_authority:
            issues.append("Keine hochautoritativen Quellen (Gesetz, Behörde, Kammer)")

        return len(issues) == 0, issues

    def generate_audit_trail(self, rule_id: str) -> str:
        """
        Generate a complete audit trail for a rule's source documentation.

        Returns formatted text suitable for audit working papers.
        """
        refs = self._links.get(rule_id, [])
        if not refs:
            return f"## Quellenaudit für {rule_id}\n\nKeine Quellen dokumentiert."

        lines = [
            f"## Quellenaudit für {rule_id}",
            "",
            f"Stand: {date.today().isoformat()}",
            f"Anzahl dokumentierter Quellen: {len(refs)}",
            "",
            "### Quellenübersicht",
            "",
        ]

        # Group by authority
        by_authority: dict[SourceAuthority, list[SourceReference]] = {}
        for ref in refs:
            if ref.authority not in by_authority:
                by_authority[ref.authority] = []
            by_authority[ref.authority].append(ref)

        for authority in SourceAuthority:
            if authority in by_authority:
                lines.append(f"#### {authority.value}")
                for ref in by_authority[authority]:
                    lines.append(f"- **{ref.source_id}**")
                    lines.append(f"  - Verwendung: {ref.reference_type}")
                    lines.append(f"  - Komponente: {ref.rule_component}")
                    if ref.specific_location:
                        lines.append(f"  - Fundstelle: {ref.specific_location}")
                    if ref.interpretation_caveat:
                        lines.append(f"  - Einschränkung: {ref.interpretation_caveat}")
                lines.append("")

        # Validation result
        is_valid, issues = self.validate_rule_sourcing(rule_id)
        lines.append("### Validierungsergebnis")
        lines.append("")
        if is_valid:
            lines.append("Quelldokumentation vollständig.")
        else:
            lines.append("**Mängel identifiziert:**")
            for issue in issues:
                lines.append(f"- {issue}")

        return "\n".join(lines)


def link_source_to_rule(
    source_id: str,
    authority: SourceAuthority,
    rule_id: str,
    reference_type: str,
    rule_component: str,
    storage_root: Path,
    **kwargs
) -> SourceReference:
    """
    Convenience function to create and register a source-to-rule link.

    Returns the created SourceReference.
    """
    reference = SourceReference(
        source_id=source_id,
        authority=authority,
        reference_type=reference_type,
        rule_id=rule_id,
        rule_component=rule_component,
        **kwargs
    )

    registry = SourceRegistry(storage_root)
    registry.add_link(reference)

    return reference

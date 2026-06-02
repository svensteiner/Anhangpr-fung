"""Enumeration types for Anhangsprüfer."""

from enum import Enum, auto


class ComplianceStatus(Enum):
    """
    Assessment status for each checklist item.

    These statuses are preliminary assessments requiring auditor validation.
    """
    COMPLIANT = "ENTSPRICHT"
    PARTIALLY_COMPLIANT = "TEILWEISE ENTSPRECHEND"
    NOT_COMPLIANT = "NICHT ENTSPRECHEND"
    NOT_ASSESSABLE = "NICHT BEURTEILBAR"
    NOT_APPLICABLE = "NICHT ANWENDBAR"
    PENDING_REVIEW = "PRÜFUNG AUSSTEHEND"

    def to_display_text(self) -> str:
        """Return display text with explanation."""
        explanations = {
            self.COMPLIANT: "Anforderung erfüllt (vorbehaltlich Prüfervalidierung)",
            self.PARTIALLY_COMPLIANT: "Anforderung teilweise erfüllt - manuelle Prüfung erforderlich",
            self.NOT_COMPLIANT: "Anforderung nicht erfüllt - Prüferfeststellung erforderlich",
            self.NOT_ASSESSABLE: "Automatische Beurteilung nicht möglich",
            self.NOT_APPLICABLE: "Nicht anwendbar auf diesen Abschluss",
            self.PENDING_REVIEW: "Wartet auf manuelle Prüfung",
        }
        return explanations.get(self, self.value)


class DocumentType(Enum):
    """Types of input documents."""
    NOTES = auto()          # Anhang document
    UGB_SOURCE = auto()     # UGB legal text
    CHECKLIST = auto()      # Audit checklist
    OTHER = auto()


class SectionType(Enum):
    """Types of sections in the notes document."""
    HEADER = auto()
    GENERAL_INFORMATION = auto()
    ACCOUNTING_POLICIES = auto()
    BALANCE_SHEET_DISCLOSURES = auto()
    INCOME_STATEMENT_DISCLOSURES = auto()
    OTHER_DISCLOSURES = auto()
    RELATED_PARTIES = auto()
    EVENTS_AFTER_REPORTING = auto()
    SIGNATURE = auto()
    UNKNOWN = auto()

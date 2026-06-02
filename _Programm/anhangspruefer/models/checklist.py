"""Checklist data models."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChecklistItem:
    """
    Represents a single item from the audit checklist.

    Each item corresponds to a specific disclosure requirement
    that must be verified in the notes document.
    """
    item_id: str
    category: str
    description: str
    ugb_references: list[str] = field(default_factory=list)
    search_keywords: list[str] = field(default_factory=list)
    applicable_to: list[str] = field(default_factory=list)  # e.g., ["alle", "mittelgroß", "groß"]
    is_mandatory: bool = True
    notes: str = ""

    # Markers for domain-specific knowledge requirements
    requires_professional_judgment: bool = True
    judgment_guidance: str = ""

    def get_search_patterns(self) -> list[str]:
        """
        Return patterns to search for in the notes document.

        NOTE: This is a simplified implementation. Domain experts should
        refine these patterns based on audit experience.
        """
        patterns = self.search_keywords.copy()

        # Add UGB paragraph numbers as search terms
        for ref in self.ugb_references:
            patterns.append(ref)
            # Also add common variations
            if ref.startswith("§"):
                patterns.append(ref.replace("§", "Paragraph"))

        return patterns


@dataclass
class Checklist:
    """
    Collection of checklist items organized by category.

    The checklist structure is derived from the PwC Anhangscheckliste
    or similar audit practice checklists.
    """
    name: str
    version: str
    items: list[ChecklistItem] = field(default_factory=list)
    categories: dict[str, list[str]] = field(default_factory=dict)  # category -> item_ids
    source_file: Optional[str] = None

    def add_item(self, item: ChecklistItem) -> None:
        """Add an item to the checklist."""
        self.items.append(item)
        if item.category not in self.categories:
            self.categories[item.category] = []
        self.categories[item.category].append(item.item_id)

    def get_item(self, item_id: str) -> Optional[ChecklistItem]:
        """Get a checklist item by ID."""
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None

    def get_items_by_category(self, category: str) -> list[ChecklistItem]:
        """Get all items in a category."""
        return [item for item in self.items if item.category == category]

    def get_items_for_ugb_reference(self, ugb_ref: str) -> list[ChecklistItem]:
        """Get all items referencing a specific UGB paragraph."""
        return [item for item in self.items if ugb_ref in item.ugb_references]

    def get_mandatory_items(self) -> list[ChecklistItem]:
        """Get all mandatory checklist items."""
        return [item for item in self.items if item.is_mandatory]

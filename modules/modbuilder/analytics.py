from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Mapping, Optional, Sequence, Tuple, TYPE_CHECKING

from modules.basemod_wrapper.cards import SimpleCardBlueprint

from .deck import DeckStatistics, build_statistics_from_cards

if TYPE_CHECKING:  # pragma: no cover - imported for type checkers only
    from .character import Character, CharacterDeckSnapshot


@dataclass(frozen=True)
class DeckAnalyticsRow:
    """Tabular summary for a single deck configuration."""

    label: str
    total_cards: int
    unique_cards: int
    duplicate_identifiers: Mapping[str, int]
    rarity_counts: Mapping[str, int]
    rarity_distribution: Mapping[str, float]

    def to_dict(self) -> Dict[str, object]:
        """Return a serialisable representation of the row."""

        return {
            "label": self.label,
            "total_cards": self.total_cards,
            "unique_cards": self.unique_cards,
            "duplicates": dict(self.duplicate_identifiers),
            "rarity_counts": dict(self.rarity_counts),
            "rarity_distribution": dict(self.rarity_distribution),
        }


@dataclass(frozen=True)
class DeckAnalytics:
    """Container bundling analytics rows for starter, unlockable and combined decks."""

    rows: Tuple[DeckAnalyticsRow, ...]
    rarity_targets: Mapping[str, float]

    def as_table(self) -> Tuple[Dict[str, object], ...]:
        """Return the analytics rows as dictionaries suitable for display tables."""

        return tuple(row.to_dict() for row in self.rows)

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        """Return the analytics payload encoded as JSON."""

        payload = {
            "rarity_targets": dict(self.rarity_targets),
            "rows": [row.to_dict() for row in self.rows],
        }
        return json.dumps(payload, indent=indent)

    def write_json(self, destination: Path | str, *, indent: Optional[int] = 2) -> Path:
        """Serialise the analytics payload into ``destination`` and return the path."""

        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(indent=indent), encoding="utf-8")
        return path

    @property
    def combined(self) -> DeckAnalyticsRow:
        """Return the aggregate row spanning starter and unlockable cards."""

        if not self.rows:
            raise ValueError("Deck analytics must include at least one row.")
        return self.rows[-1]

    def by_label(self) -> Mapping[str, DeckAnalyticsRow]:
        """Return a mapping of row labels to their analytic summaries."""

        return MappingProxyType({row.label: row for row in self.rows})


def build_deck_analytics(
    character: "Character",
    decks: "CharacterDeckSnapshot",
    *,
    rarity_targets: Mapping[str, float],
) -> DeckAnalytics:
    """Return :class:`DeckAnalytics` for ``character`` and ``decks``.

    The helper captures starter, unlockable and combined deck snapshots and
    exposes them as immutable dataclasses so automation tooling and plugins can
    enrich validation reports without touching lower level primitives.
    """

    rows = []
    starter_stats = decks.start_deck.statistics()
    rows.append(
        _row_from_statistics(
            label=f"{character.name} starter – {decks.start_deck.display_name}",
            statistics=starter_stats,
        )
    )

    if decks.unlockable_deck is not None:
        unlockable_stats = decks.unlockable_deck.statistics()
        rows.append(
            _row_from_statistics(
                label=f"{character.name} unlockables – {decks.unlockable_deck.display_name}",
                statistics=unlockable_stats,
            )
        )

    combined_stats = build_statistics_from_cards(decks.all_cards)
    rows.append(
        _row_from_statistics(
            label=f"{character.name} total card pool", statistics=combined_stats
        )
    )

    return DeckAnalytics(rows=tuple(rows), rarity_targets=MappingProxyType(dict(rarity_targets)))


def _row_from_statistics(label: str, statistics: DeckStatistics) -> DeckAnalyticsRow:
    return DeckAnalyticsRow(
        label=label,
        total_cards=statistics.total_cards,
        unique_cards=statistics.unique_cards,
        duplicate_identifiers=statistics.duplicate_identifiers,
        rarity_counts=statistics.rarity_counts,
        rarity_distribution=statistics.rarity_distribution,
    )


def tabulate_blueprints(
    label: str,
    blueprints: Sequence[SimpleCardBlueprint],
) -> DeckAnalyticsRow:
    """Convenience helper mirroring :func:`build_deck_analytics` for ad-hoc decks."""

    statistics = build_statistics_from_cards(blueprints)
    return _row_from_statistics(label, statistics)


__all__ = [
    "DeckAnalytics",
    "DeckAnalyticsRow",
    "build_deck_analytics",
    "tabulate_blueprints",
]

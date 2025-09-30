from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Iterable, Iterator, List, Mapping, Sequence, Tuple

from modules.basemod_wrapper.cards import SimpleCardBlueprint


class DeckMeta(type):
    """Metaclass that keeps track of cards registered on subclasses."""

    def __new__(mcls, name: str, bases: Tuple[type, ...], namespace: Dict[str, object]):
        cls = super().__new__(mcls, name, bases, namespace)
        cls._card_sequence: List[SimpleCardBlueprint] = []  # type: ignore[attr-defined]
        return cls

    def __iter__(cls) -> Iterator[SimpleCardBlueprint]:  # pragma: no cover - trivial delegation
        return iter(cls._card_sequence)

    def __len__(cls) -> int:  # pragma: no cover - trivial delegation
        return len(cls._card_sequence)


class Deck(metaclass=DeckMeta):
    """Base class representing an ordered collection of card blueprints."""

    display_name: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.display_name = getattr(cls, "display_name", cls.__name__)

    # ------------------------------------------------------------------
    # Card management helpers
    # ------------------------------------------------------------------
    @classmethod
    def addCard(cls, blueprint: SimpleCardBlueprint) -> SimpleCardBlueprint:
        """Register ``blueprint`` with the deck and return it."""

        if not isinstance(blueprint, SimpleCardBlueprint):
            raise TypeError("addCard expects a SimpleCardBlueprint instance.")
        cls._card_sequence.append(blueprint)
        return blueprint

    @classmethod
    def add_card(cls, blueprint: SimpleCardBlueprint) -> SimpleCardBlueprint:
        """Alias mirroring the camelCase API used by authoring scripts."""

        return cls.addCard(blueprint)

    @classmethod
    def extend(cls, blueprints: Iterable[SimpleCardBlueprint]) -> None:
        """Append multiple ``blueprints`` in the given order."""

        for blueprint in blueprints:
            cls.addCard(blueprint)

    @classmethod
    def cards(cls) -> Tuple[SimpleCardBlueprint, ...]:
        """Return an immutable snapshot of all card blueprints."""

        return tuple(cls._card_sequence)

    @classmethod
    def unique_cards(cls) -> Dict[str, SimpleCardBlueprint]:
        """Return a mapping of card identifiers to their first blueprint."""

        mapping: Dict[str, SimpleCardBlueprint] = {}
        for blueprint in cls._card_sequence:
            mapping.setdefault(blueprint.identifier, blueprint)
        return mapping

    @classmethod
    def rarity_counts(cls) -> Dict[str, int]:
        """Return the rarity histogram for the current deck."""

        counts = Counter(card.rarity for card in cls._card_sequence)
        return dict(counts)

    @classmethod
    def statistics(cls) -> "DeckStatistics":
        """Return an immutable snapshot describing the deck contents.

        The statistics structure exposes a high level overview that can be used
        by authoring tooling, plugins or validation routines.  It keeps the
        underlying data immutable so callers can safely cache or share the
        results without worrying about accidental mutation.
        """

        return build_statistics_from_cards(cls._card_sequence)

    @classmethod
    def card_identifiers(cls) -> List[str]:
        """Return card identifiers preserving deck order."""

        return [blueprint.identifier for blueprint in cls._card_sequence]

    @classmethod
    def clear(cls) -> None:
        """Remove all card registrations from the deck."""

        cls._card_sequence.clear()

    @classmethod
    def __iter__(cls) -> Iterator[SimpleCardBlueprint]:  # pragma: no cover - trivial delegation
        return iter(cls._card_sequence)


__all__ = ["Deck"]


def build_statistics_from_cards(
    cards: Sequence[SimpleCardBlueprint],
) -> "DeckStatistics":
    """Return :class:`DeckStatistics` for an arbitrary card sequence.

    The helper mirrors :meth:`Deck.statistics` but operates on any iterable of
    :class:`SimpleCardBlueprint` instances.  It keeps the return value immutable
    so the analytics layer and plugins can safely cache or serialise the
    results.
    """

    identifier_counts = Counter(card.identifier for card in cards)
    rarity_counts = Counter(card.rarity.upper() for card in cards)
    return DeckStatistics(
        total_cards=len(cards),
        identifier_counts=MappingProxyType(dict(identifier_counts)),
        rarity_counts=MappingProxyType(dict(rarity_counts)),
    )


@dataclass(frozen=True)
class DeckStatistics:
    """Immutable summary describing the composition of a deck."""

    total_cards: int
    identifier_counts: Mapping[str, int]
    rarity_counts: Mapping[str, int]

    @property
    def unique_cards(self) -> int:
        """Return how many distinct card identifiers exist within the deck."""

        return len(self.identifier_counts)

    @property
    def duplicate_identifiers(self) -> Mapping[str, int]:
        """Return identifiers that appear more than once in the deck."""

        duplicates = {key: count for key, count in self.identifier_counts.items() if count > 1}
        return MappingProxyType(duplicates)

    @property
    def rarity_distribution(self) -> Mapping[str, float]:
        """Return rarity ratios expressed as percentages of the total deck."""

        if self.total_cards == 0:
            return MappingProxyType({})
        distribution = {
            rarity: (count / self.total_cards) * 100.0
            for rarity, count in self.rarity_counts.items()
        }
        return MappingProxyType(distribution)


__all__.append("DeckStatistics")
__all__.append("build_statistics_from_cards")

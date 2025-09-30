from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, Iterator, List, Tuple

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

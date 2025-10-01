"""Persistence utilities for Digitales Monster level stability values.

The Digitales Monster mod tracks Stabilitätswerte (stability ratings) for every
Digimon level.  Each record stores the starting value, the current maximum and
the live stability score.  This module provides a production-ready persistence
layer that serialises the values to JSON, exposes them to plugins and mirrors
the structure expected by StSLib's persist field helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

from plugins import PLUGIN_MANAGER

__all__ = [
    "LevelStabilityRecord",
    "LevelStabilityProfile",
    "LevelStabilityStore",
    "StabilityPersistFieldAdapter",
    "LEVEL_STABILITY_PERSIST_KEY",
]

LEVEL_STABILITY_PERSIST_KEY = "digitalesmonster_level_stability"


@dataclass(frozen=True)
class LevelStabilityRecord:
    """Immutable snapshot describing the stability values for a level."""

    level: str
    start: int
    maximum: int
    current: int

    def clamp(self) -> "LevelStabilityRecord":
        """Return a record where ``current`` is clamped between 0 and ``maximum``."""

        value = max(0, min(self.current, self.maximum))
        if value == self.current:
            return self
        return LevelStabilityRecord(self.level, self.start, self.maximum, value)

    def with_current(self, value: int) -> "LevelStabilityRecord":
        return LevelStabilityRecord(self.level, self.start, self.maximum, value).clamp()

    def with_bounds(self, *, start: Optional[int] = None, maximum: Optional[int] = None) -> "LevelStabilityRecord":
        new_start = self.start if start is None else int(start)
        new_max = self.maximum if maximum is None else int(maximum)
        new_start = max(0, new_start)
        new_max = max(new_start, new_max)
        new_current = max(0, min(self.current, new_max))
        return LevelStabilityRecord(self.level, new_start, new_max, new_current)

    def to_payload(self) -> Dict[str, int]:
        return {"start": self.start, "maximum": self.maximum, "current": self.current}

    @staticmethod
    def from_payload(level: str, payload: Mapping[str, int]) -> "LevelStabilityRecord":
        return LevelStabilityRecord(
            level,
            int(payload.get("start", 0)),
            int(payload.get("maximum", payload.get("max", 0))),
            int(payload.get("current", payload.get("value", 0))),
        ).clamp()


class LevelStabilityProfile:
    """Mutable registry that keeps track of level stability values."""

    def __init__(
        self,
        *,
        records: Optional[Iterable[LevelStabilityRecord]] = None,
        persist_key: str = LEVEL_STABILITY_PERSIST_KEY,
    ) -> None:
        self._records: Dict[str, LevelStabilityRecord] = {}
        self.persist_key = persist_key
        if records:
            for record in records:
                self._records[record.level] = record.clamp()

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def register_level(
        self,
        level: str,
        *,
        start: int,
        maximum: Optional[int] = None,
        current: Optional[int] = None,
    ) -> LevelStabilityRecord:
        """Add a new level to the profile and return the resulting record."""

        level = level.strip()
        if not level:
            raise ValueError("Level identifier must be a non-empty string.")
        start_value = max(0, int(start))
        max_value = int(maximum if maximum is not None else start_value)
        if max_value < start_value:
            max_value = start_value
        current_value = int(current if current is not None else start_value)
        record = LevelStabilityRecord(level, start_value, max_value, current_value).clamp()
        self._records[level] = record
        return record

    def get(self, level: str) -> LevelStabilityRecord:
        """Return the record for ``level`` raising ``KeyError`` if unknown."""

        return self._records[level]

    def records(self) -> Iterable[LevelStabilityRecord]:
        return tuple(self._records.values())

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------
    def adjust_current(self, level: str, delta: int) -> LevelStabilityRecord:
        record = self.get(level)
        updated = record.with_current(record.current + int(delta))
        self._records[level] = updated
        return updated

    def update_level(
        self,
        level: str,
        *,
        start: Optional[int] = None,
        maximum: Optional[int] = None,
        current: Optional[int] = None,
    ) -> LevelStabilityRecord:
        record = self.get(level)
        updated = record.with_bounds(start=start, maximum=maximum)
        if current is not None:
            updated = updated.with_current(int(current))
        self._records[level] = updated
        return updated

    def as_payload(self) -> Dict[str, Dict[str, int]]:
        return {level: record.to_payload() for level, record in self._records.items()}

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps({self.persist_key: self.as_payload()}, indent=indent, sort_keys=True)

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Mapping[str, int]],
        *,
        persist_key: str = LEVEL_STABILITY_PERSIST_KEY,
    ) -> "LevelStabilityProfile":
        records = [
            LevelStabilityRecord.from_payload(level, values)
            for level, values in payload.items()
        ]
        return cls(records=records, persist_key=persist_key)

    @classmethod
    def from_json(cls, text: str) -> "LevelStabilityProfile":
        data = json.loads(text)
        payload = data.get(LEVEL_STABILITY_PERSIST_KEY, data)
        if not isinstance(payload, Mapping):
            raise ValueError("Invalid stability payload structure.")
        return cls.from_payload(payload)


class LevelStabilityStore:
    """Persist :class:`LevelStabilityProfile` instances to disk."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> LevelStabilityProfile:
        if not self.path.exists():
            return LevelStabilityProfile()
        content = self.path.read_text(encoding="utf8")
        return LevelStabilityProfile.from_json(content)

    def save(self, profile: LevelStabilityProfile) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = profile.to_json()
        self.path.write_text(serialized + "\n", encoding="utf8")


class StabilityPersistFieldAdapter:
    """Bridge between :class:`LevelStabilityProfile` and StSLib persist fields."""

    def __init__(self, profile: LevelStabilityProfile) -> None:
        self.profile = profile

    def to_stslib_payload(self) -> Dict[str, Dict[str, int]]:
        return self.profile.as_payload()

    def update_from_stslib(self, payload: Mapping[str, Mapping[str, int]]) -> None:
        for level, values in payload.items():
            record = LevelStabilityRecord.from_payload(level, values)
            if level in self.profile._records:
                self.profile.update_level(
                    level,
                    start=record.start,
                    maximum=record.maximum,
                    current=record.current,
                )
            else:
                self.profile.register_level(
                    level,
                    start=record.start,
                    maximum=record.maximum,
                    current=record.current,
                )


PLUGIN_MANAGER.expose("LevelStabilityRecord", LevelStabilityRecord)
PLUGIN_MANAGER.expose("LevelStabilityProfile", LevelStabilityProfile)
PLUGIN_MANAGER.expose("LevelStabilityStore", LevelStabilityStore)
PLUGIN_MANAGER.expose("StabilityPersistFieldAdapter", StabilityPersistFieldAdapter)
PLUGIN_MANAGER.expose("digitalesmonster_level_stability_key", LEVEL_STABILITY_PERSIST_KEY)
PLUGIN_MANAGER.expose_module("mods.digitalesmonster.persistence", alias="digitalesmonster_persistence")

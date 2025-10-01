"""Adaptive deck evolver relic implementations."""
from __future__ import annotations

from typing import Iterable

from modules.basemod_wrapper.relics import Relic


class AdaptiveTelemetryCore(Relic):
    """Relic that amplifies adaptive deck evolution feedback."""

    mod_id = "adaptive_evolver"
    identifier = "adaptive_evolver:telemetry_core"
    display_name = "Adaptive Telemetry Core"
    description_text = (
        "Records combat telemetry at an enhanced resolution. After each victory the evolution "
        "plan receives synergy-focused notes and metadata boosts."
    )
    flavor_text = "\"Every strike is a datapoint, every defence a hypothesis.\""
    tier = "RARE"
    landing_sound = "MAGICAL"
    relic_pool = "SHARED"
    image = "adaptive_evolver/images/relics/telemetry_core.png"

    def __init__(self) -> None:
        super().__init__()
        self.counter = 0

    def on_combat_begin(self, mod: object, recorder: object) -> None:
        self.counter += 1
        if hasattr(recorder, "add_note"):
            recorder.add_note("Adaptive Telemetry Core calibrates to the encounter.")

    def on_plan_finalised(self, mod: object, plan: object) -> None:
        notes: Iterable[str] = getattr(plan, "notes", ()) or ()
        enhanced_notes = list(dict.fromkeys(tuple(notes) + ("Telemetry Core prioritised synergy lines",)))
        try:
            plan.notes = tuple(enhanced_notes)
        except Exception:
            pass
        mutations = getattr(plan, "mutations", ()) or ()
        for mutation in mutations:
            try:
                mutation_notes = list(dict.fromkeys(tuple(getattr(mutation, "notes", ())) + ("Telemetry Core reinforcement",)))
                mutation.notes = tuple(mutation_notes)
            except Exception:
                pass
            metadata = dict(getattr(mutation, "metadata", {}) or {})
            metadata.setdefault("telemetry_core_boost", True)
            mutation.metadata = metadata
        style_vector = getattr(plan, "style_vector", None)
        if style_vector is not None:
            if hasattr(style_vector, "combo"):
                style_vector.combo += 0.35
            summary = getattr(style_vector, "summary", "") or ""
            if "Telemetry Core" not in summary:
                new_summary = f"{summary} | Telemetry Core boost" if summary else "Telemetry Core boost"
                try:
                    style_vector.summary = new_summary
                except Exception:
                    pass
        if getattr(plan, "source_combat", None) is None:
            plan.source_combat = f"telemetry_core:{self.counter}"

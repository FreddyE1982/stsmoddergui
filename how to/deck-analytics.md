# Enrich character validation with deck analytics

This companion guide builds on [basic-character.md](basic-character.md). Once your decks
are wired into a `Character` subclass you can generate production-grade analytics
tables and JSON artefacts without touching spreadsheets.

## 1. Capture analytics alongside validation

1. Instantiate your character and collect the deck snapshot just like in the
   basic walkthrough.

   ```python
   from pathlib import Path

   from my_mod.character import Buddy

   buddy = Buddy()
   decks = Buddy.collect_cards(buddy)
   report = Buddy.validate(buddy, decks=decks, assets_root=Path("resources/Buddy"))
   analytics = report.context["analytics"]
   table = report.context["analytics_table"]

   print(table[0]["label"], table[0]["rarity_distribution"])
   # Buddy starter – Buddy Starter {'BASIC': 53.33, 'UNCOMMON': 26.67, 'RARE': 20.0}
   ```

2. You can also rebuild the analytics table manually – handy for CLI scripts or
   continuous integration bots that want to surface deck trends without running
   the full bundler.

   ```python
   from modules.modbuilder import build_deck_analytics
   from modules.modbuilder.character import RARITY_TARGETS

   analytics = build_deck_analytics(buddy, decks, rarity_targets=RARITY_TARGETS)
   for row in analytics.rows:
       print(row.label, row.total_cards, row.duplicate_identifiers)
   ```

## 2. Export JSON artefacts for dashboards

1. The analytics helper ships with a turn-key JSON exporter. Point it at a
   destination path and wire the resulting payload into your favourite
   dashboards.

   ```python
   output = analytics.write_json(Path("dist") / "analytics" / "buddy.json")
   print(output.read_text())
   ```

   The generated file includes the rarity target ratios so designers know how
   far a deck deviates from the standard Slay the Spire proportions.

2. Consumers that prefer direct access can call `analytics.to_json()` and feed
   the returned string to an HTTP API or any downstream tooling.

## 3. Hook plugins into the analytics pipeline

1. Plugins subscribed to `CHARACTER_VALIDATION_HOOK` receive the populated
   analytics object in the `report.context` mapping. This makes it trivial to
   add archetype heuristics, synergy hints or risk warnings from external
   systems.

   ```python
   from plugins import PLUGIN_MANAGER

   class SynergyAdvisor:
       name = "synergy-advisor"

       def modbuilder_character_validate(self, *, report, **_):
           analytics = report.context["analytics"]
           combined = analytics.combined
           if combined.rarity_distribution.get("RARE", 0) > 10:
               report.context.setdefault(self.name, {})["note"] = "Lean on rare support relics."

   def setup_plugin(manager, exposed):
       advisor = SynergyAdvisor()
       return advisor

   PLUGIN_MANAGER.register_plugin(__name__)
   ```

2. Because the analytics rows expose immutable mappings, plugins can safely
   cache them or compute deltas between validation runs without worrying about
   accidental mutation.


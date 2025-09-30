# Extend the Buddy mod with custom keywords and cards

This guide builds on [Build a starter-friendly character with bundled decks](./basic-character.md). We keep leaning on the high level helpers – the decks stay `Deck` subclasses, the character is still a `Character`, and every keyword derives from the provided `Keyword` base class so scheduling and persistence work automatically.

## 1. Create and register a custom keyword

1. Import the keyword infrastructure. The `Keyword` base class already exposes proxy objects for the player, enemies, and the triggering card.

   ```python
   from modules.basemod_wrapper.keywords import Keyword
   ```

2. Model the behaviour inside `apply`. The proxies let you manipulate block, powers, and even enqueue BaseMod actions without touching the raw runtime.

   ```python
   class PhaseShift(Keyword):
       def __init__(self) -> None:
           super().__init__(
               name="PhaseShift",
               proper_name="Phase Shift",
               description="Gain Block equal to the keyword amount and convert excess into Strength.",
           )
           self.when = "now"  # execute immediately when the card is played

       def apply(self, context) -> None:
           amount = context.amount or 0
           self.player.block += amount
           overflow = max(0, amount - 5)
           if overflow:
               self.player.strength += overflow
   ```

3. Call `register` on the keyword instance to make BaseMod aware of it. Provide the mod id from your `Character` so tooltips use the right namespace.

   ```python
   phase_shift = PhaseShift()
   phase_shift.register(
       mod_id="buddy",
       names=["phase shift", "PhaseShift"],
       color=(0.20, 0.40, 0.80, 1.0),
   )
   ```

## 2. Build cards that rely on the new keyword

1. Because the deck system is declarative, you only need to append new `SimpleCardBlueprint` instances. The keyword is attached via the `keywords` tuple and powered by `keyword_values`.

   ```python
   from modules.basemod_wrapper import SimpleCardBlueprint

   Unlockables.addCard(
       SimpleCardBlueprint(
           identifier="BuddyPhaseGuard",
           title="Phase Guard",
           description="Gain {block} Block. Phase Shift {phase_shift}.",
           cost=1,
           card_type="skill",
           target="self",
           effect="block",
           rarity="uncommon",
           value=9,
           upgrade_value=4,
           keywords=("PhaseShift",),
           keyword_values={"PhaseShift": 7},
       )
   )
   ```

2. If you want a starter card to showcase the mechanic immediately, register it on `StarterDeck` in the same fashion. You still use `Deck.addCard` so validation keeps working.

3. Rerun `Deck.statistics()` to confirm the rarity ratios still match your goals.

## 3. Ship the updated mod

1. Leave the `Buddy` character subclass untouched – it already references the deck classes and therefore sees the new cards automatically.
2. Call `Buddy.createMod(...)` again. The bundler reuses the high level configuration, copies the keyword registration code, and produces an updated jar.

That is all you need to bolt custom keywords on top of the baseline character while staying entirely inside the Deck/Character/Keyword APIs.

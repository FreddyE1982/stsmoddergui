# Layer persistent card evolution on top of the Buddy mod

Continuing from the previous guides, we now tap into the advanced facilities bundled with `Keyword` and `CardEditor` to create mechanics that rewrite cards for the current combat, the running game, or permanently across saves.

## 1. Craft an advanced keyword with scheduling and persistence

1. Import everything from the high level toolkit – no direct BaseMod calls needed.

   ```python
   from modules.basemod_wrapper.keywords import (
       Keyword,
       CardEditor,
       apply_persistent_card_changes,
   )
   ```

2. Subclass `Keyword` and lean on the scheduling hints. Setting `when = "nextend"` runs the effect at the end of the next turn, giving the player time to set up combos.

   ```python
   class EchoImprint(Keyword):
       def __init__(self) -> None:
           super().__init__(
               name="EchoImprint",
               proper_name="Echo Imprint",
               description=(
                   "At the end of next turn, permanently improve the triggering card."
                   " Base amount increases damage for the combat; upgrade amount reduces cost forever."
               ),
           )
           self.when = "nextend"   # execute after the player's next turn
           self.turn_offset = 1

       def apply(self, context) -> None:
           amount = context.amount or 0
           upgrade = context.upgrade or 0

           editor = CardEditor(context.card)

           # 1. Boost the card for this combat.
           editor.persist_for_combat(value=editor.value + amount)

           # 2. Make the bonus stick for the current run by targeting the master deck copy.
           editor.persist_for_run(context.player, value=editor.value)

           # 3. On upgrade, cement a permanent benefit for future saves.
           if upgrade:
               new_cost = max(0, editor.cost - upgrade)
               editor.persist_forever(context.player, cost=new_cost)
   ```

3. Registration mirrors the earlier guide. Permanent effects rely on the persistence manager, so reuse the same mod id and colour.

   ```python
   echo_imprint = EchoImprint()
   echo_imprint.register(
       mod_id="buddy",
       names=["echo imprint"],
       color=(0.25, 0.10, 0.35, 1.0),
   )
   ```

4. The built-in scheduler automatically reapplies stored payloads on `PostDungeonInitialize`. If you need to preview the behaviour outside the game (e.g. in tests), call `apply_persistent_card_changes(player)` manually after loading a save to hydrate modified cards.

## 2. Add blueprints that drive the advanced keyword

1. Attach the keyword to a high rarity card so players unlock it mid-run.

   ```python
   from modules.basemod_wrapper import SimpleCardBlueprint

   Unlockables.addCard(
       SimpleCardBlueprint(
           identifier="BuddyEchoBlade",
           title="Echo Blade",
           description="Deal {damage} damage. Echo Imprint {echo_imprint} ({upgrade_echo_imprint}).",
           cost=2,
           card_type="attack",
           target="enemy",
           rarity="rare",
           value=14,
           upgrade_value=5,
           keywords=("EchoImprint",),
           keyword_values={"EchoImprint": 3},
           keyword_upgrades={"EchoImprint": 1},
       )
   )
   ```

2. Starter decks can showcase the mechanic immediately if you also append a cheaper blueprint there. Either way, stick to `Deck.addCard` so that the validation phase keeps your totals balanced.

## 3. Bundle the evolved mod

1. Ensure the keyword registration code executes during initialisation (for example by importing the module in `python/__init__.py`).
2. Run `Buddy.createMod(...)` one more time. The bundler carries over the persisted keyword infrastructure, so your jar now ships with cards that can rewrite themselves across combats and runs.

With `Deck`, `Character`, `Keyword`, and `CardEditor` doing the heavy lifting, even sophisticated persistence mechanics stay fully declarative.

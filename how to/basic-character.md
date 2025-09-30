# Build a starter-friendly character with bundled decks

This walkthrough leans entirely on the repository's highest level helpers – `Deck`, `Character`, `SimpleCardBlueprint`, and `Character.createMod` – so you never have to reach for raw BaseMod calls. Follow along to assemble a playable mod that ships with a starter deck and an unlockable pool.

## 1. Define the starter and unlockable decks

1. Import the turnkey helpers and keep the card art locations handy. Every
   blueprint needs an inner card illustration so the automatic asset pipeline
   can bake the portrait and small variants. The images must be **exactly**
   500x380 PNG files.

   ```python
   from pathlib import Path

   from modules.modbuilder import Deck
   from modules.basemod_wrapper import SimpleCardBlueprint

   CARD_ART = Path("resources/Buddy/images/cards/inner")
   ```

2. Model each deck as a subclass of `Deck` and register cards with `Deck.addCard`. Because `Deck` keeps the registration order, the starter draw pile will match your declarations exactly.

   ```python
   class StarterDeck(Deck):
       """Opening hand – only basic cards here."""

   StarterDeck.addCard(
       SimpleCardBlueprint(
           identifier="BuddyStrike",
           title="Buddy Strike",
           description="Deal {damage} damage.",
           cost=1,
           card_type="attack",
           target="enemy",
           rarity="basic",
           value=6,
           upgrade_value=3,
           starter=True,
       ).innerCardImage(str(CARD_ART / "BuddyStrike.png"))
   )

   StarterDeck.addCard(
       SimpleCardBlueprint(
           identifier="BuddyDefend",
           title="Buddy Defend",
           description="Gain {block} Block.",
           cost=1,
           card_type="skill",
           target="self",
           effect="block",
           rarity="basic",
           value=5,
           upgrade_value=3,
           starter=True,
       ).innerCardImage(str(CARD_ART / "BuddyDefend.png"))
   )

   class Unlockables(Deck):
       """Cards awarded through progression."""

   Unlockables.addCard(
       SimpleCardBlueprint(
           identifier="BuddyFinisher",
           title="Buddy Finisher",
           description="Deal {damage} damage to all enemies.",
           cost=2,
           card_type="attack",
           target="enemies",
           rarity="rare",
           value=14,
           upgrade_value=6,
       ).innerCardImage(str(CARD_ART / "BuddyFinisher.png"))
   )
   ```

3. Use `Deck.statistics()` whenever you need to double-check rarity spread or duplicates without writing extra tooling. Once
   the inner card image is registered, the bundler derives the card frame, small art and portrait files automatically and caches
   the results in `.inner_card_manifest.json` so reruns are instant.

   ```python
   print(StarterDeck.statistics())
   print(Unlockables.statistics())
   ```

## 2. Describe the character with the high level `Character` helper

1. Subclass `Character` and configure the metadata inside `__init__`. Stick to the provided config dataclasses instead of hand-rolled dictionaries.

   ```python
   from modules.modbuilder import Character, CharacterColorConfig, CharacterImageConfig

   class Buddy(Character):
       def __init__(self) -> None:
           super().__init__()
           self.name = "Buddy"
           self.mod_id = "buddy"
           self.author = "The Crew"
           self.description = "Friendly bruiser with simple combos."

           self.start.deck = StarterDeck
           self.unlockableDeck = Unlockables

           self.color = CharacterColorConfig(
               identifier="BUDDY_BLUE",
               card_color=(0.20, 0.40, 0.80, 1.0),
               trail_color=(0.20, 0.30, 0.70, 1.0),
               slash_color=(0.30, 0.50, 0.90, 1.0),
               attack_bg="resources/Buddy/images/cards/attack.png",
               skill_bg="resources/Buddy/images/cards/skill.png",
               power_bg="resources/Buddy/images/cards/power.png",
               orb="resources/Buddy/images/cards/orb.png",
               attack_bg_small="resources/Buddy/images/cards/attack_small.png",
               skill_bg_small="resources/Buddy/images/cards/skill_small.png",
               power_bg_small="resources/Buddy/images/cards/power_small.png",
               orb_small="resources/Buddy/images/cards/orb_small.png",
           )

           self.image = CharacterImageConfig(
               shoulder1="resources/Buddy/images/character/shoulder1.png",
               shoulder2="resources/Buddy/images/character/shoulder2.png",
               corpse="resources/Buddy/images/character/corpse.png",
               staticspineanimation="resources/Buddy/images/character/idle.png",
           )
   ```

2. Let `Character.collect_cards` and `Character.validate` do the heavy lifting. They ensure the decks conform to rarity targets
   and that every blueprint has matching art before any bundling happens. When `staticspineanimation` is set, the helper also
   generates the matching `.atlas` and `.json` skeleton files next to the PNG and wires them into the runtime automatically, so
   you can ship a static pose without touching Spine.

## 3. Bundle a runnable mod package

1. Create directories for Python scripts and assets. Make sure the resource tree mirrors the paths referenced in
   `CharacterColorConfig`, `CharacterImageConfig.staticspineanimation`, and the `innerCardImage` calls. Every inner art PNG
   should live under `resources/Buddy/images/cards/inner`, while the static character pose sits at
   `resources/Buddy/images/character/idle.png` so the auto-generated atlas and skeleton land alongside it.
2. Call `Buddy.createMod(destination, assets_root=..., python_source=...)`. Use the keyword arguments instead of lower-level project helpers – `createMod` wires decks, character blueprint, and bundling options in one go.

   ```python
   from pathlib import Path

   output = Buddy.createMod(
       Path("dist"),
       assets_root=Path("resources/Buddy"),
       python_source=Path("python"),
       bundle=True,
   )
   print(f"Bundled mod at {output}")
   ```

3. If you only want to scaffold the project without producing a jar yet, pass `bundle=False`. The method still uses the high level validation pipeline and returns the directory where assets were prepared.

That is it – by leaning on `Deck`, `Character`, and `Character.createMod`, you get a fully validated mod with zero custom plumbing.

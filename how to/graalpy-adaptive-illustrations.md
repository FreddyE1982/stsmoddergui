Walk through enabling the `experimental.graalpy_adaptive_illustrations` module to recolour card art dynamically. The flow mirrors the other guides – start with `Deck`/`Character`, activate the experiment, then let the high-level director drive the swaps.

## 1. Build decks with inner art

```python
from pathlib import Path

from modules.modbuilder.deck import Deck
from modules.basemod_wrapper.cards import SimpleCardBlueprint

ART_ROOT = Path("resources/Buddy/images/cards/inner")


class BuddyStarter(Deck):
    display_name = "Buddy Starter"


BuddyStarter.addCard(
    SimpleCardBlueprint(
        identifier="BuddyStrike",
        title="Buddy Strike",
        description="Deal {damage} damage.",
        cost=1,
        card_type="attack",
        target="enemy",
        rarity="basic",
        value=7,
        upgrade_value=3,
        starter=True,
    ).innerCardImage(str(ART_ROOT / "BuddyStrike.png"))
)

BuddyStarter.addCard(
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
    ).innerCardImage(str(ART_ROOT / "BuddyDefend.png"))
)
```

## 2. Activate the GraalPy adaptive illustrations feature

```python
from modules.basemod_wrapper import experimental

illustrations = experimental.on("graalpy_adaptive_illustrations")
```

The module guarantees `experimental.graalpy_runtime` is also enabled so Pillow transforms run under GraalPy.

## 3. Configure a director and palettes

```python
from modules.modbuilder.character import Character


class Buddy(Character):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Buddy"
        self.mod_id = "buddy"
        self.start.deck = BuddyStarter
        self.description = "Adapts card art based on relics and keywords."


director = illustrations.launch_adaptive_illustrations(
    BuddyStarter,
    asset_root=ART_ROOT,
)

director.register_rarity_palette(
    "basic",
    color=(30, 180, 240),
    intensity=0.55,
)

director.register_card_override(
    "BuddyDefend",
    illustrations.create_keyword_glow_transform(
        "poison",
        color=(0, 255, 0),
        radius=4,
        intensity=0.7,
    ),
)
```

The director caches each blueprint's original inner card art so repeats always recolour from the base asset.

## 4. Apply swaps before bundling

```python
context = director.build_context(
    relics=("Toxic Egg", "Lantern"),
    keyword_counts={"poison": 3},
    metadata={"act": 2},
)

generated_paths = director.apply(context)
```

`generated_paths` maps card identifiers to the new PNG files. The deck's blueprints now point to those files so bundling reuses the adaptive art.

## 5. Wire the character into a project

Bundle the character with `Character.createMod` exactly like the other how-to guides. The generated art files live under `lib/graalpy/adaptive_illustrations/<deck>` and travel with the mod package.

## 6. Explore the granular API for advanced rules

If you need to orchestrate swaps outside of deck-level automation you can use the engine directly:

```python
engine = illustrations.get_engine()
engine.register_rule(
    illustrations.IllustrationSwapRule(
        card_id="BuddyStrike",
        transform=illustrations.create_tint_transform((255, 80, 80), intensity=0.7),
        name="berserk",
    ),
    replace=True,
)

engine.apply_to_blueprint(BuddyStarter.cards()[0], context)
```

Both APIs are exposed through `plugins.PLUGIN_MANAGER`, enabling dashboards or external tooling to track generated art and register custom transforms.

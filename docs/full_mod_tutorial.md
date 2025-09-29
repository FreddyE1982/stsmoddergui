# Full Mod Tutorial: Building a Custom Slay the Spire Character with the BaseMod Wrapper

This walkthrough shows how to go from an empty folder to a fully packaged, ModTheSpire-ready mod using the high-level project system that ships with `modules.basemod_wrapper`. We will build the **Wraithblade** – a ghostly duellist with bespoke cards, a unique colour, and a ready-to-run bundle.

The tutorial assumes you have:

- A local checkout of this repository (so the wrapper and plugin infrastructure are available).
- Access to Slay the Spire's jars (`SlayTheSpire.jar`, `desktop-1.0.jar`) and the latest BaseMod / ModTheSpire jars.
- Your art assets exported as PNGs. Keep layered sources elsewhere; the bundler copies only the runtime-ready PNGs.
- Python 3.10+ and Java 8 or newer installed and on your `PATH`.

> **Heads up:** the wrapper handles *all* BaseMod hook wiring, enum patch generation, folder creation, and bundling. You only provide declarative metadata plus the gameplay logic for your cards.

---

## 1. Project layout

Create a workspace anywhere on disk – here we use `~/mods/wraithblade`. The wrapper's bundler will generate the ModTheSpire layout automatically, so you only need three source folders:

```
wraithblade/
├── python_src/          # Pure Python gameplay code, no Java required
│   └── wraithblade/
│       ├── __init__.py
│       ├── cards.py
│       └── entrypoint.py
├── resources_src/       # All images, localisation JSON, etc.
│   └── wraithblade/
│       ├── images/
│       │   ├── badge.png
│       │   ├── character/
│       │   │   ├── shoulder.png
│       │   │   ├── shoulder2.png
│       │   │   └── corpse.png
│       │   ├── cards/
│       │   │   ├── void_slash.png
│       │   │   └── ghostward.png
│       │   └── ui/
│       │       └── orb.png
│       └── localizations/
│           └── eng/
│               ├── cards.json
│               └── character.json
└── build_mod.py         # The script that defines the project + bundling steps
```

The bundler will copy `python_src/` and `resources_src/` into their final destinations, generate enum patches, compile them, and emit a complete ModTheSpire folder under `dist/`.

---

## 2. Implementing cards the high-level way

Create `python_src/wraithblade/cards.py` and declare your cards as regular Python classes extending `CustomCard`. The wrapper already has JPype booted, so subclassing works like native Python:

```python
# python_src/wraithblade/cards.py
from modules.basemod_wrapper import basemod, cardcrawl

CustomCard = basemod.abstracts.CustomCard
AbstractCard = cardcrawl.cards.AbstractCard
DamageInfo = cardcrawl.cards.DamageInfo
AbstractGameAction = cardcrawl.actions.AbstractGameAction

WRAITHBLADE_COLOR = AbstractCard.CardColor.valueOf("WRAITHBLADE_VIOLET")

class VoidSlash(CustomCard):
    ID = "Wraithblade:VoidSlash"
    IMG = "wraithblade/images/cards/void_slash.png"

    def __init__(self):
        super().__init__(
            self.ID,
            "Void Slash",
            self.IMG,
            1,
            "Deal 8(11) damage.",
            AbstractCard.CardType.ATTACK,
            WRAITHBLADE_COLOR,
            AbstractCard.CardRarity.BASIC,
            AbstractCard.CardTarget.ENEMY,
        )
        self.baseDamage = 8
        self.tags.add(AbstractCard.CardTags.STARTER_STRIKE)

    def use(self, player, monster):
        action = cardcrawl.actions.common.DamageAction(
            monster,
            DamageInfo(player, self.damage, self.damageTypeForTurn),
            AbstractGameAction.AttackEffect.SLASH_HEAVY,
        )
        cardcrawl.dungeons.AbstractDungeon.actionManager.addToBottom(action)

    def upgrade(self):
        if not self.upgraded:
            self.upgradeName()
            self.upgradeDamage(3)

    def makeCopy(self):
        return VoidSlash()

class GhostWard(CustomCard):
    ID = "Wraithblade:GhostWard"
    IMG = "wraithblade/images/cards/ghostward.png"

    def __init__(self):
        super().__init__(
            self.ID,
            "Ghost Ward",
            self.IMG,
            1,
            "Gain 5(8) Block.",
            AbstractCard.CardType.SKILL,
            WRAITHBLADE_COLOR,
            AbstractCard.CardRarity.BASIC,
            AbstractCard.CardTarget.SELF,
        )
        self.baseBlock = 5
        self.tags.add(AbstractCard.CardTags.STARTER_DEFEND)

    def use(self, player, monster):
        action = cardcrawl.actions.common.GainBlockAction(player, player, self.block)
        cardcrawl.dungeons.AbstractDungeon.actionManager.addToBottom(action)

    def upgrade(self):
        if not self.upgraded:
            self.upgradeName()
            self.upgradeBlock(3)

    def makeCopy(self):
        return GhostWard()
```

You never touch BaseMod hooks directly – the `ModProject` will take care of registration in §4.

---

## 3. Declaring the mod project

`build_mod.py` orchestrates everything: define the colour palette, register cards, describe the character, then bundle.

```python
# build_mod.py
from pathlib import Path

from modules.basemod_wrapper import BundleOptions, CharacterAssets, CharacterBlueprint, create_project, compileandbundle
from modules.basemod_wrapper import basemod_project  # exposed via PLUGIN_MANAGER

from python_src.wraithblade.cards import GhostWard, VoidSlash

PROJECT_ROOT = Path(__file__).parent

project = create_project(
    mod_id="wraithblade",
    name="The Wraithblade",
    author="You",
    description="Ghostly duellist who dances between the veil.",
    version="1.0.0",
)

# 1) define the colour – textures are relative to the resources directory inside the bundle
project.define_color(
    "WRAITHBLADE_VIOLET",
    card_color=(0.58, 0.28, 0.76, 1.0),
    trail_color=(0.45, 0.18, 0.62, 1.0),
    slash_color=(0.9, 0.8, 0.95, 1.0),
    attack_bg="wraithblade/images/cards/background_attack.png",
    skill_bg="wraithblade/images/cards/background_skill.png",
    power_bg="wraithblade/images/cards/background_power.png",
    orb="wraithblade/images/ui/orb.png",
    attack_bg_small="wraithblade/images/cards/background_attack_small.png",
    skill_bg_small="wraithblade/images/cards/background_skill_small.png",
    power_bg_small="wraithblade/images/cards/background_power_small.png",
    orb_small="wraithblade/images/ui/orb_small.png",
)

# 2) register cards via factories – mark basics so BaseMod adds them to the starter pool
project.add_card("VoidSlash", VoidSlash, basic=True)
project.add_card("GhostWard", GhostWard, basic=True)

# 3) declare the character blueprint (no manual enums required!)
project.add_character(
    CharacterBlueprint(
        identifier="Wraithblade",
        character_name="The Wraithblade",
        description="A duellist who spins blades of aether.",
        assets=CharacterAssets(
            shoulder_image="wraithblade/images/character/shoulder.png",
            shoulder2_image="wraithblade/images/character/shoulder2.png",
            corpse_image="wraithblade/images/character/corpse.png",
        ),
        starting_deck=[
            "Wraithblade:VoidSlash",
            "Wraithblade:VoidSlash",
            "Wraithblade:VoidSlash",
            "Wraithblade:VoidSlash",
            "Wraithblade:GhostWard",
            "Wraithblade:GhostWard",
            "Wraithblade:GhostWard",
            "Wraithblade:GhostWard",
        ],
        starting_relics=["Ring of the Wraith"],
        loadout_description="The Wraithblade cuts through reality with ethereal steel.",
        energy_per_turn=3,
        max_hp=72,
        starting_hp=72,
        starting_gold=99,
        campfire_x=0.0,
        campfire_y=0.0,
        loadout_x=225.0,
        loadout_y=280.0,
    )
)

# 4) configure bundling – point to the jars and source directories
options = BundleOptions(
    java_classpath=[
        Path("/path/to/SlayTheSpire.jar"),
        Path("/path/to/BaseMod.jar"),
        Path("/path/to/ModTheSpire.jar"),
    ],
    python_source=PROJECT_ROOT / "python_src",
    assets_source=PROJECT_ROOT / "resources_src",
    output_directory=PROJECT_ROOT / "dist",
    version="1.0.0",
)

# 5) generate the mod folder (includes ModTheSpire.json, enum patches, compiled jar, resources, python code)
mod_folder = compileandbundle(project, options)
print(f"Ready to install: {mod_folder}")
```

Run `python build_mod.py` whenever you tweak assets or gameplay code. The wrapper regenerates everything from scratch, including the enum patch jar required by BaseMod.

---

## 4. Using the project at runtime (for iterative testing)

When you want to test without rebuilding the bundle (for instance inside a live Python REPL), simply enable the runtime hooks:

```python
# python_src/wraithblade/entrypoint.py
from modules.basemod_wrapper import create_project
from python_src.wraithblade.cards import GhostWard, VoidSlash

project = create_project(
    mod_id="wraithblade",
    name="The Wraithblade",
    author="You",
    description="Ghostly duellist who dances between the veil.",
)

# configure colour, cards and character exactly as in build_mod.py ...

project.enable_runtime()
```

Drop `entrypoint.py` into your ModTheSpire bootstrapper or any Python harness. The wrapper subscribes to `receiveEditCards`, `receiveEditCharacters` and `receivePostInitialize` internally – you never touch BaseMod subscriber plumbing.

---

## 5. Packaging outcome

After running `build_mod.py` you will find:

```
dist/
└── TheWraithblade/
    ├── ModTheSpire.json
    ├── README.txt
    ├── python/
    │   └── python_src/...
    ├── patches/
    │   └── WraithbladeEnums.java
    ├── classes/
    │   └── ... compiled enum patch classes ...
    ├── wraithblade_patches.jar
    └── resources/
        └── wraithblade/...
```

Copy `dist/TheWraithblade` into `SlayTheSpire/ModTheSpire/mods/` and enable it in the launcher. Because the bundler embeds the enum patch jar and ModTheSpire manifest, the mod is instantly usable.

---

## 6. Troubleshooting checklist

| Symptom | Fix |
| --- | --- |
| `BaseModBootstrapError: Player class WRAITHBLADE is not available` | Run `compileandbundle` at least once so the enum jar is generated, or ensure the generated jar is on the classpath during runtime tests. |
| `javac` not found | Install the JDK 8+ and ensure `javac` is available on `PATH`. |
| Card art missing | Double-check the paths passed to `define_color` and card `IMG` fields – they are relative to the mod's resources root inside the bundle. |
| Mod not appearing in ModTheSpire | Verify the generated folder is inside `ModTheSpire/mods/` and that the manifest references the correct BaseMod dependency. |

---

## 7. Extending further

- Add more cards by calling `project.add_card("Id", Factory)` or using `@project.card("Id")` as a decorator on factory functions.
- Register additional characters by appending more `CharacterBlueprint` instances.
- Publish your own helper APIs through the global `PLUGIN_MANAGER` so other mods can introspect your runtime objects.
- Document future enhancements for your mod (or the wrapper itself) in `futures.md` so the roadmap stays aligned.

Happy haunting! Once the Wraithblade slices through the Spire, you can use the same workflow to script relics, powers, events, and beyond – all without touching Java boilerplate.

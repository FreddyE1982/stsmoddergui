# BaseMod Python Wrapper

The `modules.basemod_wrapper` package gives Python modders fully automated access to [BaseMod](https://github.com/daviscook477/BaseMod), StSLib and the ModTheSpire toolchain. Importing the package spins up JPype, downloads the latest jars, exposes the Java namespaces and registers every public object with the repository wide plugin system. On top of the raw APIs the wrapper offers a high level project builder that handles runtime registration, directory scaffolding and ModTheSpire packaging without ever writing Java or touching the BaseMod hook machinery yourself.

```python
from modules.basemod_wrapper import basemod

# All Java packages are available through pleasant dotted access.
basemod.BaseMod.addKeyword(
    "my_mod",
    "SOULBURN",
    ["soulburn"],
    "Loses X HP at start of turn."
)
```

The wrapper converts Python callables to functional interfaces automatically, so you can hand plain functions or lambdas to BaseMod without manual proxy classes.

## Repository-wide plugin exposure

Every module, function and class in the repository is exposed through the global plugin manager. Mod authors or helper utilities can introspect the `PLUGIN_MANAGER.exposed` mapping to obtain handles to the wrapper, the high level project builder or any other subsystem. The plugin namespace also provides a lazily imported view of the entire repository under `plugins.PLUGIN_MANAGER.exposed["repository"]`.

## A full tutorial: ship a custom character + deck

The following tutorial walks through the whole workflow using only the high level helpers. You will end up with a ModTheSpire-ready bundle containing a new hero, his colour palette and a starter deck. At no point will you touch the `BaseMod.subscribe` plumbing or write Java patches by hand.

### 1. Describe the project

```python
from modules.basemod_wrapper import create_project

project = create_project(
    mod_id="revenant",
    name="The Revenant",
    author="OldBuddy",
    description="Soul-fuelled spectre who drains the Spire.",
    version="1.0.0",
)
```

`ModProject` keeps track of every colour, card and character you define. The object can be imported from both your build scripts and your ModTheSpire entrypoint.

### 2. Let the wrapper scaffold the filesystem

```python
layout = project.scaffold("/path/to/workspace", package_name="revenant_mod")
```

Running `scaffold` creates a ready-to-edit directory tree:

```
/path/to/workspace/revenant/
├── assets/
│   └── revenant/
│       ├── images/
│       │   ├── cards/
│       │   ├── character/
│       │   └── orbs/
│       └── localizations/eng/cards.json
└── python/
    └── revenant_mod/
        ├── __init__.py
        ├── cards/__init__.py
        ├── entrypoint.py
        └── project.py
```

`project.py` contains a `PROJECT` object and `configure()` function stub where you can define colours, cards and characters. `entrypoint.py` bootstraps the runtime automatically by calling `enable_runtime()` – no manual subscriptions.

### 3. Define the card colour and textures

Edit `python/revenant_mod/project.py` and fill the `configure()` function:

```python
from modules.basemod_wrapper.project import CharacterAssets, CharacterBlueprint
from .cards.revenant_strike import RevenantStrike


def configure() -> None:
    color = PROJECT.define_color(
        "REVENANT_PURPLE",
        card_color=(0.45, 0.15, 0.7, 1.0),
        trail_color=(0.40, 0.10, 0.65, 1.0),
        slash_color=(0.55, 0.25, 0.85, 1.0),
        attack_bg=PROJECT.resource_path("images/cards/attack.png"),
        skill_bg=PROJECT.resource_path("images/cards/skill.png"),
        power_bg=PROJECT.resource_path("images/cards/power.png"),
        orb=PROJECT.resource_path("images/cards/orb.png"),
        attack_bg_small=PROJECT.resource_path("images/cards/attack_small.png"),
        skill_bg_small=PROJECT.resource_path("images/cards/skill_small.png"),
        power_bg_small=PROJECT.resource_path("images/cards/power_small.png"),
        orb_small=PROJECT.resource_path("images/cards/orb_small.png"),
    )

    @PROJECT.card("RevenantStrike", basic=True)
    def make_revenant_strike():
        return RevenantStrike(color)

    PROJECT.add_character(
        CharacterBlueprint(
            identifier="revenant",
            character_name="The Revenant",
            description="Haunts the Spire with spectral blades.",
            assets=CharacterAssets(
                shoulder_image=PROJECT.resource_path("images/character/shoulder.png"),
                shoulder2_image=PROJECT.resource_path("images/character/shoulder2.png"),
                corpse_image=PROJECT.resource_path("images/character/corpse.png"),
            ),
            starting_deck=["RevenantStrike"] * 4 + ["RevenantDefend"] * 4,
            starting_relics=["RevenantLantern"],
            loadout_description="Devours the living for borrowed strength.",
        )
    )
```

Any resources referenced via `PROJECT.resource_path(...)` resolve to the mod’s resources folder (e.g. `revenant/images/...`). Drop your PNGs into the matching directories under `assets/revenant/` and the bundler will pick them up.

### 4. Implement cards with pure Python

Create `python/revenant_mod/cards/revenant_strike.py`:

```python
from modules.basemod_wrapper import cardcrawl, basemod


class RevenantStrike(basemod.abstracts.CustomCard):
    ID = "RevenantStrike"
    IMG = "revenant/images/cards/strike.png"
    COST = 1

    def __init__(self, color):
        super().__init__(
            self.ID,
            "Soul Strike",
            self.IMG,
            self.COST,
            "Deal {0} damage.",
            cardcrawl.cards.AbstractCard.CardType.ATTACK,
            color,
            cardcrawl.cards.AbstractCard.CardRarity.BASIC,
            cardcrawl.cards.AbstractCard.CardTarget.ENEMY,
        )
        self.baseDamage = 7

    def use(self, player, monster):
        action = cardcrawl.actions.common.DamageAction(
            monster,
            cardcrawl.cards.DamageInfo(player, self.damage, self.damageTypeForTurn),
            cardcrawl.actions.AbstractGameAction.AttackEffect.SLASH_DIAGONAL,
        )
        cardcrawl.dungeons.AbstractDungeon.actionManager.addToBottom(action)

    def upgrade(self):
        if not self.upgraded:
            self.upgradeName()
            self.upgradeDamage(3)

    def makeCopy(self):
        return type(self)(self.color)
```

Because the wrapper already exposes all Java packages, card code reads like a native Python module.

### 5. Load the mod in-game

Your `entrypoint.py` already calls `enable_runtime()`, which in turn registers every BaseMod hook. Import the entrypoint in your development REPL or point your ModTheSpire bootstrapper at it; the character, colour and cards become available instantly.

### 6. Produce a ModTheSpire bundle

Once art and scripts are ready, create a bundle directly from the layout:

```python
from pathlib import Path

from modules.basemod_wrapper import compileandbundle

options = project.bundle_options_from_layout(
    layout,
    additional_classpath=[Path("/path/to/SlayTheSpire/desktop-1.0.jar")],
)

bundle_path = compileandbundle(project, options)
print(f"Mod packaged at {bundle_path}")
```

Alternatively, skip manual options altogether:

```python
compileandbundle(
    project,
    layout=layout,
    additional_classpath=[Path("/path/to/SlayTheSpire/desktop-1.0.jar")],
)
```

`compileandbundle` generates the enum patch automatically, builds a `revenant_patches.jar`, writes the ModTheSpire manifest and copies your Python sources and assets into the correct locations. Drop the produced directory into `ModTheSpire/mods/` and enable it from the launcher.

### 7. Iterate rapidly

While developing you can call `project.enable_runtime()` in a Python REPL to hot reload cards and characters without rebuilding the bundle. The underlying `BaseMod.subscribe` machinery is hidden behind the scenes; all you need to do is edit your Python files and re-import them.

## Runtime helpers

- `BaseModEnvironment` exposes the resolved dependency jars and offers helper methods for building bundle options.
- `UnifiedSpireAPI` (available as `modules.basemod_wrapper.spire`) includes helpers for common StSLib actions and keyword manipulation.

## Bundling utilities

- `ProjectLayout` represents the scaffolded filesystem and offers helper properties for resource paths.
- `ModProject.bundle_options_from_layout()` produces ready-to-use `BundleOptions` instances.
- `compileandbundle()` accepts either explicit `BundleOptions` or a layout plus overrides and returns the final mod directory.

The wrapper aims to keep everything high level and pythonic while still exposing 100% of BaseMod and StSLib to power users. If you spot a missing helper add it directly, document the use case in `futures.md`, and the plugin manager will make it discoverable instantly.

# BaseMod Python Wrapper

The `modules.basemod_wrapper` package embeds the whole Slay the Spire modding
stack (BaseMod, StSLib and ModTheSpire) behind a Python-first façade. Importing
it spins up JPype, fetches the Java dependencies, exposes every package through
friendly dotted access and registers the entire module surface with the
repository wide plugin system. The goal is simple: write Slay the Spire mods in
idiomatic Python without touching JVM bootstrap code.

```python
from modules.basemod_wrapper import basemod, create_project

# Subscribe Python callables directly to BaseMod hooks.
basemod.BaseMod.subscribe(lambda *args: print("Hook invoked!"))

# Prepare a high-level project container that mirrors BaseMod concepts.
project = create_project(
    mod_id="revenant",
    name="The Revenant",
    author="OldBuddy",
    description="Soul-fuelled spectre who drains the Spire.",
)
```

## Exported surface

Importing `modules.basemod_wrapper` eagerly initialises a
`BaseModEnvironment`. The following objects become immediately available and
are also published to the global plugin manager (`plugins.PLUGIN_MANAGER`):

- `basemod`, `cardcrawl`, `modthespire`, `stslib` and `libgdx`: lazy package
  wrappers that mirror the JVM namespaces.
- `spire`: a `UnifiedSpireAPI` façade that bundles common StSLib helpers,
  keyword utilities and modifier registration.
- `create_project`, `ModProject`, `ProjectLayout`, `BundleOptions` and
  `compileandbundle`: a batteries-included workflow for describing colours,
  characters and cards before bundling them into a ModTheSpire-ready
  distribution.
- `SimpleCardBlueprint` and `register_simple_card`: declarative helpers for
  building everyday cards without hand-written subclasses.
- `Relic` and `RELIC_REGISTRY`: declarative relic base class with automatic
  registration and plugin-friendly discovery.
- `BaseModEnvironment`: access to the resolved dependency jars and default
  classpath should you need to integrate with custom tooling.

All of these symbols are exposed to plugins via
`PLUGIN_MANAGER.expose(...)` so third-party helpers can inspect or extend the
wrapper without tight coupling.

## Boot sequence and dependency handling

`ensure_jpype()` is called as soon as the package is imported. Behind the
scenes this delegates to the currently active JVM backend – JPype by default,
GraalPy when the experimental ``graalpy_runtime`` module is toggled on. Missing
bridge dependencies are installed on the fly before the wrapper downloads (or
reuses) the BaseMod, ModTheSpire and StSLib jars and launches the JVM with a
sane default classpath. Consumers simply import and go – no manual setup of
Java paths or environment variables.

### Adaptive GraalPy illustration swaps

Enabling ``experimental.graalpy_adaptive_illustrations`` provisions a
rule-driven Pillow pipeline that recolours inner card art based on
``Deck.statistics()`` snapshots. The module exposes the granular
``AdaptiveIllustrationEngine`` plus a high-level ``AdaptiveIllustrationDirector``
that plugs straight into ``Deck`` subclasses. See
``modules.basemod_wrapper.experimental.graalpy_adaptive_illustrations`` and the
``how to/graalpy-adaptive-illustrations.md`` recipe for end-to-end usage.

### GraalPy live tutorial narrator

The ``experimental.graalpy_live_tutorial_narrator`` module streams combat events
into a GraalPy narration queue.  Its ``TutorialNarrationEngine`` lets tooling
register voice lines, while ``TutorialNarrationDirector`` inspects
``Character``/``Deck`` definitions to generate onboarding hints automatically.
Documentation lives in
``modules.basemod_wrapper.experimental.graalpy_live_tutorial_narrator`` and
``how to/live-tutorial-narrator.md``.

## High level workflow

1. **Create a project** via `create_project(...)`. The resulting `ModProject`
   tracks colours, cards and characters, and can be imported by both build
   scripts and ModTheSpire entry points.
2. **Scaffold the file system** with `project.scaffold(...)`. The helper
   creates a ready-to-edit tree with Python packages, stub entrypoints and
   resource folders while preserving existing files.
3. **Define a colour** using `project.define_color(...)` and register cards via
   `project.card` or `project.add_simple_card`.
4. **Describe characters** using `CharacterBlueprint` from
   `modules.basemod_wrapper.project` and attach starting decks plus relics.
5. **Iterate in a REPL** by calling `project.enable_runtime()` (already done in
   the generated entrypoint) or `project.enable_mechanics_runtime()` when
   tinkering with experimental rule weaving mechanics. BaseMod hooks are
   registered for you so edits only require a reload.
6. **Bundle for ModTheSpire** through `compileandbundle(project, options)` or
   by reusing `project.bundle_options_from_layout(layout, ...)`.

### Project scaffolding in practice

```python
from modules.basemod_wrapper import create_project

project = create_project(
    mod_id="revenant",
    name="The Revenant",
    author="OldBuddy",
    description="Soul-fuelled spectre who drains the Spire.",
)
layout = project.scaffold("/path/to/workspace", package_name="revenant_mod")

# Generated structure (existing files are left untouched):
# revenant/
# ├── assets/revenant/images/{cards,character,orbs}/
# ├── assets/revenant/localizations/eng/cards.json
# └── python/revenant_mod/{__init__.py,cards/,entrypoint.py,project.py}
```

`project.py` ships with a `PROJECT` singleton and `configure()` stub. Importing
`entrypoint.py` (the ModTheSpire entry point) calls `enable_runtime()` which in
turn registers BaseMod listeners, colours and cards.

### Mechanics-only rule weaving projects

Some projects only need to tweak mechanics or keywords without introducing a
new character, deck or card pool.  The scaffolder now generates
`enable_mechanics_runtime()` alongside `enable_runtime()` plus a
`MECHANICS_ONLY` toggle in `entrypoint.py`.  Switching the flag to `True` (or
calling `PROJECT.enable_mechanics_runtime()` from your own bootstrap) activates
the `experimental.graalpy_rule_weaver` module, loads registered scripts and
applies eager mutations.

```python
from pathlib import Path
from modules.basemod_wrapper.experimental import graalpy_rule_weaver


def configure() -> None:
    PROJECT.register_mechanic_script_path(
        lambda: Path(__file__).with_name("mechanics") / "rules.json"
    )
    PROJECT.register_mechanic_script_resource(
        "revenant_mod.mechanics",
        "elite_buffs.yaml",
    )
    PROJECT.register_mechanic_mutation(
        graalpy_rule_weaver.MechanicMutation(
            identifier="revenant_global_tweak",
            description="Adjust base cards while playtesting mechanics-only builds.",
            apply=lambda context: graalpy_rule_weaver.MechanicActivation(
                identifier="revenant_global_tweak",
                revert_callbacks=(context.adjust_card_values("Strike_R", value=7),),
            ),
        ),
        activate=True,
    )


def enable_mechanics_runtime() -> None:
    configure()
    PROJECT.enable_mechanics_runtime()
```

Blueprint providers registered through `PROJECT.register_mechanic_blueprint_provider`
are forwarded to the rule weaver engine so scripts can iterate existing card
definitions (for example the `Deck.cards` classmethod on a `Deck` subclass).

## Card authoring options

### Full control: custom classes

Write traditional subclasses for complex behaviour by leaning on the exposed
JVM packages:

```python
from modules.basemod_wrapper import basemod, cardcrawl


class RevenantStrike(basemod.abstracts.CustomCard):
    ID = "RevenantStrike"
    IMG = "revenant/images/cards/revenant_strike.png"
    COST = 1

    def __init__(self, color_enum):
        super().__init__(
            self.ID,
            "Soul Strike",
            self.IMG,
            self.COST,
            "Deal {0} damage.",
            cardcrawl.cards.AbstractCard.CardType.ATTACK,
            color_enum,
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

Register the class with the project using either the decorator or the explicit
`add_card` helper:

```python
from .cards.revenant_strike import RevenantStrike


@PROJECT.card("RevenantStrike", basic=True)
def make_revenant_strike():
    return RevenantStrike(PROJECT.runtime_color_enum())
```

### Fast lane: `SimpleCardBlueprint`

For everyday attacks, blocks and power cards the wrapper offers a declarative
builder that handles class generation, keyword wiring and BaseMod registration.
Each blueprint is a dataclass with the following key fields:

| Field | Purpose |
| ----- | ------- |
| `identifier` | The internal card ID (`mod_id` prefix is added automatically during registration). |
| `title` | Display name in game. |
| `description` | Card text. Placeholders `{damage}`, `{block}`, `{magic}` and `{value}` auto-format based on the effect. |
| `cost` | Base energy cost. |
| `card_type` | `attack`, `skill` or `power`. Short aliases like `atk` are accepted. |
| `target` | One of `enemy`, `all_enemies`, `self`, `self_and_enemy`, `none` or `all`. |
| `rarity` | `basic`, `common`, `uncommon`, `rare`, `special` or `curse`. |
| `value` / `upgrade_value` | Base and upgrade numbers (damage, block or magic). |
| `effect` | Required for non-attacks – choose from `block`, `draw`, `energy`, `strength`, `dexterity`, `artifact`, `focus`, `weak`, `vulnerable`, `frail` or `poison`. |
| `color_id` | Optional override to register the card against an existing Base Game colour (e.g. `RED`). |
| `starter` | Set to `True` to drop the card into the basic pool. |
| `attack_effect` | Visual for damage actions (`slash_diagonal`, `slash_horizontal`, `blunt_heavy`, etc.). |
| `keywords` | Iterable of keyword flags. Canonical names (`innate`, `retain`, `stslib:Exhaustive`) are normalised automatically. |
| `keyword_values` / `keyword_upgrades` | Numeric keyword payloads (e.g. Exhaustive counts) and their upgrade deltas. |
| `card_uses` / `card_uses_upgrade` | Required for Exhaustive cards. Provides the base number of uses (and optional upgrade delta) that will be rendered via `{uses}`. |
| `image` | Resource path used when you already have card art on disk. |
| `inner_image_source` | Optional 500x380 image that will be processed into BaseMod-ready portrait/inner art pairs. |
| `localizations` | Mapping of language codes (`eng`, `fra`, `zhs`, etc.) to dictionaries describing translated titles/descriptions. Missing languages fall back to the base `title`/`description`. |

You can also call `blueprint.innerCardImage("art/Strike.png")` (or the snake
case alias `inner_card_image`) to register a source image after initialisation.

Additional helpers keep the declarative ergonomics intact:

- `secondary_value` / `secondary_upgrade` initialise and upgrade a secondary
  magic number without manual bookkeeping.
- `effects`, `on_draw` and `on_discard` accept dictionaries (or callables)
  describing extra payloads. They can reference card fields (`damage`, `block`,
  `magic`, `secondary`, etc.) and enqueue StSLib actions via the shared
  `UnifiedSpireAPI`.
- `register_keyword_placeholder(keyword, token)` lets you expose custom
  `{placeholder}` tokens in descriptions so third-party keywords render cleanly.

```python
from modules.basemod_wrapper import SimpleCardBlueprint

strike = SimpleCardBlueprint(
    identifier="RevenantStrike",
    title="Soul Strike",
    description="Deal {damage} damage.",
    cost=1,
    card_type="attack",
    target="enemy",
    rarity="basic",
    value=7,
    upgrade_value=3,
    starter=True,
    image=PROJECT.resource_path("images/cards/revenant_strike.png"),
)

guard = SimpleCardBlueprint(
    identifier="RevenantGuard",
    title="Soul Guard",
    description="Gain {block} Block. Exhaustive {uses}.",
    cost=1,
    card_type="skill",
    target="self",
    effect="block",
    rarity="common",
    value=12,
    upgrade_value=4,
    keywords=("innate", "retain", "stslib:Exhaustive"),
    card_uses=2,
    keyword_upgrades={"exhaustive": 1},
)

PROJECT.add_simple_card(strike)
PROJECT.add_simple_card(guard)

combo = SimpleCardBlueprint(
    identifier="RevenantCombo",
    title="Soul Combo",
    description="Gain {block} Block. Apply {secondary} Weak.",
    cost=1,
    card_type="skill",
    target="enemy",
    rarity="rare",
    effect="block",
    value=9,
    secondary_value=2,
    effects=[
        {
            "effect": "weak",
            "amount": "secondary",
            "follow_up": [
                {"action": "AddTemporaryHPAction", "args": ["monster", "player", "amount"]},
                {"action": "RemoveAllTemporaryHPAction", "kwargs": {"target": "player"}},
            ],
        }
    ],
    on_draw={"effect": "draw", "amount": 1},
    on_discard={"effect": "energy", "amount": 1},
    localizations={
        "fra": {
            "title": "Combo d'âme",
            "description": "Gagnez {block} Block. Appliquez {secondary} Faiblesse.",
        }
    },
)

PROJECT.add_simple_card(combo)
```

Each localisation entry accepts optional `upgrade_description` and
`extended_description` fields. Placeholder tokens (`{damage}`, `{block}`,
`{secondary}`, etc.) are automatically converted into the appropriate Slay the
Spire dynamic markers (for example `!D!`, `!B!`, `!M2!`) when localisation files
are generated.

When registered, the blueprint generates a full `CustomCard` subclass, wires the
correct BaseMod/StSLib actions (`DamageAction`, `GainBlockAction`,
`ApplyPowerAction`) and exposes it to the runtime. The resulting card IDs are
prefixed automatically with your project’s `mod_id`.

Exhaustive blueprints automatically translate the `{uses}` placeholder into the
`!stslib:ex!` runtime token so players always see the remaining uses without
sprinkling raw StSLib variables into descriptions.

#### Inner art automation

Calling `innerCardImage(...)` prompts the wrapper to clone and build the
[StSModdingToolCardImagesCreator](https://github.com/JohnnyBazooka89/StSModdingToolCardImagesCreator)
if necessary, then renders both the 250×190 in-game art and the 500×380 portrait.
The processed textures land under `assets/<mod_id>/images/cards/` with the
expected naming convention (`<Identifier>.png` and `<Identifier>_p.png`). Repeated
runs reuse cached builds and only reprocess when the source PNG changes.

### Manual registration

If you want to bypass `ModProject` entirely you can call
`register_simple_card(project, blueprint)` directly. This is primarily useful
inside custom tooling or plugin workflows.

## Relic authoring

Subclass :class:`modules.basemod_wrapper.relics.Relic` to register relics
without manual plumbing. The metaclass instantiates a prototype as soon as the
class is defined, stores it inside :data:`modules.basemod_wrapper.relics.RELIC_REGISTRY`
and wires the prototype into `ModProject` when
:meth:`modules.basemod_wrapper.project.ModProject.enable_runtime` runs.

```python
from modules.basemod_wrapper.relics import Relic


class AdaptiveTelemetryCore(Relic):
    mod_id = "adaptive_evolver"
    identifier = "adaptive_evolver:telemetry_core"
    display_name = "Adaptive Telemetry Core"
    description_text = "Records combat telemetry and boosts evolution planning."
    tier = "RARE"
    landing_sound = "MAGICAL"
    relic_pool = "SHARED"
    image = "adaptive_evolver/images/relics/telemetry_core.png"

    def on_combat_begin(self, mod, recorder):
        recorder.add_note("Telemetry Core calibrates to the encounter.")

    def on_plan_finalised(self, mod, plan):
        plan.notes = tuple(sorted(set(plan.notes + ("Telemetry Core boost",))))
```

Projects can also opt-in manually via
``modules.basemod_wrapper.relics.RELIC_REGISTRY.install_on_project(project)``
when wiring mechanics-only experiences.

## Runtime iteration

- `project.enable_runtime()` registers the colour, cards and characters with
  BaseMod immediately. The generated `entrypoint.py` handles this for you.
- The `spire` façade exposes keyword helpers (`spire.apply_keyword`) so you can
  toggle StSLib fields without repeating reflection-heavy code.
- Damage/block modifier helpers (`spire.add_damage_modifier`,
  `spire.add_block_modifier`) wrap the relevant StSLib managers.

Import `python/<package>/entrypoint.py` in a live JPype session to hot reload
changes without re-bundling.

## Bundling for ModTheSpire

`compileandbundle(project, options)` produces a ready-to-drop directory with a
patch jar, manifest and copied Python/assets. Build options can either be passed
explicitly or sourced from a scaffolded layout:

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

Behind the scenes the bundler writes enum patches, resolves dependencies,
assembles the ModTheSpire manifest and copies assets/Python sources into the
output directory. Drop the resulting folder into `ModTheSpire/mods/` and enable
it from the launcher.

## Extensible keyword engine

Subclasses of `modules.basemod_wrapper.keywords.Keyword` automatically register
themselves and can be mixed with the canonical StS keywords inside
`SimpleCardBlueprint` declarations. The base class exposes high level proxies
for manipulating combat state:

- `self.hp`, `self.hp.current` and `self.hp.permanent` control the player's
  temporary, current and maximum health.
- `self.player` exposes block, energy and every canonical buff/debuff through
  properties (`keyword.player.strength = 5`, `keyword.player.intangible += 1`,
  etc.).
- `self.enemies` resolves the targeted monster, a random foe or the full room
  and offers fluent power access (`self.enemies.target.weak = 2`,
  `for enemy in self.enemies.all(): enemy.block = 10`).
- `self.cards.hand[index]` / `self.cards.draw_pile[index]` return
  `CardEditor` helpers that mirror the `SimpleCardBlueprint` fields and can
  persist modifications for the combat, the current run or forever. Permanent
  edits are stored in `persistent_cards.json` and automatically reapplied at the
  start of each new dungeon via the keyword scheduler.
- `self.cards.hand.add_by_name("Bash")` accepts either card IDs or the title of
  any card present in the player's decks/pools and pushes a copy into the hand.

Scheduling is controlled through `self.when` (`now`, `next`, `random`,
`nextend`, `randomend`), `self.turn_offset` for deterministic delays and
`self.random_turn_range` for probabilistic triggers. Keywords scheduled for a
future turn are executed by the shared `KeywordScheduler`, ensuring they play
nicely with canonical effects and other custom keywords.

## Plugin integration

Every public symbol in the wrapper is shared with the repository-wide plugin
system. External tooling can consume the plugin manifest to discover new
capabilities, register additional blueprints or introspect the exported Java
packages:

```python
from plugins import PLUGIN_MANAGER

context = PLUGIN_MANAGER.exposed
wrapper = context["basemod_wrapper"]  # Lazily imported module alias.
blueprint_cls = context["SimpleCardBlueprint"]
```

The plugin namespace is immutable (`MappingProxyType`) which keeps the surface
predictable while still allowing plugins to import modules lazily through the
provided aliases.

## Troubleshooting tips

- Ensure a Java runtime is available on `PATH`. JPype will raise a descriptive
  error if the JVM cannot be located.
- The first call to `innerCardImage` triggers a one-time build of the card image
  tool. Subsequent invocations reuse the compiled binary.
- If you need to inspect the raw classpath, check
  `basemod_environment.classpath` from the plugin manager or directly via the
  imported module.

The wrapper is designed to stay thin while exposing 100% of the BaseMod and
StSLib APIs. File issues or extend it directly – the plugin manager guarantees
that new helpers remain discoverable for downstream tooling.

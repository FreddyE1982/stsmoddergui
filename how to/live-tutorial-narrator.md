# How to add a GraalPy live tutorial narrator

This recipe walks through wiring the `experimental.graalpy_live_tutorial_narrator`
module into a fully fledged mod.  We start by declaring a deck, spin up a
`Character`, activate the experiment, and script both granular and high-level
voice lines before bundling.

## 1. Describe the starter deck

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
        identifier="BuddyBrew",
        title="Buddy Brew",
        description="Gain {block} Block and apply {poison} Poison.",
        cost=1,
        card_type="skill",
        target="enemy",
        effect="block",
        rarity="basic",
        value=6,
        upgrade_value=3,
        keywords=("poison",),
        keyword_values={"poison": 2},
        starter=True,
    ).innerCardImage(str(ART_ROOT / "BuddyBrew.png"))
)
```

## 2. Declare the character

```python
from modules.modbuilder.character import Character


class Buddy(Character):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Buddy"
        self.mod_id = "buddy"
        self.author = "Deck Docs"
        self.description = "Learns card flow through narrated hints."
        self.start.deck = BuddyStarter
        self.start.relics = ["Burning Blood"]
```

## 3. Activate the experimental narrator

```python
from modules.basemod_wrapper import experimental

narrator = experimental.on("graalpy_live_tutorial_narrator")
assert experimental.is_active("graalpy_runtime")
```

The module guarantees `experimental.graalpy_runtime` is also active so the
engine runs inside the GraalPy interpreter.

## 4. Script the high-level director

```python
buddy = Buddy()

director = narrator.launch_tutorial_narrator(
    buddy,
    default_voice="mentor",
    highlight_keywords=("poison",),
)

director.register_intro_line(
    "{player}, we begin with {deck_total_cards} cards – keep the flow steady.",
    priority=90,
)

director.script_from_deck(highlight_keywords=("poison",))

director.apply_to_character()
```

At this point `buddy.tutorial_narration` contains a manifest suitable for UI or
runtime playback helpers.

## 5. Register granular reminders for advanced cues

```python
engine = narrator.get_engine()

engine.register_voice_line(
    narrator.VoiceLine(
        identifier="buddy_low_health",
        event_type=narrator.NarrationEventType.DAMAGE_TAKEN,
        script="{player}, grit your teeth – you're down to {current_hp} HP!",
        priority=40,
        metadata={"category": "danger"},
    ),
    replace=True,
)
```

Later, feed a `NarrationEvent` when the player's health dips too low to queue
the warning.

## 6. Bundle the project

```python
from pathlib import Path

from modules.basemod_wrapper import compileandbundle, create_project

project = create_project(
    mod_id="buddy",
    name="Buddy",
    author="Deck Docs",
    description="Learns card flow through narrated hints.",
)

project.register_character(buddy)

compileandbundle(
    project,
    project.default_bundle_options(
        python_source=Path("python"),
        assets_source=Path("resources/Buddy"),
        output_directory=Path("dist"),
    ),
)
```

The resulting bundle now ships with a GraalPy-powered narrator ready to react to
combat events and deck flow.

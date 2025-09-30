# Stage a cinematic boss rivalry with GraalPy

This walkthrough shows how to wire up a full mod that leans on the
`experimental.graalpy_cinematic_rivalries` module. We start with the familiar
`Deck`/`Character` workflow, then let the cinematic rivalry director feed live
telemetry back into the encounter script.

## 1. Prepare decks and a character shell

```python
from pathlib import Path

from modules.modbuilder import Deck
from modules.basemod_wrapper import SimpleCardBlueprint

CARD_ART = Path("resources/Buddy/images/cards/inner")


class BuddyStarter(Deck):
    """Straightforward opening hand."""


BuddyStarter.addCard(
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
    ).innerCardImage(str(CARD_ART / "BuddyDefend.png"))
)
```

Populate an unlockable deck exactly the same way, then build a character class
using `modules.modbuilder.Character`. See `how to/basic-character.md` if you
need a refresher on configuring colours, assets, and validation.

## 2. Activate the GraalPy cinematic rivalry feature

```python
from modules.basemod_wrapper import experimental

rivalries = experimental.on("graalpy_cinematic_rivalries")
```

Activating the module automatically toggles `experimental.graalpy_runtime` so
the repository runs under GraalPy. The returned module exposes both the
low-level `RivalryEngine` and the high-level `CinematicRivalryDirector` helper.

## 3. Describe the encounter script

```python
from modules.modbuilder.character import Character


class Buddy(Character):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Buddy"
        self.mod_id = "buddy"
        self.start.deck = BuddyStarter
        self.description = "Fearless fighter with a vendetta against the Guardian."


guardian_intro = rivalries.RivalryScript(
    boss_id="guardian",
    rivalry_name="Guardian Rivalry",
    frames=(
        rivalries.IntentFrame(
            turn=1,
            title="Opening Gambit",
            description="Guardian flexes crystalline armour.",
            actions=(rivalries.IntentAction(action="buff", value=3.0),),
        ),
    ),
)

director = rivalries.launch_cinematic_rivalry(
    "guardian",
    narrative="Guardian versus Buddy",
    initial_script=guardian_intro,
    soundtrack="audio/guardian.ogg",
)

buddy = Buddy()
director.apply_to_character(buddy)
```

`launch_cinematic_rivalry` creates a director that keeps the character's
`cinematic_rivalry_scripts` mapping in sync with the evolving intent script.
The dictionary contains the generated `RivalryScript`, the narrative blurb, and
an optional soundtrack hint so runtime overlays can pick an appropriate mix.

## 4. Stream telemetry into the rivalry

```python
turn_events = [
    rivalries.BossTelemetryEvent(
        boss_id="guardian",
        turn=1,
        event_type=rivalries.TelemetryEventType.DAMAGE_DEALT,
        payload={"amount": 16},
    ),
    rivalries.BossTelemetryEvent(
        boss_id="guardian",
        turn=1,
        event_type=rivalries.TelemetryEventType.CARD_PLAYED,
        payload={"card": "BuddyStrike", "damage": 8},
    ),
]

director.record_turn(turn_events)

latest_script = director.current_script()
for frame in latest_script.frames:
    print(frame.turn, frame.title, frame.actions)
```

The bundled `AdaptiveDamageTrainer` keeps a rolling average of damage dealt and
uses it to modulate the next turn's aggression. You can register additional
trainers with `rivalries.register_trainer` – they receive every telemetry event
and can replace or append frames as required.

## 5. Bundle and test the mod

Call `Buddy.createMod` exactly like in the other how-to guides. Because the
cinematic rivalry runtime is purely Python, it travels with the rest of the
bundle. When the mod runs under GraalPy the rivalry engine reacts instantly to
combat telemetry, rewriting intents without any JPype overhead.

To add live dashboards or overlays, subscribe to `rivalries.register_listener`
or to the plugin exposure `experimental_graalpy_rivalries_record` – both receive
the continuously updated `RivalryScript` instances.

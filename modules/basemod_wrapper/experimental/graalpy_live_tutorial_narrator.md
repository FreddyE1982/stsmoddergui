# GraalPy live tutorial narrator

The `experimental.graalpy_live_tutorial_narrator` module streams combat and
deck telemetry into a narration queue hosted by the GraalPy backend.  It packs
two complementary APIs so mod teams can choose between granular control and a
turn-key helper.

## Granular engine: `TutorialNarrationEngine`

```python
from modules.basemod_wrapper import experimental

narrator = experimental.on("graalpy_live_tutorial_narrator")
engine = narrator.get_engine()

line = narrator.VoiceLine(
    identifier="buddy_strike_hint",
    event_type=narrator.NarrationEventType.CARD_DRAWN,
    script="{player}, lean on {card_title} when you need burst damage.",
    priority=25,
    metadata={"category": "card"},
)

engine.register_voice_line(line, replace=True)

event = narrator.NarrationEvent(
    event_type=narrator.NarrationEventType.CARD_DRAWN,
    player="Buddy",
    turn=1,
    metadata={"card_id": "BuddyStrike", "card_title": "Buddy Strike"},
    deck_statistics=my_deck.statistics(),
)

cue = engine.ingest_event(event, voice_profile="mentor")
print(cue.text)
```

The engine keeps a bounded queue of `NarrationCue` objects.  Voice lines can be
conditioned on metadata, throttled with cooldowns, and observed via listeners
registered through `engine.subscribe`.

## High level helper: `TutorialNarrationDirector`

```python
from modules.modbuilder.deck import Deck
from modules.modbuilder.character import Character


class BuddyDeck(Deck):
    display_name = "Buddy Starter"


class Buddy(Character):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Buddy"
        self.mod_id = "buddy"
        self.start.deck = BuddyDeck


director = narrator.launch_tutorial_narrator(
    Buddy(),
    default_voice="mentor",
    highlight_keywords=("poison",),
)

director.register_intro_line(
    "{player}, we begin with {deck_total_cards} cards – steer the run one turn at a time.",
    priority=80,
)

director.script_from_deck(highlight_keywords=("poison",))

director.apply_to_character()
```

The director inspects the starting deck, generates scripted hints for each
card, and exposes helpers such as:

- `queue_run_start(player_name="Buddy")` – queue an onboarding voice line.
- `record_card_draw("BuddyStrike", player_name="Buddy")` – annotate specific draws.
- `record_keyword_trigger("poison")` – vocalise keyword spikes.

Activating the module automatically enables `experimental.graalpy_runtime` so
voice generation runs on GraalPy.  Plugin authors can access the engine,
director registry, and launch helper via `plugins.PLUGIN_MANAGER.exposed` using
the names `experimental_graalpy_narration_engine`,
`experimental_graalpy_narration_directors`, and
`experimental_graalpy_narration_launch`.

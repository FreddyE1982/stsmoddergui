# GraalPy cinematic rivalries

The `experimental.graalpy_cinematic_rivalries` module pairs the repository's
GraalPy backend with a telemetry-driven intent engine. Activating the module
ensures `experimental.graalpy_runtime` is toggled on so the BaseMod wrapper runs
inside the GraalVM process. Two complementary APIs are provided:

## Granular: `RivalryEngine`

```python
from modules.basemod_wrapper import experimental

rivalries = experimental.on("graalpy_cinematic_rivalries")
engine = rivalries.get_engine()

def echo_updates(script):
    print("New script", script.frames[-1].description)

engine.register_listener(echo_updates, boss_id="guardian")
engine.register_trainer(rivalries.AdaptiveDamageTrainer(aggression_multiplier=1.6))

engine.set_initial_script(
    rivalries.RivalryScript(
        boss_id="guardian",
        rivalry_name="Guardian Rivalry",
        frames=(
            rivalries.IntentFrame(
                turn=1,
                title="Opening Gambit",
                description="Guardian studies the player's stance.",
                actions=(
                    rivalries.IntentAction(action="buff", value=3.0),
                ),
            ),
        ),
    )
)

engine.ingest_event(
    rivalries.BossTelemetryEvent(
        boss_id="guardian",
        turn=1,
        event_type=rivalries.TelemetryEventType.DAMAGE_DEALT,
        payload={"amount": 18},
    )
)
```

The engine keeps rolling averages of combat damage via
`AdaptiveDamageTrainer`, rewrites intent frames for the following turn, and
notifies registered listeners. Additional trainers can subscribe to other event
types and merge their outputs into the evolving script.

## High level: `CinematicRivalryDirector`

```python
from modules.basemod_wrapper import experimental
from modules.modbuilder.character import Character

rivalries = experimental.on("graalpy_cinematic_rivalries")

director = rivalries.launch_cinematic_rivalry(
    "guardian",
    narrative="Guardian versus the fearless Buddy.",
    soundtrack="audio/guardian.ogg",
)

character = Character()
director.apply_to_character(character)

director.record_turn(
    [
        rivalries.BossTelemetryEvent(
            boss_id="guardian",
            turn=1,
            event_type=rivalries.TelemetryEventType.DAMAGE_DEALT,
            payload={"amount": 12},
        )
    ]
)

print(character.cinematic_rivalry_scripts["guardian"]["script"].frames)
```

The director keeps the `Character` instance synchronised with the telemetry
engine. Any listeners registered on the granular API receive the same script
updates, making it straightforward to broadcast rivalries to UI overlays or
external tooling.

Both APIs are exposed through `plugins.PLUGIN_MANAGER` under the names
`experimental_graalpy_rivalries_engine` and
`experimental_graalpy_rivalries_record`, giving plugins full access to the
intent pipeline.

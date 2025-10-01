# GraalPy coaching ghosts

The `experimental.graalpy_coaching_ghosts` module brings leaderboard ghosts
into the GraalPy runtime so players can race against top runs while receiving
live coaching prompts. Activating the feature automatically enables
`experimental.graalpy_runtime` and exposes two complementary APIs.

## Granular engine: `GhostPlaybackEngine`

```python
from pathlib import Path

from modules.basemod_wrapper import experimental

ghosts = experimental.on("graalpy_coaching_ghosts")
engine = ghosts.get_engine()

# Register ghost runs from a JSON manifest.
engine.load_runs(Path("leaderboards/buddy-top-10.json"))

snapshot = engine.start_session(
    "buddy_top_run",
    player_name="Buddy",
    metadata={"ascension": 15},
)

def announce(update):
    if update.matched:
        print("Kept pace with", update.ghost_action.description)
    else:
        print("Ghost diverged: ", update.recommendation)

engine.register_listener(announce, session_id=snapshot.session_id)

update = engine.record_player_action(
    snapshot.session_id,
    ghosts.ActionRecord(
        actor=ghosts.ActionActor.PLAYER,
        floor=1,
        turn=1,
        action_type=ghosts.GhostActionType.PLAY_CARD,
        description="Buddy Strike on Jaw Worm",
        payload={"card_id": "BuddyStrike", "damage": 9},
    ),
)

print("Score delta", update.score_delta)
```

The engine keeps a per-session history, exposes upcoming ghost actions via
`preview_actions`, and broadcasts every recommendation through
`plugins.PLUGIN_MANAGER` so tooling can surface overlays or dashboards.

## High level director: `CoachingGhostDirector`

```python
from modules.modbuilder.deck import Deck


class BuddyDeck(Deck):
    display_name = "Buddy"


director = ghosts.launch_coaching_ghosts(
    BuddyDeck,
    default_player_name="Buddy",
    leaderboard=Path("leaderboards/buddy-top-10.json"),
)

session = director.start_session("buddy_top_run")

updates = director.record_turn(
    session.session_id,
    [
        {
            "floor": 1,
            "turn": 1,
            "action_type": ghosts.GhostActionType.PLAY_CARD,
            "description": "Buddy Strike",
            "payload": {"card_id": "BuddyStrike", "damage": 9},
        },
        {
            "floor": 1,
            "turn": 1,
            "action_type": ghosts.GhostActionType.END_TURN,
            "description": "End turn",
        },
    ],
)

for update in updates:
    print(update.recommendation)

from modules.modbuilder.character import Character

character = Character()
director.apply_to_character(character)
print(character.coaching_ghost_sessions[session.session_id]["pace_delta"])
```

The director mirrors the deck metadata inside each session, making it easy to
sync race information back into a character definition before bundling. Plugin
authors can access the same helpers through the exposed entries
`experimental_graalpy_ghosts_engine`, `experimental_graalpy_ghosts_sessions`, and
`experimental_graalpy_ghosts_launch` on `plugins.PLUGIN_MANAGER`.

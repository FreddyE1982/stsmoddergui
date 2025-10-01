`experimental.graalpy_coaching_ghosts` module. The walkthrough mirrors the
established Deck/Character workflow so you can bolt the ghost coach onto an
existing project without wrestling with BaseMod plumbing.

## 1. Describe the starter deck

```python
from pathlib import Path

from modules.modbuilder import Deck
from modules.basemod_wrapper import SimpleCardBlueprint

CARD_ART = Path("resources/Buddy/images/cards/inner")


class BuddyStarter(Deck):
    """Reliable opener for the Buddy archetype."""


BuddyStarter.addCard(
    SimpleCardBlueprint(
        identifier="BuddyStrike",
        title="Buddy Strike",
        description="Deal {damage} damage.",
        cost=1,
        card_type="attack",
        target="enemy",
        rarity="basic",
        value=8,
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
        value=6,
        upgrade_value=3,
        starter=True,
    ).innerCardImage(str(CARD_ART / "BuddyDefend.png"))
)
```

Reuse the pattern above to populate the rest of the deck. The director later
inspects `BuddyStarter.statistics()` to tag sessions with deck metadata.

## 2. Wire up a character shell

```python
from modules.modbuilder.character import Character


class Buddy(Character):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Buddy"
        self.mod_id = "buddy"
        self.description = "Enthusiastic striker chasing leaderboard ghosts."
        self.start.deck = BuddyStarter
```

Configure colours, art, and unlockable decks the same way the
`how to/basic-character.md` recipe does.

## 3. Activate the coaching ghost feature

```python
from modules.basemod_wrapper import experimental

ghosts = experimental.on("graalpy_coaching_ghosts")
```

The call toggles both `experimental.graalpy_coaching_ghosts` and
`experimental.graalpy_runtime`, provisioning the GraalPy backend on demand. The
returned module exposes dataclasses (`ActionRecord`, `GhostRun`) and helpers for
both API tiers.

## 4. Import leaderboard ghosts

Create a JSON file (`leaderboards/buddy-top-10.json`) containing one or more
ghost runs:

```json
[
  {
    "ghost_id": "buddy_top_run",
    "player_name": "Buddy",
    "score": 890,
    "ascension_level": 15,
    "actions": [
      {
        "floor": 1,
        "turn": 1,
        "action_type": "play_card",
        "description": "Buddy Strike on Jaw Worm",
        "payload": {"card_id": "BuddyStrike", "damage": 9}
      },
      {
        "floor": 1,
        "turn": 1,
        "action_type": "end_turn",
        "description": "End turn"
      }
    ],
    "metadata": {"notes": "High-tempo opener"}
  }
]
```

Load it through the high level director:

```python
from pathlib import Path

director = ghosts.launch_coaching_ghosts(
    BuddyStarter,
    default_player_name="Buddy",
    leaderboard=Path("leaderboards/buddy-top-10.json"),
)
```

`launch_coaching_ghosts` registers the ghost runs with the granular engine and
keeps a deck-specific director handy for future sessions.

## 5. Start a coaching session during playtests

```python
session = director.start_session("buddy_top_run")

updates = director.record_turn(
    session.session_id,
    [
        {
            "floor": 1,
            "turn": 1,
            "action_type": ghosts.GhostActionType.PLAY_CARD,
            "description": "Buddy Strike on Jaw Worm",
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
```

Every recorded turn yields `CoachingUpdate` entries with pacing and score deltas.
Plugins can subscribe to `experimental_graalpy_ghosts_engine` for the same feed.

## 6. Attach run summaries to the character

```python
character = Buddy()
director.apply_to_character(character)

for session_id, details in character.coaching_ghost_sessions.items():
    print(session_id, details["pace_delta"], details["recommendations"][-1])
```

`apply_to_character` stores the most recent snapshot for each active session in
`character.coaching_ghost_sessions`. When you later call `Buddy.createMod`, the
metadata travels with the bundle so in-game overlays or plugins can reference
the pace differentials.

## 7. Bundle and iterate

Compile and bundle the mod exactly like the other tutorials. As you playtest new
runs, feed the resulting ghost logs back into the JSON manifest and re-run the
session recorder – the GraalPy backend keeps everything in Python, so no BaseMod
patches are required to keep the coaching overlay fresh.

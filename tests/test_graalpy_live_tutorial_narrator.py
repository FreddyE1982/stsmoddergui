from __future__ import annotations

import os
from pathlib import Path
from typing import List

import pytest

from modules.basemod_wrapper import experimental
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.card_assets import ensure_pillow
from modules.modbuilder.character import Character
from modules.modbuilder.deck import Deck
from plugins import PLUGIN_MANAGER


def _write_fake_graalpy(executable: Path) -> None:
    executable.write_text(
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("GraalPy 23.0.0")
    sys.exit(0)

if len(args) >= 3 and args[0:2] == ["-m", "pip"]:
    command = args[2]
    if command == "install":
        print("Simulated install", " ".join(args[3:]))
        sys.exit(0)
    if command == "show" and len(args) >= 4:
        package = args[3]
        print(f"Name: {package}")
        print("Version: 10.1.0")
        sys.exit(0)

print("Unhandled GraalPy invocation", args, file=sys.stderr)
sys.exit(0)
""",
        encoding="utf8",
    )
    executable.chmod(0o755)


class BuddyDeck(Deck):
    display_name = "Buddy Starter"


def _prepare_deck(art_root: Path) -> None:
    BuddyDeck.clear()
    BuddyDeck.addCard(
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
        ).innerCardImage(str(art_root / "BuddyStrike.png"))
    )
    BuddyDeck.addCard(
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
        ).innerCardImage(str(art_root / "BuddyBrew.png"))
    )


class Buddy(Character):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Buddy"
        self.mod_id = "buddy"
        self.description = "Narrated tutorial flow."
        self.start.deck = BuddyDeck


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_live_tutorial_narrator_pipeline(tmp_path: Path, use_real_dependencies: bool) -> None:
    for name in (
        "graalpy_live_tutorial_narrator",
        "graalpy_runtime",
    ):
        try:
            experimental.off(name)
        except Exception:
            pass

    env_backup = {
        key: os.environ.get(key)
        for key in (
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE",
            "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
            "GRAALPY_HOME",
        )
    }

    try:
        art_root = tmp_path / "art"
        art_root.mkdir()
        image_module = ensure_pillow()
        for filename in ("BuddyStrike.png", "BuddyBrew.png"):
            image = image_module.new("RGBA", (500, 380), (32, 64, 128, 255))
            image.save(art_root / filename)

        _prepare_deck(art_root)

        if use_real_dependencies:
            graalpy_home = tmp_path / "graalpy_home"
            (graalpy_home / "bin").mkdir(parents=True)
            executable = graalpy_home / "bin" / "graalpy"
            _write_fake_graalpy(executable)
            os.environ["GRAALPY_HOME"] = str(graalpy_home)
        else:
            simulator = tmp_path / "simulated_graalpy"
            simulator.write_text(
                "#!/usr/bin/env python3\nimport sys; sys.exit(0)\n",
                encoding="utf8",
            )
            simulator.chmod(0o755)
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE"] = "1"
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE"] = str(simulator)

        module = experimental.on("graalpy_live_tutorial_narrator")
        assert experimental.is_active("graalpy_runtime"), "Activation must enable GraalPy runtime."

        engine = module.get_engine()

        captured: List[module.NarrationCue] = []
        engine.subscribe(captured.append)

        card_hint = module.VoiceLine(
            identifier="buddy_strike_hint",
            event_type=module.NarrationEventType.CARD_DRAWN,
            script="{player}, line up {card_title} for big hits.",
            priority=35,
            metadata={"category": "card"},
        )
        engine.register_voice_line(card_hint, replace=True)

        event = module.NarrationEvent(
            event_type=module.NarrationEventType.CARD_DRAWN,
            player="Buddy",
            turn=1,
            metadata={
                "card_id": "BuddyStrike",
                "card_title": "Buddy Strike",
            },
            deck_statistics=BuddyDeck.statistics(),
        )

        cue = engine.ingest_event(event, voice_profile="mentor")
        assert cue is not None
        assert "Buddy Strike" in cue.text
        assert captured and captured[-1] == cue
        assert engine.pending_cues()[0] == cue
        assert engine.pop_next_cue() == cue

        buddy = Buddy()
        director = module.launch_tutorial_narrator(
            buddy,
            default_voice="mentor",
            highlight_keywords=("poison",),
        )

        intro_cues = director.queue_run_start(player_name="Buddy")
        assert intro_cues and intro_cues[0] is not None

        draw_cue = director.record_card_draw("BuddyBrew", player_name="Buddy", turn=1)
        assert draw_cue is not None
        assert "Buddy Brew" in draw_cue.text

        keyword_cue = director.record_keyword_trigger("poison", player_name="Buddy")
        assert keyword_cue is None or "poison" in " ".join(keyword_cue.metadata.keys())

        payload = director.apply_to_character()
        assert payload["voice_profile"] == "mentor"
        assert "script_summary" in payload
        assert getattr(buddy, "tutorial_narration") == payload

        exposed = PLUGIN_MANAGER.exposed
        assert exposed["experimental_graalpy_narration_engine"] is engine
        directors = exposed["experimental_graalpy_narration_directors"]
        assert buddy.mod_id in directors
        assert directors[buddy.mod_id] is director
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for name in (
            "graalpy_live_tutorial_narrator",
            "graalpy_runtime",
        ):
            try:
                experimental.off(name)
            except Exception:
                pass
        BuddyDeck.clear()

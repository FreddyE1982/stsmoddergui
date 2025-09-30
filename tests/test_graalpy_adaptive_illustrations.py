from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from modules.basemod_wrapper import experimental
from modules.basemod_wrapper.cards import SimpleCardBlueprint
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


def _write_card_art(path: Path, color: tuple[int, int, int]) -> None:
    image = Image.new("RGBA", (500, 380), color + (255,))
    image.save(path)


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_adaptive_illustration_workflow(tmp_path: Path, use_real_dependencies: bool) -> None:
    for name in ("graalpy_adaptive_illustrations", "graalpy_runtime"):
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

    class BuddyDeck(Deck):
        display_name = "Buddy Deck"

    BuddyDeck.clear()

    try:
        if use_real_dependencies:
            graalpy_home = tmp_path / "graalpy_home"
            (graalpy_home / "bin").mkdir(parents=True)
            executable = graalpy_home / "bin" / "graalpy"
            _write_fake_graalpy(executable)
            os.environ["GRAALPY_HOME"] = str(graalpy_home)
        else:
            simulator = tmp_path / "simulated_graalpy"
            simulator.write_text("#!/usr/bin/env python3\nimport sys; sys.exit(0)\n", encoding="utf8")
            simulator.chmod(0o755)
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE"] = "1"
            os.environ["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE"] = str(simulator)

        art_root = tmp_path / "art"
        art_root.mkdir()
        strike_path = art_root / "BuddyStrike.png"
        defend_path = art_root / "BuddyDefend.png"
        _write_card_art(strike_path, (20, 40, 80))
        _write_card_art(defend_path, (40, 80, 20))

        strike = SimpleCardBlueprint(
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
        ).innerCardImage(str(strike_path))

        defend = SimpleCardBlueprint(
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
        ).innerCardImage(str(defend_path))

        BuddyDeck.addCard(strike)
        BuddyDeck.addCard(defend)

        module = experimental.on("graalpy_adaptive_illustrations")
        assert experimental.is_active("graalpy_runtime"), "Activating adaptive illustrations must enable GraalPy."

        engine = module.get_engine()

        granular_context = module.IllustrationSwapContext(
            deck_statistics=BuddyDeck.statistics(),
            relics=("Champion Belt",),
            keyword_counts={"poison": 2},
            metadata={"act": 2},
        )

        engine.register_rule(
            module.IllustrationSwapRule(
                card_id="BuddyStrike",
                transform=module.create_tint_transform((255, 80, 80), intensity=0.7),
                name="berserk",
            ),
            replace=True,
        )

        generated_path = engine.apply_to_blueprint(strike, granular_context)
        assert generated_path is not None
        assert generated_path.exists()

        with Image.open(generated_path) as handle:
            red, green, blue, _ = handle.getpixel((20, 20))
        assert red > green and red > blue, "Tint transform must skew the colour palette."

        director = module.launch_adaptive_illustrations(
            BuddyDeck,
            asset_root=art_root,
            output_directory=tmp_path / "adaptive_output",
        )

        director.register_rarity_palette(
            "basic",
            color=(30, 180, 240),
            intensity=0.55,
            name="aqua-basic",
        )

        director.register_card_override(
            "BuddyDefend",
            module.create_keyword_glow_transform("poison", color=(0, 255, 0), radius=4, intensity=0.7),
        )

        director_context = director.build_context(
            relics=("Toxic Egg", "Lantern"),
            keyword_counts={"poison": 3},
            metadata={"note": "integration"},
        )

        results = director.apply(director_context)
        assert "BuddyDefend" in results
        assert results["BuddyDefend"].exists()
        assert Path(strike.inner_image_source).exists()

        exposed_engine = PLUGIN_MANAGER.exposed["experimental_graalpy_illustrations_engine"]
        assert exposed_engine is engine
        assert "experimental_graalpy_illustrations_launch" in PLUGIN_MANAGER.exposed
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for name in ("graalpy_adaptive_illustrations", "graalpy_runtime"):
            try:
                experimental.off(name)
            except Exception:
                pass
        BuddyDeck.clear()

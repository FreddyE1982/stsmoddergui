# Adaptive GraalPy illustration swaps

The `experimental.graalpy_adaptive_illustrations` module pairs the GraalPy
runtime with Pillow-powered transformations so decks can recolour and remix card
art during a run.  Activating the experiment ensures
`experimental.graalpy_runtime` is toggled on, exposes the adaptive engine via
`plugins.PLUGIN_MANAGER`, and registers both the granular and high-level APIs.

## Granular engine usage

```python
from modules.basemod_wrapper import experimental

illustrations = experimental.on("graalpy_adaptive_illustrations")
engine = illustrations.get_engine()

context = illustrations.IllustrationSwapContext(
    deck_statistics=my_deck.statistics(),
    relics=("Champion Belt",),
    keyword_counts={"poison": 2},
    metadata={"act": 2},
)

engine.register_rule(
    illustrations.IllustrationSwapRule(
        card_id="BuddyStrike",
        transform=illustrations.create_tint_transform((255, 64, 64), intensity=0.6),
        name="berserk",
    ),
    replace=True,
)

engine.apply_to_blueprint(strike_blueprint, context)
```

The engine maintains a rule registry keyed by card identifier and rule slug.
Rules may return any Pillow `Image` instance.  By default the generated textures
are written to `lib/graalpy/adaptive_illustrations/<deck>/`.

## High level director

```python
from pathlib import Path

from modules.basemod_wrapper import experimental
from modules.modbuilder.deck import Deck


class BuddyDeck(Deck):
    display_name = "Buddy"


illustrations = experimental.on("graalpy_adaptive_illustrations")
director = illustrations.launch_adaptive_illustrations(
    BuddyDeck,
    asset_root=Path("resources/Buddy/images/cards/inner"),
)

director.register_rarity_palette(
    "basic",
    color=(30, 180, 240),
    intensity=0.55,
)

director.register_card_override(
    "BuddyDefend",
    illustrations.create_keyword_glow_transform(
        "poison",
        color=(0, 255, 0),
        radius=4,
        intensity=0.7,
    ),
)

results = director.apply()
```

The director caches each blueprint's original inner card art so follow-up calls
always start from the unmodified asset.  Palettes are declared per rarity and
overrides can introduce context-sensitive transforms.  The returned dictionary
maps card identifiers to the generated file paths.

## Plugin exposure

When the module is active, the following entries appear in
`plugins.PLUGIN_MANAGER.exposed`:

- `experimental_graalpy_illustrations_engine` – shared instance of
  `AdaptiveIllustrationEngine`.
- `experimental_graalpy_illustrations_directors` – mapping of registered deck
  directors keyed by deck class name and `Deck.display_name`.
- `experimental_graalpy_illustrations_launch` – callable alias for
  `launch_adaptive_illustrations`.

Companion tooling can subscribe to the plugin registry to monitor generated
paths, add custom transforms, or orchestrate palette swaps across multiple
decks.

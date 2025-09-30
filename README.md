# stsmoddergui

This repository now ships with a Python-first BaseMod wrapper backed by JPype.
The wrapper hides all JVM plumbing and exposes the Slay the Spire modding API
directly to Python developers.

## Features

- Automatic JPype installation and BaseMod jar download on first use.
- High level access to the `basemod`, `com.megacrit.cardcrawl`, `libgdx` and
  ModTheSpire packages through simple dot notation.
- Repository wide plugin manager that exposes every module to third party
  extensions.
- High level project system for declaring characters, card colours and cards via `ModProject`.
- Declarative `SimpleCardBlueprint` helper that builds everyday attacks, skills and powers without boilerplate.
- Turn-key bundling through `compileandbundle` which writes ModTheSpire manifests, Java enum patches and copies Python assets.
- Forward-looking roadmap documented in `futures.md`.
- Built-in deck analytics helper that converts validation snapshots into tables and JSON artefacts for dashboards and plugins.

## Getting started

```python
from modules.basemod_wrapper import basemod

basemod.BaseMod.subscribe(lambda *args: print("Hook invoked!"))
```

See `modules/basemod_wrapper/README.md` for detailed instructions.


## High level workflow

```python
from pathlib import Path
from modules.basemod_wrapper import create_project, compileandbundle, BundleOptions

project = create_project(
    mod_id="revenant",
    name="Revenant",
    author="Your Name",
    description="Spectral powerhouse",
)
color = project.define_color(
    "REVENANT_PURPLE",
    card_color=(0.45, 0.2, 0.6, 1.0),
    trail_color=(0.3, 0.1, 0.4, 1.0),
    slash_color=(0.7, 0.4, 0.9, 1.0),
    attack_bg="resources/Revenant/images/cards/card_attack.png",
    skill_bg="resources/Revenant/images/cards/card_skill.png",
    power_bg="resources/Revenant/images/cards/card_power.png",
    orb="resources/Revenant/images/cards/card_orb.png",
    attack_bg_small="resources/Revenant/images/cards/card_attack_small.png",
    skill_bg_small="resources/Revenant/images/cards/card_skill_small.png",
    power_bg_small="resources/Revenant/images/cards/card_power_small.png",
    orb_small="resources/Revenant/images/cards/card_orb_small.png",
)

# Register cards and characters via helper methods here...

options = BundleOptions(
    java_classpath=[
        Path("/path/to/SlayTheSpire.jar"),
        Path("/path/to/BaseMod.jar"),
        Path("/path/to/ModTheSpire.jar"),
    ],
    python_source=Path("python"),
    assets_source=Path("resources/Revenant"),
    output_directory=Path("dist"),
)
compileandbundle(project, options)
```

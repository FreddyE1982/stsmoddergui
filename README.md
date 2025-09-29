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
- Forward-looking roadmap documented in `futures.md`.

## Getting started

```python
from modules.basemod_wrapper import basemod

basemod.BaseMod.subscribe(lambda *args: print("Hook invoked!"))
```

See `modules/basemod_wrapper/README.md` for detailed instructions.

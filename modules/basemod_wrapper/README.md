# BaseMod Python Wrapper

This package provides a high level JPype wrapper around the [BaseMod](https://github.com/daviscook477/BaseMod)
modding framework for Slay the Spire.  The wrapper focuses on giving Python
developers first class access to the Java API while keeping usage entirely
pythonic – there is no need to implement Java interfaces manually or deal with
classpath management.  Everything is automatic and discoverable via dot
notation.

## Quick start

```python
from modules.basemod_wrapper import basemod

basemod.BaseMod.addColor(
    basemod.BaseMod.MAX_COLOR,
    (255, 0, 0),
    (255, 50, 50),
    (255, 100, 100),
    "Example",
)
```

The example above works without additional setup:

1. JPype is installed automatically if it is missing.
2. The latest BaseMod release jar is downloaded on demand.
3. The JVM is started with the jar on the classpath.
4. The `basemod` namespace becomes available through convenient dot access.

Passing Python callables to functional interfaces is supported automatically. If
a BaseMod method expects a single method interface, you can provide a regular
Python function and it will be wrapped transparently.

## Plugin integration

The wrapper registers itself with the repository wide plugin manager.  Plugins
can grab the `basemod_environment`, `basemod`, `cardcrawl`, `modthespire` and
`libgdx` objects from the exposed context to hook into the running JVM.

## Limitations

Running BaseMod still requires Slay the Spire and the ModTheSpire loader.  This
wrapper focuses on exposing the API – it does not attempt to emulate the game or
ship its assets.

## High level project builder

The `ModProject` helper lets you declare colours, cards and characters without touching BaseMod hooks. After defining your content you can call `enable_runtime()` to wire all hooks or `compileandbundle()` to produce a ModTheSpire ready bundle. See the [Full Mod Tutorial](../../docs/full_mod_tutorial.md) for a concrete walkthrough that creates a complete character, registers their starting deck, and outputs a ready-to-install mod folder.

# stsmoddergui

A modular toolkit focused on integrating Slay the Spire modding
capabilities into Python workflows.  The repository provides a global
plugin architecture that automatically exposes every function, class, and
variable to extensions, ensuring full introspection and hackability.

## Features

* **Global plugin registry** – dynamically scans the project and hands a
  fully-populated API map to every plugin.
* **BaseMod JPype wrapper** – located in `modules/basemod_wrapper`, this
  package offers full feature parity with the original Java API by
  mirroring it through JPype.
* **Research vault** – documentation collected while working on the
  project lives under `research/` for easy reuse.

## Getting started

Install the Python dependencies and configure the BaseMod wrapper with
paths to your JAR files.  See `modules/basemod_wrapper/README.md` for a
complete walkthrough.

Plugins can be registered at runtime:

```python
from stsmoddergui import GLOBAL_PLUGIN_REGISTRY

GLOBAL_PLUGIN_REGISTRY.register("your_plugin_module")
```

Each plugin receives a `PluginContext` containing dictionaries for all
packages, modules, classes, functions, and variables defined in the
repository.

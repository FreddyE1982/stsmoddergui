# BaseMod JPype Wrapper

This module exposes the entirety of the [BaseMod](https://github.com/daviscook477/BaseMod)
API to Python code by relying on the [JPype](https://github.com/jpype-project/jpype)
bridge.  The wrapper is deliberately thin – it mirrors the Java classes and
methods directly – but enriches the developer experience with:

* Simple configuration management via `BaseModConfig`.
* Automatic JVM lifecycle handling with `JVMGateway`.
* A Pythonic `BaseModFacade` that exposes the static methods on
  `basemod.BaseMod`.
* Lazy access to the entire BaseMod package tree through
  `JavaPackageProxy`.
* Helper utilities for converting Python callables into Java interface
  proxies (`ProxyFactory`).

The combination of these components gives you full feature parity with the
original Java API while keeping the ergonomics of Python.

## Installation

Install the `jpype1` dependency into your Python environment:

```bash
pip install jpype1
```

Download the BaseMod JAR together with the Slay the Spire JAR.  The wrapper
needs paths to both in order to assemble a complete classpath.

## Quick start

```python
from modules.basemod_wrapper import BaseModConfig, configure, get_facade

config = BaseModConfig(
    basemod_jar="/path/to/BaseMod.jar",
    slay_the_spire_jar="/path/to/desktop-1.0.jar",
)

configure(config)
base_mod = get_facade()

# Use any BaseMod static method
base_mod.addColor(...)
```

You can also configure the wrapper via environment variables:

* `BASEMOD_JAR`
* `SLAY_THE_SPIRE_JAR`
* `BASEMOD_EXTRA_CLASSPATH`
* `BASEMOD_JVM_ARGS`

Call `configure()` with no arguments to load from the environment.

## Working with interfaces

Many BaseMod entry points require you to implement Java interfaces.  The
`ProxyFactory` hides the ceremony required to create `jpype.JProxy`
instances:

```python
from modules.basemod_wrapper import get_proxy_factory, ensure_basemod

factory = get_proxy_factory()
base_mod = ensure_basemod()

# Create a proxy for basemod.interfaces.ISubscriber
subscriber = factory.callable("basemod.interfaces.ISubscriber", lambda *args: print(args))
base_mod.subscribe(subscriber)
```

For multi-method interfaces you can supply a mapping of method names to
callables:

```python
proxy = factory.mapping(
    ["basemod.abstracts.CustomSavable"],
    {
        "onSave": lambda: {"key": "value"},
        "onLoad": lambda data: print(data),
    },
)
```

## Plugin integration

The module registers itself with the repository wide plugin infrastructure.
Every function, class, and variable declared here is automatically exposed in
the plugin context through `GLOBAL_PLUGIN_REGISTRY`.  Third-party plugins can
use this to access the active JVM gateway, the BaseMod facade, or any other
component that ships with this package.

## Troubleshooting

* **Missing JPype** – Install the `jpype1` package.
* **Classpath errors** – Ensure that every path provided in the configuration
  exists on disk.
* **JVM already started** – JPype only allows a single JVM instance per
  process.  Make sure you do not start JPype manually outside of the wrapper.

## Extensibility

All helper classes follow small, composable patterns.  Extend or replace them
using the plugin system if you want to customise behaviour without touching
core files.

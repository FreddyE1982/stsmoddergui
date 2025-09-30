# Futures roadmap

## Module level plugin discovery

Implement automatic discovery of plugin entry points via naming conventions or
package metadata.  This would allow dropping plugin modules into a dedicated
folder without touching the core code.  Usage: call
``PLUGIN_MANAGER.auto_discover("plugins")`` once implemented.

## JVM dependency caching strategy

Persist downloaded jars with version tracking to avoid unnecessary re-downloads
when different wrapper versions are required.  Usage: expand
``ensure_basemod_jar`` to accept a version string and maintain a local manifest.

## Desktop jar discovery helper

Provide a small helper that scans common Steam install directories and honours
environment variables to automatically locate ``desktop-1.0.jar``. Usage: expose
``ensure_desktop_jar()`` that either returns a valid path or raises a helpful
error instructing users how to obtain the jar.

## Interface signature caching

Cache inspected Java method signatures to speed up repeated calls to heavily
used BaseMod hooks.  Usage: extend ``JavaCallableWrapper`` with a lookup table so
plugins do not incur repeated reflection overhead.

## Advanced simple card effects

Extend `SimpleCardBlueprint` with multi-target power routing, secondary magic numbers and optional follow-up actions.
Usage: allow blueprint authors to declare additional `effects` in sequence, plus hooks for `on_draw` and
`on_discard` so heavily scripted cards can still be described declaratively.

## Inner card image caching and deduplication

Cache processed inner card art keyed by source checksum so repeated calls to `innerCardImage` do not rebuild identical assets.
Usage: extend `prepare_inner_card_image` with a hash manifest stored alongside generated files; reuse outputs when available
and expose the manifest through the plugin layer for advanced asset tooling.

## LimeWire decryption pipeline

Build a Python implementation of the LimeWire content decrypter so that the encrypted jars downloaded during bundling can be unwrapped automatically. Usage: mirror the `GE#getContentItemDecryptionKeys` flow in Python, deriving AES keys from the passphrase and decrypting the AES-CTR stream into usable game jars.

## StSLib feature matrix generation

Generate runtime documentation for every exposed StSLib hook, action and interface by introspecting the loaded JVM classes. Usage: extend ``UnifiedSpireAPI`` with an ``introspect()`` helper that emits Markdown files inside ``research/`` summarising constructor signatures and expected usage patterns. This keeps the Python façade aligned with future StSLib releases.

## Unified keyword profiles

Allow describing complex keyword setups declaratively via JSON/YAML manifest files. Usage: add ``UnifiedSpireAPI.load_keywords(path: Path)`` that consumes manifests, registers keywords, and applies card field defaults to reduce boilerplate for large mods.

## Keyword upgrade presets

Expand ``SimpleCardBlueprint`` with reusable presets that bundle ``keywords``, ``keyword_values`` and ``keyword_upgrades`` for
common archetypes (e.g. Exhaustive retainers or Persist powers). Usage: expose ``modules.basemod_wrapper.cards.keyword_preset``
helpers that merge preset dictionaries into blueprints so mods can opt-in via a single call and plugins can contribute
additional presets through ``PLUGIN_MANAGER`` broadcasts.

## ProjectLayout localisation variants

Teach ``ModProject.scaffold`` to generate localisation folders for multiple languages in one go (eng, fra, deu, zhs, etc.) and expose a helper that mirrors ``resource_path`` for localisation files. Usage: extend the scaffold signature with ``languages: Sequence[str]`` and update ``ProjectLayout`` with a mapping from language codes to directories so future tutorials can demonstrate multi-language text packs out of the box.

## Asset templating helpers

Provide optional PNG placeholders (solid alpha grids) whenever ``scaffold`` creates texture slots. Usage: add an ``include_placeholders: bool`` flag that writes simple coloured PNGs using Pillow to make generated mods immediately runnable even before artists deliver final assets.

## Plugin attribute diff subscriptions

Build a watcher atop ``repository_attributes`` that emits change events whenever modules expose new callables or state. Usage: extend ``PLUGIN_MANAGER`` with a ``subscribe_to_exports`` helper that hands plugins a diff of newly discovered attributes so tooling can hot-reload capabilities without rescanning the entire manifest.

# Futures roadmap

## Completed milestones

- ✅ **Module level plugin discovery** – `PLUGIN_MANAGER.auto_discover(...)` now
  scans packages recursively and registers plugins that follow the existing
  naming conventions. Tests in `tests/test_plugins.py` ensure the matcher and
  error reporting behave as expected.
- ✅ **JVM dependency caching strategy** – dependency helpers persist resolved
  jar paths and reuse cached files across runs. The manifest lives under
  ``lib/dependency_manifest.json`` and is covered by
  `tests/test_loader.py::test_ensure_basemod_jar_reuses_manifest_cache`.
- ✅ **Desktop jar discovery helper** – `ensure_desktop_jar` consults
  environment variables, explicit search paths and common Steam locations before
  raising a user-facing error. Behaviour is verified in `tests/test_loader.py`.
- ✅ **Interface signature caching** – the BaseMod proxy caches resolved
  signatures inside `modules/basemod_wrapper/proxy.py`, ensuring repeat calls
  avoid expensive lookups.
- ✅ **Advanced simple card effects** – `SimpleCardBlueprint` gained secondary
  values, chained effect descriptors, follow-up actions and draw/discard hooks.
  See the expanded documentation in `modules/basemod_wrapper/README.md` and
  tests in `tests/test_cards.py::test_secondary_values_follow_ups_and_hooks`.
- ✅ **Inner card image caching and deduplication** – inner art now reuses cached
  outputs via a manifest stored next to the generated assets. The new
  `load_inner_card_manifest` helper exposes the data to plugins. Covered by
  `tests/test_card_assets.py`.
- ✅ **Plugin attribute diff subscriptions** – `PLUGIN_MANAGER.subscribe_to_exports`
  now replays repository attribute diffs and notifies subscribers on change.
  The behaviour is exercised in `tests/test_plugins.py`.

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

## Generalised dynamic keyword placeholders

Now that Exhaustive cards translate ``{uses}`` into the runtime ``!stslib:ex!`` token automatically, extend the formatter so
other numeric keywords (Refund, Persist, Fleeting, Soulbound, etc.) can expose intuitive placeholders as well. Usage: build a
mapping from keyword name to dynamic token within ``_uses_placeholder`` (renamed to a generic helper) and document the supported
placeholders in the wrapper README. Plugins should be able to contribute additional mappings through a shared registry exposed
on ``PLUGIN_MANAGER``.

## ProjectLayout localisation variants

Teach ``ModProject.scaffold`` to generate localisation folders for multiple languages in one go (eng, fra, deu, zhs, etc.) and expose a helper that mirrors ``resource_path`` for localisation files. Usage: extend the scaffold signature with ``languages: Sequence[str]`` and update ``ProjectLayout`` with a mapping from language codes to directories so future tutorials can demonstrate multi-language text packs out of the box.

## Asset templating helpers

Provide optional PNG placeholders (solid alpha grids) whenever ``scaffold`` creates texture slots. Usage: add an ``include_placeholders: bool`` flag that writes simple coloured PNGs using Pillow to make generated mods immediately runnable even before artists deliver final assets.

## Simple card blueprint CLI preview

Provide a small `python -m modules.basemod_wrapper.cards preview ...` helper that
instantiates `SimpleCardBlueprint`s from JSON/YAML manifests and dumps the
resulting auto-generated card classes plus resolved resource paths. Usage:
`python -m modules.basemod_wrapper.cards preview blueprint.json` would process
blueprints, emit a tabular summary of costs/keywords and highlight any missing
art assets before bundling.

## Keyword timeline hooks

Expand the newly introduced `Keyword` scheduler so keywords can subscribe to
additional combat lifecycle events (enemy intent changes, card draws, shuffles).
Usage: expose optional callbacks on the base class (``on_draw``, ``on_intent``)
that the scheduler wires into BaseMod subscribers, and surface the registration
points on ``PLUGIN_MANAGER`` so third-party extensions can augment the event
matrix without monkeypatching the core implementation.

## Character builder scaffolding

Teach the high-level `Character` helper to generate self-contained runtime
packages so that mods assembled through the declarative decks API can bundle a
ready-to-run `project.py`. Usage: extend `Character.createMod` with an optional
`generate_python_package` flag that writes a minimal package embedding the
registered decks and characters, ensuring teams without an existing Python code
base can still rely on the automated bundler.

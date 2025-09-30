# Futures roadmap

## Completed milestones

- [complete] **Module level plugin discovery** – `PLUGIN_MANAGER.auto_discover(...)` now
  scans packages recursively and registers plugins that follow the existing
  naming conventions. Tests in `tests/test_plugins.py` ensure the matcher and
  error reporting behave as expected.
- [complete] **JVM dependency caching strategy** – dependency helpers persist
  resolved jar paths and reuse cached files across runs. The manifest lives
  under `lib/dependency_manifest.json` and is covered by
  `tests/test_loader.py::test_ensure_basemod_jar_reuses_manifest_cache`.
- [complete] **Desktop jar discovery helper** – `ensure_desktop_jar` consults
  environment variables, explicit search paths and common Steam locations
  before raising a user-facing error. Behaviour is verified in
  `tests/test_loader.py`.
- [complete] **Interface signature caching** – the BaseMod proxy caches
  resolved signatures inside `modules/basemod_wrapper/proxy.py`, ensuring
  repeat calls avoid expensive lookups.
- [complete] **Advanced simple card effects** – `SimpleCardBlueprint` gained
  secondary values, chained effect descriptors, follow-up actions and
  draw/discard hooks. See the expanded documentation in
  `modules/basemod_wrapper/README.md` and tests in
  `tests/test_cards.py::test_secondary_values_follow_ups_and_hooks`.
- [complete] **Inner card image caching and deduplication** – inner art now
  reuses cached outputs via a manifest stored next to the generated assets.
  The new `load_inner_card_manifest` helper exposes the data to plugins.
  Covered by `tests/test_card_assets.py`.
- [complete] **Plugin attribute diff subscriptions** –
  `PLUGIN_MANAGER.subscribe_to_exports` now replays repository attribute diffs
  and notifies subscribers on change. The behaviour is exercised in
  `tests/test_plugins.py`.
- [complete] **Deck analytics visualiser** – `modules/modbuilder/analytics.py`
  adds `DeckAnalytics` helpers that convert deck snapshots into immutable
  tables and JSON artefacts. `Character.validate` now injects the analytics
  payload into validation reports, `tests/test_modbuilder.py` verifies the
  integration, and `how to/deck-analytics.md` walks contributors through real
  world usage.
- [complete] **Python runtime auto-launcher** – Bundles write
  `bootstrap_mod.py` via `modules.modbuilder.runtime_env.write_runtime_bootstrapper`
  so testers can run `python bootstrap_mod.py` to provision the `.venv` and
  execute the entrypoint. The executable workflow is covered by
  `modules.modbuilder.runtime_env.bootstrap_python_runtime` and documented in
  `how to/load-and-play-mod.md`.

## Upcoming work

- [todo] **Experimental feature catalogue** – Populate
  `modules.basemod_wrapper.experimental` with opt-in utilities that showcase
  advanced integrations (e.g. runtime logging overlays, StSLib diagnostics,
  analytics probes). Usage: implement each capability as a dedicated
  submodule, document its activation hooks, and surface an `experimental.on`
  example in the wrapper README so teams can trial features without forking
  the stable API.
- [todo] **LimeWire decryption pipeline** – Build a Python implementation of
  the LimeWire content decrypter so that the encrypted jars downloaded during
  bundling can be unwrapped automatically. Usage: mirror the
  `GE#getContentItemDecryptionKeys` flow in Python, deriving AES keys from the
  passphrase and decrypting the AES-CTR stream into usable game jars.
- [todo] **StSLib feature matrix generation** – Generate runtime documentation
  for every exposed StSLib hook, action and interface by introspecting the
  loaded JVM classes. Usage: extend `UnifiedSpireAPI` with an `introspect()`
  helper that emits Markdown files inside `research/` summarising constructor
  signatures and expected usage patterns. This keeps the Python façade aligned
  with future StSLib releases.
- [todo] **Unified keyword profiles** – Allow describing complex keyword setups
  declaratively via JSON/YAML manifest files. Usage: add
  `UnifiedSpireAPI.load_keywords(path: Path)` that consumes manifests,
  registers keywords, and applies card field defaults to reduce boilerplate
  for large mods.
- [todo] **Keyword upgrade presets** – Expand `SimpleCardBlueprint` with
  reusable presets that bundle `keywords`, `keyword_values` and
  `keyword_upgrades` for common archetypes (e.g. Exhaustive retainers or
  Persist powers). Usage: expose `modules.basemod_wrapper.cards.keyword_preset`
  helpers that merge preset dictionaries into blueprints so mods can opt-in via
  a single call and plugins can contribute additional presets through
  `PLUGIN_MANAGER` broadcasts.
- [todo] **Generalised dynamic keyword placeholders** – Extend the Exhaustive
  placeholder formatter so other numeric keywords (Refund, Persist, Fleeting,
  Soulbound, etc.) expose intuitive placeholders. Usage: build a mapping from
  keyword name to dynamic token within the formatter and document the
  supported placeholders in the wrapper README. Plugins should be able to
  contribute additional mappings through a shared registry exposed on
  `PLUGIN_MANAGER`.
- [todo] **ProjectLayout localisation variants** – Teach
  `ModProject.scaffold` to generate localisation folders for multiple
  languages in one go (eng, fra, deu, zhs, etc.) and expose a helper that
  mirrors `resource_path` for localisation files. Usage: extend the scaffold
  signature with `languages: Sequence[str]` and update `ProjectLayout` with a
  mapping from language codes to directories so future tutorials can
  demonstrate multi-language text packs out of the box.
- [todo] **Asset templating helpers** – Provide optional PNG placeholders
  whenever `scaffold` creates texture slots. Usage: add an
  `include_placeholders: bool` flag that writes simple coloured PNGs using
  Pillow to make generated mods immediately runnable even before artists
  deliver final assets.
- [todo] **Simple card blueprint CLI preview** – Provide a small
  `python -m modules.basemod_wrapper.cards preview ...` helper that
  instantiates `SimpleCardBlueprint`s from JSON/YAML manifests and dumps the
  resulting auto-generated card classes plus resolved resource paths. Usage:
  `python -m modules.basemod_wrapper.cards preview blueprint.json` would
  process blueprints, emit a tabular summary of costs/keywords and highlight
  any missing art assets before bundling.
- [todo] **Keyword timeline hooks** – Expand the newly introduced `Keyword`
  scheduler so keywords can subscribe to additional combat lifecycle events
  (enemy intent changes, card draws, shuffles). Usage: expose optional
  callbacks on the base class (`on_draw`, `on_intent`) that the scheduler wires
  into BaseMod subscribers, and surface the registration points on
  `PLUGIN_MANAGER` so third-party extensions can augment the event matrix
  without monkeypatching the core implementation.
- [todo] **Power instantiation metadata registry** – Introduce a metadata
  registry that enumerates the known constructor signatures for Slay the Spire
  powers and exposes an override hook for modded ones. Usage: ship a JSON
  manifest under `research/` describing the expected positional parameters,
  whether a power consumes the player as source, and any supplementary flags
  (e.g. `isSourceMonster`). `KeywordContext` would consult the registry before
  falling back to heuristics, while plugins could register additional entries
  via `PLUGIN_MANAGER.expose(...)` to guarantee future compatibility.
- [todo] **Character builder scaffolding** – Teach the high-level `Character`
  helper to generate self-contained runtime packages so that mods assembled
  through the declarative decks API can bundle a ready-to-run `project.py`.
  Usage: extend `Character.createMod` with an optional
  `generate_python_package` flag that writes a minimal package embedding the
  registered decks and characters, ensuring teams without an existing Python
  code base can still rely on the automated bundler.
- [todo] **Inner card generation telemetry** – Record manifest entries whenever
  `Character.createMod` schedules inner card art generation so the bundler can
  report skipped outputs or stale cache hits. Usage: extend the card asset
  pipeline with a lightweight audit log that captures blueprint identifiers,
  source digests and resolved resource paths, then surface a
  `PLUGIN_MANAGER` broadcast so tooling plugins can surface progress bars or
  regeneration prompts.
- [todo] **How-to recipe synchroniser** – Link the new `how to/` recipes with
  runnable sample projects so documentation never drifts from the code. Usage:
  add a `modules.tools.recipes` helper that parses the Markdown snippets,
  materialises temporary mods with `Deck`, `Character`, and `Keyword`, and
  exposes a CLI (`python -m modules.tools.recipes verify how to/basic-character.md`)
  to ensure examples still compile and bundle. Plugins should receive a
  broadcast before and after verification so they can contribute extra
  validation or telemetry.
- [todo] **Launcher profile validation helpers** – Automate sanity checks for
  the two launcher flows documented in `how to/load-and-play-mod.md`. Usage:
  extend the bundler with an optional `validate_launchers` flag that inspects
  the ModTheSpire output directory and Steam Workshop subscriptions via the
  Steam Web API so scripts can warn if required utilities (ModTheSpire,
  BaseMod, StSLib) are missing before testers try to run the game.
- [todo] **Localization consistency audits** – Now that simple cards can emit
  multilingual `cards.json` payloads, add a tooling pass that compares the
  generated files against existing assets and highlights missing or stale
  translations. Usage: surface a `modules.tools.localization.audit()` helper
  that scans the `assets/<mod_id>/localizations` tree, reports cards that only
  exist in a subset of languages, and exposes a plugin hook so translation
  workflows can gate builds when required locales are incomplete.
- [todo] **GraalPy migration playbook integration** – Consolidate the
  GraalPy compatibility and migration notes under
  `modules.basemod_wrapper.experimental` into a guided activation flow.
  Usage: ship an `experimental.graalpy` feature that surfaces the collected
  compatibility guidance, validates the local GraalPy toolchain, and exposes
  plugin hooks so external tooling can extend the migration checks before a
  mod toggles into GraalPy mode.


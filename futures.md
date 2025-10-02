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
- [complete] **GraalPy runtime playbook integration** – The new
  `experimental.graalpy_runtime` feature provisions the GraalPy interpreter,
  rebuilds Pillow for the host platform, registers a polyglot JVM backend and
  exposes plugin hooks so toggling the experiment immediately reroutes all
  BaseMod bridge calls through GraalPy.
- [complete] **Rule-weaver battle mutators** –
  `experimental.graalpy_rule_weaver` layers a GraalPy-powered mutation engine
  over card blueprints and the keyword registry.  Mods can register
  `MechanicMutation` instances, load declarative rule scripts, and rely on the
  plugin exports to coordinate mechanic tweaks across tooling, live builds and
  playtests.

## Upcoming work

- [todo] **Experimental feature catalogue** – Populate
  `modules.basemod_wrapper.experimental` with opt-in utilities that showcase
  advanced integrations (e.g. runtime logging overlays, StSLib diagnostics,
  analytics probes). Usage: implement each capability as a dedicated
  submodule, document its activation hooks, and surface an `experimental.on`
  example in the wrapper README so teams can trial features without forking
  the stable API.
- [todo] **Deferred stance runtime bootstrap** – Introduce a readiness
  coordinator that finalises Digimon stances once the GraalPy backend becomes
  available. Usage: emit a `digitalesmonster_stance_runtime_ready` broadcast
  when `graalpy_runtime` switches on, re-run the stance registration helpers,
  and update the plugin exports so UI overlays and analytics plugins can react
  without polling the project façade.
- [todo] **SkullGreymon Korrumpierungsereignisse** – Ergänze Ereignis- und
  Kampfhooks, die den SkullGreymon-Abzweig in Kartenbelohnungen, Events und
  Relikte einspeisen. Usage: erweitere den Levelmanager um eine "corruption"
  Telemetrie, triggere Plugin-Broadcasts bei jedem SkullGreymon-Einstieg und
  erlaube Relikten, Stabilitätsstrafen oder Bonusheilungen abhängig vom
  `skullgreymon`-Metadatenblock zu registrieren.
- [todo] **Digi-Ei Reliktkanalisation** – Implementiere eine Inventar- und
  Reliktbrücke, die Armor-Digitation automatisch auf spezifische Digi-Eier
  mappt. Usage: erweitere den Stance-Manager um eine `armor_pipeline`
  Integrations-API, die Relikte als `ArmorEggProvider` registriert, Stabilität
  dynamisch nach Eityp justiert und Plugin-Hooks bereitstellt, um neue Eier mit
  Spezialeffekten einzubinden.
- [todo] **Overlay animation presets** – Extend the runtime overlay director
  with reusable easing timelines (fade, slide, pulse) and scripted sequences.
  Usage: add `OverlayAnimation` descriptors that the manager can attach to an
  overlay, tick animations alongside duration tracking, and broadcast progress
  updates through `PLUGIN_MANAGER` so plugins can mirror transitions or extend
  them with custom shaders.
- [todo] **Overlay trigger diagnostics console** – Build a live inspector that
  lists registered overlay triggers, highlights their predicates and shows the
  last payload each trigger consumed. Usage: add `overlay_manager().trigger_map()`
  and a lightweight CLI/overlay that visualises trigger cooldowns plus recent
  executions so designers can iterate on automation rules without diving into
  logs.
- [todo] **In-process compact loader activation** – Teach the compact bundling
  pipeline to hydrate `.pystsmod` archives directly inside the ModTheSpire
  JVM. Usage: extend the generated loader jar to bootstrap the Python runtime,
  surface the archive contents as an in-memory class loader, and update
  `modules.modbuilder.runtime_env` to consume `CompactBundleLoader`
  descriptors when launching mods.
- [todo] **Adaptive evolver tuning console** – Ship a CLI and dashboard that
  visualises the persistent adaptive deck profile, highlights mutation
  rationales, and allows designers to export/import heuristic weights.
  Usage: extend `mods.adaptive_deck_evolver.runtime` with an inspection API,
  build a `python -m mods.adaptive_deck_evolver inspect` entrypoint that dumps
  the current `PlayerProfile`, and document how plugins can subscribe to the
  emitted telemetry to provide custom UIs.
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
- [todo] **GraalPy stance director** – Layer a declarative director over the new
  `Stance` base class so mods can register particle scripts, looping VFX, and
  combat hooks through JSON manifests. Usage: provide a `register_stance_script`
  helper that loads manifests, exposes them via `PLUGIN_MANAGER`, and binds the
  generated Python callables to stance lifecycle events without touching
  `AbstractStance` directly.
- [todo] **ProjectLayout localisation variants** – Teach
  `ModProject.scaffold` to generate localisation folders for multiple
  languages in one go (eng, fra, deu, zhs, etc.) and expose a helper that
  mirrors `resource_path` for localisation files. Usage: extend the scaffold
  signature with `languages: Sequence[str]` and update `ProjectLayout` with a
  mapping from language codes to directories so future tutorials can
  demonstrate multi-language text packs out of the box.
- [todo] **Localization manifest coverage expansion** – Extend the
  compile-time localisation manifest to capture relic, stance and keyword
  strings sourced from runtime registries so YAML contributors see every
  player-facing tooltip. Usage: surface registry snapshots before bundling,
  merge them into the manifest generator, and document how plugins can
  contribute additional registries for bespoke mods.
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
- [todo] **Simple card playtest art overrides** – Add a `playtest: bool = False`
  flag to the existing simple card configuration (the helper that currently
  wires `SimpleCardBlueprint` into the runtime card factory). When the flag is
  enabled, the pipeline must procedurally generate a solid-black PNG that
  matches the expected inner card resolution, persist it in the managed asset
  cache, and force every registered card's inner art reference to point at this
  default placeholder. Usage: expose the toggle on all relevant blueprint and
  scaffolding helpers, make sure the generated art participates in the
  manifest/telemetry systems so plugins can detect the override, and document
  the flag in the simple card how-to with a reminder that production builds
  should leave `playtest` disabled.
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
- [todo] **GraalPy verification harness** – Extend the GraalPy backend with
  smoke tests that execute under the GraalPy interpreter and exercise
  functional interface proxies, package resolution, and runtime_env bootstrap
  plans to ensure future upgrades of GraalPy do not break the bridge.
- [todo] **Cinematic rivalry timeline visualiser** – Build on the new
  `experimental.graalpy_cinematic_rivalries` module by emitting structured
  JSON timelines for every updated `RivalryScript`. Usage: expose
  `export_timelines(path: Path)` on the module so tooling can persist annotated
  turn-by-turn breakdowns, then document how plugins can subscribe to the
  timeline feed to generate UI overlays or debugging notebooks.
- [todo] **Ghost session export harness** – Extend
  `experimental.graalpy_coaching_ghosts` with helpers that persist session
  histories to JSON so teams can replay coaching deltas after internal
  playtests. Usage: surface `export_session(session_id, path)` on the engine,
  include an importer for historical comparisons, and document how plugins can
  diff exported sessions to surface actionable training drills.

- [todo] **Adaptive illustration preset marketplace** – Extend
  `experimental.graalpy_adaptive_illustrations` with transform bundles that
  plugin authors can publish and share. Usage: add a registry on the adaptive
  engine that loads presets from JSON manifests (tints, glows,
  shader-inspired blends) and document how decks can opt-in with a single
  `director.apply_presets("buddy_glow")` call so future updates stay
  data-driven.
- [todo] **Narration sample pack exchange** – Build on
  `experimental.graalpy_live_tutorial_narrator` by introducing a plugin-driven
  marketplace for voice packs and synthesis presets. Usage: expose a
  `register_voice_pack(name, loader)` helper on the narration engine so plugins
  can publish text-to-speech hooks, stream audio assets, and tag lines by
  language/accent.  Document how directors select packs via
  `director.use_voice_pack("mentors/en_gb")` and expose the registration
  points through `PLUGIN_MANAGER` for tooling dashboards.
- [todo] **Rule weaver script manifest verification** – Extend the new mechanics
  runtime helpers with a `ProjectLayout` inspection pass that scans registered
  script paths/resources, validates JSON/YAML structure ahead of bundling, and
  publishes a manifest to `PLUGIN_MANAGER` so CI pipelines can diff mechanic
  packs for unexpected mutations.
- [todo] **Digimon Stance-Balance Telemetrie** – Ergänze das zukünftige
  Digimon-Level-System um eine optionale Telemetrie, die Stabilitätswerte,
  Digitationstrigger und Rückfallhäufigkeiten pro Kampf sammelt. Nutzung:
  Implementiere eine `collect_digimon_metrics()`-Schnittstelle, die Daten an
  `PLUGIN_MANAGER` broadcastet, damit Balancing-Tools und Analytics-Plugins die
  Effekte neuer Stances oder Karten bewerten können.
- [todo] **Adaptive telemetry core visual pass** – Produce production-quality relic art
  and outline textures for the new Adaptive Telemetry Core relic. Usage: create
  high contrast PNGs under `assets/adaptive_evolver/images/relics/` and update
  the relic documentation with sizing guidelines so bundling workflows include
  finalised art instead of placeholders.
- [todo] **Digitales Monster stability CLI** – Build a command line helper that prints and migrates saved stability
  profiles. Usage: expose `python -m mods.digitalesmonster.persistence audit` which loads the current
  profile, validates ranges against project defaults, and provides plugin hooks so balancing tools can
  veto runs when values fall outside expected ranges.
- [todo] **Jogress partner manifest** – Extend the new level transition manager so fusion partners are
  described in declarative JSON manifests. Usage: load manifests on project bootstrap, map partner IDs to
  cards/relics, and allow plugins to register additional partner pairs for future Jogress stances without
  modifying core code.
- [todo] **Stability progression dashboard** – Surface the persisted stability deltas in a rich analytics
  overlay or CLI report. Usage: build atop `StabilityPersistenceController` to visualise per-level start/
  max history, highlight defeat penalties and let designers fine-tune the progression constants.

# GraalPy runtime modding opportunities

The following catalogue expands on the practical gameplay-facing features that become feasible only after enabling the `experimental.graalpy_runtime` feature flag. Each entry highlights the player-facing result alongside the modules and helpers that mod teams can lean on once the GraalPy backend is active.

1. **Cinematic hand-crafted boss rivalries** – Feed fight telemetry straight into Python-side AI trainers that refine encounter scripts in real time, letting the same GraalPy process push updated intents through `modules.modbuilder.Character` without the latency of JPype marshalling.
2. **Adaptive card-illustration swaps** – Combine Pillow-powered texture remaps with `modules.modbuilder.Deck` snapshots to recolour cards mid-run based on relics collected, creating a living codex of the player's journey without shipping pre-rendered variants.
3. **Live tutorial narrator** – Stitch together GraalPy-accessible voice-over queues that react to combat events surfaced by `modules.basemod_wrapper.events`, enabling a fully voiced mentor that comments on draws, discards and power spikes as they happen.
4. **Coaching ghosts for high-score chases** – Use GraalPy to read and replay leaderboard ghosts, overlaying their actions through the BaseMod wrapper so players duel their past runs or community legends inside the same session.
5. **Card-slinger roguelite editor** – Launch an in-run deck tinkerer that applies blueprint edits from a web UI, piping the results through `SimpleCardBlueprint` helpers backed by GraalPy's zero-copy data sharing to patch cards without restarting the JVM.
6. **Multi-language lore drops** – Tap into GraalPy's text-to-speech libraries to narrate dynamic lore snippets when new keywords trigger, relying on the keyword helpers to surface contextual metadata for immersive storytelling beats.
7. **Party-wide sentiment system** – Power a relationship simulator that samples Python sentiment models, feeding updated power modifiers back into combat to reflect how allies feel about the player's choices, all within one GraalVM process.
8. **Reactive dungeon painter** – Bind GraalPy's image generation stack to `Character.validate` analytics so the map art morphs alongside deck archetypes, colouring future encounters and reward screens with bespoke art the moment analytics detect a style shift.
9. **Run historian timelines** – Stream run logs directly into GraalPy-backed dataframes to craft timeline overlays, letting players scrub through card plays, damage spikes, and relic triggers via an in-game panel built on the high-level wrappers.
10. **Collaborative mod trainer** – Expose the full plugin registry through GraalPy so remote teammates can hot-load balancing scripts, share experimental decks via the `Deck.statistics()` output, and iterate together without shipping patched jars.

Each scenario above relies on the tighter GraalPy integration to remove cross-runtime overhead, letting the high-level helpers (`Deck`, `Character`, `Keyword`, and the analytics stack) stay responsive even when complex Python-side processing is involved.

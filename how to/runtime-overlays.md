# Runtime overlays

This recipe demonstrates how to project arbitrary graphics onto the Slay the
Spire client while your mod is running. The `OverlayManager` keeps overlays
visible across every screen (combat, map, events, rewards, shops) without
interrupting the core game loop so players can continue acting normally while
your visuals are present.

## Quick start

```python
from modules.basemod_wrapper import show_overlay

warning = show_overlay(
    "assets/chronomancer/images/ui/time_warning.png",
    x=1780,
    y=1040,
    width=260,
    height=120,
    anchor="top_right",
    z_index=25,
    duration=6.0,
    metadata={"tag": "chronomancer_time_warning"},
)

# Fade the overlay while it remains active.
warning.update(opacity=0.65)

# Remove the overlay explicitly once the mechanic resolves.
warning.hide(reason="player_resolved_time_snare")
```

### Scheduling overlays in advance

Use `delay` or `start_time` to queue an overlay for the future. The manager keeps
track of the runtime clock so the overlay activates without freezing combat.

```python
handle = show_overlay(
    "assets/ui/tip_arrow.png",
    x=960,
    y=540,
    width=200,
    height=80,
    anchor="center",
    delay=1.25,
    duration=3.5,
    z_index=5,
)
```

### Updating overlays mid-flight

All geometry and style properties can be changed via
`OverlayHandle.update(...)` or `overlay_manager().update_overlay(...)`.

```python
handle.update(x=player.drawX + 120, y=player.drawY + 300, rotation=22)
```

### Cleaning up

Call `handle.hide()` or `overlay_manager().hide_overlay(identifier)` to remove an
overlay early. `clear_overlays()` removes everything at once, which is handy when
switching scenes or restarting a run.

## Plugin integration

Plugins receive live updates through the hooks `on_overlay_shown`,
`on_overlay_updated` and `on_overlay_hidden`. Each hook receives an
`OverlaySnapshot` plus the active `OverlayManager`, allowing third-party
extensions to drive custom HUD elements, telemetry streams or video capture
pipelines.

```python
def on_overlay_shown(self, overlay, manager):
    print(f"Overlay {overlay.identifier} is live at {overlay.x}, {overlay.y}")
```

Use `manager.snapshots()` to fetch the complete list of overlays if a plugin
needs to resynchronise after loading.

## Texture sources

* **Existing textures** – Pass the libGDX `Texture` instance directly. Width and
  height are inferred automatically.
* **File paths** – Provide the path to a PNG, JPG or similar asset. Width and
  height are inferred when libGDX (or Pillow during tests) can load the image.
  Specify `width` and `height` manually for procedural assets or when running in
  a headless environment.

## Anchoring and coordinate systems

Coordinates are always expressed in screen space. Anchors determine which point
of the overlay is pinned to `(x, y)`. Use one of the presets (`top_right`,
`center`, `bottom_left`, etc.) or supply a custom pair like `(0.2, 0.75)`.

## Lifecycle management best practices

* Keep overlays lightweight—prefer a single overlay with metadata instead of
  spawning duplicates each frame.
* Use `metadata` to track ownership (card IDs, relic IDs, mechanic names) so
  other systems can reason about the overlay.
* Always dispose overlays on quit or when your mechanic deactivates to avoid
  orphaned visuals lingering across fights.

## Troubleshooting

If an overlay fails to appear, check the following:

1. Ensure the asset path is correct and available to the ModTheSpire runtime.
2. Verify that the overlay is not delayed (`start_time`/`delay`) beyond the
   current combat duration.
3. Confirm no plugin hides the overlay immediately via `on_overlay_shown`.
4. When testing outside the game, provide explicit `width` and `height` so the
   manager can render using pure Python fallbacks.

"""Runtime overlay management for Slay the Spire mods.

This module implements a production ready overlay director that lets mods
spawn arbitrary graphics at any point during gameplay without pausing or
blocking the underlying game loop.  Overlays can be positioned anywhere on the
screen, sized independently of the source asset, delayed, time limited and
stacked via z-index ordering.  The manager integrates directly with BaseMod's
``RenderSubscriber`` and ``PostUpdateSubscriber`` hooks so overlays remain
visible across every screen (combat, map, events, rewards, campfires, menus).

The public API intentionally mirrors common game UI terminology:

``overlay_manager``
    Returns the singleton :class:`OverlayManager` instance.

:class:`OverlayManager`
    Provides imperative helpers to create, update and remove overlays.  All
    operations run on the live game state when BaseMod is available but degrade
    gracefully to pure Python logic when the JVM runtime is offline (e.g. in
    tests).

:class:`OverlayHandle`
    Lightweight handle returned by :meth:`OverlayManager.show_overlay`.  It
    exposes convenience methods for hiding and updating overlays and produces
    :class:`OverlaySnapshot` structures for diagnostics.

The manager broadcasts lifecycle events (``on_overlay_shown``,
``on_overlay_updated`` and ``on_overlay_hidden``) through the global
``PLUGIN_MANAGER`` so tooling plugins can mirror overlay state or react to
changes without tight coupling.  Event-driven triggers can be registered via
``OverlayManager.register_trigger`` or :func:`register_overlay_trigger` to show,
update or hide overlays automatically when gameplay events such as
``"card_used"`` or ``"keyword_triggered"`` occur.  Every dispatched event also
fires ``on_overlay_event`` for plugins that need to observe trigger execution or
publish their own overlay automation logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import itertools
import math
from pathlib import Path
import time
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    Protocol,
    runtime_checkable,
)
import weakref

from plugins import PLUGIN_MANAGER

__all__ = [
    "OverlayError",
    "OverlaySnapshot",
    "OverlayHandle",
    "OverlayManager",
    "OverlayTriggerHandle",
    "overlay_manager",
    "show_overlay",
    "hide_overlay",
    "update_overlay",
    "clear_overlays",
    "register_overlay_trigger",
    "unregister_overlay_trigger",
    "handle_overlay_event",
]

ColorTuple = Tuple[float, float, float, float]
AnchorTuple = Tuple[float, float]
OverlaySource = Union[str, Path, Any]


class OverlayError(RuntimeError):
    """Raised when overlays cannot be created or manipulated."""


@runtime_checkable
class _SupportsDimensions(Protocol):
    def getWidth(self) -> int:  # pragma: no cover - structural typing helper
        ...

    def getHeight(self) -> int:  # pragma: no cover - structural typing helper
        ...


@runtime_checkable
class _SupportsColor(Protocol):
    def setColor(self, r: float, g: float, b: float, a: float) -> Any:  # pragma: no cover
        ...

    def getColor(self) -> Any:  # pragma: no cover
        ...


_ANCHOR_MAP: Dict[str, AnchorTuple] = {
    "bottom_left": (0.0, 0.0),
    "bottom_center": (0.5, 0.0),
    "bottom_right": (1.0, 0.0),
    "center_left": (0.0, 0.5),
    "center": (0.5, 0.5),
    "center_right": (1.0, 0.5),
    "top_left": (0.0, 1.0),
    "top_center": (0.5, 1.0),
    "top_right": (1.0, 1.0),
}


def _wrapper_module():
    return import_module("modules.basemod_wrapper")


def _basemod() -> Any | None:
    try:
        return getattr(_wrapper_module(), "basemod")
    except Exception:  # pragma: no cover - optional during tests
        return None


def _libgdx() -> Any | None:
    try:
        return getattr(_wrapper_module(), "libgdx")
    except Exception:  # pragma: no cover - optional during tests
        return None


@dataclass
class _OverlayTexture:
    """Descriptor around the texture backing an overlay."""

    texture: Any | None
    path: str | None
    width: float
    height: float
    owns_texture: bool

    def resolve(self) -> Any | None:
        """Ensure the backing texture object is materialised if possible."""

        if self.texture is not None:
            return self.texture
        if not self.path:
            return None
        libgdx = _libgdx()
        if libgdx is None:
            # Without libGDX we cannot materialise a Texture.  Returning the
            # path is still useful for diagnostics and fake sprite batches used
            # in tests.
            return self.path
        try:
            texture = libgdx.graphics.Texture(self.path)
        except Exception as exc:  # pragma: no cover - requires JVM runtime
            raise OverlayError(
                f"Failed to load overlay texture '{self.path}'. Ensure the asset exists and the JVM runtime is active."
            ) from exc
        self.texture = texture
        self.owns_texture = True
        self.width = float(getattr(texture, "getWidth", lambda: self.width)())
        self.height = float(getattr(texture, "getHeight", lambda: self.height)())
        return texture

    def dispose(self) -> None:
        """Dispose the texture if it originated from this descriptor."""

        if self.owns_texture and self.texture is not None:
            dispose = getattr(self.texture, "dispose", None)
            if callable(dispose):
                try:
                    dispose()
                except Exception:  # pragma: no cover - defensive cleanup
                    pass
            self.texture = None


@dataclass(frozen=True)
class OverlaySnapshot:
    """Immutable public view of an overlay's state."""

    identifier: str
    x: float
    y: float
    width: float
    height: float
    anchor: AnchorTuple
    z_index: int
    opacity: float
    color: ColorTuple
    start_time: float
    duration: float | None
    visible: bool
    metadata: Mapping[str, Any]
    rotation: float
    scale_x: float
    scale_y: float
    texture_source: str | None


@dataclass
class OverlayHandle:
    """Convenience wrapper returned by :meth:`OverlayManager.show_overlay`."""

    identifier: str
    _manager_ref: "weakref.ReferenceType[OverlayManager]"

    @property
    def manager(self) -> "OverlayManager":
        manager = self._manager_ref()
        if manager is None:  # pragma: no cover - only if manager GC'd
            raise OverlayError("Overlay manager is no longer available.")
        return manager

    def hide(self, *, reason: str | None = None) -> None:
        """Hide the overlay associated with this handle."""

        self.manager.hide_overlay(self.identifier, reason=reason)

    def update(self, **changes: Any) -> None:
        """Forward updates to :meth:`OverlayManager.update_overlay`."""

        self.manager.update_overlay(self.identifier, **changes)

    def snapshot(self) -> OverlaySnapshot:
        """Return the latest snapshot for this overlay."""

        return self.manager.overlay_snapshot(self.identifier)


@dataclass
class OverlayTriggerHandle:
    """Handle returned by :meth:`OverlayManager.register_trigger`."""

    identifier: str
    _manager_ref: "weakref.ReferenceType[OverlayManager]"

    @property
    def manager(self) -> "OverlayManager":
        manager = self._manager_ref()
        if manager is None:  # pragma: no cover - manager GC'd
            raise OverlayError("Overlay manager is no longer available.")
        return manager

    def unregister(self) -> None:
        """Remove the associated trigger from the manager."""

        self.manager.unregister_trigger(self.identifier)


@dataclass
class _Overlay:
    identifier: str
    texture: _OverlayTexture
    x: float
    y: float
    width: float
    height: float
    anchor: AnchorTuple
    z_index: int
    opacity: float
    color: ColorTuple
    start_time: float
    duration: float | None
    metadata: Dict[str, Any]
    rotation: float
    scale_x: float
    scale_y: float
    order: int
    visible: bool = False

    def snapshot(self) -> OverlaySnapshot:
        return OverlaySnapshot(
            identifier=self.identifier,
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            anchor=self.anchor,
            z_index=self.z_index,
            opacity=self.opacity,
            color=self.color,
            start_time=self.start_time,
            duration=self.duration,
            visible=self.visible,
            metadata=dict(self.metadata),
            rotation=self.rotation,
            scale_x=self.scale_x,
            scale_y=self.scale_y,
            texture_source=self.texture.path,
        )


@dataclass
class _OverlayTrigger:
    identifier: str
    event: str
    predicate: Callable[[Mapping[str, Any]], bool]
    builder: Callable[[Mapping[str, Any]], Optional[MutableMapping[str, Any]]]
    once: bool
    overlay_identifier: Optional[str]
    replace_existing: Optional[bool]
    cooldown: Optional[float]
    last_fired_time: Optional[float] = None
    last_overlay_identifier: Optional[str] = None


class OverlayManager:
    """Manage the lifecycle of runtime overlays."""

    def __init__(self, *, auto_register: bool = True) -> None:
        self._overlays: Dict[str, _Overlay] = {}
        self._sorted_cache: list[_Overlay] = []
        self._dirty = False
        self._id_counter = itertools.count(1)
        self._trigger_counter = itertools.count(1)
        self._time = 0.0
        self._last_monotonic = time.monotonic()
        self._registered = False
        self._triggers: Dict[str, _OverlayTrigger] = {}
        self._triggers_by_event: Dict[str, list[_OverlayTrigger]] = {}
        if auto_register:
            self._register_with_basemod()

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def _register_with_basemod(self) -> None:
        if self._registered:
            return
        basemod = _basemod()
        if basemod is None:
            return
        try:
            basemod.BaseMod.subscribe(self)
        except Exception:
            return
        self._registered = True

    # BaseMod hook signatures -------------------------------------------
    def receivePostUpdate(self) -> None:  # pragma: no cover - requires JVM
        self._tick_runtime(self._resolve_delta())

    def receiveRender(self, sprite_batch: Any) -> None:  # pragma: no cover - requires JVM
        self.render_to(sprite_batch)

    def receiveCardUsed(self, card: Any) -> None:  # pragma: no cover - requires JVM
        card_id = getattr(card, "cardID", None)
        payload: Dict[str, Any] = {
            "card": card,
            "card_id": card_id,
            "card_name": getattr(card, "name", None),
            "card_type": getattr(getattr(card, "type", None), "name", None),
            "card_rarity": getattr(getattr(card, "rarity", None), "name", None),
            "card_color": getattr(getattr(card, "color", None), "name", None),
            "uuid": str(getattr(card, "uuid", "")) if hasattr(card, "uuid") else None,
            "upgraded": bool(getattr(card, "upgraded", False)),
        }
        self.handle_event("card_used", **payload)

    # ------------------------------------------------------------------
    # Time keeping
    # ------------------------------------------------------------------
    def _resolve_delta(self) -> float:
        libgdx = _libgdx()
        if libgdx is not None:
            try:
                gdx = getattr(libgdx, "Gdx")
                graphics = getattr(gdx, "graphics", None)
                if graphics is not None:
                    delta = getattr(graphics, "getDeltaTime", None)
                    if callable(delta):
                        value = float(delta())
                        if value >= 0:
                            self._last_monotonic = time.monotonic()
                            return value
            except Exception:  # pragma: no cover - guards runtime failures
                pass
        current = time.monotonic()
        delta = max(0.0, current - self._last_monotonic)
        self._last_monotonic = current
        return delta

    def _tick_runtime(self, delta: float) -> None:
        if delta <= 0:
            return
        self._time += delta
        expired: list[str] = []
        now = self._time
        for overlay in self._overlays.values():
            if not overlay.visible and now >= overlay.start_time:
                overlay.visible = True
            if overlay.duration is not None and overlay.visible:
                if now >= overlay.start_time + overlay.duration:
                    expired.append(overlay.identifier)
        for identifier in expired:
            self.hide_overlay(identifier, reason="expired")

    # Debug/testing helper ----------------------------------------------
    def debug_tick(self, delta: float) -> None:
        """Advance the overlay timeline without relying on BaseMod."""

        self._tick_runtime(delta)

    # ------------------------------------------------------------------
    # Overlay CRUD
    # ------------------------------------------------------------------
    def _generate_identifier(self) -> str:
        return f"overlay_{next(self._id_counter)}"

    def _generate_trigger_identifier(self) -> str:
        return f"overlay_trigger_{next(self._trigger_counter)}"

    def _resolve_anchor(self, anchor: Union[str, AnchorTuple]) -> AnchorTuple:
        if isinstance(anchor, str):
            key = anchor.lower().strip()
            if key not in _ANCHOR_MAP:
                raise OverlayError(f"Unknown overlay anchor '{anchor}'.")
            return _ANCHOR_MAP[key]
        if not isinstance(anchor, (tuple, list)) or len(anchor) != 2:
            raise OverlayError("Anchor must be a named preset or a (x, y) tuple.")
        return (float(anchor[0]), float(anchor[1]))

    def _coerce_color(self, color: Optional[Sequence[float]], opacity: float) -> ColorTuple:
        if color is None:
            return (1.0, 1.0, 1.0, float(opacity))
        if len(color) not in (3, 4):
            raise OverlayError("Color must contain 3 or 4 components.")
        components = list(float(c) for c in color)
        if len(components) == 3:
            components.append(float(opacity))
        components[3] = float(opacity) * components[3]
        return tuple(max(0.0, min(1.0, c)) for c in components)  # type: ignore[return-value]

    def _probe_dimensions(self, path: str) -> Tuple[float, float] | None:
        try:
            from PIL import Image  # type: ignore
        except Exception:
            return None
        try:
            with Image.open(path) as img:
                return float(img.width), float(img.height)
        except Exception:
            return None

    def _prepare_texture(
        self,
        source: OverlaySource,
        *,
        width: float | None,
        height: float | None,
    ) -> _OverlayTexture:
        path: str | None = None
        texture: Any | None = None
        if isinstance(source, (str, Path)):
            path = str(source)
        else:
            texture = source
        resolved_width = float(width) if width is not None else None
        resolved_height = float(height) if height is not None else None
        if texture is not None:
            if isinstance(texture, _SupportsDimensions):
                resolved_width = resolved_width or float(texture.getWidth())
                resolved_height = resolved_height or float(texture.getHeight())
            else:
                resolved_width = resolved_width or float(getattr(texture, "width", 0)) or None
                resolved_height = resolved_height or float(getattr(texture, "height", 0)) or None
        if (resolved_width is None or resolved_height is None) and path:
            dims = self._probe_dimensions(path)
            if dims:
                resolved_width, resolved_height = dims
        if resolved_width is None or resolved_height is None:
            raise OverlayError(
                "Overlay dimensions could not be determined. Provide explicit width and height when using non-texture sources."
            )
        return _OverlayTexture(
            texture=texture,
            path=path,
            width=float(resolved_width),
            height=float(resolved_height),
            owns_texture=False,
        )

    def show_overlay(
        self,
        source: OverlaySource,
        *,
        x: float,
        y: float,
        width: float | None = None,
        height: float | None = None,
        anchor: Union[str, AnchorTuple] = "bottom_left",
        duration: float | None = None,
        delay: float = 0.0,
        start_time: float | None = None,
        z_index: int = 0,
        opacity: float = 1.0,
        color: Optional[Sequence[float]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        identifier: str | None = None,
        replace_existing: bool = False,
    ) -> OverlayHandle:
        """Create a new overlay using ``source`` as the backing graphic."""

        if duration is not None and duration < 0:
            raise OverlayError("Duration must be positive when provided.")
        if opacity < 0 or opacity > 1:
            raise OverlayError("Opacity must be between 0 and 1.")
        anchor_tuple = self._resolve_anchor(anchor)
        texture = self._prepare_texture(source, width=width, height=height)
        overlay_id = identifier or self._generate_identifier()
        existing = self._overlays.get(overlay_id)
        if existing is not None and not replace_existing:
            raise OverlayError(f"Overlay '{overlay_id}' already exists.")
        self._register_with_basemod()
        start = start_time if start_time is not None else self._time + max(0.0, delay)
        overlay = _Overlay(
            identifier=overlay_id,
            texture=texture,
            x=float(x),
            y=float(y),
            width=float(texture.width if width is None else width),
            height=float(texture.height if height is None else height),
            anchor=anchor_tuple,
            z_index=int(z_index),
            opacity=float(opacity),
            color=self._coerce_color(color, opacity),
            start_time=float(start),
            duration=float(duration) if duration is not None else None,
            metadata=dict(metadata or {}),
            rotation=float(rotation),
            scale_x=float(scale_x),
            scale_y=float(scale_y),
            order=next(self._id_counter),
            visible=self._time >= start,
        )
        self._overlays[overlay_id] = overlay
        self._dirty = True
        snapshot = overlay.snapshot()
        PLUGIN_MANAGER.broadcast("on_overlay_shown", overlay=snapshot, manager=self)
        return OverlayHandle(overlay_id, weakref.ref(self))

    def update_overlay(self, identifier: str, **changes: Any) -> OverlaySnapshot:
        """Mutate overlay properties and return the latest snapshot."""

        overlay = self._overlays.get(identifier)
        if overlay is None:
            raise OverlayError(f"Overlay '{identifier}' does not exist.")
        allowed = {
            "x",
            "y",
            "width",
            "height",
            "anchor",
            "z_index",
            "opacity",
            "color",
            "duration",
            "metadata",
            "rotation",
            "scale_x",
            "scale_y",
            "start_time",
            "delay",
            "source",
        }
        invalid = set(changes) - allowed
        if invalid:
            raise OverlayError(f"Unsupported overlay updates: {', '.join(sorted(invalid))}.")
        if "source" in changes:
            overlay.texture.dispose()
            overlay.texture = self._prepare_texture(
                changes["source"],
                width=changes.get("width", overlay.width),
                height=changes.get("height", overlay.height),
            )
        if "width" in changes:
            overlay.width = float(changes["width"])
        if "height" in changes:
            overlay.height = float(changes["height"])
        if "x" in changes:
            overlay.x = float(changes["x"])
        if "y" in changes:
            overlay.y = float(changes["y"])
        if "anchor" in changes:
            overlay.anchor = self._resolve_anchor(changes["anchor"])
        if "z_index" in changes:
            overlay.z_index = int(changes["z_index"])
            self._dirty = True
        if "opacity" in changes:
            value = float(changes["opacity"])
            if value < 0 or value > 1:
                raise OverlayError("Opacity must be between 0 and 1.")
            overlay.opacity = value
            overlay.color = self._coerce_color(changes.get("color"), value)
        elif "color" in changes:
            overlay.color = self._coerce_color(changes["color"], overlay.opacity)
        if "duration" in changes:
            overlay.duration = float(changes["duration"]) if changes["duration"] is not None else None
        if "metadata" in changes:
            overlay.metadata = dict(changes["metadata"])
        if "rotation" in changes:
            overlay.rotation = float(changes["rotation"])
        if "scale_x" in changes:
            overlay.scale_x = float(changes["scale_x"])
        if "scale_y" in changes:
            overlay.scale_y = float(changes["scale_y"])
        if "start_time" in changes or "delay" in changes:
            if "start_time" in changes:
                overlay.start_time = float(changes["start_time"])
            else:
                overlay.start_time = self._time + max(0.0, float(changes["delay"]))
            overlay.visible = self._time >= overlay.start_time
        snapshot = overlay.snapshot()
        PLUGIN_MANAGER.broadcast("on_overlay_updated", overlay=snapshot, manager=self)
        return snapshot

    def hide_overlay(self, identifier: str, *, reason: str | None = None) -> None:
        """Remove an overlay from the runtime."""

        overlay = self._overlays.pop(identifier, None)
        if overlay is None:
            return
        snapshot = overlay.snapshot()
        overlay.texture.dispose()
        self._dirty = True
        PLUGIN_MANAGER.broadcast(
            "on_overlay_hidden",
            overlay=snapshot,
            manager=self,
            reason=reason or "explicit",
        )

    def clear(self) -> None:
        """Remove all overlays immediately."""

        for identifier in list(self._overlays):
            self.hide_overlay(identifier, reason="cleared")

    # ------------------------------------------------------------------
    # Trigger registration
    # ------------------------------------------------------------------
    def _normalise_event(self, event: str) -> str:
        if not isinstance(event, str):
            raise OverlayError("Event name must be a string.")
        key = event.strip().lower()
        if not key:
            raise OverlayError("Event name cannot be empty.")
        return key

    def _make_predicate(
        self,
        match: Optional[Mapping[str, Any]],
        predicate: Optional[Callable[[Mapping[str, Any]], bool]],
    ) -> Callable[[Mapping[str, Any]], bool]:
        checks: list[Callable[[Mapping[str, Any]], bool]] = []
        if match:
            def _match(payload: Mapping[str, Any]) -> bool:
                for key, expected in match.items():
                    actual = payload.get(key)
                    if callable(expected):
                        if not expected(actual):
                            return False
                        continue
                    if isinstance(expected, (set, frozenset, list, tuple)):
                        if actual not in expected:
                            return False
                        continue
                    if actual != expected:
                        return False
                return True

            checks.append(_match)
        if predicate is not None:
            checks.append(predicate)
        if not checks:
            return lambda payload: True

        def _combined(payload: Mapping[str, Any]) -> bool:
            return all(check(payload) for check in checks)

        return _combined

    def _coerce_builder(
        self,
        *,
        source: Optional[OverlaySource],
        overlay_kwargs: Optional[Mapping[str, Any]],
        factory: Optional[Callable[[Mapping[str, Any]], MutableMapping[str, Any]]],
    ) -> Callable[[Mapping[str, Any]], Optional[MutableMapping[str, Any]]]:
        if factory is not None:
            def _factory(payload: Mapping[str, Any]) -> Optional[MutableMapping[str, Any]]:
                result = factory(payload)
                if result is None:
                    return None
                return dict(result)

            return _factory

        if source is None:
            raise OverlayError("Either 'source' or 'builder' must be provided when registering a trigger.")

        options = dict(overlay_kwargs or {})
        metadata = options.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise OverlayError("Trigger metadata must be a mapping when provided.")

        def _builder(payload: Mapping[str, Any]) -> MutableMapping[str, Any]:
            resolved_source = source(payload) if callable(source) else source
            if resolved_source is None:
                raise OverlayError("Trigger source callable returned None.")
            spec: Dict[str, Any] = {
                "source": resolved_source,
            }
            spec.update(options)
            if metadata is not None:
                spec["metadata"] = dict(metadata)
            return spec

        return _builder

    def register_trigger(
        self,
        event: str,
        *,
        match: Optional[Mapping[str, Any]] = None,
        predicate: Optional[Callable[[Mapping[str, Any]], bool]] = None,
        source: Optional[Union[OverlaySource, Callable[[Mapping[str, Any]], OverlaySource]]] = None,
        overlay_kwargs: Optional[Mapping[str, Any]] = None,
        builder: Optional[Callable[[Mapping[str, Any]], MutableMapping[str, Any]]] = None,
        identifier: Optional[str] = None,
        overlay_identifier: Optional[str] = None,
        replace_existing: Optional[bool] = None,
        once: bool = False,
        cooldown: Optional[float] = None,
    ) -> OverlayTriggerHandle:
        """Register an automatic overlay trigger for ``event``."""

        if cooldown is not None and cooldown < 0:
            raise OverlayError("Cooldown must be positive when provided.")
        event_key = self._normalise_event(event)
        trigger_id = identifier or self._generate_trigger_identifier()
        if trigger_id in self._triggers:
            raise OverlayError(f"Overlay trigger '{trigger_id}' is already registered.")
        predicate_fn = self._make_predicate(match, predicate)
        builder_fn = self._coerce_builder(
            source=source,
            overlay_kwargs=overlay_kwargs,
            factory=builder,
        )
        trigger = _OverlayTrigger(
            identifier=trigger_id,
            event=event_key,
            predicate=predicate_fn,
            builder=builder_fn,
            once=once,
            overlay_identifier=overlay_identifier,
            replace_existing=replace_existing if replace_existing is not None else (overlay_identifier is not None),
            cooldown=cooldown,
        )
        self._triggers[trigger_id] = trigger
        self._triggers_by_event.setdefault(event_key, []).append(trigger)
        self._register_with_basemod()
        return OverlayTriggerHandle(trigger_id, weakref.ref(self))

    def unregister_trigger(self, identifier: str) -> None:
        trigger = self._triggers.pop(identifier, None)
        if trigger is None:
            return
        bucket = self._triggers_by_event.get(trigger.event)
        if bucket is not None:
            self._triggers_by_event[trigger.event] = [item for item in bucket if item.identifier != identifier]
            if not self._triggers_by_event[trigger.event]:
                self._triggers_by_event.pop(trigger.event, None)

    def clear_triggers(self, event: Optional[str] = None) -> None:
        """Remove registered triggers, optionally filtered by ``event``."""

        if event is None:
            self._triggers.clear()
            self._triggers_by_event.clear()
            return
        event_key = self._normalise_event(event)
        for trigger in list(self._triggers_by_event.get(event_key, [])):
            self._triggers.pop(trigger.identifier, None)
        self._triggers_by_event.pop(event_key, None)

    @property
    def active_trigger_ids(self) -> Tuple[str, ...]:
        return tuple(self._triggers.keys())

    def handle_event(self, event: str, **payload: Any) -> None:
        """Dispatch ``event`` to registered overlay triggers."""

        event_key = self._normalise_event(event)
        triggers = list(self._triggers_by_event.get(event_key, []))
        if not triggers:
            PLUGIN_MANAGER.broadcast(
                "on_overlay_event",
                event=event_key,
                payload=dict(payload),
                manager=self,
                triggers=(),
            )
            return
        executed: list[str] = []
        now = self._time
        for trigger in list(triggers):
            if trigger.identifier not in self._triggers:
                continue
            if not trigger.predicate(payload):
                continue
            if trigger.cooldown is not None and trigger.last_fired_time is not None:
                if now - trigger.last_fired_time < trigger.cooldown:
                    continue
            try:
                spec_mapping = trigger.builder(payload)
            except Exception as exc:  # pragma: no cover - defensive
                raise OverlayError(
                    f"Overlay trigger '{trigger.identifier}' failed to build an overlay payload: {exc}"
                ) from exc
            if not spec_mapping:
                continue
            spec = dict(spec_mapping)
            action = str(spec.pop("action", "show")).lower()
            overlay_id = spec.pop("identifier", None) or trigger.overlay_identifier or trigger.last_overlay_identifier
            if action == "show":
                source = spec.pop("source", None)
                if source is None:
                    raise OverlayError(
                        f"Overlay trigger '{trigger.identifier}' must provide a 'source' when showing an overlay."
                    )
                if overlay_id is not None and "identifier" not in spec:
                    spec["identifier"] = overlay_id
                if trigger.replace_existing is not None and "replace_existing" not in spec:
                    spec["replace_existing"] = trigger.replace_existing
                handle = self.show_overlay(source, **spec)
                trigger.last_overlay_identifier = handle.identifier
            elif action == "update":
                if overlay_id is None:
                    raise OverlayError(
                        f"Overlay trigger '{trigger.identifier}' attempted to update an unknown overlay."
                    )
                self.update_overlay(overlay_id, **spec)
                trigger.last_overlay_identifier = overlay_id
            elif action == "hide":
                if overlay_id is None:
                    continue
                reason = spec.pop("reason", None)
                self.hide_overlay(overlay_id, reason=reason)
                trigger.last_overlay_identifier = overlay_id
            else:
                raise OverlayError(f"Unsupported trigger action '{action}' for overlay trigger '{trigger.identifier}'.")
            trigger.last_fired_time = now
            executed.append(trigger.identifier)
            if trigger.once:
                self.unregister_trigger(trigger.identifier)
        PLUGIN_MANAGER.broadcast(
            "on_overlay_event",
            event=event_key,
            payload=dict(payload),
            manager=self,
            triggers=tuple(executed),
        )

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _sorted_overlays(self) -> Iterable[_Overlay]:
        if not self._dirty:
            return self._sorted_cache
        overlays = sorted(
            self._overlays.values(),
            key=lambda item: (item.z_index, item.order),
        )
        self._sorted_cache = overlays
        self._dirty = False
        return overlays

    def _apply_color(self, sprite_batch: Any, overlay: _Overlay) -> Any | None:
        if isinstance(sprite_batch, _SupportsColor):
            try:
                previous = sprite_batch.getColor()
            except Exception:  # pragma: no cover - fallback path
                previous = None
            try:
                sprite_batch.setColor(*overlay.color)
            except Exception:  # pragma: no cover - fallback path
                pass
            return previous
        return None

    def _restore_color(self, sprite_batch: Any, previous: Any) -> None:
        if previous is None:
            return
        restore = getattr(sprite_batch, "setColor", None)
        if callable(restore):
            try:
                if isinstance(previous, _SupportsColor):  # pragma: no cover - defensive
                    restore(previous)
                else:
                    if hasattr(previous, "r"):
                        restore(previous.r, previous.g, previous.b, previous.a)
                    else:
                        restore(*previous)
            except Exception:  # pragma: no cover - defensive
                pass

    def render_to(self, sprite_batch: Any) -> None:
        """Render all currently visible overlays onto ``sprite_batch``."""

        now = self._time
        for overlay in self._sorted_overlays():
            if not overlay.visible or now < overlay.start_time:
                continue
            if overlay.duration is not None and now > overlay.start_time + overlay.duration:
                continue
            width = overlay.width
            height = overlay.height
            anchor_x, anchor_y = overlay.anchor
            offset_x = overlay.x - width * anchor_x
            offset_y = overlay.y - height * anchor_y
            texture = overlay.texture.resolve()
            draw = getattr(sprite_batch, "draw", None)
            if not callable(draw):
                raise OverlayError("SpriteBatch-like object must provide a 'draw' method.")
            previous_color = self._apply_color(sprite_batch, overlay)
            try:
                if any(
                    not math.isclose(value, default)
                    for value, default in (
                        (overlay.rotation, 0.0),
                        (overlay.scale_x, 1.0),
                        (overlay.scale_y, 1.0),
                    )
                ):
                    draw(
                        texture,
                        float(offset_x),
                        float(offset_y),
                        float(width * 0.5),
                        float(height * 0.5),
                        float(width),
                        float(height),
                        float(overlay.scale_x),
                        float(overlay.scale_y),
                        float(overlay.rotation),
                    )
                else:
                    draw(texture, float(offset_x), float(offset_y), float(width), float(height))
            finally:
                self._restore_color(sprite_batch, previous_color)

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------
    @property
    def active_overlay_ids(self) -> Tuple[str, ...]:
        return tuple(self._overlays.keys())

    def overlay_snapshot(self, identifier: str) -> OverlaySnapshot:
        overlay = self._overlays.get(identifier)
        if overlay is None:
            raise OverlayError(f"Overlay '{identifier}' does not exist.")
        return overlay.snapshot()

    def snapshots(self) -> Tuple[OverlaySnapshot, ...]:
        return tuple(overlay.snapshot() for overlay in self._overlays.values())


# Global singleton -------------------------------------------------------
_OVERLAY_MANAGER = OverlayManager()


def overlay_manager() -> OverlayManager:
    """Return the global overlay manager."""

    return _OVERLAY_MANAGER


def show_overlay(*args: Any, **kwargs: Any) -> OverlayHandle:
    """Proxy to :meth:`OverlayManager.show_overlay` on the global manager."""

    return _OVERLAY_MANAGER.show_overlay(*args, **kwargs)


def update_overlay(identifier: str, **changes: Any) -> OverlaySnapshot:
    """Proxy to :meth:`OverlayManager.update_overlay`."""

    return _OVERLAY_MANAGER.update_overlay(identifier, **changes)


def hide_overlay(identifier: str, *, reason: str | None = None) -> None:
    """Proxy to :meth:`OverlayManager.hide_overlay`."""

    _OVERLAY_MANAGER.hide_overlay(identifier, reason=reason)


def clear_overlays() -> None:
    """Proxy to :meth:`OverlayManager.clear`."""

    _OVERLAY_MANAGER.clear()


def register_overlay_trigger(*args: Any, **kwargs: Any) -> OverlayTriggerHandle:
    """Proxy to :meth:`OverlayManager.register_trigger`."""

    return _OVERLAY_MANAGER.register_trigger(*args, **kwargs)


def unregister_overlay_trigger(identifier: str) -> None:
    """Proxy to :meth:`OverlayManager.unregister_trigger`."""

    _OVERLAY_MANAGER.unregister_trigger(identifier)


def handle_overlay_event(event: str, **payload: Any) -> None:
    """Proxy to :meth:`OverlayManager.handle_event`."""

    _OVERLAY_MANAGER.handle_event(event, **payload)


PLUGIN_MANAGER.expose("overlay_manager", overlay_manager)
PLUGIN_MANAGER.expose("OverlayManager", OverlayManager)
PLUGIN_MANAGER.expose("OverlayHandle", OverlayHandle)
PLUGIN_MANAGER.expose("OverlaySnapshot", OverlaySnapshot)
PLUGIN_MANAGER.expose("OverlayTriggerHandle", OverlayTriggerHandle)
PLUGIN_MANAGER.expose("register_overlay_trigger", register_overlay_trigger)
PLUGIN_MANAGER.expose("unregister_overlay_trigger", unregister_overlay_trigger)
PLUGIN_MANAGER.expose("handle_overlay_event", handle_overlay_event)
PLUGIN_MANAGER.expose_module("modules.basemod_wrapper.overlays", alias="overlays")

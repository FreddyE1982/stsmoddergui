"""Project bootstrap helpers for the Digitales Monster mod package.

The module assembles a :class:`~modules.basemod_wrapper.project.ModProject`
configuration backed by the high level helpers exposed through
:mod:`modules.modbuilder`.  It also wires the GraalPy experimental runtime into
our project pipeline so downstream tools can rely on the polyglot backend
without having to duplicate activation logic.

Typical usage::

    from mods.digitalesmonster.project import (
        DigitalesMonsterProject,
        DigitalesMonsterProjectConfig,
        bootstrap_digitalesmonster_project,
    )

    project = bootstrap_digitalesmonster_project(simulate_graalpy=True)
    basemod_project = project.mod_project

    # Register cards, stances and additional metadata on ``basemod_project``
    # before bundling.

The bootstrapper keeps the workflow plugin-friendly: every relevant object is
exposed through :mod:`plugins` so third-party extensions can augment the mod at
runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Dict, Iterable, Mapping, Optional, Sequence

from modules.basemod_wrapper import experimental
from modules.basemod_wrapper.experimental.graalpy_runtime import GraalPyProvisioningState
from modules.basemod_wrapper.project import ModProject, create_project
from modules.modbuilder import Character, CharacterColorConfig, CharacterImageConfig, CharacterStartConfig, Deck
from plugins import PLUGIN_MANAGER

__all__ = [
    "DigitalesMonsterProject",
    "DigitalesMonsterProjectConfig",
    "DigitalesMonsterDeck",
    "DigitalesMonsterCharacter",
    "bootstrap_digitalesmonster_project",
]


@dataclass(slots=True)
class DigitalesMonsterProjectConfig:
    """Static metadata describing the Digitales Monster mod package."""

    mod_id: str = "digitalesmonster"
    name: str = "Digitales Monster"
    author: str = "Digital Frontier Initiative"
    description: str = (
        "Digitation über mehrere Evolutionspfade hinweg mit Stabilitätsmanagement,"
        " DigiSoul-Verstärkung und Stance-getriebenen Kampfabschnitten."
    )
    version: str = "0.1.0"
    dependencies: Sequence[str] = ("basemod", "stslib")


class DigitalesMonsterDeck(Deck):
    """Base deck placeholder used by :class:`DigitalesMonsterCharacter`."""

    display_name = "Digitales Monster Kernkarten"


class DigitalesMonsterCharacter(Character):
    """Character scaffold for the Digitales Monster player avatar."""

    def __init__(self) -> None:
        super().__init__()
        self.name = "Digitales Monster"
        self.mod_id = "digitalesmonster"
        self.author = "Digital Frontier Initiative"
        self.description = (
            "Agumons Evolutionslinien treffen auf Stabilitäts- und DigiSoul-Mechaniken."
        )
        self.version = "0.1.0"
        self.start = CharacterStartConfig(hp=70, max_hp=70, gold=99, deck=DigitalesMonsterDeck)
        self.loadout_description = (
            "Beginnt als natürliches Rookie-Level mit Fokus auf Stabilität und DigiSoul-Aufbau."
        )
        self.energyPerTurn = 3
        self.handSize = 5
        self.orbSlots = 0
        self.color = CharacterColorConfig(
            identifier="DIGITALESMONSTER_ORANGE",
            card_color=(0.95, 0.58, 0.18, 1.0),
            trail_color=(0.96, 0.68, 0.24, 1.0),
            slash_color=(1.0, 0.76, 0.32, 1.0),
            attack_bg="digitalesmonster/images/cards/attack.png",
            skill_bg="digitalesmonster/images/cards/skill.png",
            power_bg="digitalesmonster/images/cards/power.png",
            orb="digitalesmonster/images/cards/orb.png",
            attack_bg_small="digitalesmonster/images/cards/attack_small.png",
            skill_bg_small="digitalesmonster/images/cards/skill_small.png",
            power_bg_small="digitalesmonster/images/cards/power_small.png",
            orb_small="digitalesmonster/images/cards/orb_small.png",
        )
        self.image = CharacterImageConfig(
            shoulder1="digitalesmonster/images/character/shoulder1.png",
            shoulder2="digitalesmonster/images/character/shoulder2.png",
            corpse="digitalesmonster/images/character/corpse.png",
            energy_orb="digitalesmonster/images/character/energy_orb.png",
            staticspineanimation="digitalesmonster/images/character/static.png",
        )


@dataclass(slots=True)
class DigitalesMonsterProject:
    """High level façade that wires Digitales Monster helpers into a project."""

    config: DigitalesMonsterProjectConfig = field(default_factory=DigitalesMonsterProjectConfig)
    auto_expose: bool = True
    _project: ModProject = field(init=False)
    _graalpy_state: Optional[GraalPyProvisioningState] = field(init=False, default=None)
    _plugin_exports: Dict[str, object] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._project = create_project(
            self.config.mod_id,
            self.config.name,
            self.config.author,
            self.config.description,
            version=self.config.version,
        )
        if self.auto_expose:
            self._expose_to_plugins()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def mod_project(self) -> ModProject:
        """Return the underlying :class:`ModProject` instance."""

        return self._project

    @property
    def graalpy_state(self) -> Optional[GraalPyProvisioningState]:
        """Return the cached GraalPy provisioning state, if available."""

        return self._graalpy_state

    def expose(self, name: str, obj: object) -> None:
        """Expose ``obj`` under ``name`` via the global plugin manager."""

        PLUGIN_MANAGER.expose(name, obj)
        self._plugin_exports[name] = obj

    def _expose_to_plugins(self) -> None:
        self.expose("digitalesmonster_project_metadata", self.config)
        self.expose("digitalesmonster_mod_project", self._project)
        self.expose("digitalesmonster_project_builder", self)

    def enable_graalpy_runtime(
        self,
        *,
        simulate: bool = False,
        allow_fallback: bool = True,
        executable: Optional[Path] = None,
    ) -> GraalPyProvisioningState:
        """Activate the GraalPy backend and cache the provisioning state.

        Parameters
        ----------
        simulate:
            When ``True`` the activation relies on the built-in simulation
            helpers provided by :mod:`graalpy_runtime`.  This avoids installing
            a full GraalPy distribution during tests or documentation builds.
        allow_fallback:
            Permit the runtime to restore the previous backend when activation
            fails.  The flag maps to the ``STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK``
            environment variable.
        executable:
            Optional explicit path to the GraalPy interpreter used when
            ``simulate`` is ``True``.
        """

        env: Dict[str, str] = {}
        if simulate:
            env["STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE"] = "1"
            env.setdefault(
                "STSMODDERGUI_GRAALPY_RUNTIME_SIMULATE_EXECUTABLE",
                str(executable or Path(sys.executable)),
            )
        if allow_fallback:
            env["STSMODDERGUI_GRAALPY_RUNTIME_ALLOW_FALLBACK"] = "1"
        for key, value in env.items():
            os.environ[key] = value

        module = experimental.on("graalpy_runtime")
        state = PLUGIN_MANAGER.exposed.get("experimental_graalpy_state")
        if not isinstance(state, GraalPyProvisioningState):
            # Ensure we have an explicit state when the plugin exposure is not
            # available (e.g. when activation completed before plugins were
            # registered).
            provisioner = getattr(module, "activate", None)
            if provisioner is None:
                raise RuntimeError("graalpy_runtime module does not expose an activate hook.")
            state = provisioner()
        self._graalpy_state = state
        self.expose("digitalesmonster_graalpy_state", state)
        return state

    def is_graalpy_active(self) -> bool:
        """Return ``True`` when the GraalPy runtime is currently active."""

        return experimental.is_active("graalpy_runtime")

    def configure_character_assets(self, character: Optional[DigitalesMonsterCharacter] = None) -> None:
        """Register the current colour definition and placeholder assets."""

        character = character or DigitalesMonsterCharacter()
        color = character.color
        if not all(
            (
                color.identifier,
                color.card_color,
                color.trail_color,
                color.slash_color,
                color.attack_bg,
                color.skill_bg,
                color.power_bg,
                color.orb,
                color.attack_bg_small,
                color.skill_bg_small,
                color.power_bg_small,
                color.orb_small,
            )
        ):
            raise ValueError("Character colour configuration is incomplete.")
        self._project.define_color(
            color.identifier,  # type: ignore[arg-type]
            card_color=color.card_color,  # type: ignore[arg-type]
            trail_color=color.trail_color,  # type: ignore[arg-type]
            slash_color=color.slash_color,  # type: ignore[arg-type]
            attack_bg=color.attack_bg,  # type: ignore[arg-type]
            skill_bg=color.skill_bg,  # type: ignore[arg-type]
            power_bg=color.power_bg,  # type: ignore[arg-type]
            orb=color.orb,  # type: ignore[arg-type]
            attack_bg_small=color.attack_bg_small,  # type: ignore[arg-type]
            skill_bg_small=color.skill_bg_small,  # type: ignore[arg-type]
            power_bg_small=color.power_bg_small,  # type: ignore[arg-type]
            orb_small=color.orb_small,  # type: ignore[arg-type]
        )
        self.expose("digitalesmonster_character_color", color)
        self.expose("digitalesmonster_character_image", character.image)


def bootstrap_digitalesmonster_project(
    *,
    activate_graalpy: bool = True,
    simulate_graalpy: bool = True,
    graalpy_executable: Optional[Path] = None,
) -> DigitalesMonsterProject:
    """Create a :class:`DigitalesMonsterProject` and optionally enable GraalPy."""

    project = DigitalesMonsterProject()
    if activate_graalpy:
        project.enable_graalpy_runtime(simulate=simulate_graalpy, executable=graalpy_executable)
    return project


PLUGIN_MANAGER.expose("DigitalesMonsterProject", DigitalesMonsterProject)
PLUGIN_MANAGER.expose("DigitalesMonsterProjectConfig", DigitalesMonsterProjectConfig)
PLUGIN_MANAGER.expose("DigitalesMonsterDeck", DigitalesMonsterDeck)
PLUGIN_MANAGER.expose("DigitalesMonsterCharacter", DigitalesMonsterCharacter)
PLUGIN_MANAGER.expose("digitalesmonster_bootstrap_project", bootstrap_digitalesmonster_project)
PLUGIN_MANAGER.expose_module("mods.digitalesmonster.project", alias="digitalesmonster_project")

"""Configuration helpers for the BaseMod JPype wrapper."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Mapping, MutableMapping, Optional

DEFAULT_CONFIG_FILE = Path.home() / ".stsmoddergui" / "basemod.json"


@dataclass(slots=True)
class BaseModConfig:
    """Runtime configuration describing how to bootstrap BaseMod."""

    basemod_jar: Path
    slay_the_spire_jar: Optional[Path] = None
    extra_classpath: List[Path] = field(default_factory=list)
    jvm_args: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "BaseModConfig":
        env = env or os.environ
        jar = env.get("BASEMOD_JAR")
        if not jar:
            raise RuntimeError(
                "Environment variable BASEMOD_JAR must point to the BaseMod JAR file."
            )
        basemod_jar = Path(jar).expanduser().resolve()
        sts_jar = env.get("SLAY_THE_SPIRE_JAR")
        extra = [Path(p).expanduser().resolve() for p in env.get("BASEMOD_EXTRA_CLASSPATH", "").split(os.pathsep) if p]
        jvm_args = [arg for arg in env.get("BASEMOD_JVM_ARGS", "").split(" ") if arg]
        return cls(
            basemod_jar=basemod_jar,
            slay_the_spire_jar=Path(sts_jar).expanduser().resolve() if sts_jar else None,
            extra_classpath=extra,
            jvm_args=jvm_args,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, str | Iterable[str] | None]) -> "BaseModConfig":
        basemod_jar = Path(str(data["basemod_jar"])).expanduser().resolve()
        sts_jar = data.get("slay_the_spire_jar")
        extra = [Path(str(p)).expanduser().resolve() for p in data.get("extra_classpath", []) or []]
        jvm_args = [str(arg) for arg in data.get("jvm_args", []) or []]
        return cls(
            basemod_jar=basemod_jar,
            slay_the_spire_jar=Path(str(sts_jar)).expanduser().resolve() if sts_jar else None,
            extra_classpath=extra,
            jvm_args=jvm_args,
        )

    def to_mapping(self) -> MutableMapping[str, object]:
        return {
            "basemod_jar": str(self.basemod_jar),
            "slay_the_spire_jar": str(self.slay_the_spire_jar) if self.slay_the_spire_jar else None,
            "extra_classpath": [str(p) for p in self.extra_classpath],
            "jvm_args": list(self.jvm_args),
        }

    def dump(self, destination: Path | None = None) -> None:
        destination = destination or DEFAULT_CONFIG_FILE
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.to_mapping(), indent=2))

    @classmethod
    def load(cls, source: Path | None = None) -> "BaseModConfig":
        source = source or DEFAULT_CONFIG_FILE
        if not source.exists():
            raise FileNotFoundError(f"Configuration file not found: {source}")
        data = json.loads(source.read_text())
        return cls.from_mapping(data)

    def compute_classpath(self) -> List[str]:
        paths = [str(self.basemod_jar)]
        if self.slay_the_spire_jar:
            paths.append(str(self.slay_the_spire_jar))
        paths.extend(str(p) for p in self.extra_classpath)
        return paths

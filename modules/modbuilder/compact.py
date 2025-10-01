"""Compact bundle packaging helpers for stsmoddergui projects.

This module introduces the ``compact`` bundling pipeline which serialises an
entire mod directory into a single ``.pystsmod`` archive alongside a lightweight
ModTheSpire-compatible loader jar.  The archive packs Python sources, assets
and patch metadata into a compressed payload while the loader exposes enough
information for future runtime bootstrappers to hydrate the bundle entirely in
memory.  Tooling consumers can rely on :class:`CompactBundleLoader` to inspect
archives without touching disk.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, Mapping, Tuple
import zipfile

from plugins import PLUGIN_MANAGER
from modules.basemod_wrapper.loader import BaseModBootstrapError

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from modules.basemod_wrapper.project import BundleOptions, ModProject


class CompactBundleError(BaseModBootstrapError):
    """Raised when a compact bundle cannot be produced or inspected."""


@dataclass(frozen=True)
class CompactBundleMetadata:
    """Describes the logical content of a ``.pystsmod`` archive."""

    mod_id: str
    name: str
    author: str
    description: str
    version: str
    dependencies: Tuple[str, ...]
    sts_version: str
    mts_version: str
    python_packages: Tuple[Dict[str, str], ...]
    created_at: str

    @classmethod
    def build(
        cls,
        project: "ModProject",
        options: "BundleOptions",
        mod_directory: Path,
    ) -> "CompactBundleMetadata":
        packages = tuple(_collect_python_packages(mod_directory))
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return cls(
            mod_id=project.mod_id,
            name=project.name,
            author=project.author,
            description=project.description,
            version=options.version,
            dependencies=tuple(dict.fromkeys(options.dependencies)),
            sts_version=options.sts_version,
            mts_version=options.mts_version,
            python_packages=packages,
            created_at=timestamp,
        )

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "mod_id": self.mod_id,
            "name": self.name,
            "author": self.author,
            "description": self.description,
            "version": self.version,
            "dependencies": list(self.dependencies),
            "sts_version": self.sts_version,
            "mts_version": self.mts_version,
            "created_at": self.created_at,
            "packaging": "compact",
            "python_packages": [dict(package) for package in self.python_packages],
        }
        return payload


@dataclass(frozen=True)
class CompactBundleArtifacts:
    """Records artefacts produced by :func:`build_compact_bundle`."""

    mod_directory: Path
    bundle_path: Path
    dummy_mod_path: Path
    metadata: Mapping[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mod_directory": str(self.mod_directory),
            "bundle_path": str(self.bundle_path),
            "dummy_mod_path": str(self.dummy_mod_path),
            "metadata": dict(self.metadata),
        }


def _collect_python_packages(mod_directory: Path) -> Iterable[Dict[str, str]]:
    python_root = mod_directory / "python"
    if not python_root.exists():
        raise CompactBundleError(
            f"Compact bundles require a python/ directory inside '{mod_directory}'."
        )
    packages: list[Dict[str, str]] = []
    for candidate in sorted(python_root.iterdir()):
        if not candidate.is_dir():
            continue
        entrypoint = candidate / "entrypoint.py"
        init_py = candidate / "__init__.py"
        if entrypoint.exists() and init_py.exists():
            packages.append(
                {
                    "package": candidate.name,
                    "entrypoint": (Path("python") / candidate.name / "entrypoint.py").as_posix(),
                }
            )
    if not packages:
        raise CompactBundleError(
            "No Python entrypoint packages found in bundle. Ensure python/<package>/entrypoint.py exists."
        )
    return packages


def create_pystsmod_archive(
    source_dir: Path,
    target_file: Path,
    metadata: CompactBundleMetadata,
) -> Path:
    """Serialise ``source_dir`` into ``target_file`` with metadata."""

    target_file.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in sorted(source_dir.rglob("*")):
            if not entry.is_file():
                continue
            relative = entry.relative_to(source_dir).as_posix()
            archive.write(entry, arcname=relative)
        archive.writestr("bundle.json", json.dumps(metadata.as_dict(), indent=2) + "\n")
    return target_file


def _build_dummy_mod_loader(
    project: "ModProject",
    metadata: CompactBundleMetadata,
    mod_directory: Path,
    bundle_path: Path,
) -> Path:
    manifest_path = mod_directory / "ModTheSpire.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    manifest["stsmod_packaging"] = "compact"
    manifest["stsmod_bundle"] = bundle_path.name
    manifest.setdefault("modid", project.mod_id)
    manifest.setdefault("name", project.name)
    manifest.setdefault("author_list", [project.author])
    manifest.setdefault("version", metadata.version)
    manifest.setdefault("dependencies", list(metadata.dependencies))

    manifest_text = json.dumps(manifest, indent=2) + "\n"
    loader_payload = {
        "bundle": bundle_path.name,
        "packaging": "compact",
        "python_packages": metadata.as_dict()["python_packages"],
        "created_at": metadata.created_at,
    }
    loader_text = json.dumps(loader_payload, indent=2) + "\n"

    instructions = textwrap.dedent(
        f"""
        {metadata.name} compact loader
        =============================

        This jar is a lightweight loader that points ModTheSpire to the matching
        {bundle_path.name} archive.  Runtime launchers should read
        compact/loader.json, stream the referenced bundle entirely into memory and
        activate the Python entrypoint declared there.
        """
    ).strip() + "\n"

    dummy_name = f"{project.mod_id}_compact_loader.jar"
    target_path = bundle_path.with_name(dummy_name)
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as jar:
        jar.writestr(
            "META-INF/MANIFEST.MF",
            "Manifest-Version: 1.0\nCreated-By: stsmoddergui compact bundler\n" + "\n",
        )
        jar.writestr("ModTheSpire.json", manifest_text)
        jar.writestr("compact/loader.json", loader_text)
        jar.writestr("compact/README.txt", instructions)
    return target_path


def build_compact_bundle(
    *,
    project: "ModProject",
    options: "BundleOptions",
    mod_directory: Path,
) -> CompactBundleArtifacts:
    """Create the ``.pystsmod`` archive and dummy loader jar for ``project``."""

    metadata = CompactBundleMetadata.build(project, options, mod_directory)
    archive_name = f"{project.mod_id}-{options.version}.pystsmod"
    bundle_path = options.output_directory / archive_name
    bundle_path = create_pystsmod_archive(mod_directory, bundle_path, metadata)
    dummy_mod_path = _build_dummy_mod_loader(project, metadata, mod_directory, bundle_path)
    artefacts = CompactBundleArtifacts(
        mod_directory=mod_directory,
        bundle_path=bundle_path,
        dummy_mod_path=dummy_mod_path,
        metadata=metadata.as_dict(),
    )
    PLUGIN_MANAGER.expose("compact_bundle_artifacts", artefacts.as_dict())
    return artefacts


class CompactBundleLoader:
    """Load ``.pystsmod`` archives entirely in-memory for inspection."""

    def __init__(self, archive_path: Path) -> None:
        self.archive_path = Path(archive_path).resolve()
        self._payload = self.archive_path.read_bytes()
        self._buffer = io.BytesIO(self._payload)
        self._zip = zipfile.ZipFile(self._buffer, mode="r")
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        try:
            raw = self._zip.read("bundle.json")
            metadata = json.loads(raw.decode("utf8"))
        except KeyError:
            raw = self._zip.read("ModTheSpire.json")
            metadata = json.loads(raw.decode("utf8"))
            metadata.setdefault("packaging", "compact")
        metadata.setdefault("archive", self.archive_path.name)
        return metadata

    def close(self) -> None:
        self._zip.close()
        self._buffer.close()

    def __enter__(self) -> "CompactBundleLoader":  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
        self.close()

    @property
    def metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)

    def list_files(self) -> Tuple[str, ...]:
        return tuple(sorted(self._zip.namelist()))

    def contains(self, path: str) -> bool:
        return path in self._zip.namelist()

    def read_bytes(self, path: str) -> bytes:
        return self._zip.read(path)

    def read_text(self, path: str, encoding: str = "utf8") -> str:
        return self.read_bytes(path).decode(encoding)

    def open_binary(self, path: str) -> io.BytesIO:
        return io.BytesIO(self.read_bytes(path))

    def archive_bytes(self) -> bytes:
        """Return the raw bytes backing the archive."""

        return bytes(self._payload)


def load_compact_bundle(path: Path) -> CompactBundleLoader:
    """Convenience wrapper returning a :class:`CompactBundleLoader`."""

    return CompactBundleLoader(path)


PLUGIN_MANAGER.expose("CompactBundleLoader", CompactBundleLoader)
PLUGIN_MANAGER.expose("load_compact_bundle", load_compact_bundle)
PLUGIN_MANAGER.expose("create_pystsmod_archive", create_pystsmod_archive)
PLUGIN_MANAGER.expose("build_compact_bundle", build_compact_bundle)
PLUGIN_MANAGER.expose_module("modules.modbuilder.compact", alias="compact_bundles")

__all__ = [
    "CompactBundleError",
    "CompactBundleMetadata",
    "CompactBundleArtifacts",
    "create_pystsmod_archive",
    "build_compact_bundle",
    "CompactBundleLoader",
    "load_compact_bundle",
]

"""Tests for the GraalPy experimental backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.basemod_wrapper.experimental.graalpy_runtime import GraalPyBackend
from modules.basemod_wrapper.java_backend import active_backend, register_backend, use_backend
from modules.modbuilder.runtime_env import PythonRuntimeDescriptor


def _create_descriptor(tmp_path: Path) -> PythonRuntimeDescriptor:
    bundle_root = tmp_path / "Bundle"
    python_root = bundle_root / "python"
    package_root = python_root / "buddy"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("__all__ = []\n", encoding="utf8")
    entrypoint = package_root / "entrypoint.py"
    entrypoint.write_text("def main():\n    return None\n", encoding="utf8")
    return PythonRuntimeDescriptor(
        bundle_root=bundle_root,
        python_root=python_root,
        package_name="buddy",
        package_root=package_root,
        entrypoint=entrypoint,
        requirement_files=(),
        editable_targets=(),
    )


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_graalpy_backend_bootstrap_commands(tmp_path: Path, use_real_dependencies: bool) -> None:
    original_backend = active_backend().name
    register_backend(GraalPyBackend())
    try:
        try:
            use_backend("graalpy")
        except RuntimeError:
            # Running tests under CPython – the backend still becomes active even if ensure_bridge fails.
            pass
        descriptor = _create_descriptor(tmp_path)
        plan = descriptor.bootstrap_plan()
        assert any("--no-binary :all: Pillow" in command for command in plan.posix.install_dependencies)
        assert any(
            "--no-binary :all: Pillow" in command for command in plan.windows.install_dependencies
        )
    finally:
        use_backend(original_backend)

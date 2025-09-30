from pathlib import Path

import pytest

from modules.modbuilder.runtime_env import (
    PythonRuntimeError,
    bootstrap_python_runtime,
    discover_python_runtime,
    write_runtime_bootstrapper,
)


def _create_bundle(tmp_path: Path) -> Path:
    bundle_root = tmp_path / "BuddyMod"
    package_root = bundle_root / "python" / "buddy_mod"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("__all__ = []\n", encoding="utf8")
    entrypoint = package_root / "entrypoint.py"
    entrypoint.write_text(
        """
from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parent / "entrypoint.log"
    target.write_text(os.environ.get("PYTHONPATH", ""), encoding="utf8")


if __name__ == "__main__":
    main()
""".strip()
        + "\n",
        encoding="utf8",
    )
    (package_root / "setup.cfg").write_text(
        """
[metadata]
name = buddy-mod
version = 0.0.0

[options]
packages = find:
package_dir =
    =.

[options.packages.find]
where = .
""".strip()
        + "\n",
        encoding="utf8",
    )
    (package_root / "pyproject.toml").write_text(
        """
[build-system]
requires = ["setuptools>=61", "wheel"]
build-backend = "setuptools.build_meta"
""".strip()
        + "\n",
        encoding="utf8",
    )
    return bundle_root


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_discover_python_runtime_generates_plan(tmp_path: Path, use_real_dependencies: bool) -> None:
    bundle_root = _create_bundle(tmp_path)
    package_root = bundle_root / "python" / "buddy_mod"
    requirements = bundle_root / "python" / "requirements.txt"
    requirements.write_text("JPype1==1.5.0\n", encoding="utf8")

    descriptor = discover_python_runtime(bundle_root)
    assert descriptor.package_name == "buddy_mod"
    assert descriptor.entrypoint == package_root / "entrypoint.py"
    assert descriptor.requirement_files == (requirements,)

    plan = descriptor.bootstrap_plan()
    assert plan.descriptor is descriptor
    assert plan.venv_directory == bundle_root / ".venv"

    posix_commands = plan.posix.commands()
    windows_commands = plan.windows.commands()

    assert any("requirements.txt" in command for command in posix_commands)
    assert any("buddy_mod.entrypoint" in command for command in windows_commands)

    environment = plan.environment_variables()
    assert environment["PYTHONPATH"].endswith("python")

    serialised = plan.as_dict()
    assert serialised["package"] == "buddy_mod"
    assert serialised["entrypoint"].endswith("entrypoint.py")


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_discover_python_runtime_requires_entrypoint(tmp_path: Path, use_real_dependencies: bool) -> None:
    bundle_root = tmp_path / "BuddyMod"
    package_root = bundle_root / "python" / "buddy_mod"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("__all__ = []\n", encoding="utf8")

    with pytest.raises(PythonRuntimeError):
        discover_python_runtime(bundle_root)


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_bootstrap_plan_falls_back_to_jpype(tmp_path: Path, use_real_dependencies: bool) -> None:
    bundle_root = tmp_path / "BuddyMod"
    package_root = bundle_root / "python" / "buddy_mod"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("__all__ = []\n", encoding="utf8")
    (package_root / "entrypoint.py").write_text("def initialize():\n    pass\n", encoding="utf8")

    descriptor = discover_python_runtime(bundle_root)
    plan = descriptor.bootstrap_plan()

    assert any("JPype1" in command for command in plan.posix.install_dependencies)
    assert any("JPype1" in command for command in plan.windows.install_dependencies)


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_bootstrap_python_runtime_executes_entrypoint(tmp_path: Path, use_real_dependencies: bool) -> None:
    bundle_root = _create_bundle(tmp_path)
    package_root = bundle_root / "python" / "buddy_mod"

    if use_real_dependencies:
        bootstrap_python_runtime(bundle_root, logger=lambda *_: None)

    descriptor = bootstrap_python_runtime(bundle_root, logger=lambda *_: None)
    assert descriptor.package_name == "buddy_mod"

    venv_marker = bundle_root / ".venv" / "pyvenv.cfg"
    assert venv_marker.exists()

    log_file = package_root / "entrypoint.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf8")
    assert str(bundle_root / "python") in content


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_write_runtime_bootstrapper_creates_script(tmp_path: Path, use_real_dependencies: bool) -> None:
    target = write_runtime_bootstrapper(tmp_path)
    assert target.exists()
    content = target.read_text(encoding="utf8")
    assert "bootstrap_python_runtime" in content


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_runtime_env_cli_plan_outputs_json(tmp_path: Path, use_real_dependencies: bool, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    from modules.modbuilder import runtime_env as runtime_env_module

    bundle_root = _create_bundle(tmp_path)
    exit_code = runtime_env_module._cli(["plan", str(bundle_root), "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["package"] == "buddy_mod"

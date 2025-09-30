from pathlib import Path

import pytest

from modules.modbuilder.runtime_env import (
    PythonRuntimeError,
    discover_python_runtime,
)


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_discover_python_runtime_generates_plan(tmp_path: Path, use_real_dependencies: bool) -> None:
    bundle_root = tmp_path / "BuddyMod"
    package_root = bundle_root / "python" / "buddy_mod"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("__all__ = []\n", encoding="utf8")
    (package_root / "entrypoint.py").write_text("def initialize():\n    pass\n", encoding="utf8")
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

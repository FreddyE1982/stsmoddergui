"""One-click bootstrapper for bundled Slay the Spire mods."""
from __future__ import annotations

from pathlib import Path

from modules.modbuilder.runtime_env import bootstrap_python_runtime


def main() -> None:
    bundle_root = Path.cwd()
    descriptor = bootstrap_python_runtime(bundle_root)
    print(
        "Python runtime initialised for '",
        descriptor.package_name,
        "' at ",
        bundle_root / ".venv",
        sep="",
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.basemod_wrapper.loader import ensure_dependency_classpath


@pytest.fixture(scope="session")
def dependency_jars() -> Dict[str, Path]:
    """Ensure the core modding jars are available for the test session."""

    return ensure_dependency_classpath()


def _find_desktop_jar() -> Optional[Path]:
    """Best effort lookup for the game's desktop jar required for compilation."""

    candidates = []
    env_value = os.environ.get("STS_DESKTOP_JAR")
    if env_value:
        candidates.append(Path(env_value).expanduser())
    repo_candidate = Path(__file__).resolve().parents[1] / "modules" / "basemod_wrapper" / "lib" / "desktop-1.0.jar"
    candidates.append(repo_candidate)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


@pytest.fixture(scope="session")
def desktop_jar_path() -> Optional[Path]:
    """Return the path to ``desktop-1.0.jar`` if it can be located."""

    return _find_desktop_jar()

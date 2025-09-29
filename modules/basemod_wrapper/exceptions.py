"""Custom exception hierarchy for the BaseMod wrapper."""

from __future__ import annotations


class BaseModError(RuntimeError):
    """Base exception for BaseMod wrapper failures."""


class JVMNotStartedError(BaseModError):
    """Raised when a JPype operation is attempted without an active JVM."""


class ConfigurationError(BaseModError):
    """Raised when the wrapper is misconfigured."""

from __future__ import annotations

from modules.basemod_wrapper import experimental


def test_experimental_toggle_cycle(use_real_dependencies: bool) -> None:
    feature = experimental.load("sample_feature")
    feature.reset()

    try:
        activated = experimental.on("sample_feature")
        assert activated.is_enabled()
        assert experimental.is_active("sample_feature")
        assert "sample_feature" in experimental.available_modules()

        active_map = experimental.active_modules()
        assert "sample_feature" in active_map
        assert active_map["sample_feature"] is activated
        assert activated.history()[-1] == "on"
    finally:
        deactivated = experimental.off("sample_feature")
        assert not deactivated.is_enabled()
        assert not experimental.is_active("sample_feature")
        deactivated.reset()


def test_experimental_idempotent_deactivation(use_real_dependencies: bool) -> None:
    feature = experimental.load("sample_feature")
    feature.reset()

    # Deactivating an already disabled feature should not mutate state.
    snapshot = list(feature.history())
    untouched = experimental.off("sample_feature")
    assert untouched.history() == snapshot

    try:
        experimental.on("modules.basemod_wrapper.experimental.sample_feature")
        assert feature.is_enabled()
    finally:
        experimental.off("sample_feature")
        feature.reset()

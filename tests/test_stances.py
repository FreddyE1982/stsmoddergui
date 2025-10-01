import pytest

from modules.basemod_wrapper.stances import STANCE_REGISTRY, Stance
from modules.basemod_wrapper import stances as stances_module
from modules.basemod_wrapper.experimental import is_active as experimental_is_active
from modules.basemod_wrapper.java_backend import active_backend
from modules.basemod_wrapper.loader import BaseModBootstrapError


@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_graalpy_stance_registration(use_real_dependencies: bool, stubbed_runtime) -> None:
    if use_real_dependencies:
        with pytest.raises(BaseModBootstrapError):
            class FlowingGrace(Stance):
                mod_id = "unit_test_mod"
                identifier = "unit_test_mod:flowing_grace"
                description_text = "Testing stance integration."

        return

    class FlowingGrace(Stance):
        mod_id = "unit_test_mod"
        identifier = "unit_test_mod:flowing_grace"
        description_text = "Testing stance integration."
        primary_color = (0.2, 0.4, 0.8, 1.0)
        aura_color = (0.3, 0.5, 0.9, 1.0)

    try:
        assert experimental_is_active("graalpy_runtime"), "Stance registration should activate the GraalPy runtime."
        record = STANCE_REGISTRY.record("unit_test_mod:flowing_grace")
        assert record is not None
        basemod_stub = stances_module._basemod()
        stance_entries = getattr(basemod_stub.BaseMod, "custom_stances", [])
        assert any(entry[0] == record.identifier for entry in stance_entries)
        stance_base = stances_module._abstract_stance_base()
        runtime_map = getattr(stance_base, "stances", {})
        assert record.identifier in runtime_map
    finally:
        STANCE_REGISTRY.unregister("unit_test_mod:flowing_grace")
        stances_module._abstract_stance_base.cache_clear()
        stances_module._java_module.cache_clear()
        stances_module._stance_helper.cache_clear()
        stances_module._stance_aura_effect.cache_clear()
        stances_module._stance_particle_effect.cache_clear()

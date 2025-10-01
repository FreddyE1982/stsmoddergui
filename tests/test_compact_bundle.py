import json
import zipfile

import pytest

from modules.basemod_wrapper import BundlePackaging, create_project
from modules.modbuilder.compact import CompactBundleLoader


@pytest.mark.requires_desktop_jar
@pytest.mark.parametrize("use_real_dependencies", [False, True])
def test_compile_and_bundle_compact_mode(tmp_path, desktop_jar_path, use_real_dependencies):
    if desktop_jar_path is None:
        pytest.skip("desktop-1.0.jar is required to compile enum patches")

    mod_id = "compactbuddy"
    project = create_project(mod_id, "Compact Buddy", "OldFriend", "Compact bundle mode")
    layout = project.scaffold(tmp_path, package_name="compact_mod")

    texture_names = [
        "attack.png",
        "skill.png",
        "power.png",
        "orb.png",
        "attack_small.png",
        "skill_small.png",
        "power_small.png",
        "orb_small.png",
    ]
    for name in texture_names:
        (layout.images_root / name).write_text("texture", encoding="utf8")

    project.define_color(
        "COMPACT_BLUE",
        card_color=(0.2, 0.2, 0.9, 1.0),
        trail_color=(0.1, 0.1, 0.6, 1.0),
        slash_color=(0.6, 0.5, 0.9, 1.0),
        attack_bg=project.resource_path("images/attack.png"),
        skill_bg=project.resource_path("images/skill.png"),
        power_bg=project.resource_path("images/power.png"),
        orb=project.resource_path("images/orb.png"),
        attack_bg_small=project.resource_path("images/attack_small.png"),
        skill_bg_small=project.resource_path("images/skill_small.png"),
        power_bg_small=project.resource_path("images/power_small.png"),
        orb_small=project.resource_path("images/orb_small.png"),
    )

    layout.project_module.write_text("VALUE = 321\n", encoding="utf8")

    options = project.bundle_options_from_layout(
        layout,
        output_directory=tmp_path / "dist",
        version="2.0.0",
        additional_classpath=[desktop_jar_path],
        packaging=BundlePackaging.COMPACT,
    )

    mod_root = project.compile_and_bundle(options)
    assert mod_root.exists()

    bundle_result = project.last_bundle_result()
    assert bundle_result is not None
    assert bundle_result.is_compact()
    compact = bundle_result.compact
    assert compact is not None
    assert compact.bundle_path.exists()
    assert compact.dummy_mod_path.exists()

    with CompactBundleLoader(compact.bundle_path) as loader:
        files = loader.list_files()
        assert "bundle.json" in files
        assert f"resources/{mod_id}/images/attack.png" in files
        manifest = json.loads(loader.read_text("ModTheSpire.json"))
        assert manifest["modid"] == mod_id
        metadata = loader.metadata
        assert metadata["packaging"] == "compact"
        assert metadata["mod_id"] == mod_id
        assert metadata["python_packages"]
        assert metadata["archive"] == compact.bundle_path.name

    with zipfile.ZipFile(compact.dummy_mod_path) as jar:
        jar_manifest = json.loads(jar.read("ModTheSpire.json").decode("utf8"))
        assert jar_manifest["stsmod_bundle"] == compact.bundle_path.name
        loader_info = json.loads(jar.read("compact/loader.json").decode("utf8"))
        assert loader_info["bundle"] == compact.bundle_path.name
        assert loader_info["python_packages"]
        assert loader_info["python_packages"][0]["entrypoint"].startswith("python/")
        assert "compact/README.txt" in jar.namelist()

    contents = {item.name for item in compact.bundle_path.parent.iterdir()}
    assert compact.bundle_path.name in contents
    assert compact.dummy_mod_path.name in contents

    if use_real_dependencies:
        second_root = project.compile_and_bundle(options)
        assert second_root == mod_root
        second_result = project.last_bundle_result()
        assert second_result is not None
        assert second_result.compact is not None
        assert second_result.compact.bundle_path.exists()

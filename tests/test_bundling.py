from __future__ import annotations

import json
import zipfile

import pytest

from modules.basemod_wrapper import BaseModEnvironment, create_project, spire
from modules.basemod_wrapper.project import BundleOptions


@pytest.mark.requires_desktop_jar
def test_compile_and_bundle_with_stslib(tmp_path, dependency_jars, desktop_jar_path):
    if desktop_jar_path is None:
        pytest.skip("desktop-1.0.jar is required to compile enum patches")

    mod_id = "buddy"
    project = create_project(mod_id, "Buddy Mod", "OldFriend", "Test bundle with StSLib")
    assets_dir = tmp_path / "assets" / "images"
    assets_dir.mkdir(parents=True)
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
        (assets_dir / name).write_text("texture", encoding="utf8")

    project.define_color(
        "BUDDY_BLUE",
        card_color=(0.1, 0.2, 0.9, 1.0),
        trail_color=(0.2, 0.3, 0.8, 1.0),
        slash_color=(0.3, 0.5, 1.0, 1.0),
        attack_bg=f"resources/{mod_id}/images/attack.png",
        skill_bg=f"resources/{mod_id}/images/skill.png",
        power_bg=f"resources/{mod_id}/images/power.png",
        orb=f"resources/{mod_id}/images/orb.png",
        attack_bg_small=f"resources/{mod_id}/images/attack_small.png",
        skill_bg_small=f"resources/{mod_id}/images/skill_small.png",
        power_bg_small=f"resources/{mod_id}/images/power_small.png",
        orb_small=f"resources/{mod_id}/images/orb_small.png",
    )

    python_src = tmp_path / "python_src"
    python_src.mkdir()
    (python_src / "__init__.py").write_text("MOD_NAME = 'Buddy Mod'\n", encoding="utf8")

    classpath = [
        dependency_jars["basemod"],
        dependency_jars["stslib"],
        dependency_jars["modthespire"],
        desktop_jar_path,
    ]
    options = BundleOptions(
        java_classpath=classpath,
        python_source=python_src,
        assets_source=assets_dir.parent,
        output_directory=tmp_path / "dist",
        version="1.2.3",
    )

    output_root = project.compile_and_bundle(options)

    manifest = json.loads((output_root / "ModTheSpire.json").read_text(encoding="utf8"))
    assert manifest["modid"] == mod_id
    assert manifest["dependencies"] == ["basemod", "stslib"]
    assert manifest["version"] == "1.2.3"

    resources_root = output_root / "resources" / mod_id / "images"
    for name in texture_names:
        assert (resources_root / name).exists()

    python_copy = output_root / "python" / python_src.name / "__init__.py"
    assert python_copy.read_text(encoding="utf8") == "MOD_NAME = 'Buddy Mod'\n"

    patch_java = output_root / "patches" / "BuddyEnums.java"
    assert patch_java.exists()
    patch_jar = output_root / f"{mod_id}_patches.jar"
    with zipfile.ZipFile(patch_jar) as archive:
        assert "buddy/patches/BuddyEnums.class" in archive.namelist()


@pytest.mark.requires_desktop_jar
def test_compile_and_bundle_without_stslib(tmp_path, dependency_jars, desktop_jar_path):
    if desktop_jar_path is None:
        pytest.skip("desktop-1.0.jar is required to compile enum patches")

    mod_id = "nostslib"
    project = create_project(mod_id, "Vanilla Mod", "Buddy", "Bundle without StSLib")
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "placeholder.txt").write_text("asset", encoding="utf8")
    project.define_color(
        "VANILLA",
        card_color=(0.4, 0.4, 0.4, 1.0),
        trail_color=(0.5, 0.5, 0.5, 1.0),
        slash_color=(0.6, 0.6, 0.6, 1.0),
        attack_bg=f"resources/{mod_id}/attack.png",
        skill_bg=f"resources/{mod_id}/skill.png",
        power_bg=f"resources/{mod_id}/power.png",
        orb=f"resources/{mod_id}/orb.png",
        attack_bg_small=f"resources/{mod_id}/attack_s.png",
        skill_bg_small=f"resources/{mod_id}/skill_s.png",
        power_bg_small=f"resources/{mod_id}/power_s.png",
        orb_small=f"resources/{mod_id}/orb_s.png",
    )

    python_src = tmp_path / "py"
    python_src.mkdir()
    (python_src / "mod.py").write_text("VALUE = 7\n", encoding="utf8")

    classpath = [
        dependency_jars["basemod"],
        dependency_jars["modthespire"],
        desktop_jar_path,
    ]
    options = BundleOptions(
        java_classpath=classpath,
        python_source=python_src,
        assets_source=assets_dir,
        output_directory=tmp_path / "dist",
        dependencies=("basemod",),
    )

    output_root = project.compile_and_bundle(options)
    manifest = json.loads((output_root / "ModTheSpire.json").read_text(encoding="utf8"))
    assert manifest["dependencies"] == ["basemod"]
    assert (output_root / f"{mod_id}_patches.jar").exists()


def test_unified_spire_actions_and_keywords():
    action = spire.action("add_temporary_hp")
    assert "AddTemporaryHPAction" in action.__name__

    keywords = spire.keyword_fields()
    assert "retain" in keywords
    assert keywords["retain"].endswith("AlwaysRetainField.alwaysRetain")


def test_environment_bundle_options(tmp_path):
    env = BaseModEnvironment()
    python_src = tmp_path / "src"
    python_src.mkdir()
    assets_src = tmp_path / "assets"
    assets_src.mkdir()
    extra_cp = tmp_path / "extra.jar"
    extra_cp.write_text("jar", encoding="utf8")

    options = env.default_bundle_options(
        python_source=python_src,
        assets_source=assets_src,
        output_directory=tmp_path / "dist",
        dependencies=("basemod", "custom"),
        additional_classpath=[extra_cp],
    )

    assert options.dependencies == ("basemod", "custom")
    assert extra_cp in options.java_classpath

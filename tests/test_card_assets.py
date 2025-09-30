import hashlib
import json
from types import SimpleNamespace

from modules.basemod_wrapper.card_assets import (
    INNER_CARD_MANIFEST_NAME,
    ensure_pillow,
    load_inner_card_manifest,
    prepare_inner_card_image,
)
from modules.basemod_wrapper.cards import SimpleCardBlueprint
from modules.basemod_wrapper.project import ModProject


def test_prepare_inner_card_image_reuses_cached_assets(monkeypatch, tmp_path):
    Image = ensure_pillow()
    source = tmp_path / "source.png"
    Image.new("RGBA", (500, 380), (10, 20, 30, 255)).save(source)

    project = ModProject("combo", "Combo", "Buddy", "Testing")
    project._color_enum = "BUDDY_COLOR"
    assets_dir = tmp_path / "assets"
    project.layout = SimpleNamespace(cards_image_root=str(assets_dir))

    cached_dir = tmp_path / "cache"
    cached_dir.mkdir(parents=True)
    cached_small = cached_dir / "cached_small.png"
    cached_portrait = cached_dir / "cached_portrait.png"
    Image.new("RGBA", (250, 190), (255, 0, 0, 255)).save(cached_small)
    Image.new("RGBA", (330, 380), (0, 255, 0, 255)).save(cached_portrait)

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest_path = assets_dir / INNER_CARD_MANIFEST_NAME
    assets_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "hashes": {
            digest: {
                "source": str(source),
                "small": str(cached_small),
                "portrait": str(cached_portrait),
                "resource": "combo/images/cards/BuddyCombo.png",
            }
        },
        "cards": {},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf8")

    jar_path = tmp_path / "tool.jar"
    jar_path.write_text("jar")

    monkeypatch.setattr(
        "modules.basemod_wrapper.card_assets.ensure_card_image_tool_built", lambda: jar_path
    )

    def fail_run(*args, **kwargs):  # pragma: no cover - should never execute
        raise AssertionError("Image tool should not be invoked when cache is valid")

    monkeypatch.setattr("modules.basemod_wrapper.card_assets.subprocess.run", fail_run)

    blueprint = SimpleCardBlueprint(
        identifier="BuddyCombo",
        title="Buddy Combo",
        description="Deal {damage} damage.",
        cost=1,
        card_type="attack",
        target="enemy",
        rarity="common",
        value=7,
    ).innerCardImage(str(source))

    result = prepare_inner_card_image(project, blueprint)

    expected_small = assets_dir / "BuddyCombo.png"
    expected_portrait = assets_dir / "BuddyCombo_p.png"
    assert result.small_asset_path == expected_small
    assert result.portrait_asset_path == expected_portrait
    assert expected_small.read_bytes() == cached_small.read_bytes()
    assert expected_portrait.read_bytes() == cached_portrait.read_bytes()

    updated_manifest = load_inner_card_manifest(project)
    assert updated_manifest["cards"]["BuddyCombo"]["hash"] == digest
    assert updated_manifest["cards"]["BuddyCombo"]["resource"] == result.resource_path


def test_load_inner_card_manifest_creates_default_structure(tmp_path):
    project = ModProject("combo", "Combo", "Buddy", "Testing")
    project.layout = SimpleNamespace(cards_image_root=str(tmp_path / "assets"))

    manifest = load_inner_card_manifest(project)
    assert manifest == {"hashes": {}, "cards": {}}

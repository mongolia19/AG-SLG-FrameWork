from pathlib import Path
import pytest
from server.scenario_manager import ScenarioManager, SceneNode, NPC, ActionOption


def test_load_scenario():
    base_dir = Path(__file__).resolve().parent.parent / "scripts"
    mgr = ScenarioManager(base_dir=base_dir)

    scenarios = mgr.list_scenarios()
    assert "black_crow_manor" in scenarios

    spec = mgr.load_scenario("black_crow_manor")
    assert spec.world.id == "black_crow_manor"
    assert spec.world.initial_scene == "manor_entrance"
    assert "manor_entrance" in spec.scenes

    entrance = spec.scenes["manor_entrance"]
    assert len(entrance.npcs) >= 1
    assert entrance.npcs[0].id == "butler_grim"
    assert len(entrance.actions) >= 1


def test_save_and_get_scene(tmp_path):
    mgr = ScenarioManager(base_dir=tmp_path)
    # create world file
    from server.scenario_manager import WorldSpec, PlayerState
    world = WorldSpec(
        id="test_world",
        title="测试剧本",
        initial_scene="start",
        initial_player_state=PlayerState(name="勇者", current_scene="start"),
    )
    mgr.save_world("test_world", world)

    scene = SceneNode(
        id="secret_cave",
        title="隐秘山洞",
        description="潮湿阴暗的洞穴",
        actions=[ActionOption(id="light_torch", label="点燃火把", type="interact")],
    )
    saved_path = mgr.save_scene("test_world", scene)
    assert saved_path.exists()

    loaded_scene = mgr.get_scene("test_world", "secret_cave")
    assert loaded_scene is not None
    assert loaded_scene.title == "隐秘山洞"
    assert loaded_scene.actions[0].id == "light_torch"


def test_export_and_import_scenario_bundle(tmp_path):
    src_dir = tmp_path / "src_scripts"
    dst_dir = tmp_path / "dst_scripts"
    mgr_src = ScenarioManager(base_dir=src_dir)
    mgr_dst = ScenarioManager(base_dir=dst_dir)

    # 1. Create a complete scenario with world, scene, and co-located assets
    from server.scenario_manager import WorldSpec, PlayerState
    world = WorldSpec(
        id="island_demo",
        title="测试海岛",
        initial_scene="shore",
        initial_player_state=PlayerState(name="幸存者", current_scene="shore"),
    )
    mgr_src.save_world("island_demo", world)
    scene = SceneNode(
        id="shore",
        title="海岸线",
        description="风暴平息后的荒岛海岸",
        background="/assets/scenes/island_beach.png",
    )
    mgr_src.save_scene("island_demo", scene)

    # Put a co-located asset
    assets_dir = mgr_src.get_scenario_assets_dir("island_demo")
    dummy_img = assets_dir / "scenes" / "island_beach.png"
    dummy_img.parent.mkdir(parents=True, exist_ok=True)
    dummy_img.write_text("fake_png_data")

    # 2. Export scenario bundle to zip
    zip_path = tmp_path / "island_demo.zip"
    exported_zip = mgr_src.export_scenario_bundle("island_demo", target_zip=zip_path)
    assert exported_zip.exists()

    # 3. Import bundle into dst_dir
    imported_id = mgr_dst.import_scenario_bundle(exported_zip)
    assert imported_id == "island_demo"

    # Verify scenario loaded in destination
    imported_spec = mgr_dst.load_scenario("island_demo")
    assert imported_spec.world.title == "测试海岛"
    assert "shore" in imported_spec.scenes
    assert imported_spec.scenes["shore"].description == "风暴平息后的荒岛海岸"

    # Verify co-located asset was extracted
    imported_asset = dst_dir / "island_demo" / "assets" / "scenes" / "island_beach.png"
    assert imported_asset.exists()
    assert imported_asset.read_text() == "fake_png_data"

    # Test asset locator
    found = mgr_dst.find_asset_path("scenes/island_beach.png", scenario_id="island_demo")
    assert found is not None
    assert found.exists()


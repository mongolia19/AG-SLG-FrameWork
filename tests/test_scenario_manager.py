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

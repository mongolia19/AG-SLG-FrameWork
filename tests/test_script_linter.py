import pytest
from server.scenario_manager import ScenarioSpec, WorldSpec, PlayerState, SceneNode, ActionOption, NPC
from server.script_linter import ScriptLinter


def test_script_linter_valid_scenario():
    world = WorldSpec(
        id="test_scen",
        title="测试剧本",
        initial_scene="scene_1",
        initial_player_state=PlayerState(),
    )
    scenes = {
        "scene_1": SceneNode(
            id="scene_1",
            title="场景一",
            description="起点大厅",
            actions=[
                ActionOption(id="go_2", label="前往场景二", type="transition", target_scene="scene_2")
            ],
        ),
        "scene_2": SceneNode(
            id="scene_2",
            title="场景二",
            description="终点房间",
            actions=[
                ActionOption(id="go_1", label="返回场景一", type="transition", target_scene="scene_1")
            ],
        ),
    }
    spec = ScenarioSpec(world=world, scenes=scenes)
    report = ScriptLinter.lint_scenario(spec)
    assert report.valid is True
    assert report.errors == 0


def test_script_linter_detect_errors():
    world = WorldSpec(
        id="broken_scen",
        title="异常剧本",
        initial_scene="missing_initial_scene",
        initial_player_state=PlayerState(),
    )
    scenes = {
        "scene_1": SceneNode(
            id="scene_1",
            title="悬空跳转场景",
            description="",  # 触发 warning: 缺少描述
            actions=[
                # 触发 error: 目标场景不存在
                ActionOption(id="go_nowhere", label="迷失", type="transition", target_scene="ghost_room"),
                # 触发 warning: NPC 不在场景内
                ActionOption(id="talk_ghost", label="对话", type="interact", target_npc="ghost_npc"),
            ],
        )
    }
    spec = ScenarioSpec(world=world, scenes=scenes)
    report = ScriptLinter.lint_scenario(spec)
    assert report.valid is False
    assert report.errors >= 2  # initial_scene missing + target_scene ghost_room
    assert report.warnings >= 2  # empty description + target_npc not present

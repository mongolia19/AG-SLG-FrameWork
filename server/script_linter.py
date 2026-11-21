"""Scenario linter and semantic consistency checker for AG-SLG-FrameWork."""

from typing import Any, Dict, List
from pydantic import BaseModel
from server.scenario_manager import ScenarioSpec


class LintIssue(BaseModel):
    level: str  # "error", "warning", "info"
    scene_id: str
    message: str
    field: str = ""


class LintReport(BaseModel):
    scenario_id: str
    valid: bool
    total_issues: int
    errors: int
    warnings: int
    issues: List[LintIssue]


class ScriptLinter:
    """Performs static checks and consistency checks on scenario YAML definitions."""

    @staticmethod
    def lint_scenario(spec: ScenarioSpec) -> LintReport:
        issues: List[LintIssue] = []
        world = spec.world
        scenes = spec.scenes

        # 1. 检查 initial_scene 是否存在
        if world.initial_scene not in scenes:
            issues.append(
                LintIssue(
                    level="error",
                    scene_id="world.yaml",
                    field="initial_scene",
                    message=f"初始场景 '{world.initial_scene}' 未在 scenes 目录下定义！",
                )
            )

        # 2. 检查所有场景的跳转目标与 NPC 引用
        defined_scenes = set(scenes.keys())
        all_npc_ids = set()

        for s_id, scene in scenes.items():
            for npc in scene.npcs:
                all_npc_ids.add(npc.id)

        for s_id, scene in scenes.items():
            # 检查场景是否为空白描述
            if not scene.description or not scene.description.strip():
                issues.append(
                    LintIssue(
                        level="warning",
                        scene_id=s_id,
                        field="description",
                        message=f"场景 '{scene.title}' 缺少详细环境描述",
                    )
                )

            # 检查是否有出口动作
            if not scene.actions:
                issues.append(
                    LintIssue(
                        level="warning",
                        scene_id=s_id,
                        field="actions",
                        message=f"场景 '{scene.title}' 没有配置任何动作（可能是死路）",
                    )
                )

            for act in scene.actions:
                # 检查 target_scene 悬空跳转
                if act.type == "transition" and act.target_scene:
                    if act.target_scene not in defined_scenes:
                        issues.append(
                            LintIssue(
                                level="error",
                                scene_id=s_id,
                                field=f"action.{act.id}.target_scene",
                                message=f"动作 '{act.label}' 指向不存在的场景: '{act.target_scene}'",
                            )
                        )
                # 检查 check 动作里的 transition_scene 悬空
                if act.type == "check" and act.on_success:
                    succ_trans = act.on_success.get("transition_scene")
                    if succ_trans and succ_trans not in defined_scenes:
                        issues.append(
                            LintIssue(
                                level="error",
                                scene_id=s_id,
                                field=f"action.{act.id}.on_success.transition_scene",
                                message=f"检定成功跳转指向未定义场景: '{succ_trans}'",
                            )
                        )

                # 检查 target_npc 是否存在
                if act.type == "interact" and act.target_npc:
                    current_scene_npcs = {npc.id for npc in scene.npcs}
                    if act.target_npc not in current_scene_npcs:
                        issues.append(
                            LintIssue(
                                level="warning",
                                scene_id=s_id,
                                field=f"action.{act.id}.target_npc",
                                message=f"动作目标 NPC '{act.target_npc}' 未在当前场景的 npcs 列表中出现",
                            )
                        )

        errors_count = sum(1 for i in issues if i.level == "error")
        warnings_count = sum(1 for i in issues if i.level == "warning")

        return LintReport(
            scenario_id=world.id,
            valid=errors_count == 0,
            total_issues=len(issues),
            errors=errors_count,
            warnings=warnings_count,
            issues=issues,
        )

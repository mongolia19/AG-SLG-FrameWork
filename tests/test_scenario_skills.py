"""Tests for scenario-level Agent Skill packages (SKILL.md, scripts/, references/, ZIP export)."""

import json
import subprocess
import sys
import zipfile

import pytest
from ag_ui.core import RunAgentInput, TextInputContent, UserMessage

from server.agent_driver import AgentEvent, BaseAgentDriver
from server.agui_bridge import AGUIBridge
from server.scenario_manager import ScenarioManager


class _PromptCaptureDriver(BaseAgentDriver):
    def __init__(self):
        self.prompts = []

    async def run_stream(self, prompt, conversation_id=None, cwd=None):
        self.prompts.append(prompt)
        yield AgentEvent(event_type="text_delta", data={"text": "ok"})
        yield AgentEvent(event_type="done", data={"status": "SUCCESS"})


def test_skill_bundle_discovery_and_zip_roundtrip(tmp_path):
    base = tmp_path / "scripts"
    sc_dir = base / "alchemy_quest"
    (sc_dir / "scenes").mkdir(parents=True)
    (sc_dir / "scripts" / "__pycache__").mkdir(parents=True)
    (sc_dir / "references").mkdir(parents=True)
    (sc_dir / "assets" / "items").mkdir(parents=True)

    (sc_dir / "world.yaml").write_text(
        'id: "alchemy_quest"\ntitle: "炼金物语"\ninitial_scene: "lab"\ninitial_player_state:\n  hp: 100\n',
        encoding="utf-8",
    )
    (sc_dir / "scenes" / "lab.yaml").write_text(
        'id: "lab"\ntitle: "工坊"\ndescription: "药瓶林立。"\nactions: []\n',
        encoding="utf-8",
    )
    (sc_dir / "SKILL.md").write_text(
        "# 炼金推演指南\n配药时请运行 scripts/brew.py 计算成败与副产物。",
        encoding="utf-8",
    )
    (sc_dir / "scripts" / "brew.py").write_text(
        '#!/usr/bin/env python3\n"""Compute potion brew yield and side effects."""\nprint("{}")\n',
        encoding="utf-8",
    )
    (sc_dir / "scripts" / "__pycache__" / "brew.cpython-314.pyc").write_bytes(b"pyc")
    (sc_dir / "scripts" / ".hidden.py").write_text("# skip me\n", encoding="utf-8")
    (sc_dir / "references" / "recipes.md").write_text("# 配方表\n", encoding="utf-8")
    (sc_dir / "assets" / "items" / "vial.png").write_bytes(b"png")

    mgr = ScenarioManager(base_dir=base)
    bundle = mgr.get_skill_bundle("alchemy_quest")
    assert "炼金推演指南" in bundle["skill_md"]
    assert bundle["scripts"] == [
        {
            "name": "brew.py",
            "path": "scripts/alchemy_quest/scripts/brew.py",
            "summary": "Compute potion brew yield and side effects.",
        }
    ]
    assert bundle["references"] == [
        {"name": "recipes.md", "path": "scripts/alchemy_quest/references/recipes.md"}
    ]
    assert bundle["assets_dirs"] == ["items"]

    # Export omits __pycache__/pyc/hidden files, and re-import preserves SKILL.md + scripts + references + assets
    zip_path = mgr.export_scenario_bundle("alchemy_quest", target_zip=tmp_path / "alchemy.zip")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        assert "SKILL.md" in names
        assert "scripts/brew.py" in names
        assert "references/recipes.md" in names
        assert "assets/items/vial.png" in names
        assert not any("__pycache__" in n or n.endswith(".pyc") or "/." in n for n in names)

    reimport_mgr = ScenarioManager(base_dir=tmp_path / "reimported")
    new_id = reimport_mgr.import_scenario_bundle(zip_path, scenario_id="alchemy_copy")
    assert new_id == "alchemy_copy"
    reloaded_bundle = reimport_mgr.get_skill_bundle("alchemy_copy")
    assert reloaded_bundle["scripts"][0]["path"] == "scripts/alchemy_copy/scripts/brew.py"
    assert reloaded_bundle["references"][0]["path"] == "scripts/alchemy_copy/references/recipes.md"


@pytest.mark.asyncio
async def test_play_and_studio_prompts_inject_scenario_skill_and_scripts():
    mgr = ScenarioManager()
    driver = _PromptCaptureDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    # wow_elwynn_rpg includes SKILL.md + scripts/combat_calc.py
    play_session = bridge.get_or_create_session("wow-skill-prompt", "wow_elwynn_rpg")
    play_prompt = bridge.build_play_prompt(play_session, "对蜘蛛领主施放神圣风暴")
    assert "scripts/wow_elwynn_rpg/scripts/combat_calc.py" in play_prompt
    assert "combat_calc.py" in play_prompt
    assert "艾泽拉斯 RPG DM 推演 Skill" in play_prompt

    # black_crow_manor has no SKILL.md or scripts/, so the skill block should stay absent
    manor_session = bridge.get_or_create_session("manor-plain-prompt", "black_crow_manor")
    manor_prompt = bridge.build_play_prompt(manor_session, "推开大门")
    assert "剧本专属 Skill 与程序脚本" not in manor_prompt

    # Studio prompt includes scenario skill guidance + discovered assets/scripts
    inp = RunAgentInput(
        thread_id="studio-skill-test",
        run_id="r1",
        messages=[UserMessage(id="m1", role="user", content=[TextInputContent(text="查看可用脚本")])],
        forwarded_props={"scenario_id": "wow_elwynn_rpg"},
    )
    async for _ in bridge.stream_studio(inp):
        pass
    assert len(driver.prompts) == 1
    studio_prompt = driver.prompts[0]
    assert "scripts/wow_elwynn_rpg/scripts/combat_calc.py" in studio_prompt
    assert "SKILL.md" in studio_prompt
    assert "assets/characters/" in studio_prompt
    assert "skills/ag-slg-director/SKILL.md" in studio_prompt
    assert "skills/ag-slg-director/references/agui-contract-and-examples.md" in studio_prompt
    assert mgr.base_dir.parent.joinpath("skills/ag-slg-director/references/agui-contract-and-examples.md").is_file()


def test_wow_combat_calc_script_execution():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/wow_elwynn_rpg/scripts/combat_calc.py",
            "--json",
            json.dumps(
                {
                    "mode": "skill",
                    "base_power": 28,
                    "attr_value": 16,
                    "level": 3,
                    "roll": 15,
                    "dc": 12,
                    "armor_hardened": False,
                    "mark_active": True,
                }
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(proc.stdout)
    # total = 15 + floor((16-10)/2) + 2(mark) = 20 (>= 12+5 -> critical_success, x1.35)
    assert out["outcome"] == "critical_success"
    # ceil((28 + 40 + 30) * 1.15 * 1.35) = ceil(152.145) = 153
    assert out["damage"] == 153

    boss_proc = subprocess.run(
        [
            sys.executable,
            "scripts/wow_elwynn_rpg/scripts/combat_calc.py",
            "--json",
            json.dumps({"mode": "boss", "boss_hp": 220, "boss_mp": 110, "boss_phase": 1}),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    boss_out = json.loads(boss_proc.stdout)
    assert boss_out["boss_phase"] == 2
    assert boss_out["spawned_minions"] == 2
    assert boss_out["boss_mp"] == 75

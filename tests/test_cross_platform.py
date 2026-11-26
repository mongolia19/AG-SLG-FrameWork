"""Cross-platform compatibility tests (Windows vs POSIX paths, .cmd wrapping, zip bundles)."""

import io
import os
import zipfile

import run_services
from server.agent_driver import _prepare_command
from server.scenario_manager import ScenarioManager


def test_prepare_command_wraps_windows_batch_shims(monkeypatch):
    # POSIX keeps commands untouched
    monkeypatch.setattr("server.agent_driver.os.name", "posix")
    assert _prepare_command(["npx", "--yes", "pkg"]) == ["npx", "--yes", "pkg"]

    # Windows wraps .cmd / .bat with cmd.exe /d /c and leaves .exe direct
    monkeypatch.setattr("server.agent_driver.os.name", "nt")
    monkeypatch.setenv("COMSPEC", r"C:\Windows\System32\cmd.exe")
    monkeypatch.setattr(
        "server.agent_driver.shutil.which",
        lambda name: r"C:\nodejs\npx.cmd" if name == "npx" else r"C:\bin\agy.exe",
    )
    assert _prepare_command(["npx", "--yes", "@agentclientprotocol/codex-acp"]) == [
        r"C:\Windows\System32\cmd.exe",
        "/d",
        "/c",
        r"C:\nodejs\npx.cmd",
        "--yes",
        "@agentclientprotocol/codex-acp",
    ]
    assert _prepare_command(["agy", "acp"]) == [r"C:\bin\agy.exe", "acp"]


def test_run_services_windows_resolution_and_netstat_parser(tmp_path, monkeypatch):
    monkeypatch.setattr(run_services, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(run_services, "WEB_DIR", tmp_path / "web")
    win_py = tmp_path / ".venv" / "Scripts" / "python.exe"
    win_py.parent.mkdir(parents=True)
    win_py.write_text("", encoding="utf-8")

    vite_cmd = tmp_path / "web" / "node_modules" / ".bin" / "vite.cmd"
    vite_cmd.parent.mkdir(parents=True)
    vite_cmd.write_text("", encoding="utf-8")

    monkeypatch.setattr("run_services.os.name", "nt")
    assert run_services.resolve_python() == str(win_py)
    assert run_services.resolve_vite_cmd() == [str(vite_cmd)]

    netstat_sample = (
        "  TCP    127.0.0.1:8001         0.0.0.0:0              LISTENING       12345\n"
        "  TCP    0.0.0.0:80010          0.0.0.0:0              LISTENING       99999\n"
        "  TCP    127.0.0.1:8001         127.0.0.1:51234        ESTABLISHED     54321\n"
        "  TCP    [::1]:8001             [::]:0                 LISTENING       6789\n"
    )
    assert run_services._parse_windows_netstat_pids(netstat_sample, 8001) == [12345, 6789]


def test_scenario_zip_export_and_windows_backslash_import(tmp_path):
    mgr = ScenarioManager()
    zip_out = tmp_path / "exported.zip"
    mgr.export_scenario_bundle("black_crow_manor", target_zip=zip_out)
    with zipfile.ZipFile(zip_out, "r") as zf:
        assert all("\\" not in name for name in zf.namelist())
        assert "world.yaml" in zf.namelist()

    # Simulate an archive packed with Windows backslashes
    win_zip = tmp_path / "win_bundle.zip"
    with zipfile.ZipFile(win_zip, "w") as zf:
        zf.writestr(
            r"win_story\world.yaml",
            'id: "win_story"\ntitle: "Win"\ninitial_scene: "s1"\ninitial_player_state:\n  hp: 100\n',
        )
        zf.writestr(r"win_story\scenes\s1.yaml", 'id: "s1"\ntitle: "Start"\ndescription: "hi"\nactions: []\n')

    imported_mgr = ScenarioManager(base_dir=tmp_path / "scripts")
    sid = imported_mgr.import_scenario_bundle(win_zip)
    assert sid == "win_story"
    spec = imported_mgr.load_scenario("win_story")
    assert spec.world.title == "Win"
    assert "s1" in spec.scenes

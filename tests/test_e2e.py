"""E2E 场景测试：一次完整开发会话的全流程（CLI init → 任务推进 → hook 注入/拦截）。"""

from __future__ import annotations

import io
import json

from keystone.cli import main as keystone_main
from keystone.hook import cli as hook_cli
from keystone.store import sessions, tasks
from keystone.store.layout import KeystoneLayout
from keystone.store.project import load_project, save_project


def _hook(project_dir, event, payload: dict, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    code = hook_cli.main([event])
    out = capsys.readouterr().out.strip()
    return code, (json.loads(out) if out else None)


def test_full_session_scenario(tmp_path, monkeypatch, capsys):
    # 1. keystone init（Java/Maven 预设）
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert keystone_main(["init", "--dir", str(tmp_path), "-y"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)  # 后续 task CLI 从项目内运行
    project = load_project(KeystoneLayout(tmp_path))
    assert project["test_command"] == "mvn test"

    # 2. 会话开始：注入项目上下文（含禁止事项）
    code, out = _hook(tmp_path, "session-start",
                      {"cwd": str(tmp_path), "session_id": "s1"}, monkeypatch, capsys)
    assert code == 0
    assert "禁止" in out["hookSpecificOutput"]["additionalContext"]

    # 3. 首个 prompt：无任务 → 登记待确认任务并绑定
    code, out = _hook(tmp_path, "user-prompt-submit",
                      {"cwd": str(tmp_path), "session_id": "s1",
                       "prompt": "给订单接口加一个分页参数"}, monkeypatch, capsys)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "TASK-001" in ctx and "待确认任务" in ctx
    assert sessions.get_binding(KeystoneLayout(tmp_path), "s1") == "TASK-001"

    # 4. 用户确认任务后手动推进：TODO → PLANNING
    assert keystone_main(["task", "advance", "TASK-001"]) == 0
    capsys.readouterr()

    # 5. PLANNING 阶段尝试写文件 → deny
    code, out = _hook(tmp_path, "pre-tool-use",
                      {"cwd": str(tmp_path), "session_id": "s1",
                       "tool_name": "Write", "tool_input": {"file_path": "src/A.java"}},
                      monkeypatch, capsys)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    # 5.5 生成计划文件，然后推进到 PLAN_CONFIRMED
    tasks.write_plan(KeystoneLayout(tmp_path), "TASK-001")
    assert keystone_main(["task", "advance", "TASK-001"]) == 0
    capsys.readouterr()

    # 6. 计划确认 → IMPLEMENTING → 写文件放行（无输出）
    tasks.transition_task(KeystoneLayout(tmp_path), "TASK-001", "IMPLEMENTING")
    code, out = _hook(tmp_path, "pre-tool-use",
                      {"cwd": str(tmp_path), "session_id": "s1",
                       "tool_name": "Edit", "tool_input": {"file_path": "src/A.java"}},
                      monkeypatch, capsys)
    assert code == 0 and out is None

    # 7. 开启强制模式，VERIFYING 阶段 Stop → block
    project["stop_mode"] = "enforce"
    save_project(KeystoneLayout(tmp_path), project)
    tasks.transition_task(KeystoneLayout(tmp_path), "TASK-001", "VERIFYING")
    code, out = _hook(tmp_path, "stop", {"cwd": str(tmp_path), "session_id": "s1"},
                      monkeypatch, capsys)
    assert out["decision"] == "block"

    # 8. 完成任务 → Stop 放行（reminder 文案），stop_hook_active 防循环依旧生效
    assert keystone_main(["task", "complete", "TASK-001"]) == 0
    capsys.readouterr()
    code, out = _hook(tmp_path, "stop", {"cwd": str(tmp_path), "session_id": "s1"},
                      monkeypatch, capsys)
    assert out["hookSpecificOutput"]["hookEventName"] == "Stop"
    code, out = _hook(tmp_path, "stop",
                      {"cwd": str(tmp_path), "session_id": "s1", "stop_hook_active": True},
                      monkeypatch, capsys)
    assert code == 0 and out is None

    # 9. 会话结束：记录绑定任务与结束原因
    code, out = _hook(tmp_path, "session-end",
                      {"cwd": str(tmp_path), "session_id": "s1", "reason": "clear"},
                      monkeypatch, capsys)
    assert code == 0 and out is None
    last = json.loads(KeystoneLayout(tmp_path).events_jsonl.read_text("utf-8").splitlines()[-1])
    assert last == {
        "at": last["at"],
        "event": "SessionEnd",
        "reason": "clear",
        "session_id": "s1",
        "task": "TASK-001",
    }

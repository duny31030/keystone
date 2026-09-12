"""任务编号识别与策略工具集测试。"""

from __future__ import annotations

from keystone.core import policy, taskmatch


def test_task_word_variants():
    assert taskmatch.extract_task_codes("继续 TASK-123") == ["TASK-123"]
    assert taskmatch.extract_task_codes("task 5 做一下") == ["TASK-005"]
    assert taskmatch.extract_task_codes("TASK_7") == ["TASK-007"]
    assert taskmatch.extract_task_codes("先看 Task-42 的验收标准") == ["TASK-042"]


def test_hash_code():
    assert taskmatch.extract_task_codes("处理 #12") == ["TASK-012"]


def test_order_and_dedupe():
    assert taskmatch.extract_task_codes("#3 然后 TASK-001 再 #3") == ["TASK-003", "TASK-001"]
    assert taskmatch.extract_task_codes("TASK-9 task 9") == ["TASK-009"]


def test_no_match():
    assert taskmatch.extract_task_codes("") == []
    assert taskmatch.extract_task_codes("帮我看看这个报错是什么意思") == []
    # 词边界：# 前面紧贴单词字符时不匹配
    assert taskmatch.extract_task_codes("abc#123") == []


def test_write_tool_variants():
    for name in ("Write", "write", "Edit", "write_to_file", "replace-in-file",
                 "Apply_Patch", "str_replace_editor", "Bash" ):
        if name == "Bash":
            assert not policy.is_write_tool(name)
        else:
            assert policy.is_write_tool(name), name


def test_exec_tool():
    assert policy.is_exec_tool("Bash")
    assert policy.is_exec_tool("execute-command")
    assert not policy.is_exec_tool("Read")


def test_extract_target_path():
    assert policy.extract_target_path({"file_path": "/a/b.py"}) == "/a/b.py"
    assert policy.extract_target_path({"targetFile": "/a/b.py"}) == "/a/b.py"
    assert policy.extract_target_path({"command": "ls"}) is None
    assert policy.extract_target_path("not-a-dict") is None

"""状态机单元测试。"""

from __future__ import annotations

import pytest

from keystone.core import statemachine
from keystone.errors import InvalidTransitionError


def test_main_chain_is_valid():
    chain = ["TODO", "PLANNING", "PLAN_CONFIRMED", "IMPLEMENTING", "VERIFYING", "COMPLETED"]
    for current, target in zip(chain, chain[1:]):
        statemachine.validate_transition(current, target)


def test_rework_and_reopen_allowed():
    statemachine.validate_transition("VERIFYING", "IMPLEMENTING")
    statemachine.validate_transition("COMPLETED", "IMPLEMENTING")


def test_illegal_transitions_rejected():
    for current, target in [
        ("TODO", "IMPLEMENTING"),
        ("TODO", "COMPLETED"),
        ("PLANNING", "TODO"),
        ("PLANNING", "IMPLEMENTING"),
        ("PLAN_CONFIRMED", "COMPLETED"),
        ("IMPLEMENTING", "COMPLETED"),
        ("COMPLETED", "PLANNING"),
        ("VERIFYING", "TODO"),
    ]:
        with pytest.raises(InvalidTransitionError):
            statemachine.validate_transition(current, target)


def test_next_status_walks_main_chain():
    assert statemachine.next_status("TODO") == "PLANNING"
    assert statemachine.next_status("VERIFYING") == "COMPLETED"
    with pytest.raises(InvalidTransitionError):
        statemachine.next_status("COMPLETED")


def test_unknown_status_rejected():
    with pytest.raises(InvalidTransitionError):
        statemachine.validate_transition("FOO", "TODO")
    with pytest.raises(InvalidTransitionError):
        statemachine.validate_transition("TODO", "BAR")

from agent.workflow import WorkflowState, WorkflowStatus


def test_workflow_records_step_history_when_advancing():
    state = WorkflowState.create(task_id="task_001")

    next_state = state.advance("data_check", {"artifact_id": "art_001"})

    assert next_state.status == WorkflowStatus.RUNNING
    assert next_state.current_step == "data_check"
    assert next_state.history[-1].step_name == "data_check"
    assert next_state.history[-1].output == {"artifact_id": "art_001"}


def test_workflow_can_fail_and_recover_to_previous_step():
    state = WorkflowState.create(task_id="task_001").advance(
        "data_check",
        {"artifact_id": "art_001"},
    )

    failed = state.fail("tool_execution", "tool timeout")
    recovered = failed.recover("data_check")

    assert failed.status == WorkflowStatus.FAILED
    assert failed.error_message == "tool timeout"
    assert recovered.status == WorkflowStatus.RUNNING
    assert recovered.current_step == "data_check"
    assert recovered.error_message is None

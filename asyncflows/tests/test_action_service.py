# import before importing action stuff so it gets registered via metaclass
import os
from unittest import mock
from unittest.mock import ANY

import asyncflows.tests.resources.actions  # noqa: F401
from asyncflows.tests.resources.actions import AddOutputs
from asyncflows.actions.utils.prompt_context import (
    RoleElement,
    TextElement,
    ContextElement,
)

from asyncflows.models.blob import Blob


def assert_logs(
    log_list: list[dict],
    action_id: str,
    action_name: str,
    exception: bool = False,
    action_execution: bool = True,
    assert_empty: bool = True,
    cache_hit: bool = False,
    blobs_expired: bool = False,
    final_invocation_flag: bool = False,
    ignore_cache: bool = False,
    partial_yields: int = 0,
    blobs_saved: int = 0,
    blobs_cache_checks: int = 0,
    blobs_retrieved: int = 0,
):
    # ignore some logs
    # log_list[:] = [
    #     log_dict
    #     for log_dict in log_list
    #     if log_dict["event"]
    #     # not in [
    #     #     "RACE CONDITION PREVENTED",
    #     # ]
    #     and log_dict["log_level"] != "debug"
    # ]

    if final_invocation_flag:
        log_dict = log_list.pop(0)
        assert log_dict["event"] == "Running action with final invocation flag"
        assert log_dict["action"] == action_name
        assert log_dict["action_id"] == action_id
        assert log_dict["log_level"] == "info"

    for _ in range(blobs_cache_checks):
        log_dict = log_list.pop(0)
        assert log_dict["event"] == "Checked blob existence"
        assert log_dict["action"] == action_name
        assert log_dict["action_id"] == action_id
        assert log_dict["log_level"] == "info"
        assert log_dict["namespace"] == "global"
        assert "blob" in log_dict
        assert "duration" in log_dict

    if cache_hit and not blobs_expired:
        log_dict = log_list.pop(0)
        assert log_dict["event"] == "Cache hit"
        assert log_dict["action"] == action_name
        assert log_dict["action_id"] == action_id
        assert log_dict["log_level"] == "info"
    else:
        if blobs_expired:
            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Cache hit but blobs expired"
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "info"
        elif not final_invocation_flag and not ignore_cache:
            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Cache miss"
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "info"

        if action_execution:
            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Action started"
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "info"

        for _ in range(blobs_saved):
            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Checked blob existence"
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "info"
            assert log_dict["namespace"] == "global"
            assert "blob" in log_dict
            assert "duration" in log_dict

            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Saved blob"
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "info"
            assert log_dict["namespace"] == "global"
            assert "blob" in log_dict
            assert "duration" in log_dict

        for _ in range(blobs_retrieved):
            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Retrieved blob"
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "info"
            assert log_dict["namespace"] == "global"
            assert "blob" in log_dict
            assert "duration" in log_dict

        if exception:
            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Action exception"
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "error"
        elif partial_yields > 0:
            for _ in range(partial_yields):
                log_dict = log_list.pop(0)
                assert log_dict["event"] == "Yielding outputs"
                assert log_dict["partial"]
                assert log_dict["action"] == action_name
                assert log_dict["action_id"] == action_id
                assert log_dict["log_level"] == "debug"
        elif action_execution:
            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Yielding outputs"
            assert not log_dict["partial"]
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "debug"

        if action_execution:
            log_dict = log_list.pop(0)
            assert log_dict["event"] == "Action finished"
            assert log_dict["action"] == action_name
            assert log_dict["action_id"] == action_id
            assert log_dict["log_level"] == "info"
            assert "wall_time" in log_dict
            assert "blocking_time" in log_dict

    if assert_empty:
        assert len(log_list) == 0


# def assert_unordered_logs(
#     log_list: list[dict],
#     action_ids: list[str],
#     action_names: list[str],
# ):
#     while len(action_ids) > 0:
#         for action_id, action_name in zip(action_ids, action_names):
#             try:
#                 assert_logs(log_list[:], action_id, action_name)
#                 action_ids.remove(action_id)
#                 action_names.remove(action_name)
#                 log_list = log_list[4:]
#                 break
#             except AssertionError:
#                 pass
#         else:
#             raise AssertionError(
#                 f"Could not find logs for actions: {action_ids} {action_names}"
#             )


async def test_run_action_no_deps(log, in_memory_action_service, log_history):
    action_id = "first_sum"

    # with capture_logs() as log_history:
    outputs = await in_memory_action_service.run_action(log=log, action_id=action_id)
    assert outputs.result == 3

    assert_logs(log_history, action_id, "test_add")


async def test_run_action_with_deps(log, in_memory_action_service, log_history):
    dependency_action_id = "first_sum"
    action_id = "second_sum"

    outputs = await in_memory_action_service.run_action(
        log=log,
        action_id=action_id,
    )
    assert outputs.result == 7

    assert_logs(log_history, dependency_action_id, "test_add", assert_empty=False)
    assert_logs(log_history, action_id, "test_add")


async def test_action_failure_handling(log, in_memory_action_service, log_history):
    action_id = "error_action"

    await in_memory_action_service.run_action(
        log=log,
        action_id=action_id,
    )

    assert_logs(log_history, action_id, "test_error", exception=True)


async def test_cache_and_expired_blob_detection(
    log, action_service, log_history, blob_repo
):
    create_action_id = "create_blob_action"
    create_action_name = "test_create_blob"
    get_action_id = "get_blob_action"
    get_action_name = "test_get_blob"

    # Create the blob
    outputs = await action_service.run_action(
        log=log,
        action_id=create_action_id,
    )
    assert isinstance(outputs.blob, Blob)

    assert_logs(log_history, create_action_id, create_action_name, blobs_saved=1)

    # Use the cached created blob
    await action_service.run_action(
        log=log,
        action_id=get_action_id,
    )

    assert_logs(
        log_history,
        create_action_id,
        create_action_name,
        cache_hit=True,
        assert_empty=False,
        blobs_cache_checks=1,
    )
    assert_logs(
        log_history,
        get_action_id,
        get_action_name,
        assert_empty=False,
        blobs_retrieved=1,
    )

    # Delete the blob
    await blob_repo.delete(log, outputs.blob)

    blob_deleted_log = log_history.pop(0)
    assert blob_deleted_log["event"] == "Deleted blob"
    assert blob_deleted_log["blob"] == outputs.blob
    assert "duration" in blob_deleted_log
    assert blob_deleted_log["log_level"] == "info"

    # Run the action again and expect a cache miss, triggering a new blob creation
    await action_service.run_action(
        log=log,
        action_id=get_action_id,
    )

    assert_logs(
        log_history,
        create_action_id,
        create_action_name,
        blobs_expired=True,
        assert_empty=False,
        blobs_cache_checks=1,
        blobs_saved=1,
    )
    assert_logs(
        log_history,
        get_action_id,
        get_action_name,
        assert_empty=False,
        blobs_retrieved=1,
    )

    # Delete the blob again
    await blob_repo.delete(log, outputs.blob)

    blob_deleted_log = log_history.pop(0)
    assert blob_deleted_log["event"] == "Deleted blob"
    assert blob_deleted_log["blob"] == outputs.blob
    assert "duration" in blob_deleted_log
    assert blob_deleted_log["log_level"] == "info"


async def test_cache_key(log, in_memory_action_service, log_history):
    first_action_id = "first_sum"
    second_action_id = "cache_key_adder"
    third_action_id = "cache_key_adder_2"
    action_name = "test_add"

    outputs = await in_memory_action_service.run_action(
        log=log,
        action_id=second_action_id,
    )
    assert outputs.result == 4

    assert_logs(
        log_history,
        second_action_id,
        action_name,
        action_execution=False,
        cache_hit=False,
        assert_empty=False,
    )
    assert_logs(log_history, first_action_id, action_name, assert_empty=False)
    assert_logs(log_history, second_action_id, action_name)

    outputs = await in_memory_action_service.run_action(
        log=log,
        action_id=third_action_id,
    )
    assert outputs.result == 4

    assert_logs(log_history, third_action_id, action_name, cache_hit=True)


async def test_nested_inputs(log, in_memory_action_service, log_history):
    first_action_id = "first_sum_nested"
    second_action_id = "second_sum_nested"
    action_name = "test_nested_add"

    outputs = await in_memory_action_service.run_action(
        log=log,
        action_id=second_action_id,
    )
    assert outputs.nested.result == 7

    assert_logs(log_history, first_action_id, action_name, assert_empty=False)
    assert_logs(log_history, second_action_id, action_name)


async def test_optional_nested(log, in_memory_action_service, log_history):
    first_action_id = "first_sum_nested"
    first_action_name = "test_nested_add"
    second_action_id = "sum_optional_nested"
    second_action_name = "test_optional_nested_add"

    outputs = await in_memory_action_service.run_action(
        log=log,
        action_id=second_action_id,
    )
    assert outputs.nested.result == 5

    assert_logs(log_history, first_action_id, first_action_name, assert_empty=False)
    assert_logs(log_history, second_action_id, second_action_name)


async def test_transforming_inputs(log, in_memory_action_service, log_history):
    first_action_id = "first_sum"
    first_action_name = "test_add"
    second_action_id = "transforming_prompt"
    second_action_name = "test_transforming_prompt"

    outputs = await in_memory_action_service.run_action(
        log=log,
        action_id=second_action_id,
    )
    assert outputs.context_value == "3"
    assert outputs.nested_context_value == "3"

    assert_logs(log_history, first_action_id, first_action_name, assert_empty=False)
    assert_logs(log_history, second_action_id, second_action_name)


async def test_prompt_inputs(log, in_memory_action_service, log_history):
    action_id = "passing_prompt"
    action_name = "test_passing_prompt"

    openai_api_key_bak = os.environ.get("OPENAI_API_KEY")
    try:
        os.environ["OPENAI_API_KEY"] = "mock"
        outputs = await in_memory_action_service.run_action(
            log=log, action_id=action_id
        )
    finally:
        if openai_api_key_bak is not None:
            os.environ["OPENAI_API_KEY"] = openai_api_key_bak
        else:
            del os.environ["OPENAI_API_KEY"]

    assert len(outputs.prompt) == 6
    assert isinstance(outputs.prompt[0], RoleElement)
    assert outputs.prompt[0].role == "system"
    assert isinstance(outputs.prompt[1], TextElement)
    assert outputs.prompt[1].text == "Hi 3"
    assert isinstance(outputs.prompt[2], ContextElement)
    assert outputs.prompt[2].heading == "Test2 3"
    assert outputs.prompt[2].value == "Oh 7"
    assert isinstance(outputs.prompt[3], RoleElement)
    assert outputs.prompt[3].role == "assistant"
    assert isinstance(outputs.prompt[4], ContextElement)
    assert outputs.prompt[4].heading == "abc"
    assert outputs.prompt[4].value == "3"
    assert isinstance(outputs.prompt[5], TextElement)
    assert outputs.prompt[5].text == "3"
    # assert outputs.prompt.context.root[0].value == "7"
    # assert outputs.prompt.context.root[0].heading == "Test"
    # assert outputs.instructions.value == "Hi 3"
    # assert len(outputs.instructions.context.root) == 1
    # assert outputs.instructions.context.root[0].value == "Oh 7"
    # assert outputs.instructions.context.root[0].heading == "Test2 3"

    # asserting logs here is hard because their order is not guaranteed

    # import json
    # print(json.dumps(log_history, indent=2))

    # TODO figure out a better way to test for this action, instead of changing this number
    #  any time any logs get added/removed (including debug)
    #  better yet, find a streaming way to interleavingly check against logs
    assert_logs(
        log_history[-4:],
        action_id,
        action_name,
    )


async def test_streaming_action(log, in_memory_action_service, log_history):
    action_id = "range_stream"
    action_name = "test_range_stream"

    expected_outputs = list(range(10))
    async for outputs in in_memory_action_service.stream_action(
        log=log, action_id=action_id
    ):
        assert outputs.value == expected_outputs.pop(0)

    assert_logs(log_history, action_id, action_name, partial_yields=10)


async def test_successive_action(
    log, in_memory_action_service, log_history, cache_repo
):
    # test that if you send different inputs through an action twice in quick succession,
    #  it returns the correct outputs for each
    double_id = "double_add"
    double_name = "test_double_add"
    waiting_id = "waiting_add"
    waiting_name = "test_waiting_add"

    expected_double_outputs = [3, 6]
    i = 0
    async for outputs in in_memory_action_service.stream_action(
        log=log,
        action_id=double_id,
    ):
        assert outputs.result == expected_double_outputs[i]
        i += 1
        async for outputs_2 in in_memory_action_service.stream_action(
            log=log,
            action_id=waiting_id,
        ):
            assert outputs_2.result == 7

    assert_logs(
        log_history, double_id, double_name, partial_yields=2, assert_empty=False
    )
    assert_logs(log_history, double_id, double_name, cache_hit=True, assert_empty=False)
    assert_logs(log_history, waiting_id, waiting_name, assert_empty=False)
    assert_logs(log_history, double_id, double_name, cache_hit=True, assert_empty=False)
    assert_logs(log_history, waiting_id, waiting_name, cache_hit=True)


async def test_final_invocation_action(log, in_memory_action_service, log_history):
    action_id = "finish_action"
    action_name = "test_finish"

    result = await in_memory_action_service.run_action(log=log, action_id=action_id)
    assert result.finish_history == [False, True]

    assert_logs(log_history, action_id, action_name, assert_empty=False)
    assert_logs(log_history, action_id, action_name, final_invocation_flag=True)


async def test_non_caching_adder(log, in_memory_action_service, log_history):
    action_id = "non_caching_adder"
    action_name = "test_non_caching_adder"

    for _ in range(2):
        outputs = await in_memory_action_service.run_action(
            log=log, action_id=action_id
        )
        assert outputs.result == 3

    assert_logs(
        log_history,
        action_id,
        action_name,
        assert_empty=False,
        ignore_cache=True,
    )
    assert_logs(log_history, action_id, action_name, ignore_cache=True)


async def test_exception_in_internals(log, in_memory_action_service, log_history):
    action_id = "first_sum"
    action_name = "test_add"

    # replace action_service._run_action with lambda: raise Exception
    with mock.patch.object(
        in_memory_action_service,
        "_run_action",
        side_effect=Exception("test_exception_in_internals"),
    ):
        await in_memory_action_service.run_action(log=log, action_id=action_id)

    assert log_history == [
        {
            "action": action_name,
            "action_id": action_id,
            "event": "Cache miss",
            "log_level": "info",
        },
        {
            "action": action_name,
            "action_id": action_id,
            "event": "Action service exception",
            "traceback": ANY,
            "log_level": "error",
        },
        {
            "action": action_name,
            "action_id": action_id,
            "event": "Action task ended without yielding outputs",
            "log_level": "error",
            "partial": False,
        },
    ]


async def test_exception_in_upstream_action_internals(
    log, in_memory_action_service, log_history, cache_repo
):
    action_id = "second_sum"
    action_name = "test_add"
    upstream_action_id = "first_sum"
    upstream_action_name = "test_add"

    # replace action_service._run_action with lambda: raise Exception,
    # but only when called with `action_id=upstream_action_id` kwarg
    run_func = in_memory_action_service._run_action

    def _run_action(*args, **kwargs):
        if kwargs["action_id"] == upstream_action_id:
            raise Exception("test_exception_in_upstream_action_internals")
        else:
            return run_func(*args, **kwargs)

    with mock.patch.object(
        in_memory_action_service,
        "_run_action",
        side_effect=_run_action,
    ):
        await in_memory_action_service.run_action(log=log, action_id=action_id)

    assert log_history == [
        {
            "action": upstream_action_name,
            "action_id": upstream_action_id,
            "event": "Cache miss",
            "log_level": "info",
            "downstream_action_id": action_id,
        },
        {
            "action_id": upstream_action_id,
            "action": upstream_action_name,
            "event": "Action service exception",
            "traceback": ANY,
            "log_level": "error",
            "downstream_action_id": action_id,
        },
        {
            "action_id": upstream_action_id,
            "action": upstream_action_name,
            "event": "Action task ended without yielding outputs",
            "log_level": "error",
            "partial": False,
            "downstream_action_id": action_id,
        },
        {
            "action_id": action_id,
            "action": action_name,
            "event": "Not all action tasks completed",
            "action_task_ids": [upstream_action_id],
            "missing_action_ids": {upstream_action_id},
            "log_level": "error",
        },
        {
            "action_id": action_id,
            "action": action_name,
            "event": "Action task ended without yielding outputs",
            "log_level": "error",
            "partial": False,
        },
    ]


async def test_streaming_dependency(log, in_memory_action_service, log_history):
    action_id = "streaming_dependency_add"
    action_name = "test_add"
    dependency_id = "double_add"
    dependency_name = "test_double_add"

    expected_outputs = [4, 7]
    i = 0
    async for outputs in in_memory_action_service.stream_action(
        log=log,
        action_id=action_id,
    ):
        assert outputs.result == expected_outputs[i]
        i += 1

    assert_logs(
        log_history,
        dependency_id,
        dependency_name,
        partial_yields=2,
        assert_empty=False,
    )
    assert_logs(log_history, action_id, action_name, assert_empty=False)
    assert_logs(log_history, action_id, action_name)


async def test_non_streaming_dependency(log, in_memory_action_service, log_history):
    action_id = "non_streaming_dependency_add"
    action_name = "test_add"
    dependency_id = "double_add"
    dependency_name = "test_double_add"

    expected_output = 7
    async for outputs in in_memory_action_service.stream_action(
        log=log,
        action_id=action_id,
    ):
        assert outputs.result == expected_output

    assert_logs(
        log_history,
        dependency_id,
        dependency_name,
        partial_yields=2,
        assert_empty=False,
    )
    assert_logs(log_history, action_id, action_name)


async def test_both_streaming_dependency(log, in_memory_action_service, log_history):
    action_id = "both_streaming_dependency_add"
    action_name = "test_add"
    dependency_id = "double_add"
    dependency_name = "test_double_add"

    expected_outputs = [12]
    i = 0
    async for outputs in in_memory_action_service.stream_action(
        log=log,
        action_id=action_id,
    ):
        assert outputs.result == expected_outputs[i]
        i += 1

    assert_logs(
        log_history,
        dependency_id,
        dependency_name,
        partial_yields=2,
        assert_empty=False,
    )
    assert_logs(log_history, action_id, action_name)


async def test_env_adder(log, in_memory_action_service, log_history):
    action_id = "env_adder"
    action_name = "test_add"

    try:
        os.environ["DUMMY_ENV_VAR"] = "10"
        outputs = await in_memory_action_service.run_action(
            log=log, action_id=action_id
        )
    finally:
        del os.environ["DUMMY_ENV_VAR"]

    assert outputs.result == 11

    assert_logs(log_history, action_id, action_name)


async def test_lambda_adder(log, in_memory_action_service, log_history):
    action_id = "lambda_adder"
    action_name = "test_add"
    first_dependency_id = "first_sum"
    second_dependency_id = "second_sum"

    outputs = await in_memory_action_service.run_action(log=log, action_id=action_id)

    assert outputs.result == 11

    assert_logs(log_history, first_dependency_id, action_name, assert_empty=False)
    assert_logs(
        log_history,
        first_dependency_id,
        action_name,
        assert_empty=False,
        cache_hit=True,
    )
    assert_logs(log_history, second_dependency_id, action_name, assert_empty=False)
    assert_logs(log_history, action_id, action_name)


async def test_for_loop_adder(log, in_memory_action_service, log_history):
    loop_id = "sum_iterator"

    outputs = await in_memory_action_service.run_loop(log=log, loop_id=loop_id)

    assert outputs == [
        {
            "add": AddOutputs(result=1),
        },
        {
            "add": AddOutputs(result=2),
        },
        {
            "add": AddOutputs(result=3),
        },
    ]

    # TODO test unordered logs


async def test_dependent_in_loop(log, in_memory_action_service, log_history):
    loop_id = "dependent_in_iterator"

    outputs = await in_memory_action_service.run_loop(log=log, loop_id=loop_id)

    assert outputs == [
        {
            "add": AddOutputs(result=1),
        },
        {
            "add": AddOutputs(result=2),
        },
        {
            "add": AddOutputs(result=3),
        },
    ]

    # TODO test unordered logs


async def test_dependent_flow_loop(log, in_memory_action_service, log_history):
    loop_id = "dependent_flow_iterator"

    outputs = await in_memory_action_service.run_loop(log=log, loop_id=loop_id)

    assert outputs == [
        {
            "add": AddOutputs(result=3),
        },
        {
            "add": AddOutputs(result=4),
        },
        {
            "add": AddOutputs(result=5),
        },
    ]

    # TODO test unordered logs


async def test_nested_loop(log, in_memory_action_service, log_history):
    loop_id = "nested_iterator"

    expected_outputs = []
    for i in range(3):
        nested_outputs = []
        for j in range(3):
            nested_outputs.append({"add": AddOutputs(result=i + j)})
        expected_outputs.append({"nested": nested_outputs})

    outputs = await in_memory_action_service.run_loop(log=log, loop_id=loop_id)
    assert outputs == expected_outputs

    # TODO test unordered logs


async def test_loop_with_internal_dependencies(
    log, in_memory_action_service, log_history
):
    loop_id = "iterator_with_internal_dependencies"

    expected_outputs = []
    for i in range(3):
        expected_outputs.append(
            {
                "add": AddOutputs(result=i + 3),
                "add2": AddOutputs(result=i * 2 + 3),
            }
        )

    outputs = await in_memory_action_service.run_loop(log=log, loop_id=loop_id)
    assert outputs == expected_outputs

    # TODO test unordered logs


# TODO test that `new_listeners` are all delivered the latest output when starting to listen while action is caching
# TODO test exception throwing through dependencies
# TODO test multiple interleaving streaming actions
# TODO smoke out race conditions (randomly spawn many interleaving actions/dependencies)
# TODO test streaming action connecting to streaming action
#  if receiving streaming action runs slower than the sending, it should wait for the current one to finish,
#  then run another instance with updated inputs

from typing_extensions import Any, assert_never

import structlog

from asyncflows.models.config.action import ActionInvocation
from asyncflows.utils.rendering_utils import extract_root_var
from asyncflows.models.config.flow import (
    ActionConfig,
    Loop,
    FlowConfig,
    Executable,
)
from asyncflows.models.config.model import ModelConfig
from asyncflows.models.primitives import ContextVarPath, ExecutableId
from asyncflows.services.action_service import ActionService


def _get_root_dependencies(
    input_spec: Any,
):
    dependency_tuples = (
        ActionService._get_dependency_ids_and_stream_flag_from_input_spec(input_spec)
    )
    return [dep for dep, _ in dependency_tuples]


def check_default_model_consistency(
    log: structlog.stdlib.BoundLogger,
    default_model: ModelConfig,
    variables: set[str],
):
    dependencies = _get_root_dependencies(default_model)

    unmet_dependencies = [dep for dep in dependencies if dep not in variables]

    pass_ = True

    for dep in unmet_dependencies:
        log.error("Variable not found", variable_name=dep)
        pass_ = False

    return pass_


def check_flow_consistency(
    log: structlog.stdlib.BoundLogger,
    nodes: list[ExecutableId],
    variables: set[str],
    flow: FlowConfig,
):
    pass_ = True

    for executable_id in nodes:
        log = log.bind(
            dependency_path=f"{log._context['dependency_path']}.{executable_id}"
        )
        invocation = flow[executable_id]
        if isinstance(invocation, Loop):
            if not check_loop_consistency(log, flow, invocation, variables):
                pass_ = False
        elif isinstance(invocation, ActionInvocation):
            if not check_action_consistency(log, flow, invocation, variables):
                pass_ = False
        else:
            assert_never(invocation)

    return pass_


def check_loop_consistency(
    log: structlog.stdlib.BoundLogger,
    flow: FlowConfig,
    loop: Loop,
    variables: set[str],
):
    dependencies = _get_root_dependencies(loop.in_)

    unmet_dependencies = [dep for dep in dependencies if dep not in variables]

    pass_ = True

    for dep in unmet_dependencies:
        if dep not in flow:
            log.error("Dependency not found in flow", dependency=dep)
            pass_ = False
        else:
            if not check_invocation_consistency(
                log.bind(dependency_path=dep), flow, flow[dep], variables
            ):
                pass_ = False

    joint_variables = variables | {loop.for_}
    joint_flow = flow | loop.flow

    # TODO at time of writing all actions in the loop subflow are run;
    #  after we move from that, this shouldn't check against the whole flow, but only the relevant invocations
    if not check_flow_consistency(
        log, list(loop.flow), joint_variables, flow=joint_flow
    ):
        pass_ = False

    return pass_


def check_action_consistency(
    log: structlog.stdlib.BoundLogger,
    flow: FlowConfig,
    invocation: ActionInvocation,
    variables: set[str],
):
    dependencies = _get_root_dependencies(invocation)

    unmet_dependencies = [dep for dep in dependencies if dep not in variables]

    pass_ = True

    for dep in unmet_dependencies:
        if dep not in flow:
            log.error("Dependency not found in flow", dependency=dep)
            pass_ = False
        else:
            if not check_invocation_consistency(
                log.bind(dependency_path=dep), flow, flow[dep], variables
            ):
                pass_ = False

    return pass_


def check_invocation_consistency(
    log: structlog.stdlib.BoundLogger,
    flow: FlowConfig,
    invocation: Executable,
    variables: set[str],
):
    if isinstance(invocation, Loop):
        return check_loop_consistency(log, flow, invocation, variables)
    elif isinstance(invocation, ActionInvocation):
        return check_action_consistency(log, flow, invocation, variables)
    else:
        assert_never(invocation)


def check_config_consistency(
    log: structlog.stdlib.BoundLogger,
    config: ActionConfig,
    variables: set[str],
    target_output: ContextVarPath,
):
    pass_ = True

    if not check_default_model_consistency(
        log.bind(dependency_path="default_model"), config.default_model, variables
    ):
        pass_ = False

    root_dependency_id = extract_root_var(target_output)
    if root_dependency_id not in config.flow:
        log.error("Dependency not found in flow", dependency=root_dependency_id)
        return False

    if not check_invocation_consistency(
        log.bind(dependency_path=root_dependency_id),
        config.flow,
        config.flow[root_dependency_id],
        variables,
    ):
        pass_ = False

    return pass_

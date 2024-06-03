from typing import Any, assert_never

import structlog

from asyncflows.models.config.action import ActionInvocation
from asyncflows.models.config.flow import (
    ActionConfig,
    Loop,
    FlowConfig,
)
from asyncflows.models.config.model import ModelConfig
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

    joint_variables = variables | {loop.for_}
    joint_flow = flow | loop.flow

    if not check_flow_consistency(
        log, loop.flow, joint_variables, flow_namespace=joint_flow
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

    return pass_


def check_flow_consistency(
    log: structlog.stdlib.BoundLogger,
    flow: FlowConfig,
    variables: set[str],
    flow_namespace: FlowConfig | None = None,
):
    if flow_namespace is None:
        flow_namespace = flow
    pass_ = True

    for name, invocation in flow.items():
        log = log.bind(dependency_path=f"{log._context['dependency_path']}.{name}")
        if isinstance(invocation, Loop):
            if not check_loop_consistency(log, flow_namespace, invocation, variables):
                pass_ = False
        elif isinstance(invocation, ActionInvocation):
            if not check_action_consistency(log, flow_namespace, invocation, variables):
                pass_ = False
        else:
            assert_never(invocation)

    return pass_


def check_config_consistency(
    log: structlog.stdlib.BoundLogger,
    config: ActionConfig,
    variables: set[str],
):
    pass_ = True

    if not check_default_model_consistency(
        log.bind(dependency_path="default_model"), config.default_model, variables
    ):
        pass_ = False

    if not check_flow_consistency(
        log.bind(dependency_path="flow"), config.flow, variables
    ):
        pass_ = False

    return pass_

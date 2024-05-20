from typing import Union

from pydantic import Field

from asyncflows.models.config.action import (
    ActionInvocationUnion,
    TestingActionInvocationUnion,
)
from asyncflows.models.config.common import StrictModel
from asyncflows.models.config.model import ModelConfig
from asyncflows.models.config.value_declarations import ValueDeclaration
from asyncflows.models.primitives import ContextVarName, ContextVarPath, ExecutableId


class Loop(StrictModel):
    for_: ContextVarName = Field(
        ...,
        alias="for",
    )
    in_: ValueDeclaration = Field(
        ...,
        alias="in",
    )
    flow: "FlowConfig"


class TestLoop(Loop):
    flow: "TestFlowConfig"


class ActionConfig(StrictModel):
    default_model: ModelConfig
    action_timeout: float = 360
    flow: "FlowConfig"
    default_output: ContextVarPath


class TestActionConfig(ActionConfig):
    flow: "TestFlowConfig"


Executable = Union[ActionInvocationUnion, Loop]
FlowConfig = dict[ExecutableId, Executable]

TestExecutable = Union[TestingActionInvocationUnion, TestLoop]
TestFlowConfig = dict[ExecutableId, TestExecutable]

from typing import Union

import pydantic
from pydantic import Field

from asyncflows.models.config.action import (
    ActionInvocationUnion,
    TestingActionInvocationUnion,
)
from asyncflows.models.config.common import StrictModel
from asyncflows.models.config.model import ModelConfig
from asyncflows.models.config.value_declarations import ValueDeclaration
from asyncflows.models.primitives import ContextVarName, ContextVarPath, ExecutableId
from asyncflows.models.config.action import build_hinted_value_declaration
from asyncflows.models.config.value_declarations import (
    LinkDeclaration,
    LambdaDeclaration,
)
from asyncflows.utils.config_utils import templatify_model


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


def build_model_config(
    strict: bool = False,
):
    # Dynamically build the model config like ActionModel, with the ValueDeclarations

    HintedValueDeclaration = build_hinted_value_declaration(
        strict=strict, excluded_declaration_types=[LinkDeclaration, LambdaDeclaration]
    )

    fields = templatify_model(
        ModelConfig,
        vars_=None,
        links=None,
        add_union=HintedValueDeclaration,  # type: ignore
        strict=strict,
    )

    return pydantic.create_model(
        "ModelConfigDeclaration",
        __base__=ModelConfig,
        __module__=__name__,
        # model_config=ConfigDict(
        #     arbitrary_types_allowed=True,
        # ),
        **fields,  # pyright: ignore[reportGeneralTypeIssues]
    )


ModelConfigDeclaration = build_model_config()


class ActionConfig(StrictModel):
    default_model: ModelConfigDeclaration  # type: ignore
    action_timeout: float = 360
    flow: "FlowConfig"
    default_output: ContextVarPath


class TestActionConfig(ActionConfig):
    flow: "TestFlowConfig"


Executable = Union[ActionInvocationUnion, Loop]
FlowConfig = dict[ExecutableId, Executable]

TestExecutable = Union[TestingActionInvocationUnion, TestLoop]
TestFlowConfig = dict[ExecutableId, TestExecutable]

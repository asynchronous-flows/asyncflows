from typing import Union

from pydantic import Field

from asyncflows.models.config.action import (
    ActionInvocation,
    build_actions,
)
from asyncflows.models.config.common import StrictModel
from asyncflows.models.config.model import ModelConfig
from asyncflows.utils.type_utils import transform_and_templatify_type
from asyncflows.models.config.value_declarations import ValueDeclaration
from asyncflows.models.primitives import (
    ContextVarName,
    ContextVarPath,
    ExecutableId,
    HintLiteral,
)
from asyncflows.models.config.action import build_hinted_value_declaration
from asyncflows.models.config.value_declarations import (
    LinkDeclaration,
    LambdaDeclaration,
)


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


def build_model_config(
    strict: bool = False,
):
    # Dynamically build the model config like ActionModel, with the ValueDeclarations

    HintedValueDeclaration = build_hinted_value_declaration(
        strict=strict, excluded_declaration_types=[LinkDeclaration, LambdaDeclaration]
    )

    return transform_and_templatify_type(
        ModelConfig,
        add_union=HintedValueDeclaration,  # type: ignore
        strict=strict,
    )


ModelConfigDeclaration = build_model_config()


class ActionConfig(StrictModel):
    default_model: ModelConfigDeclaration  # type: ignore
    action_timeout: float = 360
    flow: "FlowConfig"
    default_output: ContextVarPath  # TODO `| ValueDeclaration`


Executable = Union[ActionInvocation, Loop]
FlowConfig = dict[ExecutableId, Executable]


def build_hinted_action_config(
    action_names: list[str] | None = None,
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    strict: bool = False,
):
    HintedValueDeclaration = build_hinted_value_declaration(
        # vars_=vars_,
        links=links,
        strict=strict,
    )

    ActionInvocationUnion = Union[
        tuple(
            build_actions(
                action_names=action_names,
                vars_=vars_,
                links=links,
                strict=strict,
            )
        )  # pyright: ignore
    ]

    class HintedLoop(Loop):
        in_: HintedValueDeclaration = Field(  # type: ignore
            ...,
            alias="in",
        )
        flow: "HintedFlowConfig"  # type: ignore

    class HintedActionConfig(ActionConfig):
        flow: "HintedFlowConfig"  # type: ignore

    HintedExecutable = Union[ActionInvocationUnion, HintedLoop]
    HintedFlowConfig = dict[ExecutableId, HintedExecutable]

    HintedActionConfig.model_rebuild()  # TODO is this necessary?

    return HintedActionConfig

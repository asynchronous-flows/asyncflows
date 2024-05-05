from typing import Union, Literal

import pydantic
from pydantic import ConfigDict, Field

from asyncflows.actions import get_actions_dict
from asyncflows.models.config.common import StrictModel
from asyncflows.models.config.model import ModelConfig
from asyncflows.models.config.value_declarations import (
    VarDeclaration,
    ValueDeclaration,
    LinkDeclaration,
)
from asyncflows.models.primitives import HintType
from asyncflows.models.primitives import ExecutableName, ExecutableId
from asyncflows.utils.config_utils import templatify_model


# if TYPE_CHECKING:
#     ActionId = str
#     Action = Any
# else:
#     actions = get_actions_dict()
#     ActionId = Literal[tuple(actions)]
#     Action = Union[tuple(actions.values())]


class ActionInvocation(StrictModel):
    action: ExecutableName
    cache_key: None | str | ValueDeclaration = Field(
        None,
        description="The cache key for this action's result. Should be unique among all actions.",
    )


def build_actions(
    vars_: HintType | None = None,
    links: HintType | None = None,
    strict: bool = False,
):
    # Dynamically build action models from currently defined actions
    # for best typehints and autocompletion possible in the jsonschema

    HintedValueDeclaration = ValueDeclaration

    if vars_:
        HintedValueDeclaration = Union[
            HintedValueDeclaration, VarDeclaration.from_vars(vars_, strict)
        ]

    if links:
        HintedValueDeclaration = Union[
            HintedValueDeclaration, LinkDeclaration.from_vars(links, strict)
        ]

    actions = get_actions_dict()
    action_models = []
    for action in actions.values():
        # build base model field
        fields = {
            "action": (Literal[action.name], ...)  # type: ignore
        }

        # build input fields
        inputs = action._get_inputs_type()
        if not isinstance(None, inputs):
            fields |= templatify_model(
                inputs,
                vars_=vars_,
                add_union=HintedValueDeclaration,
                strict=strict,
            )

        # build action invocation model
        action_basemodel = pydantic.create_model(
            action.name + "ActionInvocation",
            __base__=ActionInvocation,
            __module__=__name__,
            model_config=ConfigDict(
                arbitrary_types_allowed=True,
            ),
            **fields,  # pyright: ignore[reportGeneralTypeIssues]
        )
        action_models.append(action_basemodel)
    return action_models


ActionInvocationUnion = Union[tuple(build_actions())]  # pyright: ignore


class ActionConfig(StrictModel):
    default_model: ModelConfig
    action_timeout: float = 360
    flow: dict[ExecutableId, ActionInvocationUnion]
    default_output: ExecutableId


# TODO assert tests not imported before this line
import asyncflows.tests.resources.actions  # noqa


TestingActionInvocationUnion = Union[tuple(build_actions())]  # pyright: ignore


class TestActionConfig(ActionConfig):
    flow: dict[ExecutableId, TestingActionInvocationUnion]

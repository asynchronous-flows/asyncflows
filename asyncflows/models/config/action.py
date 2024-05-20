from typing import Union, Literal

import pydantic
from pydantic import ConfigDict, Field

from asyncflows.actions import get_actions_dict
from asyncflows.models.config.common import StrictModel
from asyncflows.models.config.value_declarations import (
    VarDeclaration,
    ValueDeclaration,
    LinkDeclaration,
)
from asyncflows.models.primitives import HintType
from asyncflows.models.primitives import ExecutableName
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
    action_names: list[str],
    vars_: HintType | None = None,
    links: HintType | None = None,
    strict: bool = False,
):
    # Dynamically build action models from currently defined actions
    # for best typehints and autocompletion possible in the jsonschema

    HintedValueDeclaration = ValueDeclaration

    if vars_:
        HintedValueDeclaration = Union[
            VarDeclaration.from_vars(vars_, strict), HintedValueDeclaration
        ]

    if links:
        HintedValueDeclaration = Union[
            LinkDeclaration.from_vars(links, strict), HintedValueDeclaration
        ]

    actions_dict = get_actions_dict()
    action_models = []
    for action_name in action_names:
        action = actions_dict[action_name]
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
                links=links,
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


_action_names = list(get_actions_dict().keys())
ActionInvocationUnion = Union[tuple(build_actions(_action_names))]  # pyright: ignore


# TODO assert tests not imported before this line
import asyncflows.tests.resources.actions  # noqa


_testing_action_names = list(get_actions_dict().keys())
TestingActionInvocationUnion = Union[tuple(build_actions(_testing_action_names))]  # pyright: ignore

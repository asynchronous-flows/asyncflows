import typing
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
from asyncflows.models.primitives import HintLiteral
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


def build_hinted_value_declaration(
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    strict: bool = False,
    excluded_declaration_types: None | list[type[ValueDeclaration]] = None,
):
    if excluded_declaration_types is None:
        excluded_declaration_types = []

    union_elements = []

    if vars_:
        union_elements.append(
            VarDeclaration.from_hint_literal(vars_, strict),
        )
    if not vars_ or not strict and VarDeclaration not in excluded_declaration_types:
        union_elements.append(VarDeclaration)

    if links:
        union_elements.append(
            LinkDeclaration.from_hint_literal(links, strict),
        )
    if not links or not strict and LinkDeclaration not in excluded_declaration_types:
        union_elements.append(LinkDeclaration)

    other_elements = [
        element
        for element in typing.get_args(ValueDeclaration)
        if element not in (VarDeclaration, LinkDeclaration)
        and element not in excluded_declaration_types
    ]
    union_elements.extend(other_elements)

    return Union[tuple(union_elements)]  # type: ignore


def build_actions(
    action_names: list[str] | None = None,
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    strict: bool = False,
):
    # Dynamically build action models from currently defined actions
    # for best typehints and autocompletion possible in the jsonschema

    HintedValueDeclaration = build_hinted_value_declaration(vars_, links, strict)

    if action_names is None:
        action_names = list(get_actions_dict().keys())

    actions_dict = get_actions_dict()
    action_models = []
    for action_name in action_names:
        action = actions_dict[action_name]
        # build base model field
        fields = {
            "action": (Literal[action.name], ...),  # type: ignore
            "cache_key": (None | str | HintedValueDeclaration, None),
        }

        # build input fields
        inputs = action._get_inputs_type()
        if not isinstance(None, inputs):
            fields |= templatify_model(
                inputs,
                vars_=vars_,
                links=links,
                add_union=HintedValueDeclaration,  # type: ignore
                strict=strict,
            )

        # build action invocation model
        action_basemodel = pydantic.create_model(
            action.name + "ActionInvocation",
            __base__=ActionInvocation,
            __module__=__name__,
            model_config=ConfigDict(
                arbitrary_types_allowed=True,
                extra="forbid",
            ),
            **fields,  # pyright: ignore[reportGeneralTypeIssues]
        )
        action_models.append(action_basemodel)
    return action_models

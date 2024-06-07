import inspect
import os
import types
import typing
from enum import Enum
from typing import Union, Literal

import pydantic
from pydantic import ConfigDict, Field
from pydantic.fields import FieldInfo

from asyncflows.actions import get_actions_dict, InternalActionBase
from asyncflows.models.config.common import StrictModel
from asyncflows.models.config.transform import TransformsFrom
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


def build_type_qualified_name(type_: type, *, markdown: bool) -> str:
    if type_ is type(None):
        return "None"

    # convert unions to a string
    origin = typing.get_origin(type_)
    if origin is not None:
        if origin in [Union, types.UnionType]:
            args = typing.get_args(type_)
            return " | ".join(
                build_type_qualified_name(arg, markdown=markdown) for arg in args
            )

        # convert literal to a string
        if origin is Literal:
            args = typing.get_args(type_)
            return " | ".join(repr(arg) for arg in args)

        # handle other origins
        origin_qual_name = build_type_qualified_name(origin, markdown=markdown)
        args_qual_names = " | ".join(
            build_type_qualified_name(arg, markdown=markdown)
            for arg in typing.get_args(type_)
        )
        return f"{origin_qual_name}[{args_qual_names}]"

    # if not isinstance(type_, type):
    #     raise ValueError(f"Invalid type: {type_}")

    if inspect.isclass(type_) and issubclass(type_, TransformsFrom):
        return build_type_qualified_name(
            type_._get_config_type(None, None), markdown=markdown
        )

    # convert string enums to a string
    if inspect.isclass(type_) and issubclass(type_, Enum):
        return " | ".join(repr(member.value) for member in type_)

    # pass through names of simple and well-known types
    if type_.__module__ in ["builtins", "typing"]:
        return type_.__qualname__

    # add markdown link to custom types
    if not markdown:
        return type_.__qualname__

    # Building the link to the source code file
    try:
        # Get the file and line number where the type is defined
        source_file = inspect.getfile(type_)
        source_line = inspect.getsourcelines(type_)[1]

        # Construct the file URL
        source_path = os.path.abspath(source_file)
        file_url = f"file://{source_path}#L{source_line}"
        return f"[{type_.__qualname__}]({file_url})"
    except Exception:
        # Fallback to just the type name if we can't get the source file
        return type_.__qualname__


def remove_optional(type_: type | None) -> tuple[type, bool]:
    if type_ is None:
        return typing.Any, True
    if typing.get_origin(type_) in [Union, types.UnionType]:
        args = typing.get_args(type_)
        if type(None) in args:
            return args[0], True
    return type_, False


def build_field_description(
    field_name: str, field_info: FieldInfo, *, markdown: bool
) -> str:
    type_, is_optional = remove_optional(field_info.annotation)
    qualified_name = build_type_qualified_name(type_, markdown=markdown)

    field_desc = f"{field_name}: {qualified_name}"
    if is_optional:
        field_desc += " (optional)"

    if field_info.description:
        field_desc += f"  \n  {field_info.description}"

    return field_desc


def build_action_description(
    action: type[InternalActionBase], *, markdown: bool
) -> None | str:
    description_items = []

    # grab the main description
    if action.description:
        description_items.append(inspect.cleandoc(action.description))

    # add inputs description
    inputs_description_items = []
    inputs = action._get_inputs_type()
    if not isinstance(None, inputs):
        for field_name, field_info in inputs.model_fields.items():
            inputs_description_items.append(
                f"- {build_field_description(field_name, field_info, markdown=markdown)}"
            )
    if inputs_description_items:
        if markdown:
            title = "**Inputs**"
        else:
            title = "INPUTS"
        description_items.append(f"{title}\n" + "\n".join(inputs_description_items))

    # add outputs description
    outputs_description_items = []
    outputs = action._get_outputs_type()
    if not isinstance(None, outputs):
        for field_name, field_info in outputs.model_fields.items():
            outputs_description_items.append(
                f"- {build_field_description(field_name, field_info, markdown=markdown)}"
            )
    if outputs_description_items:
        if markdown:
            title = "**Outputs**"
        else:
            title = "OUTPUTS"
        description_items.append(f"{title}\n" + "\n".join(outputs_description_items))

    if not description_items:
        return None
    if markdown:
        description_items.append("---")
    return "\n\n".join(description_items)


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

        if action.readable_name:
            title = action.readable_name
        else:
            title = f"{action.name.replace('_', ' ').title()} Action"
        description = build_action_description(action, markdown=False)
        markdown_description = build_action_description(action, markdown=True)

        # build action literal
        action_literal = Literal[action.name]  # type: ignore
        if description is not None:
            action_literal = typing.Annotated[
                action_literal,
                Field(
                    title=title,
                    description=description,
                    json_schema_extra={
                        "markdownDescription": markdown_description,
                    },
                ),
            ]

        # build base model field
        fields = {
            "action": (action_literal, ...),
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
            __doc__=description,
            model_config=ConfigDict(
                title=title,
                json_schema_extra={
                    "markdownDescription": markdown_description,
                },
                arbitrary_types_allowed=True,
                extra="forbid",
            ),
            **fields,  # pyright: ignore[reportGeneralTypeIssues]
        )
        action_models.append(action_basemodel)
    return action_models

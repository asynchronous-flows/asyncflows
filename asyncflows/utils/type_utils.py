import inspect
import os
import types
import typing
from enum import Enum
from typing import Any, Literal, Union, Annotated
from weakref import WeakValueDictionary

import pydantic
from pydantic import Field, BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from asyncflows.actions import InternalActionBase, get_actions_dict
from asyncflows.models.config.transform import TransformsFrom
from asyncflows.models.primitives import HintLiteral, ExecutableId

# forgive me father for I have sinned
# "I have used a global variable", says copilot
# this goes beyond mere global variables
# here is a function that transforms types, and renamespaces them to this module if they're pydantic models
# some types have recursive references, so we cache their forward references

# edit: im kind of proud of this function now that it's been refactored a bit

_forward_ref_cache = WeakValueDictionary()
_transformation_cache = {}  # TODO this could be a WeakValueDictionary too, but it complains about types being stored


def templatify_fields(
    fields: dict[str, FieldInfo],
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    add_union: type | None = None,
    strict: bool = False,
):
    new_fields = {}
    for field_name, field_ in fields.items():
        # Annotate optional fields with a default of None
        if field_.default is not PydanticUndefined:
            default = field_.default
        elif not field_.is_required():
            default = None
        else:
            default = ...
        field_type = field_.annotation

        # recurse over each field
        new_field_type = transform_and_templatify_type(
            field_type, vars_, links, add_union, strict
        )

        # add a union to the mix
        if add_union is not None:
            # raise if `add_union` collides with existing an existing field name
            # TODO should we just not add the union if it collides?
            # for field_name in type_.model_fields:
            #     if any(
            #         field_name in m.model_fields for m in typing.get_args(add_union)
            #     ):
            #         raise ValueError(f"{field_name} is a restricted field name.")
            new_field_type = Union[new_field_type, add_union]

        # keep original FieldInfo
        annotated_field_type = Annotated[new_field_type, field_]

        new_fields[field_name] = (annotated_field_type, default)

    return new_fields


def templatify_model(
    type_: type[BaseModel],
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    add_union: type | None = None,
    strict: bool = False,
):
    return templatify_fields(
        type_.model_fields,
        vars_,
        links,
        add_union,
        strict,
    )


def transform_and_templatify_type(
    type_: Any,
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    add_union: type | None = None,
    strict: bool = False,
) -> Any:  # Union[type[ConfigType], type[ImplementsTransformsInContext]]:
    # cache resolved types to avoid forward references when unnecessary
    var_string = get_var_string(vars_, strict)
    cache_key = str((type_, var_string))
    if cache_key in _transformation_cache:
        return _transformation_cache[cache_key]
    # cache ForwardRefs to avoid infinite recursion
    if cache_key in _forward_ref_cache:
        return _forward_ref_cache[cache_key]

    # determine `name` and `module`,
    # store ForwardRef if necessary
    if (
        hasattr(type_, "__name__")
        and not hasattr(type_, "__origin__")
        and type_.__module__ != "builtins"
    ):
        if inspect.isclass(type_) and issubclass(type_, BaseModel):
            name = f"{type_.__name__}_{var_string}"
            module = __name__
        else:
            name = type_.__name__
            module = type_.__module__
        _forward_ref_cache[cache_key] = typing.ForwardRef(
            arg=name,
            module=module,
        )
    else:
        name = None
        module = None

    origin = typing.get_origin(type_)
    args = typing.get_args(type_)
    if origin is types.UnionType:
        origin = Union

    # remove None from union and denote as optional
    if origin is Union and type(None) in args:
        is_optional = True
        args = tuple(arg for arg in args if arg is not type(None))
        if len(args) == 1:
            type_ = args[0]
        else:
            type_ = Union[args]  # type: ignore
    else:
        is_optional = False

    # recurse over type args if it's a type with origin
    if origin is not None:
        args = tuple(
            transform_and_templatify_type(arg, vars_, links, add_union, strict)
            for arg in args
        )
        type_ = origin[args]  # type: ignore
    # special case pydantic models
    elif inspect.isclass(type_) and issubclass(type_, BaseModel):
        fields = templatify_model(
            type_,
            vars_=vars_,
            links=links,
            add_union=add_union,
            strict=strict,
        )
        # repackage the pydantic model
        # TODO does this break anything? the module namespacing miiiight be a problem
        type_ = pydantic.create_model(
            name or type_.__name__,
            __base__=type_,
            __module__=module or __name__,
            **fields,
        )
        type_.model_rebuild()

    # resolve TransformsFrom
    if inspect.isclass(type_) and issubclass(type_, TransformsFrom):
        type_ = type_._get_config_type(
            vars_=vars_,
            links=links,
            strict=strict,
        )

    if is_optional:
        type_ = Union[type_, None]
    _transformation_cache[cache_key] = type_
    return type_


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

    # handle TransformsFrom
    if inspect.isclass(type_) and issubclass(type_, TransformsFrom):
        return build_type_qualified_name(
            type_._get_config_type(None, None), markdown=markdown
        )

    # convert string enums to a string
    if inspect.isclass(type_) and issubclass(type_, Enum):
        return " | ".join(repr(member.value) for member in type_)

    # if hasattr(type_, "title") and isinstance(type_.title, str):
    #     name = type_.title
    # else:
    name = type_.__qualname__

    # pass through names of simple and well-known types
    if type_.__module__ in ["builtins", "typing"]:
        return name

    # add markdown link to custom types
    if not markdown:
        return name

    # Building the link to the source code file
    try:
        # Get the file and line number where the type is defined
        source_file = inspect.getfile(type_)
        source_line = inspect.getsourcelines(type_)[1]

        # Construct the file URL
        source_path = os.path.abspath(source_file)
        file_url = f"file://{source_path}#L{source_line}"
        return f"[{name}]({file_url})"
    except Exception:
        # Fallback to just the type name if we can't get the source file
        return name


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


def build_input_fields(
    action: type[InternalActionBase],
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    add_union: type | None = None,
    strict: bool = False,
) -> dict[str, tuple[type, Any]]:
    inputs = action._get_inputs_type()
    if isinstance(None, inputs):
        return {}

    # generate action description
    action_title = build_action_title(action, markdown=False, title_suffix=" Input")
    action_description = build_action_description(
        action,
        markdown=False,
        include_title=False,
        include_io=False,
    )
    markdown_action_description = build_action_description(
        action,
        markdown=True,
        include_title=False,
        include_io=False,
    )

    new_field_infos = {}

    # add input description
    for field_name, field_info in inputs.model_fields.items():
        # field_title = field_name.replace("_", " ").title()
        # title = f"{field_title}: {action_title}"
        title = action_title

        field_description = build_field_description(
            field_name, field_info, markdown=False
        )
        markdown_field_description = (
            f"- {build_field_description(field_name, field_info, markdown=True)}"
        )

        description = field_description
        if action_description:
            description = action_description + "\n\n" + description
        markdown_description = markdown_field_description + "\n\n---"
        if markdown_action_description:
            markdown_description = (
                markdown_action_description + "\n\n" + markdown_description
            )

        new_field_info = FieldInfo.merge_field_infos(
            field_info,
            title=title,
            description=description,
            json_schema_extra={
                "markdownDescription": markdown_description,
            },
        )
        new_field_infos[field_name] = new_field_info

    # templatify the input fields
    return templatify_fields(new_field_infos, vars_, links, add_union, strict)


def _get_recursive_subfields(
    obj: dict | pydantic.BaseModel | Any,
    base_description: str | None,
    base_markdown_description: str | None,
    name_prefix: str = "",
) -> list[type[str]]:
    out = []
    # if isinstance(obj, dict):
    #     for name, field in obj.items():
    #         # out.append(name)
    #         out.extend(_get_recursive_subfields(field, base_description, base_markdown_description, f"{name}."))
    if inspect.isclass(obj) and issubclass(obj, pydantic.BaseModel):
        for name, field in obj.model_fields.items():
            description = build_field_description(name, field, markdown=False)
            if base_description:
                description = base_description + "\n\n" + description
            markdown_description = (
                "- " + build_field_description(name, field, markdown=True) + "\n\n---"
            )
            if base_markdown_description:
                markdown_description = (
                    base_markdown_description + "\n\n" + markdown_description
                )
            out.append(
                Annotated[
                    Literal[f"{name_prefix}{name}"],
                    Field(
                        description=description,
                        json_schema_extra={
                            "markdownDescription": markdown_description,
                        },
                    ),
                ]
            )
            out.extend(
                _get_recursive_subfields(
                    field.annotation,
                    base_description,
                    base_markdown_description,
                    name_prefix=f"{name_prefix}{name}.",
                )
            )
    return out


def build_action_title(
    action: type[InternalActionBase],
    *,
    markdown: bool,
    title_suffix: str = "",
) -> str:
    if action.readable_name:
        title = action.readable_name
    else:
        title = action.name.replace("_", " ").title()
    title += " Action"

    title = f"{title}{title_suffix}"

    if markdown:
        title = f"**{title}**"
    return title


def build_action_description(
    action: type[InternalActionBase],
    *,
    markdown: bool,
    include_title: bool = False,
    title_suffix: str = "",
    include_io: bool = True,
) -> None | str:
    description_items = []

    if include_title:
        title = build_action_title(action, markdown=markdown, title_suffix=title_suffix)
        description_items.append(title)

    # grab the main description
    if action.description:
        description_items.append(inspect.cleandoc(action.description))

    if include_io:
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
            description_items.append(
                f"{title}\n" + "\n".join(outputs_description_items)
            )

    if not description_items:
        return None
    return "\n\n".join(description_items)


def build_var_literal(
    vars_: list[str],
    strict: bool,
):
    union_elements = []

    if not strict:
        union_elements.append(str)

    if vars_:
        union_elements.append(Literal[tuple(vars_)])  # type: ignore

    if union_elements:
        return Union[tuple(union_elements)]  # type: ignore
    return str


def build_link_literal(
    action_invocations: dict[ExecutableId, type[InternalActionBase]],
    strict: bool,
) -> type[str]:
    union_elements = []

    if not strict:
        union_elements.append(str)

    actions_dict = get_actions_dict()
    unique_action_names = set(action.name for action in action_invocations.values())
    action_descriptions = {
        name: build_action_description(
            actions_dict[name],
            markdown=False,
            include_title=True,
            include_io=False,
            title_suffix=" Output",
        )
        for name in unique_action_names
    }
    markdown_action_descriptions = {
        name: build_action_description(
            actions_dict[name],
            markdown=True,
            include_title=True,
            include_io=False,
            title_suffix=" Output",
        )
        for name in unique_action_names
    }

    # if there are any models, then each recursive subfield is a var, like jsonpath
    for action_id, action in action_invocations.items():
        outputs = action._get_outputs_type()
        base_description = action_descriptions[action.name]
        base_markdown_description = markdown_action_descriptions[action.name]
        possible_links = _get_recursive_subfields(
            outputs,
            base_description,
            base_markdown_description,
            name_prefix=f"{action_id}.",
        )
        if possible_links:
            union_elements.extend(possible_links)

    if union_elements:
        return Union[tuple(union_elements)]  # type: ignore
    return str


def get_var_string(
    hint_literal: HintLiteral | None,
    strict: bool,
) -> str:
    if hint_literal is None:
        var_str = ""
    else:
        # hint_literal is a nested annotated literal union, pull out only the strings
        strings = []
        frontier = [hint_literal]
        while frontier:
            arg = frontier.pop()
            if isinstance(arg, str):
                strings.append(arg)
            elif hasattr(arg, "__args__"):
                frontier.extend(arg.__args__)  # type: ignore

        var_str = "".join(strings)
    if strict:
        var_str = var_str + "__strict"
    return var_str

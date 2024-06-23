import inspect
import typing
from typing import Any, Annotated, Literal, Union, Type

import pydantic
from pydantic import Field, ConfigDict

from pydantic.fields import FieldInfo

from asyncflows.models.config.action import (
    InternalActionBase,
    ActionInvocation,
    ActionMeta,
)
from asyncflows.models.config.value_declarations import (
    ValueDeclaration,
    VarDeclaration,
    LinkDeclaration,
)
from asyncflows.models.io import Inputs, Outputs, DefaultOutputOutputs
from asyncflows.models.primitives import HintLiteral, ExecutableId, ExecutableName
from asyncflows.utils.type_utils import build_field_description, templatify_fields


def build_input_fields(
    action: type[InternalActionBase[Inputs, Outputs]],
    *,
    vars_: HintLiteral | None,
    links: HintLiteral | None,
    add_union: type | None,
    strict: bool,
    include_paths: bool,
    action_invocation: ActionInvocation | None = None,
) -> dict[str, tuple[type, Any]]:
    inputs_type = action._get_inputs_type()
    if issubclass(inputs_type, type(None)):
        return {}

    # generate action description
    action_title = build_action_title(action, markdown=False, title_suffix=" Input")
    action_description = build_action_description(
        action,
        action_invocation=action_invocation,
        markdown=False,
        include_title=False,
        include_io=False,
        include_paths=include_paths,
    )
    markdown_action_description = build_action_description(
        action,
        action_invocation=action_invocation,
        markdown=True,
        include_title=False,
        include_io=False,
        include_paths=include_paths,
    )

    new_field_infos = {}

    # add input description
    for field_name, field_info in inputs_type.model_fields.items():
        # field_title = field_name.replace("_", " ").title()
        # title = f"{field_title}: {action_title}"

        title = action_title

        field_description = build_field_description(
            field_name, field_info, markdown=False, include_paths=include_paths
        )
        markdown_field_description = f"- {build_field_description(field_name, field_info, markdown=True, include_paths=include_paths)}"

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
    include_paths: bool,
    name_prefix: str = "",
) -> list[type[str]]:
    out = []
    # if isinstance(obj, dict):
    #     for name, field in obj.items():
    #         # out.append(name)
    #         out.extend(_get_recursive_subfields(field, base_description, base_markdown_description, f"{name}."))
    if inspect.isclass(obj) and issubclass(obj, pydantic.BaseModel):
        for name, field in obj.model_fields.items():
            annotated_field = _build_annotated_field(
                base_description=base_description,
                base_markdown_description=base_markdown_description,
                field=field,
                include_paths=include_paths,
                name=name,
                name_prefix=name_prefix,
            )
            out.append(annotated_field)
            out.extend(
                _get_recursive_subfields(
                    field.annotation,
                    base_description,
                    base_markdown_description,
                    include_paths=include_paths,
                    name_prefix=f"{name_prefix}{name}.",
                )
            )
    return out


def _build_annotated_field(
    base_description: str | None,
    base_markdown_description: str | None,
    field: FieldInfo,
    include_paths: bool,
    name: str,
    alias_name: str | None = None,
    name_prefix: str = "",
):
    if alias_name is None:
        alias_name = name
    description = build_field_description(
        name, field, markdown=False, include_paths=include_paths
    )
    if base_description:
        description = base_description + "\n\n" + description
    markdown_description = (
        "- "
        + build_field_description(
            name, field, markdown=True, include_paths=include_paths
        )
        + "\n\n---"
    )
    if base_markdown_description:
        markdown_description = base_markdown_description + "\n\n" + markdown_description
    annotated_field = Annotated[
        Literal[f"{name_prefix}{alias_name}"],
        Field(
            description=description,
            json_schema_extra={
                "markdownDescription": markdown_description,
            },
        ),
    ]
    return annotated_field


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
    action: type[InternalActionBase[Inputs, Outputs]],
    *,
    markdown: bool,
    include_paths: bool,
    action_invocation: ActionInvocation | None = None,
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
        inputs_type = action._get_inputs_type()
        if not issubclass(inputs_type, type(None)):
            for field_name, field_info in inputs_type.model_fields.items():
                inputs_description_items.append(
                    f"- {build_field_description(field_name, field_info, markdown=markdown, include_paths=include_paths)}"
                )
        if inputs_description_items:
            if markdown:
                title = "**Inputs**"
            else:
                title = "INPUTS"
            description_items.append(f"{title}\n" + "\n".join(inputs_description_items))

        # add outputs description
        outputs_description_items = []
        outputs_type = action._get_outputs_type(action_invocation)
        if not issubclass(outputs_type, type(None)):
            for field_name, field_info in outputs_type.model_fields.items():
                outputs_description_items.append(
                    f"- {build_field_description(field_name, field_info, markdown=markdown, include_paths=include_paths)}"
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


def build_link_literal(
    action_invocations: dict[ExecutableId, ActionInvocation],
    strict: bool,
    include_paths: bool,
) -> type[str]:
    union_elements = []

    if not strict:
        union_elements.append(str)

    actions_dict = get_actions_dict()

    # if there are any models, then each recursive subfield is a var, like jsonpath
    for action_id, action_invocation in action_invocations.items():
        action_type = actions_dict[action_invocation.action]
        outputs_type = action_type._get_outputs_type(action_invocation)
        base_description = build_action_description(
            action_type,
            action_invocation=action_invocation,
            markdown=False,
            include_title=True,
            include_io=False,
            include_paths=include_paths,
            title_suffix=" Output",
        )
        base_markdown_description = build_action_description(
            action_type,
            action_invocation=action_invocation,
            markdown=True,
            include_title=True,
            include_io=False,
            include_paths=include_paths,
            title_suffix=" Output",
        )
        if issubclass(outputs_type, DefaultOutputOutputs):
            output_attr = outputs_type._default_output
            field = outputs_type.model_fields[output_attr]
            annotated_field = _build_annotated_field(
                base_description=base_description,
                base_markdown_description=base_markdown_description,
                field=field,
                include_paths=include_paths,
                name=output_attr,
                alias_name=action_id,
            )
            union_elements.append(annotated_field)

        possible_links = _get_recursive_subfields(
            outputs_type,
            base_description,
            base_markdown_description,
            include_paths=include_paths,
            name_prefix=f"{action_id}.",
        )
        if possible_links:
            union_elements.extend(possible_links)

    if union_elements:
        return Union[tuple(union_elements)]  # type: ignore
    return str


def build_hinted_value_declaration(
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    strict: bool = False,
    excluded_declaration_types: None | list[type[ValueDeclaration]] = None,
) -> type[ValueDeclaration]:
    if excluded_declaration_types is None:
        excluded_declaration_types = []

    union_elements = []

    if vars_:
        union_elements.append(
            VarDeclaration.from_hint_literal(vars_, strict),
        )
    if (not vars_ or not strict) and VarDeclaration not in excluded_declaration_types:
        union_elements.append(VarDeclaration)

    if links:
        union_elements.append(
            LinkDeclaration.from_hint_literal(links, strict),
        )
    if (not links or not strict) and LinkDeclaration not in excluded_declaration_types:
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
    include_paths: bool = False,
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

        title = build_action_title(action, markdown=False)

        description = build_action_description(
            action, markdown=False, include_paths=include_paths
        )
        markdown_description = build_action_description(
            action, markdown=True, include_paths=include_paths
        )

        # build action literal
        action_literal = Literal[action.name]  # type: ignore

        # add title
        action_literal = Annotated[
            action_literal,
            Field(
                title=title,
            ),
        ]

        # add description
        if description is not None:
            action_literal = Annotated[
                action_literal,
                Field(
                    description=description,
                    json_schema_extra={
                        "markdownDescription": markdown_description + "\n\n---",
                    }
                    if markdown_description is not None
                    else None,
                ),
            ]

        # build base model field
        fields = {
            "action": (action_literal, ...),
            "cache_key": (None | str | HintedValueDeclaration, None),
        }

        # build input fields
        fields |= build_input_fields(
            action,
            vars_=vars_,
            links=links,
            add_union=HintedValueDeclaration,
            strict=strict,
            include_paths=include_paths,
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


def recursive_import(package_name):
    import pkgutil
    import importlib

    package = importlib.import_module(package_name)
    if not hasattr(package, "__path__"):
        print(f"Package {package_name} has no __path__ attribute")
        raise ImportError
    for _, module_name, is_pkg in pkgutil.walk_packages(
        package.__path__, package.__name__ + "."
    ):
        try:
            importlib.import_module(module_name)
            if is_pkg:
                recursive_import(module_name)
        except ImportError as e:
            print(f"Failed to import {module_name}: {e}")


_processed_entrypoints = set()


def get_actions_dict(
    entrypoint_whitelist: list[str] | None = None,
) -> dict[ExecutableName, Type[InternalActionBase[Any, Any]]]:
    import importlib_metadata

    # import all action entrypoints, including `asyncflows.actions` and other installed packages
    entrypoints = importlib_metadata.entry_points(group="asyncflows")
    for entrypoint in entrypoints.select(name="actions"):
        dist_name = entrypoint.dist.name
        if dist_name in _processed_entrypoints or (
            entrypoint_whitelist is not None and dist_name not in entrypoint_whitelist
        ):
            continue
        _processed_entrypoints.add(dist_name)
        try:
            recursive_import(entrypoint.value)
        except Exception as e:
            print(f"Failed to import {dist_name} entrypoint: {e}")

    # return all subclasses of Action as registered in the metaclass
    return ActionMeta.actions_registry

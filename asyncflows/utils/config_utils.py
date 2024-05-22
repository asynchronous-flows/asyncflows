import ast
import builtins
import os
import types
import typing
from typing import Optional, Any, Union

import pydantic
import yaml
from pydantic import BaseModel, ConfigDict, Field

from asyncflows.models.config.transform import resolve_transforms_from
from asyncflows.models.primitives import HintType
from asyncflows.utils.type_utils import filter_none_from_type


def is_subclass_of_basemodel(type_) -> typing.TypeGuard[type[BaseModel]]:
    # 3.11 doesn't need this special case,
    # but in 3.10 `issubclass(type_, BaseModel)` throws on GenericAlias-likes
    origin_type = typing.get_origin(type_)
    if origin_type is not None:
        type_ = origin_type
    return isinstance(type_, type) and issubclass(type_, BaseModel)


def templatify_model(
    model: type[BaseModel],
    vars_: HintType | None,
    links: HintType | None,
    add_union: Optional[type] = None,
    strict: bool = False,
) -> dict[str, tuple[type, Any]]:
    # Create a new model, put in a field of "field_type" for each input
    template_fields = {}
    for name_, field_ in model.model_fields.items():
        # Get the type of the field, which may be different in context than in the action
        # TODO i think if you pass SQLModel objects in it breaks on config parse
        type_ = field_.annotation

        type_ = resolve_transforms_from(type_, vars_, links, strict)

        is_none_union = False
        if typing.get_origin(type_) in [Union, types.UnionType]:
            # filter out None from the union
            args = typing.get_args(type_)
            if type(None) in args:
                type_ = filter_none_from_type(type_)
                is_none_union = True

        # templatify subfields
        if is_subclass_of_basemodel(type_):
            subfields = templatify_model(
                type_,
                vars_=vars_,
                links=links,
                add_union=add_union,
                strict=strict,
            )
            type_ = pydantic.create_model(
                type_.__name__ + "ActionFieldTemplate",
                __base__=type_,
                __module__=__name__,
                model_config=ConfigDict(
                    arbitrary_types_allowed=True,
                ),
                **subfields,  # pyright: ignore[reportGeneralTypeIssues]
            )

        if is_none_union:
            type_ = Union[type_, None]

        # Annotate optional fields with a default of None
        kwargs = {}
        if not field_.is_required() or (
            add_union is not None and isinstance(None, add_union)
        ):
            kwargs["default"] = None
        if field_.alias is not None:
            kwargs["alias"] = field_.alias
        # else:
        #     default = ...
        if not kwargs:
            template_field = ...
        else:
            template_field = Field(
                # alias=field_.alias,
                # default=default,
                **kwargs
            )
        if add_union is not None:
            # check that union does not collide with existing type
            collides = False
            if (
                isinstance(type_, type)
                and typing.get_origin(type_) is None
                and issubclass(type_, pydantic.BaseModel)
            ):
                for field_name in type_.model_fields:
                    if any(
                        field_name in m.__fields__ for m in typing.get_args(add_union)
                    ):
                        # raise ValueError(f"{field_name} is a restricted field name.")
                        collides = True
            # TODO if it's a template, enforce dict structure on the template
            if not collides:
                type_ = Union[type_, add_union]
        template_fields[name_] = (type_, template_field)
    # inputs_template = pydantic.create_model(
    #     action.name + model.__name__ + "ActionFieldTemplate",
    #     __base__=StrictModel,
    #     __module__=__name__,
    #     **template_fields,
    # )
    # inputs_template.update_forward_refs()
    #
    # # Annotate with a good default for the inputs themselves,
    # # given if any of the inputs are required
    # if not all_optional and any(
    #     f.is_required() for f in model.model_fields.values()
    # ):
    #     default = ...
    # else:
    #     default = {}

    return template_fields


# def construct_optional_config(model: type[BaseModel]) -> type[BaseModel]:
#     return pydantic.create_model(
#         "Optional" + model.__name__,
#         __base__=model,
#         __module__=__name__,
#         model_config=ConfigDict(
#             arbitrary_types_allowed=True,
#         ),
#         **templatify_model(
#             model,
#             vars_=None,
#             add_union=type(None),
#         ),
#     )


def get_names_from_ast(node: ast.AST, ignore_vars: None | frozenset = None) -> set:
    if ignore_vars is None:
        ignore_vars = frozenset()
    names = set()
    if isinstance(node, ast.Name):
        if node.id not in ignore_vars and node.id not in builtins.__dict__:
            names.add(node.id)
    elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
        new_ignore_vars = ignore_vars
        for gen in node.generators:
            # The 'target' introduces loop variables, add them to ignore list
            loop_vars = {n.id for n in ast.walk(gen.target) if isinstance(n, ast.Name)}
            new_ignore_vars |= loop_vars

            # Process 'iter' part which can include external dependencies
            names |= get_names_from_ast(gen.iter, new_ignore_vars)

            # Comprehensions can be nested, so handle 'ifs'
            for if_clause in gen.ifs:
                names |= get_names_from_ast(if_clause, new_ignore_vars)
    else:
        for child in ast.iter_child_nodes(node):
            names |= get_names_from_ast(child, ignore_vars)
    return names


def extract_attribute_path(node: ast.AST) -> str:
    """Helper function to correctly build the attribute path."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def get_full_paths_from_ast(node: ast.AST, ignore_vars: None | frozenset = None) -> set:
    if ignore_vars is None:
        ignore_vars = frozenset()
    paths = set()

    if isinstance(node, ast.Name):
        if node.id not in ignore_vars:
            paths.add(node.id)
    elif isinstance(node, ast.Attribute):
        full_path = extract_attribute_path(node)
        # Include the full path if the base variable is not ignored
        base_var = full_path.split(".")[0]
        if base_var not in ignore_vars:
            paths.add(full_path)
    elif isinstance(node, (ast.ListComp, ast.DictComp)):
        for gen in node.generators:
            loop_vars = {n.id for n in ast.walk(gen.target) if isinstance(n, ast.Name)}
            new_ignore_vars = ignore_vars | loop_vars

            paths |= get_full_paths_from_ast(gen.iter, new_ignore_vars)

            for if_clause in gen.ifs:
                paths |= get_full_paths_from_ast(if_clause, new_ignore_vars)
    else:
        for child in ast.iter_child_nodes(node):
            paths |= get_full_paths_from_ast(child, ignore_vars)

    return paths


_allowed_ast_types = (
    ast.Module,
    ast.Expr,
    ast.Constant,
    ast.Name,
    ast.Attribute,
    ast.Load,
    ast.Store,
    ast.ListComp,
    ast.comprehension,
    ast.List,
    ast.Subscript,
    ast.Tuple,
    ast.BinOp,
    ast.Add,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Call,
)


def verify_ast(node: ast.AST):
    if not isinstance(node, _allowed_ast_types):
        raise ValueError(f"Unexpected AST type: {type(node)}")
    for child in ast.iter_child_nodes(node):
        verify_ast(child)


def collect_ast_types(node: ast.AST) -> set[type]:
    types = set()
    if isinstance(node, _allowed_ast_types):
        types.add(type(node))
        for child in ast.iter_child_nodes(node):
            types |= collect_ast_types(child)
    return types


T = typing.TypeVar("T", bound=BaseModel)


def load_config_text(model: type[T], config_text: str) -> T:
    return model.model_validate(yaml.safe_load(config_text))


def load_config_file(model: type[T], filename: str) -> T:
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Could not find {filename}")

    with open(filename, "r") as f:
        return model.model_validate(yaml.safe_load(f))

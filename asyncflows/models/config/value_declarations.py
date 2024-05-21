import ast
import os
from typing import Any, Union

import pydantic
import simpleeval
from pydantic import Field
from typing_extensions import Self

from asyncflows.models.config.common import (
    StrictModel,
    extract_root_var,
    render_var,
    extract_vars_from_template,
    render_template,
)
from asyncflows.models.primitives import (
    ContextVarPath,
    LambdaString,
    TemplateString,
    ContextVarName,
    HintType,
)
from asyncflows.utils.config_utils import get_names_from_ast, verify_ast
from asyncflows.utils.type_utils import get_var_string, get_path_literal


###
### Variables
###


class Declaration(StrictModel):
    stream: bool = False

    def get_dependencies(self) -> set[ContextVarName]:
        raise NotImplementedError

    async def render(self, context: dict[str, Any]) -> Any:
        raise NotImplementedError

    @classmethod
    def from_vars(cls, vars_: HintType, strict: bool) -> type[Self]:
        return cls


class TextDeclaration(Declaration):
    """
    A template declaration is a string that can be rendered within a context.
    """

    text: TemplateString

    def get_dependencies(self) -> set[ContextVarName]:
        return extract_vars_from_template(self.text)

    async def render(self, context: dict[str, Any]) -> Any:
        rendered = await render_template(self.text, context)
        if not rendered:
            return ""
        return str(rendered)


class VarDeclaration(Declaration):
    """
    A variable declaration is a string that references a variable (or path to nested variable) in the context.
    """

    var: ContextVarPath

    def get_dependencies(self) -> set[ContextVarName]:
        id_ = extract_root_var(self.var)
        return {id_}

    async def render(self, context: dict[str, Any]) -> Any:
        return await render_var(self.var, context)

    @classmethod
    def from_vars(cls, vars_: HintType, strict: bool) -> type[Self]:
        var_type = get_path_literal(vars_, strict)
        varstr = get_var_string(vars_, strict)
        field_infos = cls.model_fields.copy()
        fields: dict[str, tuple] = {
            var: (info.annotation, info) for var, info in field_infos.items()
        }
        fields["var"] = (var_type, ...)
        return pydantic.create_model(  # type: ignore
            f"{cls.__name__}_{varstr}",
            __base__=cls,
            __module__=__name__,
            **fields,  # type: ignore
        )


class LinkDeclaration(Declaration):
    """
    An link declaration is a string that references another action's output
    """

    link: ContextVarPath

    def get_dependencies(self) -> set[ContextVarName]:
        id_ = extract_root_var(self.link)
        return {id_}

    async def render(self, context: dict[str, Any]) -> Any:
        return await render_var(self.link, context)

    @classmethod
    def from_vars(cls, vars_: HintType, strict: bool) -> type[Self]:
        var_type = get_path_literal(vars_, strict)
        varstr = get_var_string(vars_, strict)
        field_infos = cls.model_fields.copy()
        fields: dict[str, tuple] = {
            var: (info.annotation, info) for var, info in field_infos.items()
        }
        fields["link"] = (var_type, ...)
        return pydantic.create_model(  # type: ignore
            f"{cls.__name__}_{varstr}",
            __base__=cls,
            __module__=__name__,
            **fields,  # type: ignore
        )


class EnvDeclaration(Declaration):
    """
    An env declaration is a string that references an environment variable.
    """

    env: str

    def get_dependencies(self) -> set[ContextVarName]:
        return set()

    async def render(self, context: dict[str, Any]) -> Any:
        if self.env not in os.environ:
            raise ValueError(f"Environment variable not found: {self.env}")
        return os.environ[self.env]


# class ConstDeclaration(Variable):
#     """
#     A constant declaration is a string that is interpreted as a constant value.
#     """
#     const: Any
#
#     def render(self, context: ContextDict):
#         return self.const


class LambdaDeclaration(Declaration):
    """
    A lambda declaration is a python expression that can be evaluated within a context.
    """

    lambda_: LambdaString = Field(alias="lambda")

    def get_dependencies(self) -> set[ContextVarName]:
        parsed_code = ast.parse(self.lambda_, mode="eval")
        return get_names_from_ast(parsed_code)

    async def render(self, context: dict[str, Any]) -> Any:
        verify_ast(ast.parse(self.lambda_))

        evaluator = simpleeval.EvalWithCompoundTypes(
            names=context,
            functions={
                "range": range,
            },
        )
        return evaluator.eval(self.lambda_)


ValueDeclaration = Union[
    TextDeclaration,
    VarDeclaration,
    LinkDeclaration,
    EnvDeclaration,
    # ConstDeclaration,
    LambdaDeclaration,
    # ParamDeclaration,
]

EvaluableDeclaration = Union[
    VarDeclaration,
    LambdaDeclaration,
]

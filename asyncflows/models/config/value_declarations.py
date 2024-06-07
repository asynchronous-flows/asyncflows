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
    HintLiteral,
)
from asyncflows.utils.config_utils import get_names_from_ast, verify_ast
from asyncflows.utils.type_utils import get_var_string


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
    def from_hint_literal(cls, hint_literal: HintLiteral, strict: bool) -> type[Self]:
        return cls


class TextDeclaration(Declaration):
    text: TemplateString = Field(
        description="""
A template declaration is a jinja2 template, rendered within the context of the flow and any provided variables.
If you reference an action's output, it will ensure that action runs before this one.

For more information, see the Jinja2 documentation: https://jinja.palletsprojects.com/en/3.0.x/templates/.
""",
        json_schema_extra={
            "markdownDescription": """
A template declaration is a jinja2 template, rendered within the context of the flow and any provided variables.  
If you reference an action's output, it will ensure that action runs before this one.

Reference variables or action outputs like: 

> ```yaml
> text: |
> ```
> ```jinja
>   Hi {{ name }}, the output of action_id is {{ action_id.output_name }}
> ```

It also supports advanced features such as loops and conditionals:

> ```yaml
> text: |
> ```
> ```jinja
>   {% for item in items -%}
>     {% if item.name != 'foo' -%}
>     {{ item.name }}: {{ item.value }}
>     {% endif %}
>   {% endfor %}
> ```

For more information, see the [Jinja2 documentation](https://jinja.palletsprojects.com/en/3.0.x/templates/).
"""
        },
    )

    def get_dependencies(self) -> set[ContextVarName]:
        return extract_vars_from_template(self.text)

    async def render(self, context: dict[str, Any]) -> Any:
        rendered = await render_template(self.text, context)
        if not rendered:
            return ""
        return str(rendered)


class VarDeclaration(Declaration):
    var: ContextVarPath = Field(
        description="A variable declaration references a variable (or path to nested variable) in the context."
    )

    def get_dependencies(self) -> set[ContextVarName]:
        id_ = extract_root_var(self.var)
        return {id_}

    async def render(self, context: dict[str, Any]) -> Any:
        return await render_var(self.var, context)

    @classmethod
    def from_hint_literal(cls, hint_literal: HintLiteral, strict: bool) -> type[Self]:
        varstr = get_var_string(hint_literal, strict)
        field_infos = cls.model_fields.copy()
        fields: dict[str, tuple] = {
            var: (info.annotation, info) for var, info in field_infos.items()
        }
        fields["var"] = (hint_literal, ...)
        return pydantic.create_model(  # type: ignore
            f"{cls.__name__}_{varstr}",
            __base__=cls,
            __module__=__name__,
            **fields,  # type: ignore
        )


class LinkDeclaration(Declaration):
    link: ContextVarPath = Field(
        description="A link declaration references another action's output, and ensures that action runs before this one."
    )

    def get_dependencies(self) -> set[ContextVarName]:
        id_ = extract_root_var(self.link)
        return {id_}

    async def render(self, context: dict[str, Any]) -> Any:
        return await render_var(self.link, context)

    @classmethod
    def from_hint_literal(cls, hint_literal: HintLiteral, strict: bool) -> type[Self]:
        varstr = get_var_string(hint_literal, strict)
        field_infos = cls.model_fields.copy()
        fields: dict[str, tuple] = {
            var: (info.annotation, info) for var, info in field_infos.items()
        }
        fields["link"] = (hint_literal, ...)
        return pydantic.create_model(  # type: ignore
            f"{cls.__name__}_{varstr}",
            __base__=cls,
            __module__=__name__,
            **fields,  # type: ignore
        )


class EnvDeclaration(Declaration):
    env: str = Field(
        description="An environment declaration references the name of an environment variable that is loaded during runtime."
    )

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
    lambda_: LambdaString = Field(
        alias="lambda",
        description="""
A lambda declaration is a python expression evaluated within the context of the flow and any provided variables.
If you reference an action's output, it will ensure that action runs before this one.
""",
        json_schema_extra={
            "markdownDescription": """
A lambda declaration is a python expression evaluated within the context of the flow and any provided variables.  
If you reference an action's output, it will ensure that action runs before this one.

Reference variables or action outputs like:

> ```yaml
> lambda: |
> ```
> ```python
>   "My name is " + name + ". The output of action_id is " + action_id.output_name
> ```

You can also use list comprehension and conditionals:

> ```yaml
> lambda: |
> ```
> ```python
>   [item for item in items if item.name != 'foo']
> ```
""",
        },
    )

    def get_dependencies(self) -> set[ContextVarName]:
        parsed_code = ast.parse(self.lambda_, mode="eval")
        return get_names_from_ast(parsed_code)

    async def render(self, context: dict[str, Any]) -> Any:
        verify_ast(ast.parse(self.lambda_))

        simpleeval.MAX_COMPREHENSION_LENGTH = 9999999999999

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

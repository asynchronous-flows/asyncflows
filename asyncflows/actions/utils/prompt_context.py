import enum
import typing
from typing import Union, Any, Literal
from typing_extensions import assert_never

import structlog.stdlib
from pydantic import ConfigDict

from asyncflows import Field
from asyncflows.models.config.common import StrictModel
from asyncflows.models.config.transform import (
    TransformsInto,
    TransformsFrom,
)
from asyncflows.models.config.value_declarations import (
    VarDeclaration,
    TextDeclaration,
    LambdaDeclaration,
    Declaration,
    LinkDeclaration,
    # ConstDeclaration,
)
from asyncflows.models.primitives import TemplateString, HintLiteral


class QuoteStyle(enum.Enum):
    BACKTICKS = "backticks"
    XML = "xml"


class PromptElementBase(StrictModel):
    def as_string(
        self,
        quote_style: QuoteStyle = QuoteStyle.XML,
    ):
        raise NotImplementedError()


class RoleElement(PromptElementBase):
    role: Literal["user", "system", "assistant"]

    def as_string(
        self,
        quote_style: QuoteStyle = QuoteStyle.XML,
    ):
        raise RuntimeError("RoleElement cannot be converted to a string.")


class TextElement(PromptElementBase):
    # copy the documentation from TextDeclaration.text
    # can't inherit TextDeclaration or the object will turn into a string by action_service
    # TODO explore compositional methods for this instead of inheritance?
    text: TemplateString = TextDeclaration.model_fields["text"]  # type: ignore
    role: Literal["user", "system", "assistant"] | None = None

    def as_string(
        self,
        quote_style: QuoteStyle = QuoteStyle.XML,
    ):
        return self.text


class ContextElement(PromptElementBase, TransformsFrom):
    """
    A single entry in the context heading dict
    """

    model_config = ConfigDict(
        coerce_numbers_to_str=True,
    )

    value: str
    heading: str

    @classmethod
    def _get_config_type(
        cls,
        vars_: HintLiteral | None,
        links: HintLiteral | None,
        strict: bool = False,
    ) -> type["PromptContextInConfig"]:
        union_elements = []

        if vars_:
            union_elements.append(
                ContextVar.from_hint_literal(vars_, strict),
            )
        if not vars_ or not strict:
            union_elements.append(ContextVar)

        if links:
            union_elements.append(
                ContextLink.from_hint_literal(links, strict),
            )
        if not links or not strict:
            union_elements.append(ContextLink)

        other_elements = [
            element
            for element in typing.get_args(PromptContextInConfig)
            if element not in (ContextVar, ContextLink)
        ]
        union_elements.extend(other_elements)

        return Union[tuple(union_elements)]  # type: ignore

        # TODO reimplement `strict` parameter
        # prompt_context_union_members = tuple(
        #     arg
        #     for arg in typing.get_args(PromptContextInConfig)
        #     if arg != PromptContextInConfigVar
        # )
        # return Union[HintedPromptContextInConfigVar, *prompt_context_union_members]  # type: ignore

    def as_string(
        self,
        quote_style: QuoteStyle = QuoteStyle.XML,
    ):
        """
        Format the context as a string.

        Parameters
        ----------

        variable_headings
            A dictionary mapping context keys to headings.
            If not provided, the keys will be used as headings.
        quote_style
            The style of quotes to use. Defaults to XML-style quotes.
        """
        # Format the value as a string
        # if isinstance(self.value, list):
        #     valstr = "\n".join(str(item) for item in self.value)
        # else:
        valstr = str(self.value)

        if quote_style == QuoteStyle.BACKTICKS:
            return f"""{self.heading}:
```
{valstr}
```"""
        elif quote_style == QuoteStyle.XML:
            return f"""<{self.heading}>
{valstr}
</{self.heading}>"""
        else:
            assert_never(quote_style)


PromptElement = Union[
    RoleElement,
    TextElement,
    ContextElement,
]


###
# Config representation
###


class PromptContextInConfigBase(Declaration, TransformsInto[ContextElement]):
    """
    A base class for prompt context in config.
    """

    heading: TemplateString = Field(
        description="The heading for the context element.",
        json_schema_extra={
            "markdownDescription": """
The heading for the context element.

If `quote_style` is set to `backticks`, the heading will be wrapped in backticks, according to the following jinja template:    

> ~~~jinja
> {{ heading }}
> ```
> {{ value }}
> ```
> ~~~


If `quote_style` is set to `xml`, the heading will be wrapped in XML tags, according to the following jinja template:

> ```jinja
> <{{ heading }}>
> {{ value }}
> </{{ heading }}>
> ```

""",
        },
    )

    async def transform_from_config(
        self, log: structlog.stdlib.BoundLogger, context: dict[str, Any]
    ) -> ContextElement:
        return ContextElement(
            value=await self.render(context),
            heading=await TextDeclaration(
                text=self.heading,
            ).render(context),
        )


class ContextVar(PromptContextInConfigBase, VarDeclaration):
    """
    A variable declaration for prompt context in config.
    """


class ContextLink(PromptContextInConfigBase, LinkDeclaration):
    """
    An input declaration for prompt context in config.
    """


class ContextTemplate(PromptContextInConfigBase, TextDeclaration):
    """
    A template string for prompt context in config.
    """


class ContextLambda(PromptContextInConfigBase, LambdaDeclaration):
    """
    A lambda declaration for prompt context in config.
    """


# class PromptContextInConfigConst(PromptContextInConfigBase, ConstDeclaration):
#     """
#     A constant declaration for prompt context in config.
#     """


PromptContextInConfig = Union[
    ContextVar,
    ContextTemplate,
    ContextLink,
    ContextLambda,
    # PromptContextInConfigConst,
]

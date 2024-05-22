import enum
import typing
from typing import Union, Any, Literal
from typing_extensions import assert_never

import structlog.stdlib
from pydantic import ConfigDict

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
from asyncflows.models.primitives import TemplateString, HintType


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
    text: str
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
        vars_: HintType | None,
        links: HintType | None,
        strict: bool = False,
    ) -> type["PromptContextInConfig"]:
        union_elements = []

        if vars_:
            union_elements.append(
                PromptContextInConfigVar.from_vars(vars_, strict),
            )
        if not vars_ or not strict:
            union_elements.append(PromptContextInConfigVar)

        if links:
            union_elements.append(
                PromptContextInConfigLink.from_vars(links, strict),
            )
        if not links or not strict:
            union_elements.append(PromptContextInConfigLink)

        other_elements = [
            element
            for element in typing.get_args(PromptContextInConfig)
            if element not in (PromptContextInConfigVar, PromptContextInConfigLink)
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

    heading: TemplateString

    async def transform_from_config(
        self, log: structlog.stdlib.BoundLogger, context: dict[str, Any]
    ) -> ContextElement:
        return ContextElement(
            value=await self.render(context),
            heading=await TextDeclaration(
                text=self.heading,
            ).render(context),
        )


class PromptContextInConfigVar(PromptContextInConfigBase, VarDeclaration):
    """
    A variable declaration for prompt context in config.
    """


class PromptContextInConfigLink(PromptContextInConfigBase, LinkDeclaration):
    """
    An input declaration for prompt context in config.
    """


class PromptContextInConfigTemplate(PromptContextInConfigBase, TextDeclaration):
    """
    A template string for prompt context in config.
    """


class PromptContextInConfigLambda(PromptContextInConfigBase, LambdaDeclaration):
    """
    A lambda declaration for prompt context in config.
    """


# class PromptContextInConfigConst(PromptContextInConfigBase, ConstDeclaration):
#     """
#     A constant declaration for prompt context in config.
#     """


PromptContextInConfig = Union[
    PromptContextInConfigVar,
    PromptContextInConfigTemplate,
    PromptContextInConfigLink,
    PromptContextInConfigLambda,
    # PromptContextInConfigConst,
]

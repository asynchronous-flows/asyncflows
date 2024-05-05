from typing import Any, TypeVar, Generic

import jinja2
import jinja2.nativetypes
import jinja2.meta
import numpy as np
import pydantic
from pydantic import ConfigDict

from asyncflows.models.primitives import ContextVarName, ContextVarPath, TemplateString
from asyncflows.utils.jinja_utils import NativeEnvironment


class StrictModel(pydantic.BaseModel):
    model_config = ConfigDict(
        extra=pydantic.Extra.forbid,
    )


OptionT = TypeVar("OptionT")


class Option(StrictModel, Generic[OptionT]):
    option: OptionT
    weight: float = 1.0


# Use this to simulate the action/workflow invocation models in config
class ExtraModel(pydantic.BaseModel):
    model_config = ConfigDict(
        extra=pydantic.Extra.allow,
    )


def extract_root_var(var: ContextVarPath) -> ContextVarName:
    # TODO use a library like jsonpath_ng here instead, tho we shouldn't support [*] i think
    return var.split(".")[0]


_jinja_env = NativeEnvironment(
    extensions=["jinja2.ext.loopcontrols"],
    enable_async=True,
)


def extract_vars_from_template(text: TemplateString) -> set[ContextVarName]:
    # this should only pull out the root variables (e.g., `d.split('.')[0]`)
    parsed_text = _jinja_env.parse(text)
    vars = jinja2.meta.find_undeclared_variables(parsed_text)
    return {var for var in vars if var != "_"}


def extract_from_options(options: str | list[str | Option[str]]) -> set[ContextVarName]:
    if isinstance(options, list):
        pure_strings = [m.option if isinstance(m, Option) else m for m in options]
    else:
        pure_strings = [options]

    return set.union(*[extract_vars_from_template(m) for m in pure_strings])


def randomly_pick_option(options: OptionT | list[OptionT | Option[OptionT]]) -> OptionT:
    if not isinstance(options, list):
        return options

    pure_options = [m if isinstance(m, Option) else Option(option=m) for m in options]

    total_weight = sum(option.weight for option in pure_options)
    probabilities = [option.weight / total_weight for option in pure_options]
    chosen_option_i = np.random.choice(len(pure_options), p=probabilities)
    chosen_option = pure_options[chosen_option_i]

    # FIXME why does pyright not like this?
    return chosen_option.option  # type: ignore


async def render_var(
    var: ContextVarPath,
    context: dict[ContextVarName, Any],
) -> Any:
    return await render_template(f"{{{{ {var} }}}}", context)


async def render_template(
    template_string: TemplateString,
    context: dict[ContextVarName, Any],
) -> Any:
    # TODO make rendering jinja2 async
    template = _jinja_env.from_string(template_string)
    return await template.render_async(context)

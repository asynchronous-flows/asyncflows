import inspect
import typing
import structlog
from typing import ClassVar, Type, Any, Optional, TypeVar, Generic, AsyncIterator

from pydantic import Field

from asyncflows.models.config.common import ExtraModel
from asyncflows.models.config.value_declarations import (
    ValueDeclaration,
)
from asyncflows.models.io import Inputs, Outputs
from asyncflows.models.primitives import ExecutableName
from asyncflows.utils.request_utils import request_text, request_read


class ActionInvocation(ExtraModel):
    action: ExecutableName
    cache_key: None | str | ValueDeclaration = Field(
        None,
        description="The cache key for this action's result. Should be unique among all actions.",
    )


class ActionMeta(type):
    """
    Metaclass for actions.
    Its only responsibility is to register actions in a global registry.
    """

    actions_registry: dict[ExecutableName, Type["InternalActionBase"]] = {}

    def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        cls = super().__new__(mcs, name, bases, attrs)
        if name in ("InternalActionBase", "Action", "StreamingAction"):
            return cls
        if not hasattr(cls, "name"):
            raise ValueError(
                f"Action `{cls.__name__}` does not specify `name` class variable"
            )
        action_name = getattr(cls, "name")
        if action_name in mcs.actions_registry and not mcs.is_same_class(
            cls, mcs.actions_registry[action_name]
        ):
            raise ValueError(
                f"Action `{cls.__name__}` has duplicate name `{action_name}`"
            )
        if issubclass(cls, InternalActionBase):
            mcs.actions_registry[action_name] = cls
        return cls

    @staticmethod
    def is_same_class(cls1, cls2):
        return (
            inspect.getfile(cls1) == inspect.getfile(cls2)
            and cls1.__qualname__ == cls2.__qualname__
        )


class InternalActionBase(Generic[Inputs, Outputs], metaclass=ActionMeta):
    ### Abstract interface

    #: The name of the action, used to identify it in the asyncflows configuration. Required.
    # `finished` is a reserved name (FIXME is it still?).
    name: ClassVar[str]

    #: The name of the action, used to describe it to the LLM upon action selection. Optional, defaults to `id`.
    readable_name: ClassVar[Optional[str]] = None

    #: The description of the action, used to describe it to the LLM upon action selection. Optional.
    description: ClassVar[Optional[str]] = None

    #: Whether to cache the (final) result of this action. Optional, defaults to `True`.
    cache: bool = True

    #: The version of the action, used to persist cache across project changes.
    # Optional, defaults to `None` (never cache across project changes).
    version: None | int = None

    ### Helpers

    async def request_read(
        self, url: str, method: str = "GET", fields: None | list[dict] = None, **kwargs
    ) -> bytes:
        return await request_read(self.log, url, method, fields, **kwargs)

    async def request_text(
        self, url: str, method: str = "GET", fields: None | list[dict] = None, **kwargs
    ) -> str:
        return await request_text(self.log, url, method, fields, **kwargs)

    ### Internals

    def __init__(
        self,
        log: structlog.stdlib.BoundLogger,
        temp_dir: str,
    ) -> None:
        self.log = log
        self.temp_dir = temp_dir

    @classmethod
    def _get_inputs_type(cls) -> type[Inputs]:
        i = typing.get_args(cls.__orig_bases__[0])[0]  # pyright: ignore
        if isinstance(i, TypeVar):
            raise ValueError(
                f"Action `{cls.name}` does not specify inputs type argument"
            )
        return i

    @classmethod
    def narrow_outputs_type(
        cls, action_invocation: ActionInvocation
    ) -> type[Outputs] | None:
        return None

    @classmethod
    def _get_outputs_type(
        cls,
        action_invocation: ActionInvocation | None,
    ) -> type[Outputs]:
        if action_invocation is not None:
            narrowed_output = cls.narrow_outputs_type(action_invocation)
            if narrowed_output is not None:
                return narrowed_output
        o = typing.get_args(cls.__orig_bases__[0])[1]  # pyright: ignore
        if isinstance(o, TypeVar):
            raise ValueError(
                f"Action `{cls.name}` does not specify outputs type argument"
            )
        return o


class Action(InternalActionBase[Inputs, Outputs]):
    """
    Base class for actions.

    Actions are the basic unit of work in the autonomous agent.
    They are responsible for performing a single task, affecting the environment in some way,
    and returning a string describing the result of the action.
    """

    async def run(self, inputs: Inputs) -> Outputs:
        """
        Run the action.

        Read the `inputs` argument to read variables from the context.
        Return outputs to write variables to the context.
        """
        raise NotImplementedError


class StreamingAction(InternalActionBase[Inputs, Outputs]):
    """
    Base class for actions that stream outputs.
    """

    async def run(self, inputs: Inputs) -> AsyncIterator[Outputs]:
        """
        Run the action.

        Read the `inputs` argument to read variables from the context.
        Yield outputs to write variables to the context.
        """
        raise NotImplementedError
        yield

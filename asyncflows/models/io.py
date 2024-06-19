# re-export these from pydantic, in case we need to change them later
from typing import ClassVar, TypeVar, Union

import pydantic

from asyncflows.models.config.model import ModelConfig
from asyncflows.models.primitives import ContextVarPath
from asyncflows.repos.blob_repo import BlobRepo


class BaseModel(pydantic.BaseModel):
    pass


def Field(*args, **kwargs):
    return pydantic.Field(*args, **kwargs)


def PrivateAttr(*args, **kwargs):
    return pydantic.PrivateAttr(*args, **kwargs)


# TODO ensure that inputs don't contain `id` or `action` as fields
Inputs = TypeVar("Inputs", bound=Union[BaseModel, type(None)])
Outputs = TypeVar("Outputs", bound=Union[BaseModel, type(None)])


class RedisUrlInputs(BaseModel):
    """
    Base class for inputs that include a `redis_url`.
    """

    _redis_url: str = PrivateAttr()


class BlobRepoInputs(BaseModel):
    """
    Base class for inputs that include a `blob_repo`.
    """

    _blob_repo: BlobRepo = PrivateAttr()


class DefaultModelInputs(BaseModel):
    """
    Base class for inputs that include a `default_model`.
    """

    _default_model: ModelConfig = PrivateAttr()


class FinalInvocationInputs(BaseModel):
    """
    Base class for inputs that include information on whether this is the action's last invocation.
    Actions using FinalInvocationInputs will be invoked again after all dependencies are finished,
    with `_finished` set to `True`.
    """

    _finished: bool = PrivateAttr(default=False)


class CacheControlOutputs(BaseModel):
    """
    Base class for outputs that control their caching.
    Set `cache` to `False` to prevent that output from being cached.
    """

    _cache: bool = PrivateAttr(default=True)

    def __init__(
        self,
        _cache: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._cache = _cache


class DefaultOutputOutputs(BaseModel):
    """
    Base class for outputs that include a default output (ClassVar).
    The path should be relative to the output object root.
    """

    _default_output: ClassVar[ContextVarPath]

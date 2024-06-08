# Transforming between config and action variables
from typing import TypeVar, Generic, Any

import structlog

from asyncflows.models.primitives import HintLiteral

RealType = TypeVar("RealType")
ConfigType = TypeVar("ConfigType")
ImplementsTransformsInContext = TypeVar("ImplementsTransformsInContext")


class TransformsInto(Generic[RealType]):
    """
    In the config, some IO types will have a different representation.
    """

    async def transform_from_config(
        self, log: structlog.stdlib.BoundLogger, context: dict[str, Any]
    ) -> RealType:
        """
        Transform a config variable into the type used in the action.
        """
        raise NotImplementedError


class TransformsFrom:  # (Generic[ConfigType]):
    """
    In the config, some IO types will have a different representation.
    """

    @classmethod
    def _get_config_type(
        cls,
        vars_: HintLiteral | None,
        links: HintLiteral | None,
        strict: bool = False,
    ) -> type:  # -> type[ConfigType]:
        raise NotImplementedError

import pydantic
from pydantic import ConfigDict


class StrictModel(pydantic.BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )


class ExtraModel(pydantic.BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )

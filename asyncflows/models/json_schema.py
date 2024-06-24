# Adapted from koxudaxi/datamodel-code-generator@0.25.7, licensed under:
#
# MIT License
#
# Copyright (c) 2019 Koudai Aono
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations
from typing import Union, Literal
from pydantic import (
    BaseModel,
    Field,
)

import enum as _enum
from functools import lru_cache
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
)


from pydantic import ConfigDict, field_validator, model_validator

UnionIntFloat = Union[int, float]


def get_model_by_path(
    schema: Union[Dict[str, Any], List[Any]], keys: Union[List[str], List[int]]
) -> Dict[Any, Any]:
    model: Union[Dict[Any, Any], List[Any]]
    if not keys:
        model = schema
    elif len(keys) == 1:
        if isinstance(schema, dict):
            model = schema.get(keys[0], {})  # type: ignore
        else:  # pragma: no cover
            model = schema[int(keys[0])]
    elif isinstance(schema, dict):
        model = get_model_by_path(schema[keys[0]], keys[1:])  # type: ignore
    else:
        model = get_model_by_path(schema[int(keys[0])], keys[1:])
    if isinstance(model, dict):
        return model
    raise NotImplementedError(  # pragma: no cover
        f"Does not support json pointer to array. schema={schema}, key={keys}"
    )


class JSONReference(_enum.Enum):
    LOCAL = "LOCAL"
    REMOTE = "REMOTE"
    URL = "URL"


class Discriminator(BaseModel):
    propertyName: str
    mapping: Optional[Dict[str, str]] = None


typestring_type = Literal[
    "string", "number", "integer", "object", "array", "boolean", "null"
]


class JsonSchemaObject(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )

    @classmethod
    def get_fields(cls) -> Dict[str, Any]:
        return cls.model_fields

    __constraint_fields__: Set[str] = {
        "exclusiveMinimum",
        "minimum",
        "exclusiveMaximum",
        "maximum",
        "multipleOf",
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
        # "pattern",
        "uniqueItems",
    }
    # __extra_key__: str = SPECIAL_PATH_FORMAT.format('extras')

    @model_validator(mode="before")
    def validate_exclusive_maximum_and_exclusive_minimum(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        exclusive_maximum: Union[float, bool, None] = values.get("exclusiveMaximum")
        exclusive_minimum: Union[float, bool, None] = values.get("exclusiveMinimum")

        if exclusive_maximum is True:
            values["exclusiveMaximum"] = values["maximum"]
            del values["maximum"]
        elif exclusive_maximum is False:
            del values["exclusiveMaximum"]
        if exclusive_minimum is True:
            values["exclusiveMinimum"] = values["minimum"]
            del values["minimum"]
        elif exclusive_minimum is False:
            del values["exclusiveMinimum"]
        return values

    @field_validator("ref")
    def validate_ref(cls, value: Any) -> Any:
        if isinstance(value, str) and "#" in value:
            if value.endswith("#/"):
                return value[:-1]
            elif "#/" in value or value[0] == "#" or value[-1] == "#":
                return value
            return value.replace("#", "#/")
        return value

    items: Union[List[JsonSchemaObject], JsonSchemaObject, bool, None] = None
    uniqueItems: Optional[bool] = None
    type: Union[typestring_type, List[typestring_type], None] = None
    format: Optional[Literal["email", "uri", "date"]] = None
    # pattern: Optional[str] = Field(
    #     default=None, description="A regular expression pattern."
    # )
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    minimum: Optional[UnionIntFloat] = None
    maximum: Optional[UnionIntFloat] = None
    minItems: Optional[int] = None
    maxItems: Optional[int] = None
    multipleOf: Optional[float] = None
    exclusiveMaximum: Union[float, bool, None] = None
    exclusiveMinimum: Union[float, bool, None] = None
    # additionalProperties: Union[JsonSchemaObject, bool, None] = None
    # patternProperties: Optional[Dict[str, JsonSchemaObject]] = None
    oneOf: List[JsonSchemaObject] = []
    anyOf: List[JsonSchemaObject] = []
    allOf: List[JsonSchemaObject] = []
    enum: List[Any] = []
    # writeOnly: Optional[bool] = None
    # readOnly: Optional[bool] = None
    properties: Optional[Dict[str, JsonSchemaObject]] = None
    required: List[str] | None = Field(
        default=None,
        description="List of required properties. Defaults to all properties.",
    )
    ref: Optional[str] = Field(default=None, alias="$ref")
    nullable: Optional[bool] = False
    x_enum_varnames: List[str] = Field(default=[], alias="x-enum-varnames")
    description: Optional[str] = None
    title: Optional[str] = None
    example: Any = None
    examples: Any = None
    default: Any = None
    id: Optional[str] = Field(default=None, alias="$id")
    custom_type_path: Optional[str] = Field(default=None, alias="customTypePath")
    custom_base_path: Optional[str] = Field(default=None, alias="customBasePath")
    # extras: Dict[str, Any] = Field(alias=__extra_key__, default_factory=dict)
    discriminator: Union[Discriminator, str, None] = None

    def is_object(self) -> bool:
        return (
            self.properties is not None
            or self.type == "object"
            and not self.allOf
            and not self.oneOf
            and not self.anyOf
            and not self.ref
        )

    def is_array(self) -> bool:
        return self.items is not None or self.type == "array"

    def ref_object_name(self) -> str:  # pragma: no cover
        return self.ref.rsplit("/", 1)[-1]  # type: ignore

    @field_validator("items", mode="before")
    def validate_items(cls, values: Any) -> Any:
        # this condition expects empty dict
        return values or None

    # def has_default(self) -> bool:
    #     return "default" in self.__fields_set__ or "default_factory" in self.extras

    def has_constraint(self) -> bool:
        return bool(self.__constraint_fields__ & self.__fields_set__)

    def ref_type(self) -> Optional[JSONReference]:
        if self.ref:
            return get_ref_type(self.ref)
        return None  # pragma: no cover

    def type_has_null(self) -> bool:
        return isinstance(self.type, list) and "null" in self.type


@lru_cache()
def get_ref_type(ref: str) -> JSONReference:
    if ref[0] == "#":
        return JSONReference.LOCAL
    elif ref.startswith(("https://", "http://")):
        return JSONReference.URL
    return JSONReference.REMOTE


JsonSchemaObject.model_rebuild()

from datetime import date
from typing import Any, Union, Literal

from pydantic import (
    conint,
    confloat,
    AnyUrl,
    EmailStr,
    conlist,
    conset,
    create_model,
    BaseModel,
    Field,
)

from asyncflows.models.json_schema import JsonSchemaObject


class ModelNamer:
    def __init__(self, name_root: str = "Model", initial: int = -1):
        self._name_root = name_root
        self._count = initial

    def get(self):
        self._count += 1
        return f"{self._name_root}{self._count}"


def jsonschema_to_pydantic(
    schema_object: JsonSchemaObject,
    definitions: dict[str, JsonSchemaObject] | None = None,
    model_namer: ModelNamer | None = None,
) -> Any:
    if model_namer is None:
        model_namer = ModelNamer()

    if definitions is None:
        definitions = {}

    if schema_object.ref:
        ref_name = schema_object.ref.split("/")[-1]
        if ref_name in definitions:
            return jsonschema_to_pydantic(
                definitions[ref_name], definitions, model_namer=model_namer
            )

    if schema_object.type == "object":
        return _create_object_model(schema_object, definitions, model_namer=model_namer)
    elif schema_object.type == "array":
        return _create_array_model(schema_object, definitions, model_namer=model_namer)
    elif schema_object.oneOf:
        return Union[
            tuple(
                jsonschema_to_pydantic(item, definitions, model_namer=model_namer)
                for item in schema_object.oneOf
            )  # type: ignore
        ]
    elif schema_object.anyOf:
        return Union[
            tuple(
                jsonschema_to_pydantic(item, definitions, model_namer=model_namer)
                for item in schema_object.anyOf
            )  # type: ignore
        ]
    elif schema_object.allOf:
        combined_properties = {}
        for item in schema_object.allOf:
            if isinstance(item, JsonSchemaObject) and item.properties:
                combined_properties.update(item.properties)
        return _create_object_model(
            JsonSchemaObject(type="object", properties=combined_properties),
            definitions,
            model_namer=model_namer,
        )
    else:
        return _get_field_type(schema_object, definitions, model_namer=model_namer)


def _create_object_model(
    schema_object: JsonSchemaObject,
    definitions: dict[str, JsonSchemaObject],
    model_namer: ModelNamer,
) -> type[BaseModel]:
    model_name = model_namer.get()

    fields: dict[str, Any] = {}
    if schema_object.properties:
        for prop_name, prop_schema in schema_object.properties.items():
            if isinstance(prop_schema, JsonSchemaObject):
                field_type = jsonschema_to_pydantic(
                    prop_schema, definitions, model_namer=model_namer
                )
                default = (
                    ...
                    if schema_object.required is None
                    or prop_name in schema_object.required
                    else None
                )
                if prop_schema.default is not None:
                    default = prop_schema.default
                fields[prop_name] = (field_type, Field(default=default))

    return create_model(model_name, **fields)


def _create_array_model(
    schema_object: JsonSchemaObject,
    definitions: dict[str, JsonSchemaObject],
    model_namer: ModelNamer,
) -> Any:
    if isinstance(schema_object.items, JsonSchemaObject):
        item_type = jsonschema_to_pydantic(
            schema_object.items, definitions, model_namer=model_namer
        )
        if schema_object.uniqueItems:
            return conset(item_type)
        if schema_object.minItems is not None or schema_object.maxItems is not None:
            return conlist(
                item_type,
                min_length=schema_object.minItems,
                max_length=schema_object.maxItems,
            )
        return list[item_type]
    else:
        raise ValueError("Array items must be a JsonSchemaObject")


def _get_field_type(
    schema: JsonSchemaObject,
    definitions: dict[str, JsonSchemaObject],
    model_namer: ModelNamer,
) -> Any:
    if schema.enum:
        return Literal[tuple(schema.enum)]  # type: ignore
    if schema.type == "string":
        if schema.format == "email":
            return EmailStr
        elif schema.format == "uri":
            return AnyUrl
        elif schema.format == "date":
            return date
        return str
    elif schema.type == "number":
        constraints = {}
        if schema.minimum is not None:
            constraints["ge"] = schema.minimum
        if schema.maximum is not None:
            constraints["le"] = schema.maximum
        if schema.multipleOf is not None:
            constraints["multiple_of"] = schema.multipleOf
        return confloat(**constraints) if constraints else float
    elif schema.type == "integer":
        constraints = {}
        if schema.minimum is not None:
            constraints["ge"] = schema.minimum
        if schema.maximum is not None:
            constraints["le"] = schema.maximum
        if schema.multipleOf is not None:
            constraints["multiple_of"] = schema.multipleOf
        return conint(**constraints) if constraints else int
    elif schema.type == "boolean":
        return bool
    elif schema.type == "array":
        return _create_array_model(schema, definitions, model_namer=model_namer)
    elif schema.type == "object":
        return _create_object_model(schema, definitions, model_namer=model_namer)
    elif isinstance(schema.type, list):
        types = [
            _get_field_type(
                JsonSchemaObject(type=t), definitions, model_namer=model_namer
            )
            for t in schema.type
            if t != "null"
        ]
        return Union[tuple(types + [type(None)])]  # type: ignore
    else:
        raise NotImplementedError(f"Unsupported field type: {schema.type}")

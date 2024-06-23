from typing import Union, Literal

import pytest
from pydantic import TypeAdapter

from asyncflows.models.json_schema import JsonSchemaObject
from asyncflows.utils.json_schema_utils import jsonschema_to_pydantic
import pydantic


@pytest.mark.parametrize(
    "json_schema, expected_pydantic",
    [
        (
            """
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"}
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                name=(str, ...),
                age=(float, ...),
            ),
        ),
        (
            """
            {
                "type": "array",
                "items": {"type": "string"}
            }
            """,
            list[str],
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "names": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                names=(list[str], ...),
            ),
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"}
                },
                "required": ["id"]
            }
            """,
            pydantic.create_model(
                "Model0",
                id=(int, ...),
                name=(str, None),
            ),
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "color": {
                        "type": "string",
                        "enum": ["red", "green", "blue"]
                    }
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                color=(Literal["red", "green", "blue"], ...),
            ),
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"}
                        }
                    }
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                user=(
                    pydantic.create_model(
                        "Model1",
                        name=(str, ...),
                        email=(str, ...),
                    ),
                    ...,
                ),
            ),
        ),
        (
            """
            {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 1,
                "maxItems": 5
            }
            """,
            pydantic.conlist(float, min_length=1, max_length=5),
        ),
        # (
        #     """
        #     {
        #         "type": "object",
        #         "properties": {
        #             "email": {
        #                 "type": "string",
        #                 "pattern": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"
        #             }
        #         }
        #     }
        #     """,
        #     pydantic.create_model(
        #         "Model0",
        #         email=(Annotated[str, StringConstraints(pattern='^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$')], ...),
        #     ),
        # ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100
                    }
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                score=(pydantic.confloat(ge=0, le=100), ...),
            ),
        ),
        (
            """
            {
                "oneOf": [
                    {"type": "string"},
                    {"type": "number"}
                ]
            }
            """,
            Union[str, float],
        ),
        (
            """
            {
                "allOf": [
                    {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        }
                    },
                    {
                        "type": "object",
                        "properties": {
                            "age": {"type": "number"}
                        }
                    }
                ]
            }
            """,
            pydantic.create_model(
                "Model0",
                name=(str, ...),
                age=(float, ...),
            ),
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": ["number", "null"]}
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                name=(str, ...),
                age=(float | None, ...),
            ),
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "is_active": {"type": "boolean", "default": true}
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                name=(str, ...),
                is_active=(bool, True),
            ),
        ),
        (
            """
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                    {"type": "boolean"}
                ]
            }
            """,
            Union[str, float, bool],
        ),
        # (
        #     """
        #     {
        #         "type": "object",
        #         "properties": {
        #             "user": {"$ref": "#/definitions/User"}
        #         },
        #         "definitions": {
        #             "User": {
        #                 "type": "object",
        #                 "properties": {
        #                     "id": {"type": "integer"},
        #                     "name": {"type": "string"}
        #                 }
        #             }
        #         }
        #     }
        #     """,
        #     pydantic.create_model(
        #         "Model0",
        #         user=(pydantic.create_model(
        #             "User",
        #             id=(int, ...),
        #             name=(str, ...),
        #         ), ...),
        #     ),
        # ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "website": {"type": "string", "format": "uri"},
                    "birthday": {"type": "string", "format": "date"}
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                email=(pydantic.EmailStr, ...),
                website=(pydantic.AnyUrl, ...),
                birthday=(pydantic.condate(), ...),
            ),
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "factor": {"type": "number", "multipleOf": 0.5}
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                factor=(pydantic.confloat(multiple_of=0.5), ...),
            ),
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "uniqueItems": true
                    }
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                tags=(pydantic.conset(str), ...),
            ),
        ),
        (
            """
            {
                "type": "object",
                "properties": {
                    "matrix": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "number"}
                        }
                    }
                }
            }
            """,
            pydantic.create_model(
                "Model0",
                matrix=(list[list[float]], ...),
            ),
        ),
        (
            """
            {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "pet_type": {"type": "string", "enum": ["cat"]},
                            "meow_volume": {"type": "number"}
                        }
                    },
                    {
                        "type": "object",
                        "properties": {
                            "pet_type": {"type": "string", "enum": ["dog"]},
                            "bark_volume": {"type": "number"}
                        }
                    }
                ],
                "discriminator": {"propertyName": "pet_type"}
            }
            """,
            Union[
                pydantic.create_model(
                    "Model0",
                    pet_type=(Literal["cat"], ...),
                    meow_volume=(float, ...),
                ),
                pydantic.create_model(
                    "Model1",
                    pet_type=(Literal["dog"], ...),
                    bark_volume=(float, ...),
                ),
            ],
        ),
    ],
)
def test_jsonschema_to_pydantic(json_schema, expected_pydantic):
    schema_obj = JsonSchemaObject.model_validate_json(json_schema)
    pydantic_model = jsonschema_to_pydantic(schema_obj)
    assert (
        TypeAdapter(pydantic_model).json_schema()
        == TypeAdapter(expected_pydantic).json_schema()
    )

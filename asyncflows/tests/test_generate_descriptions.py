import pytest
from pydantic.fields import FieldInfo

from asyncflows import Field
from asyncflows.actions.utils.prompt_context import ContextElement
from asyncflows.utils.type_utils import build_field_description
from asyncflows.models.config.model import ModelConfig
import enum


# string enum
class Color(str, enum.Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


@pytest.mark.parametrize(
    "field_name, field_info, markdown, expected_output",
    [
        (
            "data",
            Field(
                description="The data to classify.",
            ),
            False,
            "`data`: Any (optional)  \n  The data to classify.",
        ),
        (
            "list_of_data",
            FieldInfo.from_annotation(list[str]),
            False,
            "`list_of_data`: list[str]",
        ),
        (
            "string_enum",
            FieldInfo.from_annotation(Color),
            False,
            "`string_enum`: 'red' | 'green' | 'blue'",
        ),
        (
            "list_of_models",
            FieldInfo.from_annotation(list[ModelConfig]),
            False,
            "`list_of_models`: list[ModelConfig]",
        ),
        (
            "list_of_models",
            FieldInfo.from_annotation(list[ModelConfig]),
            True,
            "`list_of_models`: list[ModelConfig](file:///",
        ),
        (
            "transformed",
            FieldInfo.from_annotation(ContextElement),
            False,
            "`transformed`: ContextVar | ContextLink | ContextTemplate | ContextLambda",
        ),
    ],
)
def test_generate_field_description(field_name, field_info, markdown, expected_output):
    if markdown:
        build_field_description(
            field_name, field_info, markdown=markdown, include_paths=True
        ).startswith(expected_output)
    else:
        assert (
            build_field_description(
                field_name, field_info, markdown=markdown, include_paths=True
            )
            == expected_output
        )

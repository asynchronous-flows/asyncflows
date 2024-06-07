import pytest
from pydantic.fields import FieldInfo

from asyncflows import Field
from asyncflows.actions.utils.prompt_context import ContextElement
from asyncflows.models.config.action import build_field_description
from asyncflows.models.config.model import ModelConfig


@pytest.mark.parametrize(
    "field_name, field_info, markdown, expected_output",
    [
        (
            "data",
            Field(
                description="The data to classify.",
            ),
            False,
            "data: Any (optional)  \n  The data to classify.",
        ),
        (
            "list_of_data",
            FieldInfo.from_annotation(list[str]),
            False,
            "list_of_data: list[str]",
        ),
        (
            "list_of_models",
            FieldInfo.from_annotation(list[ModelConfig]),
            False,
            "list_of_models: list[ModelConfig]",
        ),
        (
            "list_of_models",
            FieldInfo.from_annotation(list[ModelConfig]),
            True,
            "list_of_models: list[ModelConfig](file:///",
        ),
        (
            "transformed",
            FieldInfo.from_annotation(ContextElement),
            False,
            "transformed: ContextVar | ContextLink | ContextTemplate | ContextLambda",
        ),
    ],
)
def test_generate_field_description(field_name, field_info, markdown, expected_output):
    if markdown:
        build_field_description(field_name, field_info, markdown=markdown).startswith(
            expected_output
        )
    else:
        assert (
            build_field_description(field_name, field_info, markdown=markdown)
            == expected_output
        )

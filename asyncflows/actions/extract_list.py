from typing import Optional, Literal
from typing_extensions import assert_never

from asyncflows import Action, BaseModel

LIST_FORMAT = Literal["comma", "newline", "space", "bullet points"]


class Inputs(BaseModel):
    text: str
    valid_values: Optional[list[str]] = None
    list_format: LIST_FORMAT = "bullet points"


class Outputs(BaseModel):
    results: list[str]


class ExtractList(Action[Inputs, Outputs]):
    name = "extract_list"

    async def run(self, inputs: Inputs) -> Outputs:
        if inputs.list_format == "comma":
            candidates = inputs.text.split(",")
        elif inputs.list_format == "newline":
            candidates = inputs.text.split("\n")
        elif inputs.list_format == "space":
            candidates = inputs.text.split(" ")
        elif inputs.list_format == "bullet points":
            candidates = inputs.text.split("-")
        else:
            assert_never(inputs.list_format)
            # raise ValueError(f"Invalid list_format: {inputs.list_format}")

        choices = []
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate:
                continue
            if inputs.valid_values and candidate not in inputs.valid_values:
                continue
            choices.append(candidate)
        return Outputs(
            results=choices,
        )

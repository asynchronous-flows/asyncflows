import asyncio
from typing import AsyncIterator

from asyncflows.models.config.action import (
    Action,
    StreamingAction,
)
from asyncflows.models.io import (
    FinalInvocationInputs,
    BlobRepoInputs,
    BaseModel,
)
from asyncflows.actions.utils.prompt_context import (
    PromptElement,
    RoleElement,
    ContextElement,
)
from asyncflows.models.blob import Blob
from asyncflows.actions.prompt import Inputs as PromptInputs

# Add


class AddInputs(BaseModel):
    a: int
    b: int


class AddOutputs(BaseModel):
    result: int


class Add(Action[AddInputs, AddOutputs]):
    name = "test_add"

    async def run(self, inputs: AddInputs) -> AddOutputs:
        return AddOutputs(result=inputs.a + inputs.b)


# Nested add


class NestedAddInputs(BaseModel):
    nested: AddInputs


class NestedAddOutputs(BaseModel):
    nested: AddOutputs


class AddNested(Action[NestedAddInputs, NestedAddOutputs]):
    name = "test_nested_add"

    async def run(self, inputs: NestedAddInputs) -> NestedAddOutputs:
        return NestedAddOutputs(
            nested=AddOutputs(result=inputs.nested.a + inputs.nested.b),
        )


# optional nested add


class OptionalNestedAddInputs(BaseModel):
    nested: AddInputs | None


class OptionalNestedAddOutputs(BaseModel):
    nested: AddOutputs | None


class OptionalAddNested(Action[OptionalNestedAddInputs, OptionalNestedAddOutputs]):
    name = "test_optional_nested_add"

    async def run(self, inputs: OptionalNestedAddInputs) -> OptionalNestedAddOutputs:
        if inputs.nested is None:
            return OptionalNestedAddOutputs(nested=None)
        return OptionalNestedAddOutputs(
            nested=AddOutputs(result=inputs.nested.a + inputs.nested.b),
        )


# Double add


class DoubleAdd(StreamingAction[AddInputs, AddOutputs]):
    name = "test_double_add"

    async def run(self, inputs: AddInputs) -> AsyncIterator[AddOutputs]:
        yield AddOutputs(result=inputs.a + inputs.b)
        yield AddOutputs(result=2 * (inputs.a + inputs.b))


# Waiting add


class WaitingAdd(Action[AddInputs, AddOutputs]):
    name = "test_waiting_add"

    async def run(self, inputs: AddInputs) -> AddOutputs:
        await asyncio.sleep(0.05)
        return AddOutputs(result=inputs.a + inputs.b)


# Error


class ErrorAction(Action[None, None]):
    name = "test_error"

    async def run(self, inputs: None) -> None:
        raise RuntimeError("This action always fails")


# Create blob


class CreateBlobOutputs(BaseModel):
    blob: Blob


class CreateBlob(Action[BlobRepoInputs, CreateBlobOutputs]):
    name = "test_create_blob"

    async def run(self, inputs: BlobRepoInputs) -> CreateBlobOutputs:
        blob = await inputs._blob_repo.save(self.log, b"testy_blob")
        return CreateBlobOutputs(blob=blob)


# Get blob


class GetBlobInputs(BlobRepoInputs):
    blob: Blob


class GetBlob(Action[GetBlobInputs, None]):
    name = "test_get_blob"

    async def run(self, inputs: GetBlobInputs) -> None:
        await inputs._blob_repo.retrieve(self.log, inputs.blob)


# Transforming prompt


class NestedPromptContext(BaseModel):
    context: list[PromptElement]


class TransformingPromptInputs(BaseModel):
    context: list[PromptElement]
    nested: NestedPromptContext


class TransformingPromptOutputs(BaseModel):
    context_value: str
    nested_context_value: str


class TransformingInput(Action[TransformingPromptInputs, TransformingPromptOutputs]):
    name = "test_transforming_prompt"

    async def run(self, inputs: TransformingPromptInputs) -> TransformingPromptOutputs:
        first_element = inputs.context[0]
        if isinstance(first_element, RoleElement):
            text = ""
        elif isinstance(first_element, ContextElement):
            text = first_element.value
        else:
            text = first_element.text
        return TransformingPromptOutputs(
            context_value=text,
            nested_context_value=text,
        )


class PromptTransformingInput(Action[PromptInputs, PromptInputs]):
    name = "test_passing_prompt"

    async def run(self, inputs: PromptInputs) -> PromptInputs:
        return inputs


class RangeStreamInput(BaseModel):
    range: int


class RangeStreamOutput(BaseModel):
    value: int


class RangeStream(StreamingAction[RangeStreamInput, RangeStreamOutput]):
    name = "test_range_stream"

    async def run(self, inputs: RangeStreamInput) -> AsyncIterator[RangeStreamOutput]:
        for i in range(inputs.range):
            yield RangeStreamOutput(value=i)


class StringifierInput(BaseModel):
    value: int


class StringifierOutput(BaseModel):
    string: str


class Stringifier(Action[StringifierInput, StringifierOutput]):
    name = "test_stringifier"

    async def run(self, inputs: StringifierInput) -> StringifierOutput:
        return StringifierOutput(string=str(inputs.value))


# Non-caching action


class NonCacheAdderInputs(BaseModel):
    a: int
    b: int


class NonCacheAdderOutputs(BaseModel):
    result: int


class NonCachingAdder(Action[NonCacheAdderInputs, NonCacheAdderOutputs]):
    name = "test_non_caching_adder"
    cache = False

    async def run(self, inputs: NonCacheAdderInputs) -> NonCacheAdderOutputs:
        return NonCacheAdderOutputs(result=inputs.a + inputs.b)


# finish action


class FinishInputs(FinalInvocationInputs):
    pass


class FinishOutputs(BaseModel):
    finish_history: list[bool]


class FinishAction(Action[FinishInputs, FinishOutputs]):
    name = "test_finish"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history = []

    async def run(self, inputs: FinishInputs) -> FinishOutputs:
        self.history.append(inputs._finished)
        return FinishOutputs(finish_history=self.history[:])

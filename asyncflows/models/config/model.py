from typing import Optional, Literal

from asyncflows.models.config.common import StrictModel

ModelType = (
    Literal[
        "gpt-4-1106-preview",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo-16k",
        "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo",
        "gemini-pro",
        "claude-3-haiku-20240307",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
    ]
    | str
)


class ModelConfig(StrictModel):
    max_output_tokens: int = 2000
    max_prompt_tokens: int = 8000
    temperature: float = 0.6
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    model: ModelType = "gpt-3.5-turbo-1106"


class OptionalModelConfig(ModelConfig):
    max_output_tokens: Optional[int] = None
    max_prompt_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    model: Optional[ModelType] = None


BiEncoderModelType = Literal[
    "sentence-transformers/all-mpnet-base-v2",
    "BAAI/bge-small-en-v1.5",
]
CrossEncoderModelType = Literal[
    "cross-encoder/ms-marco-TinyBERT-L-2-v2",
    "BAAI/bge-reranker-base",
]

from typing import Optional, Literal, Annotated

from pydantic import Field

from asyncflows.models.config.common import StrictModel

ModelType = (
    # ollama models
    Annotated[
        Literal[
            "ollama/llama3",
            "ollama/llama3:8b",
            "ollama/llama3:70b",
            "ollama/gemma",
            "ollama/gemma:2b",
            "ollama/gemma:7b",
            "ollama/mixtral",
            "ollama/mixtral:8x7b",
            "ollama/mixtral:8x22b",
        ],
        Field(
            description="Run inference on [Ollama](https://ollama.com/); defaults `api_base` to `localhost:11434`"
        ),
    ]
    |
    # openai models
    Annotated[
        Literal[
            "gpt-4o",
            "gpt-4-1106-preview",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-3.5-turbo-1106",
            "gpt-3.5-turbo",
        ],
        Field(
            description="OpenAI model; requires `OPENAI_API_KEY` environment variable"
        ),
    ]
    |
    # google models
    Annotated[
        Literal["gemini-pro",],
        Field(
            description="Google model; requires `GCP_CREDENTIALS_64` environment variable (base64-encoded GCP credentials JSON)"
        ),
    ]
    |
    # anthropic models
    Annotated[
        Literal[
            "claude-3-5-sonnet-20240620",
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
        ],
        Field(
            description="Anthropic model; requires `ANTHROPIC_API_KEY` environment variable"
        ),
    ]
    | str
)


BiEncoderModelType = Literal[
    "sentence-transformers/all-mpnet-base-v2",
    "BAAI/bge-small-en-v1.5",
]
CrossEncoderModelType = Literal[
    "cross-encoder/ms-marco-TinyBERT-L-2-v2",
    "BAAI/bge-reranker-base",
]


class ModelConfig(StrictModel):
    max_output_tokens: int = 2000
    max_prompt_tokens: int = 8000
    temperature: float | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    model: ModelType = "ollama/llama3"
    api_base: Optional[str] = None
    auth_token: Optional[str] = None


class OptionalModelConfig(ModelConfig):
    max_output_tokens: Optional[int] = None
    max_prompt_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    model: Optional[ModelType] = None
    api_base: Optional[str] = None
    auth_token: Optional[str] = None

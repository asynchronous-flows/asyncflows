import datetime
import os
from typing import Literal
from unittest.mock import patch

import pytest
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import ChoiceDelta, Choice

from asyncflows.actions.prompt import Inputs, Prompt
from asyncflows.actions.utils.prompt_context import (
    TextElement,
    ContextElement,
    RoleElement,
    QuoteStyle,
)
from asyncflows.models.config.model import ModelConfig


def create_stream_chat_completion(
    response: str, role: Literal["system", "user", "assistant", "tool"] = "assistant"
):
    async def _(*args, **kwargs):
        async def gen():
            for token in response:
                yield ChatCompletionChunk(
                    id="foo",
                    model="gpt-3.5-turbo",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            finish_reason=None,
                            delta=ChoiceDelta(
                                content=token,
                                role=role,
                            ),
                        ),
                    ],
                    created=int(datetime.datetime.now().timestamp()),
                )

        return gen()

    return _


@pytest.fixture
def expected_response():
    return "This is the result."


@pytest.fixture
def openai_mock(expected_response):
    # mock AsyncOpenAI
    openai_key_bak = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "123"
    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_openai().chat.completions.create = create_stream_chat_completion(
            expected_response
        )

        async def _():
            pass

        mock_openai().close = _
        yield mock_openai
    if openai_key_bak is None:
        del os.environ["OPENAI_API_KEY"]
    else:
        os.environ["OPENAI_API_KEY"] = openai_key_bak


@pytest.fixture
def action(log, temp_dir):
    return Prompt(
        log=log,
        temp_dir=temp_dir,
    )


async def test_with_openai_mock(action, expected_response, openai_mock, log, temp_dir):
    result = ""
    inputs = Inputs(
        prompt=[
            TextElement(
                text="This is the prompt.",
            )
        ],
    )
    inputs._default_model = ModelConfig(
        model="gpt-3.5-turbo",
    )
    async for outputs in action.run(inputs):
        result = outputs.result
        assert expected_response.startswith(result)

    assert result == expected_response


@pytest.mark.parametrize(
    "message_config, quote_style, expected_text",
    [
        (
            apples := [
                ContextElement(
                    heading="What I have in my kitchen",
                    value="Apples",
                )
            ],
            QuoteStyle.BACKTICKS,
            [
                {
                    "role": "user",
                    "content": """What I have in my kitchen:
```
Apples
```""",
                }
            ],
        ),
        (
            apples,
            QuoteStyle.XML,
            [
                {
                    "role": "user",
                    "content": """<What I have in my kitchen>
Apples
</What I have in my kitchen>""",
                }
            ],
        ),
        (
            [
                TextElement(
                    text="This is a test.",
                ),
                TextElement(
                    role="user",
                    text="This is another test.",
                ),
                TextElement(
                    text="And a third",
                ),
            ],
            QuoteStyle.BACKTICKS,
            [
                {"role": "user", "content": "This is a test."},
                {"role": "user", "content": "This is another test.\n\nAnd a third"},
            ],
        ),
    ],
)
def test_build_messages(action, message_config, quote_style, expected_text):
    max_prompt_tokens = 100
    model = "gpt-3.5-turbo-16k"

    messages = action.build_messages(
        message_config=message_config,
        model_config=ModelConfig(
            model=model,
            max_prompt_tokens=max_prompt_tokens,
        ),
        quote_style=quote_style,
    )
    assert messages == expected_text


def test_trim_messages(action):
    max_prompt_tokens = 60
    model = "gpt-3.5-turbo-16k"

    context = [
        ContextElement(
            heading="What I have in my kitchen",
            value="Apple, bananas, oranges, tomatoes, " * 50,
        ),
    ]
    trimmed_context = action.build_messages(
        message_config=context,
        model_config=ModelConfig(
            model=model,
            max_prompt_tokens=max_prompt_tokens,
        ),
        quote_style=QuoteStyle.BACKTICKS,
    )
    assert (
        trimmed_context[0]["content"]
        == """What I have in my kitchen:
```
Apple, bananas, oranges, tomatoes, Apple, bananas, oranges, tomatoes..anas, oranges, tomatoes, Apple, bananas, oranges, tomatoes, Apple, bananas, oranges, tomatoes, 
```"""
    )

    max_prompt_tokens = 100

    # litellm joins multiple messagestogether

    context = [
        RoleElement(
            role="user",
        ),
        ContextElement(
            heading="What I have in my kitchen",
            value="Apple, bananas, oranges, tomatoes, " * 50,
        ),
        RoleElement(
            role="user",
        ),
        ContextElement(
            heading="What I have in my pantry",
            value="Flour, sugar, salt, pepper, " * 50,
        ),
        RoleElement(
            role="user",
        ),
        ContextElement(
            heading="What I have in my fridge",
            value="Milk, eggs, cheese, " * 50,
        ),
    ]
    trimmed_context = action.build_messages(
        message_config=context,
        model_config=ModelConfig(
            model=model,
            max_prompt_tokens=max_prompt_tokens,
        ),
        quote_style=QuoteStyle.BACKTICKS,
    )
    assert len(trimmed_context) == 1
    assert (
        trimmed_context[0]["content"]
        == """What I have in my fridge:
```
Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, che.. Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, 
```"""
    )

    # litellm moves up system messages

    context = [
        RoleElement(
            role="user",
        ),
        ContextElement(
            heading="What I have in my pantry",
            value="Flour, sugar, salt, pepper, " * 10,
        ),
        RoleElement(
            role="system",
        ),
        ContextElement(
            heading="What I have in my fridge",
            value="Milk, eggs, cheese, " * 10,
        ),
        RoleElement(
            role="user",
        ),
        ContextElement(
            heading="What I have in my fridge",
            value="Milk, eggs, cheese, " * 10,
        ),
    ]
    # trimmed_context = trim_context(context, max_prompt_tokens, strategy, model)
    trimmed_context = action.build_messages(
        message_config=context,
        model_config=ModelConfig(
            model=model,
            max_prompt_tokens=max_prompt_tokens,
        ),
        quote_style=QuoteStyle.BACKTICKS,
    )
    assert len(trimmed_context) == 2
    assert trimmed_context[0]["role"] == "system"
    assert (
        trimmed_context[0]["content"]
        == """What I have in my fridge:
```
Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, Milk, eggs, cheese, 
```"""
    )
    assert trimmed_context[1]["role"] == "user"
    assert (
        trimmed_context[1]["content"]
        == """What I have in ..s, cheese, 
```"""
    )

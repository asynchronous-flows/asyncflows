import asyncio
import os
from asyncio import Event
from unittest.mock import Mock, patch

import pytest
from asyncflows.models.config.action import Action
from asyncflows.models.io import BaseModel
from asyncflows.utils.async_utils import Timer, measure_coro, measure_async_iterator


@pytest.fixture(scope="function")
def mock_time():
    # Mock time.time() and time.perf_counter()
    mock_time = Mock()
    mock_time.monotonic.side_effect = lambda: mock_time.monotonic.call_count
    mock_time.perf_counter.side_effect = lambda: mock_time.perf_counter.call_count
    with patch("asyncflows.utils.async_utils.time", mock_time):
        yield


@pytest.mark.parametrize(
    "sleep_time, expected_wall_time, expected_blocking_time",
    [
        (
            None,
            1,
            1,
        ),
        (
            0,
            3,
            2,
        ),
        (
            0.0000000000001,
            3,
            2,
        ),
    ],
)
async def test_measure_coro(
    log, mock_time, sleep_time, expected_wall_time, expected_blocking_time
):
    async def coro(x):
        if sleep_time is not None:
            await asyncio.sleep(sleep_time)
        return x * 2

    measurement = Timer()
    result = await measure_coro(log, coro(1), measurement)

    assert result == 2
    assert measurement.wall_time == expected_wall_time
    assert measurement.blocking_time == expected_blocking_time


@pytest.mark.parametrize(
    "sleep_time, expected_wall_time, expected_blocking_time",
    [
        (
            None,
            3,
            2,
        ),
        (
            0,
            5,
            3,
        ),
        (
            0.0000000000001,
            5,
            3,
        ),
    ],
)
async def test_measure_iterator(
    log, mock_time, sleep_time, expected_wall_time, expected_blocking_time
):
    async def sample_async_iter(x):
        for i in range(x):
            if sleep_time is not None:
                await asyncio.sleep(sleep_time)
            yield i

    measurement = Timer()
    measured_sample_async_iter = measure_async_iterator(
        log, sample_async_iter(1), measurement
    )
    results = [val async for val in measured_sample_async_iter]

    assert results == [0]
    assert measurement.wall_time == expected_wall_time
    assert measurement.blocking_time == expected_blocking_time


async def test_measure_action_request_with_mocked_aiohttp(
    mock_aioresponse, log, mock_time, temp_dir
):
    link = "https://example.com"
    text = "Hello, world!"

    mock_aioresponse.get(link, body=text)

    class MyActionOutputs(BaseModel):
        text: str

    class MyAction(Action[None, MyActionOutputs]):
        name = "my_action"

        async def run(self, inputs: None) -> MyActionOutputs:
            return MyActionOutputs(
                text=await self.request_text(link),
            )

    measurement = Timer()
    action = MyAction(log, temp_dir)
    result = await measure_coro(log, action.run(None), measurement)

    assert result.text == text
    assert measurement.wall_time == 3
    assert measurement.blocking_time == 2


# @pytest.mark.skipif(
#     "OPENAI_API_KEY" not in os.environ, reason="requires OPENAI_API_KEY"
# )
@pytest.mark.parametrize(
    "model",
    [
        pytest.param(
            "gpt-3.5-turbo",
            marks=pytest.mark.skipif(
                "OPENAI_API_KEY" not in os.environ,
                reason="requires OPENAI_API_KEY",
            ),
        ),
        pytest.param(
            "claude-3-sonnet-20240229",
            marks=pytest.mark.skipif(
                "ANTHROPIC_API_KEY" not in os.environ,
                reason="requires ANTHROPIC_API_KEY",
            ),
        ),
        pytest.param(
            "gemini-pro",
            marks=pytest.mark.skipif(
                "GCP_CREDENTIALS_64" not in os.environ,
                reason="requires GCP_CREDENTIALS_64",
            ),
        ),
    ],
)
@pytest.mark.slow
@pytest.mark.allow_skip
async def test_measure_live_prompt_action(log, temp_dir, model):
    from asyncflows.actions.prompt import Inputs, Prompt
    from asyncflows.models.config.model import ModelConfig
    from asyncflows.actions.utils.prompt_context import TextElement

    expected_response = "This is the response."

    action = Prompt(
        log=log,
        temp_dir=temp_dir,
    )

    inputs = Inputs(
        prompt=[
            TextElement(
                text='Respond only with "This is the response."',
            )
        ]
    )
    inputs._default_model = ModelConfig(
        temperature=0,
        model=model,
    )

    timer = Timer()
    result = ""
    async for outputs in measure_async_iterator(
        log,
        action.run(inputs),
        timer,
    ):
        result = outputs.result
        assert expected_response.startswith(expected_response)

    log.info("Ran prompt action", blocking_time=timer.blocking_time)
    assert result == expected_response


async def _test_measure_live_httpcore_call(log):
    import httpcore

    async def api_call():
        async with httpcore.AsyncConnectionPool() as http:
            return await http.request("GET", "https://example.com")

    measurement = Timer()
    result = await measure_coro(log, api_call(), measurement)

    assert result.status == 200


@pytest.mark.parametrize(
    "n",
    [1, 5],
)
@pytest.mark.slow
async def test_measure_live_httpcore_calls(log, n):
    tasks = []
    for i in range(n):
        tasks.append(measure_coro(log, _test_measure_live_httpcore_call(log), Timer()))
    await asyncio.gather(*tasks)


async def test_measure_with_cancel_scope(log, mock_time):
    from anyio import move_on_after

    async def try_connect():
        event = Event()
        loop = asyncio.get_event_loop()
        loop.call_soon(event.set)
        event.clear()
        async with move_on_after(0.01):
            await asyncio.sleep(0.1)
            await event.wait()
        return "yay"

    measurement = Timer()
    # result = await try_connect()
    result = await measure_coro(log, try_connect(), measurement)

    assert result == "yay"
    assert measurement.wall_time == 3
    assert measurement.blocking_time == 2

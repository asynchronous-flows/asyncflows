import pytest

from asyncflows.actions.transformer import (
    Retrieve,
    Rerank,
    RetrieveInputs,
    RerankInputs,
)


@pytest.fixture
def retrieve(log, temp_dir, mock_trace_id):
    log = log.bind(trace_id=mock_trace_id)
    return Retrieve(log=log, temp_dir=temp_dir)


@pytest.fixture
def rerank(log, temp_dir, mock_trace_id):
    log = log.bind(trace_id=mock_trace_id)
    return Rerank(log=log, temp_dir=temp_dir)


@pytest.mark.slow
@pytest.mark.parametrize(
    "documents, texts, query, expected_result",
    [
        (["pizza", "flowers"], None, "magnolia", ["flowers"]),
        ([1, 2], ["pizza", "flowers"], "magnolia", [2]),
    ],
)
async def test_retrieve(
    retrieve, log, temp_dir, lag_monitor, documents, texts, query, expected_result
):
    inputs = RetrieveInputs(
        documents=documents,
        texts=texts,
        query=query,
        model="sentence-transformers/all-mpnet-base-v2",
        k=1,
        # server_url=os.environ.get("TRANSFORMERS_SERVER_URL"),
    )

    outputs = await retrieve.run(inputs)

    assert outputs.result == expected_result


@pytest.mark.slow
@pytest.mark.parametrize(
    "documents, texts, query, expected_result",
    [
        (
            ["pizza", "magnolia"],
            None,
            "my favorite flower is",
            ["magnolia"],
        ),
        (
            [1, 2],
            ["pizza", "magnolia"],
            "my favorite flower is",
            [2],
        ),
    ],
)
async def test_rerank(
    rerank, log, temp_dir, lag_monitor, documents, texts, query, expected_result
):
    inputs = RerankInputs(
        documents=documents,
        texts=texts,
        query=query,
        model="cross-encoder/ms-marco-TinyBERT-L-2-v2",
        k=1,
        # server_url=os.environ.get("TRANSFORMERS_SERVER_URL"),
    )

    outputs = await rerank.run(inputs)

    assert outputs.result == expected_result

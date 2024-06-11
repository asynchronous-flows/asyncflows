import asyncio
import contextlib
from collections import defaultdict
from typing import AsyncIterator, Any, Literal, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from infinity_emb import AsyncEmbeddingEngine
else:
    AsyncEmbeddingEngine = Any


DEFAULT_KEEP_ENGINE_ALIVE_DELAY = 2

active_engines: dict[str, AsyncEmbeddingEngine] = {}
_engine_usage_counts = defaultdict(int)


async def shutdown_engine(log, delay: float, model: str, engine: AsyncEmbeddingEngine):
    try:
        await asyncio.sleep(delay)
    finally:
        _engine_usage_counts[model] -= 1
        if _engine_usage_counts[model] == 0:
            del active_engines[model]
            log.info("Shutting down engine", model=model)
            await engine.astop()
            log.info("Successfully shut down engine", model=model)


@contextlib.asynccontextmanager
async def get_engine(
    log,
    model: str,
    device: Literal["cpu", "cuda", "mps", "tensorrt"] | None,
    keep_engine_alive_delay: float,
) -> AsyncIterator[AsyncEmbeddingEngine]:
    from infinity_emb import AsyncEmbeddingEngine, EngineArgs
    from infinity_emb.primitives import Device

    if model in active_engines:
        engine = active_engines[model]
        if not engine.running:
            # idk if this will ever trigger but here we are
            log.debug("Engine not running, waiting for it to start")
            await asyncio.sleep(0.1)
            if not engine.running:
                raise ValueError("Engine not starting up, something is wrong")
    else:
        args = EngineArgs(
            model_name_or_path=model,
            device=Device(device),
        )
        engine = AsyncEmbeddingEngine.from_args(args)
        active_engines[model] = engine
        log.info("Starting engine", model=model)
        await engine.astart()

    _engine_usage_counts[model] += 1
    try:
        yield engine
    finally:
        # FIXME does this break stuff? just trying not to shut down the engine immediately
        asyncio.create_task(
            shutdown_engine(log, keep_engine_alive_delay, model, engine)
        )


async def retrieve_indices(
    log,
    model: str,
    device: Literal["cpu", "cuda", "mps", "tensorrt"] | None,
    documents: list[str],
    query: str,
    k: int,
    keep_engine_alive_delay: float = DEFAULT_KEEP_ENGINE_ALIVE_DELAY,
) -> list[int]:
    # embed query and documents
    documents.append(query)
    async with get_engine(log, model, device, keep_engine_alive_delay) as engine:
        embeddings, usage = await engine.embed(sentences=documents)
    log.info("Embedded documents", usage=usage)
    query_embedding = embeddings.pop()

    # calculate cosine similarity between query and documents
    query_norm = np.linalg.norm(query_embedding)
    scores = [
        np.dot(query_embedding, doc_embedding)
        / (query_norm * np.linalg.norm(doc_embedding))
        for doc_embedding in embeddings
    ]

    # return indices of most similar documents
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]


async def rerank_indices(
    log,
    model: str,
    device: Literal["cpu", "cuda", "mps", "tensorrt"] | None,
    documents: list[str],
    query: str,
    k: int,
    keep_engine_alive_delay: float = DEFAULT_KEEP_ENGINE_ALIVE_DELAY,
) -> list[int]:
    # rerank documents based on query
    async with get_engine(log, model, device, keep_engine_alive_delay) as engine:
        scores, usage = await engine.rerank(query=query, docs=documents)
    log.info("Reranked documents", usage=usage)

    # return indices of most relevant documents
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

from typing import Any, Literal

from asyncflows import Action, BaseModel
from asyncflows.models.config.model import BiEncoderModelType, CrossEncoderModelType

# from asyncflows.scripts.run_transformers_service import DocumentQueryRequest
from asyncflows.utils.transformers_utils import retrieve_indices, rerank_indices


class BaseTransformerInputs(BaseModel):
    model: str
    device: Literal["cpu", "cuda", "mps", "tensorrt"] | None = None
    # TODO use typevar
    documents: list[Any]
    texts: None | list[str] = None
    query: str
    # server_url: None | str
    k: int = 10


class RetrieveInputs(BaseTransformerInputs):
    model: BiEncoderModelType = "sentence-transformers/all-mpnet-base-v2"


class RerankInputs(BaseTransformerInputs):
    model: CrossEncoderModelType = "cross-encoder/ms-marco-TinyBERT-L-2-v2"


class Outputs(BaseModel):
    result: list[Any]


# @tenacity.retry(
#     stop=tenacity.stop_after_attempt(3),
#     wait=tenacity.wait_random_exponential(multiplier=1, max=10),
#     retry=tenacity.retry_if_exception_type(aiohttp.ClientError),
# )
# async def api_call_transformers_service(
#     trace_id: str, query: str, texts: list[str], model: str, k: int, url: str
# ) -> list[int]:
#     async with aiohttp.ClientSession() as session:
#         async with session.post(
#             url,
#             json=DocumentQueryRequest(
#                 trace_id=trace_id,
#                 model=model,
#                 documents=texts,
#                 query=query,
#                 k=k,
#             ).dict(),
#         ) as resp:
#             resp.raise_for_status()
#             return await resp.json()


def get_texts(documents: list[Any], texts: None | list[str]) -> list[str]:
    if texts is None:
        if not all(isinstance(doc, str) for doc in documents):
            raise ValueError(
                "All `documents` must be strings if `texts` is not provided"
            )
        return documents

    if len(texts) != len(documents):
        raise ValueError("`texts` must have the same length as `documents`")

    return texts


class Retrieve(Action[RetrieveInputs, Outputs]):
    name = "retrieve"

    async def run(self, inputs: RetrieveInputs) -> Outputs:
        texts = get_texts(inputs.documents, inputs.texts)

        if not texts:
            self.log.warning("No documents to retrieve")
            return Outputs(result=[])

        # if inputs.server_url is not None:
        #     # call the transformer service
        #     trace_id = self.log._context["trace_id"]
        #     url = urljoin(inputs.server_url, "retrieve")
        #     indices = await api_call_transformers_service(
        #         trace_id=trace_id,
        #         query=inputs.query,
        #         texts=texts,
        #         model=inputs.model,
        #         k=inputs.k,
        #         url=url,
        #     )
        # else:
        # run the transformer in the same process
        indices = await retrieve_indices(
            log=self.log,
            model=inputs.model,
            device=inputs.device,
            documents=texts,
            query=inputs.query,
            k=inputs.k,
        )

        result = [inputs.documents[i] for i in indices]
        return Outputs(result=result)


class Rerank(Action[RerankInputs, Outputs]):
    name = "rerank"

    async def run(self, inputs: RerankInputs) -> Outputs:
        texts = get_texts(inputs.documents, inputs.texts)

        if not texts:
            self.log.warning("No documents to rerank")
            return Outputs(result=[])

        # if inputs.server_url is not None:
        #     # call the transformer service
        #     trace_id = self.log._context["trace_id"]
        #     url = urljoin(inputs.server_url, "rerank")
        #     indices = await api_call_transformers_service(
        #         trace_id=trace_id,
        #         query=inputs.query,
        #         texts=texts,
        #         model=inputs.model,
        #         k=inputs.k,
        #         url=url,
        #     )
        # else:
        # run the transformer in the same process
        indices = await rerank_indices(
            log=self.log,
            model=inputs.model,
            device=inputs.device,
            documents=texts,
            query=inputs.query,
            k=inputs.k,
        )

        result = [inputs.documents[i] for i in indices]
        return Outputs(result=result)

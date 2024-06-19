import asyncio
import os
import typing
import uuid
from hashlib import sha256
from typing_extensions import assert_never

import structlog
from pydantic import PrivateAttr

from asyncflows.models.io import Field, BaseModel
from asyncflows.models.blob import Blob
from asyncflows.repos.blob_repo import BlobRepo
from asyncflows.utils.request_utils import request_read

URL = typing.NewType("URL", str)


class File(BaseModel):
    sources: list[Blob | URL] = Field(
        description="List of blobs or URLs to download the file from"
    )

    _filepath: None | str = PrivateAttr(None)
    _downloading_mutex: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    def __eq__(self, other):
        # mutex does not equal another mutex if they are different objects
        return self.model_dump() == other.model_dump()

    async def hash_file(
        self,
        log: structlog.stdlib.BoundLogger,
        temp_dir: str,
        blob_repo: BlobRepo,
    ) -> str | None:
        filepath = await self.download_file(log, temp_dir, blob_repo)
        if filepath is None:
            return None
        with open(filepath, "rb") as f:
            content = f.read()
            return sha256(content).hexdigest()

    async def _download_file(
        self,
        log: structlog.stdlib.BoundLogger,
        temp_dir: str,
        blob_repo: BlobRepo,
    ) -> str | None:
        if self._filepath is None or not os.path.exists(self._filepath):
            random_id = str(uuid.uuid4())
            file_stem = (
                random_id + ".pdf"
            )  # pdffigures2 fails if it doesn't end in .pdf
            temp_file = os.path.join(temp_dir, random_id, file_stem)
            os.makedirs(temp_file, exist_ok=True)

            for source in self.sources:
                if isinstance(source, Blob):
                    filepath = await blob_repo.download(log, source)
                    break
                elif isinstance(source, str):
                    try:
                        response = await request_read(
                            log,
                            source,
                            timeout=60,
                        )
                    except Exception as e:
                        log.warning("Failed to download file", url=source, error=str(e))
                        continue
                    with open(temp_file, "wb") as f:
                        f.write(response)
                    filepath = temp_file
                    break
                else:
                    assert_never(source)
            else:
                log.error(
                    "Failed to download file from any of the URLs",
                    urls=self.sources,
                )
                return None

            self._filepath = filepath
        return self._filepath

    async def download_file(
        self,
        log: structlog.stdlib.BoundLogger,
        temp_dir: str,
        blob_repo: BlobRepo,
    ) -> str | None:
        async with self._downloading_mutex:
            return await self._download_file(log, temp_dir, blob_repo)


class Paper(File):
    # title: None | str = None
    # doi: None | str = None
    arxiv_id: None | str = None
    biorxiv_id: None | str = None
    homepage_url: None | str = None

import asyncio
import hashlib
import logging
import uuid
from collections import defaultdict
import os

from typing import Optional, Callable

import aioboto3
import structlog
import tenacity
import types_aiobotocore_s3
from boto3.exceptions import Boto3Error
from botocore.exceptions import BotoCoreError

from asyncflows.models.blob import Blob
from asyncflows.utils.async_utils import Timer
from asyncflows.utils.redis_utils import get_aioredis
from asyncflows.utils.secret_utils import get_secret

Value = bytes


class BlobRepo:
    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir
        self.default_namespace = "global"
        self.blob_paths = {}

    async def on_startup(self, log: structlog.stdlib.BoundLogger):
        pass

    async def close(self):
        pass

    async def save(
        self,
        log: structlog.stdlib.BoundLogger,
        value: Value,
        file_extension: None | str = None,
        namespace: None | str = None,
    ) -> Blob:
        if namespace is None:
            namespace = self.default_namespace

        # hash `value` to make an id
        id_ = hashlib.sha256(value).hexdigest()
        blob = Blob(id=id_, file_extension=file_extension)
        if await self.exists(log, blob, namespace):
            return blob

        timer = Timer()
        timer.start()
        blob = await self._save(
            log=log,
            blob=blob,
            value=value,
            namespace=namespace,
        )
        timer.end()
        log.info(
            "Saved blob",
            blob=blob,
            namespace=namespace,
            duration=timer.wall_time,
        )
        return blob

    async def _save(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        value: Value,
        namespace: str,
    ) -> Blob:
        raise NotImplementedError

    async def _extend_ttl(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        raise NotImplementedError

    async def retrieve(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: None | str = None,
    ) -> Optional[Value]:
        if namespace is None:
            namespace = self.default_namespace

        timer = Timer()
        timer.start()
        value = await self._retrieve(log=log, blob=blob, namespace=namespace)
        timer.end()
        log.info(
            "Retrieved blob",
            blob=blob,
            namespace=namespace,
            duration=timer.wall_time,
        )
        return value

    async def _retrieve(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> Optional[Value]:
        raise NotImplementedError

    async def multi_retrieve(
        self,
        log: structlog.stdlib.BoundLogger,
        blobs: list[Blob],
        namespace: None | str = None,
    ) -> list[None | Value]:
        if namespace is None:
            namespace = self.default_namespace
        return await self._multi_retrieve(log, blobs, namespace)

    async def _multi_retrieve(
        self,
        log: structlog.stdlib.BoundLogger,
        blobs: list[Blob],
        namespace: str,
    ) -> list[None | Value]:
        raise NotImplementedError

    async def exists(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: None | str = None,
    ) -> bool:
        if namespace is None:
            namespace = self.default_namespace

        timer = Timer()
        timer.start()
        exists = await self._exists(log, blob, namespace)
        timer.end()
        log.info(
            "Checked blob existence",
            blob=blob,
            namespace=namespace,
            duration=timer.wall_time,
        )
        if exists:
            await self._extend_ttl(log, blob, namespace)
        return exists

    async def _exists(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> bool:
        raise NotImplementedError

    async def download(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: None | str = None,
    ) -> str:
        if namespace is None:
            namespace = self.default_namespace
        id_ = blob.id
        if id_ in self.blob_paths:
            return self.blob_paths[id_]

        timer = Timer()
        timer.start()
        path = await self._download(log, blob, namespace)
        timer.end()
        log.info(
            "Downloaded blob",
            blob=blob,
            namespace=namespace,
            duration=timer.wall_time,
        )

        self.blob_paths[id_] = path
        return path

    async def _download(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> str:
        raise NotImplementedError

    async def delete(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: None | str = None,
    ) -> None:
        if namespace is None:
            namespace = self.default_namespace

        timer = Timer()
        timer.start()
        await self._delete(log, blob, namespace)
        timer.end()
        log.info(
            "Deleted blob",
            blob=blob,
            namespace=namespace,
            duration=timer.wall_time,
        )

    async def _delete(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        # don't actually use this, it's just for testing
        raise NotImplementedError


class InMemoryBlobRepo(BlobRepo):
    _store = defaultdict(dict)

    async def _save(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        value: Value,
        namespace: str,
    ) -> Blob:
        InMemoryBlobRepo._store[namespace][blob.id] = value
        return blob

    async def _extend_ttl(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        pass

    async def _retrieve(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> Optional[Value]:
        return InMemoryBlobRepo._store[namespace].get(blob.id, None)

    async def _multi_retrieve(
        self, log: structlog.stdlib.BoundLogger, blobs: list[Blob], namespace: str
    ) -> list[None | Value]:
        return [InMemoryBlobRepo._store[namespace][blob.id] for blob in blobs]

    async def _exists(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> bool:
        return blob.id in InMemoryBlobRepo._store[namespace]

    async def _download(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> str:
        # save to temp dir
        dir_ = os.path.join(self.temp_dir, "blobs", namespace)
        os.makedirs(dir_, exist_ok=True)
        rand_id = uuid.uuid4().hex
        path = os.path.join(dir_, rand_id)
        if blob.file_extension is not None:
            path += f".{blob.file_extension}"
        with open(path, "wb") as f:
            f.write(InMemoryBlobRepo._store[namespace][blob.id])
        return path

    async def _delete(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        del InMemoryBlobRepo._store[namespace][blob.id]


class RedisBlobRepo(BlobRepo):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = get_aioredis()

    async def close(self):
        await self.redis.aclose()

    async def _save(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        value: Value,
        namespace: str,
    ) -> Blob:
        await self.redis.set(f"blob:{namespace}:{blob.id}", value)
        return blob

    async def _extend_ttl(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        pass

    async def _retrieve(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> Optional[Value]:
        return await self.redis.get(f"blob:{namespace}:{blob.id}")

    async def _multi_retrieve(
        self, log: structlog.stdlib.BoundLogger, blobs: list[Blob], namespace: str
    ) -> list[None | Value]:
        return await self.redis.mget(*[f"blob:{namespace}:{blob.id}" for blob in blobs])

    async def _exists(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> bool:
        return bool(await self.redis.exists(f"blob:{namespace}:{blob.id}"))

    async def _download(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> str:
        # save to temp dir
        dir_ = os.path.join(self.temp_dir, "blobs", namespace)
        os.makedirs(dir_, exist_ok=True)
        rand_id = uuid.uuid4().hex
        path = os.path.join(dir_, rand_id)
        if blob.file_extension is not None:
            path += f".{blob.file_extension}"
        with open(path, "wb") as f:
            f.write(await self.redis.get(f"blob:{namespace}:{blob.id}"))
        return path

    async def _delete(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        await self.redis.delete(f"blob:{namespace}:{blob.id}")


class FilesystemBlobRepo(BlobRepo):
    async def _save(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        value: Value,
        namespace: str,
    ) -> Blob:
        blob_dir = os.path.join(self.temp_dir, "blobs", namespace)
        os.makedirs(blob_dir, exist_ok=True)

        path = os.path.join(blob_dir, blob.id)
        if blob.file_extension is not None:
            path += f".{blob.file_extension}"
        with open(path, "wb") as f:
            f.write(value)
        return blob

    async def _extend_ttl(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        pass

    async def _retrieve(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> Optional[Value]:
        path = os.path.join(self.temp_dir, "blobs", namespace, blob.id)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    async def _multi_retrieve(
        self, log: structlog.stdlib.BoundLogger, blobs: list[Blob], namespace: str
    ) -> list[None | Value]:
        return [await self._retrieve(log, blob, namespace=namespace) for blob in blobs]

    async def _exists(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> bool:
        path = os.path.join(self.temp_dir, "blobs", namespace, blob.id)
        return os.path.exists(path)

    async def _download(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> str:
        dir_ = os.path.join(self.temp_dir, "blobs", namespace)
        os.makedirs(dir_, exist_ok=True)
        path = os.path.join(dir_, blob.id)
        if blob.file_extension is not None:
            path += f".{blob.file_extension}"
        return path

    async def _delete(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        path = os.path.join(self.temp_dir, "blobs", namespace, blob.id)
        os.remove(path)


class S3BlobRepo(BlobRepo):
    # if aioboto3 isn't stable just implement the lower level aiobotocore library

    def __init__(
        self,
        temp_dir: str,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        super().__init__(temp_dir)

        if bucket_name is None:
            bucket_name = os.environ["BUCKET_NAME"]

        if endpoint_url is None and "AWS_ENDPOINT_URL" in os.environ:
            endpoint_url = os.environ["AWS_ENDPOINT_URL"]

        if aws_access_key_id is None:
            aws_access_key_id = get_secret("AWS_ACCESS_KEY_ID")
            if aws_access_key_id is None:
                raise ValueError("AWS_ACCESS_KEY_ID not set")
        if aws_secret_access_key is None:
            aws_secret_access_key = get_secret("AWS_SECRET_ACCESS_KEY")
            if aws_secret_access_key is None:
                raise ValueError("AWS_SECRET_ACCESS_KEY not set")

        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

        self.aioboto3_session: None | aioboto3.Session = None

    async def on_startup(self, log: structlog.stdlib.BoundLogger):
        async with self._get_s3_resource() as s3:
            return await self._wrap_tenacity(
                log,
                s3.meta.client.exceptions.ClientError,
                self.__on_startup,
            )(s3)

    async def __on_startup(
        self,
        s3: types_aiobotocore_s3.S3ServiceResource,
    ):
        bucket = await s3.Bucket(self.bucket_name)

        # create bucket if it doesn't exist
        try:
            await bucket.create()
        except (
            s3.meta.client.exceptions.BucketAlreadyOwnedByYou,
            s3.meta.client.exceptions.BucketAlreadyExists,
        ):
            pass

    async def close(self):
        pass
        # there seems to be nothing to close here?
        # if self.aioboto3_session is not None:
        #     await self.aioboto3_session.close()

    def _wrap_tenacity(
        self,
        log: structlog.stdlib.BoundLogger,
        exception: type[BaseException] | tuple[type[BaseException], ...],
        func: Callable,
    ):
        async def _timeout(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=5)

        if isinstance(exception, tuple):
            exc_tuple = exception
        else:  # isinstance(exception, type):
            exc_tuple = (exception,)

        exc_tuple += (BotoCoreError, Boto3Error, asyncio.TimeoutError)

        return tenacity.retry(
            retry=tenacity.retry_if_exception_type(exc_tuple),
            wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
            stop=tenacity.stop_after_attempt(3),
            before_sleep=tenacity.before_sleep_log(
                log.bind(func=func),  # type: ignore
                logging.WARNING,
                exc_info=True,
            ),
        )(_timeout)

    def _get_s3_resource(self) -> types_aiobotocore_s3.S3ServiceResource:
        if self.aioboto3_session is None:
            self.aioboto3_session = aioboto3.Session()
        return self.aioboto3_session.resource(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

    def _get_s3_client(self) -> types_aiobotocore_s3.S3Client:
        if self.aioboto3_session is None:
            self.aioboto3_session = aioboto3.Session()
        return self.aioboto3_session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

    def _get_object_key(self, blob: Blob, namespace: str):
        object_key = f"{namespace}/{blob.id}"
        if blob.file_extension:
            object_key += f".{blob.file_extension}"
        return object_key

    async def _save(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        value: Value,
        namespace: str,
    ) -> Blob:
        async with self._get_s3_resource() as s3:
            return await self._wrap_tenacity(
                log,
                s3.meta.client.exceptions.ClientError,
                self.__save,
            )(s3, blob, value, namespace)

    async def __save(
        self,
        s3: types_aiobotocore_s3.S3ServiceResource,
        blob: Blob,
        value: Value,
        namespace: str,
    ) -> Blob:
        object_key = self._get_object_key(blob, namespace)

        bucket = await s3.Bucket(self.bucket_name)

        await bucket.put_object(
            Key=object_key,
            Body=value,
        )

        return blob

    async def _extend_ttl(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        # TODO figure out how to check TTL first, else this causes a massive slowdown
        pass
        # object_key = self._get_object_key(blob, namespace)
        #
        # async with self._get_s3_resource() as s3:
        #     obj = await s3.Object(self.bucket_name, object_key)
        #     await obj.load()
        #     await obj.copy_from(
        #         CopySource=f"{self.bucket_name}/{object_key}",
        #         MetadataDirective="REPLACE",
        #     )

    async def _retrieve(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> Optional[Value]:
        async with self._get_s3_resource() as s3:
            return await self._wrap_tenacity(
                log,
                s3.meta.client.exceptions.ClientError,
                self.__retrieve,
            )(s3, blob, namespace)

    async def __retrieve(
        self, s3: types_aiobotocore_s3.S3ServiceResource, blob: Blob, namespace: str
    ) -> Optional[Value]:
        object_key = self._get_object_key(blob, namespace)
        try:
            obj = await s3.Object(self.bucket_name, object_key)
            obj_get = await obj.get()
            return await obj_get["Body"].read()
        except s3.meta.client.exceptions.NoSuchKey:
            return None

    async def _multi_retrieve(
        self, log: structlog.stdlib.BoundLogger, blobs: list[Blob], namespace: str
    ) -> list[Optional[Value]]:
        # Note: aioboto3 does not have native support for multi-object retrieval either
        return [await self.retrieve(log, blob, namespace) for blob in blobs]

    async def _exists(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> bool:
        async with self._get_s3_client() as s3_client:
            return await self._wrap_tenacity(
                log, s3_client.exceptions.ClientError, self.__exists
            )(s3_client, blob, namespace)

    async def __exists(
        self, s3_client: types_aiobotocore_s3.S3Client, blob: Blob, namespace: str
    ) -> bool:
        object_key = self._get_object_key(blob, namespace)

        try:
            await s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except s3_client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                raise

    async def _download(
        self, log: structlog.stdlib.BoundLogger, blob: Blob, namespace: str
    ) -> str:
        value = await self.retrieve(log, blob, namespace)
        if value is None:
            raise ValueError(f"Blob {blob} does not exist")

        dir_ = os.path.join(self.temp_dir, "blobs", namespace)
        os.makedirs(dir_, exist_ok=True)
        local_path = os.path.join(dir_, blob.id)
        if blob.file_extension:
            local_path += f".{blob.file_extension}"
        with open(local_path, "wb") as file:
            file.write(value)
        return local_path

    async def _delete(
        self,
        log: structlog.stdlib.BoundLogger,
        blob: Blob,
        namespace: str,
    ) -> None:
        async with self._get_s3_resource() as s3:
            return await self._wrap_tenacity(
                log, s3.meta.client.exceptions.ClientError, self.__delete
            )(s3, blob, namespace)

    async def __delete(
        self,
        s3: types_aiobotocore_s3.S3ServiceResource,
        blob: Blob,
        namespace: str,
    ) -> None:
        object_key = self._get_object_key(blob, namespace)

        obj = await s3.Object(self.bucket_name, object_key)
        await obj.delete()

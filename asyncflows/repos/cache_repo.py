import asyncio
import logging
import os
import shelve
from datetime import timedelta
from typing import Any

import structlog
import tenacity

from asyncflows.utils.cache_utils import _get_latest_modified_timestamp
from asyncflows.utils.redis_utils import get_aioredis


class CacheRepo:
    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir
        self.default_namespace = "global"

    async def close(self):
        pass

    def _prepare_key(self, key: Any, version: None | int) -> str:
        str_key = str(key)
        if version is None:
            version_modifier = f"t{_get_latest_modified_timestamp()}"
        else:
            version_modifier = f"v{version}"
        return f"{str_key}:{version_modifier}"

    async def store(
        self,
        log: structlog.stdlib.BoundLogger,
        key: Any,
        value: Any,
        version: None | int,
        namespace: None | str = None,
        expire: int | timedelta | None = None,
    ) -> None:
        str_key = self._prepare_key(key, version)
        if namespace is None:
            namespace = self.default_namespace
        await self._store(log, str_key, value, namespace, expire)

    async def _store(
        self,
        log: structlog.stdlib.BoundLogger,
        key: str,
        value: Any,
        namespace: str,
        expire: int | timedelta | None,
    ) -> None:
        raise NotImplementedError()

    async def retrieve(
        self,
        log: structlog.stdlib.BoundLogger,
        key: Any,
        version: None | int,
        namespace: None | str = None,
    ) -> Any | None:
        str_key = self._prepare_key(key, version)
        if namespace is None:
            namespace = self.default_namespace
        return await self._retrieve(log, str_key, namespace)

    async def _retrieve(
        self,
        log: structlog.stdlib.BoundLogger,
        key: Any,
        namespace: str,
    ) -> Any | None:
        raise NotImplementedError()


class ShelveCacheRepo(CacheRepo):
    def _get_shelf_path(self, namespace: str) -> str:
        return os.path.join(self.temp_dir, f"{namespace}.db")

    def _load_shelf(self, namespace: str) -> shelve.Shelf:
        return shelve.open(
            self._get_shelf_path(namespace),
            writeback=True,
        )

    async def _store(
        self,
        log: structlog.stdlib.BoundLogger,
        key: str,
        value: Any,
        namespace: str,
        expire: int | timedelta | None,
    ) -> None:
        shelf = self._load_shelf(namespace)
        shelf[key] = value
        shelf.close()

    async def _retrieve(
        self,
        log: structlog.stdlib.BoundLogger,
        key: str,
        namespace: str,
    ) -> Any | None:
        shelf = self._load_shelf(namespace)
        value = shelf.get(key)
        shelf.close()

        return value


class RedisCacheRepo(CacheRepo):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_client = get_aioredis()

    async def close(self):
        await self.redis_client.close()

    def _wrap_tenacity(self, log: structlog.stdlib.BoundLogger, func):
        async def _timeout(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=5)

        return tenacity.retry(
            retry=tenacity.retry_if_exception_type(
                (ConnectionError, asyncio.TimeoutError)
            ),
            wait=tenacity.wait_random_exponential(multiplier=1, max=5),
            stop=tenacity.stop_after_attempt(3),
            before_sleep=tenacity.before_sleep_log(
                log.bind(func=func),  # type: ignore
                logging.WARNING,
                exc_info=True,
            ),
        )(_timeout)

    async def _store(
        self,
        log: structlog.stdlib.BoundLogger,
        key: str,
        value: Any,
        namespace: str,
        expire: int | timedelta | None,
    ) -> None:
        tenacious_set = self._wrap_tenacity(log, self.redis_client.set)
        await tenacious_set(
            name=f"{namespace}:{key}",
            value=value,
            ex=expire,
        )

    async def _retrieve(
        self,
        log: structlog.stdlib.BoundLogger,
        key: str,
        namespace: str,
    ) -> Any | None:
        tenacious_get = self._wrap_tenacity(log, self.redis_client.get)
        return await tenacious_get(f"{namespace}:{key}")

# import asyncio
# import logging
# import os
# import shelve
# from typing import Optional, Any, Callable
#
# import structlog
# import tenacity
#
# from asyncflows.utils.redis_utils import get_aioredis
#
#
# class CacheRepo:
#     def __init__(self, temp_dir: str):
#         self.temp_dir = temp_dir
#         self.default_namespace = "global"
#
#     async def close(self):
#         pass
#
#     def _prepare_key(self, key: Any) -> str:
#         return str(key)
#
#     async def store(
#         self,
#         log: structlog.stdlib.BoundLogger,
#         key: Any,
#         value: Any,
#         namespace: Optional[str] = None,
#     ) -> None:
#         str_key = self._prepare_key(key)
#         if namespace is None:
#             namespace = self.default_namespace
#         await self._store(log, str_key, value, namespace)
#
#     async def _store(
#         self,
#         log: structlog.stdlib.BoundLogger,
#         key: str,
#         value: Any,
#         namespace: str,
#     ) -> None:
#         raise NotImplementedError()
#
#     async def retrieve(
#         self,
#         log: structlog.stdlib.BoundLogger,
#         key: Any,
#         namespace: Optional[str] = None,
#     ) -> Optional[Any]:
#         str_key = self._prepare_key(key)
#         if namespace is None:
#             namespace = self.default_namespace
#         return await self._retrieve(log, str_key, namespace)
#
#     async def _retrieve(
#         self,
#         log: structlog.stdlib.BoundLogger,
#         key: Any,
#         namespace: str,
#     ) -> Optional[Any]:
#         raise NotImplementedError()
#
#
# class ShelveCacheRepo(CacheRepo):
#     def _get_shelf_path(self, namespace: str) -> str:
#         return os.path.join(self.temp_dir, f"{namespace}.db")
#
#     def _load_shelf(self, namespace: str) -> shelve.Shelf:
#         return shelve.open(
#             self._get_shelf_path(namespace),
#             writeback=True,
#         )
#
#     async def _store(
#         self,
#         log: structlog.stdlib.BoundLogger,
#         key: str,
#         value: Any,
#         namespace: str,
#     ) -> None:
#         shelf = self._load_shelf(namespace)
#         shelf[key] = value
#         shelf.close()
#
#     async def _retrieve(
#         self,
#         log: structlog.stdlib.BoundLogger,
#         key: str,
#         namespace: str,
#     ) -> Optional[Any]:
#         shelf = self._load_shelf(namespace)
#         value = shelf.get(key)
#         shelf.close()
#
#         return value
#
#
# class RedisCacheRepo(CacheRepo):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.redis_client = get_aioredis()
#
#     async def close(self):
#         await self.redis_client.close()
#
#     def _wrap_tenacity(self, log: structlog.stdlib.BoundLogger, func):
#         return tenacity.retry(
#             retry=tenacity.retry_if_exception_type((ConnectionError, asyncio.CancelledError)),
#             wait=tenacity.wait_random_exponential(multiplier=1, max=5),
#             stop=tenacity.stop_after_attempt(3),
#             before_sleep=tenacity.before_sleep_log(log, logging.DEBUG, exc_info=True),  # type: ignore
#         )(func)
#
#     async def _store(
#         self,
#         log: structlog.stdlib.BoundLogger,
#         key: str,
#         value: Any,
#         namespace: str,
#     ) -> None:
#         timeout_set = asyncio.wait_for(
#             self.redis_client.set(f"{namespace}:{key}", value),
#             timeout=5,
#         )
#         tenacious_set = self._wrap_tenacity(log, timeout_set)
#         await tenacious_set()
#
#     async def _retrieve(
#         self,
#         log: structlog.stdlib.BoundLogger,
#         key: str,
#         namespace: str,
#     ) -> Optional[Any]:
#         timeout_get = asyncio.wait_for(
#             self.redis_client.get(f"{namespace}:{key}"),
#             timeout=5,
#         )
#         tenacious_get = self._wrap_tenacity(log, timeout_get)
#         return await tenacious_get()
import os
from unittest.mock import MagicMock, ANY, patch

import pytest
import tenacity

from asyncflows.repos.cache_repo import RedisCacheRepo


async def test_save_retrieve(log, cache_repo):
    key = "test-key"
    value = "test-value"
    await cache_repo.store(log, key, value, None)
    retrieved_value = await cache_repo.retrieve(log, key, None)
    assert retrieved_value == value


async def test_save_retrieve_versions(log, cache_repo):
    versions = [None, 1, 2]
    key = "test-key"
    value = "test-value"

    for version in versions:
        await cache_repo.store(log, key, value, version)
        retrieved_value = await cache_repo.retrieve(log, key, version)
        assert retrieved_value == value
    for version in versions:
        retrieved_value = await cache_repo.retrieve(log, key, version)
        assert retrieved_value == value


@pytest.fixture
def mock_redis_cache_repo(temp_dir, blocking_func):
    redis_host_bak = os.environ.get("REDIS_HOST")
    os.environ["REDIS_HOST"] = "localhost"
    redis_password_bak = os.environ.get("REDIS_PASSWORD")
    os.environ["REDIS_PASSWORD"] = "password"

    yield RedisCacheRepo(
        temp_dir=temp_dir,
    )

    if redis_host_bak is not None:
        os.environ["REDIS_HOST"] = redis_host_bak
    else:
        del os.environ["REDIS_HOST"]
    if redis_password_bak is not None:
        os.environ["REDIS_PASSWORD"] = redis_password_bak
    else:
        del os.environ["REDIS_PASSWORD"]


@pytest.fixture
async def block_redis(blocking_func):
    get_aioredis_mock = MagicMock()
    get_aioredis_mock.return_value.set = blocking_func
    get_aioredis_mock.return_value.get = blocking_func

    with patch("asyncflows.repos.cache_repo.get_aioredis", get_aioredis_mock):
        yield get_aioredis_mock


async def test_timeout(
    log,
    log_history,
    blocking_func,
    block_redis,
    mock_wait_for,
    mock_tenacity,
    mock_redis_cache_repo,
):
    with pytest.raises(tenacity.RetryError):
        await mock_redis_cache_repo.store(log, "test-key", "test-value", None)
    with pytest.raises(tenacity.RetryError):
        await mock_redis_cache_repo.retrieve(log, "test-key", None)

    assert len(log_history) == 4
    for log_entry in log_history:
        assert log_entry == {
            "event": "Retrying asyncflows.repos.cache_repo.RedisCacheRepo._wrap_tenacity.<locals>._timeout in 0.0 seconds as it raised TimeoutError: .",
            "exc_info": ANY,
            "log_level": "warning",
            "func": blocking_func,
        }

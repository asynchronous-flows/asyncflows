import os
import typing

from redis import asyncio as aioredis
import pydantic

from asyncflows.utils.secret_utils import get_secret

T = typing.TypeVar("T", bound=pydantic.BaseModel)


aioredis_client = None


def get_redis_port() -> int:
    return int(os.environ.get("REDIS_PORT", 6379))


def get_redis_username() -> str | None:
    return os.environ.get("REDIS_USERNAME", None)


def get_redis_url() -> str:
    host = get_secret("REDIS_HOST")
    if host is None:
        raise ValueError("REDIS_HOST is not set")
    port = get_redis_port()
    username = get_redis_username()
    if username is None:
        username = ""
    password = get_secret("REDIS_PASSWORD")
    if password is None:
        raise ValueError("REDIS_PASSWORD is not set")

    return f"redis://{username}:{password}@{host}:{port}"


def load_aioredis():
    host = get_secret("REDIS_HOST")
    if host is None:
        raise ValueError("REDIS_HOST is not set")
    port = get_redis_port()
    username = get_redis_username()
    password = get_secret("REDIS_PASSWORD")
    if password is None:
        raise ValueError("REDIS_PASSWORD is not set")
    return aioredis.Redis(
        host=host,
        port=port,
        password=password,
        username=username,
    )


def get_aioredis():
    global aioredis_client
    # TODO use a redis connection pool
    if aioredis_client is None or aioredis_client.connection is None:
        aioredis_client = load_aioredis()
    return aioredis_client

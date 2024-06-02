import pytest
from sqlalchemy import URL
from sqlalchemy.util import immutabledict

from asyncflows.utils.db_utils import get_async_db_url, get_sync_db_url


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "postgresql://localhost",
            # "postgresql+asyncpg://localhost"
            URL(
                drivername="postgresql+asyncpg",
                username=None,
                password=None,
                host="localhost",
                port=None,
                database=None,
                query=immutabledict(),
            ),
        ),
        (
            "sqlite:///:memory:",
            URL(
                drivername="sqlite+aiosqlite",
                username=None,
                password=None,
                host=None,
                port=None,
                database=":memory:",
                query=immutabledict(),
            ),
        ),
        (
            "sqlite:///dummy.db",
            URL(
                drivername="sqlite+aiosqlite",
                username=None,
                password=None,
                host=None,
                port=None,
                database="dummy.db",
                query=immutabledict(),
            ),
        ),
    ],
)
def test_get_async_url(url, expected):
    assert get_async_db_url(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "postgresql+asyncpg://localhost",
            URL(
                drivername="postgresql",
                username=None,
                password=None,
                host="localhost",
                port=None,
                database=None,
                query=immutabledict(),
            ),
        ),
        (
            "sqlite+aiosqlite:///:memory:",
            URL(
                drivername="sqlite",
                username=None,
                password=None,
                host=None,
                port=None,
                database=":memory:",
                query=immutabledict(),
            ),
        ),
        (
            "sqlite+aiosqlite:///dummy.db",
            URL(
                drivername="sqlite",
                username=None,
                password=None,
                host=None,
                port=None,
                database="dummy.db",
                query=immutabledict(),
            ),
        ),
    ],
)
def test_get_sync_url(url, expected):
    assert get_sync_db_url(url) == expected

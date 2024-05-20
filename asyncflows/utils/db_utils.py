from urllib.parse import urlparse


def get_async_db_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme == "sqlite":
        aiosqlite_url = parsed._replace(scheme="aiosqlite")
        return aiosqlite_url.geturl()
    if parsed.scheme == "postgresql":
        asyncpg_url = parsed._replace(scheme="postgresql+asyncpg")
        return asyncpg_url.geturl()
    return url


def get_sync_db_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme == "aiosqlite":
        sqlite_url = parsed._replace(scheme="sqlite")
        return sqlite_url.geturl()
    if parsed.scheme == "postgresql+asyncpg":
        asyncpg_url = parsed._replace(scheme="postgresql")
        return asyncpg_url.geturl()
    return url

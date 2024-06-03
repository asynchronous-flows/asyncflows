def get_async_db_url(url: str):
    from sqlalchemy import make_url

    parsed = make_url(url)
    if parsed.drivername == "sqlite":
        aiosqlite_url = parsed._replace(drivername="sqlite+aiosqlite")
        return aiosqlite_url
    if parsed.drivername == "postgresql":
        asyncpg_url = parsed._replace(drivername="postgresql+asyncpg")
        return asyncpg_url
    return parsed


def get_sync_db_url(url: str):
    from sqlalchemy import make_url

    parsed = make_url(url)
    if parsed.drivername == "sqlite+aiosqlite":
        sqlite_url = parsed._replace(drivername="sqlite")
        return sqlite_url
    if parsed.drivername == "postgresql+asyncpg":
        asyncpg_url = parsed._replace(drivername="postgresql")
        return asyncpg_url
    return parsed

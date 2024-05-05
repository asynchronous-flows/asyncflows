import logging

import aiohttp
import structlog
import tenacity


async def request_read(
    log: structlog.stdlib.BoundLogger,
    url: str,
    method: str = "GET",
    fields: None | list[dict] = None,
    **kwargs,
) -> bytes:
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(aiohttp.ClientError),
        wait=tenacity.wait_random_exponential(multiplier=1, max=5),
        stop=tenacity.stop_after_attempt(5),
        before_sleep=tenacity.before_sleep_log(
            log,  # type: ignore
            logging.WARNING,
            exc_info=True,
        ),
    )
    async def make_request():
        if not fields:
            data = None
        else:
            data = aiohttp.FormData()
            for f in fields:
                data.add_field(**f)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method, url=url, data=data, **kwargs
            ) as resp:
                if resp.status != 200:
                    log.warning(
                        "Non-200 status code",
                        status=resp.status,
                        url=url,
                        response=resp,
                    )
                    raise aiohttp.ClientError(f"Non-200 status code {resp.status}")
                return await resp.read()

    return await make_request()


async def request_text(
    log: structlog.stdlib.BoundLogger,
    url: str,
    method: str = "GET",
    fields: None | list[dict] = None,
    **kwargs,
) -> str:
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(aiohttp.ClientError),
        wait=tenacity.wait_random_exponential(multiplier=1, max=5),
        stop=tenacity.stop_after_attempt(5),
        before_sleep=tenacity.before_sleep_log(
            log,  # type: ignore
            logging.WARNING,
            exc_info=True,
        ),
    )
    async def make_request():
        if not fields:
            data = None
        else:
            data = aiohttp.FormData()
            for f in fields:
                data.add_field(**f)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method, url=url, data=data, **kwargs
            ) as resp:
                if resp.status != 200:
                    log.warning(
                        "Non-200 status code",
                        status=resp.status,
                        url=url,
                        response=resp,
                    )
                    raise aiohttp.ClientError(f"Non-200 status code {resp.status}")
                return await resp.text()

    return await make_request()

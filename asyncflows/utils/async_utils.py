import asyncio
import time
from asyncio import CancelledError
from typing import TypeVar, AsyncIterator, Awaitable, Sequence

import sentry_sdk
import structlog

T = TypeVar("T")
IdType = TypeVar("IdType")
OutputType = TypeVar("OutputType")


class LagMonitor:
    def __init__(
        self,
        log: structlog.stdlib.BoundLogger,
        interval: float = 0.5,
        lag_threshold: float = 0.3,
    ):
        self.log = log
        self.interval = interval
        self.lag_threshold = lag_threshold
        self.task = None

    def start(self):
        loop = asyncio.get_running_loop()
        self.task = loop.create_task(self._loop_monitor(loop))

    def stop(self):
        if self.task is None:
            raise RuntimeError("LagMonitor not started")
        self.task.cancel()

    async def _loop_monitor(self, loop: asyncio.AbstractEventLoop):
        while loop.is_running():
            start = loop.time()

            await asyncio.sleep(self.interval)

            time_elapsed = loop.time() - start
            lag = time_elapsed - self.interval
            if lag > self.lag_threshold:
                self.log.warning(
                    "Event loop lagging",
                    lag=lag,
                )


async def merge_iterators(
    log: structlog.stdlib.BoundLogger,
    ids: Sequence[IdType],
    coros: list[AsyncIterator[OutputType]],
) -> AsyncIterator[tuple[IdType, OutputType | None]]:
    async def worker(
        aiter: AsyncIterator[OutputType], iterator_id: IdType, queue: asyncio.Queue
    ):
        try:
            async for value in aiter:
                await queue.put((False, (iterator_id, value)))
        except Exception as exc:
            # If an exception occurs, send it through the queue
            await queue.put((True, (iterator_id, exc)))
        finally:
            # Notify the main loop that this coroutine is done
            await queue.put(None)

    queue = asyncio.Queue()
    workers = []  # List to keep track of worker tasks.

    try:
        for id_, aiter in zip(ids, coros):
            worker_task = asyncio.create_task(worker(aiter, id_, queue))
            workers.append(worker_task)

        remaining_workers = len(workers)
        while remaining_workers > 0:
            result = await queue.get()
            if result is None:
                # One coroutine has finished.
                remaining_workers -= 1
                continue

            # A result or an exception was received.
            exception_raised, (id_, value_or_exc) = result
            if exception_raised:
                log.exception(
                    "Exception raised in worker",
                    id=id_,
                    exc_info=value_or_exc,
                )
                sentry_sdk.capture_exception(value_or_exc)
                # yield id_, None
                # If any exception is received, cancel all workers and raise the exception.
                # for worker_task in workers:
                #     worker_task.cancel()
                # await asyncio.gather(*workers, return_exceptions=True)
                # raise value_or_exc
            else:
                # Yield the result.
                try:
                    yield id_, value_or_exc
                except GeneratorExit:
                    log.warning(
                        "Generator exited",
                        id=id_,
                    )
                except CancelledError:
                    log.warning(
                        "Generator cancelled",
                        id=id_,
                    )
    finally:
        for worker_task in workers:
            worker_task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


async def iterator_to_coro(async_iterator: AsyncIterator[T | None]) -> T | None:
    output = None
    async for output in async_iterator:
        pass
    return output


class Timer:
    def __init__(self):
        self.blocking_time = 0
        self.blocking_start_time = None
        self.wall_start_time = 0
        self.wall_end_time = 0

    def start(self):
        now = time.monotonic()
        if not self.wall_start_time:
            self.wall_start_time = now
        self.blocking_start_time = time.perf_counter()

    def end(self):
        self.wall_end_time = time.monotonic()
        if self.blocking_start_time is None:
            return
        end_perf_counter = time.perf_counter()
        self.blocking_time += end_perf_counter - self.blocking_start_time
        self.blocking_start_time = None

    @property
    def wall_time(self):
        # if self.wall_end_time is None or self.wall_start_time is None:
        #     raise RuntimeError("Timer not yet started")
        return self.wall_end_time - self.wall_start_time


async def measure_coro(
    log: structlog.stdlib.BoundLogger,
    f: Awaitable[T],
    timer: Timer,
    timeout: float = 180,
) -> T:
    coro_wrapper = f.__await__()
    arg = None
    exc = None
    fut = None
    first_run = True

    while True:
        try:
            if first_run:
                first_run = False
            elif fut is None:
                log.debug(
                    "Coroutine returned None",
                    arg=arg,
                )
                try:
                    await asyncio.sleep(0)
                except asyncio.CancelledError:
                    log.debug(
                        "Subcoroutine cancelled during bare yield",
                        arg=arg,
                    )
            else:
                try:
                    arg = await asyncio.wait_for(fut, timeout=timeout)
                    log.debug(
                        "Subcoroutine finished",
                        # result=arg,
                    )
                except asyncio.TimeoutError as e:
                    log.error(
                        "Subcoroutine timed out",
                        arg=arg,
                        exc_info=e,
                    )
                    raise
                except asyncio.CancelledError:
                    log.debug(
                        "Subcoroutine cancelled during wait",
                        arg=arg,
                        # exc_info=e,
                    )
                    # fut.set_exception(e)
                except Exception as e:
                    log.debug(
                        "Subcoroutine raised exception",
                        arg=arg,
                        # exc_info=e,
                    )
                    exc = e
            timer.start()
            if exc is not None:
                fut = coro_wrapper.throw(exc)
                exc = None
            else:
                fut = coro_wrapper.send(arg)
        except StopIteration as e:
            return e.value
        finally:
            timer.end()
            arg = None


async def measure_async_iterator(
    log: structlog.stdlib.BoundLogger,
    f: AsyncIterator[T],
    timer: Timer,
    timeout: float = 180,
) -> AsyncIterator[T]:
    iter_wrapper = f.__aiter__()
    while True:
        try:
            yield await measure_coro(
                log,
                iter_wrapper.__anext__(),
                timer,
                timeout,
            )
        except StopAsyncIteration:
            break
        # except Exception:
        #     raise
    # iter_wrapper = f.__aiter__()
    # out = sentinel = object()
    # while True:
    #     try:
    #         if out is not sentinel:
    #             # it still thinks this is an `object()` and not a `T`
    #             yield out  # type: ignore
    #         # timer.start()
    #         out = await measure_coro(
    #             log,
    #             iter_wrapper.__anext__(),
    #             timer,
    #         )
    #     except StopAsyncIteration:
    #         break
    #     except Exception:
    #         raise
    # finally:
    #     timer.end()
    #     timer.start()
    #     try:
    #         # TODO this does not measure blocking time properly;
    #         #  it could also yield within f to other coroutines and it would get counted as part of f's blocking time
    #         async for out in f:
    #             timer.end()
    #             yield out
    #             timer.start()
    #     except Exception:
    #         # fut.set_exception(e)
    #         # break
    #         raise
    #     finally:
    #         timer.end()

    # async def wrapper(*args, **kwargs):
    #     async_gen = f(*args, **kwargs).__aiter__()
    #
    #     while True:
    #         timer.start()
    #         # Attempt to yield the next value from the async generator
    #         try:
    #             yield await async_gen.asend(None)
    #         except StopAsyncIteration:
    #             # If no more values are available, break the loop
    #             break
    #         except Exception as e:
    #             # If an exception occurs, send it back to the async generator
    #             yield async_gen.athrow(e)
    #         finally:
    #             timer.end()
    #
    # return wrapper

    # write iterator in same style as  measure_coro

    # async_gen = f.__aiter__()
    # arg = None
    #
    # while True:
    #     try:
    #         timer.start()
    #         fut = await async_gen.asend(arg)
    #         if fut is None:
    #             log.debug(
    #                 "Coroutine returned None",
    #                 async_gen=async_gen,
    #                 arg=arg,
    #             )
    #             await asyncio.sleep(0)
    #         else:
    #             arg = await asyncio.wait([fut], timeout=120)
    #     except StopIteration as e:
    #         return e.value
    #     except Exception as e:
    #         # fut.set_exception(e)
    #         # break
    #         raise
    #     finally:
    #         timer.end()

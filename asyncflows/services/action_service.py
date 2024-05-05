import asyncio
from collections import defaultdict
from typing import Any, AsyncIterator

import sentry_sdk
import structlog
from pydantic import BaseModel, RootModel, ValidationError

from asyncflows.actions import get_actions_dict
from asyncflows.actions.base import (
    StreamingAction,
    InternalActionBase,
    Action,
    CacheControlOutputs,
    FinalInvocationInputs,
    BlobRepoInputs,
    DefaultModelInputs,
    RedisUrlInputs,
)
from asyncflows.models.blob import Blob
from asyncflows.models.config.action import ActionInvocation
from asyncflows.models.config.transform import TransformsInto
from asyncflows.models.config.value_declarations import (
    TextDeclaration,
    ValueDeclaration,
)
from asyncflows.models.config.action import ActionConfig
from asyncflows.models.primitives import ExecutableName, ExecutableId

from asyncflows.repos.blob_repo import BlobRepo

from asyncflows.repos.cache_repo import CacheRepo
from asyncflows.utils.async_utils import (
    merge_iterators,
    iterator_to_coro,
    Timer,
    measure_coro,
    measure_async_iterator,
)
from asyncflows.utils.redis_utils import get_redis_url
from asyncflows.utils.sentinel_utils import is_sentinel, Sentinel, is_set_of_tuples

ActionSubclass = InternalActionBase[Any, Any]
Inputs = Outputs = BaseModel


class ActionService:
    # class Finished(Action):
    #     id = "finished"

    def __init__(
        self,
        temp_dir: str,
        use_cache: bool,
        cache_repo: CacheRepo,
        blob_repo: BlobRepo,
        config: ActionConfig,
    ):
        self.temp_dir = temp_dir
        self.use_cache = use_cache
        self.cache_repo = cache_repo
        self.blob_repo = blob_repo
        self.config = config

        self.tasks: dict[str, asyncio.Task] = {}
        self.action_output_broadcast: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self.new_listeners: dict[str, list[asyncio.Queue]] = defaultdict(list)

        # Load all actions in the `asyncflows/actions` directory
        self.actions: dict[ExecutableName, type[ActionSubclass]] = get_actions_dict()
        # This relies on using a separate action instance for each trace_id
        self.action_cache: dict[ExecutableId, ActionSubclass] = {}

    def get_action_type(self, name: ExecutableName) -> type[ActionSubclass]:
        if name in self.actions:
            return self.actions[name]
        raise ValueError(f"Unknown action: {name}")

    def _get_action_instance(
        self, log: structlog.stdlib.BoundLogger, action_id: ExecutableId
    ) -> ActionSubclass:
        if action_id in self.action_cache:
            return self.action_cache[action_id]
        action_config = self.config.flow[action_id]
        action_name = action_config.action
        action_type = self.get_action_type(action_name)

        action = action_type(
            log=log,
            temp_dir=self.temp_dir,
        )
        self.action_cache[action_id] = action
        return action

    async def _run_action(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        inputs: Inputs | None,
    ) -> AsyncIterator[Outputs | None]:
        # Prepare inputs
        if isinstance(inputs, RedisUrlInputs):
            inputs._redis_url = get_redis_url()
        if isinstance(inputs, BlobRepoInputs):
            inputs._blob_repo = self.blob_repo
        if isinstance(inputs, DefaultModelInputs):
            inputs._default_model = self.config.default_model

        # Get the action instance
        action = self._get_action_instance(log, action_id)
        if not isinstance(inputs, action._get_inputs_type()):
            raise ValueError(
                f"Inputs type mismatch: {type(inputs)} != {action._get_inputs_type()}"
            )

        # measure blocking time and wall clock time

        timer = Timer()

        # Run the action
        log.info(
            "Action started",
            # inputs=inputs,
        )
        try:
            if isinstance(action, StreamingAction):
                async for outputs in measure_async_iterator(
                    log,
                    action.run(inputs),
                    timer,
                ):
                    # async for outputs in action.run(inputs):
                    log.debug(
                        "Yielding outputs",
                        partial=True,
                        # outputs=outputs,
                    )
                    yield outputs
            elif isinstance(action, Action):
                result = await measure_coro(log, action.run(inputs), timer)
                log.debug(
                    "Yielding outputs",
                    partial=False,
                    # outputs=result,
                )
                yield result
            else:
                raise ValueError(f"Unknown action type: {type(action)}")
        except Exception as e:
            log.exception("Action exception", exc_info=True)
            sentry_sdk.capture_exception(e)
            yield None
        finally:
            log.info(
                "Action finished",
                wall_time=timer.wall_time,
                blocking_time=timer.blocking_time,
            )

    async def _contains_expired_blobs(
        self,
        log: structlog.stdlib.BoundLogger,
        output: Any,
    ):
        if isinstance(output, Blob):
            try:
                return not await self.blob_repo.exists(log, output)
            except Exception as e:
                log.exception("Blob existence check error", exc_info=True)
                sentry_sdk.capture_exception(e)
                return True

        if isinstance(output, BaseModel):
            return any(
                await asyncio.gather(
                    *[
                        self._contains_expired_blobs(log, field_value)
                        for field_value in output.__dict__.values()
                    ]
                )
            )
        elif isinstance(output, list):
            return any(
                await asyncio.gather(
                    *[self._contains_expired_blobs(log, item) for item in output]
                )
            )
        elif isinstance(output, dict):
            return any(
                await asyncio.gather(
                    *[
                        self._contains_expired_blobs(log, value)
                        for value in output.values()
                    ]
                )
            )

        return False

    @classmethod
    def _get_dependency_ids_and_stream_flag_from_input_spec(
        cls,
        input_spec: Any,
    ) -> set[tuple[ExecutableId, bool]]:
        dependencies = set()
        if isinstance(input_spec, dict):
            for key, value in input_spec.items():
                dependencies.update(
                    cls._get_dependency_ids_and_stream_flag_from_input_spec(value)
                )
        elif isinstance(input_spec, list):
            for value in input_spec:
                dependencies.update(
                    cls._get_dependency_ids_and_stream_flag_from_input_spec(value)
                )
        elif isinstance(input_spec, str):
            template = TextDeclaration(text=input_spec)
            dependencies.update(
                (d, template.stream) for d in template.get_dependencies()
            )
        elif isinstance(input_spec, (ValueDeclaration, str)):
            dependencies.update(
                (d, input_spec.stream) for d in input_spec.get_dependencies()
            )
        if isinstance(input_spec, BaseModel):
            for field_name in input_spec.model_fields:
                field_value = getattr(input_spec, field_name)
                dependencies.update(
                    cls._get_dependency_ids_and_stream_flag_from_input_spec(field_value)
                )

        return dependencies

    async def _collect_inputs_from_context(
        self,
        log: structlog.stdlib.BoundLogger,
        input_spec: Any,
        context: dict[
            ExecutableId | str, Any | Outputs
        ],  # typehint for verbosity, merged variables and outputs
    ):
        value = input_spec
        if isinstance(value, list):
            return [
                await self._collect_inputs_from_context(log, v, context=context)
                for v in value
            ]
        if isinstance(value, dict):
            return {
                k: await self._collect_inputs_from_context(log, v, context=context)
                for k, v in value.items()
            }
        if isinstance(value, TransformsInto):
            return await value.transform_from_config(log, context=context)
        if isinstance(value, RootModel):
            value = value.root
        if isinstance(value, str):
            value = TextDeclaration(text=value)
        if isinstance(value, ValueDeclaration):
            value = await value.render(context)
        if isinstance(value, BaseModel):
            fields = {}
            for field_name in value.model_fields:
                field_value = getattr(value, field_name)
                fields[field_name] = await self._collect_inputs_from_context(
                    log, field_value, context=context
                )
            value = fields
        return value

    async def stream_dependencies(
        self,
        log: structlog.stdlib.BoundLogger,
        dependencies: set[tuple[ExecutableId, bool]],
        variables: dict[str, Any],
    ) -> AsyncIterator[dict[ExecutableId, Outputs] | type[Sentinel]]:
        action_dependencies = {d for d in dependencies if d[0] in self.config.flow}
        extra_dependency_ids = {
            d[0]
            for d in dependencies
            if d not in action_dependencies and d[0] not in variables
        }
        if extra_dependency_ids:
            log.error(
                "Unknown dependencies, replacing with None",
                dependency_ids=extra_dependency_ids,
            )
            for id_ in extra_dependency_ids:
                variables[id_] = None

        async for dependency_outputs in self.stream_action_tasks(
            log, action_dependencies, variables
        ):
            yield dependency_outputs

    async def stream_input_dependencies(
        self,
        log: structlog.stdlib.BoundLogger,
        action_config: ActionInvocation,
        variables: dict[str, Any],
    ) -> AsyncIterator[Inputs | None | type[Sentinel]]:
        # Get action type
        action_type = self.get_action_type(action_config.action)
        inputs_type = action_type._get_inputs_type()
        if isinstance(None, inputs_type):
            yield None
            return

        input_spec = {
            key: getattr(action_config, key)
            for key in action_config.model_fields
            if key not in ("id", "action") and getattr(action_config, key) is not None
        }

        # FIXME remove this,
        #  unnecessary since all strings are interpreted as templates in _dependency_ids_from_input_spec
        # for key, value in input_spec.items():
        #     if isinstance(value, str):
        #         value = TemplateDeclaration(text=value)
        #     input_spec[key] = value

        dependencies = self._get_dependency_ids_and_stream_flag_from_input_spec(
            input_spec
        )
        if not dependencies:
            rendered = await self._collect_inputs_from_context(
                log,
                input_spec=input_spec,
                context=variables,
            )
            try:
                yield inputs_type.model_validate(rendered)
            except Exception as e:
                log.exception(
                    "Invalid inputs",
                    exc_info=True,
                    inputs_dict=rendered,
                )
                sentry_sdk.capture_exception(e)
            return

        async for dependency_outputs in self.stream_dependencies(
            log, dependencies, variables
        ):
            if is_sentinel(dependency_outputs):
                # propagate error
                yield Sentinel
                return
            # Compile the inputs
            context = dependency_outputs | variables
            inputs_dict = await self._collect_inputs_from_context(
                log,
                input_spec=input_spec,
                context=context,
            )
            try:
                yield inputs_type.model_validate(inputs_dict)
            except Exception as e:
                log.exception(
                    "Invalid inputs",
                    exc_info=True,
                    inputs_dict=inputs_dict,
                )
                sentry_sdk.capture_exception(e)

    async def stream_action_tasks(
        self,
        log: structlog.stdlib.BoundLogger,
        dependencies: set[tuple[ExecutableId, bool]] | set[ExecutableId],
        variables: None | dict[str, Any] = None,
    ) -> AsyncIterator[dict[ExecutableId, Outputs] | type[Sentinel]]:
        if variables is None:
            variables = {}

        if not dependencies:
            yield {}
            return

        if is_set_of_tuples(dependencies):
            action_ids = {id_ for id_, _ in dependencies}
            stream_flags = [
                not any(id_ == action_id and not stream for id_, stream in dependencies)
                for action_id in action_ids
            ]
        else:
            action_ids = dependencies
            stream_flags = [True for _ in action_ids]

        if len(action_ids) != len(stream_flags):
            log.error(
                "Length mismatch between action_ids and stream_flags",
                action_ids=action_ids,
                stream_flags=stream_flags,
            )
            yield Sentinel

        merged_iterator = merge_iterators(
            log,
            action_ids,
            [
                self.stream_action(
                    log=log,
                    action_id=id_,
                    variables=variables,
                    partial=stream,
                )
                for id_, stream in zip(action_ids, stream_flags)
            ],
        )

        log = log.bind(action_task_ids=action_ids)
        dependency_outputs = {}
        async for action_id, action_outputs in merged_iterator:
            # None is yielded as action_outputs if an action throws an exception
            # if action_outputs is None:
            #     raise RuntimeError(f"{action_id} returned None")

            # if action_outputs is not None:
            #     # TODO consider parity with `stream_action` in returning a model instead of a dict
            #     action_outputs = action_outputs.model_dump()
            dependency_outputs[action_id] = action_outputs

            # TODO do we need more fine grained controls on what actions need to return?
            if all(action_id in dependency_outputs for action_id in action_ids):
                log.debug("Yielding combined action task results")
                yield dependency_outputs
            else:
                log.debug(
                    "Action task results received, waiting for other actions to complete",
                    received_action_id=action_id,
                )
        if not all(action_id in dependency_outputs for action_id in action_ids):
            log.error(
                "Not all action tasks completed",
                missing_action_ids=action_ids - set(dependency_outputs.keys()),
            )
            yield Sentinel

    def _broadcast_outputs(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        outputs: Outputs | None | type[Sentinel],
        queues: list[asyncio.Queue] | None = None,
    ):
        if queues is None:
            queues = self.action_output_broadcast[action_id]

        # Broadcast outputs
        new_listeners_queues = self.new_listeners[action_id]
        for queue in queues[:]:
            # TODO should we only ever leave one output in queue? or should we just let the subscriber handle partials?
            #  pro: badly written actions will work better/faster
            #  con: it makes it less deterministic and makes tests slightly harder to write
            # if outputs is not sentinel and not queue.empty():
            #     # the subscriber only cares about the most recent outputs
            #     log.debug("Clearing queue")
            #     queue.get_nowait()
            queue.put_nowait(outputs)
            if queue in new_listeners_queues:
                new_listeners_queues.remove(queue)

    async def _check_cache(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        cache_key: Any,
    ) -> None | Outputs:
        action_config = self.config.flow[action_id]
        action_name = action_config.action
        action_type = self.get_action_type(action_name)

        if self.use_cache and action_type.cache:
            log.debug("Checking cache")
            try:
                outputs_json = await self.cache_repo.retrieve(
                    log, cache_key, namespace=action_name, version=action_type.version
                )
            except Exception as e:
                log.warning(
                    "Cache retrieve error",
                    exc_info=e,
                )
                outputs_json = None
            if outputs_json is not None:
                outputs_type: BaseModel = action_type._get_outputs_type()
                try:
                    outputs = outputs_type.model_validate_json(outputs_json)
                    if not await self._contains_expired_blobs(log, outputs):
                        log.info("Cache hit")
                        return outputs
                    else:
                        log.info("Cache hit but blobs expired")
                except ValidationError as e:
                    log.warning(
                        "Cache hit but outputs invalid",
                        exc_info=e,
                    )
            else:
                log.info("Cache miss")
        else:
            log.debug(
                "Cache disabled",
                global_cache_flag=self.use_cache,
                action_cache_flag=action_type.cache,
            )

        return None

    async def _resolve_cache_key(
        self,
        log: structlog.stdlib.BoundLogger,
        action_config: ActionInvocation,
        variables: dict[str, Any],
    ) -> str | type[Sentinel] | None:
        if action_config.cache_key is None:
            return None
        dependencies = self._get_dependency_ids_and_stream_flag_from_input_spec(
            action_config.cache_key
        )
        if not dependencies:
            return str(action_config.cache_key)

        cache_key = None
        async for dependency_outputs in self.stream_dependencies(
            log, dependencies, variables
        ):
            if is_sentinel(dependency_outputs):
                # propagate error
                return Sentinel
            # Compile the inputs
            context = dependency_outputs | variables
            cache_key = str(
                await self._collect_inputs_from_context(
                    log,
                    input_spec=action_config.cache_key,
                    context=context,
                )
            )
        log.debug("Resolved cache key", cache_key=cache_key)
        return cache_key

    async def _run_and_broadcast_action(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        variables: dict[str, Any],
    ) -> None:
        log.debug("Running action task")

        action_config = self.config.flow[action_id]
        action_name = action_config.action
        action_type = self.get_action_type(action_name)

        # Check cache by `cache_key` if provided
        cache_key = await self._resolve_cache_key(log, action_config, variables)
        if cache_key is not None:
            hardcoded_cache_key = True
            outputs = await self._check_cache(log, action_id, action_config.cache_key)
            if outputs is not None:
                self._broadcast_outputs(log, action_id, outputs)
                return
        else:
            hardcoded_cache_key = False

        inputs = None
        outputs = None
        cache_hit = False

        # Run dependencies
        # FIXME instead of running the action on each partial dependency result, every time the action execution
        #  finishes on partial results, run it on the most recent set of partial inputs
        async for inputs in self.stream_input_dependencies(
            log, action_config, variables
        ):
            if is_sentinel(inputs):
                # propagate error
                return None
            cache_hit = False

            # Check cache
            if not hardcoded_cache_key:
                cache_key = inputs.model_dump_json() if inputs is not None else None
            outputs = await self._check_cache(log, action_id, cache_key)
            if outputs is not None:
                cache_hit = True
                self._broadcast_outputs(log, action_id, outputs)
                continue

            # TODO rework this to handle partial outputs, not just full output objects
            async for outputs in self._run_action(
                log=log,
                action_id=action_id,
                inputs=inputs,
            ):
                # TODO are there any race conditions here, between result caching and in-progress action awaiting?
                #  also consider paradigm of multiple workers, indexing tasks in a database and pulling from cache instead

                # Send result to queue
                # log.debug("Broadcasting outputs")
                self._broadcast_outputs(log, action_id, outputs)

            # log.debug("Outputs done")

        # log.debug("Inputs done")

        # Run action one more time with `inputs._finished = True` if so requested
        if inputs is not None and isinstance(inputs, FinalInvocationInputs):
            log.info("Running action with final invocation flag")
            inputs._finished = True
            async for outputs in self._run_action(
                log=log,
                action_id=action_id,
                inputs=inputs,
            ):
                self._broadcast_outputs(log, action_id, outputs)

        # Cache result
        # TODO should we cache intermediate results too, or only on the final set of inputs/outputs?
        # TODO we shouldn't cache if all we did was pull from cache
        if (
            self.use_cache
            and outputs is not None
            and not cache_hit
            and action_type.cache
            and (not isinstance(outputs, CacheControlOutputs) or outputs._cache)
        ):
            outputs_json = outputs.model_dump_json()
            log.debug("Caching result")
            try:
                await self.cache_repo.store(
                    log,
                    cache_key,
                    outputs_json,
                    version=action_type.version,
                    namespace=action_name,
                    # TODO add expire
                    # expire=self.config.action_cache_expire,
                )
            except Exception as e:
                log.warning(
                    "Cache store error",
                    exc_info=e,
                )

        if queues := self.new_listeners[action_id]:
            log.debug("Final output broadcast for new listeners")
            self._broadcast_outputs(log, action_id, outputs, queues=queues)

    async def _run_and_broadcast_action_task(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        variables: dict[str, Any],
    ):
        try:
            await self._run_and_broadcast_action(log, action_id, variables)
        except Exception as e:
            log.exception("Action service exception", exc_info=True)
            sentry_sdk.capture_exception(e)
        finally:
            log.debug("Broadcasting end of stream")
            # Signal end of queue
            self._broadcast_outputs(log, action_id, Sentinel)

            # Signal that the task is done
            del self.tasks[action_id]

    async def stream_action(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        variables: None | dict[str, Any] = None,
        partial: bool = True,
    ) -> AsyncIterator[Outputs | None]:
        """
        Execute the action and stream the outputs of the action as async iterator.
        If the action is already running, subscribe to that execution's output stream.
        If the action has run before, reuse the same action instance.
        Downstream, the action's final outputs are cached for each set of inputs.

        This assumes that:
        - each output is a partial output, and we only care about the final output
        - the action is idempotent, and the action needs not be re-run if the inputs are the same
        - each action ID is run with the same inputs (albeit possibly partial inputs)
          - in particular, if you plug different inputs in quick succession,
            the second request will simply subscribe to the first execution instead
        """
        if variables is None:
            variables = {}

        action_task = None
        queue = None

        # Configure logger
        action_name = self.config.flow[action_id].action

        if "action_id" in log._context:
            downstream_action_id = log._context["action_id"]
            log = log.unbind("action_id").bind(
                downstream_action_id=downstream_action_id
            )
        log = log.bind(action_id=action_id, action=action_name)

        # TODO rewrite this try/finally into a `with` scope that cleans up
        try:
            # Join broadcast
            queue = asyncio.Queue()
            self.action_output_broadcast[action_id].append(queue)
            self.new_listeners[action_id].append(queue)

            # Start action task if not already running
            if action_id not in self.tasks:
                log.debug(
                    "Scheduling action task",
                )
                action_task = asyncio.create_task(
                    self._run_and_broadcast_action_task(log, action_id, variables)
                )

                self.tasks[action_id] = action_task
            else:
                log.debug(
                    "Listening to existing action task",
                )

            # Yield outputs from queue
            outputs = Sentinel
            while True:
                try:
                    new_outputs = await asyncio.wait_for(
                        queue.get(), timeout=self.config.action_timeout
                    )
                except asyncio.TimeoutError:
                    log.error(
                        "Timed out waiting for action output",
                        timeout=self.config.action_timeout,
                    )
                    break
                if is_sentinel(new_outputs):
                    log.debug(
                        "Action task stream signaled end",
                    )
                    if is_sentinel(outputs):
                        log.error(
                            "Action task ended without yielding outputs",
                            partial=partial,
                        )
                    break
                outputs = new_outputs
                if partial:
                    # log.debug("Yielding action task outputs", stream=stream)
                    yield outputs
            if not partial:
                # log.debug("Yielding action task outputs", stream=stream)
                if not is_sentinel(outputs):
                    yield outputs

        finally:
            # Clean up
            if queue is not None:
                self.action_output_broadcast[action_id].remove(queue)
            if action_task is not None:
                try:
                    # give task 3 seconds to finish
                    await asyncio.wait_for(action_task, timeout=3)
                except asyncio.TimeoutError:
                    # cancel task
                    action_task.cancel()
                    try:
                        await action_task
                    except asyncio.CancelledError:
                        pass

    async def run_action(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        variables: None | dict[str, Any] = None,
    ) -> Outputs | None:
        return await iterator_to_coro(
            self.stream_action(log, action_id, variables, partial=False)
        )

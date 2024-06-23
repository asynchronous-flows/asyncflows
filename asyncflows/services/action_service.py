import asyncio
import traceback
from collections import defaultdict
from typing import Any, AsyncIterator, Iterable

from typing_extensions import assert_never

import sentry_sdk
import structlog
from pydantic import BaseModel, RootModel, ValidationError

from asyncflows.models.io import (
    CacheControlOutputs,
    FinalInvocationInputs,
    BlobRepoInputs,
    DefaultModelInputs,
    RedisUrlInputs,
)
from asyncflows.models.blob import Blob
from asyncflows.models.config.action import (
    ActionInvocation,
    StreamingAction,
    InternalActionBase,
    Action,
)
from asyncflows.utils.action_utils import get_actions_dict
from asyncflows.models.config.flow import ActionConfig, Loop, FlowConfig
from asyncflows.models.config.model import ModelConfig
from asyncflows.models.config.transform import TransformsInto
from asyncflows.models.config.value_declarations import (
    TextDeclaration,
    ValueDeclaration,
)
from asyncflows.models.primitives import ExecutableName, ExecutableId, TaskId

from asyncflows.repos.blob_repo import BlobRepo

from asyncflows.repos.cache_repo import CacheRepo
from asyncflows.utils.async_utils import (
    merge_iterators,
    iterator_to_coro,
    Timer,
    measure_coro,
    measure_async_iterator,
)
from asyncflows.utils.pydantic_utils import iterate_fields
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
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        flow: FlowConfig,
    ) -> ActionSubclass:
        if action_id in self.action_cache:
            return self.action_cache[action_id]
        action_config = flow[action_id]
        if not isinstance(action_config, ActionInvocation):
            log.error("Not an action", action_id=action_id)
            raise RuntimeError("Not an action")
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
        flow: FlowConfig,
        variables: dict[str, Any],
    ) -> AsyncIterator[Outputs | None]:
        # Prepare inputs
        if isinstance(inputs, RedisUrlInputs):
            inputs._redis_url = get_redis_url()
        if isinstance(inputs, BlobRepoInputs):
            inputs._blob_repo = self.blob_repo
        if isinstance(inputs, DefaultModelInputs):
            # default_model is a special case,
            # allows ValueDeclaration union except for links and lambdas
            model_config_dict = await self._collect_inputs_from_context(
                log,
                self.config.default_model,
                variables,
            )
            inputs._default_model = ModelConfig.model_validate(model_config_dict)

        # Get the action instance
        action = self._get_action_instance(log, action_id, flow=flow)
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
                    timeout=self.config.action_timeout,
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
            tb = traceback.format_exception(type(e), e, e.__traceback__)
            log.error("Action exception", traceback="".join(tb))
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
            for field_name, field_value in iterate_fields(value):
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
        flow: FlowConfig | None = None,
        task_prefix: str = "",
    ) -> AsyncIterator[dict[ExecutableId, Outputs] | type[Sentinel]]:
        if flow is None:
            flow = self.config.flow
        executable_dependencies = {d for d in dependencies if d[0] in flow}
        extra_dependency_ids = {
            d[0]
            for d in dependencies
            if d not in executable_dependencies and d[0] not in variables
        }
        if extra_dependency_ids:
            log.error(
                "Unknown dependencies, replacing with None",
                dependency_ids=extra_dependency_ids,
            )
            for id_ in extra_dependency_ids:
                variables[id_] = None

        async for dependency_outputs in self.stream_executable_tasks(
            log,
            executable_dependencies,
            variables,
            flow=flow,
            task_prefix=task_prefix,
        ):
            yield dependency_outputs

    async def stream_input_dependencies(
        self,
        log: structlog.stdlib.BoundLogger,
        action_config: ActionInvocation,
        variables: dict[str, Any],
        flow: FlowConfig | None = None,
        task_prefix: str = "",
    ) -> AsyncIterator[Inputs | None | type[Sentinel]]:
        if flow is None:
            flow = self.config.flow
        # Get action type
        action_type = self.get_action_type(action_config.action)
        inputs_type = action_type._get_inputs_type()
        if isinstance(None, inputs_type):
            yield None
            return

        input_spec = {}
        for name, value in iterate_fields(action_config):
            if name in ("id", "action"):
                continue
            if value is not None:
                input_spec[name] = value

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
                tb = traceback.format_exception(type(e), e, e.__traceback__)
                log.exception(
                    "Invalid inputs",
                    inputs_dict=rendered,
                    traceback="".join(tb),
                )
                sentry_sdk.capture_exception(e)
            return

        async for dependency_outputs in self.stream_dependencies(
            log,
            dependencies,
            variables,
            flow=flow,
            task_prefix=task_prefix,
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
                tb = traceback.format_exception(type(e), e, e.__traceback__)
                log.exception(
                    "Invalid inputs",
                    inputs_dict=inputs_dict,
                    traceback="".join(tb),
                )
                sentry_sdk.capture_exception(e)

    async def stream_executable_tasks(
        self,
        log: structlog.stdlib.BoundLogger,
        dependencies: set[tuple[ExecutableId, bool]] | set[ExecutableId],
        variables: None | dict[str, Any] = None,
        flow: FlowConfig | None = None,
        task_prefix: str = "",
    ) -> AsyncIterator[dict[ExecutableId, Outputs] | type[Sentinel]]:
        if variables is None:
            variables = {}
        if flow is None:
            flow = self.config.flow

        if not dependencies:
            yield {}
            return

        if is_set_of_tuples(dependencies):
            executable_ids = list({id_ for id_, _ in dependencies})
            stream_flags = [
                not any(
                    id_ == executable_id and not stream for id_, stream in dependencies
                )
                for executable_id in executable_ids
            ]
        else:
            executable_ids = list(set(dependencies))
            stream_flags = [True for _ in executable_ids]

        if len(executable_ids) != len(stream_flags):
            log.error(
                "Length mismatch between action_ids and stream_flags",
                action_ids=executable_ids,
                stream_flags=stream_flags,
            )
            yield Sentinel

        iterators = []
        for id_, stream in zip(executable_ids, stream_flags):
            executable = flow[id_]
            if isinstance(executable, ActionInvocation):
                iter_ = self.stream_action(
                    log=log,
                    action_id=id_,
                    variables=variables,
                    partial=stream,
                    flow=flow,
                    task_prefix=task_prefix,
                )
            elif isinstance(executable, Loop):
                iter_ = self.stream_loop(
                    log=log,
                    loop_id=id_,
                    variables=variables,
                    partial=stream,
                    flow=flow,
                    task_prefix=task_prefix,
                )
            else:
                assert_never(executable)
            iterators.append(iter_)

        merged_iterator = merge_iterators(
            log,
            executable_ids,
            iterators,
        )

        log = log.bind(action_task_ids=executable_ids)
        dependency_outputs = {}
        async for executable_id, executable_outputs in merged_iterator:
            # None is yielded as action_outputs if an action throws an exception
            # if action_outputs is None:
            #     raise RuntimeError(f"{action_id} returned None")

            # if action_outputs is not None:
            #     # TODO consider parity with `stream_action` in returning a model instead of a dict
            #     action_outputs = action_outputs.model_dump()
            dependency_outputs[executable_id] = executable_outputs

            # TODO do we need more fine grained controls on what actions need to return?
            if all(action_id in dependency_outputs for action_id in executable_ids):
                log.debug("Yielding combined action task results")
                yield dependency_outputs
            else:
                log.debug(
                    "Action task results received, waiting for other actions to complete",
                    received_action_id=executable_id,
                )
        if not all(action_id in dependency_outputs for action_id in executable_ids):
            log.error(
                "Not all action tasks completed",
                missing_action_ids=set(executable_ids) - set(dependency_outputs.keys()),
            )
            yield Sentinel

    def _broadcast_outputs(
        self,
        log: structlog.stdlib.BoundLogger,
        task_id: TaskId,
        outputs: Outputs | None | type[Sentinel],
        queues: list[asyncio.Queue] | None = None,
    ):
        if queues is None:
            queues = self.action_output_broadcast[task_id]

        # Broadcast outputs
        new_listeners_queues = self.new_listeners[task_id]
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
        cache_key: str | None,
        flow: FlowConfig,
    ) -> None | Outputs:
        action_invocation = flow[action_id]
        if not isinstance(action_invocation, ActionInvocation):
            log.error("Not an action", action_id=action_id)
            return None
        action_name = action_invocation.action
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
                outputs_type: BaseModel = action_type._get_outputs_type(
                    action_invocation
                )
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
        flow: FlowConfig,
        task_prefix: str,
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
            log,
            dependencies,
            variables,
            flow,
            task_prefix,
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
        task_id: TaskId,
        variables: dict[str, Any],
        flow: FlowConfig,
        task_prefix: str,
    ) -> None:
        log.debug("Running action task")

        action_config = flow[action_id]
        if not isinstance(action_config, ActionInvocation):
            log.error("Not an action", task_id=task_id)
            return
        action_name = action_config.action
        action_type = self.get_action_type(action_name)

        # Check cache by `cache_key` if provided
        cache_key = await self._resolve_cache_key(
            log, action_config, variables, flow, task_prefix
        )
        if is_sentinel(cache_key):
            log.error("Failed to create cache key")
            return

        if cache_key is not None:
            hardcoded_cache_key = cache_key
            outputs = await self._check_cache(log, action_id, cache_key, flow=flow)
            if outputs is not None:
                self._broadcast_outputs(log, task_id, outputs)
                return
        else:
            hardcoded_cache_key = cache_key

        inputs = None
        outputs = None
        cache_hit = False

        # Run dependencies
        # FIXME instead of running the action on each partial dependency result, every time the action execution
        #  finishes on partial results, run it on the most recent set of partial inputs
        # FIXME if an action's output is requested from within an inner scope (i.e., a loop),
        #  it is treated as a separate action from the outer scope, due to task_prefix.
        #  This should be consolidated, but then there needs to be a way of telling apart actions with the same name
        #  in different levels of scope
        async for inputs in self.stream_input_dependencies(
            log,
            action_config,
            variables,
            flow,
            task_prefix=task_prefix,
        ):
            if is_sentinel(inputs):
                # propagate error
                return None
            cache_hit = False

            # Check cache
            if hardcoded_cache_key is not None:
                cache_key = hardcoded_cache_key
            else:
                cache_key = inputs.model_dump_json() if inputs is not None else None
            outputs = await self._check_cache(log, action_id, cache_key, flow=flow)
            if outputs is not None:
                cache_hit = True
                self._broadcast_outputs(log, task_id, outputs)
                continue

            # TODO rework this to handle partial outputs, not just full output objects
            async for outputs in self._run_action(
                log=log,
                action_id=action_id,
                inputs=inputs,
                flow=flow,
                variables=variables,
            ):
                # TODO are there any race conditions here, between result caching and in-progress action awaiting?
                #  also consider paradigm of multiple workers, indexing tasks in a database and pulling from cache instead

                # Send result to queue
                # log.debug("Broadcasting outputs")
                self._broadcast_outputs(log, task_id, outputs)

            # log.debug("Outputs done")

        # log.debug("Inputs done")

        # Run action one more time with `inputs._finished = True` if so requested
        if inputs is not None and isinstance(inputs, FinalInvocationInputs):
            log.info("Running action with final invocation flag")
            inputs._finished = True
            async for outputs in self._run_action(
                log=log,
                action_id=task_id,
                inputs=inputs,
                flow=flow,
                variables=variables,
            ):
                self._broadcast_outputs(log, task_id, outputs)

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

        if queues := self.new_listeners[task_id]:
            log.debug("Final output broadcast for new listeners")
            self._broadcast_outputs(log, task_id, outputs, queues=queues)

    async def _run_and_broadcast_action_task(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        task_id: TaskId,
        variables: dict[str, Any],
        flow: FlowConfig,
        task_prefix: str,
    ):
        try:
            await self._run_and_broadcast_action(
                log=log,
                action_id=action_id,
                task_id=task_id,
                variables=variables,
                flow=flow,
                task_prefix=task_prefix,
            )
        except Exception as e:
            tb = traceback.format_exception(type(e), e, e.__traceback__)
            log.error("Action service exception", traceback="".join(tb))
            sentry_sdk.capture_exception(e)
        finally:
            log.debug("Broadcasting end of stream")
            # Signal end of queue
            self._broadcast_outputs(log, task_id, Sentinel)

            # Signal that the task is done
            del self.tasks[task_id]

    async def stream_loop(
        self,
        log: structlog.stdlib.BoundLogger,
        loop_id: ExecutableId,
        variables: dict[str, Any] | None = None,
        partial: bool = False,
        flow: FlowConfig | None = None,
        task_prefix: str = "",
    ) -> AsyncIterator[list[Outputs]]:
        if flow is None:
            flow = self.config.flow
        if variables is None:
            variables = {}
        if partial:
            # TODO support streaming
            log.warning(
                "Streaming outputs from a loop is not yet supported",
                loop_id=loop_id,
            )
            partial = False

        if "action_id" in log._context:
            downstream_action_id = log._context["action_id"]
            log = log.unbind("action_id").bind(
                downstream_action_id=downstream_action_id
            )
        if "action_name" in log._context:
            log = log.unbind("action_name")
        log = log.bind(action_id=loop_id)

        loop = flow[loop_id]
        if not isinstance(loop, Loop):
            log.error("Not a loop", loop_id=loop_id)
            raise RuntimeError("Not a loop")

        # Get the dependencies of the variable we're iterating
        looped_dependency = self._get_dependency_ids_and_stream_flag_from_input_spec(
            loop.in_
        )
        dependency_outputs = Sentinel
        async for dependency_outputs in self.stream_dependencies(
            log,
            looped_dependency,
            variables,
            flow=flow,
            task_prefix=task_prefix,
        ):
            pass
        if is_sentinel(dependency_outputs):
            return

        # Render the variable
        looped_variable = await self._collect_inputs_from_context(
            log,
            input_spec=loop.in_,
            context=dependency_outputs | variables,
        )
        if not isinstance(looped_variable, Iterable):
            log.error(
                "Looped variable is not iterable",
                looped_variable=looped_variable,
            )
            return

        # Run the loop
        iterators = []
        for i, item in enumerate(looped_variable):
            loop_variables = {loop.for_: item} | variables
            new_task_prefix = f"{task_prefix}{loop_id}[{i}]."
            # TODO don't run all the actions in the loop, only those that are actually used
            iterators.append(
                self.stream_executable_tasks(
                    log,
                    set(loop.flow),
                    loop_variables,
                    flow=flow | loop.flow,
                    task_prefix=new_task_prefix,
                )
            )

        # Merge the iterators and wait for results
        merged_iterator = merge_iterators(
            log,
            range(len(iterators)),
            iterators,
        )
        indexed_results = {}
        async for id_, outputs in merged_iterator:
            if is_sentinel(outputs):
                log.error(
                    "Loop stream ended with sentinel",
                )
                return
            indexed_results[id_] = outputs

        if not all(id_ in indexed_results for id_ in range(len(iterators))):
            log.error(
                "Not all loop tasks completed",
                missing_task_ids=set(range(len(iterators)))
                - set(indexed_results.keys()),
            )
            return

        # Combine the results
        combined_results = []
        for i in range(len(iterators)):
            combined_results.append(indexed_results[i])
        yield combined_results

    async def stream_action(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        variables: None | dict[str, Any] = None,
        partial: bool = True,
        flow: FlowConfig | None = None,
        task_prefix: str = "",
    ) -> AsyncIterator[Outputs]:
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
        if flow is None:
            flow = self.config.flow

        action_task = None
        queue = None

        # Configure logger
        action = flow[action_id]
        if not isinstance(action, ActionInvocation):
            log.error(
                "Not an action",
                action_id=action_id,
            )
            raise RuntimeError
        action_name = action.action

        if "action_id" in log._context:
            downstream_action_id = log._context["action_id"]
            log = log.unbind("action_id").bind(
                downstream_action_id=downstream_action_id
            )
        log = log.bind(action_id=action_id, action=action_name)

        task_id = f"{task_prefix}{action_id}"

        # TODO rewrite this try/finally into a `with` scope that cleans up
        try:
            # Join broadcast
            queue = asyncio.Queue()
            self.action_output_broadcast[task_id].append(queue)
            self.new_listeners[task_id].append(queue)

            # Start action task if not already running
            if task_id not in self.tasks:
                log.debug(
                    "Scheduling action task",
                )
                action_task = asyncio.create_task(
                    self._run_and_broadcast_action_task(
                        log=log,
                        action_id=action_id,
                        task_id=task_id,
                        variables=variables,
                        flow=flow,
                        task_prefix=task_prefix,
                    )
                )

                self.tasks[task_id] = action_task
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
                self.action_output_broadcast[task_id].remove(queue)
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

    async def stream_executable(
        self,
        log: structlog.stdlib.BoundLogger,
        executable_id: ExecutableId,
        variables: None | dict[str, Any] = None,
        partial: bool = True,
        flow: FlowConfig | None = None,
    ) -> AsyncIterator[list[Outputs] | Outputs]:
        if flow is None:
            flow = self.config.flow

        executable = flow[executable_id]

        if isinstance(executable, ActionInvocation):
            async for outputs in self.stream_action(
                log=log,
                action_id=executable_id,
                variables=variables,
                partial=partial,
                flow=flow,
            ):
                yield outputs
        elif isinstance(executable, Loop):
            result = Sentinel
            async for result in self.stream_loop(
                log=log, loop_id=executable_id, variables=variables, partial=partial
            ):
                pass
            if is_sentinel(result):
                log.error("Loop did not yield an output")
            else:
                yield result
            return
        else:
            assert_never(executable)

    async def run_executable(
        self,
        log: structlog.stdlib.BoundLogger,
        executable_id: ExecutableId,
        variables: None | dict[str, Any] = None,
    ) -> list[Outputs] | Outputs | None:
        return await iterator_to_coro(
            self.stream_executable(
                log=log, executable_id=executable_id, variables=variables, partial=False
            )
        )

    async def run_action(
        self,
        log: structlog.stdlib.BoundLogger,
        action_id: ExecutableId,
        variables: None | dict[str, Any] = None,
    ):
        return await iterator_to_coro(
            self.stream_action(
                log=log, action_id=action_id, variables=variables, partial=False
            )
        )

    async def run_loop(
        self,
        log: structlog.stdlib.BoundLogger,
        loop_id: ExecutableId,
        variables: None | dict[str, Any] = None,
    ) -> list[Outputs] | None:
        return await iterator_to_coro(
            self.stream_loop(
                log=log, loop_id=loop_id, variables=variables, partial=False
            )
        )

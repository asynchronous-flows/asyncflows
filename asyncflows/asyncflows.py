from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from asyncflows.models.config.flow import ActionConfig
from asyncflows.services.action_service import ActionService

from asyncflows.log_config import get_logger
from asyncflows.models.config.value_declarations import VarDeclaration
from asyncflows.repos.blob_repo import InMemoryBlobRepo, BlobRepo
from asyncflows.repos.cache_repo import ShelveCacheRepo, CacheRepo
from asyncflows.utils.loader_utils import load_config_file, load_config_text
from asyncflows.utils.static_utils import check_config_consistency


class AsyncFlows:
    def __init__(
        self,
        config: ActionConfig,
        cache_repo: CacheRepo | type[CacheRepo] = ShelveCacheRepo,
        blob_repo: BlobRepo | type[BlobRepo] = InMemoryBlobRepo,
        temp_dir: None | str | TemporaryDirectory = None,
        _vars: None | dict[str, Any] = None,
    ):
        self.log = get_logger()
        self.variables = _vars or {}
        if isinstance(temp_dir, TemporaryDirectory):
            self.temp_dir = temp_dir
            temp_dir_path = temp_dir.name
        elif isinstance(temp_dir, str):
            self.temp_dir = temp_dir
            temp_dir_path = temp_dir
        else:
            self.temp_dir = TemporaryDirectory()
            temp_dir_path = self.temp_dir.name

        if isinstance(cache_repo, CacheRepo):
            self.cache_repo = cache_repo
        else:
            self.cache_repo = cache_repo(
                temp_dir=temp_dir_path,
            )

        if isinstance(blob_repo, BlobRepo):
            self.blob_repo = blob_repo
        else:
            self.blob_repo = blob_repo(
                temp_dir=temp_dir_path,
            )

        self.action_config = config
        self.action_service = ActionService(
            temp_dir=temp_dir_path,
            use_cache=True,
            cache_repo=self.cache_repo,
            blob_repo=self.blob_repo,
            config=self.action_config,
        )

    async def close(self):
        await self.cache_repo.close()
        await self.blob_repo.close()
        if isinstance(self.temp_dir, TemporaryDirectory):
            self.temp_dir.cleanup()

    @classmethod
    def from_text(
        cls,
        text: str,
        cache_repo: CacheRepo | type[CacheRepo] = ShelveCacheRepo,
        blob_repo: BlobRepo | type[BlobRepo] = InMemoryBlobRepo,
    ):
        config = load_config_text(text)
        return AsyncFlows(
            config=config,
            cache_repo=cache_repo,
            blob_repo=blob_repo,
        )

    @classmethod
    def from_file(
        cls,
        file: str | Path,
        cache_repo: CacheRepo | type[CacheRepo] = ShelveCacheRepo,
        blob_repo: BlobRepo | type[BlobRepo] = InMemoryBlobRepo,
    ) -> "AsyncFlows":
        if isinstance(file, Path):
            file = file.as_posix()
        config = load_config_file(file)
        return AsyncFlows(
            config=config,
            cache_repo=cache_repo,
            blob_repo=blob_repo,
        )

    def set_vars(self, **kwargs) -> "AsyncFlows":
        variables = self.variables | kwargs
        return AsyncFlows(
            config=self.action_config,
            cache_repo=self.cache_repo,
            blob_repo=self.blob_repo,
            temp_dir=self.temp_dir,
            _vars=variables,
        )

    async def run(self, target_output: None | str = None):
        """
        Run the subset of the flow required to get the target output.
        If the action has already been run, the cached output will be returned.

        Parameters
        ----------
        target_output : None | str
            the output to return (defaults to `default_output` in the config, or the last action's output if not set)
        """

        if target_output is None:
            target_output = self.action_config.get_default_output()

        if not check_config_consistency(
            self.log,
            self.action_config,
            set(self.variables),
            target_output,
        ):
            raise ValueError("Flow references unset variables")

        declaration = VarDeclaration(
            var=target_output,
        )

        dependencies = declaration.get_dependencies()
        if len(dependencies) != 1:
            raise NotImplementedError("Only one dependency is supported for now")
        executable_id = list(dependencies)[0]

        outputs = await self.action_service.run_executable(
            self.log,
            executable_id=executable_id,
            variables=self.variables,
        )
        context = {
            executable_id: outputs,
        }

        return await declaration.render(context)

    async def stream(self, target_output: None | str = None):
        """
        Run the subset of the flow required to get the target output, and asynchronously iterate the output.
        If the action has already been run, the cached output will be returned.

        Parameters
        ----------
        target_output : None | str
            the output to return (defaults to `default_output` in the config, or the last action's output if not set)
        """
        if target_output is None:
            target_output = self.action_config.get_default_output()

        if not check_config_consistency(
            self.log,
            self.action_config,
            set(self.variables),
            target_output,
        ):
            raise ValueError("Flow references unset variables")

        declaration = VarDeclaration(
            var=target_output,
        )

        dependencies = declaration.get_dependencies()
        if len(dependencies) != 1:
            raise NotImplementedError("Only one dependency is supported for now")
        executable_id = list(dependencies)[0]

        async for outputs in self.action_service.stream_executable(
            self.log,
            executable_id=executable_id,
            variables=self.variables,
        ):
            context = {
                executable_id: outputs,
            }

            yield await declaration.render(context)

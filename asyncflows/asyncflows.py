import tempfile
from pathlib import Path
from typing import Any

from asyncflows.services.action_service import ActionService

from asyncflows.log_config import get_logger
from asyncflows.models.config.value_declarations import VarDeclaration
from asyncflows.repos.blob_repo import InMemoryBlobRepo
from asyncflows.repos.cache_repo import ShelveCacheRepo
from asyncflows.services.config_service import ConfigService


class AsyncFlows:
    def __init__(
        self,
        filename: str,
        _vars: None | dict[str, Any] = None,
    ):
        self.log = get_logger()
        self.variables = _vars or {}
        self.filename = filename
        self.temp_dir = tempfile.TemporaryDirectory()
        cache_repo = ShelveCacheRepo(
            temp_dir=self.temp_dir.name,
        )
        blob_repo = InMemoryBlobRepo(
            temp_dir=self.temp_dir.name,
        )
        config_service = ConfigService(
            filename=filename,
        )
        self.action_config = config_service.load()
        self.action_service = ActionService(
            temp_dir=self.temp_dir.name,
            use_cache=True,
            cache_repo=cache_repo,
            blob_repo=blob_repo,
            config=self.action_config,
        )

    @classmethod
    def from_file(
        cls,
        file: str | Path,
    ) -> "AsyncFlows":
        if isinstance(file, Path):
            file = file.as_posix()
        return AsyncFlows(
            filename=file,
        )

    def set_vars(self, **kwargs) -> "AsyncFlows":
        variables = self.variables | kwargs
        return AsyncFlows(
            filename=self.filename,
            _vars=variables,
        )

    async def run(self, target_output: None | str = None):
        if target_output is None:
            target_output = self.action_config.default_output

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

import os
from typing import TypeVar

import yaml
from pydantic import BaseModel

from asyncflows.models.config.flow import ActionConfig

T = TypeVar("T", bound=BaseModel)


class ConfigService:
    def __init__(self, filename: str):
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Could not find {filename}")
        self.filename = filename

    def load(self) -> ActionConfig:
        with open(self.filename, "r") as f:
            return ActionConfig.model_validate(yaml.safe_load(f))

    def _load_config_file(self, model: type[T], filename: str) -> T:
        # load override config if exists
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Could not find {filename}")

        with open(filename, "r") as f:
            return model.model_validate(yaml.safe_load(f))

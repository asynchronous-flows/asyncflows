import os

import yaml

from asyncflows.models.config.flow import ActionConfig, build_hinted_action_config


def get_config_model() -> type[ActionConfig]:
    # TODO cache this so it only rebuilds when the action registry changes
    return build_hinted_action_config()


def load_config_text(config_text: str) -> ActionConfig:
    config_model = get_config_model()
    return config_model.model_validate(yaml.safe_load(config_text))


def load_config_file(
    filename: str, config_model: type[ActionConfig] | None = None
) -> ActionConfig:
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Could not find {filename}")

    if config_model is None:
        config_model = get_config_model()

    with open(filename, "r") as f:
        return config_model.model_validate(yaml.safe_load(f))

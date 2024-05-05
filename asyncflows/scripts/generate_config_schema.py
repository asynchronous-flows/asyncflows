import json
import os
import traceback
from typing import Union

from pydantic import ValidationError

from asyncflows.actions import get_actions_dict
from asyncflows.models.config.action import (
    TestActionConfig,
    build_actions,
    ActionConfig,
)
from asyncflows.models.primitives import ExecutableId
from asyncflows.services.config_service import ConfigService

_cache = {}


def _build_action_specs(
    config_class: type[ActionConfig],
    config_service: ConfigService,
):
    key = str((config_class.__dict__, config_service.__dict__))
    if key in _cache:
        return _cache[key]

    try:
        action_config = config_service._load_config_file(
            config_class, config_service.filename
        )
    except ValidationError:
        print("Failed to load action config")
        traceback.print_exc()
        return None

    action_specs = []
    actions = get_actions_dict()
    for action_id, action_invocation in action_config.flow.items():
        action_name = action_invocation.action
        action_specs.append(
            {
                action_id: actions[action_name]._get_outputs_type(),
            }
        )

    _cache[key] = action_specs
    return action_specs


def _build_vars(
    config_class: type[ActionConfig],
    config_service: ConfigService,
):
    action_specs = _build_action_specs(
        config_class=config_class,
        config_service=config_service,
    )
    if action_specs is None:
        action_specs = []

    return action_specs


def _build_hinted_action_model(
    config_class: type[ActionConfig],
    # config_seravice: ConfigService,
    strict: bool,
):
    # vars_ = _build_vars(
    #     config_class=config_class,
    #     config_service=config_service,
    # )

    HintedActionInvocationUnion = Union[
        tuple(
            build_actions(
                # vars_=vars_,
                strict=strict,
            )
        )  # pyright: ignore
    ]

    class HintedActionConfig(config_class):
        flow: dict[ExecutableId, HintedActionInvocationUnion]  # type: ignore

    return HintedActionConfig


def _build_action_schema(
    config_class: type[ActionConfig],
    # config_service: ConfigService,
    output_file: str,
    strict: bool,
):
    HintedActionConfig = _build_hinted_action_model(
        config_class=config_class,
        # config_service=config_service,
        strict=strict,
    )
    workflow_schema = HintedActionConfig.model_json_schema()
    with open(os.path.join("schemas", output_file), "w") as f:
        json.dump(workflow_schema, f, indent=2)


if __name__ == "__main__":
    _build_action_schema(
        config_class=ActionConfig,
        # config_service=ConfigService(),
        output_file="action_schema.json",
        strict=False,
    )

    _build_action_schema(
        config_class=TestActionConfig,
        # config_service=ConfigService(
        #     base_config_dir="asyncflows/tests/resources/config",
        #     action_config_stem="testing_actions.yaml",
        # ),
        output_file="testing_action_schema.json",
        strict=False,
    )

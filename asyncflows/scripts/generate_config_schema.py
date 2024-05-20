import argparse
import json
import os
import traceback
from typing import Union

from pydantic import ValidationError

from asyncflows.actions import get_actions_dict
from asyncflows.models.config.action import (
    build_actions,
    _action_names,
    _testing_action_names,
)
from asyncflows.models.primitives import ExecutableId
from asyncflows.models.config.flow import (
    ActionConfig,
    Loop,
    TestActionConfig,
    NonActionExecutable,
    TestNonActionExecutable,
)
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
        if isinstance(action_invocation, Loop):
            # TODO build for-loop specs
            continue
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
    action_names: list[str],
    non_action_executable: type,
    config_class: type[ActionConfig],
    config_service: ConfigService | None,
    strict: bool,
):
    if config_service:
        links = _build_vars(
            config_class=config_class,
            config_service=config_service,
        )
    else:
        links = None

    HintedActionInvocationUnion = (
        non_action_executable
        | Union[
            tuple(
                build_actions(
                    action_names,
                    links=links,
                    strict=strict,
                )
            )  # pyright: ignore
        ]
    )

    class HintedActionConfig(config_class):
        flow: dict[ExecutableId, HintedActionInvocationUnion]  # type: ignore

    return HintedActionConfig


def _build_action_schema(
    action_names: list[str],
    config_class: type[ActionConfig],
    non_action_executable: type,
    strict: bool,
    config_service: ConfigService | None = None,
):
    HintedActionConfig = _build_hinted_action_model(
        action_names=action_names,
        config_class=config_class,
        non_action_executable=non_action_executable,
        config_service=config_service,
        strict=strict,
    )
    workflow_schema = HintedActionConfig.model_json_schema()
    return workflow_schema


def _build_and_save_action_schema(
    action_names: list[str],
    config_class: type[ActionConfig],
    non_action_executable: type,
    output_file: str,
    strict: bool,
    config_service: ConfigService | None = None,
):
    workflow_schema = _build_action_schema(
        action_names=action_names,
        config_class=config_class,
        non_action_executable=non_action_executable,
        strict=strict,
        config_service=config_service,
    )
    with open(os.path.join("schemas", output_file), "w") as f:
        json.dump(workflow_schema, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flow",
        default="",
        help="Path to flow for populating link fields with",
    )

    args = parser.parse_args()

    if args.flow:
        schema = _build_action_schema(
            action_names=_action_names,
            config_class=ActionConfig,
            non_action_executable=NonActionExecutable,
            config_service=ConfigService(args.flow),
            strict=False,
        )
        # straight to stdout we go
        print(json.dumps(schema, indent=2))
    else:
        # build default action and test action schemas
        _build_and_save_action_schema(
            action_names=_action_names,
            config_class=ActionConfig,
            non_action_executable=NonActionExecutable,
            output_file="action_schema.json",
            strict=False,
        )

        _build_and_save_action_schema(
            action_names=_testing_action_names,
            config_class=TestActionConfig,
            non_action_executable=TestNonActionExecutable,
            output_file="testing_action_schema.json",
            strict=False,
        )

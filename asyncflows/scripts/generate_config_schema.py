import argparse
import json
import os
import traceback
from typing import Union

from pydantic import ValidationError

from asyncflows.actions.base import Field
from asyncflows.actions import get_actions_dict
from asyncflows.models.config.action import (
    build_actions,
    _action_names,
    _testing_action_names,
    build_hinted_value_declaration,
)
from asyncflows.models.primitives import ExecutableId
from asyncflows.models.config.flow import (
    ActionConfig,
    Loop,
    TestActionConfig,
)
from asyncflows.utils.config_utils import load_config_file

_cache = {}


def _build_action_specs(
    config_class: type[ActionConfig],
    config_filename: str,
):
    key = str((config_class.__dict__, config_filename))
    if key in _cache:
        return _cache[key]

    try:
        action_config = load_config_file(config_class, config_filename)
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
    config_filename: str,
):
    action_specs = _build_action_specs(
        config_class=config_class,
        config_filename=config_filename,
    )
    if action_specs is None:
        action_specs = []

    return action_specs


def build_hinted_flow_model(
    action_names: list[str],
    config_class: type[ActionConfig],
    config_filename: str | None,
    strict: bool,
):
    if config_filename:
        links = _build_vars(
            config_class=config_class,
            config_filename=config_filename,
        )
    else:
        links = None

    # TODO this is called inside `build_actions` too, make it so it doesn't do it twice
    HintedValueDeclaration = build_hinted_value_declaration(
        # vars_=vars_,
        links=links,
        strict=strict,
    )

    class HintedLoop(Loop):
        in_: HintedValueDeclaration = Field(  # type: ignore
            ...,
            alias="in",
        )
        flow: "HintedFlowConfig"  # type: ignore

    HintedActionInvocationUnion = Union[
        tuple(
            build_actions(
                action_names,
                links=links,
                strict=strict,
            )
        )  # pyright: ignore
    ]

    HintedExecutable = HintedLoop | HintedActionInvocationUnion

    HintedFlowConfig = dict[ExecutableId, HintedExecutable]

    class HintedActionConfig(config_class):
        flow: HintedFlowConfig  # type: ignore

    # HintedLoop.model_rebuild()  # TODO is this necessary?

    return HintedActionConfig


def _build_action_schema(
    action_names: list[str],
    config_class: type[ActionConfig],
    strict: bool,
    config_filename: str | None = None,
):
    HintedActionConfig = build_hinted_flow_model(
        action_names=action_names,
        config_class=config_class,
        config_filename=config_filename,
        strict=strict,
    )
    workflow_schema = HintedActionConfig.model_json_schema()
    return workflow_schema


def _build_and_save_action_schema(
    action_names: list[str],
    config_class: type[ActionConfig],
    output_file: str,
    strict: bool,
    config_filename: str | None = None,
):
    workflow_schema = _build_action_schema(
        action_names=action_names,
        config_class=config_class,
        strict=strict,
        config_filename=config_filename,
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
            config_filename=args.flow,
            strict=True,
        )
        # straight to stdout we go
        print(json.dumps(schema, indent=2))
    else:
        # build default action and test action schemas
        _build_and_save_action_schema(
            action_names=_action_names,
            config_class=ActionConfig,
            output_file="action_schema.json",
            strict=False,
        )

        _build_and_save_action_schema(
            action_names=_testing_action_names,
            config_class=TestActionConfig,
            output_file="testing_action_schema.json",
            strict=False,
        )

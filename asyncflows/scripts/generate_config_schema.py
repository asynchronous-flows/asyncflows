import argparse
import json
import os
import traceback

from pydantic import ValidationError

from asyncflows.actions import get_actions_dict
from asyncflows.models.config.flow import (
    Loop,
    build_hinted_action_config,
)
from asyncflows.utils.loader_utils import load_config_file

_cache = {}


def _build_action_specs(
    config_filename: str,
):
    key = config_filename
    if key in _cache:
        return _cache[key]

    try:
        action_config = load_config_file(config_filename)
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
    config_filename: str,
):
    action_specs = _build_action_specs(
        config_filename=config_filename,
    )
    if action_specs is None:
        action_specs = []

    return action_specs


def _build_asyncflows_schema(
    action_names: list[str],
    strict: bool,
    config_filename: str | None = None,
):
    if config_filename:
        links = _build_vars(
            config_filename=config_filename,
        )
    else:
        links = None

    HintedActionConfig = build_hinted_action_config(
        action_names=action_names,
        links=links,
        vars_=None,
        strict=strict,
    )
    workflow_schema = HintedActionConfig.model_json_schema()
    return workflow_schema


def _build_and_save_asyncflows_schema(
    action_names: list[str],
    output_file: str,
    strict: bool,
    config_filename: str | None = None,
):
    workflow_schema = _build_asyncflows_schema(
        action_names=action_names,
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

    action_names = list(get_actions_dict().keys())

    if args.flow:
        schema = _build_asyncflows_schema(
            action_names=action_names,
            config_filename=args.flow,
            strict=True,
        )
        # straight to stdout we go
        print(json.dumps(schema, indent=2))
    else:
        # TODO assert tests not imported before this line
        import asyncflows.tests.resources.actions  # noqa

        testing_action_names = list(get_actions_dict().keys())

        # build default action and test action schemas
        _build_and_save_asyncflows_schema(
            action_names=action_names,
            output_file="asyncflows_schema.json",
            strict=False,
        )

        _build_and_save_asyncflows_schema(
            action_names=testing_action_names,
            output_file="testing_asyncflows_schema.json",
            strict=False,
        )

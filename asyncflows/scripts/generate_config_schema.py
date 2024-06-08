import argparse
import json
import os
import traceback

import pydantic
from pydantic import TypeAdapter

from asyncflows.actions import get_actions_dict, InternalActionBase
from asyncflows.models.config.flow import (
    Loop,
    build_hinted_action_config,
    ActionConfig,
)
from asyncflows.utils.loader_utils import load_config_file
from asyncflows.utils.type_utils import build_link_literal


def _get_action_invocations(
    config_filename: str,
) -> dict[str, type[InternalActionBase]]:
    try:
        # load the file not as a non-strict model
        action_config = load_config_file(config_filename, config_model=ActionConfig)
    except pydantic.ValidationError:
        traceback.print_exc()
        print("Failed to load action config")
        return {}

    action_invocations = {}
    actions = get_actions_dict()
    for action_id, action_invocation in action_config.flow.items():
        if isinstance(action_invocation, Loop):
            # TODO support for loops in link fields
            continue
        action_name = action_invocation.action
        action_invocations[action_id] = actions[action_name]

    return action_invocations


def _build_asyncflows_schema(
    action_names: list[str],
    strict: bool,
    config_filename: str | None = None,
    link_hint_literal_name: str = "__LinkHintLiteral",
):
    if config_filename:
        action_invocations = _get_action_invocations(
            config_filename=config_filename,
        )
        link_hint_literal = build_link_literal(
            action_invocations=action_invocations,
            strict=strict,
        )
    else:
        link_hint_literal = None

    HintedActionConfig = build_hinted_action_config(
        action_names=action_names,
        links=link_hint_literal,
        vars_=None,
        strict=strict,
    )
    workflow_schema = HintedActionConfig.model_json_schema()

    if link_hint_literal is not None:
        definitions = workflow_schema["$defs"]
        if link_hint_literal_name in definitions:
            raise ValueError(
                f"Link hint literal name `{link_hint_literal_name}` already exists in definitions"
            )
        definitions[link_hint_literal_name] = TypeAdapter(
            link_hint_literal
        ).json_schema()

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

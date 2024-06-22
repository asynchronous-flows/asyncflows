from unittest.mock import patch

from asyncflows import AsyncFlows
from asyncflows.utils.loader_utils import load_config_file

from asyncflows.actions.prompt import (
    Outputs as PromptOutputs,
    Prompt,
    Inputs as PromptInputs,
)


async def test_default_model_var(log_history):
    config = load_config_file("asyncflows/tests/resources/default_model_var.yaml")
    af = AsyncFlows(config=config).set_vars(
        some_model="hi",
    )

    outputs = PromptOutputs(
        result="3",
        response="3",
        data=None,
    )

    async def run(self, inputs: PromptInputs):
        assert inputs._default_model.model == "hi"
        yield outputs

    with patch.object(Prompt, "run", new=run):
        outputs = await af.run()

    assert outputs == "3"

    assert all(log_["log_level"] != "error" for log_ in log_history)

    # with capture_logs() as log_history:
    # outputs = await action_service.run_action(log=log, action_id=action_id)

    # assert_logs(log_history, action_id, "test_add")

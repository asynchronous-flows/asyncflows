import builtins
import importlib
import os

import pytest


@pytest.fixture(scope="function")
def mock_builtins_input(monkeypatch):
    responded = False

    def input_mock(*args, **kwargs):
        nonlocal responded

        if responded:
            # simulate CTRL+D
            raise EOFError
        responded = True
        return "Hi"

    monkeypatch.setattr(builtins, "input", input_mock)


@pytest.mark.slow
# @pytest.mark.skipif(
#     "ANTHROPIC_API_KEY" not in os.environ, reason="requires ANTROPIC_API_KEY env var"
# )
@pytest.mark.parametrize(
    "example_name",
    [
        "hello_world",
        "rag",
        "debono",
    ],
)
async def test_run_example(
    mock_prompt_action,
    mock_transformer_action,
    example_name,
    mock_builtins_input,
    log_history,
):
    example_stem = f"examples/{example_name}"
    example_yaml = f"{example_stem}.yaml"
    example_py = f"{example_stem}.py"

    # if example files don't exist
    if any(not os.path.exists(f) for f in (example_yaml, example_py)):
        raise FileNotFoundError(f"Example not found: {example_name}")

    example_module = importlib.import_module(example_stem.replace("/", "."))

    # if does not have `main` func
    if not hasattr(example_module, "main"):
        raise AttributeError(f"Example does not have `main` function: {example_name}")

    await example_module.main()
    assert not any(log_line["log_level"] == "error" for log_line in log_history)

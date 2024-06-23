import builtins
import importlib
import os

import pytest

from asyncflows.utils.loader_utils import load_config_file
from asyncflows.utils.static_utils import check_config_consistency


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


@pytest.fixture
def mock_database_url_env_var():
    database_url_bak = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    yield
    if database_url_bak is not None:
        os.environ["DATABASE_URL"] = database_url_bak
    else:
        del os.environ["DATABASE_URL"]


def get_example_names():
    examples_dir = "asyncflows/examples"
    example_names = []
    for example in os.listdir(examples_dir):
        if example.endswith(".yaml"):
            example_names.append(example[:-5])
    return example_names


# @pytest.mark.skipif(
#     "ANTHROPIC_API_KEY" not in os.environ, reason="requires ANTROPIC_API_KEY env var"
# )
@pytest.mark.parametrize(
    "example_name",
    get_example_names(),
)
async def test_run_example(
    mock_prompt_action,
    mock_transformer_action,
    mock_builtins_input,
    mock_sqlite_engine,
    mock_async_sqlite_engine,
    mock_database_url_env_var,
    example_name,
    log_history,
):
    example_stem = f"asyncflows/examples/{example_name}"
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


example_vars = {
    "application_judgement": {"application", "application_criteria"},
    "chatbot": {"pdf_filepaths", "message", "conversation_history"},
    "debono": {"query"},
    "get_page_title": {"url"},
    "rag": {"texts", "question"},
    "sql_rag": {"query"},
    "text_style_transfer": {"writing_sample", "topic"},
    "meeting_review": {"meeting_notes"},
}


@pytest.mark.parametrize(
    "example_name",
    get_example_names(),
)
async def test_examples_statically(log, example_name):
    example_stem = f"asyncflows/examples/{example_name}"
    example_yaml = f"{example_stem}.yaml"

    vars_ = example_vars.get(example_name, set())

    # if example files don't exist
    if not os.path.exists(example_yaml):
        raise FileNotFoundError(f"Example not found: {example_name}")

    config = load_config_file(example_yaml)
    assert check_config_consistency(log, config, vars_, config.get_default_output())

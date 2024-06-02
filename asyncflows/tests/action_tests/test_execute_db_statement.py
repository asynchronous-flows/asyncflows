import pytest

from asyncflows.actions.execute_db_statement import Inputs, Outputs, ExecuteDBStatement


@pytest.fixture
def action(log, temp_dir):
    return ExecuteDBStatement(log=log, temp_dir=temp_dir)


@pytest.mark.parametrize(
    "inputs, expected_outputs",
    [
        (
            Inputs(
                database_url="sqlite:///dummy_this_is_mocked.db",
                statement="SELECT * FROM users",
            ),
            Outputs(
                text=""" id name fullname nickname   
1   ed   Ed Jones edsnickname""",
                headers=["id", "name", "fullname", "nickname"],
                data=[
                    ["1", "ed", "Ed Jones", "edsnickname"],
                ],
            ),
        ),
    ],
)
async def test_get_db_schema(
    mock_async_sqlite_engine, action, inputs, expected_outputs
):
    outputs = await action.run(inputs)
    assert outputs == expected_outputs

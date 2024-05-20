from unittest.mock import patch

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
                database_url="DUMMY",
                statement="SELECT * FROM users",
            ),
            Outputs(
                result=""" id name fullname nickname   
1   ed   Ed Jones edsnickname""",
            ),
        ),
    ],
)
async def test_get_db_schema(
    dummy_async_sqlite_engine, action, inputs, expected_outputs
):
    with patch(
        "asyncflows.actions.execute_db_statement.create_async_engine",
        return_value=dummy_async_sqlite_engine,
    ):
        outputs = await action.run(inputs)
    assert outputs == expected_outputs
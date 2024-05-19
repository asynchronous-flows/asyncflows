from unittest.mock import patch

import pytest

from asyncflows.actions.get_db_schema import Inputs, Outputs, GetDBSchema


@pytest.fixture
def action(log, temp_dir):
    return GetDBSchema(log=log, temp_dir=temp_dir)


@pytest.mark.parametrize(
    "inputs, expected_outputs",
    [
        (
            Inputs(database_url="DUMMY"),
            Outputs(
                schema_text="""
CREATE TABLE users (
\tid INTEGER NOT NULL, 
\tname VARCHAR, 
\tfullname VARCHAR, 
\tnickname VARCHAR, 
\tPRIMARY KEY (id)
)

"""
            ),
        ),
    ],
)
async def test_get_db_schema(dummy_sqlite_engine, action, inputs, expected_outputs):
    with patch(
        "asyncflows.actions.get_db_schema.create_engine",
        return_value=dummy_sqlite_engine,
    ):
        outputs = await action.run(inputs)
    assert outputs == expected_outputs

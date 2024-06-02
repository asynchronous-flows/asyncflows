import pytest

from asyncflows.actions.get_db_schema import Inputs, Outputs, GetDBSchema


@pytest.fixture
def action(log, temp_dir):
    return GetDBSchema(log=log, temp_dir=temp_dir)


@pytest.mark.parametrize(
    "inputs, expected_outputs",
    [
        (
            Inputs(database_url="sqlite:///dummy_this_is_mocked.db"),
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
async def test_get_db_schema(mock_sqlite_engine, action, inputs, expected_outputs):
    outputs = await action.run(inputs)
    assert outputs == expected_outputs

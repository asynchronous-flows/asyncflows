from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from asyncflows.actions.base import Action, BaseModel, Field


class Inputs(BaseModel):
    database_url: str = Field(description="Database URL (asynchronous)")
    statement: str = Field(description="SQL statement to execute")

    allowed_statement_prefixes: list[str] = Field(
        default=["SELECT"],
        description="List of allowed statement prefixes",
    )
    max_rows: int = Field(
        default=5,
        description="Maximum number of rows to return",
    )


class Outputs(BaseModel):
    result: str = Field(description="Result of the SQL statement")


class ExecuteDBStatement(Action[Inputs, Outputs]):
    name = "execute_db_statement"

    async def run(self, inputs: Inputs) -> Outputs:
        import pandas as pd
        from pandas import Index

        statement = inputs.statement.strip()

        if not any(
            statement.lower().startswith(prefix.lower())
            for prefix in inputs.allowed_statement_prefixes
        ):
            raise ValueError(
                f"Statement must start with one of {inputs.allowed_statement_prefixes}"
            )

        statement = text(statement)

        engine = create_async_engine(inputs.database_url)
        if engine is None:
            raise ValueError("Could not connect to the database")

        async with engine.begin() as conn:
            result = await conn.execute(statement)
            rows = result.fetchall()[: inputs.max_rows]
            column_names = list(result.keys())

        df = pd.DataFrame(rows, columns=Index(column_names))
        result_str = df.to_string(index=False, justify="left")

        return Outputs(result=result_str)
from sqlalchemy import create_engine, MetaData
from sqlalchemy.sql.ddl import CreateTable

from asyncflows.actions.base import BaseModel, Action, Field


class Inputs(BaseModel):
    database_url: str = Field(description="Database URL (synchronous)")


class Outputs(BaseModel):
    schema_text: str = Field(description="Text describing the database schema in `CREATE TABLE` statements")


class GetDBSchema(Action[Inputs, Outputs]):
    name = "get_db_schema"

    async def run(self, inputs: Inputs) -> Outputs:
        engine = create_engine(inputs.database_url)
        if engine is None:
            raise ValueError("Could not connect to the database")

        metadata = MetaData()
        metadata.reflect(bind=engine)

        create_statements = []

        for table_name in metadata.tables:
            table = metadata.tables[table_name]
            create_statements.append(str(CreateTable(table).compile(engine)))

        schema_text = "\n".join(create_statements)

        return Outputs(schema_text=schema_text)

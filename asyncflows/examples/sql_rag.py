import os
from pathlib import Path

from asyncflows import AsyncFlows


async def main():
    # Find the `rag.yaml` file in the `examples` directory
    # This is to make sure the example can be run from any directory,
    # e.g., `DATABASE_URL=... python -m asyncflows.examples.sql_rag`
    examples_dir = Path(os.path.dirname(__file__))
    rag_flow_path = examples_dir / "sql_rag.yaml"

    # Load the chatbot flow
    flow = AsyncFlows.from_file(rag_flow_path)

    # Show the database schema
    schema = await flow.run("get_db_schema")
    print(schema.schema_text)

    # Run the question answering flow
    while True:
        # Get the user's query via CLI interface (swap out with whatever input method you use)
        try:
            query = input("Ask me anything: ")
        except EOFError:
            break

        # Set the query
        question_flow = flow.set_vars(
            query=query,
        )

        # Run the flow and get the result
        result = await question_flow.run()
        print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

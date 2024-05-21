import glob
import os
from pathlib import Path

from asyncflows import AsyncFlows


async def main():
    # Find the `rag.yaml` file in the `examples` directory
    # This is to make sure the example can be run from any directory,
    # e.g., `python -m asyncflows.examples.rag`
    examples_dir = Path(os.path.dirname(__file__))
    rag_flow_path = examples_dir / "rag.yaml"

    # Find all the recipes in the `recipes` directory
    recipes_glob = (examples_dir / "recipes" / "*.md",)
    document_paths = glob.glob(str(recipes_glob))

    texts = []
    for document_path in document_paths:
        with open(document_path, "r") as f:
            texts.append(f.read())

    # Load the chatbot flow
    flow = AsyncFlows.from_file(rag_flow_path).set_vars(
        texts=texts,
    )

    # Run the flow
    while True:
        # Get the user's query via CLI interface (swap out with whatever input method you use)
        try:
            question = input("Ask me anything: ")
        except EOFError:
            break

        # Set the query
        question_flow = flow.set_vars(
            question=question,
        )

        # Run the flow and get the result
        result = await question_flow.run()
        print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

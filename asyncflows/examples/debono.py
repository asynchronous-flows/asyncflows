import os
from pathlib import Path

from asyncflows import AsyncFlows


async def main():
    # Find the `debono.yaml` file in the `examples` directory
    # This is to make sure the example can be run from any directory,
    # e.g., `python -m asyncflows.examples.debono`
    examples_dir = Path(os.path.dirname(__file__))
    debono_flow_path = examples_dir / "debono.yaml"

    query = input("Provide a problem to think about: ")
    flow = AsyncFlows.from_file(debono_flow_path).set_vars(
        query=query,
    )

    # Run the flow and return the default output (result of the blue hat)
    result = await flow.run()
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

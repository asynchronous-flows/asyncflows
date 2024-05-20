import os
from pathlib import Path

from asyncflows import AsyncFlows


async def main():
    # Find the `hello_world.yaml` file in the `examples` directory
    # This is to make sure the example can be run from any directory,
    # e.g., `python -m asyncflows.examples.hello_world`
    examples_dir = Path(os.path.dirname(__file__))
    hello_world_flow_path = examples_dir / "hello_world.yaml"

    # Load the flow from the file
    flow = AsyncFlows.from_file(hello_world_flow_path)

    # Run the flow
    result = await flow.run()

    # Print the result
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

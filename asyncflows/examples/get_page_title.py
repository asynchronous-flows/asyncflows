import os
from pathlib import Path

from asyncflows import AsyncFlows


async def main():
    # Find the `get_page_title.yaml` file in the `examples` directory
    # This is to make sure the example can be run from any directory,
    # e.g., `python -m asyncflows.examples.get_page_title`
    examples_dir = Path(os.path.dirname(__file__))
    get_page_title_flow_path = examples_dir / "get_page_title.yaml"

    flow = AsyncFlows.from_file(get_page_title_flow_path)

    # run the flow
    result = await flow.set_vars(
        url="https://en.wikipedia.org/wiki/Python_(programming_language)",
    ).run()
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

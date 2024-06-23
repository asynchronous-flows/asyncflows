import os
from pathlib import Path

from asyncflows import AsyncFlows


async def main():
    # Find the `hello_world.yaml` file in the `examples` directory
    # This is to make sure the example can be run from any directory,
    # e.g., `python -m asyncflows.examples.hello_world`
    examples_dir = Path(os.path.dirname(__file__))
    meeting_review_flow_path = examples_dir / "meeting_review.yaml"

    # Load the flow from the file
    flow = AsyncFlows.from_file(meeting_review_flow_path).set_vars(
        meeting_notes="We met to discuss project alpha. Jason presented the latest updates on the project. Courtney asked about the timeline for the next milestone. The coffee still needs to be refilled. We agreed to meet again next week to review the progress."
    )

    # Run the flow
    result = await flow.run("structure.data")

    # Print the action items
    print(result["action_items"])


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

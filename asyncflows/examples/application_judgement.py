import os
from pathlib import Path
from asyncflows import AsyncFlows


async def main():
    # Find the `application_judgement` file in the `examples` directory
    # This is to make sure the example can be run from any directory,
    # e.g., `python -m asyncflows.examples.rag`
    examples_dir = Path(os.path.dirname(__file__))
    info_flow_path = examples_dir / "application_judgement.yaml"

    # Find the application and application criteria files
    application_path = examples_dir / "application_information" / "application.txt"
    application_criteria_path = (
        examples_dir / "application_information" / "application_criteria.txt"
    )

    # Read the contents of the application and application criteria files
    with open(application_path, "r") as f:
        application = f.read()
    with open(application_criteria_path, "r") as f:
        application_criteria = f.read()

    # Load the application analysis flow
    flow = AsyncFlows.from_file(info_flow_path).set_vars(
        application=application,
        application_criteria=application_criteria,
    )

    # Run the flow and get the result
    result_judge = await flow.run("judgement.result")
    print(result_judge)
    # Optionally run for feedback

    result_suggest = await flow.run("suggestions.result")
    print(result_suggest)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

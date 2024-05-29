import os
from pathlib import Path
from asyncflows import AsyncFlows

async def main():
    # Find the `rag.yaml` file in the `examples` directory
    # This is to make sure the example can be run from any directory,
    # e.g., `python -m asyncflows.examples.rag`
    examples_dir = Path(os.path.dirname(__file__))
    rag_flow_path = examples_dir / "application_judgement.yaml"

    # Find the application and application info files
    application_path = examples_dir / "application_information" / "application.txt"
    application_info_path = examples_dir / "application_information" / "application_info.txt"

    # Read the contents of the application and application info files
    with open(application_path, "r") as f:
        application = f.read()
    with open(application_info_path, "r") as f:
        application_info = f.read()

    # Load the application analysis flow
    flow = AsyncFlows.from_file(rag_flow_path).set_vars(
        application=application,
        application_info=application_info,
    )


    # Run the flow and get the result
    result = await flow.run()
    # Optionally run for feedback
    # result = await flow.run(suggestions   )
    print(result)



if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
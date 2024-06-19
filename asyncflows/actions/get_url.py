from asyncflows import Action, BaseModel, Field

import aiohttp


class Inputs(BaseModel):
    url: str = Field(
        description="URL of the webpage to GET",
    )


class Outputs(BaseModel):
    result: str = Field(
        description="Text content of the webpage",
    )


class GetURL(Action[Inputs, Outputs]):
    name = "get_url"

    async def run(self, inputs: Inputs) -> Outputs:
        async with aiohttp.ClientSession() as session:
            async with session.get(inputs.url) as response:
                return Outputs(result=await response.text())

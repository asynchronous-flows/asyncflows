from asyncflows import Action, BaseModel, Field

import re


class Inputs(BaseModel):
    text: str = Field(description="Text to extract out of <tag>text</tag>")
    tag: str = Field(description="Tag to extract from")


class Outputs(BaseModel):
    result: str = Field(description="Text extracted from the tag")


class ExtractXMLTag(Action[Inputs, Outputs]):
    name = "extract_xml_tag"

    async def run(self, inputs: Inputs) -> Outputs:
        opening_tag = f"<{inputs.tag}>"
        closing_tag = f"</{inputs.tag}>"

        if opening_tag not in inputs.text:
            self.log.debug("Opening tag not found in text", tag=inputs.tag)
            return Outputs(result="")

        if closing_tag not in inputs.text:
            # If the closing tag is not found, return the text from the opening tag to the end of the text
            self.log.debug("Closing tag not found in text", tag=inputs.tag)
            text = inputs.text.split(opening_tag)[1].strip()
            return Outputs(result=text)

        # Extract the text between the opening and closing tags
        pattern = re.compile(rf"{opening_tag}\s*(.*?)\s*{closing_tag}", re.DOTALL)
        match = pattern.search(inputs.text)
        if match is None:
            self.log.warning("No text found between tags", tag=inputs.tag)
            return Outputs(result="")
        text = match.group(1).strip()
        return Outputs(result=text)

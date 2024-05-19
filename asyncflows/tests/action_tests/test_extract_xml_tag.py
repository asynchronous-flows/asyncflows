import pytest
from asyncflows.actions.extract_xml_tag import ExtractXMLTag, Inputs


@pytest.mark.parametrize(
    "input_text, tag, expected_text",
    [
        (
            """
here is a summary:
<summary>
blablabla
</summary>
""",
            "summary",
            "blablabla",
        ),
        (
            "hi",
            "summary",
            "",
        ),
        (
            "<summary></summary>",
            "summary",
            "",
        ),
        (
            "something <tag> hm",
            "tag",
            "hm",
        ),
    ],
)
async def test_extract_tag(log, temp_dir, input_text, tag, expected_text):
    extract_tag_action = ExtractXMLTag(log=log, temp_dir=temp_dir)
    inputs = Inputs(text=input_text, tag=tag)
    outputs = await extract_tag_action.run(inputs)
    assert outputs.result == expected_text

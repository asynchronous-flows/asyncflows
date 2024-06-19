import ast

import jsonschema
import pytest
from asyncflows.models.config.common import (
    StrictModel,
)
from asyncflows.utils.rendering_utils import (
    extract_vars_from_template,
    render_template,
    render_var,
    _jinja_env,
)
from asyncflows.models.config.value_declarations import (
    TextDeclaration,
    LambdaDeclaration,
)
from asyncflows.models.primitives import TemplateString
from asyncflows.utils.config_utils import get_full_paths_from_ast


@pytest.mark.parametrize(
    "template, expected_vars",
    [
        (
            """
{% for message in conversation_history -%}
{{ message.user }}: {{ message.message }}
{% endfor %}
""",
            {"conversation_history"},
        ),
        (
            "{% set x = 2 %}",
            set(),
        ),
        (
            """
{% for message in conversation_history -%}
{% set x = message.user %}
{% endfor %}
""",
            {"conversation_history"},
        ),
        (
            """
{% set citation_ids = [] %}
{% for section in grobid.paper.sections -%}
  {% if section.number in outline_selection_extractor.results -%}
    {% for citation_id in section.citation_ids -%}
      {% if citation_id not in citation_ids -%}
        {% set _ = citation_ids.append(citation_id) %}
      {% endif %}
    {% endfor %}
  {% endif %}
{% endfor %}
{% for citation_id in citation_ids -%}
  {{ grobid.paper.citations[citation_id].full_reference }}
{% endfor %}""",
            {"grobid", "outline_selection_extractor"},
        ),
    ],
)
def test_extract_jinja2_vars(template, expected_vars):
    assert extract_vars_from_template(template) == expected_vars


@pytest.mark.parametrize(
    "context, template, expected_output",
    [
        # list
        (
            {
                "concepts_extractor": {
                    "results": ["Transformers", "Mathematical perspective"]
                }
            },
            """Concepts:
{% for concept in concepts_extractor.results -%}
- {{ concept }}
{% endfor %}""",
            """Concepts:
- Transformers
- Mathematical perspective
""",
        ),
        # list subset
        (
            {
                "concepts_extractor": {
                    "results": ["Transformers", "Mathematical perspective", "NLP"]
                }
            },
            """Concepts:
{% for concept in concepts_extractor.results[-2:] -%}
- {{ concept }}
{% endfor %}""",
            """Concepts:
- Mathematical perspective
- NLP
""",
        ),
        # list with break
        (
            {
                "concepts_extractor": {
                    "results": ["Transformers", "Mathematical perspective"]
                }
            },
            """Concepts:
{% for concept in concepts_extractor.results -%}
- {{ concept }}
{% break %}
{% endfor %}""",
            """Concepts:
- Transformers
""",
        ),
        # rstrip
        (
            {
                "concepts_extractor": {
                    "results": ["Transformers....", "Mathematical perspective."]
                }
            },
            """Concepts:
{% for concept in concepts_extractor.results -%}
- {{ concept.rstrip(".") }}
{% endfor %}""",
            """Concepts:
- Transformers
- Mathematical perspective
""",
        ),
        # this sausage of citations
        (
            {
                "grobid": {
                    "paper": {
                        "sections": [
                            {
                                "number": "1",
                                "citation_ids": ["1", "2"],
                            },
                            {
                                "number": "2",
                                "citation_ids": ["3"],
                            },
                        ],
                        "citations": {
                            "1": {"full_reference": "1"},
                            "2": {"full_reference": "2"},
                            "3": {"full_reference": "3"},
                            "4": {"full_reference": "4"},
                            "5": {"full_reference": "5"},
                        },
                    },
                },
                "outline_selection_extractor": {"results": ["1", "2"]},
            },
            """
{% set citation_ids = [] -%}
{% for section in grobid.paper.sections -%}
  {% if section.number in outline_selection_extractor.results -%}
    {% for citation_id in section.citation_ids -%}
      {% if citation_id not in citation_ids -%}
        {% set _ = citation_ids.append(citation_id) -%}
      {% endif -%}
    {% endfor -%}
  {% endif -%}
{% endfor -%}
{% for citation_id in citation_ids -%}
  {{ grobid.paper.citations[citation_id].full_reference }}
{% endfor %}
""",
            """
1
2
3
""",
        ),
    ],
)
async def test_jinja2_render(
    log,
    context,
    template,
    expected_output,
):
    template_obj = TextDeclaration(text=template)
    assert await template_obj.render(context) == expected_output


@pytest.mark.parametrize(
    "expr, expected_dependencies",
    [
        ("2", set()),
        ("a.result", {"a"}),
        ("[a for a in [1, 2, 3]]", set()),
        ("[section.number for section in grobid.sections]", {"grobid"}),
        (
            "[section.number for a, section in (something, grobid.sections)]",
            {"something", "grobid"},
        ),
        ("{a: b for a, b in grobid.sections.items()}", {"grobid"}),
        (
            """
[page
 for flow in extract_pdf_texts
 for page in flow.extractor.pages]""",
            {"extract_pdf_texts"},
        ),
        (
            """
[page.text
 for page in retrieval.result]""",
            {"retrieval"},
        ),
    ],
)
def test_lambda_declaration_dependency_extraction(expr, expected_dependencies):
    dec = LambdaDeclaration(**{"lambda": expr})
    assert dec.get_dependencies() == expected_dependencies


@pytest.mark.parametrize(
    "expr, locals_, expected_result",
    [
        ("2", {}, 2),
        ("a.result", {"a": {"result": 3}}, 3),
        ("[a for a in [1, 2, 3]]", {}, [1, 2, 3]),
        (
            "[section['number'] for section in grobid.sections]",
            {"grobid": {"sections": [{"number": 3}]}},
            [3],
        ),
        (
            "[section.number for section in grobid.sections]",
            {"grobid": {"sections": [{"number": 3}]}},
            [3],
        ),
        (
            "[section.number for a, section in (something, grobid.sections)]",
            {
                "something": ({"number": "a"}, {"number": "b"}),
                "grobid": {"sections": [{"number": 2}, {"number": 3}]},
            },
            ["b", 3],
        ),
        # TODO make sure we can constrain stuff like this
        # this is testing calls being blocked, but we allow them for `range(3)` type stuff
        # simpleeval should catch only allowing certain functions
        # (
        #     "__import__(os).listdir('.')",
        #     {},
        #     None,
        # ),
        # TODO support BaseModel formats in output context
        # (
        #     "{a: b for a, b in grobid.sections.items()}",
        #     {"grobid": {"sections": {"a": "b"}}},
        #     {"a": "b"},
        # ),
    ],
)
async def test_lambda_declaration_rendering(expr, locals_, expected_result, log):
    dec = LambdaDeclaration(**{"lambda": expr})
    if expected_result is None:
        with pytest.raises(ValueError):
            await dec.render(locals_)
    else:
        assert await dec.render(locals_) == expected_result


@pytest.mark.parametrize(
    "expr, expected_paths",
    [
        ("2", set()),
        ("a.result", {"a.result"}),
        ("[a for a in [1, 2, 3]]", set()),
        ("[section.number for section in grobid.sections]", {"grobid.sections"}),
        (
            "[section.number for a, section in (something, grobid.sections)]",
            {"something", "grobid.sections"},
        ),
        ("{a: b for a, b in grobid.sections.items()}", {"grobid.sections.items"}),
    ],
)
def test_get_full_lambda_paths(expr, expected_paths):
    assert get_full_paths_from_ast(ast.parse(expr, mode="eval")) == expected_paths


def extract_json_schema_from_template(text: TemplateString) -> dict:
    # TODO find an alternative; jinja2schema just qualifies everything except containers as `scalar`,
    #  even lists, and not maintained (last commit like 2016)
    from jinja2schema import parse, infer_from_ast, to_json_schema

    return to_json_schema(
        # infer(text)
        infer_from_ast(parse(text, jinja2_env=_jinja_env), ignore_constants=True)
    )


@pytest.mark.parametrize(
    "text, example_data",
    [
        (
            """
{% for message in conversation_history -%}
{{ message.user }}: {{ message.message }}
{% endfor %}
""",
            msg_list := {
                "conversation_history": [
                    {
                        "user": "Alice",
                        "message": "Hello",
                    },
                    {
                        "user": "Bob",
                        "message": "Hi",
                    },
                ],
            },
        ),
        (
            """
{% for message in conversation_history[-20:] -%}
{{ message.user }}: {{ message.message }}
{% endfor %}
""",
            msg_list,
        ),
    ],
)
def test_json_schema_extraction_validation(text, example_data):
    json_schema = extract_json_schema_from_template(text)
    jsonschema.validate(example_data, json_schema)


class Message(StrictModel):
    user: str
    message: str


@pytest.mark.parametrize(
    "template, context, expected_output",
    [
        (
            "{{ message.user }}",
            {
                "message": {
                    "user": "Alice",
                }
            },
            "Alice",
        ),
        (
            "{{ message.user }}",
            {
                "message": (
                    msg := Message(
                        user="Alice",
                        message="Hello",
                    )
                )
            },
            "Alice",
        ),
        ("{{ message }}", {"message": msg}, msg),
        (
            """{% for message in history -%}
{{ message }}
{% endfor %}""",
            {
                "history": [],
            },
            None,
        ),
        (
            """{% if message %}
{{ message }}
{% endif %}""",
            {
                "message": False,
            },
            None,
        ),
    ],
)
async def test_render_template(template, context, expected_output):
    assert await render_template(template, context) == expected_output


@pytest.mark.parametrize(
    "template, context, expected_output",
    [
        (
            "message.user",
            {
                "message": {
                    "user": "Alice",
                }
            },
            "Alice",
        ),
        (
            "message.user",
            {
                "message": (
                    msg := Message(
                        user="Alice",
                        message="Hello",
                    )
                )
            },
            "Alice",
        ),
        ("message", {"message": msg}, msg),
        (
            "history[0].user",
            {
                "history": [
                    Message(
                        user="Alice",
                        message="Hello",
                    ),
                    Message(
                        user="Bob",
                        message="Hi",
                    ),
                ]
            },
            "Alice",
        ),
    ],
)
async def test_render_var(template, context, expected_output):
    assert await render_var(template, context) == expected_output

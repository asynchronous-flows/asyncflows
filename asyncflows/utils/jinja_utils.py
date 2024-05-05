from itertools import islice, chain
from types import GeneratorType

import jinja2.nativetypes
import typing as t


def custom_native_concat(values: t.Iterable[t.Any]) -> t.Optional[t.Any]:
    """
    An amended jinja2.nativetypes.native_concat that doesn't try to parse the output as a Python literal.
    """
    head = list(islice(values, 2))

    if not head:
        return None

    if len(head) == 1:
        raw = head[0]
        if not isinstance(raw, str):
            return raw
    else:
        if isinstance(values, GeneratorType):
            values = chain(head, values)
        raw = "".join([str(v) for v in values])

    # try:
    #     return literal_eval(
    #         # In Python 3.10+ ast.literal_eval removes leading spaces/tabs
    #         # from the given string. For backwards compatibility we need to
    #         # parse the string ourselves without removing leading spaces/tabs.
    #         parse(raw, mode="eval")
    #     )
    # except (ValueError, SyntaxError, MemoryError):
    #     return raw
    return raw


class NativeEnvironment(jinja2.nativetypes.NativeEnvironment):
    concat = staticmethod(custom_native_concat)


class NativeTemplate(jinja2.nativetypes.NativeTemplate):
    environment_class = NativeEnvironment


NativeEnvironment.template_class = NativeTemplate

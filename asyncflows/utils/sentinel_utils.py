import inspect
from typing import Any, TypeGuard


class Sentinel:
    pass


def is_sentinel(value: Any) -> TypeGuard[type[Sentinel]]:
    return inspect.isclass(value) and issubclass(value, Sentinel)


def is_set_of_tuples(value: Any) -> TypeGuard[set[tuple]]:
    """Custom type guard to check if the value is a set of tuples."""
    if not isinstance(value, set):
        return False
    for item in value:
        if not isinstance(item, tuple):
            return False
    return True

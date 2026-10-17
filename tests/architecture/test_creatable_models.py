"""`creates` declarations: what an object's content can create in play is built when the object is created.

A subclass declares its own products by extending its parent's tuple, so a
declaration never drops a product its parent's rules still create.
"""

import server.worker  # noqa: F401  (imports every built-in content module)
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject


def _subclasses(root: type) -> list[type]:
    found, stack = [], [root]
    while stack:
        for subclass in stack.pop().__subclasses__():
            if subclass not in found:
                found.append(subclass)
                stack.append(subclass)
    return found


def test_a_subclass_creates_everything_its_parents_create():
    dropped = []
    for model in (*_subclasses(BaseObject), *_subclasses(BaseBlock)):
        for base in model.__bases__:
            if issubclass(base, (BaseObject, BaseBlock)):
                lost = set(base.creates) - set(model.creates)
                if lost:
                    dropped.append((f"{model.__module__}.{model.__qualname__}", base.__qualname__,
                        sorted(product.__qualname__ for product in lost)))
    assert dropped == []

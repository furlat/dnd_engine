"""Architecture: every block names its own value fields.

Repository policy (AGENTS.md: no getattr to discover data): a block's values come from its explicit
`value_fields()`, never from scanning its fields by name. This check keeps the explicit lists
complete: every field a block class declares as a ModifiableValue is returned by `value_fields()`,
in declaration order, so a new value field cannot silently miss ownership, sourcing or cleanup.
"""

from types import SimpleNamespace
from typing import Iterator, Optional
from uuid import uuid4

import dnd.game  # noqa: F401  (imports every block class)
from dnd.core.base_block import BaseBlock
from dnd.core.values import ModifiableValue


def _block_classes(cls: type[BaseBlock] = BaseBlock) -> Iterator[type[BaseBlock]]:
    for sub in cls.__subclasses__():
        yield sub
        yield from _block_classes(sub)


def check_block_names_its_value_fields(cls: type[BaseBlock]) -> None:
    declared = [name for name, field in cls.model_fields.items()
                if field.annotation in (ModifiableValue, Optional[ModifiableValue])]
    values = {name: ModifiableValue(source_entity_uuid=uuid4(), base=0, name=name) for name in declared}
    # The class's own value_fields read against just its declared fields, without building the block.
    listed = cls.value_fields(SimpleNamespace(**values))  # type: ignore[arg-type]
    assert [value.name for value in listed] == declared, cls.__qualname__
    assert all(value is values[value.name] for value in listed), cls.__qualname__


def test_every_block_names_its_value_fields() -> None:
    classes = [cls for cls in _block_classes()
               if any(field.annotation in (ModifiableValue, Optional[ModifiableValue])
                      for field in cls.model_fields.values())]
    assert len(classes) >= 13
    for cls in classes:
        check_block_names_its_value_fields(cls)

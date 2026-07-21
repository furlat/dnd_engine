"""Small JSON-compatible immutable collection contracts."""

from __future__ import annotations

from typing import Any, Never, Optional, TypeVar


Key = TypeVar("Key")
Value = TypeVar("Value")


class FrozenDict(dict[Key, Value]):
    """Dictionary-compatible mapping that rejects structural mutation."""

    @staticmethod
    def _immutable() -> Never:
        raise TypeError("Protocol mappings are immutable")

    def __setitem__(self, key: Key, value: Value) -> Never:
        self._immutable()

    def __delitem__(self, key: Key) -> Never:
        self._immutable()

    def clear(self) -> Never:
        self._immutable()

    def pop(self, key: Key, default: Any = None) -> Never:
        self._immutable()

    def popitem(self) -> Never:
        self._immutable()

    def setdefault(self, key: Key, default: Optional[Value] = None) -> Never:
        self._immutable()

    def update(self, *args: Any, **kwargs: Value) -> Never:
        self._immutable()

    def __ior__(self, value: Any) -> Never:
        self._immutable()

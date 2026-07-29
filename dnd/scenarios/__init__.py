"""Scenario package marker.

Import concrete scenario modules explicitly.  Keeping this package initializer
inert prevents a neutral model import from constructing the entire authored
catalog and every historical arena.
"""

__all__: tuple[str, ...] = ()

"""Evaluation, gauntlet, tournament, and artifact subpackages.

Import concrete symbols from their owning modules. The package initializer stays
lightweight so server-side gauntlet streams can import contracts without pulling
in self-play runtimes or server adapters.
"""

__all__: list[str] = []

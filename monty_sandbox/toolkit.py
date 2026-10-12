"""Portable, explicitly selected source blocks. No heap or game serialization."""
from typing import Literal, TypedDict


class ToolSource(TypedDict):
    name: str
    code: str


class Toolkit(TypedDict):
    format: Literal['monty-tools-v1']
    sources: list[ToolSource]


def validate_source(name: str, code: str) -> None:
    if not name or len(name) > 64 or not code or len(code) > 32768:
        raise ValueError('Tool source needs a name (1–64 characters) and code (1–32768 characters)')


def selected_sources(sources: dict[str, str], names: list[str]) -> Toolkit:
    if len(names) > 16 or len(set(names)) != len(names):
        raise ValueError('Choose up to 16 distinct source names in dependency order')
    if any(name not in sources for name in names):
        raise ValueError('Unknown saved source name')
    return {'format': 'monty-tools-v1', 'sources': [{'name': name, 'code': sources[name]} for name in names]}


def validate_bundle(bundle: Toolkit | None) -> list[ToolSource]:
    if bundle is None:
        return []
    sources = bundle['sources']
    if len(sources) > 16 or len({row['name'] for row in sources}) != len(sources):
        raise ValueError('A toolkit needs up to 16 distinctly named sources')
    for row in sources:
        validate_source(row['name'], row['code'])
    return sources

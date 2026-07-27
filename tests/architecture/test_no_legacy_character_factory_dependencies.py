"""Production code must use schema-2 character composition exclusively."""

from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MAINTAINED_ROOTS = (
    REPOSITORY_ROOT / "ai",
    REPOSITORY_ROOT / "dnd",
    REPOSITORY_ROOT / "server",
    REPOSITORY_ROOT / "tests",
)
LEGACY_FACTORY_MODULES = frozenset({
    "dnd.classes.barbarian_factory",
    "dnd.classes.fighter_factory",
    "dnd.classes.sorcerer_factory",
})
LEGACY_IMPLEMENTATION_PATHS = frozenset({
    Path("dnd/classes/barbarian_factory.py"),
    Path("dnd/classes/fighter_factory.py"),
    Path("dnd/classes/sorcerer_factory.py"),
})


def _maintained_python_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for root in MAINTAINED_ROOTS
            for path in root.rglob("*.py")
            if path.relative_to(REPOSITORY_ROOT)
            not in LEGACY_IMPLEMENTATION_PATHS
        ),
    )


def test_maintained_code_has_no_legacy_character_factory_dependencies(
) -> None:
    """No maintained source or test may import retired one-shot builders."""

    assert all(
        not (REPOSITORY_ROOT / relative).exists()
        for relative in LEGACY_IMPLEMENTATION_PATHS
    )
    violations: list[str] = []
    for path in _maintained_python_paths():
        relative = path.relative_to(REPOSITORY_ROOT)
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(relative),
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules = (node.module or "",)
            else:
                continue
            for module_name in imported_modules:
                if module_name in LEGACY_FACTORY_MODULES:
                    violations.append(
                        f"{relative}:{node.lineno} imports {module_name}",
                    )

    assert violations == [], (
        "Character creation and its tests must flow through "
        "CharacterDefinitionRevisionV2 + materialize_character:\n"
        + "\n".join(violations)
    )

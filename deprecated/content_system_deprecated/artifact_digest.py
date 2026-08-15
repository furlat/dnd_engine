"""Deterministic source closure and digesting for trusted built-in content."""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Iterable
from pathlib import Path


class LocalContentImportError(RuntimeError):
    """A local content implementation import could not be authenticated."""


def _module_source_candidates(
    module_name: str,
    *,
    repository_root: Path,
) -> tuple[Path, Path, bool, bool]:
    """Return exact module/package candidates and their existence facts."""
    if module_name != "dnd" and not module_name.startswith("dnd."):
        raise ValueError(
            f"Local content modules must live under dnd: {module_name}",
        )
    relative = Path(*module_name.split("."))
    module_path = repository_root / relative.with_suffix(".py")
    package_path = repository_root / relative / "__init__.py"
    return (
        module_path,
        package_path,
        module_path.is_file(),
        package_path.is_file(),
    )


def _module_source_path(
    module_name: str,
    *,
    repository_root: Path,
) -> Path:
    """Resolve one exact local Python module without importing it."""
    (
        module_path,
        package_path,
        module_exists,
        package_exists,
    ) = _module_source_candidates(
        module_name,
        repository_root=repository_root,
    )
    if module_exists == package_exists:
        reason = "ambiguous" if module_exists else "unresolved"
        raise LocalContentImportError(
            f"{reason} local content module {module_name}",
        )
    return package_path if package_exists else module_path


def _package_ancestors(module_name: str) -> tuple[str, ...]:
    """Return every package imported while resolving ``module_name``."""
    parts = module_name.split(".")
    return tuple(
        ".".join(parts[:index])
        for index in range(1, len(parts))
    )


def _relative_import_base(
    *,
    current_module: str,
    current_is_package: bool,
    imported_module: str | None,
    level: int,
) -> str:
    """Resolve one ImportFrom base with normal Python package semantics."""
    package = (
        current_module
        if current_is_package
        else current_module.rpartition(".")[0]
    )
    package_parts = package.split(".") if package else []
    upward_steps = level - 1
    if upward_steps >= len(package_parts):
        raise LocalContentImportError(
            f"relative import escapes dnd package in {current_module}",
        )
    base_parts = package_parts[: len(package_parts) - upward_steps]
    if imported_module:
        base_parts.extend(imported_module.split("."))
    return ".".join(base_parts)


def _local_imports(
    *,
    source_path: Path,
    module_name: str,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Parse local import bases and their possible package submodules."""
    try:
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=source_path.as_posix(),
        )
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise LocalContentImportError(
            f"cannot parse local content module {module_name}: {exc}",
        ) from exc
    is_package = source_path.name == "__init__.py"
    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "dnd" or alias.name.startswith("dnd."):
                    imports.append((alias.name, ()))
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            base = _relative_import_base(
                current_module=module_name,
                current_is_package=is_package,
                imported_module=node.module,
                level=node.level,
            )
        else:
            base = node.module or ""
        if base != "dnd" and not base.startswith("dnd."):
            continue
        candidates = tuple(
            alias.name
            for alias in node.names
            if alias.name != "*"
        )
        imports.append((base, candidates))
    return tuple(imports)


def resolve_local_python_module_closure(
    root_modules: Iterable[str],
    *,
    repository_root: Path,
) -> tuple[Path, ...]:
    """Resolve the complete static local import closure of exact roots.

    ``from package import name`` always authenticates the package and, when
    ``name`` is itself a resolvable module, that submodule too. Missing import
    bases fail closed; names exported by an existing module remain ordinary
    attributes and are not mistaken for missing modules.
    """
    root = repository_root.resolve(strict=True)
    pending = list(sorted(set(root_modules), reverse=True))
    if not pending:
        raise ValueError("At least one built-in implementation root is required")
    resolved_modules: dict[str, Path] = {}
    while pending:
        module_name = pending.pop()
        if module_name in resolved_modules:
            continue
        source_path = _module_source_path(
            module_name,
            repository_root=root,
        ).resolve(strict=True)
        try:
            source_path.relative_to(root)
        except ValueError as exc:
            raise LocalContentImportError(
                f"local content module escapes repository: {module_name}",
            ) from exc
        resolved_modules[module_name] = source_path

        discovered: set[str] = set(_package_ancestors(module_name))
        for base, possible_submodules in _local_imports(
            source_path=source_path,
            module_name=module_name,
        ):
            _module_source_path(base, repository_root=root)
            discovered.add(base)
            base_path = _module_source_path(base, repository_root=root)
            if base_path.name != "__init__.py":
                continue
            for name in possible_submodules:
                candidate = f"{base}.{name}"
                (
                    _,
                    _,
                    module_exists,
                    package_exists,
                ) = _module_source_candidates(
                    candidate,
                    repository_root=root,
                )
                if module_exists and package_exists:
                    raise LocalContentImportError(
                        f"ambiguous local content module {candidate}",
                    )
                if not module_exists and not package_exists:
                    continue
                discovered.add(candidate)
        pending.extend(
            sorted(
                discovered.difference(resolved_modules),
                reverse=True,
            ),
        )

    return tuple(
        sorted(
            set(resolved_modules.values()),
            key=lambda path: path.relative_to(root).as_posix(),
        ),
    )


def digest_artifact_paths(
    paths: Iterable[Path],
    *,
    repository_root: Path,
) -> str:
    """Hash one exact, path-framed artifact set."""
    root = repository_root.resolve(strict=True)
    resolved_paths = tuple(path.resolve(strict=True) for path in paths)
    if not resolved_paths:
        raise ValueError("At least one built-in artifact is required")
    if len(resolved_paths) != len(set(resolved_paths)):
        raise ValueError("Built-in artifact paths must be unique")
    relative_paths: dict[Path, str] = {}
    for resolved in resolved_paths:
        try:
            relative_paths[resolved] = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"Built-in artifact escapes repository root: {resolved}",
            ) from exc
    digest = hashlib.sha256()
    digest.update(b"dnd-engine-built-in-content-artifacts-v2\0")
    for resolved in sorted(
        resolved_paths,
        key=relative_paths.__getitem__,
    ):
        relative = relative_paths[resolved].encode("utf-8")
        payload = resolved.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()

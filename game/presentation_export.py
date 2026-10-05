"""Versioned, relocatable authoring export using the existing typed catalog.

This boundary rewrites filesystem storage references, not resource identities or
behavior. It neither loads textures nor creates a second authoring registry.
"""

from dataclasses import replace
from hashlib import sha256
from enum import Enum
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

from game.animation_types import AnimationData


class PresentationCatalogExport(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    schema_version: Literal[1] = 1
    time_unit: Literal['milliseconds'] = 'milliseconds'
    grid_unit: Literal['cells'] = 'cells'
    elevation_step_feet: Literal[5] = 5
    catalog: AnimationData


def export_catalog(data: AnimationData, package_root: Path) -> bytes:
    """Retain all effective typed fields, with package-relative file locations.

    The archive-only unused source contexts are excluded from executable data.
    A resource outside the declared package is an error, never a leaked path.
    The caller's existing installer owns the files; this function copies none.
    """
    adapter = TypeAdapter(AnimationData)
    source = replace(data, context_source_json='',
        projectile_assets={identity: asset.model_copy(update={'source': None, 'preview': None})
                           for identity, asset in data.projectile_assets.items()})
    paths: dict[tuple[str | int, ...], str] = {}

    def collect(value: object, location: tuple[str | int, ...] = ()) -> None:
        if isinstance(value, Path):
            if value == Path('.'):
                return
            resolved = value.resolve()
            try:
                relative = resolved.relative_to(package_root.resolve())
            except ValueError as error:
                raise ValueError(f'Catalog resource is outside the package: {value}') from error
            paths[location] = relative.as_posix()
        elif isinstance(value, dict):
            for key, child in value.items():
                collect(child, (*location, str(key.value if isinstance(key, Enum) else key)))
        elif isinstance(value, (tuple, list, set, frozenset)):
            for index, child in enumerate(value):
                collect(child, (*location, index))

    collect(adapter.dump_python(source, mode='python', warnings='error'))
    # Encode using the declared types first. Rewrite only actual Path values
    # collected above; logical URL strings are not treated as filesystem paths.
    def relocate(value: JsonValue, location: tuple[str | int, ...] = ()) -> JsonValue:
        if location in paths:
            return paths[location]
        if isinstance(value, list):
            return [relocate(child, (*location, index)) for index, child in enumerate(value)]
        if isinstance(value, dict):
            return {key: relocate(child, (*location, key)) for key, child in value.items()}
        return value

    value = TypeAdapter(JsonValue).validate_json(adapter.dump_json(source, warnings='error'))
    catalog = adapter.validate_json(json.dumps(relocate(value), allow_nan=False))
    exported = PresentationCatalogExport(catalog=catalog)
    return json.dumps(json.loads(exported.model_dump_json()), sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def catalog_fingerprint(data: AnimationData, package_root: Path) -> str:
    return sha256(export_catalog(data, package_root)).hexdigest()

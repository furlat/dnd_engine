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

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from dnd.items.authored_variant_inventory import AuthoredItemVariantInventory, AuthoredItemVariantLedger
from game.animation_types import AnimationData
from game.asset_types import BytePlaneSource, ImageResourceSource
from game.environment_art import EnvironmentDocument
from game.item_appearance import ItemAppearanceDocument, ItemMaterialDocument, SourcePaletteDocument
from game.ui.media_types import ChoiceRecord, SkinSource, UI_FONT_FAMILIES, UIPresentationDocument
from game.world_binding_types import AssetDocument, WorldBindingsSource


def _relative_resource(path: Path, root: Path, parents: dict[Path, Path]) -> str:
    local = path if path.is_absolute() else root / path
    parent = parents.get(local.parent)
    if parent is None:
        parent = parents[local.parent] = local.parent.resolve()
    resolved = parent / local.name
    if resolved.is_symlink():
        resolved = resolved.resolve()
    return resolved.relative_to(root).as_posix()


class PresentationCatalogExport(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    schema_version: Literal[2] = 2
    time_unit: Literal['milliseconds'] = 'milliseconds'
    grid_unit: Literal['cells'] = 'cells'
    elevation_step_feet: Literal[5] = 5
    catalog: AnimationData
    assets: AssetDocument
    world: WorldBindingsSource
    environment: EnvironmentDocument
    item_appearances: ItemAppearanceDocument
    item_materials: ItemMaterialDocument
    item_visuals: AuthoredItemVariantInventory
    source_palettes: SourcePaletteDocument
    ui_resources: dict[str, ImageResourceSource]
    ui_presentation: UIPresentationDocument
    ui_choices: tuple[ChoiceRecord, ...]
    ui_skin: dict[str, dict[str, SkinSource]]
    ui_fonts: dict[str, tuple[str, ...]]
    byte_planes: dict[str, BytePlaneSource] = Field(default_factory=dict)


def catalog_documents(data: AnimationData, package_root: Path) -> PresentationCatalogExport:
    """Join existing source owners; never export native content or source paths.

    All documents are cold values. Loading the public artwork metadata does not
    initialize a renderer, import the desktop UI or disclose a game/session.
    """
    root = package_root / 'game/data'
    ledger = AuthoredItemVariantLedger.model_validate_json(
        (package_root / 'content_data/ledgers/neuroclient_authored_item_visuals.json').read_bytes())
    return PresentationCatalogExport(
        catalog=data,
        assets=AssetDocument.model_validate_json((root / 'assets.json').read_bytes()),
        world=WorldBindingsSource.model_validate_json((root / 'world_bindings.json').read_bytes()),
        environment=EnvironmentDocument.model_validate_json((root / 'environment_art.json').read_bytes()),
        item_appearances=ItemAppearanceDocument.model_validate_json((root / 'item_appearances.json').read_bytes()),
        item_materials=ItemMaterialDocument.model_validate_json((root / 'item-materials.json').read_bytes()),
        item_visuals=ledger.inventory,
        source_palettes=SourcePaletteDocument.model_validate_json(
            (root / 'neuroclient/source/src/render/data/animation/paletteMap.json').read_bytes()),
        ui_resources=TypeAdapter(dict[str, ImageResourceSource]).validate_json((root / 'ui_media.json').read_bytes()),
        ui_presentation=UIPresentationDocument.model_validate_json((root / 'ui_presentation.json').read_bytes()),
        ui_choices=TypeAdapter(tuple[ChoiceRecord, ...]).validate_json((root / 'ui_choices.json').read_bytes()),
        ui_skin=TypeAdapter(dict[str, dict[str, SkinSource]]).validate_json((root / 'ui_skin.json').read_bytes()),
        ui_fonts=UI_FONT_FAMILIES,
    )


def export_catalog(data: AnimationData, package_root: Path, *,
                   byte_planes: dict[str, BytePlaneSource] | None = None) -> bytes:
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
    addresses: dict[Path, str] = {}
    parents: dict[Path, Path] = {}
    root = package_root.resolve()

    def collect(value: object, location: tuple[str | int, ...] = ()) -> None:
        if isinstance(value, Path):
            if value == Path('.'):
                return
            if value not in addresses:
                try:
                    addresses[value] = _relative_resource(value, root, parents)
                except ValueError as error:
                    raise ValueError(f'Catalog resource is outside the package: {value}') from error
            paths[location] = addresses[value]
        elif isinstance(value, dict):
            for key, child in value.items():
                collect(child, (*location, str(key.value if isinstance(key, Enum) else key)))
        elif isinstance(value, (tuple, list, set, frozenset)):
            for index, child in enumerate(value):
                collect(child, (*location, index))

    collect(adapter.dump_python(source, mode='python', warnings='error'))
    # Source models are already validated. Relocate only their actual Path
    # fields without reconstructing/revalidating the entire animation library.
    # Logical IDs and prose that happen to resemble paths remain untouched.
    exported = catalog_documents(source, package_root)
    if byte_planes:
        exported = exported.model_copy(update={'byte_planes': byte_planes})
    value = json.loads(exported.model_dump_json(warnings='error'))
    for location, relative in paths.items():
        owner = value['catalog']
        for key in location[:-1]:
            owner = owner[key]
        owner[location[-1]] = relative
    return json.dumps(value, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def catalog_fingerprint(data: AnimationData, package_root: Path) -> str:
    return sha256(export_catalog(data, package_root)).hexdigest()


def catalog_dependencies(document: PresentationCatalogExport, package_root: Path) -> dict[str, tuple[str, ...]]:
    """Resolve every declared resource and companion, retaining its source pointer.

    This is an offline dependency walk, not a file-extension search or a scene
    selector. Surface archives are source inputs until the registered-media
    packer replaces them with compact browser parts.
    """
    dependencies: dict[str, set[str]] = {}
    addresses: dict[Path, str] = {}
    parents: dict[Path, Path] = {}
    root = package_root.resolve()

    def segment(value: object) -> str:
        return str(value).replace('~', '~0').replace('/', '~1')

    def add(path: Path, pointer: str) -> None:
        if pointer == '/catalog/media_root':
            return  # Package location, never a downloadable resource.
        if path in addresses:
            dependencies[addresses[path]].add(pointer)
            return
        try:
            relative = _relative_resource(path, root, parents)
        except ValueError as error:
            raise ValueError(f'{pointer}: resource is outside package: {path}') from error
        dependencies.setdefault(relative, set()).add(pointer)
        addresses[path] = relative

    def paths(value: object, pointer: str) -> None:
        if isinstance(value, Path):
            if value != Path('.'):
                add(value, pointer)
        elif isinstance(value, dict):
            for key, child in value.items():
                paths(child, f'{pointer}/{segment(key)}')
        elif isinstance(value, (tuple, list, set, frozenset)):
            for index, child in enumerate(value):
                paths(child, f'{pointer}/{index}')

    paths(TypeAdapter(AnimationData).dump_python(document.catalog, warnings='error'), '/catalog')
    for section, registrations in (('assets/resources', document.assets.resources),
                                   ('ui_resources', document.ui_resources)):
        for identity, image in registrations.items():
            add(Path('game/assets') / image.path, f'/{section}/{segment(identity)}/path')
    for identity, bank in document.environment.banks.items():
        pointer = f'/environment/banks/{segment(identity)}'
        for field, path in (('path', bank.path), ('frame_path', bank.frame_path),
                            ('leaf_path', bank.leaf_path),
                            ('actor_depth/path', bank.actor_depth.path if bank.actor_depth else None)):
            if path is not None:
                add(Path('game/assets') / path, f'{pointer}/{field}')
        for field, poses in (('frames_by_pose', bank.frames_by_pose),
                              ('depth_frames_by_pose', bank.depth_frames_by_pose)):
            for pose, frames in poses.items():
                for index, region in enumerate(frames):
                    add(Path('game/assets') / region.path, f'{pointer}/{field}/{segment(pose)}/{index}/path')
        for pose, region in bank.frame_regions_by_pose.items():
            add(Path('game/assets') / region.path, f'{pointer}/frame_regions_by_pose/{segment(pose)}/path')
    for identity, prop in document.environment.props.items():
        for field, poses in (('selection_masks_by_pose', prop.selection_masks_by_pose),
                              ('aperture_masks_by_pose', prop.aperture_masks_by_pose)):
            for pose, region in poses.items():
                add(Path('game/assets') / region.path, f'/environment/props/{segment(identity)}/{field}/{segment(pose)}/path')

    data = document.catalog
    for identity, storage in data.projectile_storage.items():
        asset = data.projectile_assets[identity]
        declared_phases = {'cast': asset.phases.cast, 'travel': asset.phases.travel, 'impact': asset.phases.impact}
        for phase_name, phase in storage.phases.items():
            pointer = f'/catalog/projectile_storage/{segment(identity)}/phases/{phase_name}'
            declaration = declared_phases[phase_name]
            if declaration is None:
                raise ValueError(f'{pointer}: storage has no declared phase')
            if phase.surfaceFrames is not None:
                packet = phase.surfaceFrames
                components = packet.componentsByFacing
                directions = components.keys() if components is not None else asset.rowOrder
                for direction in directions:
                    sources = ([(part.pattern, part.archive, f'{pointer}/surfaceFrames/componentsByFacing/{direction}/{index}')
                                for index, part in enumerate(components[direction])]
                               if components is not None else [(packet.pattern, packet.archive, f'{pointer}/surfaceFrames')])
                    for pattern, archive, source_pointer in sources:
                        if archive is not None:
                            add(data.media_root / archive.file, f'{source_pointer}/archive/file')
                        else:
                            assert pattern is not None
                            for frame in packet.frameIndices:
                                add(data.media_root / pattern.format(direction=direction, frame=frame),
                                    f'{source_pointer}/pattern')
                continue
            for layer_index, layer in enumerate(phase.layers):
                layer_pointer = f'{pointer}/layers/{layer_index}'
                if layer.pattern is not None:
                    for direction in asset.rowOrder:
                        for frame in range(declaration.frames):
                            add(data.media_root / layer.pattern.format(direction=direction, frame=frame),
                                f'{layer_pointer}/pattern')
                if layer.pages is not None:
                    for direction, pages in layer.pages.items():
                        for index, page in enumerate(pages):
                            add(data.media_root / page.file, f'{layer_pointer}/pages/{direction}/{index}/file')
                banks = ([(f'{layer_pointer}/partsByFacing/{direction}', frames)
                          for direction, frames in layer.partsByFacing.items()] if layer.partsByFacing is not None
                         else [(f'{layer_pointer}/parts', layer.parts)] if layer.parts is not None else [])
                for bank_pointer, frames in banks:
                    for frame, parts in enumerate(frames):
                        for index, part in enumerate(parts):
                            part_pointer = f'{bank_pointer}/{frame}/{index}'
                            add(data.media_root / part.file, f'{part_pointer}/file')
                            if part.footpoint is not None:
                                add(data.media_root / part.footpoint.file, f'{part_pointer}/footpoint/file')
                            if part.geometryFile is not None:
                                add(data.media_root / part.geometryFile, f'{part_pointer}/geometryFile')
                            if part.ownership is not None:
                                add(data.media_root / part.ownership.file, f'{part_pointer}/ownership/file')
                            for mask, file in part.colorMasks.items():
                                add(data.media_root / file, f'{part_pointer}/colorMasks/{segment(mask)}')
    return {path: tuple(sorted(pointers)) for path, pointers in sorted(dependencies.items())}

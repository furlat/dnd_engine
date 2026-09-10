"""Read locally imported authoring data without an exporter or renderer runtime."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import struct
from types import MappingProxyType
from typing import Literal, Mapping
from uuid import UUID

from pydantic import Field, JsonValue, TypeAdapter

from dnd.blocks.appearance import AppearanceConfig
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.equipment_types import BodyPart, VisualLoadoutSlot, WeaponSet, WeaponSlot
from dnd.core.item_types import EquippedVisualPolicy, ItemPresentationState
from dnd.items.authored_variant_inventory import AUTHORED_ITEM_VARIANT_CATEGORIES
from game.animation_types import (
    AnimationData, AttackRecipe, AuthoredProjectileAsset, AuthoredRecord, BodyClip, BodyRig, BoltStyle, DamageContext, DartStyle,
    DeathContext, EquipmentTransitionContext, FloatingFeedbackStyle, FrozenMap, Identifier, MovementReactionContext, RigLayer, RigTables,
    StudioDraftFile, StudioSpellDraft, VoluntaryMovementContext,
)
from game.condition_types import load_condition_recipes


DATA_ROOT = Path(__file__).resolve().parent / "data" / "neuroclient"


_VISUAL_SLOT_BY_ENGINE_SLOT = {
    WeaponSlot.MELEE_MAIN.value: VisualLoadoutSlot.WEAPON_MELEE_MAIN,
    WeaponSlot.MELEE_OFF.value: VisualLoadoutSlot.WEAPON_MELEE_OFF,
    WeaponSlot.RANGED_MAIN.value: VisualLoadoutSlot.WEAPON_RANGED_MAIN,
    WeaponSlot.RANGED_OFF.value: VisualLoadoutSlot.WEAPON_RANGED_OFF,
    BodyPart.HEAD.value: VisualLoadoutSlot.HELMET,
    BodyPart.BODY.value: VisualLoadoutSlot.BODY_ARMOR,
    BodyPart.HANDS.value: VisualLoadoutSlot.GAUNTLETS,
    BodyPart.FEET.value: VisualLoadoutSlot.BOOTS,
}
_WEAPON_SET_BY_SLOT = {
    WeaponSlot.MELEE_MAIN.value: WeaponSet.MELEE,
    WeaponSlot.MELEE_OFF.value: WeaponSet.MELEE,
    WeaponSlot.RANGED_MAIN.value: WeaponSet.RANGED,
    WeaponSlot.RANGED_OFF.value: WeaponSet.RANGED,
}
_ITEM_VISUAL_CATEGORIES_BY_NAME = {
    category.base_category: category for category in AUTHORED_ITEM_VARIANT_CATEGORIES
}


def resolve_actor_layers(
    data: AnimationData,
    appearance: AppearanceConfig,
    items: tuple[ItemPresentationState, ...],
    equipment: tuple[tuple[str, UUID], ...],
    active_weapon_set: WeaponSet,
    *,
    rig_id: str,
) -> tuple[RigLayer, ...]:
    """Bind retained identity/loadout facts to existing authored rig layers.

    Equipment slots are the engine values retained by EntityCreatedEvent.
    Media availability remains the preloader's responsibility. Fixed rigs use
    their single-category slots; their baked gear is independent of equipment.
    """
    rig = data.rigs[rig_id]
    if rig_id != data.root_rig:
        if any(len(rig.slot_categories[slot]) != 1 for slot in rig.slot_order):
            raise ValueError(f"fixed actor rig requires one category per slot: {rig_id}")
        return tuple(
            RigLayer(slot, rig.slot_categories[slot][0], alpha=0.5 if slot == "shadow" else 1)
            for slot in rig.slot_order
        )

    if appearance.presentation_kind != "layered":
        raise ValueError("root rig requires a layered actor appearance")
    layers = {
        "shadow": RigLayer("shadow", "Shadow", alpha=0.5),
        "body": RigLayer("body", appearance.body_category, appearance.skin_tint),
    }
    if appearance.head_category is not None:
        layers["head"] = RigLayer("head", appearance.head_category, appearance.hair_tint)
    if appearance.has_beard:
        layers["beard"] = RigLayer("beard", "Head2", appearance.beard_tint)
    items_by_uuid = {item.item_uuid: item for item in items}
    for slot, item_uuid in equipment:
        if slot not in _VISUAL_SLOT_BY_ENGINE_SLOT:
            continue  # Non-rendered body slots, as in NeuroClient's equipment adapter.
        if slot in _WEAPON_SET_BY_SLOT and _WEAPON_SET_BY_SLOT[slot] != active_weapon_set:
            continue
        item = items_by_uuid[item_uuid]
        if item.equipped_visual_policy is EquippedVisualPolicy.HIDDEN:
            continue
        root = _ITEM_VISUAL_CATEGORIES_BY_NAME.get(item.visual_item_name)
        if root is None:
            raise ValueError(f"missing authored item visual: {item.visual_item_name}")
        visual_slot = _VISUAL_SLOT_BY_ENGINE_SLOT[slot]
        matches = tuple(
            category for category in AUTHORED_ITEM_VARIANT_CATEGORIES
            if any(binding.factory_identity == root.mechanical_factory_identity
                   and binding.equipment_slot is visual_slot
                   for binding in category.factory_presentation_bindings)
        )
        if len(matches) != 1:
            raise ValueError(f"missing unique authored equipment binding: {item.visual_item_name}/{slot}")
        category = matches[0]
        authored = category.base_presentation.equipment_layers
        if item.visual_variant_id is not None:
            variants = tuple(row for row in category.variants
                             if row.visual_variant_id == item.visual_variant_id)
            if len(variants) != 1:
                raise ValueError(f"missing authored item variant: {item.visual_item_name}/{item.visual_variant_id}/{slot}")
            authored = variants[0].equipment_layers
        for layer in authored:
            layers[layer.render_layer.value] = RigLayer(
                layer.render_layer.value, layer.sprite_key, layer.tint_rgb,
            )
    return tuple(layers[slot] for slot in rig.slot_order if slot in layers)


class _Bindings(AuthoredRecord):
    spells: FrozenMap[ContentRef]
    root_rig: Identifier
    resources: FrozenMap[str]


class _ResourceBindings(AuthoredRecord):
    resources: FrozenMap[str]


class _ContextFile(AuthoredRecord):
    schema_: Literal["neuroclient.actionContextPresentationRecipes"] = Field(alias="schema")
    version: Literal[17]
    contexts: dict[str, JsonValue]


class _ActionFile(AuthoredRecord):
    schema_: Literal["neuroclient.contentActionPresentationRecipes"] = Field(alias="schema")
    version: Literal[13]
    recipes: tuple[dict[str, JsonValue], ...]


class _RigBinding(AuthoredRecord):
    rig_id: Identifier
    creature_content_refs: tuple[Identifier, ...] = ()
    rig: BodyRig
    resources: FrozenMap[str]
    # Source archive information is provenance, never a runtime dependency.
    provenance: dict[str, JsonValue]


def _unique_json_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8")
        json.loads(source, object_pairs_hook=_unique_json_object)
        return source
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read animation data {path}: {exc}") from exc


def _object(value: JsonValue, name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"animation context {name} must be an object")
    return value


def _local_resources(bindings: Mapping[str, str], data_root: Path,
                     asset_family: str = "neuroclient") -> dict[str, Path]:
    # Imported paths are repository-relative. An exported tree is relocatable as
    # a whole: <root>/game/data/neuroclient and <root>/game/assets/neuroclient.
    game_root = data_root.parent.parent
    repository_root = game_root.parent
    asset_root = (game_root / "assets" / asset_family).resolve()
    resources: dict[str, Path] = {}
    for url, relative in bindings.items():
        original = PurePosixPath(url)
        if not url.startswith("/") or ".." in original.parts or "\\" in url:
            raise ValueError(f"invalid original animation resource URL {url!r}")
        authored_path = PurePosixPath(relative)
        if authored_path.is_absolute() or ".." in authored_path.parts or "\\" in relative:
            raise ValueError(f"invalid local animation resource path {relative!r}")
        path = (repository_root / relative).resolve()
        if not path.is_relative_to(asset_root):
            raise ValueError(f"animation resource escapes local asset directory: {relative!r}")
        if not path.is_file():
            raise ValueError(f"missing local animation resource {url}: {path}")
        resources[url] = path
    return resources


def _root_body_rig(rig: RigTables, resources: Mapping[str, Path]) -> BodyRig:
    clips: dict[str, dict[str, str]] = {}
    for url in resources:
        parts = PurePosixPath(url).parts
        if len(parts) == 4 and parts[1] == "spritesheets" and parts[3].endswith(".png"):
            clips.setdefault(parts[3][:-4], {})[parts[2]] = url
    return BodyRig(
        cell_width=rig.CELL_W, cell_height=rig.CELL_H,
        origin_y_from_ground=rig.RIG_ORIGIN_Y_FROM_GROUND,
        facing_rows=rig.FACING_ROW, slot_order=rig.SLOT_RENDER_ORDER,
        slot_categories=rig.SLOT_CATEGORIES,
        clips={name: BodyClip(source_clip=name, frames=rig.SHEET_COLS, fps=rig.ANIM_FPS, sheets=sheets)
               for name, sheets in clips.items()},
    )


def _additional_rigs(paths: tuple[Path, ...], data_root: Path,
                     rigs: dict[str, BodyRig], resources: dict[str, Path], creature_rigs: dict[str, str]) -> None:
    for binding_path in paths:
        binding = _RigBinding.model_validate_json(_read(binding_path))
        if binding.rig_id in rigs:
            raise ValueError(f"duplicate body rig identity: {binding.rig_id}")
        local = _local_resources(binding.resources, data_root, "rigs")
        if set(local) & set(resources):
            raise ValueError("body rig resource identity already bound")
        referenced = {url for clip in binding.rig.clips.values() for url in clip.sheets.values()}
        if referenced != set(local):
            raise ValueError("body rig clip resources and local bindings differ")
        for clip in binding.rig.clips.values():
            expected = binding.rig.cell_width * clip.frames, binding.rig.cell_height * 8
            for url in clip.sheets.values():
                with local[url].open("rb") as source:
                    header = source.read(24)
                if (len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n"
                        or header[12:16] != b"IHDR" or struct.unpack(">II", header[16:24]) != expected):
                    raise ValueError(f"body rig sheet dimensions differ from metadata: {url}")
        rigs[binding.rig_id] = binding.rig
        for identity in binding.creature_content_refs:
            if identity in creature_rigs:
                raise ValueError(f"duplicate creature rig binding: {identity}")
            creature_rigs[identity] = binding.rig_id
        resources.update(local)


def load_animation_data(data_root: Path = DATA_ROOT, *,
                        rig_files: tuple[Path, ...] = (),
                        authored_bundles: tuple[Path, ...] | None = None) -> AnimationData:
    """Validate source records and finite bindings; execution support is separate.

    Unselected media may have metadata without copied sprites. Only explicit
    local resource bindings require a file here; archive provenance URLs and
    paths are never fetched or treated as runtime dependencies. By default the
    explicit sibling CodexFX bundle is selected when present; () retains the
    original NeuroClient baseline for source comparisons.
    """
    data_root = data_root.resolve()
    drafts_file = StudioDraftFile.model_validate_json(
        _read(data_root / "spell-studio-drafts.materialized.json")
    )
    bindings = _Bindings.model_validate_json(_read(data_root / "bindings.json"))
    rig = RigTables.model_validate_json(_read(data_root / "rig-tables.json"))
    source_root = data_root / "source"
    assets = TypeAdapter(tuple[AuthoredProjectileAsset, ...]).validate_json(
        _read(source_root / "public/studio/spell-projectile-assets.json")
    )
    context_source = _read(source_root / "src/render/data/animation/actionContextPresentation.json")
    contexts = _ContextFile.model_validate_json(context_source).contexts
    action_file = _ActionFile.model_validate_json(_read(
        source_root / "src/render/data/animation/contentActionPresentationRecipes.json"
    ))
    attack_recipes: dict[str, AttackRecipe] = {}
    for row in action_file.recipes:
        kinds = row["compatibleCueKinds"]
        if isinstance(kinds, list) and "attack" in kinds:
            recipe = AttackRecipe.model_validate_json(json.dumps(row))
            identity = recipe.definitionRef.content_id
            if identity in attack_recipes:
                raise ValueError(f"ambiguous authored attack identity: {identity}")
            attack_recipes[identity] = recipe
    generated = _object(json.loads(_read(source_root / "src/render/data/animation/generatedSpellPresentationProfile.json")), "generated profile")
    projectile_profile = _object(generated["projectile"], "generated projectile")
    geometry_styles = _object(projectile_profile["geometryStyles"], "geometry styles")
    dart_style = DartStyle.model_validate_json(json.dumps(geometry_styles["dart"]))
    bolt_style = BoltStyle.model_validate_json(json.dumps(geometry_styles["bolt"]))

    drafts_by_ref: dict[ContentRef, StudioSpellDraft] = {}
    identities: set[str] = set()
    for draft in drafts_file.spells:
        ref = draft.definitionRef
        if ref.definition_kind != ContentDefinitionKind.SPELL:
            raise ValueError(f"spell draft has non-spell definitionRef: {ref.identity_key}")
        if ref in drafts_by_ref or ref.identity_key in identities:
            raise ValueError(f"duplicate spell draft definitionRef: {ref.identity_key}")
        drafts_by_ref[ref] = draft
        identities.add(ref.identity_key)
    if authored_bundles is None:
        local_bundle = data_root.parent / "codexfx"
        authored_bundles = (local_bundle,) if local_bundle.is_dir() else ()
    bundle_resources: dict[str, Path] = {}
    overridden: set[ContentRef] = set()
    for bundle in authored_bundles:
        overrides = StudioDraftFile.model_validate_json(_read(bundle / "spell-studio-drafts.json"))
        for draft in overrides.spells:
            if draft.definitionRef not in drafts_by_ref:
                raise ValueError(f"authored bundle has no exact existing spell definitionRef: {draft.definitionRef.identity_key}")
            if draft.definitionRef in overridden:
                raise ValueError(f"duplicate authored spell override: {draft.definitionRef.identity_key}")
            overridden.add(draft.definitionRef)
            drafts_by_ref[draft.definitionRef] = draft
        assets += TypeAdapter(tuple[AuthoredProjectileAsset, ...]).validate_json(
            _read(bundle / "projectile-assets.json")
        )
        resource_bindings = _ResourceBindings.model_validate_json(_read(bundle / "bindings.json"))
        local_resources = _local_resources(resource_bindings.resources, data_root, "codexfx")
        if set(local_resources) & set(bundle_resources):
            raise ValueError("authored bundle resource identity already bound")
        bundle_resources.update(local_resources)
    drafts: dict[str, StudioSpellDraft] = {}
    for semantic_id, ref in bindings.spells.items():
        if semantic_id != ref.content_id or not semantic_id.startswith("spell."):
            raise ValueError(f"spell binding identity mismatch: {semantic_id}")
        if ref not in drafts_by_ref:
            raise ValueError(f"spell binding has no exact authored definitionRef: {semantic_id}")
        drafts[semantic_id] = drafts_by_ref[ref]
    if set(bindings.spells.values()) != set(drafts_by_ref):
        raise ValueError("materialized spell drafts and local bindings differ")

    projectile_assets: dict[str, AuthoredProjectileAsset] = {}
    facing_order = rig.AUTHORED_PROJECTILE_ROW_ORDER
    if len(facing_order) != 8 or len(set(facing_order)) != 8:
        raise ValueError("root rig must identify eight unique projectile directions")
    if set(rig.FACING_ROW) != set(facing_order) or set(rig.FACING_ROW.values()) != set(range(8)):
        raise ValueError("root rig FACING_ROW must map each direction to a unique sheet row")
    for asset in assets:
        if asset.assetId in projectile_assets:
            raise ValueError(f"duplicate projectile assetId: {asset.assetId}")
        if len(asset.rowOrder) != 8 or set(asset.rowOrder) != set(facing_order):
            raise ValueError(f"projectile rowOrder must identify eight unique directions: {asset.assetId}")
        for phase in (asset.phases.cast, asset.phases.travel, asset.phases.impact):
            if phase is not None and phase.start + phase.frames > asset.frame.cols:
                raise ValueError(f"projectile phase exceeds sheet columns: {asset.assetId}")
        projectile_assets[asset.assetId] = asset

    try:
        vital = _object(contexts["vital_effect"], "vital_effect")
        feedback = _object(contexts["floating_feedback"], "floating_feedback")
        damage_context = DamageContext.model_validate_json(json.dumps(vital["damage"]))
        death_context = DeathContext.model_validate_json(json.dumps(vital["death"]))
        equipment_context = EquipmentTransitionContext.model_validate_json(json.dumps(contexts["equipment_transition"]))
        movement_context = VoluntaryMovementContext.model_validate_json(json.dumps(contexts["voluntary_movement"]))
        movement_reaction_context = MovementReactionContext.model_validate_json(json.dumps(contexts["pre_motion_reaction"]))
        number_style = FloatingFeedbackStyle.model_validate_json(json.dumps(feedback["number"]))
        badge_style = FloatingFeedbackStyle.model_validate_json(json.dumps(feedback["badge"]))
    except KeyError as exc:
        raise ValueError(f"missing animation context field {exc.args[0]!r}") from exc
    resources = _local_resources(bindings.resources, data_root)
    if set(resources) & set(bundle_resources):
        raise ValueError("authored bundle resource identity already bound")
    resources.update(bundle_resources)
    rigs = {bindings.root_rig: _root_body_rig(rig, resources)}
    creature_rigs: dict[str, str] = {}
    _additional_rigs(rig_files, data_root, rigs, resources, creature_rigs)
    return AnimationData(
        drafts=MappingProxyType(drafts),
        attack_recipes=MappingProxyType(attack_recipes),
        condition_recipes=load_condition_recipes(source_root / "src/render/data/animation/conditionPresentation.json"),
        projectile_assets=MappingProxyType(projectile_assets),
        rig=rig,
        resources=MappingProxyType(resources),
        root_rig=bindings.root_rig,
        rigs=MappingProxyType(rigs),
        creature_rigs=MappingProxyType(creature_rigs),
        damage_context=damage_context,
        death_context=death_context,
        equipment_context=equipment_context,
        movement_context=movement_context,
        movement_reaction_context=movement_reaction_context,
        number_style=number_style,
        badge_style=badge_style,
        dart_style=dart_style,
        bolt_style=bolt_style,
        vfx_source_hues=MappingProxyType(TypeAdapter(dict[str, float]).validate_json(
            _read(source_root / "src/render/data/animation/vfxSourceHues.json")
        )),
        context_source_json=context_source,
    )

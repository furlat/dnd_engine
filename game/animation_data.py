"""Read locally imported authoring data without an exporter or renderer runtime."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Literal, Mapping, Sequence
from uuid import UUID
from game.device_art import load_device_art, load_device_wrecks

from pydantic import Field, JsonValue, TypeAdapter

from dnd.types.appearance import AppearanceConfig
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.types.summoning import SummonManifestation
from dnd.core.equipment_types import BodyPart, VisualLoadoutSlot, WeaponSet, WeaponSlot
from dnd.core.item_types import EquippedVisualPolicy, ItemPresentationState
from dnd.items.authored_variant_inventory import AUTHORED_ITEM_VARIANT_CATEGORIES
from game.residue_media import region_media_assets
from game.animation_types import (
    ActionMediaAssetFile, ParticleMediaAssetFile, AnimationData, AttackProfileFile, AttackRecipe, AuthoredProjectileAsset, AuthoredRecord, BodyActionBinding, BodyActionRecipe, BloodResponse,
    BodyClip, BodyRig, BodyMaterial, BoltStyle, DamageContext, DartStyle,
    DeathContext, DeathSaveContext, EquipmentTransitionContext, FloatingFeedbackStyle, ForcedMovementContext,
    ForcedMovementProfile, FrozenMap, HealingContext, Identifier, LifecycleFeedback, LifeStateContext,
    MovementMediaTrack, MovementReactionContext, ProjectileStorage, RigLayer, RigTables, ShoveRecipe, StudioDraftFile, StudioSpellDraft,
    VoluntaryMovementContext, MovementPresentation, EntityLifecyclePhase, Point, PoseSockets, FacingMap,
    InterruptionPresentation, SpatialMediaBinding, StudioBodyMaterialTrack, ObjectIntake,
    ContentBodyQualifier, WeaponTrailBinding,
)
from game.condition_types import load_condition_recipes
from game.condition_media import load_condition_media
from game.authoring_conversion import explicit_attachments, explicit_composition, explicit_spatial_composition, validate_composition, validate_wall_modules, validate_contact_sweeps, validate_cell_modules
from game.player_facts import PlayerActor, VisualItem
from game.item_appearance import hand_appearance
from game.world_animation import prop_animation
from game.world_binding_types import WorldBindingsSource
from game.portal_art import load_portal_art


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
    BodyPart.CLOAK.value: VisualLoadoutSlot.CLOAK,
    BodyPart.BACKPACK.value: VisualLoadoutSlot.BACKPACK,
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
_EQUIPMENT_CATEGORIES = {
    (binding.factory_identity, binding.equipment_slot): category
    for category in AUTHORED_ITEM_VARIANT_CATEGORIES
    for binding in category.factory_presentation_bindings
}
_EQUIPMENT_VARIANTS = {
    (category.base_category, row.visual_variant_id): row
    for category in AUTHORED_ITEM_VARIANT_CATEGORIES for row in category.variants
}


def resolve_actor_layers(
    data: AnimationData,
    appearance: AppearanceConfig,
    items: Sequence[ItemPresentationState | VisualItem],
    equipment: tuple[tuple[str, UUID], ...],
    active_weapon_set: WeaponSet,
    *,
    rig_id: str,
) -> tuple[RigLayer, ...]:
    """Bind retained identity/loadout facts to existing authored rig layers.

    Equipment slots are the engine values retained by EntityCreatedEvent.
    Media availability remains the preloader's responsibility. Fixed rigs use
    their single-category baked slots; attack recipes select the transient slash.
    """
    rig = data.rigs[rig_id]
    if rig_id != data.root_rig:
        clip_slots = {layer.slot for clip in rig.clips.values() for layer in clip.layers}
        appearance_slots = tuple(slot for slot in rig.slot_order if slot != "slash" and slot not in clip_slots)
        if any(len(rig.slot_categories[slot]) != 1 for slot in appearance_slots):
            raise ValueError(f"fixed actor rig requires one category per slot: {rig_id}")
        return tuple(
            RigLayer(slot, rig.slot_categories[slot][0], alpha=rig.shadow_alpha if slot == "shadow" else 1)
            for slot in appearance_slots
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
        if root is None or root.mechanical_factory_identity is None:
            raise ValueError(f"missing authored item visual: {item.visual_item_name}")
        visual_slot = _VISUAL_SLOT_BY_ENGINE_SLOT[slot]
        explicit = hand_appearance(item.visual_item_name, item.visual_variant_id, visual_slot)
        if explicit is not None:
            for layer in explicit.layers:
                layers[layer.render_layer.value] = RigLayer(
                    layer.render_layer.value, layer.sprite_key, layer.tint_rgb,
                    item_effects=item.item_effects, item_uuid=item.item_uuid,
                    suppression_provider_uuids=item.suppression_provider_uuids)
            continue
        category = _EQUIPMENT_CATEGORIES.get((root.mechanical_factory_identity, visual_slot))
        if category is None:
            raise ValueError(f"missing unique authored equipment binding: {item.visual_item_name}/{slot}")
        authored = category.base_presentation.equipment_layers
        if item.visual_variant_id is not None:
            variant = _EQUIPMENT_VARIANTS.get((category.base_category, item.visual_variant_id))
            if variant is None:
                raise ValueError(f"missing authored item variant: {item.visual_item_name}/{item.visual_variant_id}/{slot}")
            authored = variant.equipment_layers
        for layer in authored:
            layers[layer.render_layer.value] = RigLayer(
                layer.render_layer.value, layer.sprite_key, layer.tint_rgb,
                item_effects=item.item_effects,
                item_uuid=item.item_uuid,
                suppression_provider_uuids=item.suppression_provider_uuids,
            )
    return tuple(layers[slot] for slot in rig.slot_order if slot in layers)


def resolve_player_layers(
    data: AnimationData, actor: PlayerActor, *, rig_id: str,
    active_weapon_set: WeaponSet | None = None,
) -> tuple[RigLayer, ...]:
    """Resolve disclosed equipment through the same authored layer mapping."""
    loadout = actor.visual_loadout
    return resolve_actor_layers(
        data, actor.appearance, loadout.layers,
        tuple((row.slot, row.item_uuid) for row in loadout.layers),
        loadout.active_weapon_set if active_weapon_set is None else active_weapon_set,
        rig_id=rig_id,
    )


class _Bindings(AuthoredRecord):
    spells: FrozenMap[ContentRef]
    root_rig: Identifier
    root_body_anchor: Point | None = None
    root_rest_pose_anchors: FrozenMap[FacingMap[Point]] = Field(default_factory=dict)
    root_pose_sockets_file: str | None = None
    root_creature_content_refs: tuple[Identifier, ...] = ()
    resources: FrozenMap[str]
    relocations: tuple[Identifier, ...] = ()


class _ResourceBindings(AuthoredRecord):
    resources: FrozenMap[str]
    spells: FrozenMap[ContentRef] = Field(default_factory=dict)
    projectileStorage: FrozenMap[ProjectileStorage] = Field(default_factory=dict)
    actionDeliveries: FrozenMap[str] = Field(default_factory=dict)


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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _object(value: JsonValue, name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"animation context {name} must be an object")
    return value


def _local_resources(bindings: Mapping[str, str], data_root: Path) -> dict[str, Path]:
    # Importers own source conversion. The shipped tree moves as one unit;
    # loading does not resolve/stat every known sprite.
    repository_root = data_root.parent.parent.parent
    return {url: repository_root / relative for url, relative in bindings.items()}


def _root_body_rig(rig: RigTables, resources: Mapping[str, Path], body_anchor: Point | None,
                   rest_pose_anchors: Mapping[str, FacingMap[Point]],
                   pose_sockets: PoseSockets) -> BodyRig:
    clips: dict[str, dict[str, str]] = {}
    categories = {category for values in rig.SLOT_CATEGORIES.values() for category in values}
    for url in resources:
        parts = PurePosixPath(url).parts
        if (len(parts) == 4 and parts[1] == "spritesheets"
                and parts[2] in categories and parts[3].endswith(".png")):
            clips.setdefault(parts[3][:-4], {})[parts[2]] = url
    return BodyRig(
        cell_width=rig.CELL_W, cell_height=rig.CELL_H,
        origin_y_from_ground=rig.RIG_ORIGIN_Y_FROM_GROUND,
        body_anchor=body_anchor,
        rest_pose_anchors=rest_pose_anchors,
        pose_sockets=pose_sockets,
        facing_rows=rig.FACING_ROW, slot_order=rig.SLOT_RENDER_ORDER,
        slot_categories=rig.SLOT_CATEGORIES,
        clips={name: BodyClip(source_clip=name, frames=rig.SHEET_COLS, fps=rig.ANIM_FPS,
                             sheets=sheets, anchors=rig.CLIP_ANCHORS.get(name, ()),
                             description=rig.CLIP_DESCRIPTIONS.get(name))
               for name, sheets in clips.items()},
    )


def _additional_rigs(paths: tuple[Path, ...], data_root: Path,
                     rigs: dict[str, BodyRig], resources: dict[str, Path], creature_rigs: dict[str, str]) -> None:
    for binding_path in paths:
        binding = _RigBinding.model_validate_json(_read(binding_path))
        if binding.rig_id in rigs:
            raise ValueError(f"duplicate body rig identity: {binding.rig_id}")
        local = _local_resources(binding.resources, data_root)
        if set(local) & set(resources):
            raise ValueError("body rig resource identity already bound")
        referenced = {url for clip in binding.rig.clips.values() for url in clip.sheets.values()}
        if referenced - set(resources) != set(local):
            raise ValueError("body rig clip resources and local bindings differ")
        rigs[binding.rig_id] = binding.rig
        for identity in binding.creature_content_refs:
            if identity in creature_rigs:
                raise ValueError(f"duplicate creature rig binding: {identity}")
            creature_rigs[identity] = binding.rig_id
        resources.update(local)


def load_animation_data(data_root: Path = DATA_ROOT, *,
                        rig_files: tuple[Path, ...] = (),
                        authored_bundles: tuple[Path, ...] | None = None,
                        world_source: WorldBindingsSource | None = None) -> AnimationData:
    """Decode shipped typed records; importers own authored source conversion.

    Unselected media may have metadata without copied sprites. Only explicit
    local resource bindings select files for the media loader. Archive provenance
    URLs and paths are never fetched or treated as runtime dependencies. By default the
    explicit sibling authored bundles are selected when present. An explicit
    bundle selection must include all media required by the supplied world;
    () excludes bundles but does not select a historical or empty world.
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
    shove_recipes: dict[str, ShoveRecipe] = {}
    body_action_recipes: dict[str, BodyActionRecipe] = {}
    for row in action_file.recipes:
        kinds = row["compatibleCueKinds"]
        if isinstance(kinds, list) and "attack" in kinds:
            recipe = AttackRecipe.model_validate_json(json.dumps(row))
            identity = recipe.definitionRef.content_id
            if identity in attack_recipes:
                raise ValueError(f"ambiguous authored attack identity: {identity}")
            attack_recipes[identity] = recipe
        if isinstance(kinds, list) and "shove" in kinds:
            shove = ShoveRecipe.model_validate_json(json.dumps(row))
            identity = shove.definitionRef.content_id
            if identity in shove_recipes:
                raise ValueError(f"ambiguous authored shove identity: {identity}")
            shove_recipes[identity] = shove
        if isinstance(kinds, list) and any(kind in kinds for kind in ("action", "item_action", "counterspell")):
            body_action = BodyActionRecipe.model_validate_json(json.dumps(row))
            identity = body_action.definitionRef.content_id
            if identity in body_action_recipes:
                raise ValueError(f"ambiguous authored body action identity: {identity}")
            body_action_recipes[identity] = body_action
    profiles = AttackProfileFile.model_validate_json(_read(data_root / "attack-profiles.json"))
    for identity in profiles.behaviors:
        attack_recipes[identity] = attack_recipes[identity].model_copy(update={"variants": profiles.variants})
    # The imported environment rows have no actor track. This
    # local authored revision uses the same Studio action schema and is shared
    # by the explicit object-action aliases below.
    for filename in ("object-interaction-recipe.json", "feast-interaction-recipe.json"):
        interaction_recipe = BodyActionRecipe.model_validate_json(_read(data_root / filename))
        body_action_recipes[interaction_recipe.definitionRef.content_id] = interaction_recipe
    body_action_bindings = TypeAdapter(FrozenMap[BodyActionBinding]).validate_json(
        _read(data_root / "action-recipe-bindings.json"))
    for binding in body_action_bindings.values():
        if binding.source_recipe not in body_action_recipes:
            raise ValueError(f"unknown source body action recipe: {binding.source_recipe}")
    generated = _object(json.loads(_read(source_root / "src/render/data/animation/generatedSpellPresentationProfile.json")), "generated profile")
    projectile_profile = _object(generated["projectile"], "generated projectile")
    geometry_styles = _object(projectile_profile["geometryStyles"], "geometry styles")
    dart_style = DartStyle.model_validate_json(json.dumps(geometry_styles["dart"]))
    bolt_style = BoltStyle.model_validate_json(json.dumps(geometry_styles["bolt"]))

    drafts_by_ref: dict[ContentRef, StudioSpellDraft] = {}
    draft_versions: dict[ContentRef, int] = {}
    identities: set[str] = set()
    for draft in drafts_file.spells:
        ref = draft.definitionRef
        if ref.definition_kind != ContentDefinitionKind.SPELL:
            raise ValueError(f"spell draft has non-spell definitionRef: {ref.identity_key}")
        if ref in drafts_by_ref or ref.identity_key in identities:
            raise ValueError(f"duplicate spell draft definitionRef: {ref.identity_key}")
        drafts_by_ref[ref] = draft
        draft_versions[ref] = drafts_file.version
        identities.add(ref.identity_key)
    if authored_bundles is None:
        authored_bundles = tuple(data_root.parent / name for name in ("codexfx", "spell_recovery", "ice_spells", "cantrips", "area_spells", "support_spells", "pending_spells", "control_spells", "liquid_media", "persistent_spells", "counterspell_media", "globe_media", "healing_spells", "support_conditions", "wall_media", "surface_contact_media", "surface_ignition_media", "curse_media", "divine_media", "control_media", "fire_media", "lightning_media", "summoning_spells", "summoning_media", "necrotic_media", "utility_media", "weather_solar_media", "holy_media", "electric_media", "transport_media", "finger_media", "class_media")
                                 if (data_root.parent / name).is_dir())
    bundle_resources: dict[str, Path] = {}
    projectile_storage: dict[str, ProjectileStorage] = {}
    spell_bindings = dict(bindings.spells)
    overridden: set[ContentRef] = set()
    effect_drafts: dict[str, StudioSpellDraft] = {}
    effect_versions: dict[str, int] = {}
    action_deliveries: dict[str, str] = {}
    entity_lifecycle_media: dict[str, EntityLifecyclePhase] = {}
    for bundle in authored_bundles:
        weapon_path=bundle / 'weapon-trails.json'
        if weapon_path.exists():
            selected=WeaponTrailBinding.model_validate_json(_read(weapon_path))
            for identity in selected.behaviors:
                attack_recipes[identity]=attack_recipes[identity].model_copy(update={'weaponTrail':selected.presentation})
        action_path = bundle / "action-recipes.json"
        if action_path.exists():
            for recipe in TypeAdapter(tuple[BodyActionRecipe, ...]).validate_json(_read(action_path)):
                prior = body_action_recipes.get(recipe.definitionRef.content_id)
                if prior is not None and prior.definitionRef != recipe.definitionRef:
                    raise ValueError("authored action definitionRef differs from its original source")
                body_action_recipes[recipe.definitionRef.content_id] = recipe
        lifecycle_path = bundle / "lifecycle.json"
        if lifecycle_path.exists():
            phases = TypeAdapter(dict[str, EntityLifecyclePhase]).validate_json(_read(lifecycle_path))
            if set(phases) - {"arrival", "departure", "bond"} or set(phases) & set(entity_lifecycle_media):
                raise ValueError("unknown or duplicate entity lifecycle phase")
            entity_lifecycle_media.update(phases)
        resource_bindings = _ResourceBindings.model_validate_json(_read(bundle / "bindings.json"))
        action_deliveries.update(resource_bindings.actionDeliveries)
        for identity, ref in resource_bindings.spells.items():
            if identity in spell_bindings and spell_bindings[identity] != ref:
                raise ValueError(f"authored spell binding disagrees with existing definitionRef: {identity}")
            spell_bindings[identity] = ref
        draft_paths = (bundle / "spell-studio-drafts.json", *sorted(bundle.glob("*-draft.json")))
        for draft_path in draft_paths:
            if not draft_path.exists():
                continue  # Media-only bundles have no spell program.
            overrides = StudioDraftFile.model_validate_json(_read(draft_path))
            if set(effect_drafts) & set(overrides.effectDrafts):
                raise ValueError("duplicate authored child-effect identity")
            effect_drafts.update(overrides.effectDrafts)
            effect_versions.update({identity: overrides.version for identity in overrides.effectDrafts})
            for draft in overrides.spells:
                if draft.definitionRef not in spell_bindings.values():
                    raise ValueError(f"authored bundle has no exact spell binding: {draft.definitionRef.identity_key}")
                if draft.definitionRef in overridden:
                    raise ValueError(f"duplicate authored spell override: {draft.definitionRef.identity_key}")
                overridden.add(draft.definitionRef)
                drafts_by_ref[draft.definitionRef] = draft
                draft_versions[draft.definitionRef] = overrides.version
        assets += TypeAdapter(tuple[AuthoredProjectileAsset, ...]).validate_json(
            _read(bundle / "projectile-assets.json")
        )
        local_resources = _local_resources(resource_bindings.resources, data_root)
        if set(local_resources) & set(bundle_resources):
            raise ValueError("authored bundle resource identity already bound")
        bundle_resources.update(local_resources)
        if set(resource_bindings.projectileStorage) & set(projectile_storage):
            raise ValueError("authored projectile storage identity already bound")
        projectile_storage.update(resource_bindings.projectileStorage)
    drafts: dict[str, StudioSpellDraft] = {}
    for semantic_id, ref in spell_bindings.items():
        if semantic_id != ref.content_id or not semantic_id.startswith("spell."):
            raise ValueError(f"spell binding identity mismatch: {semantic_id}")
        if ref not in drafts_by_ref:
            raise ValueError(f"spell binding has no exact authored definitionRef: {semantic_id}")
        drafts[semantic_id] = drafts_by_ref[ref]
    if set(spell_bindings.values()) != set(drafts_by_ref):
        raise ValueError("materialized spell drafts and local bindings differ")
    for effect_id, draft in effect_drafts.items():
        if draft.definitionRef not in drafts_by_ref or effect_id in drafts:
            raise ValueError(f"effect draft must reference its existing owning spell: {effect_id}")
        drafts[effect_id] = draft
    for action_id, spell_id in action_deliveries.items():
        drafts[action_id] = drafts[spell_id]

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

    for identity, draft in drafts.items():
        version = effect_versions.get(identity, draft_versions[draft.definitionRef])
        if version not in (2, 3):
            draft = explicit_attachments(draft, projectile_assets)
        drafts[identity] = explicit_composition(draft, projectile_storage) if version != 3 else draft
        validate_composition(drafts[identity], projectile_storage)

    try:
        vital = _object(contexts["vital_effect"], "vital_effect")
        feedback = _object(contexts["floating_feedback"], "floating_feedback")
        lifecycle = _object(contexts["lifecycle"], "lifecycle")
        damage_context = DamageContext.model_validate_json(json.dumps(vital["damage"]))
        healing_context = HealingContext.model_validate_json(json.dumps(vital["healing"]))
        death_save_context = DeathSaveContext.model_validate_json(json.dumps(lifecycle["deathSave"]))
        life_state_context = LifeStateContext.model_validate_json(json.dumps({
            **_object(lifecycle["lifeState"], "lifeState"),
            "bodyPoses": json.loads(_read(DATA_ROOT.parent / "life-state-poses.json")),
        }))
        death_context = DeathContext.model_validate_json(json.dumps({
            **_object(vital["death"], "death"),
            "silhouetteDust": json.loads(_read(DATA_ROOT.parent / "silhouette-dust.json")),
        }))
        equipment_context = EquipmentTransitionContext.model_validate_json(json.dumps(contexts["equipment_transition"]))
        movement_context = VoluntaryMovementContext.model_validate_json(json.dumps(contexts["voluntary_movement"]))
        movement_reaction_context = MovementReactionContext.model_validate_json(json.dumps(contexts["pre_motion_reaction"]))
        forced_movement_context = ForcedMovementContext.model_validate_json(json.dumps(contexts["forced_movement"]))
        outcomes = _object(contexts["outcome_feedback"], "outcome_feedback")
        shove_feedback = TypeAdapter(FrozenMap[LifecycleFeedback]).validate_json(json.dumps(outcomes["shove"]))
        number_style = FloatingFeedbackStyle.model_validate_json(json.dumps(feedback["number"]))
        badge_style = FloatingFeedbackStyle.model_validate_json(json.dumps(feedback["badge"]))
    except KeyError as exc:
        raise ValueError(f"missing animation context field {exc.args[0]!r}") from exc
    resources = _local_resources(bindings.resources, data_root)
    if set(resources) & set(bundle_resources):
        raise ValueError("authored bundle resource identity already bound")
    resources.update(bundle_resources)
    pose_sockets = (TypeAdapter(PoseSockets).validate_json(
        _read(data_root / bindings.root_pose_sockets_file))
        if bindings.root_pose_sockets_file is not None else MappingProxyType({}))
    rigs = {bindings.root_rig: _root_body_rig(rig, resources, bindings.root_body_anchor,
                                          bindings.root_rest_pose_anchors, pose_sockets)}
    creature_rigs = {identity: bindings.root_rig for identity in bindings.root_creature_content_refs}
    _additional_rigs(rig_files, data_root, rigs, resources, creature_rigs)
    world = world_source if world_source is not None else WorldBindingsSource.model_validate_json(
        _read(DATA_ROOT.parent / "world_bindings.json"))
    spatial_media = {identity: explicit_spatial_composition(
        row, projectile_storage)
        for identity, row in world.spatial_media.items()}
    for binding in spatial_media.values():
        validate_wall_modules(binding, projectile_assets, projectile_storage)
        for layer in binding.layers:
            if layer.wallAssembly is not None and layer.wallAssembly.air is not None and layer.wallAssembly.air.mesh not in resources:
                raise ValueError('Missing quiet construction air source')
        validate_cell_modules(binding, projectile_assets, projectile_storage)
        validate_contact_sweeps(binding, projectile_assets, projectile_storage)
    action_intakes = TypeAdapter(dict[str, ObjectIntake]).validate_json(
        _read(DATA_ROOT.parent / "action-intakes.json"))
    action_materials = TypeAdapter(dict[str, StudioBodyMaterialTrack]).validate_json(
        _read(DATA_ROOT.parent / "action-materials.json"))
    item_attachments = TypeAdapter(dict[str, SpatialMediaBinding]).validate_json(
        _read(DATA_ROOT.parent / "item-attachments.json"))
    for binding in item_attachments.values():
        for layer in binding.layers:
            if layer.side not in ("rear", "front") or layer.composition != "clump":
                raise ValueError("Item attachments require paired item-relative layers")
            for asset_id in (layer.assetId, layer.applicationAssetId):
                if asset_id is not None and asset_id not in projectile_assets:
                    raise ValueError(f"Missing item attachment media: {asset_id}")
    concentration_media = {identity: explicit_spatial_composition(
        row, projectile_storage)
        for identity, row in world.concentration_media.items()}
    construction_media = world.construction_media
    for binding in construction_media.values():
        if binding.surface is not None and binding.surface.motes is not None and binding.surface.motes not in resources:
            raise ValueError('Construction energy motes require a registered original resource')
        if binding.surface is not None and binding.surface.components not in resources:
            raise ValueError('Missing construction operator source')
        for direction in binding.directions:
            for variant in direction.variants:
                for phase_name, phase_identities in (('application', variant.application), ('intact', variant.intact),
                                                ('destruction', variant.destruction), ('removal', variant.removal)):
                    for identity in phase_identities or ():
                        asset = projectile_assets[identity]
                        phase = asset.phases.impact
                        storage = projectile_storage[identity].phases['impact']
                        if (phase is None or (phase.fps or asset.fps) != 32
                                or phase_name == 'intact' and (phase.frames != 1 or not phase.loop)
                                or phase_name != 'intact' and phase.loop
                                or (storage.surfaceFrames is not None and not {'E', 'S', 'W', 'N'} <= set(
                                    storage.surfaceFrames.componentsByFacing or {}))
                                or (storage.surfaceFrames is None and (not storage.layers or any(
                                    layer.partsByFacing is None or not {'E', 'S', 'W', 'N'} <= set(layer.partsByFacing)
                                    for layer in storage.layers)))):
                            raise ValueError('Construction phases require four-view finite banks and a single intact still')
                        if (phase_name == 'removal' and binding.removalDurationMs is not None
                                and phase.frames * 1000 / 32 < binding.removalDurationMs):
                            raise ValueError('Construction retirement bank ends before its source duration')
    world_animations = {identity: prop_animation(row.transition)
        for identity, row in world.props.items() if row.transition is not None}
    world_animations.update({identity: prop_animation(row)
        for identity, row in world.spatial_effects.items()})
    movement_media = MovementPresentation.model_validate_json(_read(DATA_ROOT.parent / "movement-media.json"))
    movement_context = movement_context.model_copy(update={
        "walkMedia": movement_media.walkMedia, "jumpMedia": movement_media.jumpMedia,
        "flight": movement_media.flight})
    data = AnimationData(
        interruptions=InterruptionPresentation.model_validate_json(_read(DATA_ROOT.parent / "interruptions.json")),
        devices=load_device_art(),
        device_wrecks=load_device_wrecks(),
        drafts=MappingProxyType(drafts),
        attack_recipes=MappingProxyType(attack_recipes),
        shove_recipes=MappingProxyType(shove_recipes),
        body_action_recipes=MappingProxyType(body_action_recipes),
        body_action_bindings=body_action_bindings,
        condition_recipes=load_condition_recipes(
            source_root / "src/render/data/animation/conditionPresentation.json",
            overrides=DATA_ROOT.parent / "condition-overrides.json",
            local=DATA_ROOT.parent / "condition-recipes.json",
        ),
        condition_media=load_condition_media(DATA_ROOT.parent / "condition-media.json",
            DATA_ROOT.parent / "assets.json", DATA_ROOT.parent.parent / "assets"),
        projectile_assets=MappingProxyType(projectile_assets),
        projectile_storage=MappingProxyType(projectile_storage),
        media_root=data_root.parent.parent.parent,
        rig=rig,
        resources=MappingProxyType(resources),
        root_rig=bindings.root_rig,
        rigs=MappingProxyType(rigs),
        creature_rigs=MappingProxyType(creature_rigs),
        damage_context=damage_context,
        healing_context=healing_context,
        death_save_context=death_save_context,
        life_state_context=life_state_context,
        death_context=death_context,
        equipment_context=equipment_context,
        movement_context=movement_context,
        movement_reaction_context=movement_reaction_context,
        forced_movement_context=forced_movement_context,
        forced_movement_profile=ForcedMovementProfile.model_validate_json(_read(data_root / "forced-movement-profile.json")),
        shove_feedback=shove_feedback,
        number_style=number_style,
        badge_style=badge_style,
        dart_style=dart_style,
        bolt_style=bolt_style,
        vfx_source_hues=MappingProxyType(TypeAdapter(dict[str, float]).validate_json(
            _read(source_root / "src/render/data/animation/vfxSourceHues.json")
        )),
        context_source_json=context_source,
        world_animations=MappingProxyType(world_animations),
        spatial_media=MappingProxyType(spatial_media),
        item_attachments=MappingProxyType(item_attachments),
        action_materials=MappingProxyType(action_materials),
        action_intakes=MappingProxyType(action_intakes),
        concentration_media=MappingProxyType(concentration_media),
        construction_media=MappingProxyType(construction_media),
        deposit_media=MappingProxyType(world.deposit_media),
        action_media_assets=MappingProxyType({asset.assetId: asset for asset in (
            *ActionMediaAssetFile.model_validate_json(_read(data_root / "body-release-assets.json")).assets,
            *ParticleMediaAssetFile.model_validate_json(_read(data_root / "body-release-particles.json")).assets,
            *region_media_assets().values())}),
        body_release_media=MappingProxyType(TypeAdapter(dict[str, tuple[MovementMediaTrack, ...]]).validate_json(
            _read(data_root / "body-release-bindings.json"))),
        relocation_actions=frozenset(bindings.relocations),
        portals=load_portal_art(),
        entity_lifecycle_media=MappingProxyType(entity_lifecycle_media),
        action_playback_rates=movement_media.actionPlaybackRates,
        action_deliveries=MappingProxyType(action_deliveries),
        movement_reference_speed_feet=movement_media.referenceSpeedFeet,
        body_materials=MappingProxyType(TypeAdapter(dict[SummonManifestation, BodyMaterial]).validate_json(
            _read(DATA_ROOT.parent / "body-materials.json"))),
        blood_responses=MappingProxyType(TypeAdapter(dict[str, BloodResponse | None]).validate_json(
            _read(DATA_ROOT.parent / "blood-responses.json"))),
    )
    installed_rig_ids = frozenset(TypeAdapter(Identifier).validate_python(
        json.loads(_read(path))["rig_id"]) for path in (data_root.parent / "rigs").glob("*.json"))
    for phase, recipe in data.entity_lifecycle_media.items():
        if (phase in ("arrival", "departure")) != (recipe.bodyFadeMs is not None):
            raise ValueError("arrival/departure require body markers; bond media never changes presence")
        for tracks in recipe.tracksByManifestation.values():
            for track in tracks:
                asset = data.projectile_assets.get(track.assetId)
                if asset is None or asset.phases.impact is None or track.assetPhase != "impact":
                    raise ValueError(f"lifecycle track has no registered impact phase: {track.assetId}")
    for action in data.body_action_recipes.values():
        for track in action.media:
            if track.clock != 'release' or track.attachment not in ('source_hand','source_ground'):
                raise ValueError('Body action media requires its actor release attachment')
            for identity in track.assetIdsByCamera or (track.assetId,):
                asset = data.projectile_assets.get(identity)
                storage = data.projectile_storage.get(identity)
                if asset is None or storage is None or track.assetPhase not in storage.phases:
                    raise ValueError(f'Body action media requires a registered source: {identity}')
                reference = data.projectile_assets[track.assetId]
                if (asset.frame,asset.fps,asset.phases,asset.anchor,asset.rowOrder) != (
                        reference.frame,reference.fps,reference.phases,reference.anchor,reference.rowOrder):
                    raise ValueError('Body action camera media requires identical source registration')
    for draft in data.drafts.values():
        if profile := draft.cancellationMedia:
            if profile.reactionId not in data.interruptions.reactions or profile.outcomeCode not in data.interruptions.outcomes:
                raise ValueError("Cancellation media requires registered reaction and outcome identities")
            for identity in profile.successByCamera:
                asset = data.projectile_assets.get(identity)
                if asset is None or asset.phases.impact is None or identity not in data.projectile_storage:
                    raise ValueError(f"Cancellation reaction requires registered camera media: {identity}")
        for track in (*draft.media, *(draft.cancellationMedia.media if draft.cancellationMedia is not None else ())):
            if track.assetIdsByCamera is None:
                continue
            reference = data.projectile_assets.get(track.assetId)
            if reference is None or track.assetIdsByCamera[0] != track.assetId:
                raise ValueError(f'Camera media requires its registered camera-zero default: {track.id}')
            for identity in track.assetIdsByCamera:
                asset = data.projectile_assets.get(identity)
                storage = data.projectile_storage.get(identity)
                if asset is None or storage is None or track.assetPhase not in storage.phases:
                    raise ValueError(f'Camera media requires all four registered sources: {track.id}/{identity}')
                if (asset.frame,asset.fps,asset.phases,asset.anchor,asset.anchorsByFacing,asset.rowOrder) != (
                        reference.frame,reference.fps,reference.phases,reference.anchor,reference.anchorsByFacing,reference.rowOrder):
                    raise ValueError(f'Camera media requires identical clock, canvas and pivot: {track.id}/{identity}')
        if draft.arcs is not None:
            for resource in (draft.arcs.texture, draft.arcs.glow, draft.arcs.star,
                             draft.arcs.streak, draft.arcs.spark):
                if resource not in data.resources:
                    raise ValueError(f"Directed arc requires registered material: {resource}")
        for layer in draft.displacementLayers:
            media = data.condition_media.get(layer.assetId)
            if (media is None or media.asset_id is None or media.application_asset_id is None
                    or media.removal_asset_id is None or media.application_mode != "sequence"):
                raise ValueError(f"Displacement attachment requires registered approach/hold/release: {layer.assetId}")
        for track in draft.bodyMaterials:
            if track.material.texture is not None and track.material.texture not in data.resources:
                raise ValueError(f"Body material requires registered texture: {track.material.texture}")
            if track.material.normalTexture is not None and track.material.normalTexture not in data.resources:
                raise ValueError(f"Body material requires registered normal texture: {track.material.normalTexture}")
    for recipe in data.condition_recipes.values():
        ramp = recipe.persistent.bodyRamp
        if ramp is not None and ramp.texture is not None and ramp.texture not in data.resources:
            raise ValueError(f"Condition material requires registered texture: {ramp.texture}")
        if ramp is not None and ramp.normalTexture is not None and ramp.normalTexture not in data.resources:
            raise ValueError(f"Condition material requires registered normal texture: {ramp.normalTexture}")
    validate_rig_body_contexts(data, installed_rig_ids=installed_rig_ids)
    return data


def validate_rig_body_contexts(data: AnimationData, *, installed_rig_ids: frozenset[str] = frozenset()) -> None:
    """Admit portable overrides against this installed authored vocabulary."""
    action_refs = tuple(recipe.definitionRef for recipe in (*data.drafts.values(), *data.body_action_recipes.values()))
    condition_refs = tuple(recipe.definitionRef for recipe in data.condition_recipes.values())
    references = {"body_action": action_refs, "body_action_recovery": action_refs, "cast": action_refs,
        "condition_entry": condition_refs, "condition_hold": condition_refs, "condition_exit": condition_refs,
        "shove": tuple(recipe.definitionRef for recipe in data.shove_recipes.values()),
        "save_avoidance": tuple(recipe.definitionRef for recipe in data.drafts.values())}
    for identity, rig in data.rigs.items():
        for binding in rig.body_contexts:
            if (isinstance(binding.qualifier, ContentBodyQualifier)
                    and binding.qualifier.contentRef not in references.get(binding.role, ())):
                raise ValueError(f"{identity}/{binding.role}: unknown content reference {binding.qualifier.contentRef.identity_key}")
            body = binding.body
            if body.actor.enabled and not any(rig.clips[body.actor.clip].sheets.get(category) in data.resources
                    for category in rig.slot_categories["body"]):
                raise ValueError(f"{identity}/{binding.role}: missing body resource {body.actor.clip}")
        if rig.body_contexts:
            # Alternate body selection does not erase the existing damage/life
            # owners. Their shared clips and callback frames must remain usable.
            damage, death = data.damage_context, data.death_context
            death_clip = next((binding.body.actor.clip for binding in rig.body_contexts
                               if binding.role == "death"), death.bodyClip)
            # Death samples its own Die clip. The legacy damage.deathFrame is
            # not a TakeDamage callback and must not reject shorter hit banks.
            requirements = [("Idle", 0), (damage.bodyClip, max(damage.flashFrame, damage.numberFrame,
                damage.conditionFrame)), (death_clip, death.equipmentHideFrame)]
            for pose in data.life_state_context.bodyPoses.values():
                if pose.bodyPose is not None:
                    requirements.append((pose.bodyPose, 0))
                for transition in (pose.applicationBody, pose.removalBody):
                    if transition is not None:
                        requirements.append((transition.bodyClip, 0))
            for clip_name, frame in requirements:
                clip = rig.clips.get(clip_name)
                if clip is None or frame >= clip.frames:
                    raise ValueError(f"{identity}/shared-vitals: missing {clip_name} frame {frame}")
                if not any(clip.sheets.get(category) in data.resources for category in rig.slot_categories["body"]):
                    raise ValueError(f"{identity}/shared-vitals: missing body resource {clip_name}")
    for recipe in data.attack_recipes.values():
        if recipe.weaponTrail is not None:
            trail=recipe.weaponTrail
            asset=data.projectile_assets.get(trail.impactAssetId)
            if asset is None or asset.phases.impact is None or asset.phases.impact.loop:
                raise ValueError('Weapon contact requires a registered finite impact phase')
            seen=set()
            for pose in trail.poses:
                key=(pose.rigId,pose.category,pose.clip)
                if key in seen:raise ValueError('Duplicate measured weapon pose')
                seen.add(key)
                rig=data.rigs.get(pose.rigId)
                if rig is None:continue
                clip=rig.clips.get(pose.clip)
                if clip is None or pose.category not in clip.sheets or any(
                        len(points)!=clip.frames for points in pose.pointsByFacing.values()):
                    raise ValueError(f'Invalid measured weapon pose: {key}')
        for profile in recipe.variants:
            for identity in profile.match.rigIds or ():
                if identity not in data.rigs and identity not in installed_rig_ids:
                    raise ValueError(f"unknown attack profile rig: {identity}")
                rig = data.rigs.get(identity)
                if rig is None:  # This load may intentionally select only a subset of installed rigs.
                    continue
                clip = rig.clips.get(profile.actor.clip)
                names = {"release"} if profile.projectile is not None else {"impact", "contact", "effect"}
                if (not profile.actor.enabled or profile.actor.hiddenSlots or profile.actor.media or clip is None
                        or not any(anchor.name in names for anchor in profile.anchors)
                        or len({anchor.name for anchor in profile.anchors}) != len(profile.anchors)
                        or any(anchor.name not in names | {"action_start", "prepare", "recover"}
                               or anchor.frame >= clip.frames for anchor in profile.anchors)
                        or not any(clip.sheets.get(category) in data.resources for category in rig.slot_categories["body"])):
                    raise ValueError(f"{identity}/attack/{profile.id}: incompatible body or contact markers")

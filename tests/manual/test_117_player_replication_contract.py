"""Focused checks for the canonical subjective player transport boundary."""

import hashlib
import json
from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from dnd.core.content.descriptors import (
    ContentPresentation,
    compute_safe_content_presentation_hash,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.equipment_types import WeaponSet
from dnd.core.item_types import EquippedVisualPolicy, ItemPresentationKind
from dnd.core.life_types import LifeState, LifeStateChangeReason
from server.world_contracts import (
    APIAppearance,
    APIDirectionalBlockMap,
    APIEntitySummary,
    APIEntityVisibility,
    APIEquipmentOverview,
    APIGrid,
    APITile,
    APIVisibilityResponse,
    SafeContentPresentationRef,
    StructuralEdgeAppearance,
    StructuralEdgeKind,
)
from server.player_replication_contract import (
    PLAYER_REPLICATION_CONTRACT_HASH,
    PLAYER_REPLICATION_CONTRACT_VERSION,
    ActiveWeaponSet,
    ActorVisualSlot,
    AttackDelivery,
    AttackOutcome,
    AttackPresentationCue,
    ConeAreaGeometry,
    ConditionOperation,
    ConditionPresentationCue,
    CounterspellAutomaticSuccess,
    CounterspellCheckFailure,
    CounterspellCheckSuccess,
    CounterspellPresentationCue,
    CubeAreaGeometry,
    DamagePresentationCue,
    DeathSaveOutcome,
    DoorPresentationCue,
    EffectiveLightCell,
    EncounterPresentationCue,
    EncounterTransition,
    EntityVisualLoadout,
    EquipmentPresentationCue,
    HealPresentationCue,
    ForcedMovementCause,
    ForcedMovementPresentationCue,
    FloorObjectBlockingChannel,
    FloorObjectDirection,
    FloorObjectProjectionKind,
    FloorObjectUpsertPatch,
    ItemActionKind,
    ItemActionPresentationCue,
    LifecycleCauseKind,
    LifecycleCausePresentationCue,
    LifeStatePresentationCue,
    LightPresentationCue,
    MovementKind,
    MovementPresentationCue,
    PerspectiveKind,
    PlayerReplicationProtocolIdentity,
    PlayerReplicationWatermarks,
    PresentationDamageType,
    BehaviorPresentationRole,
    PresentationProjectile,
    PresentationSpellSchool,
    PresentationWeaponSlot,
    ShoveOutcome,
    ShovePresentationCue,
    RootedBehaviorPresentationAttribution,
    SourceItemPresentationAttribution,
    SphereAreaGeometry,
    SpellApplicationOutcome,
    SpellDelivery,
    SpellPresentationCue,
    SpellTargetPresentation,
    SubjectiveCombatLogDelivery,
    SubjectiveCombatLogFrame,
    SubjectiveCombatLogFramesResponse,
    SubjectiveFrameDelivery,
    SubjectiveFramesResponse,
    SubjectiveFloorObject,
    SubjectiveGameState,
    SubjectivePerspective,
    SubjectivePresentationCue,
    SubjectiveReplicatedWorld,
    SubjectiveReplicationBootstrap,
    SubjectiveReplicationFrame,
    SubjectiveStreamDelivery,
    SubjectiveSyncDelivery,
    SubjectiveWorldPatch,
    VisualEquipmentLayer,
    VisualLoadoutSlot,
    UnrootedBehaviorPresentationAttribution,
    player_replication_contract_summary,
    player_replication_wire_schema,
)
from server.timeline_contracts import CombatLogFramesResponse, CombatLogProjection


def _safe_presentation_ref(
    presentation: ContentPresentation,
) -> SafeContentPresentationRef:
    return SafeContentPresentationRef(
        presentation_contract_hash=compute_safe_content_presentation_hash(
            presentation,
        ),
    )


def _content_ref(
    *,
    kind: ContentDefinitionKind,
    content_id: str,
    digest_char: str,
) -> ContentRef:
    return ContentRef(
        pack_id="fixture.player_replication",
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=digest_char * 64,
    )


def _blocks() -> APIDirectionalBlockMap:
    return APIDirectionalBlockMap(
        north=False,
        south=False,
        east=False,
        west=False,
    )


def _tile(x: int, y: int) -> APITile:
    return APITile(
        x=x,
        y=y,
        visual_key="floor.png",
        walkable=True,
        visible=True,
        name="Floor",
        walking_cost=1,
        is_hazardous=False,
        conditions=[],
        light_level=3,
        directional_blocks_movement=_blocks(),
        directional_blocks_vision=_blocks(),
        directional_blocks_light=_blocks(),
        directional_blocks_propagation=_blocks(),
    )


def _appearance(*, tint: int) -> APIAppearance:
    return APIAppearance(
        portrait_key=None,
        presentation_kind="layered",
        visual_scale=1.0,
        placeholder_tint=tint,
        body_category="NakedBody",
        skin_tint=tint,
        head_category="Head1",
        hair_tint=0,
        has_beard=False,
        beard_tint=0,
    )


def test_structural_edge_appearance_is_closed_and_privacy_minimal() -> None:
    """Doors require state, walls reject it, and no object identity can enter."""

    assert StructuralEdgeAppearance(
        kind=StructuralEdgeKind.DOOR,
        is_open=False,
    ).model_dump(mode="json") == {"kind": "door", "is_open": False}
    assert StructuralEdgeAppearance(
        kind=StructuralEdgeKind.WALL,
        is_open=None,
    ).model_dump(mode="json") == {"kind": "wall", "is_open": None}
    with pytest.raises(ValidationError, match="explicit open state"):
        StructuralEdgeAppearance(kind=StructuralEdgeKind.DOOR)
    with pytest.raises(ValidationError, match="cannot carry open state"):
        StructuralEdgeAppearance(kind=StructuralEdgeKind.WALL, is_open=True)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StructuralEdgeAppearance.model_validate({
            "kind": "door",
            "is_open": False,
            "uuid": "hidden-object",
        })


def _entity(uuid: str, name: str, position: tuple[int, int], tint: int) -> APIEntitySummary:
    return APIEntitySummary(
        uuid=uuid,
        name=name,
        position=position,
        hp=10,
        max_hp=10,
        ac=13,
        conditions=[],
        condition_details=[],
        life_state=LifeState.ALIVE,
        is_dead=False,
        faction=None,
        creature_type="humanoid",
        size="Medium",
        appearance=_appearance(tint=tint),
    )


def _loadout(entity_uuid: str, visual_item_name: str | None = None) -> EntityVisualLoadout:
    layers = ()
    if visual_item_name is not None:
        layers = (
            VisualEquipmentLayer(
                slot=VisualLoadoutSlot.WEAPON_MELEE_MAIN,
                item_kind=ItemPresentationKind.WEAPON,
                safe_presentation_ref=_safe_presentation_ref(
                    ContentPresentation(sprite_key=visual_item_name),
                ),
                visual_item_name=visual_item_name,
                visual_variant_id=None,
                equipped_visual_policy=EquippedVisualPolicy.VISIBLE,
            ),
        )
    return EntityVisualLoadout(
        entity_uuid=entity_uuid,
        active_weapon_set=(
            ActiveWeaponSet.MELEE if visual_item_name is not None else ActiveWeaponSet.NONE
        ),
        layers=layers,
    )


def _equipment(ac: int = 13) -> APIEquipmentOverview:
    return APIEquipmentOverview(
        slots=[],
        active_weapon_set=WeaponSet.NONE,
        ac=ac,
        inventory=[],
    )


def _perspective(
    *controlled: str,
    observers: tuple[str, ...] | None = None,
    active: str | None = None,
) -> SubjectivePerspective:
    effective_observers = observers if observers is not None else tuple(controlled)
    return SubjectivePerspective(
        perspective_epoch_id="perspective-1",
        kind=(
            PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION
            if controlled
            else PerspectiveKind.SPECTATOR_KNOWLEDGE_UNION
        ),
        controlled_entity_uuids=tuple(controlled),
        observer_entity_uuids=effective_observers,
        active_observer_uuid=active or effective_observers[0],
    )


def _world(
    *,
    controlled: tuple[str, ...] = ("hero",),
    observer_uuids: tuple[str, ...] = ("hero",),
) -> SubjectiveReplicatedWorld:
    entities = [
        _entity("hero", "Hero", (0, 0), 0xDDAA88),
        _entity("ally", "Ally", (1, 0), 0xCCAA88),
        _entity("enemy", "Visible Enemy", (2, 0), 0x55AA55),
    ]
    visibility = {
        observer_uuid: APIEntityVisibility(
            name=observer_uuid.title(),
            position=next(entity.position for entity in entities if entity.uuid == observer_uuid),
            visible_cells=[(0, 0), (1, 0), (2, 0)],
            visible_entities=[entity.uuid for entity in entities],
            visible_objects=[],
            seen_cells=[(0, 0), (1, 0), (2, 0)],
            sense_modes=[],
            effective_light_levels={"0,0": 3, "1,0": 2, "2,0": 1},
        )
        for observer_uuid in observer_uuids
    }
    return SubjectiveReplicatedWorld(
        state=SubjectiveGameState(
            grid=APIGrid(
                min_x=0,
                min_y=0,
                max_x=2,
                max_y=0,
                tiles=[_tile(0, 0), _tile(1, 0), _tile(2, 0)],
            ),
            entities=tuple(entities),
            encounter=None,
            floor_objects=(),
        ),
        visibility=APIVisibilityResponse(root=visibility),
        equipment_by_entity={entity_uuid: _equipment() for entity_uuid in controlled},
        visual_loadout_by_entity={
            "hero": _loadout("hero", "Longsword"),
            "ally": _loadout("ally", "Staff"),
            "enemy": _loadout("enemy", "RustySword"),
        },
    )


def _watermarks(
    *,
    source: int = 5,
    observation: int = 2,
    presentation: int = 1,
    combat_log: int = 0,
) -> PlayerReplicationWatermarks:
    return PlayerReplicationWatermarks(
        source_event_cursor=source,
        observation_cursor=observation,
        presentation_cursor=presentation,
        combat_log_cursor=combat_log,
    )


def _empty_logs(*, combat_log_cursor: int = 0) -> SubjectiveCombatLogFramesResponse:
    return SubjectiveCombatLogFramesResponse(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        retained_from_cursor=combat_log_cursor,
        from_cursor=combat_log_cursor,
        through_cursor=combat_log_cursor,
        frames=(),
        total=combat_log_cursor,
    )


def _bootstrap(
    *,
    perspective: SubjectivePerspective | None = None,
    world: SubjectiveReplicatedWorld | None = None,
) -> SubjectiveReplicationBootstrap:
    effective_perspective = perspective or _perspective("hero")
    effective_world = world or _world(
        controlled=effective_perspective.controlled_entity_uuids,
        observer_uuids=effective_perspective.observer_entity_uuids,
    )
    return SubjectiveReplicationBootstrap(
        protocol=PlayerReplicationProtocolIdentity(
            source_stream_id="stream-1",
            generation_id="generation-1",
        ),
        perspective=effective_perspective,
        watermarks=_watermarks(),
        world=effective_world,
        combat_log_frames=_empty_logs(),
    )


def test_bootstrap_is_renderer_complete_and_round_trips_without_objective_equipment() -> None:
    """Projected state retains render seeds while full gear stays owner-private."""
    bootstrap = _bootstrap()

    restored = SubjectiveReplicationBootstrap.model_validate_json(
        bootstrap.model_dump_json()
    )

    assert restored == bootstrap
    assert restored.perspective.projection == "subjective"
    assert restored.world.state.grid.max_x == 2
    assert restored.world.state.entities[2].appearance.body_category == "NakedBody"
    assert restored.world.state.entities[2].size == "Medium"
    assert restored.world.visibility.root["hero"].effective_light_levels["2,0"] == 1
    assert set(restored.world.equipment_by_entity) == {"hero"}
    assert set(restored.world.visual_loadout_by_entity) == {"hero", "ally", "enemy"}
    assert (
        restored.world.visual_loadout_by_entity["enemy"].layers[0].visual_item_name
        == "RustySword"
    )


def test_world_and_bootstrap_reject_equipment_visibility_and_light_leaks() -> None:
    """Full equipment, observer rows, and resolved light obey the perspective."""
    valid = _bootstrap()
    world_payload = valid.world.model_dump(mode="python")
    world_payload["equipment_by_entity"]["enemy"] = _equipment()
    leaky_world = SubjectiveReplicatedWorld.model_validate(world_payload)

    with pytest.raises(ValidationError, match="controlled entities only"):
        _bootstrap(world=leaky_world)

    missing_loadout = valid.world.model_dump(mode="python")
    missing_loadout["visual_loadout_by_entity"].pop("enemy")
    with pytest.raises(ValidationError, match="exactly cover"):
        SubjectiveReplicatedWorld.model_validate(missing_loadout)

    incomplete_light = valid.world.model_dump(mode="python")
    incomplete_light["visibility"]["hero"]["effective_light_levels"].pop("2,0")
    with pytest.raises(ValidationError, match="exactly cover visible cells"):
        SubjectiveReplicatedWorld.model_validate(incomplete_light)

    wrong_observer = valid.world.model_dump(mode="python")
    wrong_observer["visibility"]["enemy"] = wrong_observer["visibility"]["hero"]
    with pytest.raises(ValidationError, match="authorized observer union"):
        _bootstrap(world=SubjectiveReplicatedWorld.model_validate(wrong_observer))


def test_controlled_and_spectator_perspectives_are_explicit_knowledge_unions() -> None:
    """Multi-actor and zero-control views cannot silently become objective."""
    controlled_union = _perspective(
        "hero",
        "ally",
        observers=("ally", "hero"),
        active="ally",
    )
    controlled_bootstrap = _bootstrap(
        perspective=controlled_union,
        world=_world(
            controlled=("hero", "ally"),
            observer_uuids=("ally", "hero"),
        ),
    )
    assert controlled_bootstrap.perspective.kind is PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION
    assert controlled_bootstrap.perspective.active_observer_uuid == "ally"

    spectator = _perspective(observers=("hero", "ally"), active="hero")
    spectator_bootstrap = _bootstrap(
        perspective=spectator,
        world=_world(controlled=(), observer_uuids=("hero", "ally")),
    )
    assert spectator_bootstrap.perspective.kind is PerspectiveKind.SPECTATOR_KNOWLEDGE_UNION
    assert spectator_bootstrap.world.equipment_by_entity == {}

    with pytest.raises(ValidationError, match="exactly match controlled"):
        SubjectivePerspective(
            perspective_epoch_id="p",
            kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
            controlled_entity_uuids=("hero", "ally"),
            observer_entity_uuids=("hero",),
            active_observer_uuid="hero",
        )
    with pytest.raises(ValidationError):
        SubjectivePerspective.model_validate({
            "projection": "objective",
            "perspective_epoch_id": "p",
            "kind": "spectator_knowledge_union",
            "controlled_entity_uuids": [],
            "observer_entity_uuids": ["hero"],
            "active_observer_uuid": "hero",
        })
    with pytest.raises(ValidationError, match="at least 1 item"):
        SubjectivePerspective.model_validate({
            "perspective_epoch_id": "p",
            "kind": "spectator_knowledge_union",
            "controlled_entity_uuids": [],
            "observer_entity_uuids": [],
            "active_observer_uuid": "hero",
        })


def test_world_patches_are_discriminated_and_have_no_opaque_data_payload() -> None:
    """Patch decoding is closed over concrete reducer mutations."""
    adapter = TypeAdapter(SubjectiveWorldPatch)
    patch = adapter.validate_python({
        "kind": "entity_remove",
        "entity_uuid": "hidden-after-departure",
    })
    schema = adapter.json_schema()

    assert patch.kind == "entity_remove"
    assert schema["discriminator"]["propertyName"] == "kind"
    assert set(schema["discriminator"]["mapping"]) == {
        "controlled_equipment_replace",
        "door_state",
        "encounter_replace",
        "entity_remove",
        "entity_upsert",
        "floor_object_remove",
        "floor_object_upsert",
        "observer_visibility_remove",
        "observer_visibility_replace",
        "tile_upsert",
        "visual_loadout_replace",
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        adapter.validate_python({
            "kind": "entity_remove",
            "entity_uuid": "entity-1",
            "data": {"raw": "payload"},
        })
    with pytest.raises(ValidationError, match="union_tag_invalid"):
        adapter.validate_python({"kind": "raw_event", "event": {}})


def test_floor_objects_use_a_closed_typed_world_and_patch_projection() -> None:
    door = SubjectiveFloorObject(
        uuid="door-1",
        name="Directional Door",
        position=(1, 0),
        map_char="D",
        object_kind=FloorObjectProjectionKind.DOOR,
        safe_presentation_ref=_safe_presentation_ref(
            ContentPresentation(
                sprite_key="DirectionalDoor",
                visual_variant_key="stone",
            ),
        ),
        visual_item_name="DirectionalDoor",
        visual_variant_id="stone",
        blocks_movement=True,
        blocks_vision=True,
        is_open=False,
        blocked_directions=(FloorObjectDirection.WEST,),
        blocked_channels=(
            FloorObjectBlockingChannel.MOVEMENT,
            FloorObjectBlockingChannel.VISION,
        ),
    )
    world_payload = _world().model_dump(mode="python")
    world_payload["state"]["floor_objects"] = (door.model_dump(mode="python"),)
    world = SubjectiveReplicatedWorld.model_validate(world_payload)
    patch = TypeAdapter(SubjectiveWorldPatch).validate_python({
        "kind": "floor_object_upsert",
        "object": door.model_dump(mode="python"),
    })

    assert isinstance(patch, FloorObjectUpsertPatch)
    assert world.state.floor_objects == (door,)
    assert patch.object == door
    assert patch.object.visual_item_name == "DirectionalDoor"
    assert patch.object.visual_variant_id == "stone"
    assert "state" not in SubjectiveFloorObject.model_fields

    opaque = door.model_dump(mode="python")
    opaque["state"] = {"is_open": False, "concrete_model_secret": "leak"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TypeAdapter(SubjectiveWorldPatch).validate_python({
            "kind": "floor_object_upsert",
            "object": opaque,
        })

    mismatched = door.model_dump(mode="python")
    mismatched["object_kind"] = FloorObjectProjectionKind.ITEM
    with pytest.raises(ValidationError, match="only for doors and structures"):
        SubjectiveFloorObject.model_validate(mismatched)


def _cue_base(
    cursor: int,
    *,
    presentation_id: str,
    parent_presentation_id: str | None = None,
    child_presentation_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "presentation_cursor": cursor,
        "presentation_id": presentation_id,
        "parent_presentation_id": parent_presentation_id,
        "child_presentation_ids": child_presentation_ids,
        "source_event_cursor": cursor + 20,
        "source_event_uuid": f"event-{cursor}",
    }


def _all_presentation_cues() -> tuple[SubjectivePresentationCue, ...]:
    enemy_loadout = _loadout("enemy", "RustySword")
    return (
        MovementPresentationCue.model_validate({
            **_cue_base(1, presentation_id="movement"),
            "entity_uuid": "hero",
            "movement_kind": MovementKind.WALK,
            "trajectory": ((0, 0), (1, 0), (2, 0)),
            "path_start_index": 0,
            "path_total_steps": 2,
            "perception_commit": "observation_frame",
        }),
        AttackPresentationCue.model_validate({
            **_cue_base(
                2,
                presentation_id="attack",
                child_presentation_ids=("attack-damage",),
            ),
            "actor_uuid": "hero",
            "target_uuid": "enemy",
            "action_name": "Longbow",
            "outcome": AttackOutcome.HIT,
            "delivery": AttackDelivery.PROJECTILE,
            "weapon_slot": PresentationWeaponSlot.RANGED_MAIN,
            "damage_types": (PresentationDamageType.PIERCING,),
            "projectile_type": PresentationProjectile.BOLT,
            "impact_effect_presentation_ids": ("attack-damage",),
        }),
        DamagePresentationCue.model_validate({
            **_cue_base(
                3,
                presentation_id="attack-damage",
                parent_presentation_id="attack",
                child_presentation_ids=("enemy-dies",),
            ),
            "source_uuid": "hero",
            "target_uuid": "enemy",
            "applied_amount": 7,
            "resulting_hp": 0,
            "damage_types": (PresentationDamageType.PIERCING,),
        }),
        LifeStatePresentationCue.model_validate({
            **_cue_base(
                4,
                presentation_id="enemy-dies",
                parent_presentation_id="attack-damage",
            ),
            "entity_uuid": "enemy",
            "previous": LifeState.ALIVE,
            "current": LifeState.DEAD,
            "reason": LifeStateChangeReason.DAMAGE,
            "causing_effect_presentation_id": "attack-damage",
        }),
        SpellPresentationCue.model_validate({
            **_cue_base(
                5,
                presentation_id="spell",
                child_presentation_ids=("spell-damage", "spell-condition"),
            ),
            "actor_uuid": "hero",
            "spell_id": "fireball",
            "spell_name": "Fireball",
            "spell_school": PresentationSpellSchool.EVOCATION,
            "spell_level": 3,
            "delivery": SpellDelivery.AOE,
            "targets": (
                SpellTargetPresentation(
                    application_index=0,
                    application_id="fireball-application-0",
                    outcome=SpellApplicationOutcome.SAVE_FAILED,
                    target_uuid="enemy",
                    effect_presentation_ids=("spell-damage",),
                ),
                SpellTargetPresentation(
                    application_index=1,
                    application_id="fireball-application-1",
                    outcome=SpellApplicationOutcome.SAVE_SUCCEEDED,
                    target_uuid="enemy",
                    effect_presentation_ids=("spell-condition",),
                ),
            ),
            "projectile_type": PresentationProjectile.ORB,
            "area": SphereAreaGeometry(
                center=(2, 0),
                radius_feet=20,
            ),
        }),
        DamagePresentationCue.model_validate({
            **_cue_base(
                6,
                presentation_id="spell-damage",
                parent_presentation_id="spell",
            ),
            "source_uuid": "hero",
            "target_uuid": "enemy",
            "applied_amount": 4,
            "resulting_hp": 0,
            "damage_types": (PresentationDamageType.FIRE,),
        }),
        ConditionPresentationCue.model_validate({
            **_cue_base(
                7,
                presentation_id="spell-condition",
                parent_presentation_id="spell",
            ),
            "target_uuid": "enemy",
            "condition_semantic_key": "test.Burning",
            "condition_name": "Burning",
            "condition_category": "harmful",
            "operation": ConditionOperation.APPLIED,
        }),
        ItemActionPresentationCue.model_validate({
            **_cue_base(
                8,
                presentation_id="drink-potion",
                child_presentation_ids=("potion-heal",),
            ),
            "actor_uuid": "hero",
            "item_uuid": "potion-1",
            "item_kind": ItemPresentationKind.USABLE,
            "action_kind": ItemActionKind.DRINK,
            "actor_clip": "Taunt",
            "effect_frame": 8,
            "playback_speed": 1.0,
            "hidden_slots": (
                ActorVisualSlot.WEAPON,
                ActorVisualSlot.WEAPON_GLOW,
                ActorVisualSlot.OFFHAND,
            ),
            "effect_presentation_ids": ("potion-heal",),
        }),
        HealPresentationCue.model_validate({
            **_cue_base(
                9,
                presentation_id="potion-heal",
                parent_presentation_id="drink-potion",
                child_presentation_ids=("hero-recovers",),
            ),
            "source_uuid": "hero",
            "target_uuid": "hero",
            "amount": 4,
            "resulting_hp": 9,
        }),
        LifeStatePresentationCue.model_validate({
            **_cue_base(
                10,
                presentation_id="hero-recovers",
                parent_presentation_id="potion-heal",
            ),
            "entity_uuid": "hero",
            "previous": LifeState.DYING,
            "current": LifeState.ALIVE,
            "reason": LifeStateChangeReason.HEALING,
            "causing_effect_presentation_id": "potion-heal",
        }),
        ShovePresentationCue.model_validate({
            **_cue_base(
                11,
                presentation_id="shove-success",
                child_presentation_ids=("shove-movement",),
            ),
            "actor_uuid": "hero",
            "target_uuid": "enemy",
            "outcome": ShoveOutcome.SUCCEEDED_PUSH,
            "actor_clip": "Kick",
            "contact_frame": 7,
            "playback_speed": 1.35,
            "forced_movement_presentation_id": "shove-movement",
        }),
        ForcedMovementPresentationCue.model_validate({
            **_cue_base(
                12,
                presentation_id="shove-movement",
                parent_presentation_id="shove-success",
            ),
            "entity_uuid": "enemy",
            "source_uuid": "hero",
            "cause": ForcedMovementCause.SHOVE,
            "actor_action_presentation_id": "shove-success",
            "start_position": (2, 0),
            "end_position": (3, 0),
            "duration_ms": 260,
            "target_clip": "TakeDamage",
            "brace_frame": 5,
            "playback_speed": 1.25,
        }),
        ShovePresentationCue.model_validate({
            **_cue_base(13, presentation_id="shove-resisted"),
            "actor_uuid": "hero",
            "target_uuid": "ally",
            "outcome": ShoveOutcome.RESISTED,
            "actor_clip": "Kick",
            "contact_frame": 7,
            "playback_speed": 1.35,
            "forced_movement_presentation_id": None,
        }),
        DoorPresentationCue.model_validate({
            **_cue_base(14, presentation_id="door"),
            "object_uuid": "door-1",
            "position": (1, 0),
            "is_open": True,
        }),
        LightPresentationCue.model_validate({
            **_cue_base(15, presentation_id="light"),
            "observer_uuid": "hero",
            "mode": "replacement",
            "cells": (EffectiveLightCell(position=(2, 0), light_level=2),),
        }),
        EquipmentPresentationCue.model_validate({
            **_cue_base(16, presentation_id="equipment"),
            "entity_uuid": "enemy",
            "visual_loadout": enemy_loadout,
        }),
        EncounterPresentationCue.model_validate({
            **_cue_base(17, presentation_id="encounter-end"),
            "encounter_uuid": "encounter-1",
            "transition": EncounterTransition.END,
            "round_number": 3,
            "acting_entity_uuid": "hero",
            "reason": "victory",
            "terminal_barrier": True,
            "projected_combatant_uuids": ("hero", "enemy"),
        }),
    )


def test_presentation_union_covers_renderer_semantics_without_raw_events() -> None:
    """Safe cue families preserve animation order, attachments, and graph identity."""
    cues = _all_presentation_cues()
    frame = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=_watermarks(
            source=40,
            observation=1,
            presentation=len(cues),
        ),
        presentation_from_cursor=0,
        presentation=cues,
    )
    restored = SubjectiveReplicationFrame.model_validate_json(frame.model_dump_json())

    assert [cue.kind for cue in restored.presentation] == [
        "movement",
        "attack",
        "damage",
        "life_state",
        "spell",
        "damage",
        "condition",
        "item_action",
        "heal",
        "life_state",
        "shove",
        "forced_movement",
        "shove",
        "door",
        "light",
        "equipment",
        "encounter",
    ]
    movement = restored.presentation[0]
    assert isinstance(movement, MovementPresentationCue)
    assert movement.trajectory == ((0, 0), (1, 0), (2, 0))
    attack = restored.presentation[1]
    assert isinstance(attack, AttackPresentationCue)
    assert attack.projectile_type is PresentationProjectile.BOLT
    assert attack.damage_types == (PresentationDamageType.PIERCING,)
    assert attack.impact_effect_presentation_ids == ("attack-damage",)
    spell = restored.presentation[4]
    assert isinstance(spell, SpellPresentationCue)
    assert [target.application_index for target in spell.targets] == [0, 1]
    assert [target.target_uuid for target in spell.targets] == ["enemy", "enemy"]
    assert [target.outcome for target in spell.targets] == [
        SpellApplicationOutcome.SAVE_FAILED,
        SpellApplicationOutcome.SAVE_SUCCEEDED,
    ]
    assert [target.effect_presentation_ids for target in spell.targets] == [
        ("spell-damage",),
        ("spell-condition",),
    ]
    assert isinstance(spell.area, SphereAreaGeometry)
    assert spell.area.radius_feet == 20
    item = restored.presentation[7]
    assert isinstance(item, ItemActionPresentationCue)
    assert item.effect_frame == 8
    assert item.effect_presentation_ids == ("potion-heal",)
    shove = restored.presentation[10]
    forced = restored.presentation[11]
    resisted = restored.presentation[12]
    assert isinstance(shove, ShovePresentationCue)
    assert isinstance(forced, ForcedMovementPresentationCue)
    assert isinstance(resisted, ShovePresentationCue)
    assert forced.actor_action_presentation_id == shove.presentation_id
    assert resisted.outcome is ShoveOutcome.RESISTED
    assert resisted.forced_movement_presentation_id is None
    terminal = restored.presentation[-1]
    assert isinstance(terminal, EncounterPresentationCue)
    assert terminal.terminal_barrier is True

    cue_adapter = TypeAdapter(SubjectivePresentationCue)
    assert cue_adapter.json_schema()["discriminator"]["propertyName"] == "kind"
    assert "event" not in SubjectiveReplicationFrame.model_fields
    assert all("event" not in cue_type.model_fields for cue_type in get_args(get_args(SubjectivePresentationCue)[0]))

    payload = frame.model_dump(mode="python")
    payload["event"] = {"wire_type": "dnd.core.events.Event"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SubjectiveReplicationFrame.model_validate(payload)


def test_content_attribution_is_exact_rooted_or_unrooted_without_nullable_refs() -> None:
    """Authenticated content roles never reconstruct identity from cue labels."""
    reaction_ref = _content_ref(
        kind=ContentDefinitionKind.REACTION,
        content_id="reaction.counterspell",
        digest_char="a",
    )
    spell_ref = _content_ref(
        kind=ContentDefinitionKind.SPELL,
        content_id="spell.fireball",
        digest_char="b",
    )
    item_ref = _content_ref(
        kind=ContentDefinitionKind.ITEM,
        content_id="item.red_cloak",
        digest_char="c",
    )
    direct = UnrootedBehaviorPresentationAttribution(
        role=BehaviorPresentationRole.BEHAVIOR,
        definition_ref=reaction_ref,
        provided_by_ref=reaction_ref,
    )
    rooted = RootedBehaviorPresentationAttribution(
        role=BehaviorPresentationRole.TRIGGER_BEHAVIOR,
        definition_ref=spell_ref,
        provided_by_ref=spell_ref,
        origin_root_ref=item_ref,
    )
    source_item = SourceItemPresentationAttribution(definition_ref=item_ref)

    assert "origin_root_ref" not in type(direct).model_fields
    assert rooted.origin_root_ref == item_ref
    assert source_item.definition_ref.content_id == "item.red_cloak"

    invalid_rooted = rooted.model_dump(mode="python")
    invalid_rooted.pop("origin_root_ref")
    with pytest.raises(ValidationError, match="origin_root_ref"):
        RootedBehaviorPresentationAttribution.model_validate(invalid_rooted)
    with pytest.raises(ValidationError, match="item or environment-object"):
        SourceItemPresentationAttribution(
            definition_ref=spell_ref,
        )


def test_counterspell_is_a_closed_attributed_nonmovement_reaction() -> None:
    """Counterspell check shape and both causal content roles are explicit."""
    reaction_ref = _content_ref(
        kind=ContentDefinitionKind.REACTION,
        content_id="reaction.counterspell",
        digest_char="d",
    )
    spell_ref = _content_ref(
        kind=ContentDefinitionKind.SPELL,
        content_id="spell.fireball",
        digest_char="e",
    )
    attributions = (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=reaction_ref,
            provided_by_ref=reaction_ref,
        ),
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.TRIGGER_BEHAVIOR,
            definition_ref=spell_ref,
            provided_by_ref=spell_ref,
        ),
    )
    automatic = CounterspellPresentationCue.model_validate({
        **_cue_base(1, presentation_id="counterspell"),
        "reactor_uuid": "abjurer",
        "incoming_caster_uuid": "wizard",
        "incoming_spell_level": 3,
        "counterspell_slot_level": 3,
        "resolution": CounterspellAutomaticSuccess(),
        "content_attributions": attributions,
    })
    restored = TypeAdapter(SubjectivePresentationCue).validate_json(
        automatic.model_dump_json()
    )
    assert isinstance(restored, CounterspellPresentationCue)
    assert isinstance(restored.resolution, CounterspellAutomaticSuccess)

    checked = automatic.model_copy(update={
        "incoming_spell_level": 5,
        "resolution": CounterspellCheckSuccess(
            check_total=15,
            check_dc=15,
        ),
    })
    assert isinstance(checked.resolution, CounterspellCheckSuccess)
    failed = automatic.model_copy(update={
        "incoming_spell_level": 5,
        "resolution": CounterspellCheckFailure(
            check_total=14,
            check_dc=15,
        ),
    })
    assert isinstance(failed.resolution, CounterspellCheckFailure)

    missing_trigger = automatic.model_dump(mode="python")
    missing_trigger["content_attributions"] = attributions[:1]
    with pytest.raises(ValidationError, match="incoming-spell behavior attribution"):
        CounterspellPresentationCue.model_validate(missing_trigger)

    duplicate_role = automatic.model_dump(mode="python")
    duplicate_role["content_attributions"] = (attributions[0], attributions[0])
    with pytest.raises(ValidationError, match="roles must be unique"):
        CounterspellPresentationCue.model_validate(duplicate_role)

    invalid_checked = automatic.model_dump(mode="python")
    invalid_checked["incoming_spell_level"] = 5
    invalid_checked["resolution"] = {
        "kind": "check_failure",
        "check_total": 15,
        "check_dc": 15,
    }
    with pytest.raises(ValidationError, match="below its DC"):
        CounterspellPresentationCue.model_validate(invalid_checked)


def test_presentation_graph_rejects_dangling_duplicate_and_wrongly_reparented_nodes() -> None:
    """Projection output is one closed graph, not a partially leaked source lineage."""
    valid = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=_watermarks(source=50, observation=1, presentation=17),
        presentation_from_cursor=0,
        presentation=_all_presentation_cues(),
    )

    dangling = valid.model_dump(mode="python")
    dangling["presentation"] = [
        cue for cue in dangling["presentation"] if cue["presentation_id"] != "attack-damage"
    ]
    dangling["watermarks"]["presentation_cursor"] = 16
    for cursor, cue in enumerate(dangling["presentation"], start=1):
        cue["presentation_cursor"] = cursor
    with pytest.raises(ValidationError, match="dangling child"):
        SubjectiveReplicationFrame.model_validate(dangling)

    duplicate = valid.model_dump(mode="python")
    duplicate["presentation"][1]["presentation_id"] = "movement"
    with pytest.raises(ValidationError, match="exactly one cue"):
        SubjectiveReplicationFrame.model_validate(duplicate)

    reparented = valid.model_dump(mode="python")
    reparented["presentation"][2]["parent_presentation_id"] = "spell"
    with pytest.raises(ValidationError, match="bidirectional"):
        SubjectiveReplicationFrame.model_validate(reparented)


def test_movement_children_are_pre_segment_reactive_actions() -> None:
    """Movement may own only reactions resolved before its segment commit."""
    movement = MovementPresentationCue.model_validate({
        **_cue_base(
            1,
            presentation_id="movement",
            child_presentation_ids=("reaction",),
        ),
        "source_event_cursor": 30,
        "entity_uuid": "hero",
        "movement_kind": MovementKind.WALK,
        "trajectory": ((0, 0), (1, 0), (2, 0)),
        "path_start_index": 4,
        "path_total_steps": 8,
        "perception_commit": "observation_frame",
    })
    reaction = AttackPresentationCue.model_validate({
        **_cue_base(
            2,
            presentation_id="reaction",
            parent_presentation_id="movement",
        ),
        "source_event_cursor": 29,
        "actor_uuid": "enemy",
        "target_uuid": "hero",
        "action_name": "Opportunity Attack",
        "outcome": AttackOutcome.MISS,
        "delivery": AttackDelivery.MELEE,
        "weapon_slot": PresentationWeaponSlot.MELEE_MAIN,
        "damage_types": (PresentationDamageType.SLASHING,),
        "projectile_type": None,
        "impact_effect_presentation_ids": (),
    })
    valid = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=_watermarks(source=30, observation=1, presentation=2),
        presentation_from_cursor=0,
        presentation=(movement, reaction),
    )
    assert valid.presentation == (movement, reaction)

    late = valid.model_dump(mode="python")
    late["presentation"][1]["source_event_cursor"] = 30
    with pytest.raises(ValidationError, match="before the owning segment commits"):
        SubjectiveReplicationFrame.model_validate(late)

    wrong_child = DoorPresentationCue.model_validate({
        **_cue_base(
            2,
            presentation_id="reaction",
            parent_presentation_id="movement",
        ),
        "source_event_cursor": 29,
        "object_uuid": "door",
        "position": (0, 0),
        "is_open": True,
    })
    with pytest.raises(ValidationError, match="pre-motion attack, spell, or shove"):
        SubjectiveReplicationFrame(
            source_stream_id="stream-1",
            generation_id="generation-1",
            perspective_epoch_id="perspective-1",
            watermarks=_watermarks(source=30, observation=1, presentation=2),
            presentation_from_cursor=0,
            presentation=(movement, wrong_child),
        )


def test_presentation_graph_rejects_action_effect_ownership_mismatches() -> None:
    """Delivered impact targets and sources must agree with their owning action."""
    valid = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=_watermarks(source=50, observation=1, presentation=17),
        presentation_from_cursor=0,
        presentation=_all_presentation_cues(),
    )

    wrong_attack_target = valid.model_dump(mode="python")
    wrong_attack_target["presentation"][2]["target_uuid"] = "bystander"
    with pytest.raises(ValidationError, match="attack impact target"):
        SubjectiveReplicationFrame.model_validate(wrong_attack_target)

    wrong_attack_source = valid.model_dump(mode="python")
    wrong_attack_source["presentation"][2]["source_uuid"] = "bystander"
    with pytest.raises(ValidationError, match="attack impact source"):
        SubjectiveReplicationFrame.model_validate(wrong_attack_source)

    wrong_drink_target = valid.model_dump(mode="python")
    wrong_drink_target["presentation"][8]["target_uuid"] = "bystander"
    with pytest.raises(ValidationError, match="drink-item impact target"):
        SubjectiveReplicationFrame.model_validate(wrong_drink_target)

    position_only_effect = valid.model_dump(mode="python")
    position_only_effect["presentation"][4]["targets"][0]["target_uuid"] = None
    position_only_effect["presentation"][4]["targets"][0]["position"] = (2, 0)
    with pytest.raises(ValidationError, match="explicit target UUID"):
        SubjectiveReplicationFrame.model_validate(position_only_effect)


def test_presentation_ids_remain_unique_across_an_observation_page() -> None:
    first_cue = MovementPresentationCue.model_validate({
        **_cue_base(1, presentation_id="reused-id"),
        "entity_uuid": "hero",
        "movement_kind": MovementKind.WALK,
        "trajectory": ((0, 0), (1, 0)),
        "path_total_steps": 1,
        "perception_commit": "observation_frame",
    })
    second_cue = DoorPresentationCue.model_validate({
        **_cue_base(2, presentation_id="reused-id"),
        "object_uuid": "door-1",
        "position": (1, 0),
        "is_open": True,
    })
    first_watermarks = _watermarks(source=21, observation=1, presentation=1)
    second_watermarks = _watermarks(source=22, observation=2, presentation=2)
    first = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=first_watermarks,
        presentation_from_cursor=0,
        presentation=(first_cue,),
    )
    second = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=second_watermarks,
        presentation_from_cursor=1,
        presentation=(second_cue,),
    )

    with pytest.raises(ValidationError, match="unique across response frames"):
        SubjectiveFramesResponse(
            source_stream_id="stream-1",
            generation_id="generation-1",
            perspective_epoch_id="perspective-1",
            retained_from_observation_cursor=0,
            from_watermarks=_watermarks(
                source=0,
                observation=0,
                presentation=0,
            ),
            through_watermarks=second_watermarks,
            captured_watermarks=second_watermarks,
            frames=(first, second),
        )


def test_closed_dispatch_enums_and_shape_geometry_reject_client_inference() -> None:
    """Unsupported arrows, arbitrary damage tags, and incomplete AOE shapes fail closed."""
    assert PresentationWeaponSlot.RANGED_OFF.value == "RANGED_OFF"

    attack = _all_presentation_cues()[1].model_dump(mode="python")
    attack["projectile_type"] = "arrow"
    with pytest.raises(ValidationError, match="enum"):
        AttackPresentationCue.model_validate(attack)

    damage = _all_presentation_cues()[2].model_dump(mode="python")
    damage["damage_types"] = ["plasma"]
    with pytest.raises(ValidationError, match="enum"):
        DamagePresentationCue.model_validate(damage)

    with pytest.raises(ValidationError, match="width_feet"):
        SpellPresentationCue.model_validate({
            **_cue_base(1, presentation_id="line-spell"),
            "actor_uuid": "hero",
            "spell_id": "lightning_bolt",
            "spell_name": "Lightning Bolt",
            "spell_school": PresentationSpellSchool.EVOCATION,
            "spell_level": 3,
            "delivery": SpellDelivery.AOE,
            "targets": (),
            "area": {
                "shape": "line",
                "origin": (0, 0),
                "direction": (1, 0),
                "length_feet": 100,
            },
        })

    cone = ConeAreaGeometry(
        origin=(0, 0),
        direction=(1, 0),
        length_feet=30,
        angle_degrees=53,
    )
    assert cone.angle_degrees == 53
    with pytest.raises(ValidationError, match="angle_degrees"):
        ConeAreaGeometry.model_validate({
            "origin": (0, 0),
            "direction": (1, 0),
            "length_feet": 30,
        })

    centered_cube = CubeAreaGeometry(
        origin=(2, 2),
        size_feet=10,
        centered=True,
    )
    directional_cube = CubeAreaGeometry(
        origin=(2, 2),
        direction=(0, 1),
        size_feet=15,
        centered=False,
    )
    assert centered_cube.direction is None
    assert directional_cube.direction == (0, 1)
    with pytest.raises(ValidationError, match="directional cube requires"):
        CubeAreaGeometry(
            origin=(2, 2),
            size_feet=15,
            centered=False,
        )
    with pytest.raises(ValidationError, match="centered cube cannot"):
        CubeAreaGeometry(
            origin=(2, 2),
            direction=(0, 1),
            size_feet=15,
            centered=True,
        )

    direct_spell = SpellPresentationCue.model_validate({
        **_cue_base(1, presentation_id="hold-person"),
        "actor_uuid": "hero",
        "spell_id": "hold_person",
        "spell_name": "Hold Person",
        "spell_school": PresentationSpellSchool.ENCHANTMENT,
        "spell_level": 2,
        "delivery": SpellDelivery.DIRECT,
        "targets": (
            SpellTargetPresentation(
                application_index=0,
                application_id="hold-person-application-0",
                outcome=SpellApplicationOutcome.SAVE_SUCCEEDED,
                target_uuid="enemy",
            ),
        ),
    })
    assert direct_spell.projectile_type is None
    assert direct_spell.area is None


def test_spell_forced_movement_is_an_explicit_application_effect() -> None:
    """A spell push is attached to one target application, never inferred from adjacency."""
    spell = SpellPresentationCue.model_validate({
        **_cue_base(
            1,
            presentation_id="thunderwave",
            child_presentation_ids=("thunderwave-push",),
        ),
        "actor_uuid": "hero",
        "spell_id": "thunderwave",
        "spell_name": "Thunderwave",
        "spell_school": PresentationSpellSchool.EVOCATION,
        "spell_level": 1,
        "delivery": SpellDelivery.AOE,
        "targets": (
            SpellTargetPresentation(
                application_index=0,
                application_id="thunderwave-application-0",
                outcome=SpellApplicationOutcome.SAVE_FAILED,
                target_uuid="enemy",
                effect_presentation_ids=("thunderwave-push",),
            ),
        ),
        "area": SphereAreaGeometry(center=(0, 0), radius_feet=15),
    })
    forced = ForcedMovementPresentationCue.model_validate({
        **_cue_base(
            2,
            presentation_id="thunderwave-push",
            parent_presentation_id="thunderwave",
        ),
        "entity_uuid": "enemy",
        "source_uuid": "hero",
        "cause": ForcedMovementCause.SPELL,
        "actor_action_presentation_id": "thunderwave",
        "start_position": (1, 0),
        "end_position": (2, 0),
        "duration_ms": 260,
        "brace_frame": 5,
        "playback_speed": 1.25,
    })
    frame = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=_watermarks(source=30, observation=1, presentation=2),
        presentation_from_cursor=0,
        presentation=(spell, forced),
    )

    assert frame.presentation[1].presentation_id == "thunderwave-push"
    assert spell.targets[0].effect_presentation_ids == ("thunderwave-push",)

    mismatched = frame.model_dump(mode="python")
    mismatched["presentation"][1]["entity_uuid"] = "ally"
    with pytest.raises(ValidationError, match="target must match"):
        SubjectiveReplicationFrame.model_validate(mismatched)


def test_shove_outcomes_distinguish_push_prone_blocked_and_resisted() -> None:
    prone = ShovePresentationCue.model_validate({
        **_cue_base(
            1,
            presentation_id="shove-prone",
            child_presentation_ids=("prone-applied",),
        ),
        "actor_uuid": "hero",
        "target_uuid": "enemy",
        "outcome": ShoveOutcome.SUCCEEDED_PRONE,
        "actor_clip": "Kick",
        "contact_frame": 7,
        "playback_speed": 1.35,
        "prone_condition_presentation_id": "prone-applied",
    })
    prone_applied = ConditionPresentationCue.model_validate({
        **_cue_base(
            2,
            presentation_id="prone-applied",
            parent_presentation_id="shove-prone",
        ),
        "target_uuid": "enemy",
        "condition_semantic_key": "dnd.conditions.Prone",
        "condition_name": "Prone",
        "condition_category": "harmful",
        "operation": ConditionOperation.APPLIED,
    })
    blocked = ShovePresentationCue.model_validate({
        **_cue_base(3, presentation_id="shove-blocked"),
        "actor_uuid": "hero",
        "target_uuid": "blocked-enemy",
        "outcome": ShoveOutcome.SUCCEEDED_BLOCKED,
        "actor_clip": "Kick",
        "contact_frame": 7,
        "playback_speed": 1.35,
    })
    resisted = ShovePresentationCue.model_validate({
        **_cue_base(4, presentation_id="shove-resisted-again"),
        "actor_uuid": "hero",
        "target_uuid": "resisting-enemy",
        "outcome": ShoveOutcome.RESISTED,
        "actor_clip": "Kick",
        "contact_frame": 7,
        "playback_speed": 1.35,
    })
    frame = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=_watermarks(source=30, observation=1, presentation=4),
        presentation_from_cursor=0,
        presentation=(prone, prone_applied, blocked, resisted),
    )

    assert [cue.outcome for cue in frame.presentation if isinstance(cue, ShovePresentationCue)] == [
        ShoveOutcome.SUCCEEDED_PRONE,
        ShoveOutcome.SUCCEEDED_BLOCKED,
        ShoveOutcome.RESISTED,
    ]
    assert blocked.child_presentation_ids == ()

    with pytest.raises(ValidationError, match="requires a forced-movement child"):
        ShovePresentationCue.model_validate({
            **blocked.model_dump(mode="python"),
            "outcome": ShoveOutcome.SUCCEEDED_PUSH,
        })

    wrong_condition = frame.model_dump(mode="python")
    wrong_condition["presentation"][1]["condition_name"] = "Grappled"
    with pytest.raises(ValidationError, match="apply Prone"):
        SubjectiveReplicationFrame.model_validate(wrong_condition)


def test_damage_carries_applied_total_and_ordered_categories_without_allocation() -> None:
    damage = DamagePresentationCue.model_validate({
        **_cue_base(1, presentation_id="mixed-damage"),
        "source_uuid": "hero",
        "target_uuid": "enemy",
        "applied_amount": 5,
        "resulting_hp": 3,
        "damage_types": (
            PresentationDamageType.SLASHING,
            PresentationDamageType.FIRE,
        ),
    })

    assert damage.applied_amount == 5
    assert damage.damage_types == (
        PresentationDamageType.SLASHING,
        PresentationDamageType.FIRE,
    )
    assert "components" not in DamagePresentationCue.model_fields

    invented_allocation = damage.model_dump(mode="python")
    invented_allocation["components"] = (
        {"amount": 2, "damage_type": PresentationDamageType.SLASHING},
        {"amount": 3, "damage_type": PresentationDamageType.FIRE},
    )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DamagePresentationCue.model_validate({
            **invented_allocation,
        })


def test_dying_and_death_save_stabilization_are_explicit_impact_attached_transitions() -> None:
    damage = DamagePresentationCue.model_validate({
        **_cue_base(
            1,
            presentation_id="downing-damage",
            child_presentation_ids=("becomes-dying",),
        ),
        "source_uuid": "enemy",
        "target_uuid": "hero",
        "applied_amount": 5,
        "resulting_hp": 0,
        "damage_types": (PresentationDamageType.BLUDGEONING,),
    })
    dying = LifeStatePresentationCue.model_validate({
        **_cue_base(
            2,
            presentation_id="becomes-dying",
            parent_presentation_id="downing-damage",
        ),
        "entity_uuid": "hero",
        "previous": LifeState.ALIVE,
        "current": LifeState.DYING,
        "reason": LifeStateChangeReason.DAMAGE,
        "causing_effect_presentation_id": "downing-damage",
    })
    stabilizing = LifecycleCausePresentationCue.model_validate({
        **_cue_base(
            3,
            presentation_id="stabilizing-death-save",
            child_presentation_ids=("becomes-stable",),
        ),
        "entity_uuid": "hero",
        "cause_kind": LifecycleCauseKind.DEATH_SAVE,
        "death_save_outcome": DeathSaveOutcome.SUCCESS,
    })
    stable = LifeStatePresentationCue.model_validate({
        **_cue_base(
            4,
            presentation_id="becomes-stable",
            parent_presentation_id="stabilizing-death-save",
        ),
        "entity_uuid": "hero",
        "previous": LifeState.DYING,
        "current": LifeState.STABLE,
        "reason": LifeStateChangeReason.STABILIZATION,
        "causing_effect_presentation_id": "stabilizing-death-save",
    })
    frame = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=_watermarks(source=30, observation=1, presentation=4),
        presentation_from_cursor=0,
        presentation=(damage, dying, stabilizing, stable),
    )

    assert [cue.current for cue in frame.presentation if isinstance(cue, LifeStatePresentationCue)] == [
        LifeState.DYING,
        LifeState.STABLE,
    ]


def test_non_damage_lifecycle_causes_do_not_require_fabricated_damage_or_heal() -> None:
    death_save = LifecycleCausePresentationCue.model_validate({
        **_cue_base(
            1,
            presentation_id="failed-death-save",
            child_presentation_ids=("death-save-death",),
        ),
        "entity_uuid": "failed-hero",
        "cause_kind": LifecycleCauseKind.DEATH_SAVE,
        "death_save_outcome": DeathSaveOutcome.FAILURE,
    })
    death_save_death = LifeStatePresentationCue.model_validate({
        **_cue_base(
            2,
            presentation_id="death-save-death",
            parent_presentation_id="failed-death-save",
        ),
        "entity_uuid": "failed-hero",
        "previous": LifeState.DYING,
        "current": LifeState.DEAD,
        "reason": LifeStateChangeReason.DEATH_SAVE_FAILURES,
        "causing_effect_presentation_id": "failed-death-save",
    })
    revive = LifecycleCausePresentationCue.model_validate({
        **_cue_base(
            3,
            presentation_id="revive",
            child_presentation_ids=("revived",),
        ),
        "entity_uuid": "revived-hero",
        "cause_kind": LifecycleCauseKind.REVIVE,
    })
    revived = LifeStatePresentationCue.model_validate({
        **_cue_base(
            4,
            presentation_id="revived",
            parent_presentation_id="revive",
        ),
        "entity_uuid": "revived-hero",
        "previous": LifeState.DEAD,
        "current": LifeState.ALIVE,
        "reason": LifeStateChangeReason.REVIVAL,
        "causing_effect_presentation_id": "revive",
    })
    instant_death = LifecycleCausePresentationCue.model_validate({
        **_cue_base(
            5,
            presentation_id="instant-death",
            child_presentation_ids=("instantly-dead",),
        ),
        "entity_uuid": "instant-target",
        "cause_kind": LifecycleCauseKind.INSTANT_DEATH,
        "source_uuid": "lich",
    })
    instantly_dead = LifeStatePresentationCue.model_validate({
        **_cue_base(
            6,
            presentation_id="instantly-dead",
            parent_presentation_id="instant-death",
        ),
        "entity_uuid": "instant-target",
        "previous": LifeState.ALIVE,
        "current": LifeState.DEAD,
        "reason": LifeStateChangeReason.INSTANT_DEATH,
        "causing_effect_presentation_id": "instant-death",
    })
    direct_check = LifecycleCausePresentationCue.model_validate({
        **_cue_base(
            7,
            presentation_id="direct-state-check",
            child_presentation_ids=("directly-dead",),
        ),
        "entity_uuid": "unchecked-npc",
        "cause_kind": LifecycleCauseKind.DIRECT_STATE_CHECK,
    })
    directly_dead = LifeStatePresentationCue.model_validate({
        **_cue_base(
            8,
            presentation_id="directly-dead",
            parent_presentation_id="direct-state-check",
        ),
        "entity_uuid": "unchecked-npc",
        "previous": LifeState.ALIVE,
        "current": LifeState.DEAD,
        "reason": LifeStateChangeReason.DIRECT_STATE_CHECK,
        "causing_effect_presentation_id": "direct-state-check",
    })
    frame = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=_watermarks(source=40, observation=1, presentation=8),
        presentation_from_cursor=0,
        presentation=(
            death_save,
            death_save_death,
            revive,
            revived,
            instant_death,
            instantly_dead,
            direct_check,
            directly_dead,
        ),
    )

    assert not any(
        isinstance(cue, (DamagePresentationCue, HealPresentationCue))
        for cue in frame.presentation
    )

    mismatched = frame.model_dump(mode="python")
    mismatched["presentation"][7]["reason"] = LifeStateChangeReason.INSTANT_DEATH
    with pytest.raises(ValidationError, match="direct-state cause"):
        SubjectiveReplicationFrame.model_validate(mismatched)


def test_active_weapon_set_allows_hidden_and_unarmed_presentations() -> None:
    hidden = EntityVisualLoadout(
        entity_uuid="hidden-archer",
        active_weapon_set=ActiveWeaponSet.RANGED,
        layers=(
            VisualEquipmentLayer(
                slot=VisualLoadoutSlot.WEAPON_RANGED_MAIN,
                item_kind=ItemPresentationKind.WEAPON,
                safe_presentation_ref=_safe_presentation_ref(
                    ContentPresentation(sprite_key="Longbow"),
                ),
                visual_item_name="Longbow",
                equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
            ),
        ),
    )
    unarmed = EntityVisualLoadout(
        entity_uuid="unarmed-brawler",
        active_weapon_set=ActiveWeaponSet.MELEE,
        layers=(),
    )

    assert hidden.layers[0].equipped_visual_policy is EquippedVisualPolicy.HIDDEN
    assert unarmed.layers == ()

    with pytest.raises(ValidationError, match="slots must be unique"):
        EntityVisualLoadout(
            entity_uuid="duplicate",
            layers=(hidden.layers[0], hidden.layers[0]),
        )


def test_light_presentation_has_one_complete_replacement_path() -> None:
    replacement = LightPresentationCue.model_validate({
        **_cue_base(1, presentation_id="light-replacement"),
        "observer_uuid": "hero",
        "cells": (EffectiveLightCell(position=(0, 0), light_level=3),),
    })

    assert replacement.mode == "replacement"
    with pytest.raises(ValidationError, match="positions must be unique"):
        LightPresentationCue.model_validate({
            **_cue_base(1, presentation_id="duplicate-light"),
            "observer_uuid": "hero",
            "cells": (
                EffectiveLightCell(position=(0, 0), light_level=3),
                EffectiveLightCell(position=(0, 0), light_level=2),
            ),
        })


def test_hidden_source_slots_advance_only_safe_watermarks_and_release_log_barriers() -> None:
    """A hidden event needs no fake patch or cue to unblock an exact log slot."""
    before = _watermarks(source=10, observation=5, presentation=3, combat_log=0)
    after_hidden = _watermarks(source=15, observation=6, presentation=3, combat_log=1)
    hidden_frame = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=after_hidden,
        presentation_from_cursor=3,
        patches=(),
        presentation=(),
    )
    page = SubjectiveFramesResponse(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        retained_from_observation_cursor=0,
        from_watermarks=before,
        through_watermarks=after_hidden,
        captured_watermarks=after_hidden,
        frames=(hidden_frame,),
    )
    hidden_log = SubjectiveCombatLogFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        combat_log_cursor=1,
        event_cursor=15,
        entry=None,
    )
    delivery = SubjectiveCombatLogDelivery(
        watermarks=after_hidden,
        frame=hidden_log,
    )

    assert page.frames[0].patches == ()
    assert page.frames[0].presentation == ()
    assert page.through_watermarks.source_event_cursor == 15
    assert page.through_watermarks.presentation_cursor == 3
    assert delivery.frame.entry is None
    assert delivery.frame.event_cursor <= delivery.watermarks.source_event_cursor


def test_live_delivery_union_carries_watermarks_for_sync_frame_and_log() -> None:
    """Every asynchronous delivery has an explicit observation/presentation boundary."""
    bootstrap = _bootstrap()
    watermarks = _watermarks(source=15, observation=6, presentation=3, combat_log=1)
    frame = SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        watermarks=watermarks,
        presentation_from_cursor=3,
    )
    log = SubjectiveCombatLogFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        combat_log_cursor=1,
        event_cursor=15,
        entry=None,
    )
    deliveries: tuple[SubjectiveStreamDelivery, ...] = (
        SubjectiveSyncDelivery(
            protocol=bootstrap.protocol,
            perspective=bootstrap.perspective,
            watermarks=watermarks,
        ),
        SubjectiveFrameDelivery(frame=frame),
        SubjectiveCombatLogDelivery(watermarks=watermarks, frame=log),
    )
    adapter = TypeAdapter(SubjectiveStreamDelivery)

    restored = [adapter.validate_json(adapter.dump_json(item)) for item in deliveries]

    assert [item.kind for item in restored] == [
        "sync",
        "frame",
        "combat_log",
    ]
    assert adapter.json_schema()["discriminator"]["propertyName"] == "kind"
    assert restored[0].watermarks.presentation_cursor == 3
    assert restored[1].frame.watermarks.observation_cursor == 6
    assert restored[2].watermarks.source_event_cursor == 15


def test_bootstrap_rejects_mixed_log_identity_and_objective_projection() -> None:
    """A safe world cannot be paired with another stream, epoch, or projection."""
    valid = _bootstrap()
    objective_logs = CombatLogFramesResponse(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        projection=CombatLogProjection.OBJECTIVE,
        retained_from_cursor=0,
        from_cursor=0,
        through_cursor=0,
        frames=(),
        total=0,
    )
    with pytest.raises(ValidationError, match="projection"):
        SubjectiveReplicationBootstrap.model_validate(
            {
                "protocol": valid.protocol,
                "perspective": valid.perspective,
                "watermarks": valid.watermarks,
                "world": valid.world,
                "combat_log_frames": objective_logs.model_dump(mode="json"),
            }
        )

    wrong_epoch = _empty_logs().model_copy(
        update={"perspective_epoch_id": "another-perspective"}
    )
    with pytest.raises(ValidationError, match="perspective epoch"):
        SubjectiveReplicationBootstrap(
            protocol=valid.protocol,
            perspective=valid.perspective,
            watermarks=valid.watermarks,
            world=valid.world,
            combat_log_frames=wrong_epoch,
        )


def test_contract_identity_is_stable_and_self_authenticating() -> None:
    summary = player_replication_contract_summary()
    wire_schema = player_replication_wire_schema()

    assert summary == {
        "player_replication_contract_version": PLAYER_REPLICATION_CONTRACT_VERSION,
        "player_replication_contract_hash": PLAYER_REPLICATION_CONTRACT_HASH,
    }
    assert PLAYER_REPLICATION_CONTRACT_HASH == hashlib.sha256(
        json.dumps(wire_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    serialized_schema = json.dumps(wire_schema, sort_keys=True)
    for imported_wire_type in (
        "APIEntitySummary",
        "APITile",
        "APIEquipmentOverview",
        "CombatLogFrame",
    ):
        assert imported_wire_type in serialized_schema
    assert wire_schema["canonical_routes"] == (
        "/replication/bootstrap",
        "/replication/frames",
        "/replication/combat-log",
        "/replication/subscribe",
    )
    with pytest.raises(ValidationError, match="contract hash mismatch"):
        PlayerReplicationProtocolIdentity(
            player_replication_contract_hash="drift",
            source_stream_id="stream-1",
            generation_id="generation-1",
        )

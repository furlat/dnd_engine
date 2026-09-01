"""Public chronology and ownership proofs for cold world/entity birth."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.actions_functional import setup_standard_actions
from dnd.blocks.base_item import BaseItem
from dnd.blocks.inventory import Inventory
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.base_block import BaseBlock
from dnd.core.content.encounters import AuthoredCreatureRosterSource
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import ArmorType, WeaponProperty
from dnd.core.events import (
    Event,
    EntityCreatedEvent,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
    WorldConnectorState,
    WorldInitializedEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import ResistanceStatus
from dnd.core.values import BaseValue
from dnd.types.world import MovementMode
from dnd.content_system.creature_bindings import CREATURE_RUNTIME_BINDINGS
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import BATTLEFIELDS, build_battlefield
import dnd.scenarios.encounter_assembler as encounter_assembler
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import encounter_recipe
from dnd.items.torches import WallTorch


def _events():
    """Return the current objective stream through its indexed public read."""
    return tuple(event for _, event in EventQueue.iter_events_since(0))


def _expected_entity_created_fields(entity: Entity) -> dict[str, object]:
    """Derive every birth payload field from the uncommitted aggregate."""
    proficiencies = entity.creature_proficiencies
    equipped_items = tuple(entity.equipment.get_all_equipped_items())
    items_by_uuid = {
        item.uuid: item
        for item in (*entity.inventory.items.values(), *equipped_items)
    }

    weapon_proficiencies = [
        f"weapon.{category.value.lower()}"
        for category in (WeaponProperty.SIMPLE, WeaponProperty.MARTIAL)
        if proficiencies.is_weapon_proficient((category,))
    ]
    weapon_proficiencies.extend(sorted(
        set(proficiencies.base_weapon_ids)
        | {
            key
            for key, sources in proficiencies.specific_weapon_sources.items()
            if sources.sources
        },
    ))
    languages = tuple(sorted(
        set(proficiencies.base_languages)
        | {
            key
            for key, sources in proficiencies.language_sources.items()
            if sources.sources
        },
    ))
    tools = tuple(sorted(
        set(proficiencies.base_tools)
        | {
            key
            for key, sources in proficiencies.tool_sources.items()
            if sources.sources
        },
    ))

    aggregate_blocks = {}
    pending_blocks = [entity]
    while pending_blocks:
        block = pending_blocks.pop()
        if block.uuid in aggregate_blocks:
            continue
        aggregate_blocks[block.uuid] = block
        pending_blocks.extend(block.get_blocks())

    body_semantics = [
        ("structural_base_size", entity.structural_base_size.value),
    ]
    body_semantics.extend(
        (f"size_source:{source_id}", size.value)
        for source_id, size in sorted(
            entity.structural_size_sources.items(),
            key=lambda row: str(row[0]),
        )
    )
    appearance = tuple(
        (field_name, getattr(entity.appearance, field_name))
        for field_name in (
            "portrait_key",
            "presentation_kind",
            "visual_scale",
            "visual_scale_x",
            "placeholder_tint",
            "body_category",
            "skin_tint",
            "head_category",
            "hair_tint",
            "has_beard",
            "beard_tint",
        )
    )

    return {
        "entity_uuid": entity.uuid,
        "entity_kind_id": (
            entity.content_ref.identity_key
            if entity.content_ref is not None
            else f"{type(entity).__module__}.{type(entity).__qualname__}"
        ),
        "entity_name": entity.name,
        "entity_description": entity.description,
        "creature_type": entity.creature_type.value,
        "size": entity.size.value,
        "structural_base_size": entity.structural_base_size.value,
        "weight": entity.weight,
        "faction": entity.faction,
        "creature_content_ref": (
            entity.content_ref.identity_key
            if entity.content_ref is not None
            else None
        ),
        "species_ref": (
            entity.character_species_ref.identity_key
            if entity.character_species_ref is not None
            else None
        ),
        "species_variant_ref": (
            entity.character_species_variant_ref.identity_key
            if entity.character_species_variant_ref is not None
            else None
        ),
        "background_ref": (
            entity.character_background_ref.identity_key
            if entity.character_background_ref is not None
            else None
        ),
        "applied_origin_state": entity.character_origin_state,
        "class_levels": entity.character_class_levels,
        "ability_scores": tuple(
            (ability.name, ability.ability_score.score)
            for ability in entity.ability_scores.abilities_list
        ),
        "skill_proficiencies": tuple(
            skill.name for skill in entity.skill_set.proficiencies
        ),
        "skill_expertise": tuple(
            skill.name for skill in entity.skill_set.expertise
        ),
        "saving_throw_proficiencies": tuple(
            saving_throw.name
            for saving_throw in entity.saving_throws.proficiencies
        ),
        "proficiency_bonus": entity.proficiency_bonus.normalized_score,
        "initiative": entity.initiative.normalized_score,
        "armor_class": entity.ac_bonus().normalized_score,
        "life_state": entity.health.life_state.value,
        "current_hit_points": max(0, entity.get_hp()),
        "maximum_hit_points": max(0, entity.get_max_hp()),
        "temporary_hit_points": max(
            0,
            entity.health.temporary_hit_points.normalized_score,
        ),
        "damage_taken": entity.health.damage_taken,
        "hit_dice": tuple(
            (
                hit_die.hit_dice_value.normalized_score,
                hit_die.hit_dice_count.normalized_score,
                hit_die.spent_hit_dice,
                hit_die.mode,
                hit_die.ignore_first_level,
            )
            for hit_die in entity.health.hit_dices
        ),
        "damage_affinities": tuple(
            (damage_type.value, status.value)
            for damage_type in DamageType
            if (status := entity.health.get_resistance(damage_type))
            is not ResistanceStatus.NONE
        ),
        "walking_speed_feet": entity.action_economy.current_speed(),
        "swimming_speed_feet": entity.swimming_speed,
        "has_ordinary_sight": entity.has_ordinary_sight,
        "sense_modes": tuple(entity.senses.get_sense_modes()),
        "requires_breathing": entity.requires_breathing,
        "uses_death_saves": entity.uses_death_saves,
        "death_save_successes": entity.death_save_successes,
        "death_save_failures": entity.death_save_failures,
        "origin_capabilities": tuple(sorted(
            capability.value
            for capability, sources in entity.origin_capability_sources.items()
            if sources
        )),
        "body_semantics": tuple(body_semantics),
        "appearance": appearance,
        "feature_ids": entity.character_feature_ids,
        "weapon_proficiencies": tuple(weapon_proficiencies),
        "armor_proficiencies": tuple(
            armor_type.value
            for armor_type in (
                ArmorType.LIGHT,
                ArmorType.MEDIUM,
                ArmorType.HEAVY,
            )
            if proficiencies.is_armor_proficient(armor_type)
        ),
        "shield_proficient": proficiencies.is_shield_proficient(),
        "languages": languages,
        "tools": tools,
        "action_ids": tuple(sorted(
            action.get_semantic_key()
            for action in entity.registered_actions
        )),
        "handler_ids": tuple(sorted(
            handler.get_semantic_key()
            for block in aggregate_blocks.values()
            for handler in block.event_handlers.values()
        )),
        "condition_ids": tuple(sorted(
            condition.get_semantic_key()
            for condition in entity.active_conditions_by_uuid.values()
        )),
        "condition_immunities": tuple(sorted({
            condition_name
            for condition_name, _source_name in entity.condition_immunities
        })),
        "attacks_per_action": (
            entity.action_economy.resolve_attacks_per_attack_action()
        ),
        "resources": tuple(
            (
                name,
                resource.current,
                resource.maximum,
                resource.recharge_type.value,
            )
            for name, resource in sorted(
                entity.action_economy.resources.items(),
            )
        ),
        "resource_recoveries": tuple(sorted(
            (
                resource_name,
                contribution.trigger.value,
                contribution.amount,
            )
            for resource_name, resource
            in entity.action_economy.resources.items()
            for contribution in resource.recovery_contributions.values()
        )),
        "attack_multiplicity": tuple(
            (
                grant.provider_ref.identity_key,
                grant.attacks_per_attack_action,
                grant.acquisition_ordinal,
            )
            for grant
            in entity.action_economy.get_attack_multiplicity_grants()
        ),
        "spell_sources": tuple(
            (
                source.source_kind,
                source.provider_ref.identity_key,
                source.ability,
                source.provider_level,
                source.maximum_spell_rank,
            )
            for _source_id, source in sorted(
                entity.spellcasting.sources.items(),
                key=lambda row: str(row[0]),
            )
        ),
        "known_spell_ids": tuple(sorted(
            action.get_semantic_key()
            for action in entity.registered_actions
            if action.is_spell
        )),
        "reaction_spell_ids": tuple(sorted(
            entity.spellcasting.learned_reaction_spell_handlers
        )),
        "prepared_spell_ids": entity.character_prepared_spell_ids,
        "feature_toggle_ids": entity.character_feature_toggle_ids,
        "spell_slots": tuple(
            (
                rank,
                entity.action_economy.spell_slot_value(rank).normalized_score,
            )
            for rank in range(1, 10)
        ),
        "armor_class_formulas": tuple(
            (
                str(candidate.source_id),
                candidate.base_ac,
                candidate.ability_names,
                candidate.requires_unarmored,
                candidate.allows_shield,
            )
            for candidate in sorted(
                entity.equipment.armor_class_formula_candidates.values(),
                key=lambda row: str(row.source_id),
            )
        ),
        "items": tuple(
            items_by_uuid[item_uuid].to_item_presentation_state()
            for item_uuid in sorted(items_by_uuid, key=str)
        ),
        "inventory_item_uuids": tuple(sorted(
            entity.inventory.items,
            key=str,
        )),
        "equipment": tuple(
            (item.equipped_slot, item.uuid)
            for item in equipped_items
        ),
    }


def test_authored_world_publishes_one_cold_root_before_dynamic_state() -> None:
    """Cold objects are complete and traps/torch light settle afterwards."""
    reset_engine_runtime()

    built = build_battlefield("battlefield.standard_hazards_closed")
    events = _events()

    assert isinstance(events[0], WorldInitializedEvent)
    assert events[0].phase is EventPhase.COMPLETION
    assert sum(
        event.event_type is EventType.WORLD_INITIALIZED for event in events
    ) == 1
    world = events[0]
    assert len(world.tiles) == 225
    assert {row.placement for row in world.objects} == set(
        get_map().iter_object_placements()
    )
    assert built.environment is not None
    lever = next(
        row.item
        for row in world.objects
        if row.item.item_uuid == built.environment.trap_lever.uuid
    )
    assert (
        lever.linked_spatial_condition_uuid
        == built.environment.spike_condition_uuid
    )
    torch_states = tuple(
        row.item
        for row in world.objects
        if row.item.item_uuid
        in {torch.uuid for torch in built.environment.wall_torches}
    )
    assert torch_states and all(state.is_lit is False for state in torch_states)
    assert all(torch.is_lit for torch in built.environment.wall_torches)
    assert any(
        condition.uuid == built.environment.spike_condition_uuid
        for condition in get_map().get_spatial_conditions()
    )
    assert all(
        event.parent_event == world.uuid
        for event in events[1:]
        if event.event_type in {
            EventType.CONDITION_APPLICATION,
            EventType.EXPOSED_FLAME_IGNITED,
        }
        and event.phase is EventPhase.DECLARATION
    )


@pytest.mark.parametrize(
    "battlefield_id",
    tuple(spec.battlefield_id for spec in BATTLEFIELDS),
)
def test_every_authored_world_starts_with_one_exact_cold_fact(
    battlefield_id: str,
) -> None:
    """Every maintained builder exposes its exact cold topology as event zero."""
    reset_engine_runtime()

    built = build_battlefield(battlefield_id)
    events = _events()
    world = events[0]
    grid = get_map()

    assert isinstance(world, WorldInitializedEvent)
    assert sum(isinstance(event, WorldInitializedEvent) for event in events) == 1
    assert tuple(
        field_name
        for field_name in WorldInitializedEvent.model_fields
        if field_name not in Event.model_fields
    ) == (
        "battlefield_id",
        "battlefield_name",
        "bounds",
        "width",
        "height",
        "tiles",
        "objects",
        "connectors",
    )
    assert (
        world.battlefield_id,
        world.battlefield_name,
        world.bounds,
        world.width,
        world.height,
    ) == (
        battlefield_id,
        built.definition.title,
        grid.bounds,
        grid.width,
        grid.height,
    )

    tiles_by_position = grid.get_all_tiles()
    assert tuple(WorldTileState.model_fields) == (
        "tile_uuid",
        "position",
        "surface",
        "name",
        "blocks_optics",
        "blocks_propagation",
        "walking_cost",
        "flying_cost",
        "swimming_cost",
        "burrowing_cost",
        "elevation_steps",
        "surface_kind",
        "slope_axis",
        "default_light",
        "resolved_light",
    )
    assert len(world.tiles) == len(tiles_by_position)
    for row in world.tiles:
        tile = tiles_by_position[row.position]
        assert row == WorldTileState(
            tile_uuid=tile.uuid,
            position=tile.position,
            surface=tile.surface,
            name=tile.name,
            blocks_optics=tile.blocks_optics,
            blocks_propagation=tile.blocks_propagation_field,
            walking_cost=int(tile.get_movement_cost(MovementMode.WALKING)),
            flying_cost=int(tile.get_movement_cost(MovementMode.FLYING)),
            swimming_cost=int(tile.get_movement_cost(MovementMode.SWIMMING)),
            burrowing_cost=int(tile.get_movement_cost(MovementMode.BURROWING)),
            elevation_steps=tile.height,
            surface_kind=tile.elevation_surface_kind,
            slope_axis=tile.slope_axis,
            default_light=tile.default_light,
            resolved_light=tile.default_light,
        )

    placements = grid.iter_object_placements()
    assert tuple(WorldObjectState.model_fields) == (
        "placement",
        "item",
        "contained_items",
    )
    assert len(world.objects) == len(placements)
    objects_by_uuid = {row.placement.object_uuid: row for row in world.objects}
    for placement in placements:
        item = BaseBlock.get(placement.object_uuid)
        assert isinstance(item, BaseItem)
        item_state = item.to_item_presentation_state()
        if isinstance(item, WallTorch):
            item_state = item_state.model_copy(update={"is_lit": False})
        storage = item.get_storage_block()
        contained_items = (
            tuple(
                child.to_item_presentation_state()
                for child in sorted(
                    storage.items.values(),
                    key=lambda child: str(child.uuid),
                )
            )
            if isinstance(storage, Inventory)
            else ()
        )
        assert objects_by_uuid[item.uuid] == WorldObjectState(
            placement=placement,
            item=item_state,
            contained_items=contained_items,
        )

    connectors_by_uuid = {
        connector.uuid: connector
        for connector in grid.get_all_connectors()
    }
    assert tuple(WorldConnectorState.model_fields) == (
        "connector_uuid",
        "authored_id",
        "kind",
        "endpoints",
        "endpoint_elevations_feet",
        "movement_cost_feet",
        "action_cost_type",
        "action_cost_amount",
        "bidirectional",
        "enabled",
        "provocation_policy",
    )
    assert len(world.connectors) == len(connectors_by_uuid)
    for row in world.connectors:
        connector = connectors_by_uuid[row.connector_uuid]
        assert row == WorldConnectorState(
            connector_uuid=connector.uuid,
            authored_id=connector.authored_id,
            kind=connector.kind,
            endpoints=tuple(
                endpoint.position for endpoint in connector.endpoints
            ),
            endpoint_elevations_feet=tuple(
                endpoint.elevation_feet for endpoint in connector.endpoints
            ),
            movement_cost_feet=connector.movement_cost_feet,
            action_cost_type=connector.action_cost_type,
            action_cost_amount=connector.action_cost_amount,
            bidirectional=connector.bidirectional,
            enabled=connector.enabled,
            provocation_policy=connector.provocation_policy,
        )


def test_cold_elevation_and_connector_values_round_trip_exactly() -> None:
    """The proving world retains support heights and all connector mechanics."""
    reset_engine_runtime()

    build_battlefield("battlefield.elevation_proving_ground")
    world = _events()[0]
    assert isinstance(world, WorldInitializedEvent)

    by_position = {row.position: row for row in world.tiles}
    for position in ((5, 4), (6, 4), (7, 4), (6, 10), (7, 10)):
        tile = get_map().get_tile(*position)
        assert tile is not None
        assert (
            by_position[position].elevation_steps,
            by_position[position].surface_kind,
            by_position[position].slope_axis,
        ) == (
            tile.height,
            tile.elevation_surface_kind,
            tile.slope_axis,
        )
    connectors_by_uuid = {
        connector.uuid: connector
        for connector in get_map().get_all_connectors()
    }
    assert len(world.connectors) == 5
    for row in world.connectors:
        connector = connectors_by_uuid[row.connector_uuid]
        assert row.authored_id == connector.authored_id
        assert row.kind is connector.kind
        assert row.endpoints == tuple(
            endpoint.position for endpoint in connector.endpoints
        )
        assert row.endpoint_elevations_feet == tuple(
            endpoint.elevation_feet for endpoint in connector.endpoints
        )
        assert row.movement_cost_feet == connector.movement_cost_feet
        assert row.action_cost_type is connector.action_cost_type
        assert row.action_cost_amount == connector.action_cost_amount
        assert row.bidirectional is connector.bidirectional
        assert row.enabled is connector.enabled
        assert row.provocation_policy is connector.provocation_policy


def test_entity_birth_is_one_complete_fact_and_precedes_deployment() -> None:
    """Composition snapshots owner state once; Game only adds world presence."""
    reset_engine_runtime(grid_size=(6, 4))
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Composed actor",
        config=EntityConfig(position=(2, 1), faction="heroes"),
    )
    setup_standard_actions(entity)
    entity.health.add_temporary_hit_points(7, uuid4())

    created = entity.compose_entity()

    assert isinstance(created, EntityCreatedEvent)
    assert created.phase is EventPhase.COMPLETION
    assert created.entity_uuid == entity.uuid
    assert created.ability_scores == tuple(
        (ability.name, ability.ability_score.score)
        for ability in entity.ability_scores.abilities_list
    )
    assert created.action_ids == tuple(sorted(
        action.get_semantic_key() for action in entity.registered_actions
    ))
    assert created.armor_class == entity.ac_bonus().normalized_score
    assert created.maximum_hit_points == entity.get_max_hp()
    assert created.current_hit_points == max(0, entity.get_hp())
    assert created.temporary_hit_points == 7
    assert created.items == ()
    assert entity.creation_committed and not entity.is_deployed
    assert sum(
        event.event_type is EventType.ENTITY_CREATED for event in _events()
    ) == 1
    with pytest.raises(RuntimeError, match="already committed"):
        entity.compose_entity()

    game = Game()
    game.deploy_entity(entity, (2, 1))
    events = _events()
    created_index = events.index(created)
    entered_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.SPATIAL_ENTITY_ENTERED
        and event.phase is EventPhase.COMPLETION
    )
    assert created_index < entered_index
    assert game.get_entity(entity.uuid) is entity


def test_rich_entity_birth_matches_all_declared_aggregate_fields() -> None:
    """One real composed character publishes every field without omission."""
    reset_engine_runtime()
    recipe = encounter_recipe("encounter.standard_skeleton_doors")
    recipe_slot = recipe.roster_slots[0]
    member = recipe_slot.roster.members[0]
    assert isinstance(member.source, AuthoredCreatureRosterSource)

    entity = materialize_creature(
        member.source.recipe,
        runtime_entity_uuid=uuid4(),
        display_name="Rich entity birth proof",
        faction=recipe_slot.faction_id,
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(role_id="test.rich_birth"),
        possession_mode=(
            CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        ),
    )
    expected = _expected_entity_created_fields(entity)
    declared_fields = tuple(
        field_name
        for field_name in EntityCreatedEvent.model_fields
        if field_name not in Event.model_fields
    )
    assert tuple(expected) == declared_fields
    assert len(declared_fields) == 64
    assert expected["class_levels"]
    assert expected["feature_ids"]
    assert expected["handler_ids"]
    assert expected["spell_sources"]
    assert expected["known_spell_ids"]
    assert expected["items"]
    assert expected["equipment"]

    created = entity.compose_entity()

    assert {
        field_name: getattr(created, field_name)
        for field_name in declared_fields
    } == expected


def test_failed_birth_validation_discards_the_provisional_aggregate() -> None:
    """A malformed aggregate leaves no entity-owned registry or birth fact."""
    reset_engine_runtime()
    entity = Entity.create(source_entity_uuid=uuid4(), name="Malformed")
    entity.weight = True

    with pytest.raises(ValidationError):
        entity.compose_entity()

    assert Entity.get(entity.uuid) is None
    assert not any(
        block.source_entity_uuid == entity.uuid
        for block in BaseBlock._registry.values()
    )
    assert not any(
        value.source_entity_uuid == entity.uuid
        for value in BaseValue._registry.values()
    )
    assert not any(
        event.event_type is EventType.ENTITY_CREATED for event in _events()
    )


def test_prepared_scenario_uses_one_passed_game_and_required_chronology() -> None:
    """World/dynamics, births, and occupancy form one ordered scenario stream."""
    reset_engine_runtime()
    game = Game()

    assembled = prepare_encounter_recipe(
        encounter_recipe("encounter.standard_skeleton_doors"),
        game=game,
    )
    events = _events()

    world_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.WORLD_INITIALIZED
    )
    world = events[world_index]
    dynamic_indexes = [
        index
        for index, event in enumerate(events)
        if event.event_type in {
            EventType.CONDITION_APPLICATION,
            EventType.EXPOSED_FLAME_IGNITED,
        }
        and event.parent_event == world.uuid
    ]
    created_indexes = [
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.ENTITY_CREATED
    ]
    entered_indexes = [
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.SPATIAL_ENTITY_ENTERED
    ]
    assert world_index == 0
    assert dynamic_indexes
    assert created_indexes
    assert entered_indexes
    assert len(created_indexes) == len(assembled.entities)
    assert world_index < max(dynamic_indexes) < min(created_indexes)
    assert max(created_indexes) < min(entered_indexes)
    assert set(game.entities) == {entity.uuid for entity in assembled.entities}
    assert all(
        entity.creation_committed and entity.is_deployed
        for entity in assembled.entities
    )
    created_by_entity = {
        event.entity_uuid: event
        for event in events
        if isinstance(event, EntityCreatedEvent)
    }
    for entity in assembled.entities:
        created = created_by_entity[entity.uuid]
        assert created.applied_origin_state == entity.character_origin_state
        assert created.class_levels == entity.character_class_levels
        assert created.feature_ids == entity.character_feature_ids
        assert len(created.feature_ids) == len(set(created.feature_ids))
        assert created.action_ids == tuple(sorted(
            action.get_semantic_key()
            for action in entity.registered_actions
        ))
        assert created.resources == tuple(
            (
                name,
                resource.current,
                resource.maximum,
                resource.recharge_type.value,
            )
            for name, resource in sorted(
                entity.action_economy.resources.items(),
            )
        )
        assert created.inventory_item_uuids == tuple(sorted(
            entity.inventory.items,
            key=str,
        ))
        assert {item.item_uuid for item in created.items}.issuperset(
            entity.inventory.items,
        )
    hero = assembled.entities_by_member_address[("roster_1", "hero")]
    hero_birth = created_by_entity[hero.uuid]
    assert hero_birth.applied_origin_state is not None
    base_scores, flexible_bonuses, origin_choices = (
        hero_birth.applied_origin_state
    )
    assert {ability for ability, _score in base_scores} == {
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    }
    assert tuple(amount for _ability, amount in flexible_bonuses) == (2, 1)
    assert origin_choices
    assert all(values for _choice_id, values in origin_choices)
    choice_values = {
        choice_id: values
        for level in hero_birth.class_levels
        for choice_id, values in level[5]
    }
    assert any(
        "quickened_spell" in value
        for values in choice_values.values()
        for value in values
    )
    assert any(
        "twinned_spell" in value
        for values in choice_values.values()
        for value in values
    )
    assert any("quickened_spell" in value for value in hero_birth.feature_ids)
    assert any("twinned_spell" in value for value in hero_birth.feature_ids)


def test_authored_world_rejects_a_vetoed_torch_without_false_light() -> None:
    """A declaration veto leaves cold torch facts and no live light behind."""
    reset_engine_runtime()
    veto = EventHandler(
        source_entity_uuid=uuid4(),
        name="Veto authored WallTorch ignition",
        trigger_conditions=[Trigger(
            event_type=EventType.EXPOSED_FLAME_IGNITED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source_uuid: event.cancel(
            status_message="fixture ignition veto",
        ),
    )
    EventQueue.add_event_handler(veto)
    try:
        with pytest.raises(
            RuntimeError,
            match="authored WallTorch did not publish IGNITE",
        ):
            build_battlefield("battlefield.standard_hazards_closed")
    finally:
        EventQueue.remove_event_handler(veto)

    world = next(
        event for event in _events()
        if isinstance(event, WorldInitializedEvent)
    )
    torch_states = tuple(
        row.item
        for row in world.objects
        if row.item.name == "Wall Torch"
    )
    assert torch_states and all(state.is_lit is False for state in torch_states)
    flame_events = tuple(
        event for event in _events()
        if event.event_type is EventType.EXPOSED_FLAME_IGNITED
    )
    assert flame_events and flame_events[-1].canceled
    assert not any(
        event.phase is EventPhase.COMPLETION
        for event in flame_events
    )
    world_light = {tile.position: tile.resolved_light for tile in world.tiles}
    assert all(
        get_map().get_tile(*row.placement.position).resolved_light_level
        == world_light[row.placement.position]
        for row in world.objects
        if row.item.name == "Wall Torch"
    )


def test_game_rejects_an_uncommitted_entity_without_adopting_it() -> None:
    """Deployment never performs or repairs composition."""
    reset_engine_runtime(grid_size=(3, 3))
    game = Game()
    entity = Entity.create(source_entity_uuid=uuid4(), name="Cold actor")

    with pytest.raises(RuntimeError, match="before creation commits"):
        game.deploy_entity(entity, (1, 1))

    assert game.entities == {}
    assert not entity.is_deployed


def _assert_provisional_scenario_was_discarded(
    entities: list[Entity],
    game: Game,
) -> None:
    """Assert no provisional actor ownership survived failed assembly."""
    assert game.entities == {}
    assert not any(
        event.event_type is EventType.ENTITY_CREATED
        for event in _events()
    )
    for entity in entities:
        entity_uuid = entity.uuid
        assert Entity.get(entity_uuid) is None
        assert entity_uuid not in CREATURE_RUNTIME_BINDINGS.bindings
        assert not any(
            block.source_entity_uuid == entity_uuid
            for block in BaseBlock._registry.values()
        )
        assert not any(
            value.source_entity_uuid == entity_uuid
            for value in BaseValue._registry.values()
        )


def test_scenario_immediate_grant_failure_discards_every_provisional_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed scenario grant leaves no actor, item, or content binding."""
    reset_engine_runtime()
    game = Game()
    entities: list[Entity] = []
    original_materialize = encounter_assembler._materialize_member
    original_apply = encounter_assembler._apply_immediate_setup_effect

    def record_materialized(**kwargs):
        entity = original_materialize(**kwargs)
        entities.append(entity)
        return entity

    failed = False

    def fail_after_first_grant(entity, effect):
        nonlocal failed
        original_apply(entity, effect)
        if not failed:
            failed = True
            raise RuntimeError("injected immediate grant failure")

    monkeypatch.setattr(
        encounter_assembler,
        "_materialize_member",
        record_materialized,
    )
    monkeypatch.setattr(
        encounter_assembler,
        "_apply_immediate_setup_effect",
        fail_after_first_grant,
    )

    with pytest.raises(RuntimeError, match="immediate grant failure"):
        prepare_encounter_recipe(
            encounter_recipe("encounter.standard_skeleton_doors"),
            game=game,
        )

    assert len(entities) > 1
    _assert_provisional_scenario_was_discarded(entities, game)


def test_second_member_prevalidation_failure_publishes_no_partial_births(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All provisional actors validate before the first birth publishes."""
    reset_engine_runtime()
    game = Game()
    entities: list[Entity] = []
    original_materialize = encounter_assembler._materialize_member
    original_validate = Entity.validate_initial_composition

    def record_materialized(**kwargs):
        entity = original_materialize(**kwargs)
        entities.append(entity)
        return entity

    validation_count = 0

    def fail_second_validation(entity):
        nonlocal validation_count
        validation_count += 1
        original_validate(entity)
        if validation_count == 2:
            raise RuntimeError("injected second-member validation failure")

    monkeypatch.setattr(
        encounter_assembler,
        "_materialize_member",
        record_materialized,
    )
    monkeypatch.setattr(
        Entity,
        "validate_initial_composition",
        fail_second_validation,
    )

    with pytest.raises(RuntimeError, match="second-member validation failure"):
        prepare_encounter_recipe(
            encounter_recipe("encounter.standard_skeleton_doors"),
            game=game,
        )

    assert validation_count == 2
    assert len(entities) > 1
    _assert_provisional_scenario_was_discarded(entities, game)

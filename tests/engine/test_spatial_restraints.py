"""Exact source ownership and arbitration for restraining spatial effects."""

from uuid import UUID, uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.conditions import Restrained
from dnd.core.base_conditions import BaseCondition
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.types.abilities import AbilityName
from dnd.core.events.check_events import (
    AbilityCheckEvent,
)
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.world_events import (
    SpatialChangeEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.entities.entity import Entity, EntityConfig
from dnd.content.spatial_effect_recipes import (
    ENTANGLE_FIELD_RECIPE,
    EVARDS_BLACK_TENTACLES_FIELD_RECIPE,
    WEB_SURFACE_RECIPE,
)
from dnd.spells.conjuration import (
    BlackTentaclesRestrained,
    BlackTentaclesZone,
    Entangle,
    EntangleRestrained,
    EntangleZone,
    EvardsBlackTentacles,
    Web,
    WebRestrained,
    WebZone,
)
from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.support import create_test_entity, get_hp


def _reset(width: int = 18, height: int = 18) -> None:
    reset_engine_runtime(grid_size=(width, height))


def _actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    *,
    spell_slots: dict[int, int] | None = None,
    intelligence: int = 10,
) -> Entity:
    return create_test_entity(
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=10),
                constitution=AbilityConfig(ability_score=10),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=10),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(
                spell_slots=spell_slots or {},
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=8,
                        mode="maximums",
                    ),
                ],
            ),
            proficiency_bonus=3,
            spellcasting=SpellcastingConfig(
                spellcasting_ability="intelligence",
            ),
            position=position,
            faction=faction,
        ),
    )


def _penalize_save(entity: Entity, ability_name: AbilityName) -> None:
    save = entity.saving_throws.get_saving_throw(ability_name)
    save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=f"Deterministic {ability_name} save failure",
            value=-100,
        ),
    )


def _root_event(source_uuid: UUID) -> Event:
    event = EventQueue.publish_lifecycle(Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    assert event is not None
    return event


def test_square_area_controllers_use_the_authored_side_length() -> None:
    """10- and 20-foot squares resolve to 2x2 and 4x4 cells exactly."""
    _reset()
    source = _actor("Source", (1, 1), "heroes")

    web = materialize_spatial_condition(
        WEB_SURFACE_RECIPE,
        source.uuid,
        position=(8, 8),
        faction=source.faction,
        condition_type=WebZone,
    )
    entangle = materialize_spatial_condition(
        ENTANGLE_FIELD_RECIPE,
        source.uuid,
        position=(8, 8),
        faction=source.faction,
        condition_type=EntangleZone,
    )
    web.zone_radius_feet = 10

    assert len(web.resolve_area_footprint()) == 4
    assert len(entangle.resolve_area_footprint()) == 16


def test_entangle_uses_raw_strength_escape_and_exact_effect_cleanup() -> None:
    """Entangle owns one source lease, one raw check, and causal cleanup."""
    _reset()
    caster = _actor(
        "Druid",
        (1, 1),
        "heroes",
        spell_slots={1: 1},
        intelligence=18,
    )
    target = _actor("Target", (5, 5), "monsters")
    _penalize_save(target, "strength")
    Entity.materialize_all_navigation(max_distance=90)

    with fixed_dice_faces(1):
        result = Entangle(
            source_entity_uuid=caster.uuid,
            end_position=(5, 5),
            template=False,
        ).apply()

    assert result is not None and not result.canceled
    zone = next(
        candidate
        for candidate in get_map().get_spatial_conditions()
        if candidate.content_ref == ENTANGLE_FIELD_RECIPE.ref
    )
    assert isinstance(zone, EntangleZone)
    assert len(zone.affected_positions) == 16
    membership = next(
        condition
        for condition in target.active_conditions_by_uuid.values()
        if isinstance(condition, EntangleRestrained)
    )
    assert (target.uuid, membership.uuid) in zone.linked_conditions
    assert isinstance(target.active_conditions["Restrained"], Restrained)
    assert target.action_economy.movement.normalized_score == 0
    escape = next(
        action
        for action in target.registered_actions
        if action.name == "Escape Entangle"
    ).instantiate()
    target.ability_scores.strength.modifier_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Deterministic raw Strength check success",
            value=100,
        ),
    )

    with fixed_dice_faces(1):
        escape_result = escape.apply()

    assert escape_result is not None and not escape_result.canceled
    assert membership.uuid not in target.active_conditions_by_uuid
    assert all(
        child_uuid != membership.uuid
        for _, child_uuid in zone.linked_conditions
    )
    assert "Restrained" not in target.active_conditions
    assert target.action_economy.movement.normalized_score == 30
    assert all(
        action.name != "Escape Entangle"
        for action in target.registered_actions
    )
    ability_checks = [
        candidate
        for candidate in EventQueue.get_events_by_type(EventType.ABILITY_CHECK)
        if isinstance(candidate, AbilityCheckEvent)
        and candidate.phase is EventPhase.COMPLETION
    ]
    assert len(ability_checks) == 1
    assert ability_checks[0].ability_name == "strength"
    assert ability_checks[0].dc == membership.check_dc
    assert escape_result.combat_log is not None
    assert escape_result.combat_log.entry_type == CombatLogEntryType.ACTION
    assert any(
        entry.entry_type == CombatLogEntryType.ABILITY_CHECK
        for entry in escape_result.combat_log.sub_entries
    )

    caster.remove_condition("Concentrating")
    assert BaseCondition.get(zone.uuid) is None


def test_web_leaving_footprint_releases_only_its_exact_source() -> None:
    """Leaving Web removes its private lease, public restraint, and action."""
    _reset()
    caster = _actor(
        "Wizard",
        (1, 1),
        "heroes",
        spell_slots={2: 1},
        intelligence=18,
    )
    target = _actor("Target", (2, 2), "monsters")
    _penalize_save(target, "dexterity")
    Entity.materialize_all_navigation(max_distance=90)

    with fixed_dice_faces(1):
        result = Web(
            source_entity_uuid=caster.uuid,
            end_position=(8, 8),
            template=False,
        ).apply()
    assert result is not None and not result.canceled
    zone = next(
        candidate
        for candidate in get_map().get_spatial_conditions()
        if candidate.content_ref == WEB_SURFACE_RECIPE.ref
    )
    assert isinstance(zone, WebZone)

    with fixed_dice_faces(1):
        Entity.update_entity_position(target, (8, 8))
    membership = zone.find_restraint(target)
    assert isinstance(membership, WebRestrained)
    assert "Restrained" in target.active_conditions
    assert any(
        action.name == "Escape Web"
        for action in target.registered_actions
    )

    Entity.update_entity_position(target, (15, 15))
    assert membership.uuid not in target.active_conditions_by_uuid
    assert "Restrained" not in target.active_conditions
    assert all(
        action.name != "Escape Web"
        for action in target.registered_actions
    )


def test_overlapping_restraints_never_downgrade_and_promote_live_sources() -> None:
    """Removing sources preserves the strongest remaining exact lease."""
    _reset()
    caster = _actor("Caster", (1, 1), "heroes", intelligence=18)
    target = _actor("Target", (8, 8), "monsters")
    _penalize_save(target, "strength")
    parent = _root_event(caster.uuid)
    installed: list[EntangleZone] = []

    for dc in (10, 12, 18):
        zone = materialize_spatial_condition(
            ENTANGLE_FIELD_RECIPE,
            caster.uuid,
            position=(8, 8),
            faction=caster.faction,
            condition_type=EntangleZone,
            condition_fields={
                "spell_dc": dc,
            },
        )
        with fixed_dice_faces(1):
            zone.activate(parent_event=parent)
        installed.append(zone)

    active = target.active_conditions["Restrained"]
    assert isinstance(active, Restrained)
    assert active.potency_rank == (18, 0)
    assert len(target.get_condition_application_leases("Restrained")) == 3

    weak_zone = installed[0]
    assert weak_zone.remove_restraint(target, parent_event=parent)
    assert BaseCondition.get(weak_zone.uuid) is weak_zone
    active = target.active_conditions["Restrained"]
    assert isinstance(active, Restrained)
    assert active.potency_rank == (18, 0)
    assert len(target.get_condition_application_leases("Restrained")) == 2

    strong_zone = installed[2]
    assert strong_zone.remove_restraint(target, parent_event=parent)
    promoted = target.active_conditions["Restrained"]
    assert isinstance(promoted, Restrained)
    assert promoted.potency_rank == (12, 0)
    assert len(target.get_condition_application_leases("Restrained")) == 1

    middle_zone = installed[1]
    assert middle_zone.remove_restraint(target, parent_event=parent)
    assert "Restrained" not in target.active_conditions
    assert target.get_condition_application_leases("Restrained") == ()


def test_black_tentacles_share_one_entry_turn_fence_and_escape_source() -> None:
    """Entry and turn-start share one per-effect/target/turn admission fence."""
    _reset()
    caster = _actor(
        "Wizard",
        (1, 1),
        "heroes",
        spell_slots={4: 1},
        intelligence=18,
    )
    target = _actor("Target", (8, 8), "monsters")
    _penalize_save(target, "dexterity")
    Entity.materialize_all_navigation(max_distance=90)

    result = EvardsBlackTentacles(
        source_entity_uuid=caster.uuid,
        end_position=(8, 8),
        template=False,
    ).apply()
    assert result is not None and not result.canceled
    zone = next(
        candidate
        for candidate in get_map().get_spatial_conditions()
        if candidate.content_ref == EVARDS_BLACK_TENTACLES_FIELD_RECIPE.ref
    )
    assert isinstance(zone, BlackTentaclesZone)
    assert len(zone.affected_positions) == 16
    assert zone.find_restraint(target) is None
    hp_before = get_hp(target)
    turn_execution_id = uuid4()
    parent = EventQueue.publish_lifecycle(Event(
        source_entity_uuid=target.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
        turn_execution_id=turn_execution_id,
    ))
    assert parent is not None

    with fixed_dice_faces(1, 1, 1, 1):
        entered = SpatialChangeEvent.entity_entered(
            target.position,
            target.uuid,
            source_entity_uuid=target.uuid,
            parent_event=parent.uuid,
        )
        EventQueue.publish_lifecycle(entered)

    membership = zone.find_restraint(target)
    assert isinstance(membership, BlackTentaclesRestrained)
    hp_after_entry = get_hp(target)
    first_damage = hp_before - hp_after_entry
    assert first_damage > 0
    assert {
        action.name
        for action in target.registered_actions
        if action.name is not None
        and action.name.startswith("Escape Black Tentacles")
    } == {
        "Escape Black Tentacles (Strength)",
        "Escape Black Tentacles (Dexterity)",
    }

    same_turn_start = EventQueue.publish_lifecycle(Event(
        source_entity_uuid=target.uuid,
        event_type=EventType.TURN_START,
        phase=EventPhase.DECLARATION,
        use_register=False,
        turn_execution_id=turn_execution_id,
    ))
    assert same_turn_start is not None
    assert get_hp(target) == hp_after_entry

    with fixed_dice_faces(1, 1, 1):
        next_turn_start = EventQueue.publish_lifecycle(Event(
            source_entity_uuid=target.uuid,
            event_type=EventType.TURN_START,
            phase=EventPhase.DECLARATION,
            use_register=False,
            turn_execution_id=uuid4(),
        ))
    assert next_turn_start is not None
    assert hp_after_entry - get_hp(target) == first_damage

    target.ability_scores.dexterity.modifier_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Deterministic raw Dexterity check success",
            value=100,
        ),
    )
    escape = next(
        action
        for action in target.registered_actions
        if action.name == "Escape Black Tentacles (Dexterity)"
    ).instantiate()
    with fixed_dice_faces(1):
        escape_result = escape.apply()
    assert escape_result is not None and not escape_result.canceled
    assert zone.find_restraint(target) is None
    assert "Restrained" not in target.active_conditions

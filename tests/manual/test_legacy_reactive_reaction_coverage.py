"""Active coverage ledger for displaced senses, invisibility, and reaction cases.

The historical scripts mixed print-only checks, stochastic assertions, and
superseded callback internals.  This file maps every named case to a maintained
selector and restores the missing behavior through current event phases.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

import pytest

from dnd.actions import Attack, Move
from dnd.actions_functional import (
    execute_use_action,
    setup_standard_actions,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_door
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import GreaterInvisibilityEffect
from dnd.core.base_actions import ActionEvent, AvailableTarget
from dnd.core.condition_types import DurationType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SensoryUpdateEvent,
    StepMovementEvent,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.consumables import build_greater_invisibility_potion
from dnd.items.spell_items import build_invisibility_scroll
from tests.manual.reactive_fixture_support import (
    DodgeRollFeature,
    Intercepting,
    PrepareIntercept,
)
from dnd.monsters.bestiary import (
    create_caster as _create_caster,
    create_skeleton as _create_skeleton,
)
from dnd.reactions import add_opportunity_attack_handler
from dnd.spells.illusion import GreaterInvisibility, Invisibility
from dnd.types.world import CardinalDirection
from tests.engine.support import (
    force_attack_hit,
    force_attack_miss,
    remove_attack_modifier,
    reset_combat_state,
)


CoverageStatus = Literal["active", "strengthened", "retired", "stale", "unresolved"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived case's current disposition."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_legacy_reactive_reaction_coverage.py"
SENSES_BOOK = "tests/engine/test_senses_light_stealth.py"
GRID_BOOK = "tests/engine/test_grid_pathfinding.py"
MOVEMENT_BOOK = "tests/engine/test_manual_11_grid_tiles_terrain_movement.py"
PERFORMANCE_FILE = "tests/manual/test_43_ai_runtime_performance.py"

SENSES_REGISTRATION_SELECTOR = (
    f"{THIS_FILE}::test_indexed_sensory_system_updates_registered_observer_once"
)
SENSES_TRANSITION_SELECTOR = (
    f"{THIS_FILE}::test_reactive_visibility_adds_and_removes_for_multiple_observers"
)
STEP_CANCEL_SELECTOR = (
    f"{THIS_FILE}::test_effect_phase_step_handler_cancels_before_position_and_cost_commit"
)
STEP_BUDGET_SELECTOR = (
    f"{THIS_FILE}::test_effect_phase_speed_reduction_limits_the_remaining_path"
)
INVISIBILITY_OA_SELECTOR = (
    f"{THIS_FILE}::test_invisibility_reveals_on_opportunity_attack_for_spell_and_scroll"
)
INVISIBILITY_ATTACK_SELECTOR = (
    f"{THIS_FILE}::test_regular_attack_uses_the_same_invisibility_reveal_surface"
)
GREATER_OA_SELECTOR = (
    f"{THIS_FILE}::test_greater_invisibility_checks_on_opportunity_attack_for_spell_and_potion"
)
GREATER_ATTACK_SELECTOR = (
    f"{THIS_FILE}::test_regular_attack_runs_greater_invisibility_stealth_check"
)
CONCENTRATION_SELECTOR = (
    f"{THIS_FILE}::test_invisibility_follows_deterministic_concentration_damage_outcomes"
)
PREPARE_SELECTOR = f"{THIS_FILE}::test_prepare_intercept_prepays_action_and_distance"
INTERCEPT_SELECTOR = (
    f"{THIS_FILE}::test_intercept_blocks_the_triggering_step_and_charges_only_committed_steps"
)
INTERCEPT_FILTER_SELECTOR = (
    f"{THIS_FILE}::test_intercept_ignores_allies_and_cannot_fire_twice_on_one_reaction"
)
INTERCEPT_OA_SELECTOR = (
    f"{THIS_FILE}::test_intercept_and_opportunity_attack_share_an_explicit_two_reaction_budget"
)
INTERCEPT_DOOR_SELECTOR = (
    f"{THIS_FILE}::test_closed_door_invalidates_prepared_intercept_path_at_trigger_time"
)
INTERCEPT_CLEANUP_SELECTOR = (
    f"{THIS_FILE}::test_removed_intercept_condition_removes_its_handler"
)
DODGE_SELECTOR = f"{THIS_FILE}::test_dodge_roll_moves_and_consumes_one_reaction"
DODGE_OBSTRUCTION_SELECTOR = (
    f"{THIS_FILE}::test_dodge_roll_handles_fully_blocked_and_partial_retreats"
)
DODGE_DOOR_SELECTOR = (
    f"{THIS_FILE}::test_open_door_is_authoritative_when_dodge_roll_triggers"
)
DODGE_CLEANUP_SELECTOR = (
    f"{THIS_FILE}::test_removed_dodge_roll_condition_removes_its_handler"
)


REACTIVE_SENSES_LEDGER: dict[str, LegacyCoverage] = {
    "test_reactive_senses_on_movement": LegacyCoverage(
        "strengthened",
        f"{SENSES_BOOK}::test_eb_12_022_paired_movement_emits_one_subjective_transition",
        "One paired move now asserts the exact moved-entity sensory delta.",
    ),
    "test_senses_callback_registered": LegacyCoverage(
        "stale",
        SENSES_REGISTRATION_SELECTOR,
        "Per-entity EventQueue callbacks were replaced by one indexed sensory system.",
    ),
    "test_visible_entities_update_on_enter": LegacyCoverage(
        "active",
        SENSES_TRANSITION_SELECTOR,
        "Restored with hard assertions for observer-local addition payloads.",
    ),
    "test_visible_entities_update_on_leave": LegacyCoverage(
        "active",
        SENSES_TRANSITION_SELECTOR,
        "Restored with hard assertions for observer-local removal payloads.",
    ),
    "test_multiple_observers_react_to_movement": LegacyCoverage(
        "active",
        SENSES_TRANSITION_SELECTOR,
        "Restored against two independently indexed observers.",
    ),
    "test_no_reaction_to_unobserved_areas": LegacyCoverage(
        "strengthened",
        f"{SENSES_BOOK}::test_eb_12_020_distant_movement_does_not_dirty_unrelated_observer_paths",
        "Maintained test proves no sensory event and no path invalidation.",
    ),
    "test_step_movement_handler_fires": LegacyCoverage(
        "strengthened",
        f"{MOVEMENT_BOOK}::test_step_handlers_see_voluntary_movement_not_forced_movement",
        "Maintained test asserts exact ordered steps and excludes forced movement.",
    ),
    "test_movement_can_be_blocked_by_handler": LegacyCoverage(
        "active",
        STEP_CANCEL_SELECTOR,
        "Restored with effect/cancel/commit and movement-cost assertions.",
    ),
    "test_handler_reduces_movement_mid_path": LegacyCoverage(
        "active",
        STEP_BUDGET_SELECTOR,
        "Restored with an exact final cell and exhausted dynamic movement budget.",
    ),
    "test_death_updates_paths": LegacyCoverage(
        "strengthened",
        f"{GRID_BOOK}::test_eb_11_015_dead_entities_become_non_blocking_for_paths",
        "Maintained lifecycle test asserts death, path dirtiness, and recomputation.",
    ),
    "test_get_available_actions_with_difficult_terrain": LegacyCoverage(
        "strengthened",
        f"{PERFORMANCE_FILE}::test_weighted_move_discovery_uses_cached_senses_path_costs",
        "Maintained discovery test binds weighted Dijkstra costs to movement rows.",
    ),
}


INVISIBILITY_LEDGER: dict[str, LegacyCoverage] = {
    "test_1_oa_miss_breaks_invisibility_spell": LegacyCoverage(
        "active", INVISIBILITY_OA_SELECTOR, "Restored as a deterministic OA miss."
    ),
    "test_2_oa_hit_breaks_invisibility_spell": LegacyCoverage(
        "active", INVISIBILITY_OA_SELECTOR, "Restored as a deterministic OA hit."
    ),
    "test_3_oa_miss_breaks_invisibility_scroll": LegacyCoverage(
        "active",
        INVISIBILITY_OA_SELECTOR,
        "Restored through the canonical item discovery key.",
    ),
    "test_4_oa_hit_breaks_invisibility_scroll": LegacyCoverage(
        "active",
        INVISIBILITY_OA_SELECTOR,
        "Restored through the canonical item discovery key.",
    ),
    "test_5_regular_attack_breaks_invisibility": LegacyCoverage(
        "active",
        INVISIBILITY_ATTACK_SELECTOR,
        "Restored through a real Attack lifecycle rather than a synthetic action.",
    ),
    "test_6_oa_miss_triggers_stealth_check_spell": LegacyCoverage(
        "active", GREATER_OA_SELECTOR, "Restored with a fixed successful check."
    ),
    "test_7_oa_hit_triggers_stealth_check_spell": LegacyCoverage(
        "active", GREATER_OA_SELECTOR, "Restored with a fixed successful check."
    ),
    "test_8_oa_miss_triggers_stealth_check_potion": LegacyCoverage(
        "active",
        GREATER_OA_SELECTOR,
        "Restored through the potion-owned action lifecycle.",
    ),
    "test_9_oa_hit_triggers_stealth_check_potion": LegacyCoverage(
        "active",
        GREATER_OA_SELECTOR,
        "Restored through the potion-owned action lifecycle.",
    ),
    "test_10_regular_attack_triggers_stealth_check": LegacyCoverage(
        "active",
        GREATER_ATTACK_SELECTOR,
        "Restored through a real Attack lifecycle.",
    ),
    "test_11_damage_does_not_break_invisibility": LegacyCoverage(
        "strengthened",
        CONCENTRATION_SELECTOR,
        "The old conditional assertion passed on either outcome; replacement fixes the save.",
    ),
    "test_12_concentration_failure_breaks_invisibility": LegacyCoverage(
        "strengthened",
        CONCENTRATION_SELECTOR,
        "The old lethal branch declared conditions moot; replacement proves linked cleanup.",
    ),
}


INTERCEPT_DODGE_LEDGER: dict[str, LegacyCoverage] = {
    "test_intercept_basic": LegacyCoverage(
        "active", INTERCEPT_SELECTOR, "Restored exact charge and blocked-step behavior."
    ),
    "test_intercept_costs": LegacyCoverage(
        "active", PREPARE_SELECTOR, "Restored exact action and movement prepayment."
    ),
    "test_intercept_reaction_consumed": LegacyCoverage(
        "active", INTERCEPT_FILTER_SELECTOR, "Restored one-reaction limit."
    ),
    "test_intercept_ally_not_intercepted": LegacyCoverage(
        "active", INTERCEPT_FILTER_SELECTOR, "Restored ally filtering."
    ),
    "test_intercept_blocks_enemy_movement_cost_and_no_oa": LegacyCoverage(
        "active",
        INTERCEPT_SELECTOR,
        "Restored committed-step cost and exhausted-reaction behavior.",
    ),
    "test_intercept_with_2_reactions_also_oa": LegacyCoverage(
        "active", INTERCEPT_OA_SELECTOR, "Restored the explicit two-reaction budget."
    ),
    "test_dodge_roll_basic": LegacyCoverage(
        "active", DODGE_SELECTOR, "Restored exact two-cell retreat."
    ),
    "test_dodge_roll_costs_reaction": LegacyCoverage(
        "active", DODGE_SELECTOR, "Restored exact reaction cost."
    ),
    "test_dodge_roll_blocked": LegacyCoverage(
        "active", DODGE_OBSTRUCTION_SELECTOR, "Restored blocked no-cost behavior."
    ),
    "test_dodge_roll_partial": LegacyCoverage(
        "active", DODGE_OBSTRUCTION_SELECTOR, "Restored partial retreat and cost."
    ),
    "test_intercept_path_blocked_by_door": LegacyCoverage(
        "active",
        INTERCEPT_DOOR_SELECTOR,
        "Restored trigger-time path authority after a door mutation.",
    ),
    "test_dodge_roll_enabled_by_door_open": LegacyCoverage(
        "active",
        DODGE_DOOR_SELECTOR,
        "Restored trigger-time path authority after a door mutation.",
    ),
    "test_intercept_condition_removed": LegacyCoverage(
        "active", INTERCEPT_CLEANUP_SELECTOR, "Restored owned-handler cleanup."
    ),
    "test_dodge_roll_condition_removed": LegacyCoverage(
        "active", DODGE_CLEANUP_SELECTOR, "Restored owned-handler cleanup."
    ),
}


def reset_arena(width: int = 15, height: int = 5) -> None:
    """Reset engine-global state and create one open arena."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, width, height)


def create_caster(*args, **kwargs) -> Entity:
    """Create and deploy one caster in the prepared arena."""
    entity = _create_caster(*args, **kwargs)
    entity.compose_entity()
    Game().deploy_entity(entity, entity.position)
    return entity


def create_skeleton(*args, **kwargs) -> Entity:
    """Create and deploy one skeleton in the prepared arena."""
    entity = _create_skeleton(*args, **kwargs)
    entity.compose_entity()
    Game().deploy_entity(entity, entity.position)
    return entity


def create_melee_fighter(
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    """Create a durable armed actor for reaction tests."""
    source_uuid = uuid4()
    actor = Entity.create(
        source_entity_uuid=source_uuid,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=16),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=14),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=5,
                        mode="average",
                    )
                ],
            ),
            equipment=EquipmentConfig(),
            action_economy=ActionEconomyConfig(),
            proficiency_bonus=3,
            position=position,
            faction=faction,
        ),
    )
    setup_standard_actions(actor)
    actor.install_initial_items((
        (
            build_authored_item("weapon.shortsword", actor.uuid),
            WeaponSlot.MELEE_MAIN,
        ),
    ))
    actor.compose_entity()
    Game().deploy_entity(actor, position)
    return actor


def arm_intercept(interceptor: Entity, destination: tuple[int, int]) -> None:
    """Apply the one-round intercept condition directly."""
    condition = Intercepting(
        source_entity_uuid=interceptor.uuid,
        target_entity_uuid=interceptor.uuid,
        charge_destination=destination,
    )
    condition.duration.duration_type = DurationType.ROUNDS
    condition.duration.duration = 1
    interceptor.add_condition(condition)


def execute_attack(attacker: Entity, target: Entity) -> Event | None:
    """Execute one main-hand melee attack."""
    return Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()


def apply_invisibility_origin(actor: Entity, origin: str) -> None:
    """Apply normal Invisibility from the selected canonical source."""
    if origin == "spell":
        result = Invisibility(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            cast_at_level=2,
        ).apply()
    else:
        scroll = build_invisibility_scroll(actor.uuid, cast_level=2)
        actor.loot_item(scroll)
        template = scroll.get_use_actions(actor.uuid)[0]
        result = execute_use_action(
            actor,
            scroll.uuid,
            template.get_discovery_template_name(),
            AvailableTarget(
                index=0,
                target_uuid=actor.uuid,
                target_name=actor.name,
            ),
        )
    assert result is not None and not result.canceled
    assert actor.is_invisible


def apply_greater_invisibility_origin(actor: Entity, origin: str) -> None:
    """Apply Greater Invisibility from the selected canonical source."""
    if origin == "spell":
        result = GreaterInvisibility(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            cast_at_level=4,
        ).apply()
    else:
        potion = build_greater_invisibility_potion(actor.uuid)
        actor.loot_item(potion)
        stored_potion = next(
            item
            for item in actor.inventory.items.values()
            if item.stack_id == potion.stack_id
        )
        result = execute_use_action(
            actor,
            stored_potion.uuid,
            "Drink Greater Invisibility Potion",
        )
    assert result is not None and not result.canceled
    condition = actor.active_conditions.get("Invisible")
    assert isinstance(condition, GreaterInvisibilityEffect)


def setup_oa_pair() -> tuple[Entity, Entity]:
    """Create adjacent hostile actors with OA enabled on the first."""
    reset_arena(width=8, height=8)
    reactor = create_caster(
        name="Invisible Reactor",
        position=(2, 2),
        faction="heroes",
        level=7,
    )
    setup_standard_actions(reactor)
    add_opportunity_attack_handler(reactor)
    mover = create_skeleton(
        name="Provoking Mover",
        position=(2, 3),
        faction="monsters",
    )
    setup_standard_actions(mover)
    Entity.update_all_entities_senses(max_distance=8)
    return reactor, mover


def test_legacy_reactive_reaction_manifests_account_for_all_37_cases() -> None:
    """Every named archived case has one reviewed disposition and selector."""
    assert len(REACTIVE_SENSES_LEDGER) == 11
    assert len(INVISIBILITY_LEDGER) == 12
    assert len(INTERCEPT_DODGE_LEDGER) == 14
    combined = {
        **REACTIVE_SENSES_LEDGER,
        **INVISIBILITY_LEDGER,
        **INTERCEPT_DODGE_LEDGER,
    }
    assert len(combined) == 37
    assert not any(row.status == "unresolved" for row in combined.values())
    for case, row in combined.items():
        assert case.startswith("test_")
        assert row.selector.startswith("tests/") and "::test_" in row.selector
        assert row.rationale


def test_indexed_sensory_system_updates_registered_observer_once() -> None:
    """A deployed observer receives one typed delta for one visible arrival."""
    reset_arena(width=20, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0))
    mover = create_skeleton(name="Mover", position=(15, 0))
    observer.update_entity_senses(max_distance=4)
    assert mover.uuid not in observer.senses.entities
    cursor = EventQueue.event_cursor()

    Entity.update_entity_position(mover, (3, 0))

    updates = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.phase == EventPhase.COMPLETION
        and event.observer_uuid == observer.uuid
        and mover.uuid in event.entity_contacts_changed
    ]
    assert len(updates) == 1
    assert updates[0].entity_contacts_changed[mover.uuid].position == (3, 0)


def test_reactive_visibility_adds_and_removes_for_multiple_observers() -> None:
    """One spatial move publishes observer-local additions and later removals."""
    reset_arena(width=20, height=3)
    first = create_skeleton(name="First Observer", position=(0, 0))
    second = create_skeleton(name="Second Observer", position=(0, 2))
    mover = create_skeleton(name="Mover", position=(15, 1))
    first.update_entity_senses(max_distance=4)
    second.update_entity_senses(max_distance=4)

    assert mover.uuid not in first.senses.entities
    assert mover.uuid not in second.senses.entities
    cursor = EventQueue.event_cursor()

    Entity.update_entity_position(mover, (3, 1))

    for observer in (first, second):
        assert observer.senses.entities[mover.uuid].position == (3, 1)
        additions = [
            event
            for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SensoryUpdateEvent)
            and event.phase == EventPhase.COMPLETION
            and event.observer_uuid == observer.uuid
            and mover.uuid in event.entity_contacts_changed
        ]
        assert len(additions) == 1
        assert additions[0].entity_contacts_changed[mover.uuid].position == (3, 1)

    cursor = EventQueue.event_cursor()
    Entity.update_entity_position(mover, (15, 1))

    for observer in (first, second):
        assert mover.uuid not in observer.senses.entities
        removals = [
            event
            for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SensoryUpdateEvent)
            and event.phase == EventPhase.COMPLETION
            and event.observer_uuid == observer.uuid
            and mover.uuid in event.entity_contacts_removed
        ]
        assert len(removals) == 1


def test_effect_phase_step_handler_cancels_before_position_and_cost_commit() -> None:
    """Canceling the attempted step leaves actor and movement at the prior cell."""
    reset_arena(width=10, height=1)
    mover = create_skeleton(name="Mover", position=(0, 0), faction="heroes")
    canceled_steps: list[StepMovementEvent] = []

    def block_trap(
        event: Event,
        _handler_source_uuid: UUID,
    ) -> Event:
        assert isinstance(event, StepMovementEvent)
        if event.to_position != (3, 0):
            return event
        canceled = event.cancel(status_message="Blocked by trap")
        canceled_steps.append(canceled)
        return canceled

    mover.add_event_handler(
        EventHandler(
            name="Trap",
            source_entity_uuid=mover.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.STEP_MOVEMENT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=block_trap,
        )
    )
    Entity.update_all_entities_senses(max_distance=10)
    movement_before = mover.action_economy.movement.normalized_score

    result = Move(source_entity_uuid=mover.uuid, end_position=(5, 0)).apply()

    assert result is not None and not result.canceled
    assert mover.position == (2, 0)
    assert result.end_position == (2, 0)
    assert "partial" in (result.status_message or "").lower()
    assert mover.action_economy.movement.normalized_score == movement_before - 10
    assert len(canceled_steps) == 1
    assert canceled_steps[0].from_position == (2, 0)
    assert canceled_steps[0].to_position == (3, 0)


def test_effect_phase_speed_reduction_limits_the_remaining_path() -> None:
    """A speed change during a committed step constrains subsequent steps."""
    reset_arena(width=10, height=1)
    mover = create_skeleton(name="Mover", position=(0, 0), faction="heroes")
    mover.action_economy.movement.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=mover.uuid,
            name="Initial Speed Boost",
            value=20,
        )
    )
    applied = False

    def slow_on_entry(
        event: Event,
        handler_source_uuid: UUID,
    ) -> Event:
        nonlocal applied
        assert isinstance(event, StepMovementEvent)
        if event.to_position == (3, 0) and not applied:
            mover.action_economy.movement.self_static.add_value_modifier(
                NumericalModifier.create(
                    source_entity_uuid=handler_source_uuid,
                    name="Mid-path Slow",
                    value=-20,
                )
            )
            applied = True
        return event

    mover.add_event_handler(
        EventHandler(
            name="Slow Zone",
            source_entity_uuid=mover.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.STEP_MOVEMENT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=slow_on_entry,
        )
    )
    Entity.update_all_entities_senses(max_distance=10)

    result = Move(source_entity_uuid=mover.uuid, end_position=(7, 0)).apply()

    assert result is not None and not result.canceled
    assert applied
    assert mover.position == (6, 0)
    assert result.end_position == (6, 0)
    assert "partial" in (result.status_message or "").lower()
    assert mover.action_economy.movement.normalized_score == 0


@pytest.mark.parametrize(
    ("origin", "outcome"),
    (
        ("spell", "miss"),
        ("spell", "hit"),
        ("scroll", "miss"),
        ("scroll", "hit"),
    ),
)
def test_invisibility_reveals_on_opportunity_attack_for_spell_and_scroll(
    origin: str,
    outcome: str,
) -> None:
    """An OA is an attack reveal regardless of result or item/spell origin."""
    reactor, mover = setup_oa_pair()
    apply_invisibility_origin(reactor, origin)
    modifier_uuid = (
        force_attack_hit(reactor)
        if outcome == "hit"
        else force_attack_miss(reactor)
    )

    try:
        Move(source_entity_uuid=mover.uuid, end_position=(2, 7)).apply()
    finally:
        remove_attack_modifier(reactor, modifier_uuid)

    assert reactor.action_economy.reactions.normalized_score == 0
    assert "Invisible" not in reactor.active_conditions
    assert reactor.is_invisible is False


def test_regular_attack_uses_the_same_invisibility_reveal_surface() -> None:
    """A normal Attack lifecycle removes spell Invisibility on hit."""
    attacker, target = setup_oa_pair()
    apply_invisibility_origin(attacker, "spell")
    attacker.action_economy.reset_all_costs()
    modifier_uuid = force_attack_hit(attacker)

    try:
        with fixed_dice_faces(10, 1, 4):
            result = execute_attack(attacker, target)
    finally:
        remove_attack_modifier(attacker, modifier_uuid)

    assert result is not None and not result.canceled
    assert "Invisible" not in attacker.active_conditions
    assert attacker.is_invisible is False


@pytest.mark.parametrize(
    ("origin", "outcome", "faces"),
    (
        ("spell", "miss", (10, 1, 20)),
        ("spell", "hit", (10, 1, 4, 20)),
        ("potion", "miss", (10, 1, 20)),
        ("potion", "hit", (10, 1, 4, 20)),
    ),
)
def test_greater_invisibility_checks_on_opportunity_attack_for_spell_and_potion(
    origin: str,
    outcome: str,
    faces: tuple[int, ...],
) -> None:
    """An OA runs one deterministic Greater Invisibility check on hit or miss."""
    reactor, mover = setup_oa_pair()
    apply_greater_invisibility_origin(reactor, origin)
    before = reactor.active_conditions["Invisible"]
    assert isinstance(before, GreaterInvisibilityEffect)
    modifier_uuid = (
        force_attack_hit(reactor)
        if outcome == "hit"
        else force_attack_miss(reactor)
    )

    try:
        with fixed_dice_faces(*faces):
            Move(source_entity_uuid=mover.uuid, end_position=(2, 7)).apply()
    finally:
        remove_attack_modifier(reactor, modifier_uuid)

    after = reactor.active_conditions.get("Invisible")
    assert after is before
    assert isinstance(after, GreaterInvisibilityEffect)
    assert after.check_count == 1
    assert reactor.is_invisible
    assert reactor.action_economy.reactions.normalized_score == 0


def test_regular_attack_runs_greater_invisibility_stealth_check() -> None:
    """A normal attack uses the same Greater Invisibility effect-phase handler."""
    attacker, target = setup_oa_pair()
    apply_greater_invisibility_origin(attacker, "spell")
    attacker.action_economy.reset_all_costs()
    modifier_uuid = force_attack_hit(attacker)

    try:
        with fixed_dice_faces(10, 1, 4, 20):
            result = execute_attack(attacker, target)
    finally:
        remove_attack_modifier(attacker, modifier_uuid)

    condition = attacker.active_conditions.get("Invisible")
    assert result is not None and not result.canceled
    assert isinstance(condition, GreaterInvisibilityEffect)
    assert condition.check_count == 1
    assert attacker.is_invisible


def test_invisibility_follows_deterministic_concentration_damage_outcomes() -> None:
    """A held save preserves invisibility; a failed save removes the linked effect."""
    reactor, attacker = setup_oa_pair()
    apply_invisibility_origin(reactor, "spell")

    with fixed_dice_faces(20):
        reactor.receive_damage(1, DamageType.FIRE, attacker.uuid)

    assert "Concentrating" in reactor.active_conditions
    assert "Invisible" in reactor.active_conditions
    assert reactor.is_invisible

    with fixed_dice_faces(1):
        reactor.receive_damage(1, DamageType.FIRE, attacker.uuid)

    assert "Concentrating" not in reactor.active_conditions
    assert "Invisible" not in reactor.active_conditions
    assert reactor.is_invisible is False


def test_prepare_intercept_prepays_action_and_distance() -> None:
    """Preparing intercept pays one action and the declared charge distance."""
    reset_arena()
    fighter = create_melee_fighter("Fighter", (2, 2), "heroes")
    Entity.update_all_entities_senses(max_distance=20)
    action_before = fighter.action_economy.actions.normalized_score
    movement_before = fighter.action_economy.movement.normalized_score
    prepare = PrepareIntercept(source_entity_uuid=fighter.uuid)
    prepare.set_target_position((5, 2))

    result = prepare.apply()

    assert isinstance(result, ActionEvent) and not result.canceled
    assert [
        (cost.cost_type, cost.cost)
        for cost in result.costs
    ] == [
        ("actions", 1),
        ("movement", 15),
    ]
    assert "Intercepting" in fighter.active_conditions
    assert fighter.action_economy.actions.normalized_score == action_before - 1
    assert fighter.action_economy.movement.normalized_score == movement_before - 15


def test_prepare_intercept_rejects_unaffordable_distance_before_effects() -> None:
    """The typed movement cost blocks preparation without spending the action."""
    reset_arena()
    fighter = create_melee_fighter("Tired Fighter", (2, 2), "heroes")
    Entity.update_all_entities_senses(max_distance=20)
    fighter.action_economy.movement.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            name="Only ten feet remain",
            value=-20,
        )
    )
    action_before = fighter.action_economy.actions.normalized_score
    prepare = PrepareIntercept(source_entity_uuid=fighter.uuid)
    prepare.set_target_position((5, 2))

    result = prepare.apply()

    assert result is None
    assert "Intercepting" not in fighter.active_conditions
    assert fighter.action_economy.actions.normalized_score == action_before
    assert fighter.action_economy.movement.normalized_score == 10


def test_intercept_blocks_the_triggering_step_and_charges_only_committed_steps() -> None:
    """Intercept occupies the watched cell before the enemy can commit that step."""
    reset_arena()
    interceptor = create_melee_fighter("Interceptor", (2, 2), "heroes")
    enemy = create_melee_fighter("Enemy", (8, 2), "monsters")
    arm_intercept(interceptor, (5, 2))
    Entity.update_all_entities_senses(max_distance=20)
    movement_before = enemy.action_economy.movement.normalized_score

    result = Move(source_entity_uuid=enemy.uuid, end_position=(3, 2)).apply()

    assert result is not None and not result.canceled
    assert interceptor.position == (5, 2)
    assert enemy.position == (6, 2)
    assert result.end_position == (6, 2)
    assert enemy.action_economy.movement.normalized_score == movement_before - 10
    assert interceptor.action_economy.reactions.normalized_score == 0
    assert "Intercepting" not in interceptor.active_conditions

    hp_after_intercept = enemy.get_hp()
    Move(source_entity_uuid=enemy.uuid, end_position=(7, 2)).apply()
    assert enemy.position == (7, 2)
    assert enemy.get_hp() == hp_after_intercept


def test_intercept_ignores_allies_and_cannot_fire_twice_on_one_reaction() -> None:
    """Ally movement is ignored; one enemy trigger exhausts the reaction."""
    reset_arena()
    interceptor = create_melee_fighter("Interceptor", (2, 2), "heroes")
    ally = create_melee_fighter("Ally", (8, 2), "heroes")
    arm_intercept(interceptor, (5, 2))
    Entity.update_all_entities_senses(max_distance=20)

    Move(source_entity_uuid=ally.uuid, end_position=(3, 2)).apply()

    assert interceptor.position == (2, 2)
    assert interceptor.action_economy.reactions.normalized_score == 1
    assert "Intercepting" in interceptor.active_conditions

    reset_arena()
    interceptor = create_melee_fighter("Interceptor", (2, 2), "heroes")
    first_enemy = create_melee_fighter("First Enemy", (8, 2), "monsters")
    second_enemy = create_melee_fighter("Second Enemy", (10, 2), "monsters")
    arm_intercept(interceptor, (5, 2))
    Entity.update_all_entities_senses(max_distance=20)

    Move(source_entity_uuid=first_enemy.uuid, end_position=(3, 2)).apply()
    assert interceptor.position == (5, 2)
    assert interceptor.action_economy.reactions.normalized_score == 0

    position_after_first = interceptor.position
    Move(source_entity_uuid=second_enemy.uuid, end_position=(3, 2)).apply()
    assert interceptor.position == position_after_first


def test_intercept_and_opportunity_attack_share_an_explicit_two_reaction_budget() -> None:
    """Intercept and a later OA each consume one of two available reactions."""
    reset_arena()
    interceptor = create_melee_fighter("Interceptor", (2, 2), "heroes")
    enemy = create_melee_fighter("Enemy", (8, 2), "monsters")
    interceptor.action_economy.reactions.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=interceptor.uuid,
            name="Second Reaction",
            value=1,
        )
    )
    add_opportunity_attack_handler(interceptor)
    arm_intercept(interceptor, (5, 2))
    Entity.update_all_entities_senses(max_distance=20)
    hit_modifier = force_attack_hit(interceptor)

    try:
        Move(source_entity_uuid=enemy.uuid, end_position=(3, 2)).apply()
        assert interceptor.position == (5, 2)
        assert enemy.position == (6, 2)
        assert interceptor.action_economy.reactions.normalized_score == 1
        hp_after_intercept = enemy.get_hp()

        Move(source_entity_uuid=enemy.uuid, end_position=(8, 2)).apply()
    finally:
        remove_attack_modifier(interceptor, hit_modifier)

    assert interceptor.action_economy.reactions.normalized_score == 0
    assert enemy.get_hp() < hp_after_intercept


def test_closed_door_invalidates_prepared_intercept_path_at_trigger_time() -> None:
    """A newly closed door prevents a previously legal intercept charge."""
    reset_arena()
    interceptor = create_melee_fighter("Interceptor", (2, 2), "heroes")
    door_closer = create_melee_fighter("Door Closer", (4, 3), "neutral")
    enemy = create_melee_fighter("Enemy", (9, 2), "monsters")
    door = build_directional_door(is_open=True)
    door.place_on_grid(
        (4, 2),
        boundary_direction=CardinalDirection.WEST,
    )
    arm_intercept(interceptor, (6, 2))
    Entity.update_all_entities_senses(max_distance=20)

    result = execute_use_action(door_closer, door.uuid, "Close Door")

    assert result is not None and not result.canceled
    assert door.is_open is False
    assert not get_map().can_transition((3, 2), (4, 2))
    assert interceptor.senses._paths_dirty

    Move(source_entity_uuid=enemy.uuid, end_position=(5, 2)).apply()

    assert interceptor.position == (3, 2)
    assert interceptor.action_economy.reactions.normalized_score == 0
    assert enemy.position == (5, 2)


def test_removed_intercept_condition_removes_its_handler() -> None:
    """Removing Intercepting disables its future movement reaction."""
    reset_arena()
    interceptor = create_melee_fighter("Interceptor", (2, 2), "heroes")
    enemy = create_melee_fighter("Enemy", (8, 2), "monsters")
    arm_intercept(interceptor, (5, 2))
    Entity.update_all_entities_senses(max_distance=20)
    assert interceptor.get_event_handler_by_name("Intercept") is not None

    interceptor.remove_condition("Intercepting")
    Move(source_entity_uuid=enemy.uuid, end_position=(3, 2)).apply()

    assert interceptor.get_event_handler_by_name("Intercept") is None
    assert interceptor.position == (2, 2)
    assert interceptor.action_economy.reactions.normalized_score == 1


def test_dodge_roll_moves_and_consumes_one_reaction() -> None:
    """A legal Dodge Roll moves two cells and spends exactly one reaction."""
    reset_arena()
    attacker = create_melee_fighter("Attacker", (3, 2), "monsters")
    defender = create_melee_fighter("Defender", (4, 2), "heroes")
    defender.add_condition(
        DodgeRollFeature(
            source_entity_uuid=defender.uuid,
            target_entity_uuid=defender.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=20)
    modifier_uuid = force_attack_hit(attacker)

    try:
        result = execute_attack(attacker, defender)
    finally:
        remove_attack_modifier(attacker, modifier_uuid)

    assert result is not None and not result.canceled
    assert defender.position == (6, 2)
    assert defender.action_economy.reactions.normalized_score == 0


def test_dodge_roll_handles_fully_blocked_and_partial_retreats() -> None:
    """No movement costs no reaction; one legal cell costs the reaction."""
    reset_arena(width=10, height=5)
    attacker = create_melee_fighter("Attacker", (1, 2), "monsters")
    defender = create_melee_fighter("Defender", (0, 2), "heroes")
    defender.add_condition(
        DodgeRollFeature(
            source_entity_uuid=defender.uuid,
            target_entity_uuid=defender.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=20)
    modifier_uuid = force_attack_hit(attacker)
    try:
        execute_attack(attacker, defender)
    finally:
        remove_attack_modifier(attacker, modifier_uuid)

    assert defender.position == (0, 2)
    assert defender.action_economy.reactions.normalized_score == 1

    reset_arena(width=10, height=5)
    attacker = create_melee_fighter("Attacker", (3, 2), "monsters")
    defender = create_melee_fighter("Defender", (4, 2), "heroes")
    get_map().set_tile(
        6,
        2,
        walking_cost=0,
        flying_cost=0,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
    )
    defender.add_condition(
        DodgeRollFeature(
            source_entity_uuid=defender.uuid,
            target_entity_uuid=defender.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=20)
    modifier_uuid = force_attack_hit(attacker)
    try:
        execute_attack(attacker, defender)
    finally:
        remove_attack_modifier(attacker, modifier_uuid)

    assert defender.position == (5, 2)
    assert defender.action_economy.reactions.normalized_score == 0


def test_open_door_is_authoritative_when_dodge_roll_triggers() -> None:
    """Dodge Roll rechecks the grid after a closed escape door opens."""
    reset_arena(width=10, height=5)
    attacker = create_melee_fighter("Attacker", (3, 2), "monsters")
    defender = create_melee_fighter("Defender", (4, 2), "heroes")
    opener = create_melee_fighter("Door Opener", (5, 3), "heroes")
    door = build_directional_door()
    door.place_on_grid(
        (5, 2),
        boundary_direction=CardinalDirection.WEST,
    )
    defender.add_condition(
        DodgeRollFeature(
            source_entity_uuid=defender.uuid,
            target_entity_uuid=defender.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=20)

    result = execute_use_action(opener, door.uuid, "Open Door")

    assert result is not None and not result.canceled
    assert door.is_open
    modifier_uuid = force_attack_hit(attacker)
    try:
        execute_attack(attacker, defender)
    finally:
        remove_attack_modifier(attacker, modifier_uuid)

    assert defender.position == (6, 2)
    assert defender.action_economy.reactions.normalized_score == 0


def test_removed_dodge_roll_condition_removes_its_handler() -> None:
    """Removing Dodge Roll disables its future attack reaction."""
    reset_arena()
    attacker = create_melee_fighter("Attacker", (3, 2), "monsters")
    defender = create_melee_fighter("Defender", (4, 2), "heroes")
    defender.add_condition(
        DodgeRollFeature(
            source_entity_uuid=defender.uuid,
            target_entity_uuid=defender.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=20)
    assert defender.get_event_handler_by_name("Dodge Roll") is not None

    defender.remove_condition("Dodge Roll")
    modifier_uuid = force_attack_hit(attacker)
    try:
        execute_attack(attacker, defender)
    finally:
        remove_attack_modifier(attacker, modifier_uuid)

    assert defender.get_event_handler_by_name("Dodge Roll") is None
    assert defender.position == (4, 2)
    assert defender.action_economy.reactions.normalized_score == 1

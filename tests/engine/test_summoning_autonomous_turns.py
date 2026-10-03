"""Summoned creatures choose attacks through the native encounter controller."""

from uuid import UUID

from dnd.actions import AttackEvent, DropConcentration, Move
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.spells.summoning import ConjureFey
from tests.engine.test_summoning_lifecycle import battle, cast_one


def autonomous_attack(encounter: Encounter, actor_uuid: UUID) -> AttackEvent:
    """Allow the installed controller up to four decisions to make its attack."""
    cursor = EventQueue.event_cursor()
    for _ in range(4):
        current = encounter.get_current_entity()
        assert current is not None and current.uuid == actor_uuid
        with fixed_dice_faces(15, *([1] * 30)):
            result = encounter.advance_one_controller_action_boundary()
        attacks = [event for _, event in EventQueue.iter_events_since(cursor)
                   if isinstance(event, AttackEvent)
                   and event.phase is EventPhase.COMPLETION
                   and event.source_entity_uuid == actor_uuid
                   and not event.canceled]
        if attacks:
            return attacks[0]
        assert result.status == "autonomous_action_completed", result
    raise AssertionError("Summon did not attack within four controller decisions")


def test_allied_summon_autonomously_attacks_enemy_and_preserves_nearby_caster(battle):
    _game, encounter, _system, caster, enemy = battle
    Entity.update_entity_position(caster, (3, 2))
    Entity.update_entity_position(enemy, (5, 2))
    Entity.update_all_entities_senses()
    member = cast_one(battle)
    caster_hp, enemy_hp = caster.get_hp(), enemy.get_hp()
    encounter.next_turn()
    assert encounter.get_current_controller() is member.controller
    context = encounter.build_current_turn_context()
    assert caster.uuid in context.visible_allies
    assert enemy.uuid in context.visible_enemies

    attack = autonomous_attack(encounter, member.entity.uuid)

    assert attack.target_entity_uuid == enemy.uuid
    assert enemy.get_hp() < enemy_hp
    assert caster.get_hp() == caster_hp
    assert member.entity.action_economy.actions.normalized_score == 0


def test_released_fey_keeps_spent_movement_and_autonomously_attacks_former_caster(battle):
    game, encounter, system, caster, enemy = battle
    member = cast_one(battle, ConjureFey, "wolf", 6)
    entity = member.entity
    encounter.next_turn()
    initial_movement = entity.action_economy.movement_remaining()
    movement = Move(source_entity_uuid=entity.uuid, end_position=(3, 2)).apply()
    assert movement is not None and not movement.canceled
    before = encounter.build_current_turn_context()
    assert before.movement_remaining == initial_movement - 5
    duration = member.existence.duration.duration
    caster_hp, enemy_hp = caster.get_hp(), enemy.get_hp()

    released = DropConcentration(source_entity_uuid=caster.uuid).apply()

    assert released is not None and not released.canceled
    after = encounter.build_current_turn_context()
    assert after.turn_execution_id == before.turn_execution_id
    assert (after.actions_remaining, after.bonus_actions_remaining,
            after.reactions_remaining, after.movement_remaining) == (
                before.actions_remaining, before.bonus_actions_remaining,
                before.reactions_remaining, before.movement_remaining)
    assert encounter.get_current_controller() is member.controller
    assert game.get_entity(entity.uuid) is entity
    assert system.memberships[entity.uuid] is member
    assert member.existence.duration.duration == duration
    assert caster.uuid in after.visible_enemies
    assert caster.uuid not in after.visible_allies

    attack = autonomous_attack(encounter, entity.uuid)

    assert attack.target_entity_uuid == caster.uuid
    assert caster.get_hp() < caster_hp
    assert enemy.get_hp() == enemy_hp
    assert entity.action_economy.actions.normalized_score == 0
    assert entity.action_economy.movement_remaining() <= before.movement_remaining

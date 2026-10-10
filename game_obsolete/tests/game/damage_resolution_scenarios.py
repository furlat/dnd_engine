"""Real spell-triggered damage histories shared by replay and visual checks."""

from typing import Literal
from uuid import UUID, uuid4

from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.base_actions import ActionEvent
from dnd.core.creature_types import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield

from dnd.actions import Attack, Move
from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue, EventPhase, TakeDamageEvent
from dnd.spells.evocation import FireShield, Thunderwave
from dnd.spells.transmutation import SpikeGrowth
from dnd.player.capture import capture_interval, capture_lineage
from dnd.player.recorded import RecordedSequence
from tests.game.scenarios import _healing_encounter


def resolution_history(kind: Literal['retaliation', 'push', 'walk']) -> RecordedSequence:
    with _healing_encounter() as (_, caster, target, _encounter):
        setup_standard_actions(caster)
        setup_standard_actions(target)
        for spell in (FireShield, SpikeGrowth, Thunderwave):
            register_spell(caster, spell, caster_level=7)
        if kind == 'retaliation':
            result = next(row for row in caster.registered_actions if isinstance(row, FireShield)).instantiate(target_entity_uuid=caster.uuid,
                                alt_skip_slot=True).apply()
        else:
            result = next(row for row in caster.registered_actions if isinstance(row, SpikeGrowth)).instantiate(end_position=(5, 3),
                                 alt_skip_slot=True).apply()
        assert result is not None and not result.canceled
        caster.action_economy.reset_all_costs()
        target.action_economy.reset_all_costs()
        initialization = capture_interval(name=f'{kind} initialization', start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=caster.uuid,
            battlefield_id='battlefield.open_floor_bright')
        if kind == 'retaliation':
            with fixed_dice_faces(15, 2, 3, 4):
                root = next(row for row in target.registered_actions if isinstance(row, Attack) and row.weapon_slot is WeaponSlot.MELEE_MAIN).instantiate(target_entity_uuid=caster.uuid).apply()
        elif kind == 'push':
            with fixed_dice_faces(*([1] * 80)):
                root = next(row for row in caster.registered_actions if isinstance(row, Thunderwave)).instantiate(end_position=(4, 3),
                                   alt_skip_slot=True).apply()
        else:
            with fixed_dice_faces(*([1] * 80)):
                root = next(row for row in target.registered_actions if isinstance(row, Move)).instantiate(end_position=(6, 3)).apply()
        assert root is not None and not root.canceled
        lineage = capture_lineage(root, observer_uuid=caster.uuid)
        return RecordedSequence(initialization=initialization, lineages=(lineage,))


def unseen_source_damage(*, temporary_hp: int = 0, undisclosed_owner: bool = False) -> tuple[RecordedSequence, UUID]:
    reset_engine_runtime()
    build_battlefield("battlefield.visibility_doorway_closed")
    game = Game()
    try:
        observer = Entity.create(uuid4(), "Observed recipient", config=EntityConfig(
            position=(5, 7), health=HealthConfig(temporary_hit_points=temporary_hp, hit_dices=[
                HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")]),
        ))
        hidden = Entity.create(uuid4(), "Unseen private source", config=EntityConfig(position=(8, 4)))
        for actor in (observer, hidden):
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        assert hidden.uuid not in observer.senses.entities
        cursor = EventQueue.event_cursor()
        initialization = capture_interval(name="hidden damage source", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id="battlefield.visibility_doorway_closed")
        parent = ActionEvent(source_entity_uuid=hidden.uuid) if undisclosed_owner else None
        observer.receive_damage(7, DamageType.FORCE, source_entity_uuid=hidden.uuid,
                                parent_event=parent.uuid if parent else None)
        if parent:
            parent = parent.phase_to(EventPhase.COMPLETION)
        damage_root, = (event for _, event in EventQueue.iter_events_since(cursor)
                 if isinstance(event, TakeDamageEvent)
                 and event.phase is EventPhase.COMPLETION)
        assert observer.get_normal_hp() == 33 + temporary_hp and hidden.uuid not in observer.senses.entities
        root = parent or damage_root
        lineage = capture_lineage(root, observer_uuid=observer.uuid, known_actor_uuids=frozenset({observer.uuid}))
        return RecordedSequence(initialization=initialization, lineages=(lineage,)), hidden.uuid
    finally:
        game.close()
        reset_engine_runtime()


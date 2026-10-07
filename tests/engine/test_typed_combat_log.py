"""Native log records retain recorded outcomes without leaking hidden causes."""

from uuid import UUID

import pytest
from pydantic import ValidationError
from dnd.core.combat_log import (
    ActionLogData, AttackLogData, CombatLogEntry, CombatLogEntryType,
    DamageRollDisplay, DamageTakenLogData, DiceRollDisplay, EmptyLogData,
    MultiEntityLogData, SpatialInteractionLogData, SpellDamageLogData,
    TurnLogData, summarize_target_entries,
)
from dnd.core.events import EventPhase, ForcedMovementEvent, StepMovementEvent
from dnd.subjective_combat_log import project_combat_log
from dnd.types.event_facts import MovementTrajectory
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from dnd.types.world import MovementProvocationPolicy

HERO = '00000000-0000-0000-0000-000000000001'
OBSERVER = '00000000-0000-0000-0000-000000000002'
FOE = '00000000-0000-0000-0000-000000000003'
HIDDEN = '00000000-0000-0000-0000-000000000004'


def entry(data, category=CombatLogEntryType.ACTION, *, source=HERO, target=None, children=()):
    return CombatLogEntry(entry_type=category, source_uuid=source, source_name='Hero' if source == HERO else 'Foe',
        target_uuid=target, target_name='Target' if target else None, compact='Recorded occurrence',
        verbose='Recorded occurrence', detailed='Recorded occurrence', data=data, sub_entries=list(children),
        perceiver_uuids={OBSERVER})


def project(log, **kwargs):
    result = project_combat_log(log, controlled_entity_uuids=frozenset({HERO}),
        observer_entity_uuids=frozenset({OBSERVER}), **kwargs)
    if result is not None:
        # All admitted variants must actually survive the public wire boundary.
        assert CombatLogEntry.model_validate_json(result.model_dump_json()) == result
    return result


def test_log_contract_rejects_untyped_extra_and_wrong_category_payloads():
    value = entry(EmptyLogData()).model_dump()
    for payload in ({}, {'kind':'invented'}, {'kind':'empty','arbitrary_secret':'not allowed'},
                    {'kind':'turn','entity_name':'Hero','entity_uuid':HERO,'round_number':1,'turn_index':0}):
        with pytest.raises(ValidationError):
            CombatLogEntry.model_validate({**value, 'data':payload})
    with pytest.raises(ValidationError):
        CombatLogEntry.model_validate({key:v for key,v in value.items() if key != 'data'})


def test_visible_damage_does_not_publish_hidden_parent_spell_or_weapon():
    damage = entry(DamageTakenLogData(target_name='Hero', damage=7, damage_type='fire',
        source_name='Secret staff', effect_id='secret'), CombatLogEntryType.DAMAGE_TAKEN, source=HIDDEN, target=HERO)
    parent = entry(ActionLogData(entity_name='Hidden caster', entity_uuid=HIDDEN, action_name='Secret spell',
        effect_description='Private loadout'), source=HIDDEN, target=FOE, children=(damage,))
    parent.perceiver_uuids.clear()
    original = parent.model_copy(deep=True)
    result = project(parent)
    assert result is not None and result.data.kind == 'empty'
    encoded = result.model_dump_json()
    assert 'Secret' not in encoded and 'Private loadout' not in encoded and HIDDEN not in encoded
    assert result.sub_entries[0].data.damage == 7
    assert parent == original


def test_known_identity_names_an_observed_turn_end_but_does_not_reveal_unseen_death():
    log = entry(TurnLogData(entity_name='Foe', entity_uuid=FOE, round_number=3, turn_index=2),
        CombatLogEntryType.TURN_END, source=FOE)
    result = project(log, known_entity_names={FOE:'Gate guard'})
    assert result is not None and result.source_name == 'Gate guard' and result.source_uuid == FOE
    log.perceiver_uuids.clear()
    assert project(log, known_entity_names={FOE:'Gate guard'}) is None


def test_repeated_targets_and_auxiliary_children_have_one_detail_tree():
    targets = [entry(SpellDamageLogData(spell_name='Magic Missile', target_name=name,
                damage=damage, damage_type='force'), CombatLogEntryType.SPELL_DAMAGE, target=identity)
               for name,identity,damage in (('A',FOE,3),('B',HIDDEN,4),('A',FOE,5))]
    for target in targets:
        target.target_name = target.data.target_name
        target.identified_entity_observer_uuids = {target.target_uuid:{OBSERVER}}
    auxiliary = entry(EmptyLogData())
    children = [targets[0], auxiliary, targets[1], targets[2]]
    data = summarize_target_entries(MultiEntityLogData(action_name='Magic Missile', caster_name='Hero'), children, (0,2,3))
    root = entry(data, CombatLogEntryType.MULTI_ENTITY_ACTION, children=children)
    result = project(root)
    assert result is not None and result.data.kind == 'multi_entity_action'
    assert result.data.target_names == ['A','B','A']
    assert result.data.total_damage == 12 and result.data.total_targets == 3
    assert result.data.target_entry_indices == (0,2,3)
    assert 'per_target_logs' not in result.model_dump_json()
    targets[1].source_uuid = HIDDEN
    targets[1].perceiver_uuids.clear()
    targets[1].identified_entity_observer_uuids.clear()
    result = project(root)
    assert result.data.target_names == ['A','A']
    assert result.data.target_entry_indices == (0,2) and result.data.total_damage == 8


def test_roll_pairs_are_numbers_not_hidden_coordinates():
    roll = DiceRollDisplay(dice_str='d20', results=[15,8], all_d20_rolls=[15,8],
        d20_used=15, bonus=5, total=20, advantage_status='advantage')
    data = AttackLogData(attacker_name='Hero',attacker_uuid=HERO,target_name='Target',target_uuid=FOE,
        weapon_name='Bow', attack_roll=roll,target_ac=12,outcome='hit',is_hit=True,is_crit=False,
        damage_rolls=[DamageRollDisplay(dice_str='2d6', dice_results=[3,4],total=7,damage_type='piercing')], total_damage=7)
    log = entry(data, CombatLogEntryType.ATTACK, target=FOE)
    log.identified_entity_observer_uuids = {FOE:{OBSERVER}}
    result = project(log)
    assert result.data == data


def test_step_projection_does_not_reveal_hidden_prefix_length():
    event = StepMovementEvent(source_entity_uuid=UUID(FOE), source_entity_name='Foe', from_position=(1,1),
        to_position=(2,1), path_index=18, total_path_length=25, movement_cost=5,
        trajectory=MovementTrajectory.PATH, disclosed_path=((1,1),(2,1)),
        from_elevation_feet=0,to_elevation_feet=0,provocation_policy=MovementProvocationPolicy.ORDINARY_EXIT,
        committed=True,phase=EventPhase.COMPLETION,use_register=False)
    log = event.generate_combat_log()
    log.perceiver_uuids={OBSERVER}
    log.identified_entity_observer_uuids={FOE:{OBSERVER}}
    log.located_position_observer_uuids={'1,1':{OBSERVER},'2,1':{OBSERVER}}
    result = project(log)
    assert result.data.path_index == 0
    assert '18/24' not in result.detailed and '5ft' in result.detailed


def test_spatial_text_counts_only_admitted_cells():
    log = entry(SpatialInteractionLogData(operation=SpatialEffectInteractionOperation.IGNITE,
        intensity='minor',affected_positions=((1,1),(2,1),(3,1)),source_item_id=None),
        CombatLogEntryType.SPATIAL_EFFECT)
    log.verbose = log.detailed = 'Ignites 3 cells'
    log.located_position_observer_uuids={'1,1':{OBSERVER}}
    result = project(log)
    assert result.data.affected_positions == ((1,1),)
    assert '1 observed cells' in result.detailed and '3 cells' not in result.detailed


def test_direction_vector_is_not_removed_as_a_hidden_position():
    event = ForcedMovementEvent(source_entity_uuid=UUID(HERO),target_entity_uuid=UUID(FOE),
        source_entity_name='Hero',target_entity_name='Foe',start_position=(2,2),end_position=(3,2),
        direction=(1,0),intended_distance=5,actual_distance=5,use_register=False)
    log = event.generate_combat_log()
    log.identified_entity_observer_uuids={FOE:{OBSERVER}}
    result = project(log)
    assert result.data.direction == (1,0)
    assert 'perceiver_uuids' not in result.model_dump_json()

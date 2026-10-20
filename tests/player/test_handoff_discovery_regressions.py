"""Offered actions remain executable through the worker's actual selection API.

Inputs: ordinary authored actors/items and exact Choices/Preview operands.
Boundary: worker discovery, ordered preview, command and public capture.
Outputs: accepted selections and their native condition/resource effects.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from devtools.player_server_acceptance.fixtures import combat_configuration
from dnd.actions_functional import register_spell
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.content.encounters import (
    EncounterDeploymentSpec, EncounterDeploymentZone, EncounterRecipe,
)
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.items.divine_rewards import HealingIncenseZone
from dnd.player.commands import ActionSelection
from dnd.player.facts import LifeFact, SpellFact
from dnd.player.session import close_session
from dnd.spells.abjuration import ProtectionFromEnergy, ProtectionFromEnergyEffect
from dnd.spells.necromancy import (
    AbilityCurseEffect, AttackCurseEffect, BestowCurse, BlindnessDeafness,
    BlindnessDeafnessEffect, DamageCurseEffect, InactionCurseEffect, SpareTheDying,
)
from dnd.types.character_progression import CharacterClass
from server.protocol import ChoicesRequest, CommandRequest, ExecuteSelectionIntent, PlayerOperation, PreviewRequest
from server.worker import dispatch, needs_advance, start
from server.worker_protocol import Advance, Choices, Command, Preview, Start
from tests.manual.spell_regression_support import force_save_result
from tests.player.test_compact_choices import rows, world
from tests.player.test_divine_and_wizard_transport import worker
from tests.progression.prepared_class_support import prepared_build


def choices(runtime, seat, actor):
    return dispatch(runtime, Choices(seat_id=seat, request=ChoicesRequest(
        actor_uuid=actor.uuid, state_revision=runtime.publications[seat].state_revision,
        force_attack=False, correlation_id=uuid4(),
    )))[2].choices


def submit(runtime, seat, actor, discovered, selection, number):
    reply, records, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
        command_number=number, actor_uuid=actor.uuid,
        state_revision=runtime.publications[seat].state_revision,
        intent=ExecuteSelectionIntent(discovery_generation=discovered.discovery_generation,
            selection=selection),
    )))
    assert reply.rejection is None and records
    return tuple(PlayerOperation.model_validate_json(record.model_dump_json()) for record in records)


def test_worker_accepts_help_ally_returned_by_its_own_preview():
    config = combat_configuration('melee', Path('/unused-memory-only-configuration'))
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.help_discovery',
        title='Adjacent assistance', battlefield_id=config.recipe.battlefield_id,
        zones=(EncounterDeploymentZone(zone_id='amber', ordered_slots=((4, 6), (4, 7))),
               EncounterDeploymentZone(zone_id='blue', ordered_slots=((5, 6), (11, 7)))))
    recipe = EncounterRecipe.create(encounter_id='encounter.help_discovery', title='Help discovery',
        battlefield_id=config.recipe.battlefield_id, deployment=deployment,
        roster_slots=config.recipe.roster_slots, opening_policy=config.recipe.opening_policy)
    runtime, _, _ = start(Start(game_id='help-discovery', game_epoch=uuid4(),
        audience_ids={seat.seat_id: uuid4() for seat in config.credentials},
        encounter_id=None, recipe=recipe, assignments=config.assignments, test_seed=2))
    try:
        while needs_advance(runtime.session):
            dispatch(runtime, Advance())
        seat, publication = next((seat, p) for seat, p in runtime.publications.items()
            if p.boundary.input_actor_uuid is not None)
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        discovered = choices(runtime, seat, actor)
        action = next(row for row in rows(discovered) if row.behavior_id == 'action.help_attack')
        enemy = discovered.target_sets[action.target_set][0]
        before = EventQueue.event_cursor()

        def preview(indices):
            return dispatch(runtime, Preview(seat_id=seat, request=PreviewRequest(
                actor_uuid=actor.uuid, state_revision=publication.state_revision,
                discovery_generation=discovered.discovery_generation, correlation_id=uuid4(),
                selection=ActionSelection(action_index=action.discovery_index,
                    target_indices=indices),
            )))[2].preview

        prefix = preview((enemy.index,))
        assert not prefix.can_confirm
        ally, = prefix.target_sets[prefix.next_target_set]
        ally_uuid = prefix.subjects[ally.subject].uuid
        assert ally_uuid != actor.uuid
        assert preview((enemy.index, ally.index)).can_confirm
        assert EventQueue.event_cursor() == before
        assert runtime.publications[seat].state_revision == publication.state_revision
        submit(runtime, seat, actor, discovered, ActionSelection(
            action_index=action.discovery_index, target_indices=(enemy.index, ally.index)), 1)
        target = runtime.session.game.entities[discovered.subjects[enemy.subject].uuid]
        assistance, = (c for c in target.active_conditions_by_uuid.values()
            if c.get_display_name() == 'Attack Assistance')
        assert assistance.assisted_ally_uuid == ally_uuid
        assert actor.action_economy.actions.normalized_score == 0
    finally:
        close_session(runtime.session)


def test_worker_offers_and_uses_incense_from_actual_equipped_intervention_reward():
    runtime, seat, publication = worker(prepared_build(CharacterClass.CLERIC, 10))
    try:
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        discovered = choices(runtime, seat, actor)
        arm = next(row for row in rows(discovered)
            if row.behavior_id == 'action.class.cleric.divine_intervention.arm_thy_servant')
        target, = discovered.target_sets[arm.target_set]
        submit(runtime, seat, actor, discovered, ActionSelection(
            action_index=arm.discovery_index, target_indices=(target.index,)), 1)
        mace = actor.equipment.weapon_melee_main
        assert mace is not None and mace.item_id == 'weapon.devotees_mace'
        discovered = choices(runtime, seat, actor)
        incense, = (row for row in rows(discovered)
            if row.behavior_id == 'action.item.devotees_mace.healing_incense')
        assert incense.source_item_uuid == mace.uuid and incense.can_afford
        target, = discovered.target_sets[incense.target_set]
        submit(runtime, seat, actor, discovered, ActionSelection(
            action_index=incense.discovery_index, target_indices=(target.index,)), 2)
        assert mace.charges == 0 and actor.action_economy.bonus_actions.normalized_score == 0
        assert any(zone.source_item_uuid == mace.uuid for zone in get_map().get_spatial_conditions()
            if isinstance(zone, HealingIncenseZone))
    finally:
        close_session(runtime.session)


def test_worker_offers_spare_dying_for_seen_zero_hp_patient_without_attack_target_leak(world):
    runtime, seat, publication = world
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    patient = next(entity for entity in runtime.session.game.entities.values() if actor.is_enemy(entity))
    patient.move((4, 7))
    patient.uses_death_saves = True
    patient.receive_damage(patient.get_normal_hp(), DamageType.FORCE, actor.uuid)
    assert patient.health.life_state is LifeState.DYING
    assert patient.uuid in actor.senses.entities
    register_spell(actor, SpareTheDying, caster_level=7)
    discovered = choices(runtime, seat, actor)
    spell, = (row for row in rows(discovered) if row.behavior_id == 'spell.spare_the_dying')
    recipient, = (target for target in discovered.target_sets[spell.target_set]
        if discovered.subjects[target.subject].uuid == patient.uuid)
    for attack in rows(discovered):
        if attack.behavior_id == 'action.attack':
            assert all(discovered.subjects[target.subject].uuid != patient.uuid
                for target in discovered.target_sets[attack.target_set] if target.kind == 'subject')
    records = submit(runtime, seat, actor, discovered, ActionSelection(
        action_index=spell.discovery_index, target_indices=(recipient.index,)), 1)
    assert patient.health.life_state is LifeState.STABLE and patient.get_normal_hp() == 0
    assert actor.action_economy.actions.normalized_score == 0
    assert len(records) == 2
    for record in records:
        observed = [node.fact for group in record.lineages for node in group.events
            if isinstance(node.fact, LifeFact)]
        assert any(fact.entity_uuid == patient.uuid and fact.new_state is LifeState.STABLE
            and fact.normal_hit_points == 0 for fact in observed)


@pytest.mark.parametrize('spell,behavior,facets,effect_class,field,value,effect_id', [
    *((BestowCurse, 'spell.bestow_curse', (('form', 'ability'), ('ability', ability)),
        AbilityCurseEffect, 'cursed_ability', ability, 'control.bestow_curse.option_1')
      for ability in ('strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma')),
    (BestowCurse, 'spell.bestow_curse', (('form', 'attack'),), AttackCurseEffect,
        None, None, 'control.bestow_curse.option_2'),
    (BestowCurse, 'spell.bestow_curse', (('form', 'inaction'),), InactionCurseEffect,
        None, None, 'control.bestow_curse.option_3'),
    (BestowCurse, 'spell.bestow_curse', (('form', 'damage'),), DamageCurseEffect,
        None, None, 'control.bestow_curse.option_4'),
    *((BlindnessDeafness, 'spell.blindness_deafness', (('form', effect),),
        BlindnessDeafnessEffect, 'effect_type', effect, 'control.' + effect)
      for effect in ('blinded', 'deafened')),
    *((ProtectionFromEnergy, 'spell.protection_from_energy', (('damage_type', energy),),
        ProtectionFromEnergyEffect, 'energy_type', DamageType(energy.title()),
        'support.protection_from_energy.' + energy)
      for energy in ('acid', 'cold', 'fire', 'lightning', 'thunder')),
])
def test_worker_offers_and_executes_existing_spell_choices(world, spell, behavior, facets,
        effect_class, field, value, effect_id):
    runtime, seat, publication = world
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    target = (actor if spell is ProtectionFromEnergy else
        next(entity for entity in runtime.session.game.entities.values() if actor.is_enemy(entity)))
    if target is not actor:
        target.move((4, 7))
        force_save_result(target, 'constitution' if spell is BlindnessDeafness else 'wisdom',
            succeeds=False)
    register_spell(actor, spell, caster_level=7)
    discovered = choices(runtime, seat, actor)
    action, = (row for row in rows(discovered) if row.behavior_id == behavior
        and all(any(f.key == key and f.value == value for f in row.variant_facets)
            for key, value in facets))
    binding = next(binding for binding in discovered.target_sets[action.target_set]
        if discovered.subjects[binding.subject].uuid == target.uuid)
    selection = ActionSelection(action_index=action.discovery_index, target_indices=(binding.index,))
    _, _, preview = dispatch(runtime, Preview(seat_id=seat, request=PreviewRequest(
        actor_uuid=actor.uuid, state_revision=publication.state_revision,
        discovery_generation=discovered.discovery_generation, correlation_id=uuid4(),
        selection=selection)))
    assert preview.preview.can_confirm
    with fixed_dice_faces(*([2] * 80)):
        records = submit(runtime, seat, actor, discovered, selection, 1)
    condition, = (condition for condition in target.active_conditions_by_uuid.values()
        if isinstance(condition, effect_class))
    if field == 'cursed_ability':
        assert condition.cursed_ability == value
    elif field == 'effect_type':
        assert condition.effect_type == value
    elif field == 'energy_type':
        assert condition.energy_type == value
    assert len(records) == 2
    for record in records:
        facts = [node.fact for group in record.lineages for node in group.events
            if isinstance(node.fact, SpellFact)]
        assert any(fact.behavior_id == behavior and fact.effect_id == effect_id for fact in facts)

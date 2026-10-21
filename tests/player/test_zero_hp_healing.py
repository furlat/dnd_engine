"""Creator-built healers discover, preview and revive actual zero-HP patients."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions_functional import (
    execute_available_action, free_aim_target, get_available_actions, preview_available_selection,
)
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from dnd.player.commands import ActionSelection
from dnd.player.facts import HealFact, LifeFact
from dnd.player.session import close_session, create_session
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from server.protocol import CommandRequest, EndTurnIntent, PreviewRequest
from server.worker import dispatch
from server.worker_protocol import Command, Preview
from tests.player.test_compact_choices import rows
from tests.player.test_handoff_discovery_regressions import choices, submit
from tests.player.test_handoff_passive_attribution import await_actor, workers
from tests.progression.prepared_class_support import prepared_build


HEALING_SPELLS = (
    ('spell.cure_wounds', 1), ('spell.healing_word', 1), ('spell.prayer_of_healing', 2),
    ('spell.mass_healing_word', 3), ('spell.mass_cure_wounds', 5), ('spell.heal', 6),
    ('spell.regenerate', 7), ('spell.mass_heal', 9), ('spell.power_word_heal', 9),
)


@pytest.fixture
def healing_scene():
    cleric = replace(prepared_build(CharacterClass.CLERIC, 17), prepared_spells=(
        PreparedSpellSelection('class.cleric.spellcasting', tuple(key for key, _ in HEALING_SPELLS)),))
    session = create_session(player_builds=(cleric, prepared_build(CharacterClass.FIGHTER, 5)),
        player_positions=((10, 10), (11, 10)))
    try:
        yield tuple(session.game.entities[uid] for uid in session.player_uuids)
    finally:
        close_session(session)


@pytest.mark.parametrize('behavior,level', HEALING_SPELLS)
@pytest.mark.parametrize('stable', (False, True), ids=('dying', 'stable'))
def test_healing_offers_previews_and_revives_living_zero_hp_patient(healing_scene, behavior, level, stable):
    caster, patient = healing_scene
    patient.receive_damage(patient.get_normal_hp(), DamageType.FORCE, caster.uuid)
    if stable:
        assert patient.stabilize()
    assert patient.health.life_state is (LifeState.STABLE if stable else LifeState.DYING)
    assert patient.uuid in caster.senses.entities
    cursor = EventQueue.event_cursor()
    rows = get_available_actions(caster, include_aoe_preview=False).all_actions
    row, = (row for row in rows if row.behavior_id == behavior)
    if behavior == 'spell.mass_cure_wounds':
        target = free_aim_target(row, patient.position)
    else:
        target, = (target for target in row.valid_targets if target.target_uuid == patient.uuid)
    preview = preview_available_selection(caster, row, (target,), cast_at_level=level)
    assert preview.can_confirm
    assert patient.uuid in (preview.affected_entity_uuids if behavior == 'spell.mass_cure_wounds'
        else preview.effective_target_uuids)
    assert EventQueue.event_cursor() == cursor
    with fixed_dice_faces(*([4] * 100)):
        result = execute_available_action(caster, row, target, cast_at_level=level)
    assert result is not None and not result.canceled
    assert patient.get_normal_hp() > 0 and patient.health.life_state is LifeState.ALIVE


def test_healing_never_offers_or_previews_actual_dead_patient(healing_scene):
    caster, patient = healing_scene
    patient.receive_damage(3 * patient.get_normal_hp(), DamageType.FORCE, caster.uuid)
    assert patient.health.life_state is LifeState.DEAD
    hp_before = patient.get_normal_hp()
    rows = get_available_actions(caster, include_aoe_preview=False).all_actions
    for row in rows:
        if row.behavior_id in dict(HEALING_SPELLS):
            assert all(target.target_uuid != patient.uuid for target in row.valid_targets)
    area, = (row for row in rows if row.behavior_id == 'spell.mass_cure_wounds')
    preview = preview_available_selection(caster, area, (free_aim_target(area, patient.position),), cast_at_level=5)
    assert patient.uuid not in preview.affected_entity_uuids
    with fixed_dice_faces(*([4] * 100)):
        result = execute_available_action(caster, area, free_aim_target(area, patient.position), cast_at_level=5)
    assert result is not None and not result.canceled
    assert patient.get_normal_hp() == hp_before and patient.health.life_state is LifeState.DEAD


@pytest.mark.parametrize('mode', ('lesser', 'greater'))
def test_prepared_paladin_offers_and_heals_zero_hp_patient(mode):
    session = create_session(player_builds=(prepared_build(CharacterClass.PALADIN, 5),
        prepared_build(CharacterClass.FIGHTER, 5)), player_positions=((10, 10), (11, 10)))
    try:
        caster, patient = (session.game.entities[uid] for uid in session.player_uuids)
        patient.receive_damage(patient.get_normal_hp(), DamageType.FORCE, caster.uuid)
        row, = (row for row in get_available_actions(caster).all_actions
            if row.behavior_id == 'action.class.paladin.lay_on_hands'
            and any(facet.key == 'form' and facet.value == mode for facet in row.variant_facets))
        target, = (target for target in row.valid_targets if target.target_uuid == patient.uuid)
        assert preview_available_selection(caster, row, (target,)).can_confirm
        result = execute_available_action(caster, row, target)
        assert result is not None and not result.canceled
        assert patient.get_normal_hp() > 0 and patient.health.life_state is LifeState.ALIVE
    finally:
        close_session(session)


def test_worker_stabilizes_heals_then_moves_the_original_patient(workers):
    cleric = prepared_build(CharacterClass.CLERIC, 11)
    first = cleric.class_levels[0]
    first = replace(first, choices=tuple(replace(choice, values=(
        'spell.spare_the_dying', *(value for value in choice.values if value != 'spell.spare_the_dying')
    )[:len(choice.values)]) if choice.choice_id.endswith('.cantrips') else choice for choice in first.choices))
    cleric = replace(cleric, class_levels=(first, *cleric.class_levels[1:]), prepared_spells=(
        PreparedSpellSelection('class.cleric.spellcasting', ('spell.cure_wounds',)),))
    runtime = workers(audience_ids={'party': uuid4()},
        player_builds=(cleric, prepared_build(CharacterClass.FIGHTER, 5)))
    caster, patient = (runtime.session.game.entities[uid] for uid in runtime.session.player_uuids)
    with fixed_dice_faces(*([1] * 500)):
        _, seat, _ = await_actor(runtime, caster.uuid)
        patient.move((caster.position[0] + 1, caster.position[1]))
        patient.receive_damage(patient.get_normal_hp(), DamageType.FORCE, caster.uuid)
        assert patient.health.life_state is LifeState.DYING
        for number, behavior, expected in (
            (20, 'spell.spare_the_dying', LifeState.STABLE),
            (22, 'spell.cure_wounds', LifeState.ALIVE),
        ):
            discovered = choices(runtime, seat, caster)
            action, = (row for row in rows(discovered) if row.behavior_id == behavior)
            recipient, = (target for target in discovered.target_sets[action.target_set]
                if discovered.subjects[target.subject].uuid == patient.uuid)
            selection = ActionSelection(action.discovery_index, (recipient.index,))
            _, _, preview = dispatch(runtime, Preview(seat_id=seat, request=PreviewRequest(
                actor_uuid=caster.uuid, state_revision=runtime.publications[seat].state_revision,
                discovery_generation=discovered.discovery_generation, correlation_id=uuid4(), selection=selection)))
            assert preview.preview.can_confirm
            records = submit(runtime, seat, caster, discovered, selection, number)
            assert patient.health.life_state is expected
            facts = [node.fact for record in records for group in record.lineages for node in group.events]
            assert any(isinstance(fact, LifeFact) and fact.entity_uuid == patient.uuid
                and fact.new_state is expected for fact in facts)
            if expected is LifeState.STABLE:
                assert patient.get_normal_hp() == 0
                reply, _, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
                    command_number=21, actor_uuid=caster.uuid,
                    state_revision=runtime.publications[seat].state_revision, intent=EndTurnIntent())))
                assert reply.rejection is None
                _, seat, _ = await_actor(runtime, caster.uuid)
            else:
                assert patient.get_normal_hp() > 0
                assert any(isinstance(fact, HealFact) and fact.target_entity_uuid == patient.uuid for fact in facts)

        _, seat, _ = await_actor(runtime, patient.uuid)
        discovered = choices(runtime, seat, patient)
        origin = patient.position
        move, destination = next((row, target) for row in rows(discovered)
            if row.behavior_id == 'action.move' and row.can_afford
            for target in discovered.target_sets[row.target_set]
            if discovered.positions[target.position] != origin
            and max(abs(a - b) for a, b in zip(discovered.positions[target.position], origin)) == 1)
        submit(runtime, seat, patient, discovered, ActionSelection(move.discovery_index, (destination.index,)), 23)
        assert patient.position == discovered.positions[destination.position] and patient.position != origin

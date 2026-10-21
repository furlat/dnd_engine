"""A witnessed Glyph trigger keeps its exact retired zone, without borrowing memory.

Prepared Glyph casts and real entry movement publish detached two-seat updates.
Only the trigger's own observed removal authorizes its damage source UUID;
blindness, old sightings and unrelated removals in one operation do not.
"""

from dataclasses import replace
import random

import pytest

from dnd.actions_functional import execute_available_action, free_aim_target, get_available_actions
from dnd.conditions import Blinded
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.player.application import initialize_audiences, seat_content
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import SpatialEffectStateFact
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import close_session, create_session, publish_sheets
from dnd.spells.abjuration import GlyphOfWardingZone
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from tests.manual.spell_regression_support import force_save_result
from tests.player.test_emitted_update_replica import INITIALIZATION
from tests.player.test_holy_nimbus_attribution import capture, damage_facts
from tests.progression.prepared_class_support import prepared_build


@pytest.fixture
def glyph_arena():
    previous_random = random.getstate()
    random.seed(6)
    build = replace(prepared_build(CharacterClass.WIZARD, 7),
        scribed_spell_ids=('spell.glyph_of_warding',), prepared_spells=(
            PreparedSpellSelection('class.wizard.spellcasting', ('spell.glyph_of_warding',)),))
    session = create_session(player_builds=(build,), enemy_positions=((14, 12), (14, 14)))
    try:
        caster = session.game.entities[session.player_uuids[0]]
        enemy = next(actor for actor in session.game.entities.values() if actor.position == (14, 12))
        add_modifier(enemy.health.max_hit_points_bonus, Channel.SELF_STATIC, Kind.VALUE,
            NumericalModifier(name='Survive the real Glyph payload', value=100, source_entity_uuid=enemy.uuid))
        force_save_result(enemy, 'dexterity', succeeds=False)
        session = replace(session, player_uuids=(*session.player_uuids, enemy.uuid))
        session.seats['recipient'] = PlayerAudience((enemy.uuid,), (enemy.uuid,))
        publish_sheets(session)
        yield session, caster, enemy
    finally:
        close_session(session)
        random.setstate(previous_random)


def blind(enemy):
    result = enemy.add_condition(Blinded(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid))
    assert result is not None and not result.canceled


def cast_glyph(session, caster, audiences, catalog, payload):
    row, = (row for row in get_available_actions(caster).position_actions
        if row.behavior_id == 'spell.glyph_of_warding'
        and any(facet.key == 'form' and facet.value == payload for facet in row.variant_facets))
    cursor = EventQueue.event_cursor()
    result = execute_available_action(caster, row, free_aim_target(row, (11, 10)), cast_at_level=3)
    assert result is not None and not result.canceled
    updates = capture(session, audiences, catalog, cursor)
    zone, = (zone for zone in get_map().get_spatial_conditions() if isinstance(zone, GlyphOfWardingZone))
    assert zone.applied and zone.armed and not zone.initial_trigger_pending
    return zone, updates


def enter_glyph(session, enemy, audiences, catalog):
    cursor = EventQueue.event_cursor()
    hp = enemy.get_normal_hp()
    with fixed_dice_faces(*([3] * 100)):
        row = next(row for row in get_available_actions(enemy).position_actions
            if row.behavior_id == 'action.move'
            and any(target.position == (12, 11) for target in row.valid_targets))
        target = next(target for target in row.valid_targets if target.position == (12, 11))
        result = execute_available_action(enemy, row, target)
    assert result is not None and not result.canceled and enemy.position == (12, 11)
    assert enemy.get_normal_hp() == hp - 15
    return cursor, capture(session, audiences, catalog, cursor)


@pytest.mark.parametrize('payload', ['acid', 'cold', 'fire', 'lightning', 'thunder'])
@pytest.mark.parametrize('visibility', ['visible', 'hidden', 'previously_seen'])
def test_glyph_entry_damage_retains_only_its_witnessed_retired_zone(glyph_arena, payload, visibility):
    session, caster, enemy = glyph_arena
    if visibility == 'hidden':
        blind(enemy)
    catalog = ui_content_manifest()
    audiences, initializations = initialize_audiences(session, catalog)
    clients = {seat: reduce_initialization(INITIALIZATION.validate_json(INITIALIZATION.dump_json(initial)),
        content_additions=seat_content(audiences[seat])) for seat, initial in initializations.items()}
    zone, births = cast_glyph(session, caster, audiences, catalog, payload)
    for seat, update in births.items():
        clients[seat] = reduce_operation(clients[seat], update)
    assert zone.uuid in clients['party'].senses.spatial_effects
    assert (zone.uuid in clients['recipient'].senses.spatial_effects) == (
        visibility != 'hidden')
    if visibility == 'previously_seen':
        cursor = EventQueue.event_cursor()
        blind(enemy)
        for seat, update in capture(session, audiences, catalog, cursor).items():
            clients[seat] = reduce_operation(clients[seat], update)
    if visibility != 'visible':
        assert zone.uuid not in clients['recipient'].senses.spatial_effects
    cursor, updates = enter_glyph(session, enemy, audiences, catalog)
    assert not zone.applied and get_map().get_spatial_condition(zone.uuid) is None
    native = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == enemy.uuid]
    assert len(native) == 1 and native[0].source_condition_uuid == zone.uuid
    for seat, update in updates.items():
        damage, = damage_facts(update, enemy.uuid)
        assert damage.applied_damage == 15 and damage.damage_type is DamageType[payload.upper()]
        witnessed = seat == 'party' or visibility == 'visible'
        assert damage.source_condition_uuid == (zone.uuid if witnessed else None)
        removals = [node.fact for group in update.lineages for node in group.events
            if isinstance(node.fact, SpatialEffectStateFact)
            and node.fact.spatial_effect_uuid == zone.uuid
            and node.fact.operation is SpatialEffectChangeOperation.REMOVED]
        assert bool(removals) == witnessed
        clients[seat] = reduce_operation(clients[seat], update)
        assert zone.uuid not in clients[seat].senses.spatial_effects
        assert clients[seat].actors[enemy.uuid].normal_hp == enemy.get_normal_hp()
    # Later ordinary damage cannot reuse the removed contact, even in the same stream.
    cursor = EventQueue.event_cursor()
    assert enemy.receive_damage(3, DamageType[payload.upper()], caster.uuid) == 3
    for seat, update in capture(session, audiences, catalog, cursor).items():
        damage, = damage_facts(update, enemy.uuid)
        assert damage.source_condition_uuid is None
        clients[seat] = reduce_operation(clients[seat], update)


@pytest.mark.parametrize('shared_root', [False, True])
def test_unrelated_removal_in_same_operation_does_not_authorize_retired_damage(glyph_arena, shared_root):
    session, caster, enemy = glyph_arena
    catalog = ui_content_manifest()
    audiences, initializations = initialize_audiences(session, catalog)
    clients = {seat: reduce_initialization(INITIALIZATION.validate_json(INITIALIZATION.dump_json(initial)),
        content_additions=seat_content(audiences[seat])) for seat, initial in initializations.items()}
    zone, births = cast_glyph(session, caster, audiences, catalog, 'fire')
    for seat, update in births.items():
        clients[seat] = reduce_operation(clients[seat], update)
        assert zone.uuid in clients[seat].senses.spatial_effects
    cursor = EventQueue.event_cursor()
    # Either separate roots or different immediate causes under one real turn:
    # being in the same operation/tree never authorizes a retired source UUID.
    root = caster.on_turn_start() if shared_root else None
    assert zone.deactivate(parent_event=root)
    other_cause = None
    if root is not None:
        other_cause = caster.create_saving_throw_request(enemy.uuid, 'dexterity', 10, parent_event=root.uuid)
        enemy.saving_throw(other_cause)
    assert enemy.receive_damage(3, DamageType.FIRE, caster.uuid,
        source_condition_uuid=zone.uuid, parent_event=other_cause.uuid if other_cause is not None else None) == 3
    for seat, update in capture(session, audiences, catalog, cursor).items():
        damage, = damage_facts(update, enemy.uuid)
        assert damage.applied_damage == 3 and damage.source_condition_uuid is None
        assert any(isinstance(node.fact, SpatialEffectStateFact)
            and node.fact.spatial_effect_uuid == zone.uuid
            and node.fact.operation is SpatialEffectChangeOperation.REMOVED
            for group in update.lineages for node in group.events)
        clients[seat] = reduce_operation(clients[seat], update)
        assert zone.uuid not in clients[seat].senses.spatial_effects
        assert clients[seat].actors[enemy.uuid].normal_hp == enemy.get_normal_hp()

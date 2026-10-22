"""A summoned Myrmidon's real Burrow publishes its authored Landing child.

Boundary: prepared character -> native summon/Burrow -> detached seat updates.
Expected: the Landing keeps its own identity and Burrow parent without another
selectable action, while the bonus action, movement and save damage stay intact.
"""

from contextlib import contextmanager
from dataclasses import replace
import random

from dnd.core.base_actions import ActionEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue
from dnd.monsters.spell_summon_actions import MyrmidonBurrow
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import ActionFact, PlayerUpdate
from dnd.player.reduction import node_lineages, parent_lineages
from dnd.player.session import close_session, create_session
from dnd.spells.summoning import ConjureElemental
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from tests.player.test_emitted_update_replica import operation_since
from tests.progression.prepared_class_support import prepared_build


@contextmanager
def landing_world():
    state = random.getstate()
    random.seed(0)
    build = prepared_build(CharacterClass.WIZARD, 11)
    levels = tuple(replace(level, choices=tuple(
        replace(choice, values=('spell.conjure_elemental', choice.values[1]))
        if choice.choice_id == 'class.wizard.level_9.spellbook' else choice
        for choice in level.choices)) for level in build.class_levels)
    build = replace(build, class_levels=levels, prepared_spells=(
        PreparedSpellSelection('class.wizard.spellcasting', ('spell.conjure_elemental',)),))
    session = create_session(player_builds=(build,))
    try:
        caster = session.game.entities[session.player_uuids[0]]
        target = next(actor for actor in session.game.entities.values() if actor.position == (14, 10))
        session.seats['witness'] = PlayerAudience((), (target.uuid,))
        template = next(action for action in caster.registered_actions if isinstance(action, ConjureElemental))
        spell = template.instantiate(form_id='earth_myrmidon', cast_at_level=6, end_position=(11, 10))
        with fixed_dice_faces(*([2] * 300)):
            result = caster.perform(spell, spell.current_selection())
        assert result is not None and not result.canceled
        actor, = (member.entity for member in session.summoning.memberships.values())
        catalog = ui_content_manifest()
        audiences, _ = initialize_audiences(session, catalog)
        yield session, catalog, audiences, actor, target
    finally:
        close_session(session)
        random.setstate(state)


def burrow(actor):
    template, = (action for action in actor.registered_actions if isinstance(action, MyrmidonBurrow))
    action = template.instantiate(end_position=(13, 10))
    with fixed_dice_faces(*([2] * 300)):
        result = actor.perform(action, action.current_selection())
    assert result is not None and not result.canceled
    return result


def test_real_burrow_landing_identity_parentage_and_costs_reach_both_seats():
    with landing_world() as (session, catalog, audiences, actor, target):
        hp = target.get_hp()
        actions = actor.action_economy.actions.normalized_score
        registered = tuple(action.uuid for action in actor.registered_actions)
        cursor = EventQueue.event_cursor()
        result = burrow(actor)
        updates = capture_application_operation(audiences, operation_since(session, cursor), catalog)

        assert actor.position == (13, 10)
        assert actor.action_economy.bonus_actions.normalized_score == 0
        assert actor.action_economy.movement_spent() == 20
        assert actor.action_economy.actions.normalized_score == actions
        assert target.get_hp() == hp - 4
        assert tuple(action.uuid for action in actor.registered_actions) == registered

        landing, = (event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ActionEvent) and event.phase is EventPhase.COMPLETION
            and event.name == 'Burrow Landing' and event.parent_lineage == result.lineage_uuid)
        assert landing.behavior_id == 'action.earth_myrmidon.landing'
        assert landing.provided_by_id == 'action.earth_myrmidon.burrow'
        parent = EventQueue.get_event_by_uuid(landing.parent_event)
        assert parent is not None and parent.lineage_uuid == result.lineage_uuid

        assert len(updates) == 2
        for update in updates.values():
            public = PlayerUpdate.model_validate_json(update.model_dump_json())
            group, = (group for group in public.lineages if any(
                isinstance(node.fact, ActionFact) and node.fact.behavior_id == 'action.earth_myrmidon.burrow'
                for node in group.events))
            pairs = tuple(zip(group.events, node_lineages(group.events, group.version_rows), strict=True))
            parents = parent_lineages(group.events, group.version_rows)
            _, root = next((node, lineage) for node, lineage in pairs
                if isinstance(node.fact, ActionFact) and node.fact.behavior_id == 'action.earth_myrmidon.burrow')
            child, = (node for node, lineage in pairs if isinstance(node.fact, ActionFact)
                and node.fact.name == 'Burrow Landing' and parents.get(lineage) == root)
            assert child.fact.behavior_id == 'action.earth_myrmidon.landing'
            assert child.fact.source_entity_uuid == actor.uuid
            assert all(node.fact.behavior_id == 'action.earth_myrmidon.landing'
                for node in group.events if isinstance(node.fact, ActionFact)
                and node.fact.name == 'Burrow Landing')

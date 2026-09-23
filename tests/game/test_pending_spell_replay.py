"""Actual ten-spell commands remain sufficient after native and public replay."""

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.entity import Entity
from game.player_facts import ActionFact, DamageFact, MovementFact, SpellFact, StepFact, TemporaryHitPointsFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.pending_spell_scenarios import pending_spell_history


CASES = (
    ("inflict_wounds", {}), ("inflict_wounds", {"miss": True}),
    ("hellish_rebuke", {}), ("hellish_rebuke", {"saved": True}),
    ("shatter", {}), ("shatter", {"blocked": True}), ("shatter", {"raised": True}),
    ("misty_step", {}), ("misty_step", {"perspective": "departure"}),
    ("misty_step", {"perspective": "arrival"}),
    ("bless", {}), ("bane", {}),
    ("false_life", {}), ("false_life", {"replace_grant": True}),
    ("false_life", {"unrelated_grant": True}),
    ("jump", {}), ("jump", {"long_jump": True}), ("jump", {"raised": True}),
    ("expeditious_retreat", {}), ("haste", {}),
)


@pytest.mark.parametrize("program,options", CASES, ids=[name + "-" + "-".join(options) for name, options in CASES])
def test_real_spell_narratives_survive_both_observer_round_trips(program, options):
    history = pending_spell_history(program=program, **options)
    assert set(history.views) == {"caster", "witness" if program == "misty_step" else "target"}
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    for role, recorded in history.views.items():
        native = RecordedSequence.model_validate_json(recorded.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        packet = encode_player_sequence(project_sequence(native))
        before, roots = decode_player_sequence(packet)
        assert b"objective_rows" not in packet and b"identified_entity_observer_uuids" not in packet
        assert all(any(layer.item_id == "apparel.robes.red_mage" for layer in actor.visual_loadout.layers)
                   for actor in before.actors.values())
        state, states = before, []
        for root in roots:
            lineages = {event.lineage_uuid for event in root.events}
            assert all(child in lineages for event in root.events for child in event.children_lineages)
            state = reduce_lineage(state, root)
            states.append(state)
        facts = [node.fact for root in roots for node in root.events]
        spells = [fact for fact in facts if isinstance(fact, SpellFact)]
        actions = [fact for fact in facts if isinstance(fact, ActionFact)]
        actors = {actor.name: actor for actor in state.actors.values()}
        initial = {actor.name: actor for actor in before.actors.values()}
        caster = actors["Caster"].uuid
        if program != "hellish_rebuke":
            assert any(fact.behavior_id == "spell." + program for fact in spells), (program, role)
        if program == "inflict_wounds":
            assert actors["Target"].normal_hp == (120 if options.get("miss") else 108)
            released = [fact for fact in facts if isinstance(fact, DamageFact) and fact.body_release is not None]
            assert bool(released) is not bool(options.get("miss"))
            assert actors["Caster"].last_visual_position == initial["Caster"].last_visual_position
        elif program == "hellish_rebuke":
            reaction, = [node for root in roots for node in root.events
                if isinstance(node.fact, ActionFact) and node.fact.behavior_id == "reaction.spell.hellish_rebuke"]
            assert reaction.parent_event is not None
            assert actors["Caster"].normal_hp == 117
            assert actors["Target"].normal_hp == (114 if options.get("saved") else 108)
        elif program == "shatter":
            cast = next(fact for fact in spells if fact.application_id is None)
            assert cast.resolved_area_positions and cast.aoe_position == (6, 6)
            assert initial["Target"].normal_hp - actors["Target"].normal_hp == 12
            assert initial["Saved"].normal_hp - actors["Saved"].normal_hp == 6
            assert actors["Outside"].normal_hp == initial["Outside"].normal_hp
            if options.get("blocked"):
                assert (8, 6) not in cast.resolved_area_positions
        elif program in ("bless", "bane"):
            condition = "Bless" if program == "bless" else "Bane"
            affected = {actor.name for snapshot in states for actor in snapshot.actors.values()
                        if any(member.name == condition for member in actor.conditions)}
            assert affected == ({"Target", "Second", "Saved"} if program == "bless" else {"Target", "Second"})
            assert all(member.name != condition for actor in state.actors.values() for member in actor.conditions)
            assert actors["Target"].last_visual_position == (4, 8)
            assert actors["Second"].last_visual_position == (6, 7)
        elif program == "false_life":
            grants = [fact for fact in facts if isinstance(fact, TemporaryHitPointsFact) and fact.entity_uuid == caster]
            assert grants[0].resulting_temporary_hp == 6 and grants[0].grant is not None
            assert grants[0].grant.source_id == "spell.false_life"
            partial = next(snapshot.actors[caster] for snapshot in states if snapshot.actors[caster].temporary_hp == 3)
            assert partial.temporary_hp_grant == grants[0].grant
            if options.get("unrelated_grant"):
                assert actors["Caster"].temporary_hp == 12 and actors["Caster"].temporary_hp_grant is not None
                assert actors["Caster"].temporary_hp_grant.source_id is None
            elif options.get("replace_grant"):
                assert actors["Caster"].temporary_hp == 8
                assert actors["Caster"].temporary_hp_grant != grants[0].grant
                assert actors["Caster"].last_visual_position == (3, 8)
            else:
                assert actors["Caster"].temporary_hp == 0 and actors["Caster"].temporary_hp_grant is None
                assert actors["Caster"].normal_hp == 118
        elif program == "jump":
            jump, = [fact for fact in facts if isinstance(fact, MovementFact)]
            assert jump.start_position == (4, 6)
            assert jump.end_position == ((8, 6) if options.get("long_jump") else (6, 6))
            assert jump.end_elevation_feet == (10 if options.get("raised") else 0)
            assert actors["Target"].last_visual_position == jump.end_position
        elif program == "expeditious_retreat":
            assert any(action.behavior_id == "action.spell.expeditious_retreat.dash" for action in actions)
            assert {fact.resolved_speed_feet for fact in facts if isinstance(fact, StepFact)} == {30}
            assert actors["Caster"].last_visual_position == (6, 8)
            assert all(member.name != "Expeditious Retreat" for member in actors["Caster"].conditions)
        elif program == "haste":
            assert {fact.resolved_speed_feet for fact in facts if isinstance(fact, StepFact)} == {60}
            assert any(fact.behavior_id == "spell.fire_bolt" for fact in spells)
            assert actors["Target"].last_visual_position == (3, 5)
            assert all(member.name != "Haste" for member in actors["Target"].conditions)
        assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()

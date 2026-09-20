"""Native handoff narratives retain their mechanics in both saved player views."""

import pytest

from devtools.animation_review.cases import SpellHandoffCase, load_cases
from devtools.animation_review.produce import produce
from dnd.actions import AttackEvent, SpellEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import AttackOutcome
from dnd.core.events import EventQueue
from dnd.entity import Entity
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence


CASES = tuple(case for case in load_cases() if isinstance(case.scenario, SpellHandoffCase))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_native_spell_matrix_replays_both_subjective_views(case) -> None:
    captured = produce(case)
    scenario = case.scenario
    assert isinstance(scenario, SpellHandoffCase)
    assert set(captured.views) == {"caster", "perceiver"}
    native = captured.views["caster"]
    roots = [lineage.root for lineage in native.lineages if isinstance(lineage.root, SpellEvent)]
    assert len(roots) == (2 if scenario.repeat else 1)
    spell = roots[0]
    applications = [event for lineage in native.lineages for event in lineage.events
        if isinstance(event, SpellEvent) and event.application_id is not None]
    if scenario.program == "eldritch":
        count = 2 if scenario.level == 5 else 3
        assert len(applications) == count
        assert [event.application_index for event in applications] == list(range(count))
        assert len({event.application_id for event in applications}) == count
        assert len({event.target_entity_uuid for event in applications}) == (2 if scenario.split else 1)
        assert [event.attack_outcome for event in applications] == [
            AttackOutcome.CRIT_MISS if scenario.miss and index == 1 else AttackOutcome.HIT for index in range(count)]
    elif scenario.program == "guiding":
        assert spell.attack_outcome is (AttackOutcome.CRIT_MISS if scenario.miss else AttackOutcome.HIT)
        attacks = [event for lineage in native.lineages for event in lineage.events if isinstance(event, AttackEvent)]
        assert len(attacks) == (0 if scenario.miss else 1)
        if attacks:
            assert attacks[0].attack_outcome is AttackOutcome.HIT
    elif scenario.program == "acid":
        assert [event.save_success for event in applications] == [False, True]
        assert [event.total_damage for event in applications] == [6, 0]
    else:
        assert spell.resolved_area_positions
        assert (spell.total_targets == 0) is scenario.empty
        if scenario.environment != "open":
            behind = (6, 8) if scenario.environment == "wall-north" else (8, 6)
            assert (behind in spell.resolved_area_positions) is (scenario.environment == "open-door")

    for role, original in captured.views.items():
        restored = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        packet = encode_player_sequence(project_sequence(restored))
        state, lineages = decode_player_sequence(packet)
        caster = next(actor for actor in state.actors.values() if actor.name == "Caster")
        assert any(layer.item_id == "apparel.robes.red_mage" for layer in caster.visual_loadout.layers)
        if scenario.environment != "open":
            boundaries = [obj for obj in state.objects.values() if obj.item.boundary_structure is not None]
            assert boundaries, "The saved player initialization must retain the actual observed wall, not only its visibility shadow"
            incident = (6, 7) if scenario.environment == "wall-north" else (7, 6)
            assert any(obj.placement.position == incident for obj in boundaries)
        previous_ash = None
        witnessed_casts = 0
        marked_seen = False
        for lineage in lineages:
            state = reduce_lineage(state, lineage)
            fact = lineage.root.fact
            if isinstance(fact, SpellFact):
                witnessed_casts += 1
                assert fact.behavior_id == spell.behavior_id
                if scenario.program == "guiding" and not scenario.miss:
                    marked_seen = any(condition.name == "Guiding Bolt"
                        for actor in state.actors.values() for condition in actor.conditions)
                    assert marked_seen
                if scenario.program == "fireball":
                    assert fact.aoe_position == spell.aoe_position
                    assert fact.area_geometry == spell.area_geometry
                    ash = {position: tuple(residue.condition_uuid for residue in tile.residues
                        if residue.residue_id == "residue.ashen") for position, tile in state.tiles.items()
                        if any(residue.residue_id == "residue.ashen" for residue in tile.residues)}
                    assert ash and fact.aoe_position in ash
                    if previous_ash is not None:
                        assert ash == previous_ash, "Repeated area contact retains existing Ashen memberships"
                    previous_ash = ash
        assert witnessed_casts == len(roots), role
        if scenario.program == "guiding":
            assert marked_seen is not scenario.miss
            assert not any(condition.name == "Guiding Bolt" for actor in state.actors.values() for condition in actor.conditions)
        assert "objective_rows" not in packet.decode()
        assert "identified_entity_observer_uuids" not in packet.decode()
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()

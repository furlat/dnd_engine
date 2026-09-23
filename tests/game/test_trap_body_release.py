"""Actual trap review humanoids retain native blood releases through saved replay."""

from functools import partial

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.creature_types import DamageType
from dnd.core.events import DamageAppliedEvent, EventQueue
from dnd.entity import Entity
from game.player_facts import DamageFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.ground_contact_scenarios import ground_contact_history
from tests.game.mechanism_scenarios import mechanism_history
from tests.game.trap_expansion_scenarios import trap_expansion_history
from tests.game.trap_scenarios import trap_history


@pytest.mark.parametrize("make_history,types", (
    (partial(mechanism_history, program="darts"), {DamageType.PIERCING}),
    (partial(mechanism_history, program="blade"), {DamageType.SLASHING}),
    (partial(mechanism_history, program="crusher"), {DamageType.BLUDGEONING}),
    (partial(mechanism_history, program="darts", save=True), set()),
    (partial(trap_expansion_history, program="jaw"), {DamageType.PIERCING}),
    (partial(trap_expansion_history, program="jaw", save=True), set()),
    (partial(trap_expansion_history, program="tripwire"), {DamageType.PIERCING}),
    (partial(trap_expansion_history, program="gas"), {DamageType.POISON}),
    (partial(trap_history, payload="plain"), {DamageType.PIERCING}),
    (partial(trap_history, payload="poison-damage"), {DamageType.PIERCING, DamageType.POISON}),
    (ground_contact_history, {DamageType.PIERCING}),
))
def test_review_injuries_record_material_and_floor_state_for_both_observers(make_history, types):
    history = make_history()
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    for role, saved in history.views.items():
        native = RecordedSequence.model_validate_json(saved.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        injuries = {event.uuid: event for root in native.lineages for event in root.events
                    if isinstance(event, DamageAppliedEvent) and event.normal_hit_point_damage > 0}
        assert {event.damage_type for event in injuries.values()} == types, role
        assert all(event.body_release is not None for event in injuries.values()), role
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(native)))
        releases = {node.uuid: node.fact for root in roots for node in root.events
                    if isinstance(node.fact, DamageFact) and node.fact.body_release is not None}
        assert set(releases) == set(injuries), role
        for identity, release in releases.items():
            assert release.body_release is not None and release.body_release.release_id == "body.blood"
            assert release.body_release == injuries[identity].body_release
            assert release.damage_type == injuries[identity].damage_type
        for root in roots:
            state = reduce_lineage(state, root)
        assert any(residue.residue_id == "residue.blood" for tile in state.tiles.values()
                   for residue in tile.residues) is bool(types), role
        assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()

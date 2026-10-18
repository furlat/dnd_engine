"""A received group states each causal fact once (plan §3.6): a node's lineage is its version row's, a parent is
the node listing it among its children, and a target's spell application is folded with its cast's declaration."""

from uuid import uuid4

import pytest

from dnd.player.facts import PlayerNode, PlayerResolution, SpellFact, VersionRows
from dnd.player.reduction import check_spell_declarations, node_lineages, parent_lineages
from dnd.types.event_facts import EventPhase

CASTER, TARGET = uuid4(), uuid4()


def node(occurrence: int, *, children: tuple[int, ...] = (), parent: int | None = None,
         fact: SpellFact | None = None, resolution: int | None = None) -> PlayerNode:
    return PlayerNode(occurrence=occurrence, children_lineages=children, parent_lineage=parent,
        phase=EventPhase.COMPLETION, fact=fact, resolution=resolution)


def test_a_node_lineage_is_its_version_row_and_a_parent_the_node_listing_it():
    # Lineage 10 (occurrences 10, 13) lists lineage 11; lineage 12's parent sits in an earlier group (lineage 3).
    nodes = (node(10, children=(11,)), node(11), node(12, parent=3), node(13, children=(11,)))
    versions = VersionRows(occurrences=(10, 11, 12, 13), lineages=(10, 11, 12, 10))
    assert node_lineages(nodes, versions) == (10, 11, 12, 10)
    assert parent_lineages(nodes, versions) == {11: 10, 12: 3}


def test_an_application_is_folded_with_its_casts_declaration():
    cast = SpellFact(source_entity_uuid=CASTER, target_entity_uuid=None, behavior_id="spell.fireball",
        name="Fireball", cast_origin="actor", area_propagation="line_of_effect")
    application = SpellFact(target_entity_uuid=TARGET)
    resolutions = (PlayerResolution(lineage=20, application_id=uuid4()),)
    versions = VersionRows(occurrences=(20, 21), lineages=(20, 21))
    group = (node(20, children=(21,), fact=cast), node(21, fact=application, resolution=0))
    check_spell_declarations(group, versions, resolutions)
    with pytest.raises(ValueError, match="carries its cast's declaration"):
        check_spell_declarations(group[1:], VersionRows(occurrences=(21,), lineages=(21,)), resolutions)
